"""Agent registry — CRUD operations for roster and agent_runs tables."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from typing import Any

from backend.agents.base import PabadaAgent
from backend.prompts.team import generate_agent_name
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

# Lazy import map: role -> (module_path, factory_function_name)
_ROLE_FACTORIES: dict[str, tuple[str, str]] = {
    "project_lead": ("backend.agents.project_lead", "create_project_lead_agent"),
    "team_lead": ("backend.agents.team_lead", "create_team_lead_agent"),
    "developer": ("backend.agents.developer", "create_developer_agent"),
    "code_reviewer": ("backend.agents.code_reviewer", "create_code_reviewer_agent"),
    "researcher": ("backend.agents.researcher", "create_researcher_agent"),
    "research_reviewer": ("backend.agents.research_reviewer", "create_research_reviewer_agent"),
}

VALID_ROLES = frozenset(_ROLE_FACTORIES)


# Default team composition: role -> number of instances.
# Single-instance roles (project_lead, team_lead) get 1 agent.
# Multi-instance roles get 2+ agents that can work concurrently.
DEFAULT_TEAM_COMPOSITION: dict[str, int] = {
    "project_lead": 1,
    "team_lead": 1,
    "developer": 3,
    "code_reviewer": 2,
    "researcher": 2,
    "research_reviewer": 2,
}


def _import_factory(role: str):
    """Dynamically import the factory function for *role*."""
    module_path, func_name = _ROLE_FACTORIES[role]
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)


# ── Roster operations ─────────────────────────────────────────────────────


def register_agent(agent_id: str, name: str, role: str) -> None:
    """Insert or update an agent in the ``roster`` table."""
    if role not in VALID_ROLES:
        raise ValueError(f"Unknown role '{role}'. Valid: {sorted(VALID_ROLES)}")

    def _upsert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO roster (agent_id, name, role, status, created_at)
               VALUES (?, ?, ?, 'idle', CURRENT_TIMESTAMP)
               ON CONFLICT(agent_id) DO UPDATE SET
                   name = excluded.name,
                   role = excluded.role,
                   last_active_at = CURRENT_TIMESTAMP""",
            (agent_id, name, role),
        )
        conn.commit()

    execute_with_retry(_upsert)
    logger.info("Registered agent %s (%s) in roster", agent_id, role)


def update_agent_status(agent_id: str, status: str) -> None:
    """Update ``roster.status`` and ``roster.last_active_at``."""
    valid = {"idle", "active", "retired"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Valid: {sorted(valid)}")

    def _update(conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE roster SET status = ?, last_active_at = CURRENT_TIMESTAMP WHERE agent_id = ?",
            (status, agent_id),
        )
        conn.commit()

    execute_with_retry(_update)


def get_roster_for_project(project_id: int) -> list[dict[str, str]]:
    """Return all roster entries for a project.

    Uses the agent_id naming convention ``{role}_p{project_id}`` to filter.
    Returns a list of dicts with keys: agent_id, name, role, status.
    """
    suffix = f"_p{project_id}"

    def _query(conn: sqlite3.Connection) -> list[dict[str, str]]:
        rows = conn.execute(
            "SELECT agent_id, name, role, status FROM roster "
            "WHERE agent_id LIKE ? ESCAPE '\\' AND status != 'retired'",
            (f"%\\_p{project_id}",),
        ).fetchall()
        return [
            {"agent_id": r["agent_id"], "name": r["name"],
             "role": r["role"], "status": r["status"]}
            for r in rows
        ]

    return execute_with_retry(_query)


def get_existing_agent_name(agent_id: str) -> str | None:
    """Return the name of an existing agent, or None if not registered."""

    def _query(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT name FROM roster WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        return row["name"] if row else None

    return execute_with_retry(_query)


def _resolve_agent_name(agent_id: str, project_id: int) -> str:
    """Get the agent's existing name from the roster, or generate a new one.

    If the agent already exists in the roster, reuse its name for consistency.
    Otherwise, generate a random name that doesn't collide with other agents
    in the same project.
    """
    existing_name = get_existing_agent_name(agent_id)
    if existing_name:
        return existing_name

    # Get names already in use in this project
    roster = get_roster_for_project(project_id)
    used_names = {entry["name"] for entry in roster}
    return generate_agent_name(used_names)


def _get_teammates(agent_id: str, project_id: int) -> list[dict[str, str]]:
    """Return roster entries for all OTHER agents in this project."""
    roster = get_roster_for_project(project_id)
    return [entry for entry in roster if entry["agent_id"] != agent_id]


def _make_agent_id(role: str, project_id: int, instance: int = 1) -> str:
    """Build a deterministic agent_id.

    Single-instance roles: ``{role}_p{project_id}``  (e.g. ``project_lead_p1``)
    Multi-instance roles:  ``{role}_{n}_p{project_id}`` (e.g. ``developer_1_p1``)
    """
    count = DEFAULT_TEAM_COMPOSITION.get(role, 1)
    if count <= 1:
        return f"{role}_p{project_id}"
    return f"{role}_{instance}_p{project_id}"


# ── Team initialization ──────────────────────────────────────────────────


def initialize_project_team(
    project_id: int,
    composition: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    """Create and register the full agent team for a project.

    Registers agents in the roster so they show up immediately in the UI.
    Does NOT instantiate full PabadaAgent objects (which need an LLM) — only
    creates roster entries with names, roles, and idle status.

    Returns the list of created roster entries.
    """
    comp = composition or DEFAULT_TEAM_COMPOSITION
    created: list[dict[str, str]] = []

    # Gather existing names to avoid collisions
    existing_roster = get_roster_for_project(project_id)
    used_names = {entry["name"] for entry in existing_roster}
    existing_ids = {entry["agent_id"] for entry in existing_roster}

    for role, count in comp.items():
        if role not in VALID_ROLES:
            logger.warning("Skipping unknown role '%s' in team composition", role)
            continue

        for instance in range(1, count + 1):
            agent_id = _make_agent_id(role, project_id, instance)

            # If already registered, ensure role is correct (may have
            # been stored with the wrong role from a previous bug).
            if agent_id in existing_ids:
                existing_entry = next(
                    e for e in existing_roster if e["agent_id"] == agent_id
                )
                if existing_entry["role"] != role:
                    logger.warning(
                        "Fixing role mismatch for %s: %s → %s",
                        agent_id, existing_entry["role"], role,
                    )
                    register_agent(agent_id, existing_entry["name"], role)
                    existing_entry = {**existing_entry, "role": role}
                created.append(existing_entry)
                continue

            name = generate_agent_name(used_names)
            used_names.add(name)

            register_agent(agent_id, name, role)
            entry = {
                "agent_id": agent_id,
                "name": name,
                "role": role,
                "status": "idle",
            }
            created.append(entry)

    logger.info(
        "Initialized team for project %d: %d agents (%s)",
        project_id, len(created),
        ", ".join(f"{r}={c}" for r, c in comp.items()),
    )
    return created


# ── Agent instantiation ──────────────────────────────────────────────────


def get_agent_by_role(
    role: str,
    project_id: int,
    *,
    agent_id: str | None = None,
    llm: Any | None = None,
    knowledge_service: Any | None = None,
    tech_hints: list[str] | None = None,
) -> PabadaAgent:
    """Return a ``PabadaAgent`` for *role*, creating and registering it if needed.

    If *agent_id* is ``None`` a deterministic id is generated from the role
    and project.  For single-instance roles this is ``{role}_p{project_id}``.
    For multi-instance roles, prefer ``get_available_agent_by_role`` instead.

    The agent receives:
    - A randomly generated name (persisted across re-creations).
    - The live team roster so it knows about its teammates.

    Optional *knowledge_service* is forwarded to the agent factory for roles
    that support it (researcher, research_reviewer).
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Unknown role '{role}'. Valid: {sorted(VALID_ROLES)}")

    if agent_id is None:
        agent_id = _make_agent_id(role, project_id)

    # Resolve name: reuse existing or generate new
    agent_name = _resolve_agent_name(agent_id, project_id)

    # Get current teammates from the roster
    teammates = _get_teammates(agent_id, project_id)

    factory = _import_factory(role)

    # Forward knowledge/memory services only to factories that accept them
    _ROLES_WITH_KNOWLEDGE = {"researcher", "research_reviewer"}
    _ROLES_WITH_TECH = {"developer"}

    kwargs: dict[str, Any] = {
        "llm": llm,
        "agent_name": agent_name,
        "teammates": teammates,
    }
    if role in _ROLES_WITH_KNOWLEDGE:
        if knowledge_service is not None:
            kwargs["knowledge_service"] = knowledge_service
    if role in _ROLES_WITH_TECH and tech_hints is not None:
        kwargs["tech_hints"] = tech_hints

    agent: PabadaAgent = factory(agent_id, project_id, **kwargs)
    agent.register_in_roster()
    return agent


def get_available_agent_by_role(
    role: str,
    project_id: int,
    *,
    llm: Any | None = None,
    knowledge_service: Any | None = None,
    tech_hints: list[str] | None = None,
) -> PabadaAgent:
    """Return an idle agent of the given *role*, or create a default one.

    For multi-instance roles (developer, researcher, etc.) picks the agent
    with status ``idle``.  If all are busy, falls back to the first instance.
    For single-instance roles, behaves like ``get_agent_by_role``.
    """
    roster = get_roster_for_project(project_id)
    role_agents = [a for a in roster if a["role"] == role]

    # Pick an idle agent, preferring lower instance numbers
    chosen_id = None
    for agent_entry in role_agents:
        if agent_entry["status"] == "idle":
            chosen_id = agent_entry["agent_id"]
            break

    # Fallback: first agent of this role, or generate default
    if chosen_id is None and role_agents:
        chosen_id = role_agents[0]["agent_id"]

    return get_agent_by_role(
        role, project_id,
        agent_id=chosen_id,
        llm=llm,
        knowledge_service=knowledge_service,
        tech_hints=tech_hints,
    )


def get_all_agents(
    project_id: int,
    *,
    llm: Any | None = None,
) -> dict[str, PabadaAgent]:
    """Return a dict ``{role: PabadaAgent}`` with one agent per role."""
    return {
        role: get_agent_by_role(role, project_id, llm=llm)
        for role in VALID_ROLES
    }


# ── Agent run tracking ───────────────────────────────────────────────────


def create_agent_run_record(
    agent_id: str,
    project_id: int,
    task_id: int,
    role: str,
) -> str:
    """Insert a row in ``agent_runs`` and return the ``agent_run_id``."""
    agent_run_id = str(uuid.uuid4())

    def _insert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO agent_runs
                   (project_id, agent_run_id, agent_id, task_id, role, status, started_at)
               VALUES (?, ?, ?, ?, ?, 'running', CURRENT_TIMESTAMP)""",
            (project_id, agent_run_id, agent_id, task_id, role),
        )
        conn.execute(
            """UPDATE roster
                  SET status = 'active',
                      total_runs = total_runs + 1,
                      last_active_at = CURRENT_TIMESTAMP
                WHERE agent_id = ?""",
            (agent_id,),
        )
        conn.commit()

    execute_with_retry(_insert)
    logger.info("Created agent_run %s for %s", agent_run_id, agent_id)
    return agent_run_id


def complete_agent_run(
    agent_run_id: str,
    *,
    status: str = "completed",
    output_summary: str = "",
    tokens_used: int = 0,
    error_class: str | None = None,
) -> None:
    """Mark an ``agent_run`` as finished and update performance metrics."""
    valid_statuses = {"completed", "failed", "timeout"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Valid: {sorted(valid_statuses)}")

    def _finish(conn: sqlite3.Connection) -> None:
        # Read agent_id and role directly from agent_runs
        row = conn.execute(
            "SELECT agent_id, role FROM agent_runs WHERE agent_run_id = ?",
            (agent_run_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"No agent_run found with id '{agent_run_id}'")
        run_agent_id = row["agent_id"]
        role = row["role"]

        conn.execute(
            """UPDATE agent_runs
                  SET status = ?, output_summary = ?,
                      tokens_used = ?, error_class = ?,
                      ended_at = CURRENT_TIMESTAMP
                WHERE agent_run_id = ?""",
            (status, output_summary, tokens_used, error_class, agent_run_id),
        )

        # Update agent_performance
        if status == "completed":
            conn.execute(
                """INSERT INTO agent_performance
                       (agent_id, role, total_runs, successful_runs, total_tokens, last_updated_at)
                   VALUES (?, ?, 1, 1, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       total_runs = total_runs + 1,
                       successful_runs = successful_runs + 1,
                       total_tokens = total_tokens + excluded.total_tokens,
                       last_updated_at = CURRENT_TIMESTAMP""",
                (run_agent_id, role, tokens_used),
            )
        else:
            conn.execute(
                """INSERT INTO agent_performance
                       (agent_id, role, total_runs, failed_runs, total_tokens, last_updated_at)
                   VALUES (?, ?, 1, 1, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       total_runs = total_runs + 1,
                       failed_runs = failed_runs + 1,
                       total_tokens = total_tokens + excluded.total_tokens,
                       last_updated_at = CURRENT_TIMESTAMP""",
                (run_agent_id, role, tokens_used),
            )

        # Return roster to idle
        conn.execute(
            "UPDATE roster SET status = 'idle', last_active_at = CURRENT_TIMESTAMP WHERE agent_id = ?",
            (run_agent_id,),
        )
        conn.commit()

    execute_with_retry(_finish)
    logger.info("Completed agent_run %s with status=%s", agent_run_id, status)

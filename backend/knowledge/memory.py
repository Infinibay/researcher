"""AgentMemoryService — persistent memory lifecycle for agents."""

from __future__ import annotations

import logging
import sqlite3

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """Handles loading and persisting agent memory across runs.

    Memory comes from two sources:
    1. ``roster.memory`` — free-form text stored per agent
    2. ``knowledge`` table — structured key/value entries per agent
    """

    @staticmethod
    def load_agent_memory(agent_id: str, project_id: int) -> str:
        """Load combined memory for an agent.

        Returns a formatted string combining roster memory and
        structured knowledge entries. Returns empty string if nothing found.
        """

        def _load(conn: sqlite3.Connection) -> dict:
            # 1. Load roster.memory
            row = conn.execute(
                "SELECT memory FROM roster WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            roster_memory = row["memory"] if row and row["memory"] else ""

            # 2. Load knowledge entries
            knowledge_rows = conn.execute(
                """SELECT category, key, value
                   FROM knowledge
                   WHERE agent_id = ?
                   ORDER BY category, key""",
                (agent_id,),
            ).fetchall()
            knowledge_entries = [dict(r) for r in knowledge_rows]

            return {
                "roster_memory": roster_memory,
                "knowledge_entries": knowledge_entries,
            }

        try:
            data = execute_with_retry(_load)
        except Exception:
            logger.exception("Failed to load memory for agent %s", agent_id)
            return ""

        roster_memory = data["roster_memory"]
        knowledge_entries = data["knowledge_entries"]

        if not roster_memory and not knowledge_entries:
            return ""

        parts = ["## Agent Memory"]

        if roster_memory:
            parts.append("### Persistent Notes")
            parts.append(roster_memory)

        if knowledge_entries:
            parts.append("### Stored Knowledge")
            for entry in knowledge_entries:
                parts.append(
                    f"{entry['category']}/{entry['key']}: {entry['value']}"
                )

        return "\n".join(parts)

    @staticmethod
    def persist_agent_memory(agent_id: str, memory_text: str) -> None:
        """Persist free-form memory text to the ``roster.memory`` column."""

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE roster SET memory = ? WHERE agent_id = ?",
                (memory_text, agent_id),
            )
            conn.commit()

        try:
            execute_with_retry(_update)
            logger.info("Persisted memory for agent %s", agent_id)
        except Exception:
            logger.exception("Failed to persist memory for agent %s", agent_id)

    @staticmethod
    def build_memory_context_for_backstory(
        agent_id: str, project_id: int
    ) -> str:
        """Load agent memory and wrap it for backstory injection.

        Returns a string suitable for appending to an agent's backstory.
        Returns empty string if no memory exists, so it doesn't pollute
        the backstory on first run.
        """
        memory = AgentMemoryService.load_agent_memory(agent_id, project_id)
        if not memory:
            return ""

        return (
            "\n\n---\n"
            "# Previous Session Memory\n"
            "The following is your memory from previous runs. "
            "Use this context to maintain continuity.\n\n"
            f"{memory}\n"
        )

"""LoopGuard — infrastructure guardrails against agent communication loops.

Central stateless service that intercepts every outgoing message.
Runs checks in order (cheapest first), returns first non-allow verdict.

Checks:
1. Circuit Breaker — single row lookup, block if open
2. Rate Limiting — per-thread and per-agent global caps
3. Deduplication — SHA-256 fingerprint + trigram similarity
4. Ping-Pong Detection — alternating agent pattern in thread
5. Thread Context Summary — inject prior history for agent awareness
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.config.settings import settings
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


@dataclass
class LoopGuardVerdict:
    """Result of LoopGuard.check_all()."""

    allowed: bool = True
    reason: str = ""
    action: str = "allow"  # allow | block | throttle | escalate
    delay_seconds: float = 0.0
    context_summary: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fingerprint(text: str) -> str:
    """SHA-256 hex digest of normalised text."""
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _trigram_set(text: str) -> set[str]:
    """Character trigrams for Jaccard similarity."""
    t = _normalize_text(text)
    if len(t) < 3:
        return {t}
    return {t[i : i + 3] for i in range(len(t) - 2)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ── LoopGuard ────────────────────────────────────────────────────────────────


class LoopGuard:
    """Stateless guard that checks every outgoing message for loop patterns."""

    # ── Public API ───────────────────────────────────────────────────────

    def check_all(
        self,
        from_agent: str,
        message: str,
        to_agent: str | None = None,
        to_role: str | None = None,
        thread_id: str | None = None,
        project_id: int | None = None,
    ) -> LoopGuardVerdict:
        """Run all checks in order. Return first non-allow verdict."""
        if not settings.LOOP_GUARD_ENABLED:
            return LoopGuardVerdict()

        # System messages bypass all checks
        if from_agent == "system":
            return LoopGuardVerdict()

        # Brainstorming threads bypass all loop checks — the flow has its
        # own round/time limits so LoopGuard is redundant.
        if thread_id and self._is_brainstorming_thread(thread_id):
            return LoopGuardVerdict()

        checks = [
            self._check_circuit_breaker,
            self._check_rate_limit,
            self._check_dedup,
            self._check_ping_pong,
            self._check_pair_exchange,
        ]

        for check_fn in checks:
            verdict = check_fn(
                from_agent=from_agent,
                message=message,
                to_agent=to_agent,
                to_role=to_role,
                thread_id=thread_id,
                project_id=project_id,
            )
            if verdict.action != "allow":
                # Increment circuit breaker failure count on block/throttle
                if verdict.action in ("block", "throttle", "escalate"):
                    self._increment_circuit_breaker(thread_id)
                # Record incident
                if verdict.action in ("block", "escalate"):
                    self._record_incident(
                        project_id=project_id,
                        incident_type=verdict.reason.split(":")[0].strip().lower().replace(" ", "_")
                        if verdict.reason else "unknown",
                        thread_id=thread_id,
                        agents_involved=[from_agent, to_agent or to_role or ""],
                        action_taken="blocked" if verdict.action == "block" else "escalated_to_user",
                        details=verdict.reason,
                    )
                return verdict

        # Build thread context summary if thread has enough messages
        context = self._build_context_summary(thread_id, from_agent)
        return LoopGuardVerdict(context_summary=context)

    def record_fingerprint(
        self,
        message_id: int,
        message: str,
        from_agent: str,
        to_agent: str | None = None,
        to_role: str | None = None,
        thread_id: str | None = None,
        project_id: int | None = None,
    ) -> None:
        """Record a message fingerprint after successful send."""
        fp = _fingerprint(message)

        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO message_fingerprints
                   (message_id, project_id, from_agent, to_agent, to_role,
                    thread_id, fingerprint)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (message_id, project_id, from_agent, to_agent, to_role,
                 thread_id, fp),
            )
            conn.commit()

        try:
            execute_with_retry(_insert)
        except Exception:
            logger.debug("Failed to record fingerprint for message %d", message_id)

    def escalate_loop(
        self,
        project_id: int | None,
        thread_id: str | None,
        agents: list[str],
        reason: str,
    ) -> None:
        """Create a loop incident and emit event for external callers."""
        self._record_incident(
            project_id=project_id,
            incident_type="ping_pong",
            thread_id=thread_id,
            agents_involved=agents,
            action_taken="escalated_to_user",
            details=reason,
        )
        # Post system notice
        self._post_system_notice(project_id, reason)

    # ── Brainstorming thread helper ─────────────────────────────────────

    @staticmethod
    def _is_brainstorming_thread(thread_id: str) -> bool:
        """Check if thread_id belongs to a brainstorming thread."""

        def _query(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                "SELECT thread_type FROM conversation_threads WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            return row is not None and row["thread_type"] == "brainstorming"

        try:
            return execute_with_retry(_query)
        except Exception:
            return False

    # ── Check: Circuit Breaker ───────────────────────────────────────────

    def _check_circuit_breaker(self, *, thread_id, **_kw) -> LoopGuardVerdict:
        if not thread_id:
            return LoopGuardVerdict()

        cb_key = f"comm:{thread_id}"

        def _query(conn: sqlite3.Connection) -> dict | None:
            row = conn.execute(
                "SELECT state, opened_at, window_seconds FROM circuit_breaker WHERE task_type = ?",
                (cb_key,),
            ).fetchone()
            return dict(row) if row else None

        cb = execute_with_retry(_query)
        if cb is None:
            return LoopGuardVerdict()

        state = cb["state"]
        if state == "open":
            # Check cooldown
            opened_at = cb.get("opened_at", "")
            cooldown = settings.LOOP_CIRCUIT_COOLDOWN
            if opened_at:
                try:
                    opened_dt = datetime.fromisoformat(opened_at)
                    elapsed = (datetime.now(timezone.utc) - opened_dt.replace(tzinfo=timezone.utc)).total_seconds()
                    if elapsed >= cooldown:
                        self._transition_circuit_breaker(cb_key, "half_open")
                        return LoopGuardVerdict()  # Allow one through
                except (ValueError, TypeError):
                    pass
            return LoopGuardVerdict(
                allowed=False,
                reason="circuit_open: communication circuit breaker is open for this thread",
                action="block",
            )
        elif state == "half_open":
            # Allow one message through (will be reset on success or re-opened on failure)
            return LoopGuardVerdict()

        return LoopGuardVerdict()

    # ── Check: Rate Limiting ─────────────────────────────────────────────

    def _check_rate_limit(self, *, from_agent, thread_id, **_kw) -> LoopGuardVerdict:
        now_ts = time.time()

        def _query(conn: sqlite3.Connection) -> dict:
            thread_count = 0
            if thread_id:
                row = conn.execute(
                    """SELECT COUNT(*) as cnt FROM message_fingerprints
                       WHERE thread_id = ? AND from_agent = ?
                         AND created_at > datetime('now', ?)""",
                    (thread_id, from_agent, f"-{settings.LOOP_RATE_PER_THREAD_WINDOW} seconds"),
                ).fetchone()
                thread_count = row["cnt"] if row else 0

            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM message_fingerprints
                   WHERE from_agent = ?
                     AND created_at > datetime('now', ?)""",
                (from_agent, f"-{settings.LOOP_RATE_GLOBAL_WINDOW} seconds"),
            ).fetchone()
            global_count = row["cnt"] if row else 0

            return {"thread": thread_count, "global": global_count}

        counts = execute_with_retry(_query)

        if thread_id and counts["thread"] >= settings.LOOP_RATE_PER_THREAD:
            delay = min(5.0, 1.0 * (counts["thread"] - settings.LOOP_RATE_PER_THREAD + 1))
            return LoopGuardVerdict(
                allowed=False,
                reason=f"rate_limit: {counts['thread']} messages in thread within {settings.LOOP_RATE_PER_THREAD_WINDOW}s (max {settings.LOOP_RATE_PER_THREAD})",
                action="throttle",
                delay_seconds=delay,
            )

        if counts["global"] >= settings.LOOP_RATE_GLOBAL:
            delay = min(10.0, 2.0 * (counts["global"] - settings.LOOP_RATE_GLOBAL + 1))
            return LoopGuardVerdict(
                allowed=False,
                reason=f"rate_limit: {counts['global']} messages globally within {settings.LOOP_RATE_GLOBAL_WINDOW}s (max {settings.LOOP_RATE_GLOBAL})",
                action="throttle",
                delay_seconds=delay,
            )

        return LoopGuardVerdict()

    # ── Check: Deduplication ─────────────────────────────────────────────

    def _check_dedup(self, *, from_agent, message, to_agent, to_role, **_kw) -> LoopGuardVerdict:
        fp = _fingerprint(message)
        window = settings.LOOP_DEDUP_WINDOW_SECONDS

        def _query(conn: sqlite3.Connection) -> dict:
            # Exact fingerprint match
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM message_fingerprints
                   WHERE from_agent = ? AND fingerprint = ?
                     AND created_at > datetime('now', ?)""",
                (from_agent, fp, f"-{window} seconds"),
            ).fetchone()
            exact_count = row["cnt"] if row else 0

            # Get recent messages for similarity check (only if message > 20 chars)
            similar_texts: list[str] = []
            if len(message) > 20:
                rows = conn.execute(
                    """SELECT cm.message FROM message_fingerprints mf
                       JOIN chat_messages cm ON mf.message_id = cm.id
                       WHERE mf.from_agent = ?
                         AND mf.created_at > datetime('now', ?)
                       ORDER BY mf.created_at DESC LIMIT 10""",
                    (from_agent, f"-{window} seconds"),
                ).fetchall()
                similar_texts = [r["message"] for r in rows]

            return {"exact": exact_count, "texts": similar_texts}

        result = execute_with_retry(_query)

        if result["exact"] > 0:
            return LoopGuardVerdict(
                allowed=False,
                reason="duplicate_message: exact duplicate message detected within dedup window",
                action="block",
            )

        # Near-duplicate check via trigram Jaccard similarity
        if len(message) > 20 and result["texts"]:
            msg_trigrams = _trigram_set(message)
            threshold = settings.LOOP_DEDUP_SIMILARITY_THRESHOLD
            for prev_text in result["texts"]:
                if len(prev_text) > 20:
                    sim = _jaccard(msg_trigrams, _trigram_set(prev_text))
                    if sim >= threshold:
                        return LoopGuardVerdict(
                            allowed=False,
                            reason=f"duplicate_message: near-duplicate detected (similarity={sim:.2f} >= {threshold})",
                            action="block",
                        )

        return LoopGuardVerdict()

    # ── Check: Ping-Pong Detection ───────────────────────────────────────

    def _check_ping_pong(self, *, from_agent, thread_id, **_kw) -> LoopGuardVerdict:
        if not thread_id:
            return LoopGuardVerdict()

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT from_agent FROM chat_messages
                   WHERE thread_id = ?
                   ORDER BY created_at DESC LIMIT 10""",
                (thread_id,),
            ).fetchall()
            return [{"from_agent": r["from_agent"]} for r in rows]

        recent = execute_with_retry(_query)
        if len(recent) < settings.LOOP_PING_PONG_THRESHOLD:
            return LoopGuardVerdict()

        # Check alternating pattern between 2 agents
        agents = [m["from_agent"] for m in recent]
        unique_agents = set(agents[:settings.LOOP_PING_PONG_THRESHOLD])
        if len(unique_agents) == 2:
            # Check if strictly alternating
            is_alternating = all(
                agents[i] != agents[i + 1]
                for i in range(min(len(agents) - 1, settings.LOOP_PING_PONG_THRESHOLD - 1))
            )
            if is_alternating:
                agent_list = list(unique_agents)
                return LoopGuardVerdict(
                    allowed=False,
                    reason=f"ping_pong: detected {settings.LOOP_PING_PONG_THRESHOLD}+ alternating exchanges between {agent_list[0]} and {agent_list[1]}",
                    action="escalate",
                )

        # Check repeated fingerprint from same agent
        def _fp_query(conn: sqlite3.Connection) -> int:
            rows = conn.execute(
                """SELECT fingerprint, COUNT(*) as cnt
                   FROM message_fingerprints
                   WHERE thread_id = ? AND from_agent = ?
                     AND created_at > datetime('now', '-300 seconds')
                   GROUP BY fingerprint
                   HAVING cnt >= ?""",
                (thread_id, from_agent, settings.LOOP_REPEAT_THRESHOLD),
            ).fetchall()
            return len(rows)

        repeat_count = execute_with_retry(_fp_query)
        if repeat_count > 0:
            return LoopGuardVerdict(
                allowed=False,
                reason=f"ping_pong: same message fingerprint repeated {settings.LOOP_REPEAT_THRESHOLD}+ times by {from_agent}",
                action="escalate",
            )

        return LoopGuardVerdict()

    # ── Check: Pair Exchange Volume ──────────────────────────────────────

    def _check_pair_exchange(
        self, *, from_agent, to_agent, project_id, **_kw
    ) -> LoopGuardVerdict:
        """Detect excessive back-and-forth between a specific pair of agents.

        Unlike ping-pong (which checks alternating pattern in a single thread),
        this counts total messages exchanged between the same two agents across
        ALL threads within a time window.  Catches topic-based loops where
        content differs each time but the agents keep discussing the same issue.
        """
        if not to_agent or not project_id:
            return LoopGuardVerdict()

        window = settings.LOOP_PAIR_EXCHANGE_WINDOW
        limit = settings.LOOP_PAIR_EXCHANGE_MAX

        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM chat_messages
                   WHERE ((from_agent = ? AND to_agent = ?)
                       OR (from_agent = ? AND to_agent = ?))
                     AND project_id = ?
                     AND created_at > datetime('now', ?)""",
                (
                    from_agent, to_agent,
                    to_agent, from_agent,
                    project_id,
                    f"-{window} seconds",
                ),
            ).fetchone()
            return row["cnt"] if row else 0

        try:
            count = execute_with_retry(_query)
        except Exception:
            return LoopGuardVerdict()

        if count >= limit:
            return LoopGuardVerdict(
                allowed=False,
                reason=(
                    f"pair_exchange: {count} messages exchanged between "
                    f"{from_agent} and {to_agent} in {window}s (max {limit}). "
                    "Stop messaging this agent — proceed with your best judgment "
                    "or escalate to the user."
                ),
                action="escalate",
            )

        return LoopGuardVerdict()

    # ── Context Summary Builder ──────────────────────────────────────────

    def _build_context_summary(self, thread_id: str | None, from_agent: str) -> str:
        """Build compact thread history if >= 5 messages exist."""
        if not thread_id:
            return ""

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT from_agent, message, created_at FROM chat_messages
                   WHERE thread_id = ?
                   ORDER BY created_at DESC LIMIT 10""",
                (thread_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        messages = execute_with_retry(_query)
        if len(messages) < 5:
            return ""

        lines = ["[Thread History — do NOT re-ask questions already answered here]"]
        for msg in reversed(messages):
            sender = msg["from_agent"]
            text = msg["message"][:200]
            lines.append(f"- {sender}: {text}")

        return "\n".join(lines)

    # ── Circuit Breaker Management ───────────────────────────────────────

    def _increment_circuit_breaker(self, thread_id: str | None) -> None:
        if not thread_id:
            return

        cb_key = f"comm:{thread_id}"

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO circuit_breaker (task_type, state, failure_count, last_failure_at, threshold, window_seconds)
                   VALUES (?, 'closed', 1, CURRENT_TIMESTAMP, ?, ?)
                   ON CONFLICT(task_type) DO UPDATE SET
                     failure_count = failure_count + 1,
                     last_failure_at = CURRENT_TIMESTAMP""",
                (cb_key, settings.LOOP_CIRCUIT_THRESHOLD, settings.LOOP_CIRCUIT_COOLDOWN),
            )
            # Check if threshold reached → open the breaker
            row = conn.execute(
                "SELECT failure_count, threshold FROM circuit_breaker WHERE task_type = ?",
                (cb_key,),
            ).fetchone()
            if row and row["failure_count"] >= row["threshold"]:
                conn.execute(
                    """UPDATE circuit_breaker
                       SET state = 'open', opened_at = CURRENT_TIMESTAMP
                       WHERE task_type = ?""",
                    (cb_key,),
                )
            conn.commit()

        try:
            execute_with_retry(_update)
        except Exception:
            logger.debug("Failed to update circuit breaker for %s", cb_key)

    def _transition_circuit_breaker(self, cb_key: str, new_state: str) -> None:
        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE circuit_breaker SET state = ? WHERE task_type = ?",
                (new_state, cb_key),
            )
            if new_state == "closed":
                conn.execute(
                    "UPDATE circuit_breaker SET failure_count = 0 WHERE task_type = ?",
                    (cb_key,),
                )
            conn.commit()

        try:
            execute_with_retry(_update)
        except Exception:
            logger.debug("Failed to transition circuit breaker %s to %s", cb_key, new_state)

    def reset_circuit_breaker(self, thread_id: str) -> None:
        """Reset circuit breaker on successful communication (external API)."""
        cb_key = f"comm:{thread_id}"
        self._transition_circuit_breaker(cb_key, "closed")

    # ── Incident Recording ───────────────────────────────────────────────

    def _record_incident(
        self,
        project_id: int | None,
        incident_type: str,
        thread_id: str | None,
        agents_involved: list[str],
        action_taken: str,
        details: str = "",
    ) -> None:
        # Normalise incident_type to valid enum values
        valid_types = {"duplicate_message", "rate_limit", "ping_pong", "circuit_open", "question_budget", "pair_exchange"}
        if incident_type not in valid_types:
            incident_type = "duplicate_message"  # default fallback

        valid_actions = {"blocked", "throttled", "escalated_to_user", "circuit_opened"}
        if action_taken not in valid_actions:
            action_taken = "blocked"

        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO loop_incidents
                   (project_id, incident_type, thread_id, agents_involved,
                    action_taken, details)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_id, incident_type, thread_id,
                 json.dumps(agents_involved), action_taken, details),
            )
            conn.commit()

        try:
            execute_with_retry(_insert)
        except Exception:
            logger.debug("Failed to record loop incident: %s", details)

    def _post_system_notice(self, project_id: int | None, message: str) -> None:
        """Post a notice visible to all agents."""
        if not project_id:
            return

        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO notices (project_id, title, content, priority, created_by)
                   VALUES (?, 'Communication Loop Detected', ?, 2, 'system')""",
                (project_id, message),
            )
            conn.commit()

        try:
            execute_with_retry(_insert)
        except Exception:
            logger.debug("Failed to post system notice")

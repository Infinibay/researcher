"""QuestionRegistry — cross-agent deduplication of clarification questions.

Tracks all clarification questions, prevents duplicates, and propagates
answers to agents who asked similar questions.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timezone

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def _normalize_question(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _question_hash(text: str) -> str:
    """SHA-256 hex digest of normalised question text."""
    return hashlib.sha256(_normalize_question(text).encode("utf-8")).hexdigest()


class QuestionRegistry:
    """Registry for cross-agent question deduplication and answer propagation."""

    def check_existing(
        self,
        project_id: int,
        question: str,
    ) -> dict | None:
        """Check if this question was already asked and answered.

        Returns ``{"answer": str, "answered_by": str}`` if found, else ``None``.
        """
        qhash = _question_hash(question)

        def _query(conn: sqlite3.Connection) -> dict | None:
            row = conn.execute(
                """SELECT answer_text, answered_by FROM clarification_questions
                   WHERE project_id = ? AND question_hash = ? AND status = 'answered'
                   ORDER BY answered_at DESC LIMIT 1""",
                (project_id, qhash),
            ).fetchone()
            if row and row["answer_text"]:
                return {"answer": row["answer_text"], "answered_by": row["answered_by"]}
            return None

        return execute_with_retry(_query)

    def register_question(
        self,
        project_id: int,
        task_id: int | None,
        asked_by: str,
        asked_to_role: str | None,
        question: str,
    ) -> int:
        """Register a new clarification question. Returns the question ID."""
        qhash = _question_hash(question)

        def _insert(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO clarification_questions
                   (project_id, task_id, asked_by, asked_to_role,
                    question_hash, question_text, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                (project_id, task_id, asked_by, asked_to_role,
                 qhash, question),
            )
            conn.commit()
            return cursor.lastrowid

        return execute_with_retry(_insert)

    def register_answer(
        self,
        question_id: int,
        answer: str,
        answered_by: str,
    ) -> None:
        """Record an answer for a registered question."""
        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE clarification_questions
                   SET answer_text = ?, answered_by = ?, status = 'answered',
                       answered_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (answer, answered_by, question_id),
            )
            conn.commit()

        execute_with_retry(_update)

    def register_assumption(
        self,
        question_id: int,
        assumption: str,
    ) -> None:
        """Record that the agent proceeded with an assumption."""
        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE clarification_questions
                   SET status = 'assumed', assumption = ?
                   WHERE id = ?""",
                (assumption, question_id),
            )
            conn.commit()

        execute_with_retry(_update)

    def get_agent_question_count(
        self,
        project_id: int,
        agent_id: str,
        task_id: int | None = None,
    ) -> int:
        """Count clarification questions asked by this agent for this task."""
        def _query(conn: sqlite3.Connection) -> int:
            if task_id is not None:
                row = conn.execute(
                    """SELECT COUNT(*) as cnt FROM clarification_questions
                       WHERE project_id = ? AND asked_by = ? AND task_id = ?""",
                    (project_id, agent_id, task_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT COUNT(*) as cnt FROM clarification_questions
                       WHERE project_id = ? AND asked_by = ?""",
                    (project_id, agent_id),
                ).fetchone()
            return row["cnt"] if row else 0

        return execute_with_retry(_query)

    def propagate_answer(
        self,
        question_id: int,
        project_id: int,
    ) -> None:
        """Auto-answer similar pending questions from other agents.

        When a question is answered, find all pending questions with the same
        hash and mark them answered too. Also creates a notice so agents know.
        """
        def _propagate(conn: sqlite3.Connection) -> int:
            # Get the answered question's hash and answer
            answered = conn.execute(
                """SELECT question_hash, answer_text, answered_by
                   FROM clarification_questions WHERE id = ?""",
                (question_id,),
            ).fetchone()
            if not answered or not answered["answer_text"]:
                return 0

            # Find pending questions with same hash (from other agents)
            pending = conn.execute(
                """SELECT id, asked_by FROM clarification_questions
                   WHERE project_id = ? AND question_hash = ?
                     AND status = 'pending' AND id != ?""",
                (project_id, answered["question_hash"], question_id),
            ).fetchall()

            count = 0
            for row in pending:
                conn.execute(
                    """UPDATE clarification_questions
                       SET answer_text = ?, answered_by = ?,
                           status = 'answered', answered_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (answered["answer_text"], answered["answered_by"], row["id"]),
                )
                count += 1

            if count > 0:
                conn.execute(
                    """INSERT INTO notices
                       (project_id, title, content, priority, created_by)
                       VALUES (?, 'Answer Propagated',
                               ?, 0, 'system')""",
                    (project_id,
                     f"Answer from {answered['answered_by']} was auto-applied to "
                     f"{count} similar pending question(s)."),
                )

            conn.commit()
            return count

        try:
            propagated = execute_with_retry(_propagate)
            if propagated > 0:
                logger.info(
                    "Propagated answer from question %d to %d similar questions",
                    question_id, propagated,
                )
        except Exception:
            logger.debug("Failed to propagate answer for question %d", question_id)

    def get_answered_questions(
        self,
        project_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """Get recently answered questions for context injection."""
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT asked_by, question_text, answer_text, answered_by
                   FROM clarification_questions
                   WHERE project_id = ? AND status = 'answered'
                   ORDER BY answered_at DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

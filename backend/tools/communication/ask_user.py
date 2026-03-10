"""Tool for Project Lead to ask questions to the human user."""

import json
import logging
import sqlite3
import time
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.flows.event_listeners import FlowEvent, event_bus
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class AskUserInput(BaseModel):
    question: str = Field(..., description="Question to ask the user")
    options: list[str] | None = Field(
        default=None, description="Optional list of choices for the user"
    )
    timeout: int = Field(
        default=3600, ge=60, le=7200,
        description="Max seconds to wait for user response",
    )


class AskUserTool(InfinibayBaseTool):
    name: str = "ask_user"
    description: str = (
        "Ask a question to the human user. Only available to the Project Lead. "
        "Creates a user request and waits for a response."
    )
    args_schema: Type[BaseModel] = AskUserInput

    def _run(
        self,
        question: str,
        options: list[str] | None = None,
        timeout: int = 3600,
    ) -> str:
        agent_id = self._validate_agent_context()
        project_id = self.project_id
        agent_run_id = self.agent_run_id

        # ── Semantic dedup: reject questions similar to previously asked ones ──
        try:
            dup_result = self._check_duplicate_question(project_id, question)
            if dup_result is not None:
                return dup_result
        except Exception:
            logger.debug("Question dedup check failed, proceeding", exc_info=True)

        def _create_request(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO user_requests
                   (project_id, agent_id, agent_run_id, request_type, title, body,
                    options_json, status)
                   VALUES (?, ?, ?, 'question', ?, ?, ?, 'pending')""",
                (
                    project_id, agent_id, agent_run_id,
                    question[:200],  # title is abbreviated
                    question,
                    json.dumps(options or []),
                ),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            request_id = execute_with_retry(_create_request)
        except Exception as e:
            return self._error(f"Failed to create user request: {e}")

        # Mirror the question as a chat_message so it persists in chat history
        def _mirror_question(conn: sqlite3.Connection) -> None:
            thread_id = f"user-qa-p{project_id}"
            conn.execute(
                """INSERT OR IGNORE INTO conversation_threads
                   (thread_id, project_id, thread_type, created_at)
                   VALUES (?, ?, 'user_chat', CURRENT_TIMESTAMP)""",
                (thread_id, project_id),
            )
            conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, to_agent, message,
                    conversation_type, created_at)
                   VALUES (?, ?, ?, 'user', ?, 'agent_to_user', CURRENT_TIMESTAMP)""",
                (project_id, thread_id, agent_id, question),
            )
            conn.commit()

        try:
            execute_with_retry(_mirror_question)
        except Exception:
            pass  # Non-fatal — the user_request is the source of truth

        event_bus.emit(
            FlowEvent(
                event_type="user_request_created",
                project_id=project_id,
                entity_type="user_request",
                entity_id=request_id,
                data={"question": question[:200], "has_options": bool(options)},
            )
        )

        self._log_tool_usage(f"Asked user: {question[:80]}")

        # Poll for response
        start = time.time()
        poll_interval = settings.CHAT_POLL_INTERVAL

        while time.time() - start < timeout:
            time.sleep(poll_interval)

            def _check_response(conn: sqlite3.Connection) -> str | None:
                row = conn.execute(
                    """SELECT response, status FROM user_requests
                       WHERE id = ? AND status = 'responded'""",
                    (request_id,),
                ).fetchone()
                if row:
                    return row["response"]
                return None

            try:
                response = execute_with_retry(_check_response)
                if response is not None:
                    return self._success({
                        "response": response,
                        "request_id": request_id,
                    })
            except Exception:
                pass

        # Timeout - mark request as expired
        def _expire(conn: sqlite3.Connection):
            conn.execute(
                "UPDATE user_requests SET status = 'expired' WHERE id = ?",
                (request_id,),
            )
            conn.commit()

        try:
            execute_with_retry(_expire)
        except Exception:
            pass

        return self._error(f"User did not respond within {timeout}s")

    def _check_duplicate_question(
        self, project_id: int, question: str,
    ) -> str | None:
        """Return an early response if *question* is semantically similar to a previous one.

        Uses the same vector-based dedup as task/epic creation (find_semantic_duplicate).
        If the prior question already has a user response, returns that response directly.
        If the prior question is still pending, returns an error telling the agent to wait.
        Returns None when no duplicate is found (caller should proceed normally).
        """
        from backend.tools.base.dedup import find_semantic_duplicate

        def _fetch_existing(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, body, status, response
                   FROM user_requests
                   WHERE project_id = ? AND request_type = 'question'
                   ORDER BY id""",
                (project_id,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "title": r["body"],
                    "status": r["status"],
                    "response": r["response"],
                }
                for r in rows
            ]

        existing = execute_with_retry(_fetch_existing)
        if not existing:
            return None

        match = find_semantic_duplicate(
            question, existing, settings.DEDUP_SIMILARITY_THRESHOLD,
        )
        if match is None:
            return None

        matched_item = next(
            (e for e in existing if e["id"] == match["id"]), None,
        )
        if matched_item is None:
            return None

        logger.info(
            "Duplicate user question detected (%.0f%% similar to request %d): %s",
            match["similarity"] * 100, match["id"], question[:80],
        )

        if matched_item["status"] == "responded" and matched_item["response"]:
            return self._success({
                "response": matched_item["response"],
                "request_id": match["id"],
                "source": "duplicate_detected",
                "note": (
                    f"This question is {match['similarity']:.0%} similar to a "
                    f"previous question (ID {match['id']}). Returning the "
                    f"user's prior answer instead of asking again."
                ),
            })

        return self._error(
            f"Duplicate question detected: request {match['id']} "
            f"({match['similarity']:.0%} similar) is already pending. "
            f"Wait for the user to respond to the existing question instead "
            f"of asking again."
        )

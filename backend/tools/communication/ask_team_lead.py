"""Tool for asking questions to the Team Lead."""

import json
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry
from backend.tools.communication.send_message import SendMessageTool

_MAX_QUESTIONS_PER_TASK = 2


class AskTeamLeadInput(BaseModel):
    question: str = Field(..., description="Question to ask the Team Lead")
    thread_id: str | None = Field(
        default=None,
        description="Thread ID to continue an existing conversation. Pass the thread_id from a previous message in this conversation.",
    )
    wait_for_response: bool = Field(
        default=True, description="Wait for a response (polling)"
    )
    timeout: int = Field(
        default=300, ge=10, le=600,
        description="Max seconds to wait for response",
    )


class AskTeamLeadTool(InfinibayBaseTool):
    name: str = "ask_team_lead"
    description: str = (
        "Ask a question to the Team Lead agent. "
        "Can optionally wait for a response with a timeout."
    )
    args_schema: Type[BaseModel] = AskTeamLeadInput

    def _run(
        self,
        question: str,
        thread_id: str | None = None,
        wait_for_response: bool = True,
        timeout: int = 300,
    ) -> str:
        agent_id = self._validate_agent_context()
        project_id = self.project_id
        task_id = self.task_id

        # ── QuestionRegistry: check for cached answer ────────────────
        from backend.communication.question_registry import QuestionRegistry

        registry = QuestionRegistry()
        if project_id:
            cached = registry.check_existing(project_id, question)
            if cached:
                self._log_tool_usage("Returned cached answer from registry")
                return self._success({
                    "response": cached["answer"],
                    "from": cached["answered_by"],
                    "source": "cached_answer",
                })

            # Check question budget
            count = registry.get_agent_question_count(project_id, agent_id, task_id)
            if count >= _MAX_QUESTIONS_PER_TASK:
                return self._error(
                    f"Max clarification questions reached ({_MAX_QUESTIONS_PER_TASK} per task). "
                    "Proceed with your best judgment and document assumptions "
                    "using AddCommentTool with prefix 'ASSUMPTION:'."
                )

        # Enrich the question with project state context
        if project_id:
            from backend.flows.helpers.messaging import build_enriched_message
            enriched_question = build_enriched_message(
                project_id, question,
                sender_role="team_lead",
                thread_id=thread_id,
            )
        else:
            enriched_question = question

        # Send the message — propagate agent binding to delegate
        sender = SendMessageTool()
        self._bind_delegate(sender)
        send_result = sender._run(
            message=enriched_question,
            to_role="team_lead",
            priority=1,
            thread_id=thread_id,
        )

        if not wait_for_response:
            if project_id:
                registry.register_question(
                    project_id, task_id, agent_id, "team_lead", question,
                )
            return send_result

        # Poll for response
        send_data = json.loads(send_result) if isinstance(send_result, str) else send_result
        if "error" in (send_data if isinstance(send_data, dict) else {}):
            return send_result

        thread_id = send_data.get("thread_id") if isinstance(send_data, dict) else None

        # Register question in registry
        question_id = None
        if project_id:
            question_id = registry.register_question(
                project_id, task_id, agent_id, "team_lead", question,
            )

        # Wait for reply via event-based notification (no polling)
        from backend.communication.response_event_registry import response_event_registry

        reply_event = response_event_registry.register(thread_id)
        try:
            replied = reply_event.wait(timeout=timeout)

            if replied:
                def _check_reply(conn: sqlite3.Connection) -> dict | None:
                    row = conn.execute(
                        """SELECT cm.id, cm.message, cm.created_at
                           FROM chat_messages cm
                           JOIN roster r ON cm.from_agent = r.agent_id
                           WHERE cm.thread_id = ?
                             AND r.role = 'team_lead'
                             AND cm.from_agent != ?
                             AND (
                                 cm.to_agent = ?
                                 OR cm.to_role IN (
                                     SELECT role FROM roster WHERE agent_id = ?
                                 )
                                 OR (cm.to_agent IS NULL AND cm.to_role IS NULL)
                             )
                             AND cm.id NOT IN (
                                 SELECT message_id FROM message_reads WHERE agent_id = ?
                             )
                           ORDER BY cm.created_at DESC
                           LIMIT 1""",
                        (thread_id, agent_id, agent_id, agent_id, agent_id),
                    ).fetchone()
                    if row:
                        conn.execute(
                            """INSERT OR IGNORE INTO message_reads (message_id, agent_id)
                               VALUES (?, ?)""",
                            (row["id"], agent_id),
                        )
                        conn.commit()
                        return dict(row)
                    return None

                try:
                    reply = execute_with_retry(_check_reply)
                    if reply:
                        if question_id and project_id:
                            registry.register_answer(
                                question_id, reply["message"], "team_lead",
                            )
                            registry.propagate_answer(question_id, project_id)
                        self._log_tool_usage("Received response from Team Lead")
                        return self._success({
                            "response": reply["message"],
                            "from": "team_lead",
                            "thread_id": thread_id,
                        })
                except Exception:
                    pass

            # Timeout — register assumption and instruct agent to proceed
            if question_id:
                registry.register_assumption(
                    question_id,
                    "No response — agent proceeding with assumptions",
                )
            return self._error(
                f"No response from Team Lead within {timeout}s. "
                "Proceed with your best judgment on the CURRENT task. "
                "Document your assumption with AddCommentTool (prefix: ASSUMPTION:). "
                "IMPORTANT: Do NOT create new tasks, epics, or other resources as a "
                "workaround for the missing answer. Only continue working on your "
                "assigned task using reasonable assumptions."
            )
        finally:
            response_event_registry.unregister(thread_id)

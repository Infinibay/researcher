"""Tool for asking questions to the Project Lead."""

import json
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry
from backend.tools.communication.send_message import SendMessageTool

_MAX_QUESTIONS_PER_TASK = 2


class AskProjectLeadInput(BaseModel):
    question: str = Field(..., description="Question to ask the Project Lead")
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


class AskProjectLeadTool(PabadaBaseTool):
    name: str = "ask_project_lead"
    description: str = (
        "Ask a question to the Project Lead agent. "
        "Can optionally wait for a response with a timeout."
    )
    args_schema: Type[BaseModel] = AskProjectLeadInput

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
                sender_role="project_lead",
                thread_id=thread_id,
            )
        else:
            enriched_question = question

        # Send the message — propagate agent binding to delegate
        sender = SendMessageTool()
        self._bind_delegate(sender)
        send_result = sender._run(
            message=enriched_question,
            to_role="project_lead",
            priority=1,
            thread_id=thread_id,
        )

        if not wait_for_response:
            if project_id:
                registry.register_question(
                    project_id, task_id, agent_id, "project_lead", question,
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
                project_id, task_id, agent_id, "project_lead", question,
            )

        # Wait for reply via event-based notification (no polling)
        from backend.communication.response_event_registry import response_event_registry

        reply_event = response_event_registry.register(thread_id)

        # Kick off a Crew for the Project Lead to process the message and
        # reply.  This runs in a background thread so the current agent can
        # block on reply_event.wait() below while the PL works.
        import threading

        def _dispatch():
            try:
                from backend.flows.helpers.message_dispatcher import dispatch_message
                dispatch_message(
                    project_id=project_id,
                    agent_id=f"project_lead_p{project_id}",
                    from_agent=agent_id,
                    content=enriched_question,
                    thread_id=thread_id,
                )
            except Exception:
                import logging
                logging.getLogger(__name__).debug(
                    "Failed to dispatch message to project_lead", exc_info=True,
                )

        threading.Thread(
            target=_dispatch,
            name=f"DispatchPL-{thread_id}",
            daemon=True,
        ).start()
        try:
            replied = reply_event.wait(timeout=timeout)

            if replied:
                def _check_reply(conn: sqlite3.Connection) -> dict | None:
                    row = conn.execute(
                        """SELECT cm.id, cm.message, cm.created_at
                           FROM chat_messages cm
                           JOIN roster r ON cm.from_agent = r.agent_id
                           WHERE cm.thread_id = ?
                             AND r.role = 'project_lead'
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
                                question_id, reply["message"], "project_lead",
                            )
                            registry.propagate_answer(question_id, project_id)
                        self._log_tool_usage("Received response from Project Lead")
                        return self._success({
                            "response": reply["message"],
                            "from": "project_lead",
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
                f"No response from Project Lead within {timeout}s. "
                "Proceed with your best judgment. Document your assumption "
                "with AddCommentTool (prefix: ASSUMPTION:)."
            )
        finally:
            response_event_registry.unregister(thread_id)

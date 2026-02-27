"""Tool for agents to reply to user messages.

Unlike AskUserTool (which creates a user_request and waits for a response),
this tool simply posts a message visible in the chat UI. It does NOT block
waiting for a reply.

Any agent can use this tool, but ONLY to respond to a user message they
received — never to initiate a conversation with the user.
"""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.flows.event_listeners import FlowEvent, event_bus
from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReplyToUserInput(BaseModel):
    message: str = Field(
        ..., description="Reply message to send to the user"
    )
    thread_id: str | None = Field(
        default=None,
        description="Thread ID of the user's message you are replying to. "
        "If not provided, creates a new thread.",
    )


class ReplyToUserTool(PabadaBaseTool):
    name: str = "reply_to_user"
    description: str = (
        "Reply to a message from the human user. Use this ONLY to respond "
        "to a user message you received — never to initiate contact. "
        "The message appears in the chat UI immediately."
    )
    args_schema: Type[BaseModel] = ReplyToUserInput

    def _run(self, message: str, thread_id: str | None = None) -> str:
        agent_id = self._validate_agent_context()
        project_id = self.project_id

        if not message.strip():
            return self._error("Message cannot be empty.")

        def _send(conn: sqlite3.Connection) -> dict:
            # Create or reuse thread
            actual_thread_id = thread_id
            if actual_thread_id is None:
                actual_thread_id = f"user-reply-{agent_id}"
                conn.execute(
                    """INSERT OR IGNORE INTO conversation_threads
                       (thread_id, project_id, thread_type, created_at)
                       VALUES (?, ?, 'user_chat', CURRENT_TIMESTAMP)""",
                    (actual_thread_id, project_id),
                )

            cursor = conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, to_agent, message,
                    conversation_type, created_at)
                   VALUES (?, ?, ?, 'user', ?, 'agent_to_user',
                           CURRENT_TIMESTAMP)""",
                (project_id, actual_thread_id, agent_id, message),
            )
            conn.execute(
                """UPDATE conversation_threads
                   SET last_message_at = CURRENT_TIMESTAMP
                   WHERE thread_id = ?""",
                (actual_thread_id,),
            )
            conn.commit()
            return {
                "message_id": cursor.lastrowid,
                "thread_id": actual_thread_id,
            }

        try:
            result = execute_with_retry(_send)
        except Exception as e:
            return self._error(f"Failed to send reply: {e}")

        event_bus.emit(
            FlowEvent(
                event_type="agent_reply_to_user",
                project_id=project_id,
                entity_type="message",
                entity_id=result["message_id"],
                data={
                    "from_agent": agent_id,
                    "to": "user",
                    "thread_id": result["thread_id"],
                    "content": message[:200],
                },
            )
        )

        self._log_tool_usage(f"Replied to user: {message[:80]}")

        return self._success({
            "message_id": result["message_id"],
            "thread_id": result["thread_id"],
            "status": "sent",
        })

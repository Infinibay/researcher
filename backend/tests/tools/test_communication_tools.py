"""Tests for communication tools."""

import json

import pytest

from backend.tools.base.context import set_context
from backend.tools.communication import ReadMessagesTool, SendMessageTool


class TestSendMessageTool:
    def test_send_direct_message(self, test_db, agent_context):
        tool = SendMessageTool()
        result = json.loads(tool._run(
            message="Hello lead",
            to_agent="lead-1",
        ))
        assert "message_id" in result
        assert "thread_id" in result
        assert result["to"] == "lead-1"

    def test_send_role_message(self, test_db, agent_context):
        tool = SendMessageTool()
        result = json.loads(tool._run(
            message="Hello team lead",
            to_role="team_lead",
        ))
        assert result["to"] == "team_lead"

    def test_send_broadcast(self, test_db, agent_context):
        tool = SendMessageTool()
        result = json.loads(tool._run(message="Hello everyone"))
        assert result["to"] == "broadcast"

    def test_send_with_priority(self, test_db, agent_context):
        tool = SendMessageTool()
        result = json.loads(tool._run(
            message="Urgent!", to_role="team_lead", priority=3,
        ))
        assert result["priority"] == 3


class TestReadMessagesTool:
    def test_read_direct_messages(self, test_db, agent_context):
        # Send a message from lead to agent
        set_context(agent_id="lead-1")
        send = SendMessageTool()
        send._run(message="Task assignment", to_agent="agent-1")

        # Read as agent-1
        set_context(agent_id="agent-1")
        read = ReadMessagesTool()
        result = json.loads(read._run())
        assert result["count"] >= 1
        messages = [m for m in result["messages"] if m["message"] == "Task assignment"]
        assert len(messages) == 1

    def test_mark_as_read(self, test_db, agent_context):
        set_context(agent_id="lead-1")
        send = SendMessageTool()
        send._run(message="Read me", to_agent="agent-1")

        set_context(agent_id="agent-1")
        read = ReadMessagesTool()
        # First read
        r1 = json.loads(read._run(unread_only=True))
        count1 = r1["count"]

        # Second read - should be empty (already read)
        r2 = json.loads(read._run(unread_only=True))
        assert r2["count"] < count1

    def test_filter_by_thread(self, test_db, agent_context):
        set_context(agent_id="lead-1")
        send = SendMessageTool()
        r = json.loads(send._run(message="Thread msg", to_agent="agent-1"))
        thread_id = r["thread_id"]

        set_context(agent_id="agent-1")
        read = ReadMessagesTool()
        result = json.loads(read._run(thread_id=thread_id))
        assert result["count"] >= 1

"""Native peer inbox and explicit receipts under the existing live business grant boundary."""

from typing import Literal

from fastapi import APIRouter, Query

from backend.api.models.agent_messages import AcknowledgeAgentMessage, SendAgentMessage
from backend.api.research_dependencies import Context
from backend.communication.agent_messages import AgentMessages

router = APIRouter(prefix="/api/research-tools/peer-messages", tags=["research-tools"])


@router.get("/recipients")
def recipients(ctx: Context, after_seq: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    """List actual receiving project executions instead of resolving ambiguous roster roles."""
    return AgentMessages(ctx.store).recipients(ctx.scope, after_seq=after_seq, limit=limit)


@router.get("")
def messages(ctx: Context, direction: Literal["inbox", "sent"] = "inbox", after_id: int = Query(0, ge=0),
             limit: int = Query(20, ge=1, le=100), unread_only: bool = False):
    """Page this admitted run's durable conversation without acknowledging previews."""
    return AgentMessages(ctx.store).list(ctx.scope, direction=direction, after_id=after_id, limit=limit, unread_only=unread_only)


@router.get("/{message_id}")
def message_read(message_id: int, ctx: Context, offset: int = Query(0, ge=0), max_chars: int = Query(12000, ge=1, le=16000)):
    """Recover the complete original text and attributed premises of a participating run's message."""
    return AgentMessages(ctx.store).read(ctx.scope, message_id, offset=offset, max_chars=max_chars)


@router.post("", status_code=201)
def message_send(command: SendAgentMessage, ctx: Context):
    """Record one informational exchange and its operation receipt without invoking a dispatcher."""
    return AgentMessages(ctx.store).send(ctx.scope, command.operation_key, **command.model_dump(exclude={"operation_key"}))


@router.post("/acknowledgements")
def message_acknowledge(command: AcknowledgeAgentMessage, ctx: Context):
    """Bind an explicit content receipt to the current recipient's actual attempt."""
    return AgentMessages(ctx.store).acknowledge(ctx.scope, command.operation_key, command.message_id, command.expected_sha256)

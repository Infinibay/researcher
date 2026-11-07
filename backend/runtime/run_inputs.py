"""Exact host input composition, historical scope and explicit size boundaries.

This records what Researcher prepares, not hidden provider instructions, future
outputs or evidence that a model understood a message. No truncation/LLM summary.
"""

import hashlib
import json

from backend.runtime.contracts import FrozenRunInput, InputTooLarge

MAX_INPUT_BYTES = 1048576
MAX_HISTORY_MESSAGES = 200

MESSAGE_SELECT = """SELECT cm.*,r.id AS runtime_run_id,r.status AS runtime_status,
    note.operation_key AS owner_note_key,
    CASE WHEN cm.id=q.answer_message_id THEN q.answer_context_version ELSE r.context_version END AS context_version,
    r.task_id, CASE WHEN cm.id=q.question_message_id THEN 'question' WHEN cm.id=q.answer_message_id THEN 'answer'
    ELSE 'recorded' END AS delivery FROM chat_messages cm
    LEFT JOIN runtime_chat_links link ON cm.id=link.user_message_id OR cm.id=link.proposal_message_id
    LEFT JOIN runtime_question_links q ON cm.id=q.question_message_id OR cm.id=q.answer_message_id
    LEFT JOIN runtime_owner_notes note ON note.project_id=cm.project_id AND note.message_id=cm.id
    LEFT JOIN runtime_runs r ON r.id=COALESCE(link.run_id,q.run_id)"""


def conversation_history(conn, row):
    """Retain scoped original conversation and explicit note/instruction provenance; a paired note proves authorship without granting work authority."""
    link = conn.execute(
        "SELECT * FROM runtime_chat_links WHERE project_id=? AND run_id=?",
        (row["project_id"], row["id"]),
    ).fetchone()
    if link is None:
        return {
            "thread_id": None,
            "cutoff_message_id": None,
            "messages": [],
            "other_task_messages_excluded": 0,
        }
    condition = " WHERE cm.project_id=? AND cm.thread_id=? AND cm.id<?"
    args = (row["project_id"], link["thread_id"], link["user_message_id"])
    excluded = conn.execute(
        "SELECT COUNT(*) FROM (" + MESSAGE_SELECT + condition + " AND r.task_id<>?)",
        (*args, row["task_id"]),
    ).fetchone()[0]
    history = conn.execute(
        MESSAGE_SELECT
        + condition
        + " AND (r.task_id IS NULL OR r.task_id=?) ORDER BY cm.id LIMIT ?",
        (*args, row["task_id"], MAX_HISTORY_MESSAGES + 1),
    ).fetchall()
    if len(history) > MAX_HISTORY_MESSAGES:
        raise InputTooLarge("Conversation history exceeds the input message limit")
    if sum(len(m["message"].encode()) for m in history) > MAX_INPUT_BYTES:
        raise InputTooLarge("Conversation history exceeds the input byte limit")
    messages = []
    for m in history:
        kind = (
            "owner_answer"
            if m["delivery"] == "answer"
            else "agent_question"
            if m["delivery"] == "question"
            else "owner_instruction"
            if m["runtime_run_id"] is not None
            and m["conversation_type"] == "user_to_agent"
            else "agent_proposal"
            if m["runtime_run_id"] is not None
            else "owner_note"
            if m["owner_note_key"] is not None
            else "unattributed_record"
        )
        messages.append(
            {
                "message_id": m["id"],
                "kind": kind,
                **({"work_authorized": False} if kind == "owner_note" else {}),
                "recorded_sender": m["from_agent"],
                "source_context_version": m["context_version"],
                "same_context_version": m["context_version"] == row["context_version"]
                if m["context_version"] is not None
                else None,
                "run_id": m["runtime_run_id"],
                "run_status_at_snapshot": m["runtime_status"],
                "content": m["message"],
                "content_sha256": hashlib.sha256(m["message"].encode()).hexdigest(),
            }
        )
    return {
        "thread_id": link["thread_id"],
        "cutoff_message_id": link["user_message_id"],
        "messages": messages,
        "other_task_messages_excluded": excluded,
    }


def task_request_history(conn, row, conversation):
    """Retain prior same-task admissions without renewing authority or undoing a conversation reset.

    Admission order defines the cutoff, independently of wall time. A stored
    request proves admission, not human authorship or delivery to a model.
    """
    if conversation["thread_id"] is not None:
        return {"mode": "selected_conversation", "requests": []}
    history = conn.execute(
        """SELECT id,actor_id,context_version,prompt,status,execution_kind
        FROM runtime_runs WHERE project_id=? AND task_id=?
        AND rowid<(SELECT rowid FROM runtime_runs WHERE id=?)
        ORDER BY rowid LIMIT ?""",
        (row["project_id"], row["task_id"], row["id"], MAX_HISTORY_MESSAGES + 1),
    ).fetchall()
    if len(history) > MAX_HISTORY_MESSAGES:
        raise InputTooLarge("Task request history exceeds the input message limit")
    if sum(len(item["prompt"].encode()) for item in history) > MAX_INPUT_BYTES:
        raise InputTooLarge("Task request history exceeds the input byte limit")
    return {
        "mode": "same_task_admissions",
        "cutoff_run_id": row["id"],
        "requests": [{
            "kind": "recorded_admission",
            "run_id": item["id"],
            "actor_id": item["actor_id"],
            "execution_kind": item["execution_kind"],
            "source_context_version": item["context_version"],
            "same_context_version": item["context_version"] == row["context_version"],
            "run_status_at_snapshot": item["status"],
            "current_authorization": False,
            "content": item["prompt"],
            "content_sha256": hashlib.sha256(item["prompt"].encode()).hexdigest(),
        } for item in history],
    }


def freeze_input(conn, row, context):
    """Freeze complete original task/history and typed prerequisite delivery; reject oversize material without hidden omission."""
    # Input validation belongs to the owning store before this renderer; reading
    # its immutable packet here preserves the exact original causal material.
    delivery = conn.execute("SELECT h.packet_json FROM runtime_plan_handoffs h JOIN runtime_plan_deliveries d ON d.id=h.delivery_id WHERE d.run_id=?", (row["id"],)).fetchone()
    conversation = conversation_history(conn, row)
    payload = {
        "schema_version": 1,
        **context,
        "scope": {
            "project_id": row["project_id"],
            "task_id": row["task_id"],
            "run_id": row["id"],
            "attempt_id": row["current_attempt_id"],
        },
        "request": row["prompt"],
        "repository": {
            "id": row["bound_repository_id"],
            "name": row["bound_repository_name"],
        },
        "conversation": conversation,
        "request_history": task_request_history(conn, row, conversation),
        "work_delivery": json.loads(delivery["packet_json"]) if delivery else None,
    }
    from backend.runtime.code_carryover import CodeCarryovers

    prior_code = CodeCarryovers.input(conn, row)
    if prior_code is not None:
        payload["prior_code"] = prior_code
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(encoded.encode()) > MAX_INPUT_BYTES:
        raise InputTooLarge("Task context exceeds the input byte limit")
    return FrozenRunInput(encoded, hashlib.sha256(encoded.encode()).hexdigest())

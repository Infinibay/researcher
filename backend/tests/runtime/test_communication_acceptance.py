"""Cross-boundary communication scenarios using real SQLite, process loss and typed controls; model behavior remains controlled."""

import asyncio
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_agent_messages import packet, peers
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator
from backend.tests.runtime.test_workspace_delivery import owner_client, workspace_app as workspace_app


@pytest.mark.parametrize("kind", ["instruction", "peer"])
def test_process_loss_after_committed_message_retains_one_original_delivery(coordination, kind):
    """Abrupt exit after the actual commit cannot lose the pending instruction/inbox or require another effect on receipt recovery."""
    from backend.communication import agent_messages
    from backend.runtime import sqlite_runs

    c = coordination
    payload = {"database": str(c.database), "kind": kind, "spec": asdict(c.spec)}
    if kind == "peer":
        messages, sender, recipient = peers(c)
        payload.update(token=sender[3], packet=packet(recipient, message="Final condition: do not modify files."))
    child = r'''
"""Commit a real delivery then disappear before returning a receipt or scheduling any work."""
import hashlib, json, os, sys
from pathlib import Path
from backend.communication import agent_messages
from backend.research.sqlite_store import SQLiteResearchStore
from backend.runtime import sqlite_runs
from backend.runtime.contracts import RunSpec
p = json.load(sys.stdin)
if p['kind'] == 'instruction':
    sqlite_runs.SQLiteRunStore(p['database'], clock=lambda:1000).admit(RunSpec(**p['spec']), conversation_thread='crashed-instruction')
else:
    store = SQLiteResearchStore(p['database'], clock=lambda:1000)
    agent_messages.AgentMessages(store).send(store.authorize(p['token']), 'crashed-message', **p['packet'])
print(json.dumps({m.__name__:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (agent_messages,sqlite_runs)}), flush=True)
os._exit(73)
'''
    result = subprocess.run([sys.executable, "-I", "-c", child], input=json.dumps(payload), capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 73, result.stderr
    assert json.loads(result.stdout) == {m.__name__: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (agent_messages, sqlite_runs)}
    if kind == "instruction":
        recovered = c.store.admit(c.spec, conversation_thread="crashed-instruction")
        assert recovered.status == "queued" and recovered.attempt_id is None
        assert c.conn.execute("SELECT count(*) FROM runtime_chat_links").fetchone()[0] == 1
        assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 1
    else:
        inbox = messages.list(recipient[2], unread_only=True)["items"]
        recovered = messages.send(sender[2], "crashed-message", **payload["packet"])
        assert len(inbox) == 1 and inbox[0]["message_id"] == recovered["message_id"]
        assert recovered["delivery"] == "recorded" and recovered["applied"] == "not_verified"
        assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 2
    assert c.conn.execute("SELECT count(*) FROM chat_messages").fetchone()[0] == 1
    assert c.conn.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0] == 0
    assert c.conn.execute("SELECT count(*) FROM agent_events").fetchone()[0] == 0


def test_two_questions_in_one_thread_accept_reversed_answers_before_receipt_ack(coordination):
    """Replies correlate to immutable question IDs, even before the sender waits/acknowledges and after reopening the inbox."""
    from backend.communication.agent_messages import AgentMessages
    from backend.research.sqlite_store import SQLiteResearchStore

    c = coordination
    messages, sender, recipient = peers(c)
    first = messages.send(sender[2], "q-one", **packet(recipient, intent="question", message="Which unit?"))
    second = messages.send(sender[2], "q-two", **packet(recipient, intent="question", message="Which period?", in_reply_to=first["message_id"]))
    assert first["thread_id"] == second["thread_id"]
    answers = []
    for key, question, text in [("a-two", second, "Yearly"), ("a-one", first, "Kilograms")]:
        answers.append(messages.send(recipient[2], key, **packet(sender, intent="answer", message=text, in_reply_to=question["message_id"])))
    reopened = AgentMessages(SQLiteResearchStore(c.database, clock=lambda:c.now[0]))
    received = reopened.list(sender[2], unread_only=True)["items"]
    assert [r["parent_message_id"] for r in received] == [second["message_id"], first["message_id"]]
    assert [reopened.read(sender[2], r["message_id"])["content"] for r in received] == ["Yearly", "Kilograms"]
    assert all(r["thread_id"] == first["thread_id"] for r in received)
    assert [r["message_id"] for r in received] == [r["message_id"] for r in answers]
    assert len(reopened.list(recipient[2], unread_only=True)["items"]) == 2


def test_final_peer_constraint_is_recoverable_and_read_does_not_apply_correction(coordination):
    """A preview omits the final restriction explicitly; full windows preserve it, while correction revokes the old recipient despite its prior read."""
    from backend.research.models import ResearchForbidden, ResearchInputError

    c = coordination
    messages, sender, recipient = peers(c)
    text = "Background observation. " * 300 + "FINAL CONSTRAINT: do not modify files."
    saved = messages.send(sender[2], "long-context", **packet(recipient, message=text, observations=["The owner supplied a read-only example."], assumptions=["It may apply to this task; verify the current instruction."]))
    preview = messages.list(recipient[2])["items"][0]
    assert "FINAL CONSTRAINT" not in preview["preview"] and preview["total_chars"] == len(text)
    content = ""
    offset = 0
    while True:
        window = messages.read(recipient[2], saved["message_id"], offset=offset, max_chars=1000)
        assert window["body_sha256"] == saved["body_sha256"]
        assert window["observations"] != window["assumptions"]
        content += window["content"]
        if window["next_offset"] is None:
            break
        offset = window["next_offset"]
    assert content == text and window["applied"] == "not_verified"
    assert messages.list(recipient[2], unread_only=True)["items"]
    with pytest.raises(ResearchInputError):
        messages.send(sender[2], "too-large", **packet(recipient, message="x" * 12001 + "DO NOT EDIT"))
    c.store.correct_context(project_id=101, task_id=1002, expected_version=1, operation_key="actual-owner-correction", statement="Use only the new read-only scope.", source_kind="user_message", source_reference="owner:7")
    with pytest.raises(ResearchForbidden):
        messages.acknowledge(recipient[2], "late-read-receipt", saved["message_id"], saved["body_sha256"])
    state = messages.read(sender[2], saved["message_id"])
    assert state["recipient_context_current"] is False and state["applied"] == "not_verified"
    assert c.store.get(101, recipient[0].run_id).status == "reconciling"


def test_ping_pong_hits_original_run_cap_but_repeated_corrections_and_stop_remain_available(coordination):
    """Acknowledging each reply cannot reset the per-run causal bound, and saturation never blocks short typed owner controls."""
    from backend.communication.agent_messages import MAX_SENT_PER_RUN
    from backend.research.models import OperationConflict

    c = coordination
    messages, one, two = peers(c)
    parent = None
    for index in range(MAX_SENT_PER_RUN):
        for sender, recipient in ((one, two), (two, one)):
            saved = messages.send(sender[2], f"loop-{index}", **packet(recipient, message="OK", in_reply_to=parent))
            messages.acknowledge(recipient[2], f"ack-{index}", saved["message_id"], saved["body_sha256"])
            parent = saved["message_id"]
    with pytest.raises(OperationConflict, match="capacity"):
        messages.send(one[2], "over-limit", **packet(two, message="OK", in_reply_to=parent))
    assert c.conn.execute("SELECT count(*) FROM runtime_agent_messages").fetchone()[0] == 2 * MAX_SENT_PER_RUN
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 2
    for version in (1, 2):
        assert c.store.correct_context(project_id=101, task_id=1001, expected_version=version, operation_key=f"control-{version}", statement="No", source_kind="user_message", source_reference=f"owner:{version}") == version + 1
    assert len(c.store.context_snapshot(101, 1001)["corrections"]) == 2
    assert c.store.cancel(101, two[0].run_id).status == "cancelling"
    assert c.conn.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0] == 0


@pytest.mark.parametrize("repeat", [False, True])
async def test_correction_survives_slow_tool_and_exhausted_project_budget(service_setup, repeat):
    """Consecutive owner corrections remain recordable at full budget during slow closure; only a later explicit turn receives their current version."""
    from backend.runtime.history import RuntimeHistory
    from backend.runtime.project_budget import ProjectBudgetPolicies

    s = service_setup
    ProjectBudgetPolicies(s.c.store).update(101, operation_key="one-turn", expected_revision=0, turn_limit=1, token_limit=100, reason="Bound this communication scenario.")
    native = ControlledInference(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        before = RuntimeHistory(s.c.database).budget(101)
        assert before["accounted_tokens"] == 100 and before["remaining_turns"] == 0
        with service.live_grants.operation(native.scope.grant_id) as cancelled:
            version = await asyncio.wait_for(service.correct(project_id=101, task_id=1001, expected_version=1, operation_key="control-at-limit", statement="Read only; do not modify files.", source_kind="user_message", source_reference="owner:limit"), 2)
            assert version == 2 and await asyncio.to_thread(cancelled.wait, 1)
            await asyncio.wait_for(native.interrupted.wait(), 1)
            assert not service.live_grants.allows(native.scope.grant_id)
            if repeat:
                version = await asyncio.wait_for(service.correct(project_id=101, task_id=1001, expected_version=2, operation_key="second-control-at-limit", statement="Inspect only documentation and use the later example.", source_kind="user_example", source_reference="owner:second"), 2)
                assert version == 3
            waiting = asyncio.create_task(service.wait(run.run_id))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(waiting), 0.05)
            assert s.c.store.get(101, run.run_id).status != "superseded"
        await asyncio.wait_for(waiting, 2)
        assert s.c.store.get(101, run.run_id).status == "superseded"
        assert len(native.prompts) == 1
        assert s.c.store.context_snapshot(101, 1001)["context_version"] == version
        assert s.c.conn.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0] == 1
        if repeat:
            ProjectBudgetPolicies(s.c.store).update(101, operation_key="explicit-room", expected_revision=1, turn_limit=2, token_limit=200, reason="Owner permits the next explicit attempt.")
            next_native = ControlledInference(s)
            next_native.release.set()
            service.runtime = next_native
            next_run = await service.submit(replace(s.c.spec, operation_key="explicit-current-input", context_version=3))
            await service.wait(next_run.run_id)
            received = json.loads(next_native.prompts[0])
            assert received["context_version"] == 3
            assert [c["source_reference"] for c in received["corrections"]] == ["owner:limit", "owner:second"]


@pytest.mark.parametrize("answer_first", [True, False])
def test_question_answer_and_stop_race_preserves_the_first_durable_decision(coordination, answer_first):
    """Conditional answer/Stop ordering never overwrites a committed answer or treats a cancelled question as agreement."""
    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_human_questions import setup_question

    c = coordination
    questions, run, lease, _, receipt = setup_question(c)
    questions.park(lease)
    c.now[0] += 3600
    answer = dict(project_id=101, task_id=1001, request_id=receipt["request_id"], expected_version=1, operation_key="answer-race", answers={"base":"200"})
    if answer_first:
        assert questions.answer(**answer) == 2
        c.store.cancel(101, run.run_id)
        assert questions.answer(**answer) == 2
        row = c.conn.execute("SELECT status,response FROM user_requests").fetchone()
        assert row["status"] == "responded" and json.loads(row["response"]) == {"base":"200"}
    else:
        c.store.cancel(101, run.run_id)
        with pytest.raises(RunConflict):
            questions.answer(**answer)
        row = c.conn.execute("SELECT status,response FROM user_requests").fetchone()
        assert row["status"] == "expired" and row["response"] is None
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 1


def test_same_question_after_changed_context_does_not_reuse_an_old_answer(coordination):
    """An identical question in a new context remains unanswered; old operation recovery preserves provenance without overwriting the new premise."""
    from backend.tests.runtime.test_human_questions import setup_question

    c = coordination
    questions, _, lease, _, first = setup_question(c)
    questions.park(lease)
    command = dict(project_id=101, task_id=1001, request_id=first["request_id"], expected_version=1, operation_key="first-base", answers={"base":"200"})
    assert questions.answer(**command) == 2
    assert c.store.correct_context(project_id=101, task_id=1001, expected_version=2, operation_key="changed-base", statement="Use base 300 from now on.", source_kind="user_message", source_reference="owner:changed") == 3
    assert questions.answer(**command) == 2
    assert c.store.context_snapshot(101, 1001)["context_version"] == 3
    c.spec = replace(c.spec, operation_key="new-context-question", context_version=3)
    questions, _, lease, _, second = setup_question(c, question_key="new-base-question")
    assert first["request_id"] != second["request_id"]
    rows = c.conn.execute("SELECT status,response,body FROM user_requests ORDER BY id").fetchall()
    assert rows[0]["body"] == rows[1]["body"]
    assert rows[1]["status"] == "pending" and rows[1]["response"] is None
    questions.park(lease)
    assert questions.answer(project_id=101, task_id=1001, request_id=second["request_id"], expected_version=3, operation_key="second-base", answers={"base":"300"}) == 4
    context = c.store.context_snapshot(101, 1001)
    assert [entry["answers"] for entry in context["user_answers"]] == [{"base":"200"}, {"base":"300"}]
    assert c.conn.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0] == 0


async def test_immediate_owner_messages_are_distinct_and_retries_do_not_throttle_them(coordination, workspace_app):
    """Two consecutive owner messages get separate durable receipts; retry neither duplicates nor suppresses the second message."""
    c = coordination
    c.store.admit(c.spec, conversation_thread="consecutive-owner")
    bodies = [dict(operation_key=f"note-{i}", message=text, thread_id="consecutive-owner") for i,text in enumerate(("First observation.", "Second observation, with a different example."))]
    async with workspace_app.router.lifespan_context(workspace_app), owner_client(workspace_app) as owner:
        replies = []
        for body in bodies:
            response = await owner.post("/api/chat/101", json=body)
            assert response.status_code == 201, response.text
            replies.append(response.json())
        assert replies[0]["id"] < replies[1]["id"]
        for body, receipt in zip(bodies, replies, strict=True):
            assert (await owner.post("/api/chat/101", json=body)).json() == receipt
        page = (await owner.get("/api/chat/101")).json()
        assert [r["message"] for r in page][-2:] == [body["message"] for body in bodies]
        assert all(r["delivery"] == "recorded" for r in replies)
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 1
    assert c.conn.execute("SELECT count(*) FROM chat_messages").fetchone()[0] == 3


def test_duplicate_actor_labels_require_an_exact_recipient_without_fanout(coordination):
    """Two admitted researchers with the same label do not turn a directed message into a role broadcast or another assignment."""
    from backend.research.models import ResearchNotFound

    c = coordination
    messages, sender, recipient = peers(c)
    c.conn.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1003,101,'research','Another researcher')")
    c.conn.commit()
    other = c.store.admit(replace(c.spec, task_id=1003, actor_id="author-b", operation_key="same-role"))
    targets = messages.recipients(sender[2])["items"]
    assert {r["run_id"] for r in targets if r["actor_id"] == "author-b"} == {recipient[0].run_id, other.run_id}
    with pytest.raises(ResearchNotFound):
        messages.send(sender[2], "ambiguous-role", **packet(recipient, recipient_run_id="author-b"))
    saved = messages.send(sender[2], "exact-recipient", **packet(recipient))
    assert saved["recipient_run_id"] == recipient[0].run_id
    assert [r[0] for r in c.conn.execute("SELECT recipient_run_id FROM runtime_agent_messages")] == [recipient[0].run_id]
    assert c.store.get(101, other.run_id).status == "queued"
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 3

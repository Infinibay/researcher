"""Atomic user instruction/run and proposal delivery, with real SQLite."""

from dataclasses import replace

import pytest

from backend.runtime.contracts import RunConflict, RunNotFound, StaleAttempt


def test_native_conversation_is_excluded_from_legacy_dispatch(coordination):
    """Native instructions remain canonical and cannot enter historical recipient reads or the old activation queue."""
    from backend.communication.owner_history import OwnerHistory

    c = coordination
    c.store.admit(c.spec, conversation_thread="native-thread")
    c.conn.execute(
        "INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,conversation_type,message) VALUES(101,'native-thread','user','researcher','user_to_agent','Native followup')"
    )
    c.conn.execute(
        "INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('legacy-thread',101,'user_chat')"
    )
    legacy_id = c.conn.execute(
        "INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,conversation_type,message) VALUES(101,'legacy-thread','user','researcher','user_to_agent','Legacy positive control')"
    ).lastrowid
    c.conn.commit()
    assert c.conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 0
    inbox = OwnerHistory(c.store).legacy_inbox(101, "researcher")
    assert [message["id"] for message in inbox] == [legacy_id]


def test_chat_instruction_and_run_share_one_durable_receipt(coordination):
    c = coordination
    first = c.store.admit(c.spec, conversation_thread="new-thread")
    duplicate = c.store.admit(c.spec, conversation_thread="new-thread")
    assert first == duplicate
    messages = c.conn.execute("SELECT * FROM chat_messages").fetchall()
    assert len(messages) == 1
    assert messages[0]["message"] == c.spec.prompt
    link = c.conn.execute("SELECT * FROM runtime_chat_links").fetchone()
    assert link["run_id"] == first.run_id
    assert link["user_message_id"] == messages[0]["id"]
    with pytest.raises(RunConflict):
        c.store.admit(c.spec, conversation_thread="another-thread")




def test_proposal_is_published_once_in_the_same_human_thread(coordination):
    c = coordination
    run = c.store.admit(c.spec, conversation_thread="conversation")
    lease = c.store.claim(101, run.run_id, "host")
    c.store.finish(
        lease, native_status="completed", summary="The source says X; interpretation Y."
    )
    c.store.finish(
        lease, native_status="completed", summary="The source says X; interpretation Y."
    )
    messages = c.conn.execute("SELECT * FROM chat_messages ORDER BY id").fetchall()
    assert len(messages) == 2
    assert messages[1]["thread_id"] == messages[0]["thread_id"] == "conversation"
    assert messages[1]["parent_message_id"] == messages[0]["id"]
    assert messages[1]["conversation_type"] == "agent_to_user"
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )


def test_foreign_or_other_task_threads_cannot_take_an_instruction(coordination):
    c = coordination
    c.store.admit(c.spec, conversation_thread="scoped")
    with pytest.raises(RunConflict):
        c.store.admit(
            replace(c.spec, task_id=1002, operation_key="other-task"),
            conversation_thread="scoped",
        )
    with pytest.raises(RunNotFound):
        c.store.admit(
            replace(c.spec, project_id=202, task_id=2002, operation_key="foreign"),
            conversation_thread="scoped",
        )
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 1


def test_event_failure_rolls_back_message_thread_and_admission(coordination):
    c = coordination
    c.conn.execute(
        "CREATE TRIGGER reject_chat_admission BEFORE INSERT ON events_log BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    c.conn.commit()
    with pytest.raises(Exception, match="injected"):
        c.store.admit(c.spec, conversation_thread="rollback")
    for table in (
        "runtime_runs",
        "runtime_commands",
        "runtime_chat_links",
        "chat_messages",
        "conversation_threads",
    ):
        assert c.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_late_superseded_proposal_is_not_sent_as_a_current_reply(coordination):
    c = coordination
    run = c.store.admit(c.spec, conversation_thread="conversation")
    lease = c.store.claim(101, run.run_id, "host")
    c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=1,
        operation_key="correction",
        statement="Use a different example",
        source_kind="user_example",
        source_reference="user:2",
    )
    with pytest.raises(StaleAttempt):
        c.store.finish(lease, native_status="completed", summary="Old answer")
    assert c.conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == 1


def test_task_execution_history_is_visible_after_task_completion(coordination):
    """Keep scoped owner history readable after actual versioned delivery and owner acceptance."""
    from backend.tests.runtime.test_result_acceptance import make_accepted_result

    c, run = make_accepted_result(coordination)
    assert c.store.task_runs(101, 1001)[0].run_id == run.run_id
    assert c.store.context_snapshot(101, 1001)["context_version"] == 1
    with pytest.raises(RunNotFound):
        c.store.task_runs(202, 1001)


def test_recent_runs_follow_admission_even_when_wall_clock_moves_back(coordination):
    c = coordination
    first = c.store.admit(c.spec)
    c.store.cancel(101, first.run_id)
    c.now[0] -= 10
    second = c.store.admit(replace(c.spec, operation_key="after-clock-change"))
    assert [run.run_id for run in c.store.task_runs(101, 1001)] == [
        second.run_id,
        first.run_id,
    ]

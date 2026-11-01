"""Questions pause authority; answers change context without pretending application."""

import json
from dataclasses import replace

import pytest


def setup_question(c):
    from backend.runtime.questions import Question, QuestionSet
    from backend.runtime.sqlite_questions import SQLiteQuestionStore

    run = c.store.admit(c.spec, conversation_thread="human-thread")
    lease = c.store.claim(101, run.run_id, "host")
    c.store.bind_thread(lease, thread_id="native-thread")
    c.store.bind_native(lease, thread_id="native-thread", turn_id="native-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="researcher-a",
        permissions={"sources.read", "sources.capture", "questions.ask"},
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    questions = SQLiteQuestionStore(c.store, c.research)
    draft = QuestionSet(
        (
            Question(
                "base",
                "¿Qué base quieres en el ejemplo?",
                "La política da una tasa, no el valor que prefieres.",
                ("100", "200"),
                "Con base 100, impuesto = 21.",
            ),
        )
    )
    receipt = questions.ask(scope, "ask-base", draft)
    return questions, run, lease, scope, receipt


def test_question_and_pause_intent_commit_with_revocation_but_wait_for_closed_peers(
    coordination,
):
    from backend.research.models import ResearchForbidden, SourceDraft
    from backend.runtime.contracts import RunConflict

    c = coordination
    questions, run, lease, scope, receipt = setup_question(c)
    assert c.store.get(101, run.run_id).status == "cancelling"
    with pytest.raises(ResearchForbidden):
        c.research.capture_source(
            scope,
            "too-late",
            SourceDraft("web", "https://example.org", "No", "No late effect"),
            intent={},
        )
    with pytest.raises(RunConflict):
        questions.answer(
            project_id=101,
            task_id=1001,
            request_id=receipt["request_id"],
            expected_version=1,
            operation_key="early-answer",
            answers={"base": "200"},
        )
    parked = questions.park(lease)
    assert parked.status == "waiting_input"
    assert c.conn.execute("SELECT status FROM user_requests").fetchone()[0] == "pending"
    with pytest.raises(RunConflict):
        c.store.admit(replace(c.spec, operation_key="duplicate-work"))


def test_answer_is_versioned_with_question_and_receipt_and_never_starts_inference(
    coordination,
):
    c = coordination
    questions, run, lease, _, receipt = setup_question(c)
    questions.park(lease)
    command = {
        "project_id": 101,
        "task_id": 1001,
        "request_id": receipt["request_id"],
        "expected_version": 1,
        "operation_key": "answer-base",
        "answers": {"base": "200"},
    }
    assert questions.answer(**command) == 2
    assert questions.answer(**command) == 2
    assert c.store.get(101, run.run_id).status == "superseded"
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 1
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    row = c.conn.execute("SELECT response,status FROM user_requests").fetchone()
    assert row["status"] == "responded" and json.loads(row["response"]) == {
        "base": "200"
    }
    context = c.store.context_snapshot(101, 1001)
    assert context["user_answers"][0]["questions"][0]["question"].startswith(
        "¿Qué base"
    )
    assert context["user_answers"][0]["answers"] == {"base": "200"}
    assert context["corrections"][0]["source_kind"] == "user_message"
    assert "200" in context["corrections"][0]["statement"]


def test_context_correction_expires_question_and_rejects_its_stale_answer(coordination):
    from backend.runtime.contracts import RunConflict

    c = coordination
    questions, run, lease, _, receipt = setup_question(c)
    questions.park(lease)
    c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=1,
        operation_key="new-premise",
        statement="Now compare a different policy.",
        source_kind="user_message",
        source_reference="user:3",
    )
    assert c.conn.execute("SELECT status FROM user_requests").fetchone()[0] == "expired"
    assert c.store.get(101, run.run_id).status == "superseded"
    with pytest.raises(RunConflict):
        questions.answer(
            project_id=101,
            task_id=1001,
            request_id=receipt["request_id"],
            expected_version=1,
            operation_key="stale",
            answers={"base": "200"},
        )


def test_stop_wins_over_question_pause_and_question_does_not_reopen_the_run(
    coordination,
):
    c = coordination
    questions, run, lease, _, _ = setup_question(c)
    c.store.cancel(101, run.run_id)
    assert questions.park(lease).status == "cancelled"
    assert c.conn.execute("SELECT status FROM user_requests").fetchone()[0] == "expired"


def test_answer_scope_and_exact_question_ids_are_checked_before_any_change(
    coordination,
):
    from backend.runtime.contracts import RunConflict, RunNotFound

    c = coordination
    questions, _, lease, _, receipt = setup_question(c)
    questions.park(lease)
    command = {
        "project_id": 101,
        "task_id": 1001,
        "request_id": receipt["request_id"],
        "expected_version": 1,
        "operation_key": "answer",
        "answers": {"different": "200"},
    }
    with pytest.raises(ValueError):
        questions.answer(**command)
    with pytest.raises(RunNotFound):
        questions.answer(
            **{
                **command,
                "project_id": 202,
                "task_id": 2002,
                "answers": {"base": "200"},
            }
        )
    assert c.conn.execute("SELECT status FROM user_requests").fetchone()[0] == "pending"
    questions.answer(**{**command, "answers": {"base": "200"}})
    with pytest.raises(RunConflict):
        questions.answer(**{**command, "answers": {"base": "100"}})


def test_question_event_failure_rolls_back_question_chat_pause_and_revocation(
    coordination,
):

    c = coordination
    c.conn.execute(
        "CREATE TRIGGER reject_question BEFORE INSERT ON user_requests BEGIN SELECT RAISE(ABORT,'question insertion failed'); END"
    )
    c.conn.commit()
    with pytest.raises(Exception, match="question insertion failed"):
        setup_question(c)
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_question_links").fetchone()[0] == 0
    )
    assert c.conn.execute("SELECT COUNT(*) FROM user_requests").fetchone()[0] == 0
    assert c.conn.execute("SELECT status FROM runtime_runs").fetchone()[0] == "running"
    assert c.conn.execute("SELECT revoked_at FROM tool_grants").fetchone()[0] is None


def test_answer_event_failure_rolls_back_response_revision_expiry_and_chat(
    coordination,
):
    c = coordination
    questions, _, lease, _, receipt = setup_question(c)
    questions.park(lease)
    before = c.conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    c.conn.execute(
        "CREATE TRIGGER reject_answer BEFORE INSERT ON runtime_context_revisions BEGIN SELECT RAISE(ABORT,'answer revision failed'); END"
    )
    c.conn.commit()
    with pytest.raises(Exception, match="answer revision failed"):
        questions.answer(
            project_id=101,
            task_id=1001,
            request_id=receipt["request_id"],
            expected_version=1,
            operation_key="answer",
            answers={"base": "200"},
        )
    assert c.conn.execute("SELECT status FROM user_requests").fetchone()[0] == "pending"
    assert c.conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == before
    assert c.store.context_snapshot(101, 1001)["context_version"] == 1

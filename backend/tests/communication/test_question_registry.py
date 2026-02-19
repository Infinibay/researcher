"""Tests for QuestionRegistry in backend/communication/question_registry.py."""

import pytest

from backend.communication.question_registry import (
    QuestionRegistry,
    _normalize_question,
    _question_hash,
)


@pytest.fixture()
def registry():
    return QuestionRegistry()


# ── Helper tests ─────────────────────────────────────────────────────────────


class TestNormalizeQuestion:
    def test_basic_normalization(self):
        assert _normalize_question("  Hello, WORLD!  ") == "hello world"

    def test_collapse_whitespace(self):
        assert _normalize_question("a   b\n\tc") == "a b c"

    def test_strip_punctuation(self):
        assert _normalize_question("what's up?") == "whats up"


class TestQuestionHash:
    def test_same_text_same_hash(self):
        assert _question_hash("hello world") == _question_hash("hello world")

    def test_normalized_variants_match(self):
        assert _question_hash("Hello, World!") == _question_hash("hello world")

    def test_different_text_different_hash(self):
        assert _question_hash("hello") != _question_hash("goodbye")


# ── check_existing ───────────────────────────────────────────────────────────


class TestCheckExisting:
    def test_no_existing_returns_none(self, registry, seeded_project):
        result = registry.check_existing(project_id=1, question="What is the stack?")
        assert result is None

    def test_returns_cached_answer(self, registry, seeded_project, db_conn):
        qhash = _question_hash("What is the tech stack?")
        db_conn.execute(
            """INSERT INTO clarification_questions
               (project_id, asked_by, asked_to_role, question_hash,
                question_text, answer_text, answered_by, status, answered_at)
               VALUES (1, 'agent-1', 'team_lead', ?, 'What is the tech stack?',
                       'Python with FastAPI', 'lead-1', 'answered', CURRENT_TIMESTAMP)""",
            (qhash,),
        )
        db_conn.commit()

        result = registry.check_existing(project_id=1, question="What is the tech stack?")
        assert result is not None
        assert result["answer"] == "Python with FastAPI"
        assert result["answered_by"] == "lead-1"

    def test_pending_question_not_returned(self, registry, seeded_project, db_conn):
        qhash = _question_hash("What is the deadline?")
        db_conn.execute(
            """INSERT INTO clarification_questions
               (project_id, asked_by, asked_to_role, question_hash,
                question_text, status)
               VALUES (1, 'agent-1', 'team_lead', ?, 'What is the deadline?', 'pending')""",
            (qhash,),
        )
        db_conn.commit()

        result = registry.check_existing(project_id=1, question="What is the deadline?")
        assert result is None

    def test_different_project_not_returned(self, registry, seeded_project, db_conn):
        qhash = _question_hash("What is the tech stack?")
        db_conn.execute(
            """INSERT INTO clarification_questions
               (project_id, asked_by, asked_to_role, question_hash,
                question_text, answer_text, answered_by, status, answered_at)
               VALUES (1, 'agent-1', 'team_lead', ?, 'What is the tech stack?',
                       'Python with FastAPI', 'lead-1', 'answered', CURRENT_TIMESTAMP)""",
            (qhash,),
        )
        db_conn.commit()

        result = registry.check_existing(project_id=999, question="What is the tech stack?")
        assert result is None


# ── register_question ────────────────────────────────────────────────────────


class TestRegisterQuestion:
    def test_register_returns_id(self, registry, seeded_project):
        qid = registry.register_question(
            project_id=1,
            task_id=None,
            asked_by="agent-1",
            asked_to_role="team_lead",
            question="What is the tech stack?",
        )
        assert isinstance(qid, int)
        assert qid > 0

    def test_registered_question_persists(self, registry, seeded_project, db_conn):
        registry.register_question(
            project_id=1,
            task_id=None,
            asked_by="agent-1",
            asked_to_role="team_lead",
            question="What is the tech stack?",
        )

        row = db_conn.execute(
            "SELECT * FROM clarification_questions WHERE project_id = 1"
        ).fetchone()
        assert row is not None
        assert row["asked_by"] == "agent-1"
        assert row["status"] == "pending"
        assert row["question_text"] == "What is the tech stack?"


# ── register_answer ──────────────────────────────────────────────────────────


class TestRegisterAnswer:
    def test_answer_updates_question(self, registry, seeded_project, db_conn):
        qid = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="What stack?",
        )

        registry.register_answer(
            question_id=qid,
            answer="Python with FastAPI",
            answered_by="lead-1",
        )

        row = db_conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ?", (qid,)
        ).fetchone()
        assert row["status"] == "answered"
        assert row["answer_text"] == "Python with FastAPI"
        assert row["answered_by"] == "lead-1"
        assert row["answered_at"] is not None


# ── register_assumption ──────────────────────────────────────────────────────


class TestRegisterAssumption:
    def test_assumption_updates_question(self, registry, seeded_project, db_conn):
        qid = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="What stack?",
        )

        registry.register_assumption(
            question_id=qid,
            assumption="Assuming Python based on project description.",
        )

        row = db_conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ?", (qid,)
        ).fetchone()
        assert row["status"] == "assumed"
        assert row["assumption"] == "Assuming Python based on project description."


# ── get_agent_question_count ─────────────────────────────────────────────────


class TestGetAgentQuestionCount:
    def test_zero_when_none(self, registry, seeded_project):
        count = registry.get_agent_question_count(
            project_id=1, agent_id="agent-1",
        )
        assert count == 0

    def test_counts_by_agent(self, registry, seeded_project):
        for i in range(3):
            registry.register_question(
                project_id=1, task_id=None, asked_by="agent-1",
                asked_to_role="team_lead", question=f"Question {i}?",
            )
        registry.register_question(
            project_id=1, task_id=None, asked_by="agent-2",
            asked_to_role="team_lead", question="Other question?",
        )

        assert registry.get_agent_question_count(project_id=1, agent_id="agent-1") == 3
        assert registry.get_agent_question_count(project_id=1, agent_id="agent-2") == 1

    def test_counts_by_task(self, registry, seeded_project, db_conn):
        # Insert a task
        db_conn.execute(
            """INSERT INTO tasks (id, project_id, title, status, type, priority)
               VALUES (10, 1, 'Test Task', 'in_progress', 'code', 1)"""
        )
        db_conn.commit()

        registry.register_question(
            project_id=1, task_id=10, asked_by="agent-1",
            asked_to_role="team_lead", question="Task 10 question?",
        )
        registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="General question?",
        )

        assert registry.get_agent_question_count(
            project_id=1, agent_id="agent-1", task_id=10,
        ) == 1


# ── propagate_answer ─────────────────────────────────────────────────────────


class TestPropagateAnswer:
    def test_propagates_to_similar_pending(self, registry, seeded_project, db_conn):
        # Agent-1 asks a question and gets answered
        qid1 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="What is the tech stack?",
        )
        # Agent-2 asks the same question (pending)
        qid2 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-2",
            asked_to_role="team_lead", question="What is the tech stack?",
        )

        # Answer agent-1's question
        registry.register_answer(qid1, "Python + FastAPI", "lead-1")

        # Propagate
        registry.propagate_answer(question_id=qid1, project_id=1)

        # Agent-2's question should now be answered
        row = db_conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ?", (qid2,)
        ).fetchone()
        assert row["status"] == "answered"
        assert row["answer_text"] == "Python + FastAPI"
        assert row["answered_by"] == "lead-1"

    def test_does_not_propagate_to_different_questions(self, registry, seeded_project, db_conn):
        qid1 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="What is the tech stack?",
        )
        qid2 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-2",
            asked_to_role="team_lead", question="When is the deadline?",
        )

        registry.register_answer(qid1, "Python + FastAPI", "lead-1")
        registry.propagate_answer(question_id=qid1, project_id=1)

        row = db_conn.execute(
            "SELECT * FROM clarification_questions WHERE id = ?", (qid2,)
        ).fetchone()
        assert row["status"] == "pending"

    def test_creates_notice_on_propagation(self, registry, seeded_project, db_conn):
        qid1 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="What is the stack?",
        )
        qid2 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-2",
            asked_to_role="team_lead", question="What is the stack?",
        )

        registry.register_answer(qid1, "Python", "lead-1")
        registry.propagate_answer(question_id=qid1, project_id=1)

        notice = db_conn.execute(
            "SELECT * FROM notices WHERE project_id = 1 AND title = 'Answer Propagated'"
        ).fetchone()
        assert notice is not None
        assert "auto-applied" in notice["content"]


# ── get_answered_questions ───────────────────────────────────────────────────


class TestGetAnsweredQuestions:
    def test_empty_when_none(self, registry, seeded_project):
        result = registry.get_answered_questions(project_id=1)
        assert result == []

    def test_returns_answered_questions(self, registry, seeded_project):
        qid = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="What stack?",
        )
        registry.register_answer(qid, "Python", "lead-1")

        result = registry.get_answered_questions(project_id=1)
        assert len(result) == 1
        assert result[0]["asked_by"] == "agent-1"
        assert result[0]["answer_text"] == "Python"
        assert result[0]["answered_by"] == "lead-1"

    def test_excludes_pending_and_assumed(self, registry, seeded_project):
        qid1 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="Answered Q?",
        )
        registry.register_answer(qid1, "Yes", "lead-1")

        qid2 = registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="Assumed Q?",
        )
        registry.register_assumption(qid2, "Assuming yes")

        registry.register_question(
            project_id=1, task_id=None, asked_by="agent-1",
            asked_to_role="team_lead", question="Pending Q?",
        )

        result = registry.get_answered_questions(project_id=1)
        assert len(result) == 1
        assert result[0]["question_text"] == "Answered Q?"

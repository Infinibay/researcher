"""Tests for LoopGuard in backend/communication/loop_guard.py."""

import sqlite3

import pytest

from backend.communication.loop_guard import (
    LoopGuard,
    LoopGuardVerdict,
    _fingerprint,
    _jaccard,
    _normalize_text,
    _trigram_set,
)
from backend.config.settings import settings


@pytest.fixture()
def guard():
    return LoopGuard()


# ── Helper tests ─────────────────────────────────────────────────────────────


class TestNormalizeText:
    def test_basic_normalization(self):
        assert _normalize_text("  Hello, WORLD!  ") == "hello world"

    def test_collapse_whitespace(self):
        assert _normalize_text("a   b\n\tc") == "a b c"

    def test_strip_punctuation(self):
        assert _normalize_text("what's up?") == "whats up"


class TestFingerprint:
    def test_same_text_same_fingerprint(self):
        assert _fingerprint("hello world") == _fingerprint("hello world")

    def test_normalized_variants_match(self):
        assert _fingerprint("Hello, World!") == _fingerprint("hello world")

    def test_different_text_different_fingerprint(self):
        assert _fingerprint("hello") != _fingerprint("goodbye")


class TestTrigramSimilarity:
    def test_identical_texts(self):
        a = _trigram_set("hello world")
        assert _jaccard(a, a) == 1.0

    def test_completely_different(self):
        a = _trigram_set("aaaa")
        b = _trigram_set("zzzz")
        assert _jaccard(a, b) == 0.0

    def test_similar_texts_high_jaccard(self):
        a = _trigram_set("what is the tech stack for this project")
        b = _trigram_set("what is the technology stack for this project")
        assert _jaccard(a, b) > 0.5

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 1.0


# ── System bypass ────────────────────────────────────────────────────────────


class TestSystemBypass:
    def test_system_messages_bypass_all_checks(self, guard):
        verdict = guard.check_all(
            from_agent="system",
            message="any message",
        )
        assert verdict.allowed is True
        assert verdict.action == "allow"


# ── Disabled guard ───────────────────────────────────────────────────────────


class TestDisabledGuard:
    def test_disabled_guard_allows_everything(self, guard, monkeypatch):
        monkeypatch.setattr(settings, "LOOP_GUARD_ENABLED", False)
        verdict = guard.check_all(
            from_agent="dev-1",
            message="hello",
        )
        assert verdict.allowed is True
        assert verdict.action == "allow"


# ── Deduplication ────────────────────────────────────────────────────────────


class TestDedup:
    def test_first_message_passes(self, guard, seeded_project):
        verdict = guard.check_all(
            from_agent="agent-1",
            message="What is the tech stack?",
            to_role="team_lead",
            project_id=1,
        )
        assert verdict.action == "allow"

    def test_exact_duplicate_blocked(self, guard, seeded_project, db_conn):
        msg = "What is the tech stack for this project?"

        # Insert a thread and message
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('t1', 1, 'task_discussion')"""
        )
        db_conn.execute(
            """INSERT INTO chat_messages
               (project_id, thread_id, from_agent, to_role, message,
                conversation_type)
               VALUES (1, 't1', 'agent-1', 'team_lead', ?, 'agent_to_agent')""",
            (msg,),
        )
        db_conn.commit()
        msg_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Record fingerprint
        guard.record_fingerprint(
            message_id=msg_id,
            message=msg,
            from_agent="agent-1",
            to_role="team_lead",
            thread_id="t1",
            project_id=1,
        )

        # Second identical message should be blocked
        verdict = guard.check_all(
            from_agent="agent-1",
            message=msg,
            to_role="team_lead",
            project_id=1,
        )
        assert verdict.action == "block"
        assert "duplicate" in verdict.reason.lower()

    def test_different_message_passes(self, guard, seeded_project, db_conn):
        msg1 = "What is the tech stack?"
        msg2 = "When is the deadline?"

        # Insert and record first message
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('t2', 1, 'task_discussion')"""
        )
        db_conn.execute(
            """INSERT INTO chat_messages
               (project_id, thread_id, from_agent, to_role, message,
                conversation_type)
               VALUES (1, 't2', 'agent-1', 'team_lead', ?, 'agent_to_agent')""",
            (msg1,),
        )
        db_conn.commit()
        msg_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        guard.record_fingerprint(
            message_id=msg_id, message=msg1, from_agent="agent-1",
            to_role="team_lead", thread_id="t2", project_id=1,
        )

        # Different message should pass
        verdict = guard.check_all(
            from_agent="agent-1",
            message=msg2,
            to_role="team_lead",
            project_id=1,
        )
        assert verdict.action == "allow"

    def test_near_duplicate_blocked(self, guard, seeded_project, db_conn):
        msg1 = "What is the technology stack for this project please?"
        msg2 = "What is the tech stack for this project please?"

        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('t3', 1, 'task_discussion')"""
        )
        db_conn.execute(
            """INSERT INTO chat_messages
               (project_id, thread_id, from_agent, to_role, message,
                conversation_type)
               VALUES (1, 't3', 'agent-1', 'team_lead', ?, 'agent_to_agent')""",
            (msg1,),
        )
        db_conn.commit()
        msg_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        guard.record_fingerprint(
            message_id=msg_id, message=msg1, from_agent="agent-1",
            to_role="team_lead", thread_id="t3", project_id=1,
        )

        verdict = guard.check_all(
            from_agent="agent-1",
            message=msg2,
            to_role="team_lead",
            project_id=1,
        )
        assert verdict.action == "block"
        assert "duplicate" in verdict.reason.lower()


# ── Rate Limiting ────────────────────────────────────────────────────────────


class TestRateLimit:
    def test_within_limit_passes(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('rl1', 1, 'task_discussion')"""
        )
        db_conn.commit()

        # Add a few fingerprints (below limit)
        for i in range(3):
            db_conn.execute(
                """INSERT INTO message_fingerprints
                   (message_id, project_id, from_agent, thread_id, fingerprint)
                   VALUES (?, 1, 'agent-1', 'rl1', ?)""",
                (i + 100, f"fp_{i}"),
            )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="new message",
            thread_id="rl1",
            project_id=1,
        )
        assert verdict.action == "allow"

    def test_exceeding_per_thread_limit_throttled(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('rl2', 1, 'task_discussion')"""
        )
        db_conn.commit()

        # Add enough fingerprints to exceed per-thread limit
        for i in range(settings.LOOP_RATE_PER_THREAD + 1):
            db_conn.execute(
                """INSERT INTO message_fingerprints
                   (message_id, project_id, from_agent, thread_id, fingerprint)
                   VALUES (?, 1, 'agent-1', 'rl2', ?)""",
                (i + 200, f"rl_fp_{i}"),
            )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="yet another message",
            thread_id="rl2",
            project_id=1,
        )
        assert verdict.action == "throttle"
        assert "rate_limit" in verdict.reason


# ── Ping-Pong Detection ─────────────────────────────────────────────────────


class TestPingPong:
    def test_alternating_pattern_detected(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('pp1', 1, 'task_discussion')"""
        )
        # Create alternating messages
        agents = ["agent-1", "lead-1"] * 4
        for i, agent in enumerate(agents):
            db_conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, message,
                    conversation_type)
                   VALUES (1, 'pp1', ?, ?, 'agent_to_agent')""",
                (agent, f"message {i}"),
            )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="another question",
            thread_id="pp1",
            project_id=1,
        )
        assert verdict.action == "escalate"
        assert "ping_pong" in verdict.reason

    def test_non_alternating_passes(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('pp2', 1, 'task_discussion')"""
        )
        # Non-alternating: multiple messages from same agent
        for i in range(4):
            db_conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, message,
                    conversation_type)
                   VALUES (1, 'pp2', 'agent-1', ?, 'agent_to_agent')""",
                (f"message {i}",),
            )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="new message",
            thread_id="pp2",
            project_id=1,
        )
        # Should not detect ping-pong (only 1 unique agent)
        assert verdict.action != "escalate"


# ── Circuit Breaker ──────────────────────────────────────────────────────────


class TestCircuitBreaker:
    def test_open_circuit_blocks(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO circuit_breaker
               (task_type, state, failure_count, opened_at, threshold, window_seconds)
               VALUES ('comm:cb1', 'open', 5, CURRENT_TIMESTAMP, 3, 60)"""
        )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="hello",
            thread_id="cb1",
            project_id=1,
        )
        assert verdict.action == "block"
        assert "circuit" in verdict.reason.lower()

    def test_closed_circuit_passes(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO circuit_breaker
               (task_type, state, failure_count, threshold, window_seconds)
               VALUES ('comm:cb2', 'closed', 0, 3, 60)"""
        )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="hello from closed",
            thread_id="cb2",
            project_id=1,
        )
        # Closed circuit should not block (may pass all other checks too)
        assert verdict.action != "block" or "circuit" not in verdict.reason.lower()

    def test_half_open_allows_one(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO circuit_breaker
               (task_type, state, failure_count, threshold, window_seconds)
               VALUES ('comm:cb3', 'half_open', 2, 3, 60)"""
        )
        db_conn.commit()

        verdict = guard.check_all(
            from_agent="agent-1",
            message="test half open message",
            thread_id="cb3",
            project_id=1,
        )
        # Half-open should allow one through (circuit breaker check passes)
        assert verdict.action != "block" or "circuit" not in verdict.reason.lower()

    def test_failures_open_circuit(self, guard, seeded_project, db_conn):
        # Increment failures up to threshold
        for _ in range(settings.LOOP_CIRCUIT_THRESHOLD):
            guard._increment_circuit_breaker("cbtest")

        row = db_conn.execute(
            "SELECT state FROM circuit_breaker WHERE task_type = 'comm:cbtest'"
        ).fetchone()
        assert row is not None
        assert row["state"] == "open"

    def test_reset_circuit_breaker(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO circuit_breaker
               (task_type, state, failure_count, threshold, window_seconds)
               VALUES ('comm:reset1', 'open', 5, 3, 60)"""
        )
        db_conn.commit()

        guard.reset_circuit_breaker("reset1")

        row = db_conn.execute(
            "SELECT state, failure_count FROM circuit_breaker WHERE task_type = 'comm:reset1'"
        ).fetchone()
        assert row["state"] == "closed"
        assert row["failure_count"] == 0


# ── Context Summary ──────────────────────────────────────────────────────────


class TestContextSummary:
    def test_no_summary_for_short_threads(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('ctx1', 1, 'task_discussion')"""
        )
        # Only 2 messages (< 5 threshold)
        for i in range(2):
            db_conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, message, conversation_type)
                   VALUES (1, 'ctx1', 'agent-1', ?, 'agent_to_agent')""",
                (f"msg {i}",),
            )
        db_conn.commit()

        summary = guard._build_context_summary("ctx1", "agent-1")
        assert summary == ""

    def test_summary_for_long_threads(self, guard, seeded_project, db_conn):
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('ctx2', 1, 'task_discussion')"""
        )
        for i in range(6):
            db_conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, message, conversation_type)
                   VALUES (1, 'ctx2', ?, ?, 'agent_to_agent')""",
                (f"agent-{i % 2}", f"message number {i}"),
            )
        db_conn.commit()

        summary = guard._build_context_summary("ctx2", "agent-0")
        assert "Thread History" in summary
        assert "message number" in summary


# ── Incident Recording ───────────────────────────────────────────────────────


class TestIncidentRecording:
    def test_incident_recorded_on_block(self, guard, seeded_project, db_conn):
        msg = "Duplicate question"

        # Create and record first message
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type)
               VALUES ('inc1', 1, 'task_discussion')"""
        )
        db_conn.execute(
            """INSERT INTO chat_messages
               (project_id, thread_id, from_agent, message, conversation_type)
               VALUES (1, 'inc1', 'agent-1', ?, 'agent_to_agent')""",
            (msg,),
        )
        db_conn.commit()
        msg_id = db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        guard.record_fingerprint(
            message_id=msg_id, message=msg, from_agent="agent-1",
            thread_id="inc1", project_id=1,
        )

        # Trigger block
        guard.check_all(
            from_agent="agent-1",
            message=msg,
            thread_id="inc1",
            project_id=1,
        )

        # Check incident was recorded
        row = db_conn.execute(
            "SELECT * FROM loop_incidents WHERE project_id = 1"
        ).fetchone()
        assert row is not None
        assert row["incident_type"] == "duplicate_message"
        assert row["action_taken"] == "blocked"

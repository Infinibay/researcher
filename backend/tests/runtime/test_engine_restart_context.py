"""A fresh coordinator preserves queued intent, a pending question and an evidenced correction together before any new native dispatch."""

import json
from dataclasses import replace
from types import SimpleNamespace

from backend.research.sqlite_store import SQLiteResearchStore
from backend.runtime.peer_registry import AttemptPeers
from backend.runtime.questions import Question, QuestionSet
from backend.runtime.recovery import RunRecovery
from backend.runtime.sqlite_questions import SQLiteQuestionStore
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.runtime.workspaces import WorkspaceRegistry
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


async def test_new_coordinator_retains_pending_work_question_and_correction_without_native_replay(service_setup):
    """Reopen real SQLite under a fresh host owner, reconcile an unbound historical question and deliver only the explicitly reselected corrected request; historical native identities are synthetic."""
    s = service_setup
    c = s.c
    binding = WorkspaceRegistry(c.database, s.root).bind(101, 11)
    version = c.store.correct_context(project_id=101, task_id=1001, expected_version=1,
        operation_key='annual-example', statement='Use yearly totals, not monthly.',
        source_kind='user_example', source_reference='owner-example-42')
    pending = replace(c.spec, context_version=version, operation_key='queued-corrected')
    queued = c.store.admit(pending, binding=binding)
    question_run = c.store.admit(replace(c.spec, task_id=1002, operation_key='pending-question'), binding=binding)
    lease = c.store.claim(101, question_run.run_id, 'previous-host')
    AttemptPeers.prepare(c.store, lease)
    c.store.bind_native(lease, thread_id='historical-question-thread', turn_id='historical-question-turn')
    token = c.research.issue_grant(project_id=101, task_id=1002, agent_id=c.spec.actor_id, permissions={'questions.ask'})
    c.store.bind_grant(lease, c.research.authorize(token).grant_id)
    questions = SQLiteQuestionStore(c.store, c.research)
    asked = questions.ask(c.research.authorize(token), 'original-question', QuestionSet((Question('base', '¿Qué base prefieres?'),)))
    question_links = [tuple(row) for row in c.conn.execute('SELECT * FROM runtime_question_links')]
    corrections = c.store.context_snapshot(101, 1001)['corrections']

    reopened = SimpleNamespace(**{**vars(c), 'store':SQLiteRunStore(c.database, clock=lambda:c.now[0]), 'research':SQLiteResearchStore(c.database, clock=lambda:c.now[0])})
    setup = SimpleNamespace(**{**vars(s), 'c':reopened})
    native = ControlledInference(setup)
    native.release.set()
    async with coordinator(setup, native) as service:
        assert native.prompts == []
        assert reopened.store.get(101, queued.run_id).status == 'queued'
        assert reopened.store.context_snapshot(101, 1001)['corrections'] == corrections
        assert [tuple(row) for row in c.conn.execute('SELECT * FROM runtime_question_links')] == question_links
        current = reopened.store.get(101, question_run.run_id)
        assert current.status == 'reconciling'
        recovered = RunRecovery(reopened.store).reconcile(project_id=101, run_id=question_run.run_id,
            attempt_id=lease.attempt_id, expected_fence=current.fence, operation_key='recover-question')
        assert recovered['status'] == 'waiting_input' and recovered['inference_started'] is False
        answered = SQLiteQuestionStore(reopened.store, reopened.research).answer(project_id=101, task_id=1002,
            request_id=asked['request_id'], expected_version=1, operation_key='answer-original', answers={'base':'200'})
        assert answered == 2 and native.prompts == []
        selected = await service.submit(pending, repository_id=11)
        assert selected.run_id == queued.run_id and native.prompts == []
        # Looking up the original admission receipt is deliberately read-only.
        command = dict(project_id=101, run_id=selected.run_id, expected_fence=selected.fence,
            context_version=2, operation_key='explicit-start-after-restart')
        await service.retry_start(**command)
        await service.wait(selected.run_id)
        await service.retry_start(**command)
        assert len(native.prompts) == 1
        context = json.loads(native.prompts[0])
        assert context['context_version'] == 2
        assert context['corrections'][0]['source_kind'] == 'user_example'
        assert context['corrections'][0]['statement'] == 'Use yearly totals, not monthly.'
        assert c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0] == 1
        assert c.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0] == 2
        assert c.conn.execute('SELECT thread_id FROM runtime_attempts WHERE id=?', (lease.attempt_id,)).fetchone()[0] == 'historical-question-thread'

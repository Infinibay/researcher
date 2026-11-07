"""Project-specific CI acceptance, immutable decisions and owner observation boundaries."""

from dataclasses import replace

import pytest

from backend.runtime.code_acceptance_policy import assess_code_checks
from backend.runtime.code_acceptances import CodeAcceptances
from backend.runtime.contracts import RunConflict, RunNotFound
from backend.tests.runtime.test_code_acceptance import (
    candidate_state as candidate_state,
    development_state as development_state,
    review_records as review_records,
    review_state as review_state,
    code_result as code_result,
    finish_owner_review,
    owner_intent,
)

pytestmark = pytest.mark.parametrize('review_state', ['frozen_author'], indirect=True)


def change(store, mode='allow_missing', revision=0, key='ci-policy'):
    """Record one owner's explicit project choice without creating model or publication work."""
    from backend.runtime.project_check_policy import ProjectCheckPolicies
    return ProjectCheckPolicies(store).update(101, operation_key=key, expected_revision=revision, mode=mode)


def test_unconfigured_project_requires_explicit_policy(review_records):
    """A fully reviewed candidate still needs a project decision; migration must not invent one."""
    s, _, candidate = finish_owner_review(review_records)
    state = CodeAcceptances(s.c.store).state(101, candidate['run_id'])
    assert not state['eligible']
    assert 'check_policy_unset' in {b['code'] for b in state['blockers']}


def test_policy_revision_binds_new_acceptance_and_preserves_old_decision(code_result):
    """Stale observations cannot accept under a changed policy; accepted receipts retain the decision that actually governed them."""
    s, _, candidate = code_result
    owner = CodeAcceptances(s.c.store)
    old = owner_intent(owner.state(101, candidate['run_id']))
    strict = change(s.c.store, 'require_tests', 1, 'strict')
    state = owner.state(101, candidate['run_id'])
    assert not state['eligible']
    assert 'tests_required' in {b['code'] for b in state['blockers']}
    with pytest.raises(RunConflict): owner.accept(101, candidate['run_id'], old)
    allowed = change(s.c.store, 'allow_missing', 2, 'allow-again')
    with pytest.raises(RunConflict, match='policy'): owner.accept(101, candidate['run_id'], old)
    observed = owner_intent(owner.state(101, candidate['run_id']))
    with pytest.raises(RunConflict, match='policy'):
        owner.accept(101, candidate['run_id'], replace(observed, check_policy_revision=None))
    accepted = owner.accept(101, candidate['run_id'], observed)
    assert accepted['check_policy'] == {'revision':3, 'mode':'allow_missing'}
    change(s.c.store, 'require_tests', 3, 'future-strict')
    assert owner.state(101, candidate['run_id'])['acceptance_current']
    assert owner.accept(101, candidate['run_id'], observed) == accepted
    assert strict['revision'] == 2 and allowed['revision'] == 3


def test_policy_history_scope_and_atomic_conflict(code_result, monkeypatch):
    """Project isolation, immutable replay and rollback protect decisions even after later owner changes."""
    from backend.runtime.project_check_policy import ProjectCheckPolicies
    s, _, _ = code_result
    policies = ProjectCheckPolicies(s.c.store)
    first = change(s.c.store, 'require_tests', 1)
    change(s.c.store, 'allow_missing', 2, 'second')
    assert change(s.c.store, 'require_tests', 1) == first
    assert policies.receipt(101, 'ci-policy') == first
    with pytest.raises(RunConflict): change(s.c.store, 'allow_missing', 1)
    with pytest.raises(RunConflict): change(s.c.store, 'allow_missing', 1, 'stale')
    with pytest.raises(RunNotFound): policies.receipt(202, 'ci-policy')
    assert policies.state(202) == {'revision':0, 'mode':None}
    def event_failure(*args):
        """Inject failure at the shared transaction boundary after staged writes."""
        raise RuntimeError('event write failed')
    monkeypatch.setattr(s.c.store, '_event', event_failure)
    with pytest.raises(RuntimeError): change(s.c.store, 'require_tests', 3, 'rollback')
    assert policies.state(101) == {'revision':3, 'mode':'allow_missing'}
    with pytest.raises(RunNotFound): policies.receipt(101, 'rollback')


@pytest.mark.parametrize('checks,strict_ok,limit', [
    ([], False, 'checks_absent'),
    ([{'state':'finished','result':{'status':'passed','tests':None,'skipped':None}}],False,'test_execution_unproven'),
    ([{'state':'finished','result':{'status':'passed','tests':3,'skipped':1}}],False,'check_partially_skipped'),
    ([{'state':'finished','result':{'status':'passed','tests':3,'skipped':0}}],True,None),
    ([{'state':'finished','result':{'status':'no_tests','tests':0,'skipped':0}}],False,'check_no_tests'),
    ([{'state':'finished','result':{'status':'skipped','tests':2,'skipped':2}}],False,'check_skipped'),
])
def test_project_policy_distinguishes_commands_and_executed_tests(review_state, checks, strict_ok, limit):
    """A successful generic command never stands in for collected tests; partial skips stay visible."""
    strict = assess_code_checks(checks, policy_mode='require_tests')
    allowed = assess_code_checks(checks, policy_mode='allow_missing')
    assert (not strict['blockers']) is strict_ok
    assert not allowed['blockers']
    if limit: assert limit in {item['code'] for item in allowed['limitations']}


@pytest.mark.parametrize('status', ['failed','infrastructure_error','invalidated',None])
def test_no_project_policy_overrides_failed_or_unknown_checks(review_state, status):
    """Acknowledging missing evidence never overrides a failed, stale or unconfirmed check."""
    checks = [{'state':'finished','result':{'status':status}}]
    for mode in ('require_tests','allow_missing'):
        assert assess_code_checks(checks, policy_mode=mode)['blockers']


async def test_policy_http_owner_csrf_and_read_only_recovery(code_result):
    """Actual HTTP enforces owner/CSRF scope and returns the original decision after a lost reply; saving creates no work."""
    import httpx
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    s, _, _ = code_result
    app = create_app(access=LocalAccess(pairing_key='check-policy-owner-fixture-long-enough'))
    path = '/api/projects/101/check-policy'
    body = {'operation_key':'web-policy','expected_revision':1,'mode':'require_tests'}
    before = s.c.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
        assert (await client.get(path)).status_code == 401
        assert (await client.post(path,json=body,headers={'Authorization':'Bearer tool-token'})).status_code == 401
        paired = await client.post('/api/session',json={'code':'check-policy-owner-fixture-long-enough'},headers={'X-Researcher-Client':'web'})
        assert paired.status_code == 200
        assert (await client.post(path,json=body)).status_code == 403
        headers = {'X-Researcher-CSRF':paired.json()['csrf_token']}
        assert (await client.post(path,json={**body,'mode':'ignore_failures'},headers=headers)).status_code == 422
        assert (await client.post(path,json={**body,'expected_revision':True},headers=headers)).status_code == 422
        saved = await client.post(path,json=body,headers=headers)
        assert saved.status_code == 200, saved.text
        assert saved.json()['inference_started'] is False
        assert (await client.get(path+'/changes/web-policy')).json() == saved.json()
        assert (await client.post(path,json=body,headers=headers)).json() == saved.json()
        assert (await client.get(path.replace('/101/','/202/')+'/changes/web-policy')).status_code == 404
        assert (await client.get(path)).json() == {'revision':2,'mode':'require_tests'}
    assert s.c.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0] == before


@pytest.mark.parametrize('schema_target', [65])
def test_policy_migration_preserves_existing_history_and_inverse_refuses_decisions(code_result):
    """An unused inverse restores schema64, but an owner decision cannot be silently erased by rollback."""
    import sqlite3
    from backend.db.project_check_policy_migration import restore_project_check_policy_schema
    from backend.tools.base.db import ensure_migrations

    s, _, _ = code_result
    with pytest.raises(RuntimeError, match='history'):
        restore_project_check_policy_schema(s.c.conn)
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        s.c.conn.execute("UPDATE runtime_project_check_policy_changes SET request_json='{}'")
    s.c.conn.rollback()
    from pathlib import Path
    database = Path(s.c.database).parent/'unused-policy.db'
    ensure_migrations(database,target_version=64)
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Retained')")
    ensure_migrations(database, target_version=65)
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT count(*) FROM runtime_project_check_policies').fetchone()[0] == 0
        restore_project_check_policy_schema(conn)
        assert conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0] == 64
        assert conn.execute('SELECT name FROM projects WHERE id=101').fetchone()[0] == 'Retained'

"""Actual owner HTTP and kernel-backed retention, with controlled inference; no synthetic closure can authorize the integration path."""

import json
from pathlib import Path

import pytest

from backend.tests.runtime.test_development_session import development_config as development_config
from backend.tests.runtime.test_owned_factory import owned_config as owned_config


@pytest.mark.timeout(180)
async def test_owner_quarantines_only_after_real_closure_and_restores_data_without_execution(development_config):
    """Actual private code is archived after original domain retirement; owner scope, stable receipts and quarantine admission fences stay enforced."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_development_workspace import fixture_git
    from backend.tests.runtime.test_workspace_delivery import owner_client
    c=development_config
    await fixture_git(c.s.workspace,'init','-q');await fixture_git(c.s.workspace,'add','fact.txt')
    await fixture_git(c.s.workspace,'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','base')
    c.settings['limits']['wall_seconds']=90;c.path.write_text(json.dumps(c.settings))
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        version=(await owner.get('/api/projects/101/tasks/1001/workspace')).json()['context']['context_version']
        response=await owner.post('/api/projects/101/tasks/1001/runs',json={'operation_key':'retention-author','context_version':version,'request':'Change fact.txt from137to200 and preserve the original source.','repository_id':11})
        assert response.status_code==202,response.text
        runtime=app.state.runtime_service;run=response.json();await runtime.wait(run['run_id'])
        state=(await owner.get(f"/api/projects/101/runs/{run['run_id']}/code-result")).json()
        assert state['candidate_current'],state
        attempt=state['candidate']['attempt_id'];base=f'/api/projects/101/retained-work/{attempt}'
        body={'operation_key':'owned-archive','retention_days':1,'acknowledge_unavailability':True}
        assert (await owner.post(base+'/quarantine',json=body,headers={'X-Researcher-CSRF':'wrong'})).status_code==403
        assert (await owner.post(base.replace('/101/','/202/')+'/quarantine',json=body)).status_code==404
        denied=await owner.post(base+'/quarantine',json={**body,'closed':True});assert denied.status_code==422
        accepted=await owner.post(base+'/quarantine',json=body);assert accepted.status_code==202,accepted.text
        await runtime.retention.wait(attempt)
        receipt=(await owner.get('/api/projects/101/retained-work/operations/owned-archive')).json()
        assert receipt['state']=='completed',receipt
        assert (await owner.post(base+'/quarantine',json=body)).json()==receipt
        assert (await owner.post(base+'/quarantine',json={**body,'retention_days':2})).status_code==409
        record=runtime.retention.store.list(101)[0];assert record['state']=='retained'
        with runtime.store._transaction() as conn:
            original=json.loads(conn.execute('SELECT original_json FROM workspace_retention WHERE attempt_id=?',(attempt,)).fetchone()[0])
            before=conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0]
        assert original['closure']['execution_closed'] and original['closure']['grant_ids']
        current=(await owner.get(f"/api/projects/101/runs/{run['run_id']}/code-result")).json()
        assert not current['candidate_current'] and not current['eligible']
        restored=await owner.post(base+'/restore',json={'operation_key':'owned-restore','archive_sha256':record['archive_sha256']})
        assert restored.status_code==202,restored.text
        await runtime.retention.wait(attempt)
        result=(await owner.get('/api/projects/101/retained-work/operations/owned-restore')).json()
        assert result['state']=='completed',result
        recovered=Path(result['receipt']['restored_path'])/'repository'
        assert (recovered/'fact.txt').read_text()=='200'
        assert (c.s.workspace/'fact.txt').read_text()=='137'
        with runtime.store._transaction() as conn:assert conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0]==before


@pytest.mark.timeout(90)
async def test_journal_rejects_live_domain_even_when_database_labels_claim_terminal(development_config):
    """Actual still-owned kernel authority defeats fabricated terminal SQL labels; the fixture restores those labels before normal teardown."""
    from backend.runtime.retention_authority import observed_closure
    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_development_session import development_attempt
    from backend.runtime.workspace_retention import WorkspaceRetention
    c=development_config
    async with development_attempt(c) as d:
        async with d.coordinator.runtime.open(workspace=c.s.workspace,tool_token=d.token,peer_owner=d.peers,limits=d.coordinator.limits):
            store=d.coordinator.store
            retention=WorkspaceRetention(store,c.s.control,c.s.root,closed=lambda conn,row:observed_closure(d.coordinator.runtime.authority,store,conn,row))
            with store._transaction(write=True) as conn:conn.execute("UPDATE runtime_runs SET status='needs_review' WHERE id=?",(d.run.run_id,))
            try:
                with pytest.raises(RunConflict,match='cierre físico'):
                    retention.quarantine(101,d.lease.attempt_id,'false-terminal',retention_days=1,acknowledge_unavailability=True)
                assert retention.operations(101)==[]
            finally:
                with store._transaction(write=True) as conn:conn.execute("UPDATE runtime_runs SET status='running' WHERE id=?",(d.run.run_id,))

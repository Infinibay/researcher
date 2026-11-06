"""Historical owner source controls must bind the selected identity and observed fence before any reconciliation is scheduled."""

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config


async def test_history_observation_rejects_replaced_or_stale_scope_before_scheduling(owned_config):
    """An owner opening recorded history cannot reconcile another operation or fence after a stale response, and exact completed observation starts no actor."""
    from backend.tests.runtime.test_source_repair import app_for_sources
    from backend.tests.runtime.test_workspace_delivery import owner_client
    from backend.tests.runtime.test_owned_source_setup import git

    c=owned_config;app,runtime=app_for_sources();target=c.s.root/'history';base='/api/projects/202/source-operations'
    body={'operation_key':'history-original','mode':'create','name':'history','path':str(target),'branch':'main'}
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base,json=body)).status_code==202
        await runtime.sources.wait(202,body['operation_key'])
        value=(await owner.get(base+'/history-original')).json();assert value['status']=='completed'
        head=git(target,'rev-parse','HEAD');workers=dict(runtime.sources._workers)
        for scope in [{'operation_id':'b'*32,'fence':value['fence']},{'operation_id':value['operation_id'],'fence':value['fence']-1}]:
            result=await owner.post(base+'/history-original/observe',json=scope)
            assert result.status_code==409,result.text
            assert runtime.sources._workers==workers
        good={'operation_id':value['operation_id'],'fence':value['fence']}
        assert (await owner.post(base+'/history-original/observe',json={**good,'command':'git reset --hard'})).status_code==422
        result=await owner.post(base+'/history-original/observe',json=good)
        assert result.status_code==202 and result.json()==value
        assert runtime.sources._workers==workers and git(target,'rev-parse','HEAD')==head
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0

"""Local work must share durable capacity across owner/agent calls without replaying uncertain calculations."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.runtime.auxiliary_budget import AuxiliaryBudget, AuxiliaryBudgetExceeded, AuxiliaryWorkUncertain


def calculation(budget, text=b'one', execute=None):
    """Use the real ledger with deterministic worker output and explicit CPU ceiling."""
    return budget.execute(text, kind='semantic', fingerprint='a'*64, cpu_ceiling_ms=3000,
                          execute=execute or (lambda: json.dumps({'ok':True,'execution':{'cpu_used_seconds':0.025}}).encode()))


def test_original_result_survives_reply_loss_and_another_actor_without_new_work(coordination):
    """Same project/input/version returns the exact saved bytes; another project must perform its own calculation."""
    c=coordination;budget=AuxiliaryBudget(c.database,101)
    original=calculation(budget)
    def forbidden():
        """A repeated completed read must never enter the worker again."""
        pytest.fail('repeated worker')
    assert calculation(AuxiliaryBudget(c.database,101),execute=forbidden)==original
    state=budget.summary();assert state['used_operations']==1 and state['accounted_cpu_ms']==25
    assert state['observed_cpu_ms']==25 and state['unknown_operations']==0
    assert AuxiliaryBudget(c.database,202).summary()['used_operations']==0


def test_uncertain_failure_keeps_full_hold_after_restart_and_never_replays(coordination):
    """A lost worker result cannot look like zero use or authorize automatic retry of the same intent."""
    c=coordination;budget=AuxiliaryBudget(c.database,101)
    def fail():
        """Represent a transport failure after the durable reservation."""
        raise OSError('lost result')
    with pytest.raises(OSError):calculation(budget,execute=fail)
    again=AuxiliaryBudget(c.database,101)
    with pytest.raises(AuxiliaryWorkUncertain):calculation(again)
    state=again.summary();assert state['used_operations']==1 and state['accounted_cpu_ms']==3000
    assert state['observed_cpu_ms'] is None and state['unknown_operations']==1


def test_competing_calls_cannot_both_take_last_project_slot(coordination):
    """Independent database connections share one admission decision before either worker executes."""
    c=coordination
    c.conn.execute('INSERT INTO runtime_auxiliary_policies VALUES(101,1,10000)');c.conn.commit()
    gate=Barrier(2)
    def compete(index):
        """Start both independent callers at the same boundary."""
        gate.wait(timeout=5)
        try:return calculation(AuxiliaryBudget(c.database,101),str(index).encode())
        except AuxiliaryBudgetExceeded:return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(compete,[1,2]))
    assert values.count('blocked')==1
    assert AuxiliaryBudget(c.database,101).summary()['used_operations']==1


def test_worker_cpu_without_measurement_stays_unknown_even_with_result(coordination):
    """A result can be reusable while its physical consumption remains unmeasured."""
    budget=AuxiliaryBudget(coordination.database,101)
    raw=calculation(budget,execute=lambda:b'{"ok":false,"code":"too_large"}')
    assert calculation(budget)==raw
    assert budget.summary()['accounted_cpu_ms']==3000
    assert budget.summary()['observed_cpu_ms'] is None


def test_owner_policy_revision_keeps_unknown_hold_and_old_decisions_compatible(coordination):
    """Local limits share owner decision identity; a lower limit cannot erase usage or launch work."""
    from backend.runtime.project_budget import ProjectBudgetPolicies
    from backend.runtime.history import RuntimeHistory

    c=coordination;budget=AuxiliaryBudget(c.database,101)
    calculation(budget,execute=lambda:b'{"ok":false}')
    policies=ProjectBudgetPolicies(c.store)
    body=dict(operation_key='local-policy',expected_revision=0,turn_limit=2,token_limit=200,
              auxiliary_operation_limit=1,auxiliary_cpu_ms_limit=100)
    receipt=policies.update(101,**body)
    assert policies.update(101,**body)==receipt
    state=RuntimeHistory(c.database).budget(101)['auxiliary']
    assert state['accounted_cpu_ms']==3000 and state['remaining_cpu_ms']==0
    with pytest.raises(AuxiliaryBudgetExceeded):calculation(budget,b'new')
    policies.update(101,operation_key='old-client',expected_revision=1,turn_limit=3,token_limit=300)
    assert budget.summary()['policy']=={'operation_limit':1,'cpu_ms_limit':100}
    assert policies.receipt(101,'local-policy')==receipt
    assert c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==0


def test_writer_process_death_retains_original_reservation_without_replay(coordination):
    """A child dies after admission commits; a new host sees the full unknown hold and cannot recalculate."""
    import subprocess
    import sys

    c=coordination
    code="""import os,sys
from backend.runtime.auxiliary_budget import AuxiliaryBudget
AuxiliaryBudget(sys.argv[1],101).execute(b'one',kind='semantic',fingerprint='a'*64,cpu_ceiling_ms=3000,execute=lambda:os._exit(73))
"""
    assert subprocess.run([sys.executable,'-c',code,str(c.database)],check=False,timeout=10).returncode==73
    budget=AuxiliaryBudget(c.database,101)
    with pytest.raises(AuxiliaryWorkUncertain):calculation(budget)
    assert budget.summary()['pending_operations']==1
    assert budget.summary()['accounted_cpu_ms']==3000


def test_attempt_cannot_evade_its_local_allowance_or_read_after_revocation(coordination):
    """A real native grant binds each record to its attempt; project capacity cannot override the attempt cap or revoked authority."""
    from backend.tests.runtime.test_inference_journal import reservation
    from backend.research.models import ResearchForbidden

    c=coordination;_,lease=reservation(c)
    token=c.research.issue_grant(project_id=101,task_id=1001,agent_id='researcher-a',permissions={'sources.read'})
    scope=c.research.authorize(token);c.store.bind_grant(lease,scope.grant_id)
    budget=AuxiliaryBudget(c.database,101,research=c.research,scope=scope)
    for index in range(50):calculation(budget,str(index).encode())
    with pytest.raises(AuxiliaryBudgetExceeded,match='intento'):calculation(budget,b'extra')
    assert c.conn.execute('SELECT count(*) FROM runtime_auxiliary_work WHERE attempt_id=?',(lease.attempt_id,)).fetchone()[0]==50
    c.research.revoke_grant(scope.grant_id)
    with pytest.raises(ResearchForbidden):calculation(budget,b'0')


def test_unused_auxiliary_inverse_preserves_old_schema_and_refuses_work(coordination):
    """Only unused latest schema can reverse; source data and recorded work remain authoritative."""
    from backend.db.auxiliary_budget_migration import restore_auxiliary_budget_schema
    from backend.db.auxiliary_continuation_migration import restore_auxiliary_continuation_schema
    from backend.db.auxiliary_origin_migration import restore_auxiliary_origin_schema
    from backend.tools.base.db import ensure_migrations

    c=coordination
    restore_auxiliary_origin_schema(c.conn)
    restore_auxiliary_continuation_schema(c.conn)
    restore_auxiliary_budget_schema(c.conn)
    assert c.conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==60
    ensure_migrations(c.database)
    calculation(AuxiliaryBudget(c.database,101))
    with pytest.raises(RuntimeError,match='newer schema'):restore_auxiliary_budget_schema(c.conn)
    restore_auxiliary_origin_schema(c.conn)
    with pytest.raises(RuntimeError,match='recorded'):restore_auxiliary_continuation_schema(c.conn)

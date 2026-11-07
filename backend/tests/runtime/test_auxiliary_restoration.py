"""Verified restoration archives local work without transferring pending calculation permission or inventing original closure."""

import json
import sqlite3

import pytest

from backend.runtime.auxiliary_budget import AuxiliaryBudget, AuxiliaryWorkUncertain
from backend.runtime.auxiliary_recovery import AuxiliaryRecovery
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.tests.runtime.test_auxiliary_budget import calculation
from backend.tests.runtime.test_auxiliary_continuation import failed, decide
from backend.tests.runtime.test_host_installation import host_assets as host_assets
from backend.tests.runtime.test_installation_backup import installation as installation


def copy_installation(original, tmp_path, name):
    """Use the actual offline backup and verified separate-path restore, without enabling its copied authority."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation

    bundle=tmp_path/(name+'-backup');destination=tmp_path/name
    backup_installation(original,bundle)
    receipt=restore_installation(bundle,destination)
    return destination,receipt


def test_copied_pending_permission_cannot_start_work_and_needs_fresh_owner_decision(installation,tmp_path,host_assets):
    """Real backup/restore/enrollment preserves old uncertainty and receipts but cannot consume a permission from the original database."""
    from backend.runtime.restored_enrollment import enroll_restored_host

    original,_=installation;database=original/'source.db';budget=AuxiliaryBudget(database,101);failed(budget)
    recovery=AuxiliaryRecovery(SQLiteRunStore(database));operation=recovery.list(101)['items'][0]['operation_id']
    first=decide(recovery,operation)
    destination,restoration=copy_installation(original,tmp_path,'restored')
    target=AuxiliaryBudget(destination/'source.db',101)
    with pytest.raises(AuxiliaryWorkUncertain):calculation(target)
    result=enroll_restored_host(destination,witness_dir=tmp_path/'fresh-witness',assets=host_assets)
    assert result['original_host_closure_proven'] is False
    assert result['historical_work']['local_calculations']==1
    restored=AuxiliaryRecovery(SQLiteRunStore(destination/'source.db'))
    row=restored.list(101)['items'][0]
    assert row['diagnosis']['code']=='restored_history' and row['diagnosis']['can_continue']
    receipt=restored.receipt(101,'continue-1')
    assert receipt['authorization_scope']=='historical_installation'
    assert receipt['successor_operation_id']==first['successor_operation_id']
    with pytest.raises(AuxiliaryWorkUncertain):calculation(target)
    fresh=decide(restored,operation,'fresh-decision')
    assert fresh['authorization_scope']=='current_installation'
    assert fresh['successor_operation_id']!=first['successor_operation_id']
    assert target.summary()['used_operations']==1
    calculation(target)
    assert target.summary()['used_operations']==2 and target.summary()['accounted_cpu_ms']==3025
    assert budget.summary()['used_operations']==1
    assert recovery.receipt(101,'continue-1')['authorization_scope']=='current_installation'
    assert restored.receipt(101,'continue-1')==receipt


@pytest.mark.parametrize('uncertainty',['missing_identity','foreign_kernel','creation_gap'])
def test_restored_history_is_eligible_without_false_original_closure(installation,tmp_path,host_assets,uncertainty):
    """Old missing/foreign/incomplete identities remain original evidence while a verified copy gets fresh explicit calculation authority."""
    from backend.runtime.restored_enrollment import enroll_restored_host

    original,_=installation;database=original/'source.db';failed(AuxiliaryBudget(database,101))
    with sqlite3.connect(database) as conn:
        if uncertainty=='missing_identity':conn.execute('DELETE FROM runtime_auxiliary_executions')
        else:
            owner=json.loads(conn.execute('SELECT owner_json FROM runtime_auxiliary_executions').fetchone()[0])
            if uncertainty=='foreign_kernel':owner['boot_id']='00000000-0000-0000-0000-000000000001'
            conn.execute("UPDATE runtime_auxiliary_executions SET phase='spawning',owner_json=?,closed_at=NULL",(json.dumps(owner),))
    original_row=AuxiliaryRecovery(SQLiteRunStore(database)).list(101)['items'][0]
    assert not original_row['diagnosis']['can_continue']
    destination,receipt=copy_installation(original,tmp_path,'restored')
    enrolled=enroll_restored_host(destination,witness_dir=tmp_path/'fresh-witness',assets=host_assets)
    assert enrolled['original_host_closure_proven'] is False
    restored=AuxiliaryRecovery(SQLiteRunStore(destination/'source.db'));row=restored.list(101)['items'][0]
    assert row['status']=='unknown' and row['diagnosis']['code']=='restored_history'
    assert row['diagnosis']['can_continue']
    decide(restored,row['operation_id'])
    target=AuxiliaryBudget(destination/'source.db',101);calculation(target)
    assert target.summary()['held_cpu_ms']==3000 and target.summary()['used_operations']==2
    assert AuxiliaryRecovery(SQLiteRunStore(database)).list(101)['items'][0]==original_row


def test_failed_enrollment_rolls_back_local_archival_and_never_enables_host(installation,tmp_path,host_assets,monkeypatch):
    """An error after writing archival rows cannot commit only part of historical withdrawal or activate the restored host."""
    from backend.runtime import auxiliary_origin
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.host_installation import host_environment

    original,_=installation;failed(AuxiliaryBudget(original/'source.db',101))
    destination,_=copy_installation(original,tmp_path,'restored');archive=auxiliary_origin.archive_local_work
    def interrupted(*args):
        """Fail within the actual enrollment transaction after its local history write."""
        assert archive(*args)==1
        raise OSError('controlled enrollment interruption')
    monkeypatch.setattr(auxiliary_origin,'archive_local_work',interrupted)
    with pytest.raises(OSError,match='controlled'):enroll_restored_host(destination,witness_dir=tmp_path/'fresh-witness',assets=host_assets)
    with sqlite3.connect(destination/'source.db') as conn:
        assert conn.execute('SELECT count(*) FROM runtime_auxiliary_archives').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM runtime_auxiliary_work').fetchone()[0]==1
    with pytest.raises(ValueError):host_environment(destination)


def test_restoring_again_requires_another_current_decision_and_keeps_saved_results(installation,tmp_path,host_assets):
    """Neither a second copied permission nor copied archival metadata becomes current merely because the content is identical."""
    from backend.runtime.restored_enrollment import enroll_restored_host

    original,_=installation;budget=AuxiliaryBudget(original/'source.db',101);failed(budget)
    complete=calculation(budget,b'complete')
    one,_=copy_installation(original,tmp_path,'restore-one')
    enroll_restored_host(one,witness_dir=tmp_path/'witness-one',assets=host_assets)
    first=AuxiliaryRecovery(SQLiteRunStore(one/'source.db'))
    unknown=next(row for row in first.list(101)['items'] if row['status']=='unknown')
    decide(first,unknown['operation_id'],'first-copy-permission')
    two,second_restoration=copy_installation(one,tmp_path,'restore-two')
    assert not (two/'enrollment.json').exists()
    assert (two/second_restoration['evidence_directory']/'original/enrollment.json').read_bytes()==(one/'enrollment.json').read_bytes()
    enroll_restored_host(two,witness_dir=tmp_path/'witness-two',assets=host_assets)
    second=AuxiliaryRecovery(SQLiteRunStore(two/'source.db'));target=AuxiliaryBudget(two/'source.db',101)
    assert second.receipt(101,'first-copy-permission')['authorization_scope']=='historical_installation'
    with pytest.raises(AuxiliaryWorkUncertain):calculation(target)
    assert calculation(target,b'complete')==complete and target.summary()['used_operations']==2
    decide(second,unknown['operation_id'],'second-copy-permission');calculation(target)
    assert target.summary()['used_operations']==3 and target.summary()['accounted_cpu_ms']==3050
    assert AuxiliaryBudget(one/'source.db',101).summary()['used_operations']==2


@pytest.mark.parametrize('schema_target',[62])
def test_migration_preserves_legacy_receipt_without_inventing_permission_origin(coordination):
    """An old unconsumed permission has no verified database binding; preserve it and require a fresh explicit decision."""
    import hashlib
    import os
    from backend.runtime.auxiliary_execution import process_identity
    from backend.tools.base.db import ensure_migrations

    c=coordination;root=hashlib.sha256(json.dumps(['semantic','a'*64,hashlib.sha256(b'one').hexdigest(),3000]).encode()).hexdigest()
    old={'operation_key':'legacy-permission','source_operation_id':root,'reason':''}
    receipt={**old,'project_id':101,'successor_operation_id':'d'*64,'generation':1,'work_started':False}
    c.conn.execute("INSERT INTO runtime_auxiliary_work(project_id,operation_id,kind,fingerprint,input_sha256,input_bytes,cpu_ceiling_ms,status,created_at) VALUES(101,?,'semantic',?,?,3,3000,'unknown',1000)",(root,'a'*64,hashlib.sha256(b'one').hexdigest()))
    c.conn.execute("INSERT INTO runtime_auxiliary_executions VALUES(101,?,?,'closed',NULL,1001)",(root,json.dumps(process_identity(os.getpid()))))
    original_json=json.dumps(receipt)
    c.conn.execute('INSERT INTO runtime_auxiliary_continuations VALUES(?,?,?,?,?,?,?,?,?)',(101,'legacy-permission',root,'d'*64,root,1,json.dumps(old,sort_keys=True),original_json,1001));c.conn.commit()
    ensure_migrations(c.database)
    recovery=AuxiliaryRecovery(c.store);budget=AuxiliaryBudget(c.database,101)
    assert recovery.receipt(101,'legacy-permission')['authorization_scope']=='historical_installation'
    assert c.conn.execute('SELECT receipt_json FROM runtime_auxiliary_continuations').fetchone()[0]==original_json
    with pytest.raises(AuxiliaryWorkUncertain):calculation(budget)
    fresh=decide(recovery,root,'confirmed-after-upgrade')
    assert fresh['generation']==2 and fresh['authorization_scope']=='current_installation'
    calculation(budget);assert budget.summary()['accounted_cpu_ms']==3025


def test_origin_inverse_requires_unused_permission_and_archival(coordination):
    """The unused latest schema reverses without deleting work; recorded permissions prevent loss of their physical origin."""
    from backend.db.auxiliary_origin_migration import restore_auxiliary_origin_schema
    from backend.tools.base.db import ensure_migrations

    c=coordination;restore_auxiliary_origin_schema(c.conn)
    assert c.conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==62
    ensure_migrations(c.database);failed(AuxiliaryBudget(c.database,101))
    recovery=AuxiliaryRecovery(c.store);decide(recovery,recovery.list(101)['items'][0]['operation_id'])
    with pytest.raises(RuntimeError,match='recorded'):restore_auxiliary_origin_schema(c.conn)

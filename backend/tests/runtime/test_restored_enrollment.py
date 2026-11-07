"""Exercise fresh authority over copied data without replaying historical native work."""

import json
import os
import sqlite3
from contextlib import closing

import pytest

from backend.tests.runtime.test_host_installation import host_assets
from backend.tests.runtime.test_installation_backup import installation


@pytest.fixture
def restored(installation, tmp_path):
    """Copy synthetic pending and accepted history through the real backup/restore path."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation

    original, authority = installation
    with sqlite3.connect(original / 'source.db') as db:
        for index, status in enumerate(('queued', 'running', 'waiting_input', 'needs_review', 'accepted'), 1):
            task = 2000 + index
            db.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(?,101,'research',?)", (task,status))
            db.execute("INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,fence,created_at,updated_at) VALUES(?,101,?,'fixture',1,?,'original prompt','codex',?,0,1,1)", (status,task,status,status))
        db.execute("INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES('old-attempt','running','old-host',1,'running',999,1)")
        db.execute("UPDATE runtime_runs SET current_attempt_id='old-attempt',fence=1 WHERE id='running'")
        db.execute("INSERT INTO user_requests(project_id,agent_id,request_type,title) VALUES(101,'old','question','Original unanswered question')")
    bundle = tmp_path / 'backup'
    backup_installation(original,bundle)
    destination = tmp_path / 'restored'
    receipt = restore_installation(bundle,destination)
    return destination, original, authority, receipt


def test_enrollment_preserves_history_and_starts_only_fresh_authority(restored, tmp_path, host_assets):
    """A new host keeps results and uncertainty but cannot dispatch copied active work."""
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.host_installation import host_environment, inspect_host
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.contracts import RunSpec

    root, original, old_authority, restoration = restored
    result = enroll_restored_host(root, witness_dir=tmp_path/'new-witness', assets=host_assets)
    assert result['status'] == 'prepared'
    assert result['authority_id'] != old_authority['authority_id']
    assert result['old_work_replayed'] is False
    assert len(result['historical_work']['runs']) == 4
    assert host_environment(root)['INFINIBAY_DB'] == str(root/'source.db')
    assert inspect_host(root,probe=True)['kernel_probe']['domain_removed']
    config = json.loads((root/'runtime.json').read_text())
    with WitnessedAuthorityJournal(**config['authority']) as journal:
        assert journal.load().sequence == 0
    with sqlite3.connect(root/'source.db') as db:
        assert db.execute("SELECT status FROM runtime_runs WHERE id='accepted'").fetchone() == ('accepted',)
        assert db.execute("SELECT COUNT(*) FROM runtime_runs WHERE status='superseded'").fetchone() == (4,)
        assert db.execute('SELECT status,ended_at,native_result_json FROM runtime_attempts').fetchone() == ('reconciling',None,None)
        assert db.execute('SELECT status,response FROM user_requests').fetchone() == ('expired',None)
        assert db.execute("SELECT count(*) FROM events_log WHERE event_type='run.restored_history'").fetchone() == (4,)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    store = SQLiteRunStore(root/'source.db')
    assert store.recover_owners('new-owner') == 0
    fresh = store.admit(RunSpec(101,2002,'new-owner',1,'explicit-new-request','new intent','codex'))
    assert fresh.status == 'queued'
    assert fresh.run_id != 'running'
    with sqlite3.connect(original/'source.db') as db:
        assert db.execute("SELECT status FROM runtime_runs WHERE id='running'").fetchone() == ('running',)
    assert (root/restoration['evidence_directory']/'original/authority/authority.db').exists()
    assert not (root/'auth/old-pairing').exists()
    with pytest.raises(ValueError,match='pending'):
        enroll_restored_host(root,witness_dir=tmp_path/'unused-witness',assets=host_assets)
    assert not (tmp_path/'unused-witness').exists()


@pytest.mark.parametrize('obstacle', ['owner', 'writer', 'overlap', 'existing_witness', 'bad_assets'])
def test_enrollment_refusal_never_enables_pending_host(restored,tmp_path,host_assets,obstacle):
    """Busy ownership, invalid assets and unsafe witnesses fail before new authority or history changes."""
    import fcntl
    from contextlib import ExitStack
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.host_installation import host_environment

    root,_,_,_ = restored
    witness = tmp_path/'new-witness'
    with ExitStack() as stack:
        if obstacle == 'owner':
            fd = os.open(str(root/'source.db')+'.runtime-owner',os.O_RDWR|os.O_CREAT,0o600)
            stack.callback(os.close,fd)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        elif obstacle == 'writer':
            db = stack.enter_context(closing(sqlite3.connect(root/'source.db')))
            db.execute('BEGIN IMMEDIATE')
        elif obstacle == 'overlap': witness = root/'nested-witness'
        elif obstacle == 'existing_witness': witness.mkdir()
        else: host_assets['model'] = ''
        with pytest.raises((OSError,ValueError,RuntimeError,sqlite3.DatabaseError)):
            enroll_restored_host(root,witness_dir=witness,assets=host_assets)
    with pytest.raises(ValueError,match='incomplete'):
        host_environment(root)
    assert not (root/'authority').exists()
    with sqlite3.connect(root/'source.db') as db:
        assert db.execute("SELECT status FROM runtime_runs WHERE id='running'").fetchone() == ('running',)


def test_interruption_retains_partial_authority_with_startup_barrier(restored,tmp_path,host_assets,monkeypatch):
    """A failed final marker preserves evidence; recovery uses the original backup at another NEW path."""
    from backend.runtime import restored_enrollment as module
    from backend.runtime.host_installation import host_environment

    root,_,_,_ = restored
    replace = module.os.replace
    def fail_final(source,target):
        """Interrupt only the final activation after durable history and configuration writes."""
        if str(target).endswith('/installation.json'):raise OSError('injected final-marker failure')
        return replace(source,target)
    monkeypatch.setattr(module.os,'replace',fail_final)
    with pytest.raises(OSError,match='injected'):
        module.enroll_restored_host(root,witness_dir=tmp_path/'new-witness',assets=host_assets)
    with pytest.raises(ValueError,match='incomplete'):
        host_environment(root)
    assert (root/'authority/authority.db').exists()
    with pytest.raises(FileExistsError):
        module.enroll_restored_host(root,witness_dir=tmp_path/'different-witness',assets=host_assets)
    assert not (tmp_path/'different-witness').exists()


def test_copied_active_plan_is_paused_without_rewriting_its_causal_handoff(service_setup):
    """Apply restoration retirement to an accepted graph with a real durable unissued delivery."""
    from backend.tests.runtime.test_plan_execution import accepted_plan, authorize
    from backend.runtime.restored_enrollment import _retain_as_history
    from backend.planning.execution import PlanExecutions

    s,run,graph = accepted_plan(service_setup,research_only=True)
    executions,receipt = authorize(s,run)
    prepared = executions.prepare(receipt['execution_id'],graph['tasks']['learn'])
    delivery = s.c.store.admit(prepared[0],binding=prepared[1])
    before = [tuple(row) for row in s.c.conn.execute('SELECT packet_json,packet_sha256 FROM runtime_plan_handoffs')]
    assert PlanExecutions(s.c.store).pending()
    with s.c.store._transaction(write=True) as db:
        history = _retain_as_history(db,s.c.store.database,'synthetic-restore-snapshot')
    assert history['paused_plans'] == [{'id':receipt['execution_id'],'project_id':101}]
    assert PlanExecutions(s.c.store).pending() == []
    assert s.c.store.get(101,delivery.run_id).status == 'superseded'
    assert s.c.store.get(101,run.run_id).status == 'accepted'
    assert [tuple(row) for row in s.c.conn.execute('SELECT packet_json,packet_sha256 FROM runtime_plan_handoffs')] == before


def test_restored_host_http_restart_does_not_replay_copied_work(restored,tmp_path,host_assets,monkeypatch):
    """Compose the enrolled native service twice, pair afresh and inspect retained history without inference."""
    from fastapi.testclient import TestClient
    from backend.api.main import create_app
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.api.owner_endpoint import endpoint_identity
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from types import SimpleNamespace

    root, original, _, _ = restored
    prepared = enroll_restored_host(root,witness_dir=tmp_path/'new-witness',assets=host_assets)
    for key,value in prepared['environment'].items():monkeypatch.setenv(key,value)
    monkeypatch.chdir(root/'service')
    original_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime_service=SimpleNamespace(store=SQLiteRunStore(original/'source.db')))))
    original_endpoint = endpoint_identity(original_request)
    observed = []
    for _ in range(2):
        app = create_app()
        with TestClient(app,base_url='http://localhost') as client:
            code = app.state.local_access.key_file.read_text().strip()
            paired = client.post('/api/session',json={'code':code},headers={'Origin':'http://localhost','X-Researcher-Client':'web'})
            assert paired.status_code == 200
            session = paired.json()
            observed.append(session['endpoint_id'])
            assert session['endpoint_id'] != original_endpoint
            response = client.get('/api/tasks?project_id=101')
            assert response.status_code == 200
            stale = client.post('/api/projects',json={'name':'must not create'},headers={'Origin':'http://localhost','X-Researcher-CSRF':session['csrf_token'],'X-Researcher-Endpoint':original_endpoint})
            assert stale.status_code == 409
            assert stale.json()['code'] == 'owner_endpoint_changed'
        with sqlite3.connect(root/'source.db') as db:
            assert db.execute('SELECT count(*) FROM runtime_attempts').fetchone() == (1,)
            assert db.execute('SELECT count(*) FROM runtime_runs').fetchone() == (5,)
            assert db.execute('SELECT count(*) FROM runtime_peers').fetchone() == (0,)
    assert observed[0] == observed[1]


def test_public_enrollment_command_uses_explicit_new_assets_and_witness(restored,tmp_path,host_assets):
    """The installed administration entry point enables a restore without inference or implicit asset discovery."""
    from backend.tests.cli.test_bootstrap import cli

    root,_,_,_ = restored
    assets = tmp_path/'assets.json'
    assets.write_text(json.dumps(host_assets))
    result = cli('enroll-restored-host','--directory',root,'--witness-dir',tmp_path/'new-witness','--assets',assets)
    assert result.returncode == 0,result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['status'] == 'prepared'
    assert receipt['model_turns'] == 0
    assert receipt['old_work_replayed'] is False


def test_abrupt_enrollment_exit_leaves_original_backup_as_recovery_source(restored,tmp_path,host_assets):
    """An owned child exits after history/config commits; startup stays blocked and another fresh restore works."""
    import subprocess
    import sys
    from backend.runtime.host_installation import host_environment
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host

    root,_,_,_ = restored
    program = '''import json,os,sys
from backend.runtime import restored_enrollment as module
replace = module.os.replace
def interrupt(source,target):
    if str(target).endswith('/installation.json'):os._exit(93)
    return replace(source,target)
module.os.replace = interrupt
module.enroll_restored_host(sys.argv[1],witness_dir=sys.argv[2],assets=json.loads(sys.argv[3]))
'''
    child = subprocess.run([sys.executable,'-c',program,str(root),str(tmp_path/'interrupted-witness'),json.dumps(host_assets)],capture_output=True,text=True,timeout=20)
    assert child.returncode == 93,child.stderr
    with pytest.raises(ValueError,match='incomplete'):host_environment(root)
    assert (root/'enrollment.json').exists()
    recovery = tmp_path/'fresh-recovery'
    restore_installation(tmp_path/'backup',recovery)
    assert enroll_restored_host(recovery,witness_dir=tmp_path/'recovery-witness',assets=host_assets)['status'] == 'prepared'
    assert (root/'installation.enrolled.json').exists()

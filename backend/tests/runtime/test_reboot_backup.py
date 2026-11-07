"""Exercise explicit old-kernel evidence capture without weakening normal authority enrollment."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.db.migration_catalog import LATEST_VERSION
from backend.tests.runtime.test_installation_backup import installation
from backend.tests.runtime.test_host_installation import host_assets


@pytest.fixture
def historical_installation(request, monkeypatch):
    """Create the requested real forward schema prefix, then restore the current migrator before exercising backup and enrollment."""
    from backend.tools.base import db

    migrate = db.ensure_migrations

    def initialize_prefix(db_path=None, **options):
        """Restrict only fixture initialization to its explicitly requested historical schema."""
        return migrate(db_path, target_version=request.param, **options)

    with monkeypatch.context() as patch:
        patch.setattr(db, 'ensure_migrations', initialize_prefix)
        root, authority = request.getfixturevalue('installation')
    with sqlite3.connect(root / 'source.db') as connection:
        assert connection.execute('SELECT MAX(version) FROM schema_migrations').fetchone() == (request.param,)
    return root, authority, request.param


@pytest.fixture
def changed_kernel(monkeypatch):
    """Model only the observation boundary; separate VM evidence must prove an actual kernel restart."""
    from backend.runtime import reboot_authority

    current = str(uuid4())
    monkeypatch.setattr(reboot_authority,'boot_id',lambda:current)
    return current


def test_reboot_archive_requires_a_different_kernel_and_retains_normal_guard(installation,monkeypatch):
    """Changing only the observer cannot bypass live enrollment, even for explicit archival."""
    from backend.runtime.reboot_authority import frozen_reboot_evidence
    from backend.runtime.authority_journal import AuthorityUncertain, WitnessedAuthorityJournal
    from backend.runtime import authority_journal

    _,authority = installation
    with pytest.raises(AuthorityUncertain,match='different kernel'):
        with frozen_reboot_evidence(authority):pass
    monkeypatch.setattr(authority_journal,'boot_id',lambda:str(uuid4()))
    with WitnessedAuthorityJournal(**authority) as normal:
        with pytest.raises(AuthorityUncertain,match='kernel'):
            normal.load()


@pytest.mark.parametrize('historical_installation',[56,57,LATEST_VERSION],indirect=True)
def test_reboot_backup_restores_live_old_peer_as_history(historical_installation,changed_kernel,tmp_path,host_assets):
    """Historical and current source schemas retain old-peer uncertainty while the restored copy upgrades to the current schema."""
    from backend.runtime.peer_process import boot_id, observer_namespace
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.installation_backup import backup_installation, verify_backup
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.db.peer_archive_migration import restore_peer_archive_schema

    root,authority,source_version = historical_installation
    with WitnessedAuthorityJournal(**authority) as journal:
        journal.commit(journal.load(),transition_id='before-reboot',puts={'broker:active':'old-broker'})
    with sqlite3.connect(root/'source.db') as db:
        db.execute("INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,fence,current_attempt_id,created_at,updated_at) VALUES('old-run',101,1001,'old',1,'old-intent','Original request','codex','running',1,'old-attempt',1,1)")
        db.execute("INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES('old-attempt','old-run','old-host',1,'running',10,1)")
        db.execute("INSERT INTO runtime_peers(id,attempt_id,kind,protocol_version,state,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at,database_identity) VALUES('old-peer','old-attempt','native',1,'prepared',1,999999,1,?,?,1,'original-db')",(boot_id(),observer_namespace()))
    old_bytes = {key:Path(authority[key]).read_bytes() for key in ('database','witness','mutex')}
    with pytest.raises(ValueError,match='native authority'):
        backup_installation(root,tmp_path/'normal-refusal')
    backup_installation(root,tmp_path/'backup',after_reboot=True)
    manifest = verify_backup(tmp_path/'backup')
    assert manifest['reboot_evidence']['observed_boot_id'] == changed_kernel
    assert manifest['reboot_evidence']['source_boot_id'] == boot_id()
    assert all(Path(authority[key]).read_bytes()==raw for key,raw in old_bytes.items())
    restored = tmp_path/'restored'
    restore_installation(tmp_path/'backup',restored)
    result = enroll_restored_host(restored,witness_dir=tmp_path/'fresh-witness',assets=host_assets)
    assert (result['schema_before'],result['schema_version']) == (source_version,LATEST_VERSION)
    assert result['historical_work']['prior_kernel_peers'] == ['old-peer']
    with sqlite3.connect(restored/'source.db') as db:
        assert db.execute('SELECT state,reason,boot_id,database_identity FROM runtime_peers').fetchone() == ('prepared',None,boot_id(),'original-db')
        assert db.execute('SELECT peer_id,original_state,origin_boot_id FROM runtime_peer_archives').fetchone() == ('old-peer','prepared',boot_id())
        assert db.execute('SELECT status,native_result_json,ended_at FROM runtime_attempts').fetchone() == ('reconciling',None,None)
        assert db.execute('SELECT status FROM runtime_runs').fetchone() == ('superseded',)
        with pytest.raises(RuntimeError,match='newer schema'):
            restore_peer_archive_schema(db)
        assert db.execute('SELECT COUNT(*) FROM runtime_peer_archives').fetchone() == (1,)
    with sqlite3.connect(root/'source.db') as db:
        assert db.execute('SELECT state FROM runtime_peers').fetchone() == ('prepared',)
    backup_installation(restored,tmp_path/'next-backup')


@pytest.mark.parametrize('historical_installation',[57],indirect=True)
def test_used_historical_archive_inverse_preserves_original_evidence(historical_installation):
    """A real version57 archive refuses its otherwise eligible inverse and preserves every original peer and archive value."""
    from backend.db.peer_archive_migration import restore_peer_archive_schema
    from backend.runtime.peer_process import boot_id, observer_namespace
    from backend.tests.runtime.migration_fixtures import historical_run

    root,_,_ = historical_installation
    with sqlite3.connect(root/'source.db') as db:
        historical_run(db,'historical-peer',status='superseded')
        db.execute("INSERT INTO runtime_peers(id,attempt_id,kind,protocol_version,state,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at,database_identity) VALUES('old-peer','historical-peer-attempt','native',1,'prepared',1,999999,1,?,?,1,'original-db')",(boot_id(),observer_namespace()))
        db.execute("INSERT INTO runtime_peer_archives VALUES('old-peer',?,'prepared',?,?,'original-db',1)",(uuid4().hex,boot_id(),observer_namespace()))
        db.commit()
        before = [db.execute('SELECT * FROM '+table).fetchall() for table in ('runtime_peers','runtime_peer_archives')]
        with pytest.raises(RuntimeError,match='archival history'):
            restore_peer_archive_schema(db)
        assert [db.execute('SELECT * FROM '+table).fetchall() for table in ('runtime_peers','runtime_peer_archives')] == before
        assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone() == (57,)


@pytest.mark.parametrize('historical_installation',[57],indirect=True)
def test_unused_archive_inverse_and_future_refusal_preserve_data(historical_installation):
    """An unused real version57 prefix reverses to56; the fully upgraded installation refuses that historical inverse without losing data."""
    from backend.db.peer_archive_migration import restore_peer_archive_schema
    from backend.tools.base.db import ensure_migrations

    root,_,_ = historical_installation
    with sqlite3.connect(root/'source.db') as db:
        restore_peer_archive_schema(db)
        assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone() == (56,)
        assert db.execute('SELECT title FROM tasks WHERE id=1001').fetchone() == ('Retained task',)
    ensure_migrations(str(root/'source.db'),existing_only=True)
    with sqlite3.connect(root/'source.db') as db:
        with pytest.raises(RuntimeError,match='newer schema'):
            restore_peer_archive_schema(db)
        assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone() == (LATEST_VERSION,)
        assert db.execute('SELECT title FROM tasks WHERE id=1001').fetchone() == ('Retained task',)


@pytest.mark.parametrize('damage',['replaced_inode','different_recorded_boot'])
def test_reboot_cannot_rebind_original_evidence(installation,changed_kernel,tmp_path,damage):
    """Old-kernel capture keeps file identity and manifest/header agreement as mandatory evidence."""
    from backend.runtime.installation_backup import backup_installation, verify_backup
    from backend.runtime.authority_journal import AuthorityUncertain

    root,authority = installation
    if damage == 'replaced_inode':
        original = Path(authority['witness'])
        replacement = original.with_suffix('.replacement')
        replacement.write_bytes(original.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(original)
        with pytest.raises(AuthorityUncertain):
            backup_installation(root,tmp_path/'refused',after_reboot=True)
    else:
        backup_installation(root,tmp_path/'backup',after_reboot=True)
        path = tmp_path/'backup/manifest.json'
        manifest = json.loads(path.read_text())
        manifest['reboot_evidence']['source_boot_id'] = str(uuid4())
        path.write_text(json.dumps(manifest))
        with pytest.raises(ValueError,match='authority header'):
            verify_backup(tmp_path/'backup')


@pytest.mark.parametrize('wrong_identity',['boot','observer'])
def test_prior_kernel_peer_origin_must_match_the_witness(installation,changed_kernel,wrong_identity):
    """A current-kernel or foreign-observer registration cannot become historical by association."""
    from backend.runtime.reboot_authority import prior_kernel_peers, frozen_reboot_evidence

    _,authority = installation
    with frozen_reboot_evidence(authority) as (_,evidence), sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE runtime_peers(id,boot_id,observer_namespace,state,database_identity)')
        boot = changed_kernel if wrong_identity == 'boot' else evidence['source_boot_id']
        observer = evidence['source_observer_namespace'] + (wrong_identity == 'observer')
        db.execute("INSERT INTO runtime_peers VALUES('foreign',?,?,'prepared','old-db')",(boot,observer))
        with pytest.raises(ValueError,match='another kernel or observer'):
            prior_kernel_peers(db,evidence)


@pytest.mark.parametrize('stage',['before_sql','after_sql','torn_tail'])
def test_reboot_archive_preserves_prepared_and_torn_history_without_repair(installation,changed_kernel,stage):
    """Read valid crash boundaries as evidence without applying an old grant or truncating its bytes."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal, _apply, _hash
    from backend.runtime.reboot_authority import frozen_reboot_evidence

    _,authority = installation
    with WitnessedAuthorityJournal(**authority) as journal:
        with journal._operation() as conn:
            state,history = journal._verified(conn)
            pending={'kind':'PREPARE','from_sequence':state.sequence,'from_hash':state.state_hash,'sequence':state.sequence+1,'state_hash':_hash(_apply(state.records,{'old':'intent'},[])),'transition_id':'original-partial','puts':{'old':'intent'},'deletes':[]}
            journal._append_record(pending,history.head)
            if stage == 'after_sql':journal._write_database(conn,pending)
    if stage == 'torn_tail':
        with Path(authority['witness']).open('ab') as stream:stream.write(b'{"partial":')
    before={key:Path(authority[key]).read_bytes() for key in ('database','witness','mutex')}
    with frozen_reboot_evidence(authority) as (snapshot,evidence):
        assert evidence['history'] == ('prepared_after_database' if stage=='after_sql' else 'prepared_before_database')
        assert snapshot.sequence == (1 if stage=='after_sql' else 0)
        assert evidence['torn_tail'] is (stage=='torn_tail')
    assert all(Path(authority[key]).read_bytes()==raw for key,raw in before.items())


def test_changed_kernel_does_not_excuse_corrupt_history(installation,changed_kernel):
    """A reboot never permits a rewound, corrupt or missing independent witness to become trusted."""
    from backend.runtime.reboot_authority import frozen_reboot_evidence
    from backend.runtime.authority_journal import AuthorityUncertain

    _,authority = installation
    with Path(authority['witness']).open('ab') as stream:stream.write(b'{"invalid":"complete-record"}\n')
    with pytest.raises(AuthorityUncertain):
        with frozen_reboot_evidence(authority):pass


def test_reboot_manifest_cannot_claim_the_same_kernel(installation,changed_kernel,tmp_path):
    """Malformed reboot metadata is rejected before any restored destination is created."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation

    root,_ = installation
    backup_installation(root,tmp_path/'backup',after_reboot=True)
    path=tmp_path/'backup/manifest.json';manifest=json.loads(path.read_text())
    manifest['reboot_evidence']['observed_boot_id']=manifest['reboot_evidence']['source_boot_id']
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='kernel'):
        restore_installation(tmp_path/'backup',tmp_path/'refused')
    assert not (tmp_path/'refused').exists()

"""Exercise offline installation copies, relocation and refusal using real SQLite, files and Git."""

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest


def git(directory, *args):
    """Run bounded local Git fixture commands without network, hooks or inherited user configuration."""
    env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0'}
    return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', '-C', str(directory), *args], env=env, capture_output=True, text=True, timeout=10, check=True).stdout.strip()


@pytest.fixture
def installation(tmp_path):
    """Prepare real data/authority formats with no native resources or model admission claimed."""
    from backend.runtime.bootstrap import initialize_database, initialize_authority
    from backend.runtime.host_installation import _write_new

    root = tmp_path / 'original'
    root.mkdir(mode=0o700)
    for name in ('sources', 'control', 'uploads', 'auth', 'logs', 'service'):
        (root / name).mkdir(mode=0o700)
    initialize_database(root / 'source.db')
    authority = initialize_authority(database_dir=root / 'authority', witness_dir=tmp_path / 'independent-witness')
    _write_new(root / 'runtime.json', {'runtime_profile': 'owned-codex-v1', 'workspace_root': str(root / 'sources'), 'control_root': str(root / 'control'), 'authority': authority, 'token_file': str(tmp_path / 'external-token'), 'model': 'fixture-model'})
    _write_new(root / 'installation.json', {'format': 1, 'status': 'prepared'})
    (root / 'auth' / 'old-pairing').write_text('synthetic-access-material')
    (tmp_path / 'external-token').write_text('synthetic-external-not-to-copy')
    repo = root / 'sources' / 'project'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    (repo / 'sample.txt').write_text('retained repository\n')
    git(repo, 'add', 'sample.txt')
    git(repo, 'commit', '-m', 'fixture')
    linked = root / 'sources' / 'linked'
    git(repo, 'worktree', 'add', '--detach', str(linked))
    (linked / 'dirty.txt').write_text('uncommitted work survives\n')
    (repo / 'relative-link').symlink_to('sample.txt')
    upload = root / 'uploads/101/uploads/exact.txt'
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b'original evidence\n')
    with sqlite3.connect(root / 'source.db') as db:
        db.execute("INSERT INTO projects(id,name) VALUES(101,'Retained owner project')")
        db.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Retained task')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'Project',?)", (str(repo),))
        db.execute("INSERT INTO reference_files(id,project_id,file_name,file_path,file_size) VALUES(17,101,'exact.txt',?,18)", (str(upload),))
        db.execute("INSERT INTO agent_worktrees(project_id,repo_id,agent_id,worktree_path) VALUES(101,11,'historical-agent',?)", (str(linked),))
        db.execute("INSERT INTO artifacts(project_id,task_id,type,file_path,content) VALUES(101,1001,'report','report.md','Retained report')")
    return root, authority


def test_backup_restores_original_data_uploads_and_linked_git_at_another_path(installation, tmp_path):
    """Another-path restoration retains bytes/relations and blocks native startup until fresh enrollment."""
    from backend.runtime.installation_backup import backup_installation, verify_backup
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.host_installation import host_environment
    from backend.research.reference_storage import ReferenceStorage
    from types import SimpleNamespace

    root, _ = installation
    backup = tmp_path / 'backup'
    receipt = backup_installation(root, backup)
    assert receipt['status'] == 'complete'
    assert verify_backup(backup)['snapshot_id'] == receipt['snapshot_id']
    destination = tmp_path / 'restored-elsewhere'
    restored = restore_installation(backup, destination)
    assert restored['status'] == 'pending_enrollment'
    with sqlite3.connect(destination / 'source.db') as db:
        assert db.execute('SELECT id,title FROM tasks').fetchall() == [(1001,'Retained task')]
        assert db.execute('SELECT content FROM artifacts').fetchone() == ('Retained report',)
        path = db.execute('SELECT file_path FROM reference_files WHERE id=17').fetchone()[0]
        assert path == str(destination / 'uploads/101/uploads/exact.txt')
        assert ReferenceStorage(destination / 'uploads').snapshot(SimpleNamespace(path=path,project_id=101), max_bytes=1024) == b'original evidence\n'
        assert db.execute('SELECT local_path FROM repositories').fetchone()[0] == str(destination / 'sources/project')
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert git(destination / 'sources/linked', 'rev-parse', 'HEAD') == git(root / 'sources/linked', 'rev-parse', 'HEAD')
    assert git(destination / 'sources/linked', 'rev-parse', '--show-toplevel') == str(destination / 'sources/linked')
    assert (destination / 'sources/linked/dirty.txt').read_text() == 'uncommitted work survives\n'
    assert (destination / 'sources/project/relative-link').readlink() == Path('sample.txt')
    assert not (destination / 'auth/old-pairing').exists()
    assert 'runtime_profile' not in json.loads((destination / 'runtime.json').read_text())
    with pytest.raises(ValueError, match='incomplete|enrollment'):
        host_environment(destination)
    assert (root / 'uploads/101/uploads/exact.txt').read_bytes() == b'original evidence\n'
    assert json.loads((root / 'installation.json').read_text())['status'] == 'prepared'
    assert not any(p.read_bytes() == b'synthetic-external-not-to-copy' for p in (backup / 'objects').iterdir())


@pytest.mark.parametrize('obstacle', ['database_writer', 'authority_writer', 'active_grant'])
def test_backup_refuses_active_writers_or_native_concession(installation, tmp_path, obstacle):
    """A busy source or authority is an explicit refusal, never an inconsistent successful backup."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from contextlib import ExitStack

    root, authority = installation
    with ExitStack() as stack:
        if obstacle == 'database_writer':
            db = sqlite3.connect(root / 'source.db');stack.callback(db.close)
            db.execute('BEGIN IMMEDIATE')
        else:
            journal = stack.enter_context(WitnessedAuthorityJournal(**authority))
            if obstacle == 'authority_writer':stack.enter_context(journal.frozen_snapshot())
            else:journal.commit(journal.load(), transition_id='synthetic-busy', puts={'broker:active': 'not-closed'})
        with pytest.raises((RuntimeError, ValueError, sqlite3.OperationalError)):
            backup_installation(root, tmp_path / 'refused')
    assert not (tmp_path / 'refused/manifest.json').exists()


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'path_escape', 'symlink_parent'])
def test_restore_verifies_before_creating_destination(installation, tmp_path, damage):
    """Tampering, missing objects and manifest path escapes cannot publish a partial usable restore."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation

    root, _ = installation
    bundle = tmp_path / 'backup';backup_installation(root,bundle)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    entry = next(e for e in manifest['entries'] if e['kind']=='file')
    if damage == 'missing':(bundle / entry['object']).unlink()
    elif damage == 'corrupt':(bundle / entry['object']).write_bytes(b'corrupt')
    elif damage == 'path_escape':entry['path'] = '../outside'
    else:
        parent = next(e for e in manifest['entries'] if e['kind']=='directory' and e['path']=='sources')
        parent.update(kind='symlink',target='/tmp')
    if damage in ('path_escape','symlink_parent'):(bundle / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises((OSError,ValueError,RuntimeError)):
        restore_installation(bundle,tmp_path/'restore')
    assert not (tmp_path / 'restore').exists()


def test_interrupted_backup_is_retained_without_completion_marker(installation, tmp_path, monkeypatch):
    """Copy failure keeps inspectable partial files but never produces a usable manifest or overwrites source."""
    from backend.runtime import installation_backup as backups

    root,_ = installation
    copy = backups.copy_regular
    calls=[]
    def fail_later(*args,**kwargs):
        """Fail after a real initial file copy to exercise partial-output semantics."""
        calls.append(1)
        if len(calls)==2:raise OSError('injected copy failure')
        return copy(*args,**kwargs)
    monkeypatch.setattr(backups,'copy_regular',fail_later)
    with pytest.raises(OSError,match='injected'):
        backups.backup_installation(root,tmp_path/'partial')
    assert (tmp_path/'partial').is_dir()
    assert not (tmp_path/'partial/manifest.json').exists()
    with pytest.raises((OSError,ValueError)):
        backups.verify_backup(tmp_path/'partial')


def test_copy_detects_noncooperating_source_changes(installation, tmp_path, monkeypatch):
    """A user edit during the frozen SQL interval cannot receive a successful snapshot manifest."""
    from backend.runtime import installation_backup as backups

    root,_ = installation
    original_copy = backups.copy_regular
    def copy_and_change(source,name,target,budget):
        """Mutate an original file after its bytes have actually been copied."""
        result = original_copy(source,name,target,budget)
        if name=='sources/project/sample.txt':(root/name).write_text('changed during backup')
        return result
    monkeypatch.setattr(backups,'copy_regular',copy_and_change)
    with pytest.raises(ValueError,match='changed'):
        backups.backup_installation(root,tmp_path/'changing')
    assert not (tmp_path/'changing/manifest.json').exists()


def test_external_git_objects_cannot_be_silently_omitted(installation, tmp_path):
    """An alternate object store outside the captured root requires explicit storage migration first."""
    from backend.runtime.installation_backup import backup_installation

    root,_ = installation
    alternate = root/'sources/project/.git/objects/info/alternates'
    alternate.write_text(str(tmp_path/'external-objects')+'\n')
    with pytest.raises(ValueError,match='outside'):
        backup_installation(root,tmp_path/'incomplete-git')
    assert not (tmp_path/'incomplete-git').exists()


def test_abrupt_restore_exit_never_enables_host_or_overwrites_existing_state(installation, tmp_path):
    """Kill an owned restore child after actual copied data; original backup stays verifiable and partial host inactive."""
    from backend.runtime.installation_backup import backup_installation, verify_backup
    from backend.runtime.host_installation import host_environment
    import sys

    root,_ = installation
    bundle=tmp_path/'backup';backup_installation(root,bundle)
    target=tmp_path/'interrupted'
    program='''import os,sys
from backend.runtime import installation_restore as restore
original=restore.copy_regular
calls=0
def copy_then_exit(*args,**kwargs):
    """Exit this test-owned child after two real copies, before any completion marker."""
    global calls
    result=original(*args,**kwargs)
    calls+=1
    if calls==2:os._exit(92)
    return result
restore.copy_regular=copy_then_exit
restore.restore_installation(sys.argv[1],sys.argv[2])
'''
    result=subprocess.run([sys.executable,'-c',program,str(bundle),str(target)],capture_output=True,timeout=20,check=False)
    assert result.returncode==92,result.stderr.decode()
    assert target.is_dir() and not (target/'installation.json').exists()
    with pytest.raises((ValueError,OSError)):host_environment(target)
    assert verify_backup(bundle)['status']=='complete'
    from backend.runtime.installation_restore import restore_installation
    with pytest.raises(FileExistsError):restore_installation(bundle,target)


def test_public_backup_verify_restore_commands_are_inference_free(installation, tmp_path):
    """The packaged command produces verifiable receipts and pending-enrollment storage with real files and SQL."""
    from backend.tests.cli.test_bootstrap import cli

    root,_=installation
    bundle=tmp_path/'cli-backup'
    target=tmp_path/'cli-restored'
    backup=cli('backup-host','--directory',root,'--destination',bundle)
    assert backup.returncode==0,backup.stderr
    verify=cli('verify-backup','--backup',bundle)
    assert verify.returncode==0,verify.stderr
    restore=cli('restore-host','--backup',bundle,'--destination',target)
    assert restore.returncode==0,restore.stderr
    receipt=json.loads(restore.stdout)
    assert receipt['status']=='pending_enrollment' and receipt['model_turns']==0
    assert json.loads(verify.stdout)['snapshot_id']==receipt['snapshot_id']
    for completed in (backup, verify, restore):
        limits = json.loads(completed.stdout)['execution_limits']
        assert limits['address_space_bytes'] <= 1024**3
        assert limits['cpu_seconds'] <= 300
        assert limits['aggregate_disk_quota'] is False


@pytest.mark.parametrize('limit', [{'max_files':1},{'max_bytes':1},{'timeout':0}])
def test_snapshot_limits_fail_without_successful_manifest(installation,tmp_path,limit):
    """Finite operator limits reject incomplete work instead of truncating snapshot data."""
    from backend.runtime.installation_backup import backup_installation

    root,_=installation
    with pytest.raises(ValueError):backup_installation(root,tmp_path/'limited',**limit)
    assert not (tmp_path/'limited/manifest.json').exists()


def test_outputs_cannot_enter_original_storage_through_parent_alias(installation,tmp_path):
    """Canonical parent checks protect original host and witness even when the caller uses a symlink alias."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation

    root,authority=installation
    alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match='overlap'):backup_installation(root,alias/'nested-backup')
    with pytest.raises(ValueError,match='witness'):backup_installation(root,Path(authority['witness']).parent/'nested-backup')
    bundle=tmp_path/'backup';backup_installation(root,bundle)
    with pytest.raises(ValueError,match='original'):restore_installation(bundle,alias/'nested-restore')
    assert not (root/'nested-backup').exists() and not (root/'nested-restore').exists()


async def test_restored_owner_reads_upload_and_report_with_original_project_boundaries(installation,tmp_path,monkeypatch):
    """Restored data is readable through actual HTTP handlers without configuring or admitting a native runtime."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.api import config
    from backend.api.main import create_app
    from backend.api.local_access import LocalAccess
    from backend.tests.runtime.test_workspace_delivery import owner_client

    root,_=installation
    bundle=tmp_path/'backup';backup_installation(root,bundle)
    target=tmp_path/'restored';restore_installation(bundle,target)
    monkeypatch.setenv('INFINIBAY_DB',str(target/'source.db'))
    monkeypatch.delenv('INFINIBAY_RUNTIME_CONFIG',raising=False)
    monkeypatch.setenv('INFINIBAY_AUTH_DIR',str(target/'auth'))
    monkeypatch.setattr(config,'UPLOAD_DIR',str(target/'uploads'))
    monkeypatch.setattr('backend.api.run.setup_file_logging',lambda:None)
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        data=await owner.get('/api/files/17/download?project_id=101')
        assert data.status_code==200 and data.content==b'original evidence\n'
        assert (await owner.get('/api/files/17/download?project_id=202')).status_code==404
        report=await owner.get('/api/artifacts/1?project_id=101')
        assert report.status_code==200 and report.json()['content']=='Retained report'
        assert (await owner.get('/api/artifacts/1?project_id=202')).status_code==404
        assert app.state.runtime_service is None
    assert app.state.local_access.key_file is None
    with sqlite3.connect(target/'source.db') as db:
        assert db.execute('SELECT count(*) FROM runtime_runs').fetchone()==(0,)


def test_symlinked_git_metadata_requires_explicit_storage_capture(installation,tmp_path):
    """A .git symlink cannot make a snapshot silently omit its actual repository metadata."""
    from backend.runtime.installation_backup import backup_installation

    root,_=installation
    metadata=root/'sources/project/.git'
    external=tmp_path/'external-git';metadata.rename(external)
    metadata.symlink_to(external,target_is_directory=True)
    with pytest.raises(ValueError,match='Git metadata'):
        backup_installation(root,tmp_path/'omitted-git')
    assert not (tmp_path/'omitted-git/manifest.json').exists()


@pytest.mark.parametrize('boundary', ['scan', 'probe'])
@pytest.mark.parametrize('database_name', ['source.db', 'uploads/101/uploads/cache.sqlite'])
def test_backup_tolerates_transient_sqlite_sidecars_without_losing_committed_rows(
    installation, tmp_path, monkeypatch, boundary, database_name
):
    """Real SQLite closure may remove sidecars before stat or header probing; the snapshot still owns every committed row."""
    import gc
    from contextlib import closing
    from backend.runtime import installation_backup as backups
    from backend.runtime import snapshot_files

    root, _ = installation
    gc.collect()
    keeper = sqlite3.connect(root / database_name)
    keeper.execute('PRAGMA journal_mode=WAL')
    keeper.execute('CREATE TABLE snapshot_race_evidence(value TEXT)')
    keeper.execute("INSERT INTO snapshot_race_evidence VALUES('committed before sidecar removal')")
    keeper.commit()
    assert (root / (database_name + '-shm')).exists()
    parent_identity = (root / database_name).parent.stat().st_ino
    closed = []

    def close_original():
        """Let SQLite checkpoint and remove its own transient files, preserving committed contents."""
        if not closed:
            keeper.close()
            closed.append(True)
            assert not (root / (database_name + '-shm')).exists()

    if boundary == 'scan':
        original_scan = snapshot_files.os.scandir

        def close_after_listing(path):
            """Retain actual directory entries and close SQLite before the caller can stat them."""
            entries = original_scan(path)
            if isinstance(path, int) and os.fstat(path).st_ino == parent_identity and not closed:
                with entries:
                    observed = list(entries)
                close_original()
                return iter(observed)
            return entries

        monkeypatch.setattr(snapshot_files.os, 'scandir', close_after_listing)
    else:
        original_inventory = backups.inventory

        def close_after_inventory(*args, **kwargs):
            """Finish the real initial inventory and then remove sidecars before header inspection."""
            observed = original_inventory(*args, **kwargs)
            close_original()
            return observed

        monkeypatch.setattr(backups, 'inventory', close_after_inventory)
    try:
        bundle = tmp_path / 'sidecar-backup'
        backups.backup_installation(root, bundle)
        manifest = backups.verify_backup(bundle)
        entry = next(item for item in manifest['entries'] if item['path'] == database_name)
        assert not any(item['path'] in {database_name + suffix for suffix in ('-wal', '-shm', '-journal')} for item in manifest['entries'])
        with closing(sqlite3.connect(bundle / entry['object'])) as snapshot:
            assert snapshot.execute('SELECT value FROM snapshot_race_evidence').fetchall() == [('committed before sidecar removal',)]
        assert closed == [True]
    finally:
        keeper.close()


def test_backup_preserves_ordinary_sidecar_names_and_refuses_their_disappearance(installation, tmp_path, monkeypatch):
    """A suffix alone cannot authorize omitting an ordinary user file or ignoring its concurrent deletion."""
    from backend.runtime import installation_backup as backups

    root, _ = installation
    (root / 'notes').write_text('ordinary document, not SQLite')
    (root / 'notes-shm').write_text('user evidence with a similar name')
    (root / 'orphan-wal').write_text('another ordinary file')
    bundle = tmp_path / 'regular-files'
    backups.backup_installation(root, bundle)
    manifest = backups.verify_backup(bundle)
    for name in ('notes-shm', 'orphan-wal'):
        entry = next(item for item in manifest['entries'] if item['path'] == name)
        assert (bundle / entry['object']).read_bytes() == (root / name).read_bytes()
    original = backups.inventory
    removed = []

    def remove_user_file(*args, **kwargs):
        """Delete a real ordinary file after listing to prove the backup still refuses incomplete data."""
        observed = original(*args, **kwargs)
        if not removed:
            (root / 'notes-shm').unlink()
            removed.append(True)
        return observed

    monkeypatch.setattr(backups, 'inventory', remove_user_file)
    with pytest.raises(FileNotFoundError):
        backups.backup_installation(root, tmp_path / 'refused-user-file')
    assert not (tmp_path / 'refused-user-file/manifest.json').exists()

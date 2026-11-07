"""Preserve original attachment bytes and durable operation identity across failed mutations."""

import sqlite3
import hashlib
import json
import os
import subprocess
import sys
from contextlib import closing, contextmanager
from pathlib import Path

import pytest

from backend.tests.api.test_reference_files import upload, uploads
from backend.tests.runtime.test_installation_backup import installation
from backend.research.models import SourceUnavailable
from backend.research.reference_operations import ReferenceOperations
from backend.research.reference_storage import ReferenceStorage


def keyed_upload(client, key='original-upload', data=b'Original attachment'):
    """Submit a stable owner intent so a lost HTTP reply can be retried without another upload."""
    return client.post('/api/files?project_id=1', files={'file':('original.txt',data,'text/plain')}, data={'operation_key':key})


def history(client, project=1):
    """Read real project-scoped operation history without completing a pending effect."""
    response = client.get(f'/api/files/operations?project_id={project}')
    assert response.status_code == 200, response.text
    return response.json()


def recover(client, key='original-upload', project=1, action='reconcile'):
    """Request explicit recovery of a known original operation, including owner CSRF checks."""
    return client.post(f'/api/files/operations/{key}/{action}?project_id={project}')


def operations(database, root):
    """Bind the real durable service to a synthetic existing database and confined root."""
    from backend.db.connection import connect
    @contextmanager
    def connection():
        """Commit on success and roll back interrupted mutations using production connection settings."""
        with closing(connect(database, existing_only=True)) as conn, conn:
            yield conn
    return ReferenceOperations(connection, ReferenceStorage(root))


def test_failed_delete_commit_preserves_downloadable_original(uploads, db_conn):
    """A rejected metadata deletion must not erase the file that its rolled-back row still references."""
    client, _root = uploads
    row = upload(client, b'Keep the original bytes.').json()
    path = Path(row['filepath'])
    db_conn.execute("CREATE TRIGGER reject_reference_delete BEFORE DELETE ON reference_files BEGIN SELECT RAISE(ABORT,'delete rejected'); END")
    db_conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match='delete rejected'):
        client.delete(f"/api/files/{row['id']}?project_id=1")
    assert path.read_bytes() == b'Keep the original bytes.'
    assert client.get(f"/api/files/{row['id']}/download?project_id=1").content == b'Keep the original bytes.'
    assert [item['kind'] for item in history(client)] == ['upload']


def test_original_receipt_replays_without_recreating_deleted_attachment(uploads, db_conn):
    """A lost reply reuses one ID; later replay never resurrects a deleted reference or overwrites intent."""
    client, root = uploads
    first = keyed_upload(client)
    assert first.status_code == 201, first.text
    assert keyed_upload(client).json() == first.json()
    assert len(list(root.rglob('*'))) == 3
    assert keyed_upload(client, data=b'different').status_code == 409
    file_id = first.json()['id']
    assert client.delete(f'/api/files/{file_id}?project_id=1').status_code == 204
    assert client.delete(f'/api/files/{file_id}?project_id=1').status_code == 204
    assert keyed_upload(client).json() == first.json()
    assert client.get(f'/api/files/{file_id}?project_id=1').status_code == 404
    assert db_conn.execute('SELECT count(*) FROM reference_files').fetchone()[0] == 0
    assert {row['state'] for row in history(client)} == {'published','deleted'}


def test_recovery_scope_authentication_and_history_do_not_grant_authority(uploads, db_conn):
    """Known keys grant no cross-project access and inspection cannot perform owner writes."""
    client, _ = uploads
    db_conn.execute("INSERT INTO projects(id,name) VALUES(2,'Another project')")
    db_conn.commit()
    assert keyed_upload(client).status_code == 201
    assert recover(client, project=2).status_code == 404
    assert recover(client, project=2, action='abandon').status_code == 404
    assert history(client, 2) == []
    assert keyed_upload(client, key='delete:1').status_code == 400
    assert keyed_upload(client, key='').status_code == 400
    csrf = client.headers.pop('X-Researcher-CSRF')
    assert recover(client).status_code == 403
    client.headers['X-Researcher-CSRF'] = csrf
    client.cookies.clear()
    assert recover(client).status_code == 401
    assert client.get('/api/files/operations?project_id=1').status_code == 401


@pytest.mark.parametrize('failure', ['partial_write','fsync','publication'])
def test_failed_upload_retains_original_operation_and_never_returns_false_success(uploads, db_conn, monkeypatch, failure):
    """Disk-full, fsync and DB-publication failures preserve identifiable bytes for recovery or explicit closure."""
    client, root = uploads
    with monkeypatch.context() as patch:
        if failure == 'partial_write':
            write = os.write
            def partial(fd, data):
                """Write one real prefix, then reproduce a full filesystem in the owned upload."""
                write(fd, data[:4])
                raise OSError(28, 'synthetic full disk')
            patch.setattr(os, 'write', partial)
        elif failure == 'fsync':
            fsync = os.fsync
            def fail_file(fd):
                """Reject only regular-file durability, preserving directory setup and the original bytes."""
                import stat
                if stat.S_ISREG(os.fstat(fd).st_mode): raise OSError(5, 'synthetic fsync failure')
                fsync(fd)
            patch.setattr(os, 'fsync', fail_file)
        else:
            db_conn.execute("CREATE TRIGGER refuse_publication BEFORE INSERT ON reference_files BEGIN SELECT RAISE(ABORT,'publication rejected'); END")
            db_conn.commit()
        if failure == 'publication':
            with pytest.raises(sqlite3.IntegrityError, match='publication rejected'): keyed_upload(client)
        else:
            assert keyed_upload(client).status_code == 422
    pending = history(client)
    assert len(pending) == 1 and pending[0]['state'] == 'pending'
    assert db_conn.execute('SELECT count(*) FROM reference_files').fetchone()[0] == 0
    path = next(p for p in root.rglob('*') if p.is_file())
    retained = path.read_bytes()
    if failure == 'partial_write':
        assert recover(client).status_code == 422
        assert keyed_upload(client).status_code == 422
        assert recover(client, action='abandon').json()['state'] == 'abandoned'
        assert recover(client, action='abandon').json()['state'] == 'abandoned'
        assert recover(client).json()['state'] == 'abandoned'
        assert keyed_upload(client).status_code == 409
        assert path.read_bytes() == retained == b'Orig'
    else:
        if failure == 'publication':
            db_conn.execute('DROP TRIGGER refuse_publication'); db_conn.commit()
        result = recover(client)
        assert result.status_code == 200, result.text
        assert result.json()['state'] == 'published'
        assert path.read_bytes() == b'Original attachment'
        assert db_conn.execute('SELECT count(*) FROM reference_files').fetchone()[0] == 1


@pytest.mark.parametrize('boundary', ['saved_upload','removed_file'])
def test_process_death_recovers_original_filesystem_effect_once(uploads, _isolated_db, db_conn, boundary):
    """Kill a real child after fsync/unlink; recover its committed operation through HTTP without rerunning its effect."""
    import backend.research.reference_operations as module
    client, root = uploads
    file_id = upload(client).json()['id'] if boundary == 'removed_file' else 0
    program = '''import sys,hashlib,os
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from contextlib import closing,contextmanager
from backend.db.connection import connect
import backend.research.reference_operations as module
from backend.research.reference_storage import ReferenceStorage
assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()==sys.argv[6]
@contextmanager
def connection():
    """Commit the same original file intent before the injected abrupt process death."""
    with closing(connect(sys.argv[2],existing_only=True)) as c,c:yield c
storage=ReferenceStorage(Path(sys.argv[3]))
method='save' if sys.argv[4]=='saved_upload' else 'remove'
original=getattr(storage,method)
def die(*args,**kwargs):
    """Terminate only this owned child after the real filesystem operation returns."""
    original(*args,**kwargs)
    os._exit(93)
setattr(storage,method,die)
service=module.ReferenceOperations(connection,storage)
if method=='save':service.upload(1,'original.txt',b'Original attachment','text/plain','',operation_key='original-upload')
else:service.delete(1,int(sys.argv[5]))
'''
    result = subprocess.run([sys.executable,'-c',program,str(Path(module.__file__).parents[2]),str(_isolated_db),str(root),boundary,str(file_id),hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()],cwd=root.parent,capture_output=True,timeout=15)
    assert result.returncode == 93, result.stderr.decode()[-2000:]
    key = 'original-upload' if boundary == 'saved_upload' else f'delete:{file_id}'
    pending = next(row for row in history(client) if row['operation_key'] == key)
    assert pending['state'] == 'pending'
    first = recover(client,key)
    assert first.status_code == 200, first.text
    assert first.json()['state'] == ('published' if boundary == 'saved_upload' else 'deleted')
    assert recover(client,key).json() == first.json()
    assert db_conn.execute('SELECT count(*) FROM reference_files').fetchone()[0] == (1 if boundary == 'saved_upload' else 0)


def test_pending_delete_preserves_changed_file_and_unavailable_root(uploads, monkeypatch):
    """An admitted delete can recover once; changed revisions or lost storage never authorize another file's removal."""
    client, root = uploads
    row = upload(client).json(); path = Path(row['filepath'])
    def fail(*args, **kwargs):
        """Reproduce storage loss after durable deletion intent, before unlink."""
        raise SourceUnavailable('storage temporarily unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(ReferenceStorage,'remove',fail)
        assert client.delete(f"/api/files/{row['id']}?project_id=1").status_code == 422
    assert path.exists()
    assert client.get(f"/api/files/{row['id']}?project_id=1").status_code == 404
    hidden = root.with_name('temporarily-unmounted'); root.rename(hidden)
    assert recover(client,f"delete:{row['id']}").status_code == 422
    hidden.rename(root)
    path.write_bytes(b'Changed revision must survive')
    assert recover(client,f"delete:{row['id']}").status_code == 422
    assert path.read_bytes() == b'Changed revision must survive'
    assert history(client)[0]['state'] == 'pending'


def test_closing_inflight_upload_never_publishes_late_bytes(uploads, monkeypatch, db_conn):
    """Owner closure wins even while an already-admitted upload finishes its filesystem write."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    client, root = uploads
    admitted, release = Event(), Event()
    save = ReferenceStorage.save
    def delayed(self, *args, **kwargs):
        """Hold only the owned upload after its durable intent so the owner can close it."""
        admitted.set()
        assert release.wait(5)
        return save(self, *args, **kwargs)
    monkeypatch.setattr(ReferenceStorage,'save',delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(keyed_upload,client)
        try:
            assert admitted.wait(5)
            assert history(client)[0]['state'] == 'pending'
            assert recover(client,action='abandon').json()['state'] == 'abandoned'
        finally: release.set()
        assert future.result(timeout=10).status_code == 409
    assert next(p for p in root.rglob('*') if p.is_file()).read_bytes() == b'Original attachment'
    assert db_conn.execute('SELECT count(*) FROM reference_files').fetchone()[0] == 0


def test_migration_inverse_refuses_history_and_preserves_legacy_references(tmp_path):
    """Unused schema66 reverses safely; any admitted operation prevents erasing its recovery history."""
    from backend.db.reference_operations_migration import restore_reference_operations_schema
    from backend.tools.base.db import ensure_migrations
    used = tmp_path/'used.db'
    ensure_migrations(used,target_version=66)
    with sqlite3.connect(used) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(1,'Retained')")
    operations(used,tmp_path/'uploads').upload(1,'original.txt',b'original','text/plain','',operation_key='original')
    with sqlite3.connect(used) as conn:
        with pytest.raises(RuntimeError,match='history'): restore_reference_operations_schema(conn)
    database = tmp_path/'unused.db'
    ensure_migrations(database,target_version=65)
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(1,'Retained')")
        conn.execute("INSERT INTO reference_files(project_id,file_name,file_path) VALUES(1,'legacy.txt','/legacy')")
    ensure_migrations(database,target_version=66)
    with sqlite3.connect(database) as conn:
        restore_reference_operations_schema(conn)
        assert conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0] == 65
        assert conn.execute('SELECT file_path FROM reference_files').fetchone()[0] == '/legacy'


def test_backup_restore_retains_pending_upload_and_refuses_old_delete_identity(installation, tmp_path, monkeypatch):
    """Restore relocates recoverable uploads but never substitutes a new inode into an old deletion authorization."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    root, _ = installation
    service = operations(root/'source.db',root/'uploads')
    def stop(*args, **kwargs):
        """Retain a committed intent after real bytes are present and before publication or unlink."""
        raise SourceUnavailable('interrupted boundary')
    with monkeypatch.context() as patch:
        patch.setattr(service,'reconcile',stop)
        with pytest.raises(SourceUnavailable): service.upload(101,'pending.txt',b'Original attachment','text/plain','',operation_key='original-upload')
        with pytest.raises(SourceUnavailable): service.delete(101,17)
    before = service.history(101)
    bundle = tmp_path/'bundle'; restored = tmp_path/'restored'
    backup_installation(root,bundle); restore_installation(bundle,restored)
    recovered = operations(restored/'source.db',restored/'uploads')
    assert recovered.history(101) == before
    result = recovered.reconcile(101,'original-upload')
    assert result['state'] == 'published'
    assert Path(result['receipt']['filepath']).is_relative_to(restored)
    assert Path(result['receipt']['filepath']).read_bytes() == b'Original attachment'
    with pytest.raises(SourceUnavailable,match='cambió'): recovered.reconcile(101,'delete:17')
    assert (restored/'uploads/101/uploads/exact.txt').read_bytes() == b'original evidence\n'
    assert recovered.history(101)[0]['state'] == 'pending'

"""Preserve old database identities and exact external bytes before enabling a new native host."""

import json
import hashlib
from pathlib import Path
import sqlite3
from contextlib import closing

import pytest

from backend.tests.runtime.test_host_installation import host_assets
from backend.tests.runtime.test_installation_backup import git


@pytest.fixture
def legacy(tmp_path):
    """Prepare schema17 with container paths, same-named reports and cross-root linked Git storage."""
    root = tmp_path/'old';root.mkdir()
    reports = root/'reports';reports.mkdir()
    (reports/'one.md').write_text('# Original report\n\nExact historical text.\n')
    (reports/'two.md').write_text('Different filesystem revision; preserve DB body.\n')
    uploads = root/'uploads';uploads.mkdir()
    (uploads/'file.txt').write_bytes(b'original upload\n')
    repositories = root/'repositories';repositories.mkdir()
    repository = repositories/'main';repository.mkdir()
    git(repository,'init','-b','main')
    (repository/'file.py').write_text('value = 1\n')
    git(repository,'add','.');git(repository,'commit','-m','historical')
    worktrees = root/'worktrees';worktrees.mkdir()
    git(repository,'worktree','add','--detach',str(worktrees/'linked'))
    (worktrees/'linked/dirty.txt').write_text('uncommitted historical work\n')
    database = root/'old.db'
    schema = Path(__file__).resolve().parents[2]/'db/schema.sql'
    with closing(sqlite3.connect(database)) as db, db:
        db.executescript(schema.read_text())
        db.execute("INSERT INTO projects(id,name) VALUES(101,'Old project'),(202,'Other project')")
        db.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Preserve this task')")
        db.execute("INSERT INTO artifacts(id,project_id,task_id,type,file_path,content) VALUES(7,101,1001,'report','/artifacts/one.md',NULL),(8,202,NULL,'report','/artifacts/two.md','Stored original body')")
        db.execute("INSERT INTO reference_files(id,project_id,file_name,file_path,file_size) VALUES(9,101,'file.txt','/pod/uploads/file.txt',16)")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'main','/pod/repos/main')")
        db.execute("INSERT INTO agent_worktrees(id,project_id,repo_id,agent_id,worktree_path) VALUES(12,101,11,'old-agent','/pod/worktrees/linked')")
    manifest = {'format':1,'storage':[
        {'name':name,'path':str(path),'stored_prefix':prefix}
        for name,path,prefix in [('reports',reports,'/artifacts'),('uploads',uploads,'/pod/uploads'),
                                 ('repos',repositories,'/pod/repos'),('worktrees',worktrees,'/pod/worktrees')]],
        'chroma_exports':[]}
    return database,manifest


def test_staged_legacy_data_preserves_ids_files_and_new_enrollment(legacy,tmp_path,host_assets):
    """Actual Git/SQLite migration retains old data and remains blocked until explicit fresh enrollment."""
    from backend.runtime.legacy_import import stage_legacy_host
    from backend.runtime.host_installation import host_environment
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.installation_backup import backup_installation

    database,manifest = legacy
    before = database.read_bytes()
    target = tmp_path/'imported'
    receipt = stage_legacy_host(database,target,manifest=manifest)
    assert receipt['status']=='pending_enrollment' and receipt['model_turns']==0
    assert database.read_bytes()==before
    with pytest.raises(ValueError,match='incomplete'):
        host_environment(target)
    with sqlite3.connect(target/'source.db') as db:
        assert db.execute('SELECT id,content FROM artifacts ORDER BY id').fetchall()==[(7,'# Original report\n\nExact historical text.\n'),(8,'Stored original body')]
        assert db.execute('SELECT id,title FROM tasks').fetchall()==[(1001,'Preserve this task')]
        upload = db.execute('SELECT file_path FROM reference_files WHERE id=9').fetchone()[0]
        assert Path(upload).is_relative_to(target/'uploads/101/uploads')
        assert Path(upload).read_bytes()==b'original upload\n'
        repository = Path(db.execute('SELECT local_path FROM repositories WHERE id=11').fetchone()[0])
        worktree = Path(db.execute('SELECT worktree_path FROM agent_worktrees WHERE id=12').fetchone()[0])
        assert git(repository,'rev-parse','HEAD')==git(worktree,'rev-parse','HEAD')
        assert git(worktree,'rev-parse','--show-toplevel')==str(worktree)
        assert (worktree/'dirty.txt').read_text()=='uncommitted historical work\n'
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('SELECT COUNT(*) FROM research_reports').fetchone()==(0,)
    assert enroll_restored_host(target,witness_dir=tmp_path/'fresh-witness',assets=host_assets)['status']=='prepared'
    backup_installation(target,tmp_path/'new-backup')
    with pytest.raises(FileExistsError):
        stage_legacy_host(database,target,manifest=manifest)


@pytest.mark.parametrize('damage',['unmapped_upload','missing_report','symlink_report','overlap','modern_database'])
def test_invalid_legacy_import_never_activates_or_changes_original(legacy,tmp_path,damage):
    """Ambiguous/outside/missing bytes and native installations cannot bypass preservation or authority rules."""
    from backend.runtime.legacy_import import stage_legacy_host
    from backend.tools.base.db import ensure_migrations

    database,manifest = legacy
    target = tmp_path/'imported'
    report = database.parent/'reports/one.md'
    if damage=='unmapped_upload':manifest['storage']=[m for m in manifest['storage'] if m['name']!='uploads']
    elif damage=='missing_report':report.unlink()
    elif damage=='symlink_report':report.unlink();report.symlink_to(database.parent/'uploads/file.txt')
    elif damage=='overlap':target=database.parent/'reports/inside'
    else:ensure_migrations(str(database),existing_only=True)
    before = database.read_bytes()
    with pytest.raises((ValueError,OSError,RuntimeError)):
        stage_legacy_host(database,target,manifest=manifest)
    assert database.read_bytes()==before
    assert not (target/'installation.json').exists()


async def test_imported_report_and_upload_have_real_owner_http_scope(legacy,tmp_path,monkeypatch):
    """The normal readers serve hydrated content by original ID and reject a different project's access."""
    from backend.runtime.legacy_import import stage_legacy_host
    from backend.api import config
    from backend.api.main import create_app
    from backend.api.local_access import LocalAccess
    from backend.tests.runtime.test_workspace_delivery import owner_client

    database,manifest=legacy;target=tmp_path/'imported'
    stage_legacy_host(database,target,manifest=manifest)
    monkeypatch.setenv('INFINIBAY_DB',str(target/'source.db'))
    monkeypatch.delenv('INFINIBAY_RUNTIME_CONFIG',raising=False)
    monkeypatch.setenv('INFINIBAY_AUTH_DIR',str(target/'auth'))
    monkeypatch.setattr(config,'UPLOAD_DIR',str(target/'uploads'))
    monkeypatch.setattr('backend.api.run.setup_file_logging',lambda:None)
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        report=await owner.get('/api/artifacts/7?project_id=101')
        assert report.status_code==200 and 'Exact historical text' in report.json()['content']
        assert (await owner.get('/api/artifacts/7?project_id=202')).status_code==404
        attachment=await owner.get('/api/files/9/download?project_id=101')
        assert attachment.status_code==200 and attachment.content==b'original upload\n'
        assert (await owner.get('/api/files/9/download?project_id=202')).status_code==404


def test_public_legacy_import_command_keeps_execution_pending(legacy,tmp_path):
    """The installed administrative command stages data without credentials or automatic enrollment."""
    from backend.tests.cli.test_bootstrap import cli

    database,manifest=legacy
    config=tmp_path/'mapping.json';config.write_text(json.dumps(manifest))
    result=cli('stage-legacy-host','--database',database,'--storage-manifest',config,'--destination',tmp_path/'imported')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='pending_enrollment'


@pytest.fixture
def chroma_export(tmp_path):
    """Build a portable-format fixture; the separate integration trial uses the real pinned Chroma reader."""
    root=tmp_path/'export';root.mkdir()
    (root/'source').mkdir()
    (root/'source/retained.bin').write_bytes(b'original raw storage fixture')
    rows=[{'collection':'alpha','id':'same-id','document':'Exact fragment: 137 + 63 = 200.','metadata':{'project_id':202,'page':2}},
          {'collection':'alpha','id':'metadata-only','document':None,'metadata':{'source':'missing text'}},
          {'collection':'beta','id':'same-id','document':'Other project fragment.','metadata':None}]
    (root/'records.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    def descriptor(name):
        """Bind each fixture file to its exact raw bytes rather than claimed record counts alone."""
        data=(root/name).read_bytes()
        return {'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    manifest={'format':1,'kind':'researcher-chroma-export','status':'complete','reader_version':'1.5.9',
              'collections':[{'name':'alpha','count':2},{'name':'beta','count':1}],
              'records':{**descriptor('records.jsonl'),'count':3},'source_files':[descriptor('source/retained.bin')]}
    (root/'manifest.json').write_text(json.dumps(manifest))
    return root


@pytest.mark.parametrize('migration_target', [58, None])
def test_chroma_fragments_keep_exact_text_identity_and_explicit_project(legacy,chroma_export,tmp_path,monkeypatch,migration_target):
    """Same IDs in separate collections and misleading metadata cannot override an explicit project assignment."""
    from backend.runtime.legacy_import import stage_legacy_host

    database,manifest=legacy
    manifest['chroma_exports']=[{'path':str(chroma_export),'projects':{'alpha':101,'beta':202}}]
    from backend.tools.base import db as migrations
    migrate = migrations.ensure_migrations
    def historical_prefix(path, **kwargs):
        """Build a genuine schema58 fixture for its inverse, while retaining a separate current-import case."""
        return migrate(path, **{**kwargs, 'target_version':58})
    target=tmp_path/'imported'
    with monkeypatch.context() as patch:
        if migration_target is not None: patch.setattr(migrations,'ensure_migrations',historical_prefix)
        receipt=stage_legacy_host(database,target,manifest=manifest)
    assert receipt['chroma_records']==3
    evidence=json.loads((target/receipt['import_manifest']).read_text())
    fragments=evidence['chroma_chunks']
    assert fragments[0]['project_id']==101 and fragments[0]['metadata']['project_id']==202
    assert fragments[1]['reference_id'] is None and fragments[1]['disposition']=='metadata_only'
    assert fragments[2]['project_id']==202
    with sqlite3.connect(target/'source.db') as db:
        saved=db.execute("SELECT project_id,file_path,description FROM reference_files WHERE uploaded_by='legacy-import' ORDER BY id").fetchall()
        assert len(saved)==2 and saved[0][0]==101 and saved[1][0]==202
        assert Path(saved[0][1]).read_text()=='Exact fragment: 137 + 63 = 200.'
        assert 'No equivale al documento original completo' in saved[0][2]
        assert db.execute('SELECT count(*) FROM findings').fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM research_sources').fetchone()==(0,)
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.service import ResearchService
    store=SQLiteResearchStore(target/'source.db')
    token=store.issue_grant(project_id=101,task_id=1001,agent_id='import-evaluator',permissions={'sources.read','sources.capture'})
    scope=store.authorize(token)
    service=ResearchService(store,reference_reader=BoundedReferenceReader(target/'uploads'))
    captured=service.capture_reference(scope,'capture-imported-fragment',fragments[0]['reference_id'])
    source=store.read_source(scope,captured['source_id'])
    provenance=source['provenance']['imported_history']
    assert provenance['collection']=='alpha' and provenance['original_id']=='same-id'
    assert provenance['metadata']['page']==2 and provenance['assignment']=='explicit_operator_mapping'
    from backend.db.reference_provenance_migration import restore_reference_provenance_schema
    from backend.research.models import SourceUnavailable
    with sqlite3.connect(target/'source.db') as db:
        with pytest.raises(RuntimeError,match='imported history' if migration_target==58 else 'newer schema'):
            restore_reference_provenance_schema(db)
    Path(saved[0][1]).write_text('Later replacement must not inherit original page attribution.')
    with pytest.raises(SourceUnavailable,match='historical provenance'):
        service.capture_reference(scope,'different-capture-after-edit',fragments[0]['reference_id'])


@pytest.mark.parametrize('damage',['missing_project','corrupt_bytes','wrong_count','duplicate_identity'])
def test_bad_chroma_export_preserves_partial_import_without_activation(legacy,chroma_export,tmp_path,damage):
    """Unassigned, corrupt or incomplete legacy text cannot become a completed native installation."""
    from backend.runtime.legacy_import import stage_legacy_host

    database,manifest=legacy
    projects={'alpha':101,'beta':202}
    path=chroma_export/'manifest.json';saved=json.loads(path.read_text())
    if damage=='missing_project':projects.pop('beta')
    elif damage=='corrupt_bytes':(chroma_export/'records.jsonl').write_text('corrupt')
    elif damage=='wrong_count':saved['collections'][0]['count']=3
    else:
        data=(chroma_export/'records.jsonl').read_bytes()
        data+=data.splitlines(keepends=True)[0]
        (chroma_export/'records.jsonl').write_bytes(data)
        saved['records'].update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),count=4)
        saved['collections'][0]['count']=3
    path.write_text(json.dumps(saved))
    manifest['chroma_exports']=[{'path':str(chroma_export),'projects':projects}]
    target=tmp_path/'imported'
    with pytest.raises(ValueError):stage_legacy_host(database,target,manifest=manifest)
    assert not (target/'installation.json').exists()


def test_committed_wal_data_is_captured_without_changing_source_rows(legacy,tmp_path):
    """A consistent SQLite snapshot includes committed WAL rows even while the original connection stays open."""
    from backend.runtime.legacy_import import stage_legacy_host

    database,manifest=legacy
    with closing(sqlite3.connect(database)) as original:
        original.execute('PRAGMA journal_mode=WAL')
        original.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1002,101,'research','Committed in WAL')")
        original.commit()
        before=list(original.iterdump())
        stage_legacy_host(database,tmp_path/'imported',manifest=manifest)
        assert list(original.iterdump())==before
    with sqlite3.connect(tmp_path/'imported/source.db') as db:
        assert db.execute('SELECT title FROM tasks WHERE id=1002').fetchone()==('Committed in WAL',)


def test_interrupted_legacy_stage_stays_inactive_and_recovers_at_new_path(legacy,tmp_path):
    """An owned child exit after data commits cannot publish a usable host or erase the recovery source."""
    import subprocess
    import sys
    from backend.runtime.legacy_import import stage_legacy_host
    from backend.runtime.host_installation import host_environment

    database,manifest=legacy
    program='''import json,os,sys
from backend.runtime import legacy_import as module
write=module._write_new
def interrupt(path,value):
    if path.name=='installation.json':os._exit(94)
    return write(path,value)
module._write_new=interrupt
module.stage_legacy_host(sys.argv[1],sys.argv[2],manifest=json.loads(sys.argv[3]))
'''
    result=subprocess.run([sys.executable,'-c',program,str(database),str(tmp_path/'partial'),json.dumps(manifest)],capture_output=True,text=True,timeout=20)
    assert result.returncode==94,result.stderr
    with pytest.raises((OSError,ValueError)):host_environment(tmp_path/'partial')
    with pytest.raises(FileExistsError):stage_legacy_host(database,tmp_path/'partial',manifest=manifest)
    assert stage_legacy_host(database,tmp_path/'fresh',manifest=manifest)['status']=='pending_enrollment'

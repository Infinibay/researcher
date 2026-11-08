"""Retained work survives interrupted archive/removal and is restored as new data; storage fixtures do not prove kernel closure."""

from pathlib import Path

import pytest

from backend.runtime.contracts import RunConflict
from backend.runtime.workspace_retention import WorkspaceRetention
from backend.tests.runtime.test_development_state import development_state as development_state
from backend.tests.runtime.test_installation_backup import git
from backend.tests.runtime.test_installation_backup import installation as installation


@pytest.fixture
def retained(development_state):
    """Seed a real dirty private Git copy and a closed storage-only author, with an explicit synthetic closure port."""
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace
    s, lease, binding, copies = development_state
    planned, _ = copies.plan(lease)
    root = Path(planned['allocation'])/'repository'; root.mkdir(parents=True, mode=0o700)
    root.parent.chmod(0o700);root.parent.parent.chmod(0o700)
    git(root, 'init', '-b', 'main')
    (root/'value.txt').write_text('original\n');(root/'.gitignore').write_text('ignored.txt\n')
    git(root, 'add', '.');git(root, 'commit', '-m', 'base')
    (root/'value.txt').write_text('valuable pending edit\n')
    (root/'untracked.txt').write_text('new work\n');(root/'ignored.txt').write_text('ignored work\n')
    info = root.stat()
    copies.complete(lease, PreparedDevelopmentWorkspace(11,str(root),info.st_dev,info.st_ino,'a'*40,'b'*40))
    s.c.store.finish(lease,native_status='completed',summary='Synthetic author closure; no real peers in this fixture.')
    def closed(conn, row):
        """Witness only the storage boundary; production supplies the journal-backed closure observer."""
        assert row['attempt_id']==lease.attempt_id
        return {'synthetic_storage_fixture':True}
    retention = WorkspaceRetention(s.c.store,s.control,s.root,closed=closed)
    return s,lease,root,retention


def test_explicit_retention_preserves_all_work_and_restores_new_data(retained):
    """Archive tracked/untracked/ignored files, wait the chosen period, remove the original and restore bytes without reviving its identity."""
    s,lease,root,retention = retained
    operation,created = retention.quarantine(101,lease.attempt_id,'quarantine-one',retention_days=1,acknowledge_unavailability=True)
    assert created
    retention.execute(101,operation['operation_key'])
    item = retention.list(101)[0]
    assert item['state']=='retained' and item['changes']['tracked']==1
    assert item['changes']['untracked']==1 and item['changes']['ignored']==1
    assert (root/'ignored.txt').read_text()=='ignored work\n'
    assert retention.quarantine(101,lease.attempt_id,'quarantine-one',retention_days=1,acknowledge_unavailability=True)[1] is False
    with pytest.raises(RunConflict,match='retention|retención'):
        retention.request(101,lease.attempt_id,'remove-one','remove',item['archive_sha256'])
    s.c.now[0]+=86401
    removal,_=retention.request(101,lease.attempt_id,'remove-one','remove',item['archive_sha256'])
    retention.execute(101,removal['operation_key'])
    assert not root.exists() and retention.list(101)[0]['state']=='removed'
    restore,_=retention.request(101,lease.attempt_id,'restore-one','restore',item['archive_sha256'])
    receipt=retention.execute(101,restore['operation_key'])['receipt']
    recovered=Path(receipt['restored_path'])/'repository'
    assert recovered!=root and (recovered/'value.txt').read_text()=='valuable pending edit\n'
    assert (recovered/'untracked.txt').read_text()=='new work\n'
    assert (recovered/'ignored.txt').read_text()=='ignored work\n'
    assert not receipt['execution_started'] and not receipt['publication_performed']


def test_changed_files_do_not_inherit_an_older_removal_decision(retained):
    """A new owner edit after archive survives the old delete intent and remains visibly unresolved."""
    s,lease,root,retention=retained
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    retention.execute(101,'archive'); item=retention.list(101)[0];s.c.now[0]+=86401
    retention.request(101,lease.attempt_id,'remove','remove',item['archive_sha256'])
    (root/'untracked.txt').write_text('later owner work\n')
    result=retention.execute(101,'remove')
    assert result['state']=='pending' and result['issue']
    assert (root/'untracked.txt').read_text()=='later owner work\n'


def test_unproved_closure_and_foreign_scope_never_quarantine(retained):
    """No status label or caller-supplied project can substitute for the original closure observer."""
    s,lease,root,retention=retained
    def live(conn,row):
        """Represent a physical domain whose retirement has not been established."""
        raise RunConflict('Original domain remains active')
    retention.closed=live
    with pytest.raises(RunConflict,match='active'):
        retention.quarantine(101,lease.attempt_id,'uncertain',retention_days=1,acknowledge_unavailability=True)
    assert retention.list(101)[0]['state']=='available'
    assert root.exists() and not retention.operations(101)


@pytest.mark.parametrize('kind',['archive','remove','restore'])
def test_crash_after_filesystem_effect_recovers_original_receipt(retained,kind):
    """A child exits after the original filesystem effect; reopening completes the same decision without deleting replacement data or duplicating recovery."""
    import multiprocessing
    import os
    from backend.runtime import workspace_retention as module
    s,lease,root,retention=retained
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    if kind!='archive':
        retention.execute(101,'archive');item=retention.list(101)[0];s.c.now[0]+=86401
        retention.request(101,lease.attempt_id,kind,kind,item['archive_sha256'])
    def crash():
        """Terminate the actual writer after its file effect and before the result/event transaction."""
        effect=module.remove_original if kind=='remove' else module.copy_snapshot
        def die(*args,**kwargs):
            """Keep the real filesystem effect and then simulate abrupt process loss."""
            effect(*args,**kwargs);os._exit(73)
        if kind=='remove':module.remove_original=die
        else:module.copy_snapshot=die
        retention.execute(101,kind)
        os._exit(74)
    child=multiprocessing.get_context('fork').Process(target=crash);child.start();child.join(10)
    assert child.exitcode==73
    assert retention.operation(101,kind)['state']=='pending'
    if kind=='remove':
        root.mkdir(parents=True,mode=0o700);root.parent.chmod(0o700)
        (root/'replacement.txt').write_text('later independent data')
    completed=retention.execute(101,kind)
    assert completed['state']=='completed',completed
    assert retention.execute(101,kind)==completed
    if kind=='remove':assert (root/'replacement.txt').read_text()=='later independent data'
    if kind=='restore':assert (Path(completed['receipt']['restored_path'])/'repository'/'ignored.txt').read_text()=='ignored work\n'


def test_partial_copy_and_corrupt_archive_never_authorize_deletion(retained,monkeypatch):
    """Disk/copy failure retains original work; corrupted recovery bytes prevent a later removal rather than reporting success."""
    from backend.runtime import retention_files
    s,lease,root,retention=retained
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    original=retention_files.copy_regular
    def full_disk(source,relative,destination,budget):
        """Leave a partial temporary file just as a failed bounded disk write can do."""
        Path(destination).write_bytes(b'partial');raise OSError(28,'No space left')
    monkeypatch.setattr(retention_files,'copy_regular',full_disk)
    failed=retention.execute(101,'archive');assert failed['state']=='pending'
    assert (root/'value.txt').read_text()=='valuable pending edit\n'
    monkeypatch.setattr(retention_files,'copy_regular',original)
    assert retention.execute(101,'archive')['state']=='completed'
    item=retention.list(101)[0];s.c.now[0]+=86401
    with s.c.store._transaction() as conn:record=retention._record(conn,101,lease.attempt_id)
    archive=Path(retention.control['path'])/'retention'/record['archive_id']/'snapshot'
    (archive/'repository'/'value.txt').write_text('corrupted')
    retention.request(101,lease.attempt_id,'remove','remove',item['archive_sha256'])
    assert retention.execute(101,'remove')['state']=='pending'
    assert (root/'value.txt').read_text()=='valuable pending edit\n'


def test_partial_removal_failure_stays_pending_and_reconciles_without_force(retained,monkeypatch):
    """An unlink failure never marks the operation complete, and the original archived revision can be reconciled after the error clears."""
    import os
    from backend.runtime import retention_files
    s,lease,root,retention=retained
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    retention.execute(101,'archive');item=retention.list(101)[0];s.c.now[0]+=86401
    retention.request(101,lease.attempt_id,'remove','remove',item['archive_sha256'])
    original=os.unlink;count=[0]
    def interrupted(*args,**kwargs):
        """Allow one real entry removal and then fail without a recursive cleanup fallback."""
        count[0]+=1
        if count[0]==2:raise PermissionError('Deletion interrupted')
        return original(*args,**kwargs)
    monkeypatch.setattr(retention_files.os,'unlink',interrupted)
    assert retention.execute(101,'remove')['state']=='pending'
    assert retention.list(101)[0]['state']=='removing'
    monkeypatch.setattr(retention_files.os,'unlink',original)
    assert retention.execute(101,'remove')['state']=='completed'
    assert retention.list(101)[0]['state']=='removed'


def test_symlinks_are_archived_as_links_and_never_followed_during_removal(retained,tmp_path):
    """An external link preserves its payload and external bytes even when the original native allocation is removed."""
    s,lease,root,retention=retained
    external=tmp_path/'outside';external.write_text('keep outside')
    (root/'outside-link').symlink_to(external)
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    assert retention.execute(101,'archive')['state']=='completed'
    item=retention.list(101)[0];s.c.now[0]+=86401
    retention.request(101,lease.attempt_id,'remove','remove',item['archive_sha256'])
    assert retention.execute(101,'remove')['state']=='completed'
    assert external.read_text()=='keep outside'


def test_parent_replacement_cannot_redirect_partial_deletion(retained,tmp_path,monkeypatch):
    """An ancestor swapped for an external symlink during deletion stays unresolved and cannot delete outside the private allocation."""
    from contextlib import contextmanager
    from backend.runtime import retention_files
    s,lease,root,retention=retained
    nested=root/'nested';nested.mkdir();(nested/'data.txt').write_text('original nested data')
    outside=tmp_path/'outside';outside.mkdir();(outside/'data.txt').write_text('unrelated outside data')
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    retention.execute(101,'archive');item=retention.list(101)[0];s.c.now[0]+=86401
    retention.request(101,lease.attempt_id,'remove','remove',item['archive_sha256'])
    original=retention_files.parent_handle;changed=[False]
    @contextmanager
    def redirected(held,relative,items,expected):
        """Replace one parent after inventory but before the actual descriptor-pinned deletion."""
        if relative=='repository/nested/data.txt' and not changed[0]:
            parent=Path(held)/'repository'/'nested';parent.rename(parent.with_name('nested-preserved'));parent.symlink_to(outside,target_is_directory=True);changed[0]=True
        with original(held,relative,items,expected) as handle:yield handle
    monkeypatch.setattr(retention_files,'parent_handle',redirected)
    assert retention.execute(101,'remove')['state']=='pending'
    assert changed[0] and (outside/'data.txt').read_text()=='unrelated outside data'


async def test_retention_shutdown_drains_original_copy_and_rejects_new_decisions(retained,monkeypatch):
    """The host controller owns its actual thread through shutdown; cancellation of a waiting HTTP task cannot abandon a filesystem write."""
    import asyncio
    import threading
    from types import SimpleNamespace
    from backend.runtime.retention_service import RetentionService
    from backend.runtime import workspace_retention as module
    s,lease,root,retention=retained
    coordinator=SimpleNamespace(store=s.c.store,control_root=s.control,workspaces=SimpleNamespace(root=s.root),runtime=SimpleNamespace(authority={}),_accepting=lambda **kwargs:None)
    service=RetentionService(coordinator);service.store=retention
    entered=threading.Event();release=threading.Event();original=module.copy_snapshot
    def waiting(*args,**kwargs):
        """Hold a real copy until shutdown has started, then complete that exact original operation."""
        entered.set();assert release.wait(5);return original(*args,**kwargs)
    monkeypatch.setattr(module,'copy_snapshot',waiting)
    await service.submit(101,lease.attempt_id,'archive','archive',retention_days=1,acknowledge_unavailability=True)
    assert await asyncio.to_thread(entered.wait,3)
    closing=asyncio.create_task(service.close());await asyncio.sleep(0)
    try:
        assert not closing.done()
        with pytest.raises(RunConflict,match='cerrando'):
            await service.submit(101,lease.attempt_id,'another','archive',retention_days=1,acknowledge_unavailability=True)
    finally:release.set();await closing
    assert retention.operation(101,'archive')['state']=='completed'


@pytest.mark.parametrize('schema_target', [68])
def test_retention_inverse_refuses_used_history_and_preserves_unused_prefix(retained,tmp_path):
    """Rollback cannot discard quarantine/history; an unused schema68 can return to67 without touching project data."""
    import sqlite3
    from backend.db.workspace_retention_migration import restore_workspace_retention_schema
    from backend.tools.base.db import ensure_migrations
    s,lease,root,retention=retained
    retention.quarantine(101,lease.attempt_id,'archive',retention_days=1,acknowledge_unavailability=True)
    with pytest.raises(RuntimeError,match='history'):restore_workspace_retention_schema(s.c.conn)
    empty=tmp_path/'unused.db';ensure_migrations(empty, target_version=68)
    with sqlite3.connect(empty) as conn:
        restore_workspace_retention_schema(conn)
        assert conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==67
    ensure_migrations(empty, target_version=68)


def test_installation_backup_recovers_archive_data_without_replaying_copied_deletion(installation,service_setup,tmp_path):
    """A relocated full backup retains archive bytes while an old pending delete cannot touch the still-existing original host."""
    import sqlite3
    from dataclasses import replace
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry
    host,_=installation;clock=[1000.0];store=SQLiteRunStore(host/'source.db',clock=lambda:clock[0])
    with sqlite3.connect(host/'source.db') as conn:conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    version=store.context_snapshot(101,1001)['context_version'];binding=WorkspaceRegistry(store.database,host/'sources').bind(101,11)
    run=store.admit(replace(service_setup.c.spec,context_version=version),binding=binding);lease=store.claim(101,run.run_id,'retention-backup-fixture')
    development=host/'control'/'development';development.mkdir(mode=0o700)
    copies=DevelopmentWorkspaces(store,development);planned,_=copies.plan(lease)
    root=Path(planned['allocation'])/'repository';root.mkdir(parents=True,mode=0o700);root.parent.chmod(0o700);root.parent.parent.chmod(0o700)
    git(root,'init','-b','main');(root/'pending.txt').write_text('retained through backup\n');git(root,'add','.');git(root,'commit','-m','base')
    (root/'new.txt').write_text('untracked backup work\n');info=root.stat()
    copies.complete(lease,PreparedDevelopmentWorkspace(11,str(root),info.st_dev,info.st_ino,git(root,'rev-parse','HEAD'),git(root,'rev-parse','HEAD^{tree}')))
    store.finish(lease,native_status='completed',summary='Storage-only closure fixture; actual journal tested separately.')
    retention=WorkspaceRetention(store,host/'control',host/'sources',closed=lambda conn,row:{'synthetic_storage_fixture':True})
    retention.quarantine(101,lease.attempt_id,'archive-backup',retention_days=1,acknowledge_unavailability=True)
    assert retention.execute(101,'archive-backup')['state']=='completed'
    row=retention.list(101)[0];clock[0]+=86401
    retention.request(101,lease.attempt_id,'pending-original-delete','remove',row['archive_sha256'])
    bundle=tmp_path/'bundle';backup_installation(host,bundle)
    relocated=tmp_path/'relocated';restore_installation(bundle,relocated)
    restored_store=SQLiteRunStore(relocated/'source.db',clock=lambda:clock[0])
    restored=WorkspaceRetention(restored_store,relocated/'control',relocated/'sources',closed=lambda conn,row:{'synthetic_storage_fixture':True})
    assert restored.execute(101,'pending-original-delete')['state']=='pending'
    assert (root/'new.txt').read_text()=='untracked backup work\n'
    restored.request(101,lease.attempt_id,'recover-backup-data','restore',row['archive_sha256'])
    result=restored.execute(101,'recover-backup-data');assert result['state']=='completed',result
    destination=Path(result['receipt']['restored_path'])
    assert destination.is_relative_to(relocated/'sources')
    assert (destination/'repository'/'new.txt').read_text()=='untracked backup work\n'

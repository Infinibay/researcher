"""Administrative source operations retain original owner intent without inventing a native task or granting Git from a resource label."""

import json
from pathlib import Path

import pytest

from backend.runtime.contracts import RunConflict


def operations(s):
    """Use this real isolated project store and actual host root; no process, model or remote is created by the storage fixture."""
    from backend.git.source_operations import SourceOperations
    from backend.runtime.workspaces import WorkspaceRegistry

    return SourceOperations(s.c.store, workspaces=WorkspaceRegistry(s.c.database,s.root), control_root=s.control)


def test_original_setup_intent_survives_replay_without_a_fake_task(service_setup):
    """Same original scope yields one operation; changing it cannot reuse that identity or start a second intent."""
    from backend.git.source_operations import SourceRequest

    s=service_setup;records=operations(s);before=s.c.conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    request=SourceRequest(mode='create',name='fresh',path=str(s.root/'fresh'),branch='main')
    first=records.prepare(202,'source-original',request)
    assert records.prepare(202,'source-original',request)==first
    assert first['status']=='planned' and first['repository_id'] is None
    assert not (s.root/'fresh').exists()
    assert s.c.conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]==before
    assert s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0
    with pytest.raises(RunConflict):records.prepare(202,'source-original',SourceRequest(mode='create',name='other',path=str(s.root/'other'),branch='main'))


def test_source_reservations_preserve_existing_and_foreign_directories(service_setup):
    """Creating is not adopting; reservations cannot overlap another project's existing source or another uncompleted setup intent."""
    from backend.git.source_operations import SourceRequest

    s=service_setup;records=operations(s);useful=s.root/'useful';useful.mkdir();(useful/'fact.txt').write_text('137')
    with pytest.raises(RunConflict):records.prepare(202,'must-not-create',SourceRequest(mode='create',name='useful',path=str(useful),branch='main'))
    with pytest.raises(RunConflict):records.prepare(202,'must-not-adopt',SourceRequest(mode='adopt',name='foreign',path=str(s.workspace)))
    records.prepare(101,'reserve-original',SourceRequest(mode='create',name='reserved',path=str(s.root/'reserved'),branch='main'))
    with pytest.raises(RunConflict):records.prepare(202,'foreign-reservation',SourceRequest(mode='create',name='reserved',path=str(s.root/'reserved'),branch='main'))
    assert (useful/'fact.txt').read_text()=='137' and not (useful/'.git').exists()
    assert not (s.root/'reserved').exists()


def test_claim_and_allocation_have_a_real_administrative_identity(service_setup):
    """One live setup owner captures a new private directory and a distinct readonly view without a synthetic native repository binding."""
    from backend.git.source_operations import SourceRequest

    s=service_setup;records=operations(s);records.prepare(202,'owned-local',SourceRequest(mode='create',name='fresh',path=str(s.root/'fresh'),branch='main'))
    lease=records.claim(202,'owned-local','owner-a')
    assert records.claim(202,'owned-local','owner-a')==lease
    with pytest.raises(RunConflict):records.claim(202,'owned-local','owner-b')
    view=records.allocate(lease)
    assert view['allocation']['path']==str(s.root/'fresh')
    assert Path(view['source']['workspace'])!=s.root/'fresh'
    assert Path(view['source']['workspace']).is_dir()
    assert (s.root/'fresh').stat().st_mode&0o077==0
    assert records.allocate(lease)==view
    assert 'repository_id' not in view['source']
    assert records.read(202,'owned-local')['status']=='running'
    assert s.c.conn.execute('SELECT COUNT(*) FROM runtime_attempts').fetchone()[0]==0


def test_adoption_only_captures_existing_directory_and_preserves_other_metadata(service_setup):
    """Adoption does not initialize/configure a source or discard the owner's immutable creation metadata."""
    from backend.git.source_operations import SourceRequest

    s=service_setup;s.c.conn.execute('UPDATE projects SET metadata_json=? WHERE id=202',(json.dumps({'owner_creation':{'operation_key':'original-create','name':'Beta','description':'original'}}),));s.c.conn.commit()
    target=s.root/'adopt';target.mkdir();(target/'fact.txt').write_text('137')
    records=operations(s);records.prepare(202,'adopt-original',SourceRequest(mode='adopt',name='adopt',path=str(target)))
    lease=records.claim(202,'adopt-original','owner-a');view=records.allocate(lease)
    assert view['allocation'] is None and view['source']['workspace']==str(target)
    assert (target/'fact.txt').read_text()=='137' and not (target/'.git').exists()
    metadata=json.loads(s.c.conn.execute('SELECT metadata_json FROM projects WHERE id=202').fetchone()[0])
    assert metadata['owner_creation']['operation_key']=='original-create'


def test_clone_and_remote_creation_do_not_inherit_implicit_effects(service_setup):
    """Remote intent is explicit and credential-free; a clone cannot request a visibility change or use an embedded PAT."""
    from backend.git.source_operations import SourceRequest

    with pytest.raises(ValueError):SourceRequest(mode='clone',name='copy',path='/tmp/copy',remote_url='https://user:secret@example.test/repo.git')
    with pytest.raises(ValueError):SourceRequest(mode='adopt',name='copy',path='/tmp/copy',branch='main')
    with pytest.raises(ValueError):SourceRequest(mode='create',name='copy',path='/tmp/copy',branch='main',remote_url='https://example.test/repo.git')
    s=service_setup;records=operations(s)
    with pytest.raises(RunConflict):records.prepare(202,'remote-original',SourceRequest(mode='create_remote',name='remote',remote_owner='owner',private=True,remote_server='https://forgejo.example/api/v1'))
    remote=records.prepare(202,'remote-original',SourceRequest(mode='create_remote',name='remote',remote_owner='owner',private=True,remote_server='https://forgejo.example/api/v1'),remote_identity='a'*64)
    assert remote['request']['private'] is True and remote['request']['path'] is None
    assert not (s.root/'remote').exists()


async def test_prepared_source_history_blocks_project_deletion_and_plain_registration_bypass(service_setup):
    """An administrative intent retains its recovery identity and partially allocated directory even without native run history."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.git.source_operations import SourceRequest
    from backend.planning.project_workspace import ProjectWorkspace
    from backend.runtime.workspaces import WorkspaceRegistry
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s=service_setup;records=operations(s);target=s.root/'incomplete'
    records.prepare(202,'retain-source-intent',SourceRequest(mode='create',name='incomplete',path=str(target),branch='main'))
    lease=records.claim(202,'retain-source-intent','owner-original');records.allocate(lease)
    workspace=ProjectWorkspace(s.c.store,workspaces=WorkspaceRegistry(s.c.database,s.root),legacy_active=lambda _:False)
    assert workspace.state(202)['history_present']
    with pytest.raises(RunConflict):workspace.register_source(202,name='incomplete',path=str(target))
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    async with app.router.lifespan_context(app),owner_client(app)as owner:
        assert (await owner.delete('/api/projects/202')).status_code==409
    assert target.is_dir() and records.read(202,'retain-source-intent')['status']=='running'

"""Actual administrative Git setup under the existing kernel/global broker; no native task, model or remote effect is created."""

import json
import subprocess
from pathlib import Path

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414
from backend.tests.runtime.test_owned_remote_transport import tls_remote as tls_remote  # noqa: PLC0414


def git(path,*args):
    """Inspect only the test-owned source from the host to independently verify the setup result and preservation."""
    return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,text=True).stdout.strip()


@pytest.mark.timeout(120)
async def test_real_local_create_and_adopt_use_administrative_ownership_without_native_tasks(owned_config):
    """A real initial revision is usable through source admission, exact replay launches nothing, and adoption preserves dirty files/config/origin."""
    from backend.git.source_executor import execute_source
    from backend.git.source_operations import SourceOperations,SourceRequest
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.workspaces import WorkspaceRegistry

    c=owned_config;records=SourceOperations(c.s.c.store,workspaces=WorkspaceRegistry(c.s.c.database,c.s.root),control_root=c.s.control)
    target=c.s.root/'fresh'
    request=SourceRequest(mode='create',name='fresh',path=str(target),branch='main')
    records.prepare(202,'actual-owner-create',request)
    result=await execute_source(records,202,'actual-owner-create',authority=c.settings['authority'],cgroup_parent=c.parent)
    assert result['status']=='completed' and result['repository_id']>0
    assert result['observation']['head_sha']==git(target,'rev-parse','HEAD')
    assert git(target,'ls-tree','-r','HEAD')==''
    binding=records.workspaces.bind(202,result['repository_id']);assert binding.workspace==str(target)
    assert await execute_source(records,202,'actual-owner-create',authority=c.settings['authority'],cgroup_parent=c.parent)==result
    (target/'fact.txt').write_text('137');git(target,'remote','add','origin','https://example.invalid/keep.git')
    config=(target/'.git/config').read_bytes();head=git(target,'rev-parse','HEAD')
    records.prepare(202,'actual-owner-adopt',SourceRequest(mode='adopt',name='fresh',path=str(target)))
    adopted=await execute_source(records,202,'actual-owner-adopt',authority=c.settings['authority'],cgroup_parent=c.parent)
    assert adopted['repository_id']==result['repository_id'] and not adopted['observation']['working_tree_clean']
    assert (target/'fact.txt').read_text()=='137' and (target/'.git/config').read_bytes()==config
    assert git(target,'rev-parse','HEAD')==head and git(target,'remote','get-url','origin')=='https://example.invalid/keep.git'
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0

    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_attempts').fetchone()[0]==0
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]==3
    with WitnessedAuthorityJournal(**c.settings['authority']) as journal:
        snapshot=journal.load()
        assert snapshot.records['broker:active'] is None
        grants=[v for k,v in snapshot.records.items() if k.startswith('broker:grant:')]
        assert len(grants)==2 and all(g['source_kind']=='repository_setup' and g['task_id']is None and g['domain_removed'] for g in grants)
    for op in records.list(202):
        assert op['closure']['domain_removed'] and all(peer['state']=='closed' for peer in op['peers'].values())
        assert 'repository_id' not in op['view']['source']
    assert not list(c.parent.glob('researcher-source-setup-*'))


@pytest.mark.timeout(120)
async def test_git_finished_before_registration_failure_recovers_by_readonly_observation(owned_config,monkeypatch):
    """Losing the DB registration after a real initial commit must not reinitialize, recommit or replace the retained source on repair."""
    from backend.git.source_executor import execute_source,reconcile_source
    from backend.git.source_operations import SourceOperations,SourceRequest
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.workspaces import WorkspaceRegistry

    c=owned_config;records=SourceOperations(c.s.c.store,workspaces=WorkspaceRegistry(c.s.c.database,c.s.root),control_root=c.s.control)
    target=c.s.root/'retained';records.prepare(202,'lost-registration',SourceRequest(mode='create',name='retained',path=str(target),branch='main'))
    original=records.register
    def fail_registration(*_args):
        """Inject the exact crash gap after Git/domain closure but before any resource registration transaction."""
        raise RuntimeError('Controlled registration loss')
    monkeypatch.setattr(records,'register',fail_registration)
    with pytest.raises(RuntimeError,match='Controlled registration loss'):
        await execute_source(records,202,'lost-registration',authority=c.settings['authority'],cgroup_parent=c.parent)
    assert records.read(202,'lost-registration')['status']=='needs_reconciliation'
    head=git(target,'rev-parse','HEAD');config=(target/'.git/config').read_bytes()
    assert c.s.c.conn.execute("SELECT COUNT(*) FROM repositories WHERE project_id=202 AND name='retained'").fetchone()[0]==0
    monkeypatch.setattr(records,'register',original)
    result=await reconcile_source(records,202,'lost-registration',authority=c.settings['authority'],cgroup_parent=c.parent)
    assert result['status']=='completed' and result['observation']['head_sha']==head
    assert git(target,'rev-parse','HEAD')==head and (target/'.git/config').read_bytes()==config
    assert git(target,'rev-list','--count','HEAD')=='1'
    with WitnessedAuthorityJournal(**c.settings['authority'])as journal:
        state=journal.load().records;assert state['broker:active'] is None
        grants={key.removeprefix('broker:grant:'):g for key,g in state.items()if key.startswith('broker:grant:')};assert len(grants)==2
        observed=[op for key,op in state.items()if key.startswith('broker:op:') and op['runtime_manifest']['launch']['observation_only']]
        assert observed and all(op['runtime_manifest']['launch']['stage'] not in ('init','commit','clone','read_index','checkout') for op in observed)
    assert len(records.read(202,'lost-registration')['history'])==1


@pytest.mark.timeout(120)
async def test_actual_https_clone_keeps_configured_credential_outside_source_and_durable_intent(owned_config,tls_remote,tmp_path):
    """An explicitly authenticated fixed clone uses real local TLS/Git reads, never a remote creation/push, and retains one original source after completed retry."""
    from backend.git.source_executor import execute_source
    from backend.git.source_operations import SourceOperations,SourceRequest
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig
    from backend.runtime.workspaces import WorkspaceRegistry

    c=owned_config;seed=tmp_path/'remote-seed';seed.mkdir()
    git(seed,'init','-b','main');(seed/'fact.txt').write_text('137');git(seed,'add','fact.txt')
    git(seed,'-c','user.name=Fixture','-c','user.email=fixture@localhost','-c','core.hooksPath=/dev/null','commit','-m','Remote fixture137')
    git(seed,'push',str(tls_remote.repo),'main')
    remote_head=git(tls_remote.repo,'rev-parse','main')
    network=NativeNetwork.inspect(resolver='/etc/resolv.conf',ca_bundle=tls_remote.cert)
    transport=RemoteTransportConfig(tls_remote.origin+'/api/v1','fixture-user',tls_remote.token_file,network)
    records=SourceOperations(c.s.c.store,workspaces=WorkspaceRegistry(c.s.c.database,c.s.root),control_root=c.s.control)
    target=c.s.root/'copy'
    request=SourceRequest(mode='clone',name='copy',path=str(target),remote_url=tls_remote.origin+'/owner/repo.git',use_configured_auth=True)
    records.prepare(202,'actual-https-clone',request,remote_identity=transport.identity)
    result=await execute_source(records,202,'actual-https-clone',authority=c.settings['authority'],cgroup_parent=c.parent,source_network=network,source_transport=transport)
    assert result['observation']['head_sha']==remote_head and (target/'fact.txt').read_text()=='137'
    assert git(target,'remote','get-url','origin')==request.remote_url
    assert tls_remote.token not in (target/'.git/config').read_text() and tls_remote.token not in json.dumps(records.list(202))
    assert await execute_source(records,202,'actual-https-clone',authority=c.settings['authority'],cgroup_parent=c.parent,source_network=network,source_transport=transport)==result
    assert tls_remote.git_writes==0 and tls_remote.posts==[] and git(tls_remote.repo,'rev-parse','main')==remote_head
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0

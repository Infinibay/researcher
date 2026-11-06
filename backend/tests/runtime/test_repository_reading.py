"""Actual temporary Git readers distinguish immutable source revisions from branch names and failed observations; no model or remote write."""

import subprocess

import pytest
from fastapi import HTTPException

from backend.runtime.development_workspace import git_environment


def git(path, *arguments):
    """Run fixed trusted Git only against this test-owned directory with no inherited credentials or hooks."""
    return subprocess.run(['git','-c','core.hooksPath=/dev/null','-c','user.name=Controlled QA','-c','user.email=qa@localhost',*arguments],cwd=path,env=git_environment(path),check=True,capture_output=True,text=True).stdout.strip()


def test_branch_observation_returns_complete_git_identity(tmp_path):
    """A branch response can pin later tree/blob reads without resolving an abbreviated hash against a changed repository."""
    from backend.api.routes.git import _local_branches

    git(tmp_path,'init','-b','main')
    (tmp_path/'proof.txt').write_text('137')
    git(tmp_path,'add','proof.txt');git(tmp_path,'commit','-m','Original source137')
    head = git(tmp_path,'rev-parse','HEAD')
    assert _local_branches(str(tmp_path))[0].last_commit_sha == head


def test_failed_git_observation_is_not_a_successful_empty_branch_list(tmp_path):
    """Non-Git and unavailable paths produce explicit uncertainty, while a valid unborn repository can genuinely have no branches."""
    from backend.api.routes.git import _local_branches

    for path in (tmp_path,tmp_path/'missing'):
        with pytest.raises(HTTPException) as failure:
            _local_branches(str(path))
        assert failure.value.status_code == 409
    git(tmp_path,'init','-b','main')
    assert _local_branches(str(tmp_path)) == []


def test_non_repository_child_cannot_discover_and_read_its_parent_repository(tmp_path):
    """A registered ordinary folder inside another repository must not borrow that parent's references or disclose its blobs as source data."""
    from backend.api.routes.git import _local_branches, _local_file_content, _local_tree

    git(tmp_path,'init','-b','main');(tmp_path/'parent-private.txt').write_text('parent-only137');git(tmp_path,'add','.');git(tmp_path,'commit','-m','Parent only')
    child=tmp_path/'ordinary-folder';child.mkdir()
    head=git(tmp_path,'rev-parse','HEAD')
    for read in (lambda:_local_branches(str(child)),lambda:_local_tree(str(child),head),lambda:_local_file_content(str(child),'parent-private.txt',head)):
        with pytest.raises(HTTPException) as failure:
            read()
        assert failure.value.status_code==409


@pytest.mark.parametrize('object_format',['sha1','sha256'])
def test_exact_paths_and_git_object_formats_survive_tree_and_blob_reading(tmp_path, object_format):
    """Unicode/newline filenames remain exact data, and either Git object format yields the tree-selected content identity rather than a guessed SHA-1."""
    from backend.api.routes.git import _local_file_content, _local_tree

    git(tmp_path,'init','-b','main',f'--object-format={object_format}')
    path='última\nnota.txt'
    (tmp_path/path).write_text('Una observación con límites.137')
    git(tmp_path,'add','.');git(tmp_path,'commit','-m','Exact path and format')
    head=git(tmp_path,'rev-parse','HEAD')
    tree=_local_tree(str(tmp_path),head)
    assert path in [entry.path for entry in tree]
    blob=_local_file_content(str(tmp_path),path,head)
    assert blob.content=='Una observación con límites.137'
    assert blob.sha==next(entry.sha for entry in tree if entry.path==path)


async def test_owner_reads_original_tree_and_blob_after_branch_advances(service_setup):
    """Actual owner HTTP keeps a complete original snapshot readable when the same source branch later changes; no operation publishes or starts native work."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s=service_setup
    git(s.workspace,'init','-b','main');(s.workspace/'proof.txt').write_text('137');git(s.workspace,'add','.');git(s.workspace,'commit','-m','Original137')
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        response=await owner.get('/api/git/repos/alpha/branches',params={'project_id':101})
        assert response.status_code == 200,response.text
        head=response.json()[0]['last_commit_sha']
        assert head == git(s.workspace,'rev-parse','HEAD')
        (s.workspace/'proof.txt').write_text('200');git(s.workspace,'commit','-am','Later200')
        tree=await owner.get('/api/git/repos/alpha/tree',params={'project_id':101,'ref':head})
        assert tree.status_code == 200,tree.text
        blob=await owner.get('/api/git/repos/alpha/contents',params={'project_id':101,'ref':head,'path':'proof.txt'})
        assert blob.status_code == 200,blob.text
        assert blob.json()['content']=='137'
        assert blob.json()['sha']==next(e['sha'] for e in tree.json() if e['path']=='proof.txt')

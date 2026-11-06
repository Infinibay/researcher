"""Exact historical branch changes are captured by the original preparation port before inference, as data without inherited approval."""

import base64
from dataclasses import replace
from pathlib import Path

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_development_workspace import RealGitExecutor, fixture_git


@pytest.fixture
async def branch_state(service_setup):
    """Create real committed text/binary/mode/link/deletion material and a historical branch record, with no model or native execution proof."""
    from backend.runtime.workspaces import WorkspaceRegistry

    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    await fixture_git(s.workspace, 'init', '-q', '--initial-branch=main')
    await fixture_git(s.workspace, 'config', 'user.name', 'Fixture')
    await fixture_git(s.workspace, 'config', 'user.email', 'fixture@localhost')
    (s.workspace / 'fact.txt').write_text('137\n')
    (s.workspace / 'binary.bin').write_bytes(b'\0base')
    (s.workspace / 'deleted.txt').write_text('old baseline\n')
    await fixture_git(s.workspace, 'add', '.')
    await fixture_git(s.workspace, 'commit', '-qm', 'base')
    base = (await fixture_git(s.workspace, 'rev-parse', 'HEAD')).decode().strip()
    await fixture_git(s.workspace, 'checkout', '-qb', 'retained')
    (s.workspace / 'fact.txt').write_text('999\n')
    (s.workspace / 'binary.bin').write_bytes(b'\0\xffhistorical')
    (s.workspace / 'deleted.txt').unlink()
    (s.workspace / 'run.sh').write_text('echo retained\n')
    (s.workspace / 'run.sh').chmod(0o755)
    (s.workspace / 'link').symlink_to('fact.txt')
    await fixture_git(s.workspace, 'add', '-A')
    await fixture_git(s.workspace, 'commit', '-qm', 'retained material')
    head = (await fixture_git(s.workspace, 'rev-parse', 'HEAD')).decode().strip()
    await fixture_git(s.workspace, 'checkout', '-q', 'main')
    s.c.conn.execute("INSERT INTO branches(id,project_id,task_id,repo_name,branch_name,status,created_by,last_commit_hash) VALUES(71,101,1001,'alpha','retained','active','historical-label',?)", (head,))
    s.c.conn.commit()
    s.c.spec = replace(s.c.spec, context_version=s.c.store.context_snapshot(101, 1001)['context_version'])
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, 11)
    return s, binding, base, head


@pytest.mark.parametrize('branch_id,sha', [(True, 'a'*40), (0, 'a'*40), (71, 'main'), (71, 'A'*40), (71, 'a'*39)])
def test_branch_selection_requires_record_and_full_canonical_commit(branch_id, sha):
    """Owner data must name an actual record and full immutable Git identity, never an abbreviation, option or moving ref."""
    from backend.runtime.branch_inputs import PriorBranchTarget

    with pytest.raises(ValueError):
        PriorBranchTarget(branch_id, sha)


async def test_branch_data_is_owned_preparation_input_and_survives_later_ref_changes(branch_state):
    """A complete binary diff and exact base reach durable frozen input without changing canonical137 or borrowing old approval."""
    from backend.runtime.branch_inputs import BranchInputs, PriorBranchTarget, capture_branch
    from backend.runtime.code_carryover import CodeCarryovers
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.development_workspace import prepare_workspace

    s, binding, base, head = branch_state
    spec = replace(s.c.spec, operation_key='select-old-branch')
    run, admitted = s.c.store.admit_once(spec, binding=binding, prior_code=PriorBranchTarget(71, head))
    assert admitted
    lease = s.c.store.claim(101, run.run_id, 'fixture-owner')
    root = s.control / 'development'
    root.mkdir(mode=0o700, parents=True)
    copies = DevelopmentWorkspaces(s.c.store, root)
    planned, _ = copies.plan(lease)
    selected = BranchInputs(s.c.store).requested(lease)
    with s.c.store._transaction() as conn:
        row = s.c.store._row(conn, 101, run.run_id)
        with pytest.raises(RunConflict, match='captur|prepar'):
            CodeCarryovers.input(conn, row)
    executor = RealGitExecutor()
    Path(planned['allocation']).parent.mkdir(mode=0o700)
    prepared = await prepare_workspace(binding, planned['allocation'], executor=executor)
    packet = await capture_branch(binding, prepared, selected, executor=executor)
    copies.complete(lease, prepared, prior_branch=packet)
    diff = base64.b64decode(packet['snapshot']['diff_base64'])
    assert b'GIT binary patch' in diff and b'new file mode 100755' in diff and b'new file mode 120000' in diff
    assert b'deleted file mode 100644' in diff and b'+999' in diff
    assert packet['snapshot']['candidate']['base_sha'] == base
    assert packet['snapshot']['candidate']['head_sha'] == head
    assert packet['authority'] == 'data_only' and packet['acceptance'] == 'not_granted'
    assert (s.workspace / 'fact.txt').read_text() == '137\n'

    await fixture_git(s.workspace, 'branch', '-f', 'retained', base)
    with s.c.store._transaction() as conn:
        assert CodeCarryovers.input(conn, s.c.store._row(conn, 101, run.run_id)) == packet
    repeated, created = s.c.store.admit_once(spec, binding=binding, prior_code=PriorBranchTarget(71, head))
    assert not created and repeated.run_id == run.run_id


async def test_moving_branch_is_rejected_before_native_input(branch_state):
    """The original selected commit must still be the recorded ref at acquisition; never silently substitute the new tip or start inference."""
    from backend.runtime.branch_inputs import BranchInputs, PriorBranchTarget, capture_branch
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace

    s, binding, base, head = branch_state
    run, _ = s.c.store.admit_once(s.c.spec, binding=binding, prior_code=PriorBranchTarget(71, head))
    lease = s.c.store.claim(101, run.run_id, 'fixture-owner')
    selected = BranchInputs(s.c.store).requested(lease)
    await fixture_git(s.workspace, 'branch', '-f', 'retained', base)
    prepared = PreparedDevelopmentWorkspace(11, '/unused', 1, 1, base, 'a'*40)
    with pytest.raises(RunConflict, match='commit|changed'):
        await capture_branch(binding, prepared, selected, executor=RealGitExecutor())
    assert (s.workspace / 'fact.txt').read_text() == '137\n'


def test_tasks_and_conversation_accept_the_same_exact_branch_selection():
    """The owner HTTP surfaces share one strict branch contract; neither accepts replacement bytes or inherited approval fields."""
    from pydantic import ValidationError

    from backend.api.models.chat import NativeInstruction
    from backend.api.routes.runs import StartRun

    target = {'source_kind': 'legacy_branch', 'branch_id': 71, 'commit_sha': 'a'*40}
    for model, body in [
        (StartRun, {'operation_key': 'select', 'context_version': 1, 'request': 'Adapt the earlier branch', 'repository_id': 11}),
        (NativeInstruction, {'operation_key': 'select', 'context_version': 1, 'task_id': 1001, 'thread_id': 'branch', 'message': 'Adapt the earlier branch', 'repository_id': 11}),
    ]:
        parsed = model.model_validate({**body, 'prior_code': target})
        assert parsed.prior_code.target().commit_sha == 'a'*40
        with pytest.raises(ValidationError):
            model.model_validate({**body, 'prior_code': {**target, 'approved': True}})


async def test_foreign_branch_record_is_not_listed_or_admitted(branch_state):
    """A branch label in a different project cannot select objects from this registered source or create a native run."""
    from backend.runtime.branch_inputs import BranchInputs, PriorBranchTarget
    from backend.runtime.contracts import RunNotFound

    s, binding, _base, head = branch_state
    s.c.conn.execute('UPDATE branches SET project_id=202 WHERE id=71')
    s.c.conn.commit()
    assert BranchInputs(s.c.store).sources(101, 1001) == []
    with pytest.raises(RunNotFound):
        s.c.store.admit_once(s.c.spec, binding=binding, prior_code=PriorBranchTarget(71, head))
    assert s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0


@pytest.mark.parametrize('case', ['reserved', 'oversize', 'unclosed', 'truncated'])
async def test_branch_capture_rejects_unusable_material_and_unconfirmed_io(branch_state, case):
    """Complete branch data cannot hide metadata paths, silently truncate a large diff or treat an unclosed process as evidence."""
    from backend.runtime.branch_inputs import BranchInputs, PriorBranchTarget, capture_branch
    from backend.runtime.development_workspace import GitResult, PreparedDevelopmentWorkspace

    s, binding, base, head = branch_state
    if case in ('reserved', 'oversize'):
        await fixture_git(s.workspace, 'checkout', '-q', 'retained')
        path = s.workspace / ('.worktrees/private.txt' if case == 'reserved' else 'large.txt')
        path.parent.mkdir(exist_ok=True)
        path.write_text('unsafe metadata' if case == 'reserved' else 'x'*400001)
        await fixture_git(s.workspace, 'add', '-A')
        await fixture_git(s.workspace, 'commit', '-qm', 'bounded fixture')
        head = (await fixture_git(s.workspace, 'rev-parse', 'HEAD')).decode().strip()
        await fixture_git(s.workspace, 'checkout', '-q', 'main')
    run, _ = s.c.store.admit_once(s.c.spec, binding=binding, prior_code=PriorBranchTarget(71, head))
    lease = s.c.store.claim(101, run.run_id, 'fixture-owner')
    selected = BranchInputs(s.c.store).requested(lease)
    base_tree = (await fixture_git(s.workspace, 'rev-parse', base+'^{tree}')).decode().strip()
    prepared = PreparedDevelopmentWorkspace(11, '/unused', 1, 1, base, base_tree)
    executor = RealGitExecutor()
    if case in ('unclosed', 'truncated'):
        async def uncertain(*args, **kwargs):
            """Controlled port explicitly lacks the evidence whose absence must prevent model dispatch."""
            return GitResult(b'', 0, case!='truncated', case!='unclosed')
        executor.run = uncertain
    with pytest.raises(RunConflict):
        await capture_branch(binding, prepared, selected, executor=executor)
    assert (s.workspace / 'fact.txt').read_text() == '137\n'
    assert s.c.conn.execute('SELECT COUNT(*) FROM runtime_commands').fetchone()[0] == 1


@pytest.mark.parametrize('case', ['receipt_collision', 'context_change', 'missing_capture'])
async def test_branch_capture_ready_transaction_cannot_overwrite_or_use_stale_authority(branch_state, case):
    """Prepared filesystem data survives a blocked completion, but no ready state/captured input is committed without the original receipt and live context."""
    from backend.runtime.branch_inputs import BranchInputs, PriorBranchTarget, capture_branch
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.development_workspace import prepare_workspace

    s, binding, _base, head = branch_state
    run, _ = s.c.store.admit_once(s.c.spec, binding=binding, prior_code=PriorBranchTarget(71, head))
    lease = s.c.store.claim(101, run.run_id, 'fixture-owner')
    root = s.control / 'development'
    root.mkdir(mode=0o700, parents=True)
    copies = DevelopmentWorkspaces(s.c.store, root)
    planned, _ = copies.plan(lease)
    Path(planned['allocation']).parent.mkdir(mode=0o700)
    executor = RealGitExecutor()
    prepared = await prepare_workspace(binding, planned['allocation'], executor=executor)
    packet = await capture_branch(binding, prepared, BranchInputs(s.c.store).requested(lease), executor=executor)
    if case == 'receipt_collision':
        with s.c.store._transaction(write=True) as conn:
            s.c.store._save_receipt(conn, 101, 1001, 'prior-branch-'+lease.attempt_id, {'kind':'other-original-intent'}, {'preserve':True})
    elif case == 'context_change':
        s.c.store.correct_context(project_id=101, task_id=1001, expected_version=lease.context_version, operation_key='new-context', statement='Inspect the changed units first.', source_kind='user_message', source_reference='owner-correction:new-context')
    with pytest.raises(RunConflict):
        copies.complete(lease, prepared, prior_branch=None if case == 'missing_capture' else packet)
    assert Path(prepared.workspace).is_dir()
    assert s.c.conn.execute('SELECT state FROM runtime_development_workspaces WHERE attempt_id=?', (lease.attempt_id,)).fetchone()[0] != 'ready'
    assert (s.workspace / 'fact.txt').read_text() == '137\n'

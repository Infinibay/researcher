"""Engine acceptance across independent candidates and untrusted completion text, using real Git/SQLite and controlled native responses."""

import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.code_candidate import capture_candidate
from backend.runtime.contracts import RunNotFound
from backend.runtime.development_state import DevelopmentWorkspaces
from backend.runtime.development_workspace import prepare_workspace
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.runtime.workspaces import WorkspaceRegistry
from backend.tests.runtime.test_development_workspace import RealGitExecutor, source_repository
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


async def test_two_real_homonymous_candidates_keep_original_scope_under_reverse_concurrent_reads(coordination, tmp_path):
    """Concurrent actual Git capture plus scoped SQLite reads cannot exchange two authors' value.py; trusted closure proof is synthetic, with physical ownership covered separately."""
    c = coordination
    workspaces = tmp_path/'workspaces'
    workspaces.mkdir()
    control = tmp_path/'control'
    control.mkdir(mode=0o700)
    copies = DevelopmentWorkspaces(c.store, control)
    candidates = CodeCandidates(c.store)
    items = []
    for project_id, task_id, repository_id in ((101,1001,11),(202,2002,22)):
        parent = workspaces/str(project_id)
        parent.mkdir()
        source, _ = source_repository.__wrapped__(parent)
        c.conn.execute('INSERT INTO repositories(id,project_id,name,local_path) VALUES(?,?,?,?)', (repository_id,project_id,'fixture',str(source)))
        c.conn.execute("UPDATE tasks SET type='code' WHERE id=?", (task_id,))
        c.conn.commit()
        binding = WorkspaceRegistry(c.database, workspaces).bind(project_id, repository_id)
        spec = replace(c.spec, project_id=project_id, task_id=task_id, actor_id='author-'+str(project_id), operation_key='candidate-'+str(project_id), context_version=c.store.context_snapshot(project_id,task_id)['context_version'])
        run = c.store.admit(spec, binding=binding)
        assert run.execution_kind == 'development'
        lease = c.store.claim(project_id, run.run_id, 'host-'+str(project_id))
        plan, created = copies.plan(lease)
        assert created
        allocation = Path(plan['allocation'])
        allocation.parent.mkdir(mode=0o700, parents=True)
        prepared = await prepare_workspace(binding, allocation, executor=RealGitExecutor())
        copies.complete(lease, prepared)
        value = project_id + 100
        (Path(prepared.workspace)/'value.py').write_text('VALUE = '+str(value)+'\n')
        capture, created = candidates.plan(lease)
        assert created
        items.append((source, binding, lease, prepared, capture, value))
    results = await asyncio.gather(*(capture_candidate(binding, prepared, plan['allocation'], executor=RealGitExecutor()) for _,binding,_,prepared,plan,_ in items))
    for item, captured in zip(items, results, strict=True):
        source, _, lease, prepared, _, value = item
        proof = {'grant_id':str(lease.project_id).zfill(64),'operations':[{'operation_id':str(lease.task_id).zfill(64),'execution_closed':True}]}
        candidates.complete(lease, captured, proof)
        assert captured.diff_sha256 == hashlib.sha256(captured.diff).hexdigest()
        assert str(value).encode() in captured.diff
        assert '137' in (source/'value.py').read_text()
        (Path(prepared.workspace)/'value.py').write_text('VALUE = 999\n')

    def read(item):
        """Open an independent read connection against the caller's exact project/run, never a global last-result slot."""
        lease = item[2]
        return CodeCandidates(SQLiteRunStore(c.database, clock=lambda:c.now[0])).inspect(lease.project_id,lease.run_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(read, reversed(items)))
    for row, item in zip(rows, reversed(items), strict=True):
        lease, value = item[2], item[5]
        assert row['project_id'] == lease.project_id and row['attempt_id'] == lease.attempt_id
        assert row['run_id'] == lease.run_id and row['owner_id'] == lease.owner_id
        assert str(value).encode() in row['diff'] and b'999' not in row['diff']
        assert (Path(row['workspace'])/'value.py').read_text() == 'VALUE = '+str(value)+'\n'
        with pytest.raises(RunNotFound):
            candidates.inspect(202 if lease.project_id==101 else 101, lease.run_id)
    assert c.conn.execute("SELECT count(*) FROM tasks WHERE status='done'").fetchone()[0] == 0


class TextOnlyOutcome(ControlledInference):
    """Return free-form native completion text without claiming an accepted product result."""

    def __init__(self, setup, text):
        """Retain the chosen untrusted result body while using the real host coordinator contract."""
        super().__init__(setup)
        self.text = text
        self.release.set()

    async def run(self, prompt, **callbacks):
        """Complete the native turn normally so the host must still keep task acceptance separate."""
        return replace(await super().run(prompt, **callbacks), text=self.text)


@pytest.mark.parametrize('text', ['blocked: required evidence is missing', 'exhausted: work limit reached', 'invalid: guardrail could not validate the result'])
async def test_free_form_terminal_text_cannot_complete_or_accept_a_task(service_setup, text):
    """Even completed native transport carrying failure-like text is only a proposal; it cannot imply accepted work or trigger a new attempt."""
    s = service_setup
    native = TextOnlyOutcome(s, text)
    async with coordinator(s, native) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        saved = s.c.store.get(101,run.run_id)
        assert saved.status == 'needs_review' and saved.result['summary'] == text
        assert s.c.store.context_snapshot(101,1001)['task']['status'] == 'in_progress'
        assert len(native.prompts) == 1
        assert s.c.conn.execute('SELECT count(*) FROM runtime_result_acceptances').fetchone()[0] == 0
        assert s.c.conn.execute('SELECT count(*) FROM runtime_attempts').fetchone()[0] == 1

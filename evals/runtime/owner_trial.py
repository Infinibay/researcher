"""Fresh account-free command receipts for owner HTTP and browser evaluations.

Only the closed synthetic source database is copied; live authority, grants and
operator workspaces are never imported from a historical trial.
"""

import hashlib
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

TABLES = (
    "runtime_runs",
    "runtime_attempts",
    "runtime_jobs",
    "runtime_peers",
    "runtime_inference_dispatches",
    "runtime_input_snapshots",
    "tool_grants",
    "research_reports",
    "tasks",
)


def fingerprint(database):
    """Hash retained runtime rows through a read-only connection to detect unintended mutations."""
    result = {}
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    ) as conn:
        for table in TABLES:
            rows = conn.execute("SELECT * FROM " + table + " ORDER BY 1,2").fetchall()
            result[table] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(repr(rows).encode()).hexdigest(),
            }
    return result



@dataclass(frozen=True)
class OwnerTrial:
    """Identify original closed evidence and its independent read-only inspection copy."""

    root: Path
    source_database: Path
    database: Path
    execution: object
    expected_stdout: bytes


async def prepare(root, codex_binary, cgroup_parent):
    """Run one bounded native calculation, close its actors, then copy only fresh diagnostic rows."""
    from backend.runtime.contracts import CommandSpec
    from evals.runtime.kernel_trial import prepare as prepare_kernel

    root = Path(root).absolute()
    root.mkdir(mode=0o700, parents=True)
    execution = prepare_kernel(root / 'execution', codex_binary, cgroup_parent)
    source = execution.workspace / 'facts.txt'
    source.write_text('137\n63\n')
    program = execution.workspace / 'calculate.py'
    program.write_text('"""Compute the sum of synthetic source values without inference."""\n'
        'from pathlib import Path\n'
        'a, b = map(int, Path("facts.txt").read_text().split())\n'
        'print(f"Resultado local: {a} + {b} = {a + b} unidades.")\n'
        'print("Cálculo comprobado sin llamadas a modelos.")\n')
    expected = 'Resultado local: 137 + 63 = 200 unidades.\nCálculo comprobado sin llamadas a modelos.\n'.encode()
    with closing(sqlite3.connect(execution.database)) as db, db:
        db.execute("UPDATE projects SET name='Research ALPHA_ONLY' WHERE id=101")
        db.execute("UPDATE tasks SET title='Policy report',priority=2,description='Synthetic command-only diagnostic; no model result.' WHERE id=1001")
        db.execute("INSERT INTO projects(id,name) VALUES(202,'Research BETA_ONLY')")
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(2002,202,'research','Other project','in_progress')")
    async with execution.open():
        async with execution.commands() as worker:
            job = await (await worker.start(execution.lease, 'owner-inspection', CommandSpec(
                (str(Path(sys.executable).resolve()), '-I', '-S', 'calculate.py'), '.', 5, 4096))).wait()
            assert job.exit_code == 0 and job.stdout == expected and job.stderr == b''
        assert execution.store.get_job(101, job.job_id).local_execution_closed
    assert execution.peers.closed() and not execution.domain_path.exists()
    assert source.read_text() == '137\n63\n'
    database = root / 'research.db'
    with closing(sqlite3.connect(execution.database.as_uri() + '?mode=ro', uri=True)) as origin, closing(sqlite3.connect(database)) as target:
        origin.backup(target)
    assert fingerprint(execution.database) == fingerprint(database)
    return OwnerTrial(root, execution.database, database, execution, expected)

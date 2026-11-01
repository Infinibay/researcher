"""Host tools over real SQLite, owned guards and a subprocess wire peer.

The wire helper executes real children but does not emulate a filesystem sandbox;
native CLI probes separately verify that policy.
"""

import asyncio
import base64
import json
import sys
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_command_executor import claim, executor, wait_file


def envelope(name, **arguments):
    return {"tool": name, "arguments": arguments}


def content(response):
    assert response["success"], response
    return json.loads(response["contentItems"][0]["text"])


def tools(c, workspace, lease, *, active=lambda: True):
    from backend.runtime.analysis_tools import AnalysisTools

    return AnalysisTools(
        journal=c.store,
        lease=lease,
        workspace=workspace,
        executor_factory=lambda: executor(c, workspace, lease),
        python_executable=Path(sys.executable).resolve(),
        active=active,
    )


async def terminal(facade, job_id, **options):
    async with asyncio.timeout(5):
        while True:
            response = await facade.call(
                envelope(
                    "researcher_command_read", job_id=job_id, wait_ms=1000, **options
                )
            )
            result = content(response)
            if result["status"] in ("exited", "unknown"):
                return result


async def test_python_output_has_durable_bytes_and_closure_without_task_acceptance(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="calculate",
                    code="print(137 * .21)",
                )
            )
        )
        result = await terminal(facade, started["job_id"])
        assert result["exit_code"] == 0 and result["local_execution_closed"]
        assert base64.b64decode(result["stdout"]["base64"]) == b"28.77\n"
        assert c.store.get_job(101, started["job_id"]).stdout == b"28.77\n"
        assert c.store.get(101, lease.run_id).status == "running"
        assert (
            c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            != "done"
        )


async def test_reopen_and_same_intent_recovers_receipt_without_another_peer_or_effect(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    arguments = {
        "operation_key": "once",
        "argv": [
            sys.executable,
            "-c",
            "from pathlib import Path; p=Path('count'); p.write_text((p.read_text() if p.exists() else '')+'x')",
        ],
    }
    async with tools(c, tmp_path, lease) as facade:
        first = content(
            await facade.call(envelope("researcher_command_start", **arguments))
        )
        await terminal(facade, first["job_id"])
    async with tools(c, tmp_path, lease) as facade:
        again = content(
            await facade.call(envelope("researcher_command_start", **arguments))
        )
        assert again["job_id"] == first["job_id"] and again["local_execution_closed"]
        changed = await facade.call(
            envelope(
                "researcher_command_start", **{**arguments, "argv": ["/bin/false"]}
            )
        )
        assert not changed["success"]
    assert (tmp_path / "count").read_text() == "x"
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM runtime_peers WHERE kind='command'"
        ).fetchone()[0]
        == 1
    )


async def test_binary_windows_keep_byte_offsets_and_mark_lossy_utf8(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="bytes",
                    code="import sys; sys.stdout.buffer.write(b'\\xffA\\xc3\\xb1Z'); sys.stderr.buffer.write(b'err')",
                )
            )
        )
        result = await terminal(facade, started["job_id"], max_bytes=2)
        assert base64.b64decode(result["stdout"]["base64"]) == b"\xffA"
        assert result["stdout"]["next_offset"] == 2
        assert result["stdout"]["utf8_lossy"] and result["stdout"]["has_more"]
        tail = content(
            await facade.call(
                envelope(
                    "researcher_command_read",
                    job_id=started["job_id"],
                    stdout_offset=2,
                    stderr_offset=3,
                    max_bytes=3,
                )
            )
        )
        assert tail["stdout"]["text"] == "ñZ" and not tail["stdout"]["utf8_lossy"]
        assert tail["stderr"]["base64"] == "" and not tail["stderr"]["has_more"]


async def test_sequential_jobs_release_live_peer_capacity_and_keep_all_receipts(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        for number in range(9):
            started = content(
                await facade.call(
                    envelope(
                        "researcher_python",
                        operation_key=f"sequential-{number}",
                        code=f"print({number})",
                    )
                )
            )
            result = await terminal(facade, started["job_id"])
            assert (
                result["stdout"]["text"] == f"{number}\n"
                and result["local_execution_closed"]
            )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM runtime_jobs WHERE status='exited'"
        ).fetchone()[0]
        == 9
    )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM runtime_peers WHERE kind='command' AND state='closed'"
        ).fetchone()[0]
        == 9
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"argv": ["/bin/true"], "lease": "model authority"},
        {"argv": ["/bin/true"], "env": {"HOME": "/"}},
        {"argv": ["/bin/true"], "cwd": "../"},
        {"argv": ["/bin/true"], "cwd": "/tmp"},
        {"argv": []},
        {"argv": ["/bin/true", "bad\0argument"]},
        {"argv": ["/bin/true"], "timeout_seconds": True},
        {"argv": ["/bin/true"], "output_bytes": 65537},
        {"argv": ["/bin/true"], "timeout_seconds": 301},
    ],
)
async def test_invalid_model_authority_or_limits_never_start_a_peer(
    coordination, tmp_path, arguments
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        response = await facade.call(
            envelope("researcher_command_start", operation_key="invalid", **arguments)
        )
        assert not response["success"]
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM runtime_peers WHERE kind='command'"
        ).fetchone()[0]
        == 0
    )
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0


async def test_cwd_symlink_cannot_escape_the_bound_workspace(coordination, tmp_path):
    c = coordination
    lease = claim(c)
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "outside").symlink_to(tmp_path, target_is_directory=True)
    async with tools(c, workspace, lease) as facade:
        response = await facade.call(
            envelope(
                "researcher_command_start",
                operation_key="escape",
                argv=["/bin/true"],
                cwd="outside",
            )
        )
        assert not response["success"]
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0


async def test_missing_cwd_is_a_tool_refusal_without_starting_a_peer(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        response = await facade.call(
            envelope(
                "researcher_command_start",
                operation_key="missing",
                argv=["/bin/true"],
                cwd="missing",
            )
        )
        assert not response["success"]
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0


@pytest.mark.parametrize(
    "params",
    [
        None,
        [],
        {"tool": []},
        {"tool": {}},
        {"tool": "researcher_python", "arguments": []},
    ],
)
async def test_malformed_envelopes_are_refused_without_work(
    coordination, tmp_path, params
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        assert not (await facade.call(params))["success"]
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0


async def test_scope_exit_closes_an_unread_active_job(coordination, tmp_path):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="unread",
                    code="from pathlib import Path; import time; Path('started').touch(); time.sleep(3); Path('late').touch()",
                )
            )
        )
        await wait_file(tmp_path / "started")
    job = c.store.get_job(101, started["job_id"])
    assert facade.closed and job.local_execution_closed and job.exit_code != 0
    await asyncio.sleep(0.1)
    assert not (tmp_path / "late").exists()


async def test_cancelled_reader_does_not_abandon_peer_scope_cleanup(
    coordination, tmp_path
):
    from backend.runtime.analysis_tools import AnalysisTools

    c = coordination
    lease = claim(c)
    closing, release = asyncio.Event(), asyncio.Event()
    cleanup_completed = []

    @asynccontextmanager
    async def delayed_cleanup():
        async with executor(c, tmp_path, lease) as worker:
            try:
                yield worker
            finally:
                closing.set()
                await release.wait()
                cleanup_completed.append(True)

    async with AnalysisTools(
        journal=c.store,
        lease=lease,
        workspace=tmp_path,
        executor_factory=delayed_cleanup,
        python_executable=Path(sys.executable).resolve(),
    ) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="cleanup",
                    code="import time; time.sleep(.1); print('result')",
                )
            )
        )
        reader = asyncio.create_task(terminal(facade, started["job_id"]))
        try:
            await asyncio.wait_for(closing.wait(), 3)
            reader.cancel()
            with pytest.raises(asyncio.CancelledError):
                await reader
        finally:
            release.set()
    assert cleanup_completed == [True]
    assert c.store.get_job(101, started["job_id"]).local_execution_closed


async def test_stale_attempt_cannot_read_old_output_but_owner_can(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python", operation_key="old", code="print('recorded')"
                )
            )
        )
        await terminal(facade, started["job_id"])
        c.now[0] = lease.expires_at + 1
        denied = await facade.call(
            envelope("researcher_command_read", job_id=started["job_id"])
        )
        assert not denied["success"] and "recorded" not in str(denied)
    assert c.store.get_job(101, started["job_id"]).stdout == b"recorded\n"


async def test_live_flag_is_rechecked_after_waiting_for_a_tool(coordination, tmp_path):
    c = coordination
    lease = claim(c)
    active = [True]
    async with tools(c, tmp_path, lease, active=lambda: active[0]) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="delayed",
                    code="import time; time.sleep(.3); print('secret result')",
                )
            )
        )
        pending = asyncio.create_task(
            facade.call(
                envelope(
                    "researcher_command_read", job_id=started["job_id"], wait_ms=1000
                )
            )
        )
        await asyncio.sleep(0.1)
        active[0] = False
        response = await pending
        assert not response["success"] and "secret result" not in str(response)


async def test_another_attempt_cannot_read_or_cancel_a_job(coordination, tmp_path):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as first:
        started = content(
            await first.call(
                envelope(
                    "researcher_python", operation_key="first", code="print('private')"
                )
            )
        )
        await terminal(first, started["job_id"])
        run = c.store.admit(replace(c.spec, task_id=1002, operation_key="other"))
        from backend.runtime.peer_registry import AttemptPeers

        other, _ = AttemptPeers.claim(
            c.store, 101, run.run_id, "other", lease_seconds=120
        )
        async with tools(c, tmp_path, other) as second:
            for name in ("researcher_command_read", "researcher_command_cancel"):
                response = await second.call(envelope(name, job_id=started["job_id"]))
                assert not response["success"] and "private" not in str(response)


async def test_cancel_retires_owned_children_and_keeps_null_or_actual_exit(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with tools(c, tmp_path, lease) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="cancel",
                    code="from pathlib import Path; import time; Path('started').touch(); time.sleep(5); Path('late').touch()",
                )
            )
        )
        await wait_file(tmp_path / "started")
        result = content(
            await facade.call(
                envelope("researcher_command_cancel", job_id=started["job_id"])
            )
        )
        assert result["local_execution_closed"] and result["exit_code"] != 0
    assert not (tmp_path / "late").exists()
    assert c.store.get_job(101, started["job_id"]).cancel_requested


async def test_completed_parent_read_closes_detached_child_before_return(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    child = "from pathlib import Path; import time; Path('child').touch(); time.sleep(1.5); Path('late').touch()"
    code = (
        "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',"
        + repr(child)
        + "], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True);\n"
        "while not Path('child').exists(): time.sleep(.01)"
    )
    async with tools(c, tmp_path, lease) as facade:
        started = content(
            await facade.call(
                envelope("researcher_python", operation_key="detached", code=code)
            )
        )
        result = await terminal(facade, started["job_id"])
        assert result["exit_code"] == 0 and result["local_execution_closed"]
        await asyncio.sleep(1.6)
        assert not (tmp_path / "late").exists()


async def test_peer_loss_never_replays_or_invents_a_successful_exit(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    from backend.runtime.analysis_tools import AnalysisTools

    opened = []

    @asynccontextmanager
    async def owned():
        async with executor(c, tmp_path, lease) as worker:
            opened.append(worker)
            yield worker

    async with AnalysisTools(
        journal=c.store,
        lease=lease,
        workspace=tmp_path,
        executor_factory=owned,
        python_executable=Path(sys.executable).resolve(),
    ) as facade:
        started = content(
            await facade.call(
                envelope(
                    "researcher_python",
                    operation_key="lost",
                    code="from pathlib import Path; import time; Path('once').touch(); time.sleep(10)",
                )
            )
        )
        await wait_file(tmp_path / "once")
        opened[0].rpc._process.kill()
        async with asyncio.timeout(5):
            while c.store.get_job(101, started["job_id"]).status != "unknown":
                await asyncio.sleep(0.02)
        response = await facade.call(
            envelope("researcher_python", operation_key="lost", code="print('replay')")
        )
        assert not response["success"]
    job = c.store.get_job(101, started["job_id"])
    assert job.exit_code is None and job.local_execution_closed and len(opened) == 1

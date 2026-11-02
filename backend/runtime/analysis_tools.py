"""Lease-bound analysis tools. The host owns every command peer and its policy.

Product callers must supply the read-only native command factory. No credentials,
filesystem grants, interpreter selection or process ownership come from the model.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from backend.runtime.business_mediation import _failure
from backend.runtime.codex_rpc import RpcDisconnected, RpcError
from backend.runtime.command_jobs import CommandNeedsReconciliation
from backend.runtime.command_output import output_window
from backend.runtime.contracts import CommandSpec, RunConflict, RunNotFound


class _Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StartCommand(_Arguments):
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    argv: list[str] = Field(min_length=1, max_length=128)
    cwd: str = Field(default=".", min_length=1, max_length=4096)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    output_bytes: int = Field(default=65536, ge=1, le=65536)


class StartPython(_Arguments):
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    code: str = Field(min_length=1, max_length=16384)
    cwd: str = Field(default=".", min_length=1, max_length=4096)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    output_bytes: int = Field(default=65536, ge=1, le=65536)


class ReadCommand(_Arguments):
    job_id: str = Field(min_length=1, max_length=128)
    stdout_offset: int = Field(default=0, ge=0, le=65536)
    stderr_offset: int = Field(default=0, ge=0, le=65536)
    max_bytes: int = Field(default=8192, ge=1, le=16384)
    wait_ms: int = Field(default=0, ge=0, le=1000)


class CancelCommand(_Arguments):
    job_id: str = Field(min_length=1, max_length=128)


_TOOLS = {
    "researcher_command_start": (
        StartCommand,
        (
            "Start one bounded analysis command (argv, no implicit shell). Workspace is read-only; "
            "network and inherited credentials are unavailable. Returns a durable job ID, not a result. "
            "Preserve operation_key on retries. Read its output before drawing conclusions."
        ),
    ),
    "researcher_python": (
        StartPython,
        (
            "Start Python standard-library analysis using the host-selected isolated interpreter. "
            "Workspace is read-only; no network, credentials, packages or installs. Print needed results; "
            "temporary files are discarded on peer closure. Preserve operation_key and read the returned job."
        ),
    ),
    "researcher_command_read": (
        ReadCommand,
        (
            "Read this attempt's job receipt and byte windows. Canonical output is persisted at termination, "
            "so an active job may have no output yet. Use next_offset/has_more. Base64 is exact; UTF-8 preview "
            "may be lossy. Exit code, physical closure and product acceptance are different facts."
        ),
    ),
    "researcher_command_cancel": (
        CancelCommand,
        (
            "Cancel this attempt's job and close its dedicated peer, including detached children. "
            "A missing exit receipt stays unknown, never success. Cancellation does not accept the task."
        ),
    ),
}


@dataclass
class _Owned:
    scope: object
    worker: object
    handle: object
    cleanup: asyncio.Task | None = None


def _window(data, offset, count):
    return output_window(
        data[offset : offset + count], offset=offset, total_bytes=len(data)
    )


def _receipt(job, *, stdout_offset=0, stderr_offset=0, max_bytes=8192, **_):
    return {
        "job_id": job.job_id,
        "status": job.status,
        "exit_code": job.exit_code,
        "local_execution_closed": job.local_execution_closed,
        "cancel_requested": job.cancel_requested,
        "output_limited": job.output_limited,
        "error": job.error,
        "output_persistence": "terminal_receipt",
        "stdout": _window(job.stdout, stdout_offset, max_bytes),
        "stderr": _window(job.stderr, stderr_offset, max_bytes),
    }


class AnalysisTools:
    """Expose fenced command tools with descriptions matching the actual admitted execution view."""

    def __init__(
        self,
        *,
        journal,
        lease,
        workspace,
        executor_factory,
        python_executable,
        active=lambda: True,
    ):
        """Bind host-selected command ownership and a readonly catalog until the actual view is validated."""
        self.journal, self.lease = journal, lease
        self.workspace = Path(workspace).resolve(strict=True)
        self.python = str(Path(python_executable).resolve(strict=True))
        self._factory, self._active = executor_factory, active
        self._owned = {}
        self._lock = asyncio.Lock()
        self._closing = None
        self._entered = False
        self.closed = False
        self.catalog = [
            {
                "type": "function",
                "name": name,
                "description": description,
                "inputSchema": schema.model_json_schema(),
            }
            for name, (schema, description) in _TOOLS.items()
        ]

    async def __aenter__(self):
        """Validate the current directory and advertise private writes only for a proven development view."""
        if self._entered or not await self._authorized():
            raise RunConflict("Analysis tools require one live attempt scope")
        writable = await asyncio.to_thread(self._writable_view)
        if writable:
            for tool in self.catalog:
                if tool["name"] in ("researcher_command_start", "researcher_python"):
                    tool["description"] = tool["description"].replace(
                        "Workspace is read-only",
                        "This attempt's private workspace is writable; the original repository is not mounted",
                    )
                    tool["description"] += (
                        " Edits remain a private draft and do not accept or publish the task."
                    )
        self._entered = True
        return self

    def _writable_view(self):
        """Check physical dispatch identity in the same authority transaction before describing filesystem access."""
        with self.journal._transaction() as conn:
            row = self.journal._authority(conn, self.lease)
            self.journal._bound_workspace(conn, row, str(self.workspace))
            return row["execution_kind"] == "development"

    async def __aexit__(self, *_):
        await self.aclose()

    async def _authorized(self):
        return (
            self._closing is None
            and self._active()
            and await asyncio.to_thread(self.journal.attempt_active, self.lease)
        )

    async def quiescent(self):
        """Close terminal writers before an index read; an active or uncertain writer keeps the copy unstable."""
        async with self._lock:
            if not await self._authorized():
                return False
            for job_id in tuple(self._owned):
                await self._settle(await self._get(job_id))
            return not self._owned

    async def call(self, params):
        if not self._entered or not await self._authorized():
            return _failure(
                "Attempt authority ended; do not retry effects. Owner recovery can inspect receipts."
            )
        if (
            not isinstance(params, dict)
            or params.get("namespace") is not None
            or not isinstance(params.get("tool"), str)
            or params.get("tool") not in _TOOLS
            or not isinstance(params.get("arguments"), dict)
        ):
            return _failure("Unknown analysis tool or invalid argument envelope")
        name = params["tool"]
        try:
            arguments = _TOOLS[name][0].model_validate(params["arguments"])
            async with self._lock:
                if not await self._authorized():
                    raise RunConflict("Attempt authority ended")
                if isinstance(arguments, (StartCommand, StartPython)):
                    job = await self._start(arguments)
                else:
                    job = await self._read(arguments)
                result = _receipt(
                    job,
                    **(
                        arguments.model_dump()
                        if isinstance(arguments, ReadCommand)
                        else {}
                    ),
                )
            if not await self._authorized():
                return _failure(
                    "Attempt ended while the tool ran; recover its durable receipt without replay."
                )
            return {
                "success": True,
                "contentItems": [
                    {
                        "type": "inputText",
                        "text": json.dumps(result, ensure_ascii=False),
                    }
                ],
            }
        except (
            ValueError,
            OSError,
            RunConflict,
            RunNotFound,
            RpcDisconnected,
            RpcError,
            CommandNeedsReconciliation,
        ) as exc:
            # Native/validation exceptions can contain private paths or supplied
            # values. Return a stable class, not their raw messages/tracebacks.
            return _failure(
                f"Analysis tool refused or requires reconciliation ({type(exc).__name__}). "
                "Keep the original operation key; inspect its receipt before retrying."
            )

    async def _start(self, args):
        argv = (
            tuple(args.argv)
            if isinstance(args, StartCommand)
            else (self.python, "-I", "-S", "-B", "-c", args.code)
        )
        spec = CommandSpec(argv, args.cwd, args.timeout_seconds, args.output_bytes)
        cwd = (self.workspace / spec.cwd).resolve(strict=True)
        if not cwd.is_dir() or not cwd.is_relative_to(self.workspace):
            raise ValueError("Command cwd must stay inside its workspace")
        existing = await asyncio.to_thread(
            self.journal.command_receipt,
            self.lease,
            operation_key=args.operation_key,
            spec=spec,
            workspace=str(self.workspace),
        )
        if existing is not None:
            if existing.job_id in self._owned:
                return await self._settle(existing)
            if existing.status != "exited" or not existing.local_execution_closed:
                raise CommandNeedsReconciliation("Prior connection was not replayed")
            return existing
        # Reap terminal peers before admitting another operation, including any
        # detached children whose parent returned a known exit code.
        for job_id in tuple(self._owned):
            await self._settle(await self._get(job_id))
        if self._owned:
            raise RunConflict("Read or cancel the active job before starting another")
        scope = self._factory()
        worker = await scope.__aenter__()
        try:
            if not await self._authorized():
                raise RunConflict("Attempt ended before command admission")
            handle = await worker.start(self.lease, args.operation_key, spec)
        except BaseException:
            await asyncio.shield(scope.__aexit__(None, None, None))
            raise
        self._owned[handle.job_id] = _Owned(scope, worker, handle)
        return await self._settle(await self._get(handle.job_id))

    async def _get(self, job_id):
        job = await asyncio.to_thread(
            self.journal.get_job, self.lease.project_id, job_id
        )
        if job.run_id != self.lease.run_id or job.attempt_id != self.lease.attempt_id:
            raise RunNotFound("Job does not belong to this attempt")
        return job

    async def _settle(self, job):
        if job.status in ("exited", "unknown") and job.job_id in self._owned:
            await self._close_owned(job.job_id)
            job = await self._get(job.job_id)
        return job

    async def _read(self, args):
        job = await self._get(args.job_id)
        owned = self._owned.get(job.job_id)
        if isinstance(args, CancelCommand):
            if owned is not None:
                await owned.worker.cancel(job.job_id)
                await self._close_owned(job.job_id)
                job = await self._get(job.job_id)
            elif job.status != "exited" or not job.local_execution_closed:
                raise CommandNeedsReconciliation(
                    "Recover the original peer; do not replay"
                )
        elif owned is not None and args.wait_ms:
            try:
                async with asyncio.timeout(args.wait_ms / 1000):
                    job = await owned.handle.wait()
            except TimeoutError:
                job = await self._get(job.job_id)
        return await self._settle(job)

    async def _close_owned(self, job_id):
        owned = self._owned[job_id]
        if owned.cleanup is None:
            owned.cleanup = asyncio.create_task(owned.scope.__aexit__(None, None, None))
        # A cancelled tool reader cannot interrupt the resource owner's cleanup
        # or re-enter its context manager. Shutdown joins the same task.
        await asyncio.shield(owned.cleanup)
        del self._owned[job_id]

    async def aclose(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._closing)

    async def _shutdown(self):
        # Stop physical work before waiting on a reader or a database writer.
        await asyncio.gather(
            *(owned.worker.aclose() for owned in tuple(self._owned.values()))
        )
        async with self._lock:
            for job_id in tuple(self._owned):
                await self._close_owned(job_id)
        self.closed = True

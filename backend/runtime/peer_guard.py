"""Trusted host launcher: bind init identity durably before releasing exec.

Both RPC and SDK stdio can launch this program without a second wire protocol.
The payload never sees the DB path, registry arguments or a host control token.
"""

import argparse
import asyncio
import ctypes
import json
import os
import shutil
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.runtime.contracts import WorkspaceChanged
from backend.runtime.peer_process import NamespaceIdentity, close_namespace, start_ticks
from backend.runtime.peer_registry import PeerRegistry
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.runtime.workspaces import PEER_WORKSPACE


async def _info(fd):
    """Read a bounded namespace identity JSON record within five seconds and always close its pipe transport."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=4096)
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), os.fdopen(fd, "rb", buffering=0)
    )
    try:
        raw = b""
        async with asyncio.timeout(5):
            while len(raw) < 4096:
                chunk = await reader.read(4096 - len(raw))
                if not chunk:
                    raise RuntimeError(
                        "Namespace exited before its identity was available"
                    )
                raw += chunk
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    continue
            raise RuntimeError("Invalid namespace identity record")
    finally:
        transport.close()


async def _forward(writer):
    """Forward owner stdin with backpressure to the gated peer and close both transports on completion."""
    reader = asyncio.StreamReader(limit=65536)
    transport, _ = await asyncio.get_running_loop().connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer
    )
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        writer.close()
        transport.close()


def _pinned_host_view(source_fd):
    """Keep the supervisor's host view but own the source mount destination.

    Rebinding /run's direct entries preserves runtime sockets/control paths.
    The source lives beside those mounts in a private parent; no enumeration of
    arbitrary workspace ancestors or thousands of temporary files is needed.
    Inner native/worker sandboxes still own filesystem and network permissions.
    """
    command = ["--bind", "/", "/", "--tmpfs", "/run"]
    for sibling in sorted(Path("/run").iterdir()):
        if sibling == PEER_WORKSPACE:
            continue
        if sibling.is_symlink():
            command += ["--symlink", os.readlink(sibling), str(sibling)]
        else:
            command += ["--bind", str(sibling), str(sibling)]
    return [*command, "--bind-fd", str(source_fd), str(PEER_WORKSPACE)]


async def run(args):
    """Bind the prepared peer to its actual namespace before releasing exec, then own forwarding and physical cleanup."""
    registry = PeerRegistry(SQLiteRunStore(Path(args.database).resolve(strict=True)))
    peer = await asyncio.to_thread(registry.inspect, args.peer_id)
    if peer["state"] != "prepared":
        return 125
    # Linux clears PDEATHSIG in children, so bwrap also sets its own policy.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Unable to bind launcher to parent lifetime")
    if (
        os.getppid() != peer["owner_pid"]
        or start_ticks(os.getppid()) != peer["owner_start_ticks"]
    ):
        return 125
    binary = shutil.which("bwrap")
    if binary is None:
        raise RuntimeError("Owned PID namespaces require bubblewrap")
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    read_fd, write_fd = os.pipe()
    process = identity = forwarding = exited = stopping = source_fd = None
    try:
        mounts = ["--bind", "/", "/"]
        binding = await asyncio.to_thread(registry.workspace_binding, args.peer_id)
        if binding is not None:
            # Bind the admitted directory object, not a path that can select a
            # replacement between validation, kernel mount and later commands.
            # This owns source identity only; the inner native/worker policy
            # still owns read/write, credentials and network confinement.
            source_fd = os.open(
                binding.workspace,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            opened = os.fstat(source_fd)
            if (opened.st_dev, opened.st_ino) != (binding.device, binding.inode):
                raise WorkspaceChanged("Admitted directory changed before peer startup")
            mounts = _pinned_host_view(source_fd)
        process = await asyncio.create_subprocess_exec(
            binary,
            "--unshare-pid",
            "--die-with-parent",
            *mounts,
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--info-fd",
            str(write_fd),
            "--",
            sys.executable,
            "-I",
            "-S",
            str(Path(__file__).with_name("peer_payload.py")),
            *args.command,
            stdin=asyncio.subprocess.PIPE,
            pass_fds=(write_fd,) if source_fd is None else (write_fd, source_fd),
        )
        os.close(write_fd)
        write_fd = None
        info_fd, read_fd = read_fd, None  # _info takes ownership, including errors
        info = await _info(info_fd)
        pid = info.get("child-pid")
        if type(pid) is not int or pid <= 1:
            raise RuntimeError("Missing namespace init identity")
        async with asyncio.timeout(2):
            while True:
                try:
                    candidate = NamespaceIdentity.capture(
                        pid, expected_parent=process.pid
                    )
                    if candidate.init_namespace != info.get("pid-namespace"):
                        raise RuntimeError(
                            "Namespace differs from the trusted launcher record"
                        )
                    identity = candidate
                    break
                except (OSError, RuntimeError):
                    await asyncio.sleep(0.01)
        await asyncio.to_thread(registry.bind, args.peer_id, identity)
        if stopped.is_set():
            return 125
        process.stdin.write(b"G")
        await process.stdin.drain()
        forwarding = asyncio.create_task(_forward(process.stdin))
        exited = asyncio.create_task(process.wait())
        stopping = asyncio.create_task(stopped.wait())
        await asyncio.wait((exited, stopping), return_when=asyncio.FIRST_COMPLETED)
        if not exited.done():
            await asyncio.to_thread(close_namespace, identity)
        return await process.wait()
    finally:
        if forwarding is not None:
            forwarding.cancel()
            await asyncio.gather(forwarding, return_exceptions=True)
        for task in (stopping, exited):
            if task is not None and not task.done():
                task.cancel()
        if identity is not None:
            await asyncio.to_thread(close_namespace, identity)
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            if process.returncode is None:
                process.kill()
            await process.wait()
        for fd in (read_fd, write_fd, source_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        await asyncio.to_thread(registry.close, args.peer_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--peer-id", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    if arguments.command[:1] == ["--"]:
        arguments.command = arguments.command[1:]
    if not arguments.command:
        parser.error("A gated payload command is required")
    try:
        sys.exit(asyncio.run(run(arguments)))
    except Exception as exc:  # noqa: BLE001 — process boundary; redact sensitive diagnostics
        # Never print configuration/credentials/paths or untrusted payload errors.
        print("Owned peer stopped (" + type(exc).__name__ + ")", file=sys.stderr)
        sys.exit(125)

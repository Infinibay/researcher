"""Concrete no-network stdlib analysis capsule. Not the native inference profile."""

import errno
import os
import platform
import shutil
import struct
import sys
from contextlib import ExitStack
from pathlib import Path

from backend.runtime import _domain_spawn
from backend.runtime.contracts import WorkspaceChanged
from backend.runtime.workspaces import PEER_WORKSPACE


def _no_sockets():
    if platform.machine() != "x86_64":
        raise RuntimeError("Analysis seccomp profile requires verified x86_64 ABI")
    deny = 0x00050000 | errno.EPERM
    # x86_64 only; reject alternate ABIs and kernel namespace/control interfaces.
    instructions = [
        (0x20, 0, 0, 4),
        (0x15, 1, 0, 0xC000003E),
        (0x06, 0, 0, 0x80000000),
        (0x20, 0, 0, 0),
        (0x35, 0, 1, 0x40000000),
        (0x06, 0, 0, deny),
    ]
    for number in (
        41,
        53,
        101,
        155,
        161,
        165,
        166,
        272,
        298,
        304,
        308,
        321,
        428,
        429,
        430,
        431,
        432,
        433,
        442,
    ):
        instructions += [(0x15, 0, 1, number), (0x06, 0, 0, deny)]
    # libc may fall back to ordinary fork/clone after ENOSYS. Every descendant
    # still inherits this filter and its cgroup; it cannot request new namespaces.
    instructions += [
        (0x15, 0, 1, 435),
        (0x06, 0, 0, 0x00050000 | errno.ENOSYS),
        (0x15, 1, 0, 56),
        (0x06, 0, 0, 0x7FFF0000),
        (0x20, 0, 0, 20),
        (0x15, 1, 0, 0),
        (0x06, 0, 0, deny),
        (0x20, 0, 0, 16),
        (0x45, 0, 1, 0x7E020000),
        (0x06, 0, 0, deny),
        (0x06, 0, 0, 0x7FFF0000),
    ]
    return b"".join(struct.pack("=HBBI", *instruction) for instruction in instructions)


class AnalysisCapsule:
    """Own pinned input/assets through spawn; never mounts broker control or home."""

    def __init__(self, binding, code, info_fd):
        self.binding, self.code, self.info_fd = binding, code, info_fd
        self._stack = ExitStack()

    def __enter__(self):
        try:
            source = os.open(
                self.binding.workspace,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            self._stack.callback(os.close, source)
            info = os.fstat(source)
            if (info.st_dev, info.st_ino) != (self.binding.device, self.binding.inode):
                raise WorkspaceChanged("Source changed before broker capsule")
            gate = _domain_spawn.sealed(
                Path(__file__).with_name("peer_payload.py").read_bytes()
            )
            self._stack.callback(os.close, gate)
            seccomp = _domain_spawn.sealed(_no_sockets())
            self._stack.callback(os.close, seccomp)
            binary = shutil.which("bwrap")
            if binary is None:
                raise RuntimeError("Broker capsule requires bubblewrap")
            args = [
                binary,
                "--unshare-all",
                "--die-with-parent",
                "--cap-drop",
                "ALL",
                "--ro-bind",
                "/usr",
                "/usr",
            ]
            for path in (Path("/lib"), Path("/lib64")):
                if path.is_symlink():
                    args += ["--symlink", os.readlink(path), str(path)]
                elif path.exists():
                    args += ["--ro-bind", str(path), str(path)]
            runtime = Path(sys.base_prefix).resolve(strict=True)
            if not runtime.is_relative_to("/usr"):
                args += ["--ro-bind", str(runtime), str(runtime)]
            cache = Path("/etc/ld.so.cache")
            if cache.exists():
                args += ["--ro-bind", str(cache), str(cache)]
            args += [
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--tmpfs",
                "/run",
                "--dir",
                "/home/actor",
                "--dir",
                "/run/researcher-host",
                "--ro-bind-fd",
                str(source),
                str(PEER_WORKSPACE),
                "--ro-bind-data",
                str(gate),
                "/run/researcher-host/gate.py",
                "--chdir",
                str(PEER_WORKSPACE),
                "--info-fd",
                str(self.info_fd),
                "--seccomp",
                str(seccomp),
                "--",
                str(Path(sys.executable).resolve(strict=True)),
                "-I",
                "-S",
                "/run/researcher-host/gate.py",
                str(Path(sys.executable).resolve(strict=True)),
                "-I",
                "-S",
                "-c",
                self.code,
            ]
            self.argv = args
            self.env = {
                "LANG": "C.UTF-8",
                "HOME": "/home/actor",
                "TMPDIR": "/tmp",
                "PATH": "/usr/bin",
            }
            self.pass_fds = (source, gate, seccomp, self.info_fd)
            return self
        except BaseException:
            self._stack.close()
            raise

    def __exit__(self, *_):
        self._stack.close()

"""Concrete readonly analysis and credential-free native transport capsules."""

import errno
import hashlib
import os
import platform
import shutil
import stat
import struct
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from backend.runtime import _domain_spawn
from backend.runtime.contracts import WorkspaceChanged
from backend.runtime.workspaces import PEER_WORKSPACE


def _no_sockets():
    return _syscall_filter(network=False)


def _syscall_filter(*, network):
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
    if network:
        # Only Internet-client socket families. Named/abstract Unix sockets and
        # netlink/packet controls are unavailable; private socketpair remains OK.
        instructions += [
            (0x15, 0, 5, 41),
            (0x20, 0, 0, 16),
            (0x15, 2, 0, 2),
            (0x15, 1, 0, 10),
            (0x06, 0, 0, deny),
            (0x06, 0, 0, 0x7FFF0000),
        ]
    denied = (
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
    )
    if network:
        denied += (43, 49, 50, 288)  # accept/bind/listen/accept4, not client connect
    for number in (() if network else (41, 53)) + denied:
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

    def _program(self):
        return [
            str(Path(sys.executable).resolve(strict=True)),
            "-I",
            "-S",
            "-c",
            self.code,
        ]

    def _mounts(self):
        return []

    def _network(self):
        return []

    def _filter(self):
        return _no_sockets()

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
            seccomp = _domain_spawn.sealed(self._filter())
            self._stack.callback(os.close, seccomp)
            program = self._program()
            binary = shutil.which("bwrap")
            if binary is None:
                raise RuntimeError("Broker capsule requires bubblewrap")
            args = [
                binary,
                "--unshare-all",
                *self._network(),
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
                *self._mounts(),
                "--",
                str(Path(sys.executable).resolve(strict=True)),
                "-I",
                "-S",
                "/run/researcher-host/gate.py",
                *program,
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


@dataclass(frozen=True)
class CodexAsset:
    """An explicit host-selected file identity and content, never an authority."""

    path: str
    device: int
    inode: int
    size: int
    modified: int
    changed: int
    sha256: str

    @classmethod
    def _read(cls, fd, path):
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid not in (0, os.getuid())
            or before.st_mode & 0o022
            or not before.st_mode & 0o111
            or not 0 < before.st_size <= 512 * 1024**2
        ):
            raise ValueError("Native asset must be a bounded trusted executable")
        digest = hashlib.sha256()
        os.lseek(fd, 0, os.SEEK_SET)
        remaining = before.st_size
        while remaining:
            block = os.read(fd, min(1024 * 1024, remaining))
            if not block:
                raise ValueError("Native asset changed while reading")
            digest.update(block)
            remaining -= len(block)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, key) != getattr(after, key) for key in fields):
            raise ValueError("Native asset changed while reading")
        return cls(
            str(path),
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            digest.hexdigest(),
        )

    @classmethod
    def inspect(cls, path):
        path = Path(path).resolve(strict=True)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            return cls._read(fd, path)
        finally:
            os.close(fd)


class NativeCapsule(AnalysisCapsule):
    """Distinct native App Server transport profile; no credential mounts.

    Host networking is available to the trusted client; namespace/control calls
    remain denied. Ken/code-mode/full inference integration is not admitted here.
    """

    def __init__(self, binding, asset, info_fd, *, network=None):
        super().__init__(binding, None, info_fd)
        self.asset = asset
        self.network_config = network
        self._network_fds = {}
        self._asset_fd = None

    def _program(self):
        path = Path(self.asset.path)
        if path.is_relative_to(self.binding.workspace):
            raise ValueError("Native asset cannot belong to the source workspace")
        self._asset_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self._stack.callback(os.close, self._asset_fd)
        if CodexAsset._read(self._asset_fd, path) != self.asset:
            raise ValueError("Native asset no longer matches its manifest")
        command = [
            "/run/researcher-runtime/codex",
            "app-server",
            "--stdio",
            "--strict-config",
        ]
        for feature in (
            "plugins",
            "apps",
            "shell_tool",
            "unified_exec",
            "multi_agent",
            "hooks",
            "memories",
            "code_mode",
            "code_mode_host",
            "daemon_auto_start",
            "skill_search",
            "shell_snapshot",
        ):
            command += ["--disable", feature]
        command += [
            "-c",
            'forced_login_method="chatgpt"',
            "-c",
            'model_provider="openai"',
            "-c",
            "project_doc_max_bytes=0",
            "-c",
            'web_search="disabled"',
            "-c",
            'projects={"/run/researcher-source"={trust_level="untrusted"}}',
        ]
        return command

    def _mounts(self):
        mounts = [
            "--dir",
            "/home/actor/.codex",
            "--dir",
            "/run/researcher-runtime",
            "--ro-bind-fd",
            str(self._asset_fd),
            "/run/researcher-runtime/codex",
        ]
        if self.network_config is not None:
            for item in (self.network_config.resolver, self.network_config.ca_bundle):
                if Path(item.path).is_relative_to(self.binding.workspace):
                    raise ValueError(
                        "Native network input cannot belong to the source workspace"
                    )
            self._network_fds = self._stack.enter_context(self.network_config.opened())
            mounts += [
                "--dir",
                "/run/researcher-network",
                "--ro-bind-data",
                str(self._network_fds["resolver"]),
                "/etc/resolv.conf",
                "--ro-bind-data",
                str(self._network_fds["ca_bundle"]),
                "/run/researcher-network/ca.pem",
            ]
        return mounts

    def _network(self):
        return ["--share-net"]

    def _filter(self):
        return _syscall_filter(network=True)

    def __enter__(self):
        super().__enter__()
        self.env.update(
            CODEX_HOME="/home/actor/.codex",
            TOKIO_WORKER_THREADS="4",
            RAYON_NUM_THREADS="2",
        )
        self.pass_fds += (self._asset_fd,)
        if self.network_config is not None:
            self.env.update(
                CODEX_CA_CERTIFICATE="/run/researcher-network/ca.pem",
                SSL_CERT_FILE="/run/researcher-network/ca.pem",
            )
            self.pass_fds += tuple(self._network_fds.values())
        return self

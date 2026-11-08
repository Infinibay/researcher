"""Explicit public resolver/trust inputs, copied into sealed native mounts.

These assets make DNS/TLS usable; they do not restrict destinations or authorize
credentials. The host selects them outside source workspaces, never from a model.
"""

import hashlib
import ipaddress
import os
import re
import ssl
import stat
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from backend.runtime import _domain_spawn


def _validate(data, kind):
    """Validate numeric resolver directives or a parseable public-certificate PEM bundle; these inputs
    enable DNS/TLS and do not restrict destinations.
    """
    value = data.decode("utf-8")
    if kind == "resolver":
        nameservers = 0
        for line in value.splitlines():
            parts = line.split("#", 1)[0].split(";", 1)[0].split()
            if not parts:
                continue
            if parts[0] == "nameserver" and len(parts) == 2:
                ipaddress.ip_address(parts[1])
                nameservers += 1
            elif (
                parts[0] in {"options", "search", "domain", "sortlist"}
                and len(parts) > 1
            ):
                if any(
                    re.fullmatch(r"[A-Za-z0-9_.:/%+-]+", p) is None for p in parts[1:]
                ):
                    raise ValueError("Unsupported resolver directive")
            else:
                raise ValueError("Unsupported resolver directive")
        if not 1 <= nameservers <= 3:
            raise ValueError("Bounded numeric nameservers required")
    elif kind == "ca_bundle":
        # No private keys, arbitrary auxiliary blobs or executable directives.
        # Common system bundles include explanatory comment lines.
        lines, inside, count = [], False, 0
        for raw in value.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line == "-----BEGIN CERTIFICATE-----" and not inside:
                inside = True
            elif line == "-----END CERTIFICATE-----" and inside:
                inside = False
                count += 1
            elif not inside or re.fullmatch(r"[A-Za-z0-9+/=]+", line) is None:
                raise ValueError("Public PEM certificates required")
            lines.append(line)
        if inside or not count:
            raise ValueError("Public PEM certificates required")
        ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_verify_locations(
            cadata="\n".join(lines)
        )
    else:
        raise ValueError("Unknown native network input")


@dataclass(frozen=True)
class PublicNetworkFile:
    """Fingerprint one host-selected public resolver or CA asset by path, physical identity and exact
    content for later sealed mounting.
    """
    path: str
    kind: str
    device: int
    inode: int
    size: int
    modified: int
    changed: int
    sha256: str

    @classmethod
    def _read(cls, fd, path, kind):
        """Read and validate a trusted bounded regular file while checking descriptor metadata and path
        identity, returning its manifest and exact bytes.
        """
        maximum = {"resolver": 65536, "ca_bundle": 4 * 1024**2}[kind]
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid not in (0, os.getuid())
            or before.st_mode & 0o022
            or not 0 < before.st_size <= maximum
        ):
            raise ValueError("Native network input is unsafe or unbounded")
        data = bytearray()
        while len(data) <= maximum:
            block = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not block:
                break
            data.extend(block)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        path_info = Path(path).lstat()
        if (
            len(data) != before.st_size
            or any(getattr(before, key) != getattr(after, key) for key in fields)
            or (path_info.st_dev, path_info.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise ValueError("Native network input changed during read")
        data = bytes(data)
        _validate(data, kind)
        return cls(
            str(path),
            kind,
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            hashlib.sha256(data).hexdigest(),
        ), data

    @classmethod
    def inspect(cls, path, kind):
        """Inspect a selected existing resolver or CA file without retaining its descriptor, sanitizing
        unavailable or invalid source errors.
        """
        try:
            path = Path(path).resolve(strict=True)
            fd = os.open(
                path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            )
            try:
                return cls._read(fd, path, kind)[0]
            finally:
                os.close(fd)
        except (OSError, ValueError, KeyError):
            raise ValueError("Native network input is unavailable or invalid") from None


@dataclass(frozen=True)
class NativeNetwork:
    """Pair explicitly inspected resolver and public CA manifests; the pair supplies network inputs
    rather than credentials or destination authority.
    """
    resolver: PublicNetworkFile
    ca_bundle: PublicNetworkFile

    @classmethod
    def inspect(cls, *, resolver, ca_bundle):
        """Inspect both host-selected public network assets without opening a network connection or
        creating native state.
        """
        return cls(
            PublicNetworkFile.inspect(resolver, "resolver"),
            PublicNetworkFile.inspect(ca_bundle, "ca_bundle"),
        )

    @contextmanager
    def opened(self):
        """Revalidate then seal exact bytes; source changes cannot alter mounts."""
        with ExitStack() as stack:
            result = {}
            try:
                for kind in ("resolver", "ca_bundle"):
                    item = getattr(self, kind)
                    fd = os.open(
                        item.path,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                    )
                    stack.callback(os.close, fd)
                    actual, data = PublicNetworkFile._read(fd, item.path, kind)
                    if actual != item:
                        raise ValueError("Native network input no longer matches")
                    sealed = _domain_spawn.sealed(data)
                    stack.callback(os.close, sealed)
                    result[kind] = sealed
            except (OSError, ValueError, KeyError):
                raise ValueError(
                    "Native network inputs changed or became invalid"
                ) from None
            yield result

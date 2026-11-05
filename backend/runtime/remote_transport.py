"""Operator-only HTTPS credential/trust configuration, never a model-visible launch credential or repository setting."""

import hashlib
import json
import os
import ssl
import stat
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.native_network import NativeNetwork
from backend.runtime.remote_publication import RemoteRepository


@dataclass(frozen=True)
class RemoteTransportConfig:
    """One configured HTTPS origin and private host PAT file; individual accepted repositories remain separately bound by runtime admission."""

    api_base: str
    username: str
    token_file: Path
    network: NativeNetwork

    def __post_init__(self):
        """Reject ambiguous host identity and credential sources before exposing remote capability."""
        RemoteRepository(
            self.api_base,
            1,
            "validation/repository",
            self.api_base[: -len("/api/v1")] + "/validation/repository.git",
        )
        if (
            not isinstance(self.username, str)
            or not 1 <= len(self.username) <= 128
            or any(ord(c) < 33 or ord(c) > 126 or c == ":" for c in self.username)
        ):
            raise ValueError("Configured Forgejo username is invalid")
        object.__setattr__(self, "token_file", Path(self.token_file).absolute())
        if not isinstance(self.network, NativeNetwork):
            raise TypeError("Inspected remote TLS/resolver inputs required")

    def token(self):
        """Read only an ordinary private operator-owned bounded PAT file; no error includes its contents."""
        try:
            fd = os.open(self.token_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                    or not 0 < info.st_size <= 4096
                ):
                    raise ValueError
                value = os.read(fd, 4097).decode("ascii").strip()
                if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
                    raise ValueError
                return value
            finally:
                os.close(fd)
        except (OSError, ValueError, UnicodeError):
            raise ValueError(
                "Configured remote credential is unavailable or unsafe"
            ) from None

    def public_manifest(self):
        """Describe credential origin/configuration without serializing the PAT or its hash into durable execution evidence."""
        from dataclasses import asdict

        return {
            "api_base": self.api_base,
            "username": self.username,
            "credential_ref": str(self.token_file),
            "network": asdict(self.network),
        }

    @property
    def identity(self):
        """Bind each fixed Git launch to the original operator configuration, independently of secret rotation."""
        return hashlib.sha256(
            json.dumps(
                self.public_manifest(), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()

    def ssl_context(self):
        """Load only revalidated sealed public CA bytes while retaining ordinary TLS certificate and hostname verification."""
        with self.network.opened() as fds:
            data = os.read(fds["ca_bundle"], 4 * 1024**2)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=data.decode("ascii"))
        return context

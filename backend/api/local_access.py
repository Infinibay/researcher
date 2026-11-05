"""Local owner sessions, isolated from model-side business tool authority."""

import asyncio
import hashlib
import logging
import os
import secrets
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

COOKIE = "researcher_owner"
logger = logging.getLogger(__name__)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class OwnerSession:
    csrf_token: str
    expires: float
    active: bool = True


class LocalAccess:
    """Process-local sessions; restarts require pairing again, never OAuth."""

    def __init__(
        self,
        *,
        pairing_key: str | None = None,
        allowed_origins: set[str] | None = None,
        allowed_hosts: set[str] | None = None,
        clock=time.monotonic,
        session_seconds=28800,
    ):
        from backend.api.config import CORS_ORIGINS

        if pairing_key is not None and len(pairing_key) < 32:
            raise ValueError("Owner pairing keys require at least 32 characters")
        if not 0 < session_seconds <= 28800:
            raise ValueError("Owner sessions require a bounded positive lifetime")
        self.allowed_origins = frozenset(allowed_origins or CORS_ORIGINS)
        self.allowed_hosts = frozenset(
            allowed_hosts or {"localhost", "127.0.0.1", "[::1]"}
        )
        self.clock = clock
        self.session_seconds = session_seconds
        self._pairing_digest = _digest(pairing_key) if pairing_key else None
        self._sessions: dict[str, OwnerSession] = {}
        self._failures: list[float] = []
        self.key_file: Path | None = None

    def start(self):
        """Only serving creates a private pairing file; construction is inert."""
        if self._pairing_digest is not None:
            return
        state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        directory = Path(
            os.environ.get("INFINIBAY_AUTH_DIR", state / "researcher/auth")
        )
        if directory.resolve().is_relative_to(Path.cwd().resolve()):
            raise ValueError("Owner credentials must be outside the workspace")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise ValueError(
                "Owner credential directory must be private and user-owned"
            )
        key = secrets.token_urlsafe(32)
        path = directory / f"owner-{os.getpid()}-{uuid4().hex}.key"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w") as output:
                output.write(key + "\n")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        self.key_file = path
        self._pairing_digest = _digest(key)
        logger.info("Local owner pairing code file: %s", path)
        print(f"Researcher local access code file: {path}", file=sys.stderr, flush=True)

    def close(self):
        for session in self._sessions.values():
            session.active = False
        self._sessions.clear()
        self._pairing_digest = None
        if self.key_file is not None:
            self.key_file.unlink(missing_ok=True)
            self.key_file = None

    def valid(self, session: OwnerSession | None) -> bool:
        return session is not None and session.active and self.clock() < session.expires

    def session(self, connection: HTTPConnection) -> OwnerSession | None:
        token = connection.cookies.get(COOKIE, "")
        if len(token) > 256:
            return None
        session = self._sessions.get(_digest(token))
        return session if self.valid(session) else None

    def pair(self, code: str) -> tuple[str, OwnerSession]:
        now = self.clock()
        self._failures = [t for t in self._failures if now - t < 60]
        if len(self._failures) >= 20:
            raise PermissionError(
                "Pairing is temporarily limited; try again in a minute"
            )
        if self._pairing_digest is None or not secrets.compare_digest(
            _digest(code), self._pairing_digest
        ):
            self._failures.append(now)
            raise PermissionError("Owner pairing code is invalid")
        self._sessions = {
            key: value for key, value in self._sessions.items() if self.valid(value)
        }
        if len(self._sessions) >= 128:
            raise PermissionError(
                "Owner session capacity reached; close a session first"
            )
        token = secrets.token_urlsafe(32)
        session = OwnerSession(secrets.token_urlsafe(32), now + self.session_seconds)
        self._sessions[_digest(token)] = session
        return token, session

    def revoke(self, session: OwnerSession):
        session.active = False
        self._sessions = {
            key: value for key, value in self._sessions.items() if self.valid(value)
        }


class OwnerAccessMiddleware:
    """Separate owner sessions/CSRF and optional physical endpoint binding from model-side tool authority."""

    def __init__(self, app, *, access: LocalAccess):
        self.app = app
        self.access = access

    async def __call__(self, scope, receive, send):
        """Authorize owner transport and reject a changed database before a retained terminal action can reach its route."""
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        websocket = scope["type"] == "websocket"

        async def deny(status, detail):
            if websocket:
                await send({"type": "websocket.close", "code": 1008})
            else:
                await JSONResponse(
                    {"detail": detail},
                    status_code=status,
                    headers={"Cache-Control": "no-store"},
                )(scope, receive, send)

        hosts, origins = headers.getlist("host"), headers.getlist("origin")
        host = hosts[0].lower() if len(hosts) == 1 else ""
        hostname = (
            host.split("]", 1)[0] + "]"
            if host.startswith("[")
            else host.split(":", 1)[0]
        )
        if hostname not in self.access.allowed_hosts or any(
            c in host for c in "/@\\, "
        ):
            return await deny(400, "Untrusted request host")
        # The built UI is served by this same validated loopback endpoint.
        # Its port may be chosen dynamically; configured origins additionally
        # permit explicitly trusted cross-origin development clients.
        protocol = "https" if scope.get("scheme") in {"https", "wss"} else "http"
        own_origin = protocol + "://" + host
        if (
            len(origins) > 1
            or (
                origins
                and origins[0] != own_origin
                and origins[0] not in self.access.allowed_origins
            )
            or headers.get("sec-fetch-site") == "cross-site"
        ):
            return await deny(403, "Untrusted browser origin")
        connection = HTTPConnection(scope)
        if set(connection.query_params) & {"token", "access_token", "api_key", "code"}:
            return await deny(400, "Credentials must not be supplied in URLs")
        session = self.access.session(connection)
        scope.setdefault("state", {})["owner_session"] = session
        path = scope["path"]
        if websocket:
            if not origins or not self.access.valid(session):
                return await deny(401, "Owner session required")
            closed = False

            async def guarded_send(message):
                nonlocal closed
                if (
                    not self.access.valid(session)
                    and message["type"] != "websocket.close"
                ):
                    if not closed:
                        await send({"type": "websocket.close", "code": 1008})
                        closed = True
                    raise WebSocketDisconnect(1008)
                await send(message)

            async def guarded_receive():
                nonlocal closed
                while self.access.valid(session):
                    try:
                        async with asyncio.timeout(0.25):
                            return await receive()
                    except TimeoutError:
                        pass
                if not closed:
                    await send({"type": "websocket.close", "code": 1008})
                    closed = True
                return {"type": "websocket.disconnect", "code": 1008}

            return await self.app(scope, guarded_receive, guarded_send)
        # Tool grants are checked by their own boundary; they never grant owner access.
        public = path in {"/api/session", "/api/health/ready"} or path.startswith(
            "/api/research-tools/"
        )
        protected = path.startswith(("/api", "/docs", "/redoc", "/openapi"))
        if (
            protected
            and not public
            and scope["method"] != "OPTIONS"
            and session is None
        ):
            return await deny(401, "Owner session required")
        unsafe = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if unsafe and not path.startswith("/api/research-tools/"):
            pairing = path == "/api/session" and scope["method"] == "POST"
            if pairing:
                if headers.get("x-researcher-client") not in ("web", "terminal"):
                    return await deny(403, "Explicit owner pairing client required")
                if (
                    headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != "application/json"
                ):
                    return await deny(415, "Owner pairing requires JSON")
            elif session is None or not secrets.compare_digest(
                _digest(headers.get("x-researcher-csrf", "")),
                _digest(session.csrf_token),
            ):
                return await deny(403, "Valid owner CSRF token required")
        endpoint = headers.get("x-researcher-endpoint")
        if endpoint is not None and self.access.valid(session):
            from backend.api.owner_endpoint import endpoint_identity

            if endpoint != await asyncio.to_thread(endpoint_identity, connection):
                return await JSONResponse(
                    status_code=409,
                    content={"code": "owner_endpoint_changed", "detail": "Owner database identity changed; retain the original pending intent and inspect its history before another action."},
                    headers={"Cache-Control": "no-store"},
                )(scope, receive, send)
        await self.app(scope, receive, send)

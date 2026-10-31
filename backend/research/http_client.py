"""Small stdlib HTTP adapter used by the isolated research MCP process."""

import ipaddress
import json
from urllib import error, parse, request


class ResearcherClientError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ResearcherHTTPClient:
    def __init__(
        self,
        api_url: str,
        token: str,
        *,
        timeout: float = 15,
        response_limit: int = 1048576,
    ):
        try:
            origin = parse.urlsplit(api_url)
            address = ipaddress.ip_address(origin.hostname or "")
            if (
                origin.scheme != "http"
                or not address.is_loopback
                or origin.username is not None
                or origin.password is not None
                or origin.path not in ("", "/")
                or origin.query
                or origin.fragment
                or origin.port == 0
            ):
                raise ValueError("Not a local backend origin")
        except ValueError as exc:
            raise ResearcherClientError(
                "Backend origin must be an explicit numeric loopback HTTP origin without credentials or a path"
            ) from exc
        if (
            not token
            or len(token) > 512
            or any(c.isspace() or ord(c) < 32 for c in token)
        ):
            raise ResearcherClientError(
                "Host tool credentials are not configured or invalid"
            )
        if timeout <= 0 or response_limit <= 0:
            raise ValueError("HTTP bounds must be positive")
        host = f"[{address.compressed}]" if address.version == 6 else address.compressed
        authority = host + (f":{origin.port}" if origin.port is not None else "")
        self.origin = parse.urlunsplit(("http", authority, "", "", ""))
        self.token = token
        self.timeout = timeout
        self.response_limit = response_limit
        self.opener = request.build_opener(request.ProxyHandler({}), _NoRedirect())

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        query: dict | None = None,
    ) -> dict:
        if (
            method not in ("GET", "POST")
            or not path.startswith("/")
            or "?" in path
            or "#" in path
            or "\\" in path
            or any(part in ("..", ".") for part in path.split("/"))
            or "//" in path
        ):
            raise ResearcherClientError("Invalid research tool route")
        url = self.origin + "/api/research-tools" + path
        if query:
            url += "?" + parse.urlencode(
                {key: value for key, value in query.items() if value is not None}
            )
        data = None
        if body is not None:
            try:
                data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode(
                    "utf-8"
                )
            except (ValueError, TypeError) as exc:
                raise ResearcherClientError("Tool request is not valid JSON") from exc
            if len(data) > 1048576:
                raise ResearcherClientError("Tool request exceeds the byte limit")
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(self.response_limit + 1)
                if len(raw) > self.response_limit:
                    raise ResearcherClientError(
                        "Tool response exceeds the byte limit; request a smaller page"
                    )
        except error.HTTPError as exc:
            try:
                raw = exc.read(65537)
                payload = json.loads(raw) if len(raw) <= 65536 else {}
                if not isinstance(payload, dict):
                    payload = {}
                detail = (
                    payload.get("error")
                    or payload.get("detail")
                    or "Backend request failed"
                )
                if isinstance(detail, list):
                    detail = "; ".join(
                        ".".join(str(p) for p in item.get("loc", []))
                        + ": "
                        + str(item.get("msg", "Invalid input"))[:200]
                        for item in detail[:6]
                    )
                if not isinstance(detail, str):
                    detail = "Backend request failed"
            except (ValueError, UnicodeError):
                detail = "Backend request failed"
            finally:
                exc.close()
            raise ResearcherClientError(
                f"Researcher HTTP {exc.code}: {detail[:1200]}", status=exc.code
            ) from exc
        except (error.URLError, OSError, TimeoutError) as exc:
            raise ResearcherClientError(
                "No confirmed backend receipt; reconcile or retry with the same operation_key"
            ) from exc
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ResearcherClientError(
                "Backend returned invalid JSON; no receipt is confirmed"
            ) from exc
        if not isinstance(result, dict):
            raise ResearcherClientError("Backend returned an invalid tool response")
        return result

"""Synchronous terminal adapter to the sole local owner API, with private durable original intents and explicit endpoint identity; no model or database owner lives here."""

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx


class TerminalError(RuntimeError):
    """A terminal action cannot be confirmed safely; its original journal remains authoritative."""


def _private_file(path, maximum):
    """Read a bounded private regular user-owned file without following its final symlink or disclosing contents in errors."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size > maximum
            ):
                raise TerminalError(
                    "El fichero debe ser privado, regular y del usuario actual."
                )
            value = source.read(maximum + 1)
            if len(value) > maximum:
                raise TerminalError("El fichero excede su límite declarado.")
            return value
    except (OSError, UnicodeError) as error:
        raise TerminalError("No se pudo leer el fichero privado indicado.") from error


class TerminalJournal:
    """Persist pending intent and owner-observed material in one private origin/project-scoped atomic record."""

    def __init__(self, directory, origin, project):
        """Validate private storage before any domain mutation; actual server workspace evidence is checked after pairing."""
        directory = Path(directory).absolute()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise TerminalError(
                "El directorio de estado debe ser privado y del usuario actual."
            )
        scope = hashlib.sha256(json.dumps([origin, project]).encode()).hexdigest()
        self.path = directory / (scope + ".json")
        self.lock_path = directory / (scope + ".lock")
        self.origin, self.project = origin, project

    @contextmanager
    def locked(self):
        """Serialize terminal processes before reading, retaining or resolving an original owner action."""
        fd = os.open(
            self.lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise TerminalError("El bloqueo de estado no es privado.")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def read(self):
        """Recover exact scoped state; corruption is an error, never permission to invent a fresh action."""
        if not self.path.exists():
            return {
                "schema": 1,
                "origin": self.origin,
                "project_id": self.project,
                "endpoint_id": None,
                "pending": None,
                "observations": {},
                "thread_id": None,
            }
        try:
            value = json.loads(_private_file(self.path, 8388608))
            if (
                value["schema"] != 1
                or value["origin"] != self.origin
                or value["project_id"] != self.project
                or not isinstance(value["observations"], dict)
                or not all(k in value for k in ("endpoint_id", "pending", "thread_id"))
            ):
                raise ValueError("scope")
            return value
        except (ValueError, KeyError, TypeError) as error:
            raise TerminalError(
                "No se pudo recuperar el estado original. Conserva el fichero y consulta el historial."
            ) from error

    def write(self, value):
        """Atomically retain the complete next record and synchronize it before any HTTP mutation can be released."""
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        if len(data) > 8388608:
            raise TerminalError(
                "El estado completo excede 8 MiB; no se omitió información."
            )
        fd, temporary = tempfile.mkstemp(prefix=".terminal-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            parent = os.open(
                self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
            )
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            Path(temporary).unlink(missing_ok=True)


class OwnerClient:
    """Use owner pairing/CSRF and exact receipts against a fixed loopback database endpoint, retaining uncertainty across terminal restarts."""

    def __init__(self, *, origin, project_id, key_file, state_dir, transport=None):
        """Validate endpoint, explicit credentials and private journal without starting a server, runtime, provider probe or source indexer."""
        try:
            url = urlsplit(origin)
            if (
                url.scheme != "http"
                or url.hostname not in ("localhost", "127.0.0.1", "::1")
                or url.username is not None
                or url.password is not None
                or url.path not in ("", "/")
                or url.query
                or url.fragment
                or (url.port is not None and not 1 <= url.port <= 65535)
            ):
                raise ValueError("origin")
        except (ValueError, TypeError) as error:
            raise TerminalError(
                "Indica el origen HTTP local del servicio, sin ruta ni credenciales."
            ) from error
        if type(project_id) is not int or project_id < 1:
            raise TerminalError("Selecciona explícitamente un ID de proyecto positivo.")
        self.origin = origin.rstrip("/")
        self.project_id = project_id
        self.key_file = Path(key_file).resolve(strict=True)
        try:
            self._code = _private_file(key_file, 256).decode().strip()
        except UnicodeError as error:
            raise TerminalError(
                "El fichero de emparejamiento no contiene texto válido."
            ) from error
        if len(self._code) < 32:
            raise TerminalError(
                "El fichero de emparejamiento no contiene una clave válida."
            )
        self.journal = TerminalJournal(state_dir, self.origin, project_id)
        self.http = httpx.Client(
            base_url=self.origin,
            timeout=httpx.Timeout(20, connect=3),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )
        self.endpoint_id = None
        self.csrf = None

    def _pair(self):
        """Pair in memory and compare durable installation/physical database scope before any old intent is retried."""
        if self.csrf is not None:
            return
        try:
            response = self.http.post(
                "/api/session",
                json={"code": self._code},
                headers={"X-Researcher-Client": "terminal", "Origin": self.origin},
            )
            data = response.json()
            if (
                response.status_code != 200
                or data.get("authenticated") is not True
                or not isinstance(data.get("csrf_token"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", data.get("endpoint_id", ""))
            ):
                raise TerminalError(
                    "No se pudo emparejar con el servicio owner configurado."
                )
        except (httpx.HTTPError, ValueError) as error:
            raise TerminalError(
                "No se pudo conectar con el servicio local; inicia la API configurada y conserva las solicitudes pendientes."
            ) from error
        roots = data.get("workspace_roots")
        if not isinstance(roots, list) or any(
            not isinstance(root, str) or not Path(root).is_absolute() for root in roots
        ):
            raise TerminalError(
                "El servicio no declaró sus workspaces protegidos; no inferimos que el cwd de la terminal sea su repositorio."
            )
        if any(
            self.journal.path.resolve().is_relative_to(Path(root).resolve())
            or self.key_file.is_relative_to(Path(root).resolve())
            for root in roots
        ):
            raise TerminalError(
                "La clave y el estado privado deben quedar fuera de los workspaces del servicio y sus repositorios."
            )
        self.endpoint_id = data["endpoint_id"]
        self.csrf = data["csrf_token"]

    def _bind(self, state):
        """Bind a fresh journal once; matching URL/project labels never override a changed database identity."""
        self._pair()
        if (
            state["endpoint_id"] is not None
            and state["endpoint_id"] != self.endpoint_id
        ):
            raise TerminalError(
                "Cambió la identidad de la base del servicio. Conservamos el original y no reenviamos trabajo a otra base."
            )
        state["endpoint_id"] = self.endpoint_id

    def _path(self, path):
        """Accept only this project's owner reads/actions; foreign origins, credentials and cross-project paths cannot enter retained packets."""
        if (
            not isinstance(path, str)
            or not path.startswith("/api/")
            or "\\" in path
            or "#" in path
            or any(part in (".", "..") for part in path.split("/"))
        ):
            raise TerminalError("Ruta owner inválida.")
        allowed = (f"/api/projects/{self.project_id}", f"/api/chat/{self.project_id}")
        parsed = urlsplit(path)
        if parsed.path == "/api/findings-index":
            fields = parse_qs(parsed.query, keep_blank_values=True)
            if (
                fields.get("project_id") == [str(self.project_id)]
                and set(fields) <= {"project_id", "after_id", "limit"}
                and all(
                    len(values) == 1 and values[0].isascii() and values[0].isdigit()
                    for values in fields.values()
                )
            ):
                return path
        if (
            not any(
                path == prefix or path.startswith(prefix + "/") for prefix in allowed
            )
            and path != f"/api/tasks?project_id={self.project_id}"
        ):
            raise TerminalError("La solicitud no pertenece al proyecto configurado.")
        return path

    def _action(self, action):
        """Validate stored command type, project path and exact expected operation identity before releasing its first or repeated POST."""
        try:
            path = self._path(action["path"])
            p = self.project_id
            rid = r"[A-Za-z0-9][A-Za-z0-9_.:%-]{0,383}"
            routes = {
                "note.create": rf"/api/chat/{p}",
                "plan.start": rf"/api/projects/{p}/start",
                "plan.accept": rf"/api/projects/{p}/runs/{rid}/project-plan/accept",
                "plan.execute": rf"/api/projects/{p}/runs/{rid}/project-plan/execution",
                "plan.control": rf"/api/projects/{p}/plan-executions/{rid}/control",
                "plan.continue": rf"/api/projects/{p}/plan-executions/{rid}/deliveries/{rid}/continuation",
                "task.start": rf"/api/projects/{p}/tasks/[1-9][0-9]*/runs",
                "result.accept": rf"/api/projects/{p}/runs/{rid}/result/accept",
                "code.review": rf"/api/projects/{p}/tasks/[1-9][0-9]*/code-reviews",
                "code.accept": rf"/api/projects/{p}/runs/{rid}/code-result/accept",
            }
            kind, body, expected = action["kind"], action["body"], action["expected"]
            if (
                kind not in routes
                or not re.fullmatch(routes[kind], path)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", body["operation_key"])
            ):
                raise ValueError("command")
            project_field = "run.project_id" if kind == "plan.start" else "project_id"
            key_field = (
                "request.operation_key" if kind == "plan.start" else "operation_key"
            )
            if (
                expected.get(project_field) != p
                or expected.get(key_field) != body["operation_key"]
                or not expected
            ):
                raise ValueError("receipt scope")
            if action.get("endpoint_id") != self.endpoint_id:
                raise TerminalError(
                    "La solicitud pendiente pertenece a otra identidad de base."
                )
        except (KeyError, TypeError, ValueError) as error:
            raise TerminalError(
                "El paquete original está dañado o no identifica una decisión owner válida."
            ) from error

    def _request(self, method, path, body=None):
        """Perform one bounded owner HTTP operation with original scope headers and no redirect/provider fallback."""
        response = self.http.request(
            method,
            self._path(path),
            json=body,
            headers={
                "Origin": self.origin,
                "X-Researcher-CSRF": self.csrf,
                "X-Researcher-Endpoint": self.endpoint_id,
            },
        )
        if len(response.content) > 8388608:
            raise TerminalError(
                "La respuesta completa excede el límite; conserva la solicitud original."
            )
        try:
            data = response.json()
        except ValueError as error:
            raise TerminalError(
                "La respuesta no contiene un recibo legible."
            ) from error
        if isinstance(data, dict) and data.get("code") == "owner_endpoint_changed":
            raise TerminalError(
                "Cambió la identidad de la base del servicio; el resultado original sigue sin confirmar."
            )
        return response.status_code, data

    def get(self, path):
        """Inspect current owner state without releasing pending mutations or creating another runtime owner."""
        with self.journal.locked():
            state = self.journal.read()
            self._bind(state)
            self.journal.write(state)
        try:
            status, data = self._request("GET", path)
        except httpx.HTTPError as error:
            raise TerminalError(
                "No se pudo consultar el servicio local. La consulta no reejecuta trabajo."
            ) from error
        if status != 200:
            raise TerminalError(
                f"La consulta fue rechazada ({status}). Verifica proyecto, sesión e historial."
            )
        return data

    def observe(self, key, data):
        """Persist exactly the material presented to the owner; later actions may not silently fetch a newer version."""
        with self.journal.locked():
            state = self.journal.read()
            self._bind(state)
            state["observations"][key] = data
            self.journal.write(state)

    def observed(self, key):
        """Read the last presented version or require an explicit inspection before deciding."""
        with self.journal.locked():
            state = self.journal.read()
            if key not in state["observations"]:
                raise TerminalError(
                    "Consulta primero esta propuesta/contexto; aún no hay una versión observada para decidir."
                )
            return state["observations"][key]

    def pending(self):
        """Inspect the original unresolved intent without pairing, retrying or refreshing its target."""
        with self.journal.locked():
            return self.journal.read()["pending"]

    def thread(self):
        """Read the last acknowledged explanatory conversation, never inferred from a process-local chat summary."""
        with self.journal.locked():
            return self.journal.read()["thread_id"]

    def post(self, kind, path, body, expected):
        """Persist the complete exact intent before POST; another command cannot overwrite unresolved work."""
        with self.journal.locked():
            state = self.journal.read()
            if state["pending"] is not None:
                raise TerminalError(
                    "Hay una decisión original pendiente. Usa /retry para consultar su recibo antes de otra acción."
                )
            self._bind(state)
            action = {
                "kind": kind,
                "path": path,
                "body": body,
                "expected": expected,
                "endpoint_id": self.endpoint_id,
                "rejected": False,
            }
            self._action(action)
            state["pending"] = action
            self.journal.write(state)
            return self._send(state)

    def _send(self, state):
        """Release one original packet and clear it only after a matching scoped receipt is durably retained."""
        action = state["pending"]
        self._action(action)
        action["rejected"] = False
        self.journal.write(state)
        try:
            status, data = self._request("POST", action["path"], action["body"])
            if status not in (200, 201, 202):
                action["rejected"] = status in (400, 404, 409, 422)
                self.journal.write(state)
                raise TerminalError(
                    f"El servicio rechazó la decisión original ({status}). Conserva el paquete y consulta el contexto."
                )
            for field, expected in action["expected"].items():
                current = data
                for part in field.split("."):
                    if not isinstance(current, dict) or part not in current:
                        raise TerminalError(
                            "El recibo no identifica la solicitud original. Conservamos el paquete pendiente."
                        )
                    current = current[part]
                if type(current) is not type(expected) or current != expected:
                    raise TerminalError(
                        "El recibo no corresponde al proyecto o decisión original. Conservamos el paquete pendiente."
                    )
            self._receipt_identities(action["kind"], data)
            if action["kind"] == "note.create":
                state["thread_id"] = data["thread_id"]
            state["last_receipt"] = {"kind": action["kind"], "value": data}
            state["pending"] = None
            self.journal.write(state)
            return data
        except httpx.HTTPError as error:
            raise TerminalError(
                "No se confirmó el resultado original. La solicitud queda pendiente; /retry reenvía el mismo paquete."
            ) from error

    @staticmethod
    def _receipt_identities(kind, data):
        """Require actual resulting identities before clearing uncertainty; matching echoes alone cannot identify newly admitted work."""

        def reference(value):
            """Recognize bounded domain IDs without accepting paths, terminal controls or missing references."""
            return (
                isinstance(value, str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value)
                is not None
            )

        def positive(value):
            """Require real integer task/message identities, excluding booleans."""
            return type(value) is int and value > 0

        valid = True
        if kind == "plan.start":
            run = data.get("run", {})
            valid = (
                isinstance(run, dict)
                and positive(data.get("planning_task_id"))
                and run.get("task_id") == data["planning_task_id"]
                and reference(run.get("run_id"))
            )
        elif kind == "plan.accept":
            tasks = data.get("tasks")
            valid = (
                isinstance(tasks, dict)
                and bool(tasks)
                and all(positive(value) for value in tasks.values())
            )
        elif kind in ("plan.execute", "plan.control"):
            valid = reference(data.get("execution_id"))
        elif kind == "plan.continue":
            valid = all(reference(data.get(key)) for key in ("execution_id", "predecessor_delivery_id", "previous_run_id", "delivery_id")) and data["delivery_id"] != data["predecessor_delivery_id"] and data.get("inference_started") is False
        elif kind in ("task.start", "code.review"):
            valid = reference(data.get("run_id"))
        elif kind == "note.create":
            valid = positive(data.get("id")) and reference(data.get("thread_id"))
        if not valid:
            raise TerminalError(
                "El recibo omitió identidades originales del resultado. Conservamos la solicitud pendiente."
            )

    def retry(self):
        """Recover the original request after process restart, preserving body, expected receipt and physical endpoint identity."""
        with self.journal.locked():
            state = self.journal.read()
            if state["pending"] is None:
                raise TerminalError("No hay una solicitud pendiente para reenviar.")
            self._bind(state)
            return self._send(state)

    def dismiss_rejected(self):
        """Explicitly retire a definite rejection after owner inspection; uncertain successful replies cannot be discarded this way."""
        with self.journal.locked():
            state = self.journal.read()
            if state["pending"] is None or state["pending"].get("rejected") is not True:
                raise TerminalError(
                    "Sólo se puede descartar una decisión rechazada; conserva cualquier resultado incierto."
                )
            state["last_rejection"] = state["pending"]
            state["pending"] = None
            self.journal.write(state)

    def close(self):
        """Close this HTTP projection only; pending state and server-owned work survive terminal exit."""
        self.http.close()

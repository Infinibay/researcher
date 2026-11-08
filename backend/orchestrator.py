"""Terminal presentation of the shared owner API; no local agents, model loop, tool context, task completion parser or automatic Git merge."""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote
from uuid import uuid4

from backend.cli.owner_client import TerminalError


@dataclass(frozen=True)
class OrchestratorEvent:
    """Non-authoritative terminal notification of an already retained owner receipt."""

    event_type: str
    agent_id: str = ""
    data: dict = field(default_factory=dict)


HELP = """Conversación y trabajo son decisiones distintas:
  texto libre                 Guardar una nota sin iniciar agentes
  /plan OBJETIVO              Admitir planificación nativa
  /proposal RUN               Leer propuesta, evidencia y supuestos
  /accept-plan RUN            Aceptar la propuesta observada; crea pendientes
  /execution RUN              Leer versión y entregas del plan
  /execute-plan RUN           Ejecutar la versión observada
  /pause-plan RUN              Pausar despacho y solicitar detención
  /resume-plan RUN             Continuar trabajo aún no emitido
  /continuation EXEC ENTREGA   Leer cierre y efectos del intento anterior
  /continue-delivery EXEC ENTREGA  Autorizar una sucesora de esa entrega observada
  /graph-revision EXEC        Revisar cambios del grafo, efectos y resultados vigentes
  /reauthorize-plan EXEC      Adoptar ese grafo observado; mantiene el despacho pausado
  /tasks                      Leer tareas reales del proyecto
  /task ID                    Leer contexto, repositorios y runs de una tarea
  /run ID OBJETIVO            Admitir trabajo sobre el contexto observado
  /result RUN                 Leer resultado de investigación y límites
  /accept-result RUN [--ack-limits]  Aceptar ese resultado observado
  /code RUN                   Leer candidato, checks, revisión y aceptación
  /review-code RUN            Solicitar revisión independiente del candidato observado
  /accept-code RUN [--ack-limits]    Aceptar ese candidato observado; no publica
  /input RUN                  Leer el input preparado y modelo del intento
  /questions                  Consultar preguntas pendientes del proyecto
  /events [CURSOR]            Leer página durable de actividad
  /knowledge [CURSOR]         Leer página de hallazgos con límites explícitos
  /status                     Consultar proyecto y tareas
  /models                     Explicar la configuración nativa y su procedencia
  /pending                    Consultar la solicitud sin recibo confirmado
  /retry                      Reenviar exactamente esa solicitud original
  /dismiss-rejected           Retirar sólo una decisión rechazada tras inspección
  /help                       Mostrar esta ayuda
  /exit                       Cerrar terminal; el servicio conserva su trabajo
Por ejemplo, /plan Investigar el parser prepara una propuesta. Aceptarla crea
las tareas; ejecutarla es otra decisión. «Gracias» sólo se guarda como nota."""


def _identifier(value):
    """Validate one domain reference before placing it in an owner path, without interpreting it as a file or command."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise TerminalError("Indica un único identificador de run válido.")
    return quote(value, safe="")


def _number(value):
    """Accept explicit positive database references, never inferred project/task selection."""
    if not value.isascii() or not value.isdigit() or int(value) < 1:
        raise TerminalError("Indica un ID positivo.")
    return int(value)


def _json(value):
    """Render complete owner data without hidden summaries; JSON escapes terminal control characters in values."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def _plain(value):
    """Prevent evidence or model text from emitting terminal control sequences while preserving ordinary language and code formatting."""
    return "".join(c for c in value if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127))


class ProjectOrchestrator:
    """Translate explicit terminal intent to the same owner API used by the web; all execution and durable facts remain owned by that service."""

    def __init__(self, *, project_id, owner_client, on_event=None):
        """Require explicit project and configured owner transport; construction creates no team, worktree, database or native session."""
        if owner_client.project_id != project_id:
            raise TerminalError(
                "La terminal y el cliente no seleccionan el mismo proyecto."
            )
        self.project_id = project_id
        self.client = owner_client
        self.on_event = on_event or (lambda _event: None)
        self.prefix = f"/api/projects/{project_id}"

    def initialize(self):
        """Inspect the selected server project only; no model/provider/index/bootstrap work happens in the terminal."""
        return self.client.get(self.prefix)

    def _post(self, kind, path, body, expected):
        """Use a new owner decision identity once, then rely exclusively on the client's original receipt protocol."""
        body = {**body, "operation_key": uuid4().hex}
        expected = {
            **expected,
            (
                "request.operation_key" if kind == "plan.start" else "operation_key"
            ): body["operation_key"],
        }
        result = self.client.post(kind, path, body, expected)
        self.on_event(
            OrchestratorEvent("owner_receipt", data={"kind": kind, "receipt": result})
        )
        return result

    def _read(self, key, path):
        """Retain exact material offered for inspection; this records delivery preparation, not proof that a person understood it."""
        value = self.client.get(path)
        if not isinstance(value, dict) or value.get("project_id") != self.project_id:
            raise TerminalError("La lectura no identifica el proyecto seleccionado.")
        self.client.observe(key, value)
        return value

    def _proposal(self, run):
        """Explain original basis and unknowns, preserving the full exact proposal hash for a separate owner decision."""
        state = self._read(
            "proposal:" + run, f"{self.prefix}/runs/{_identifier(run)}/project-plan"
        )
        proposal = state.get("proposal")
        if not proposal:
            return (
                "Todavía no hay propuesta estructurada. Un mensaje terminado no equivale a un plan aceptable.\n"
                + _json(state)
            )
        draft = proposal["draft"]
        origins = state["snapshot"].get("source_origins", {})
        lines = [
            draft["title"],
            draft["rationale"],
            "Versión exacta: " + proposal["proposal_sha256"],
            "Bases atribuidas:",
        ]
        for basis in draft["basis"]:
            origin = origins.get(basis["source"], "origen registrado")
            lines.append(f"- {basis['source']} ({origin}): {basis['quote']}")
        lines.append("Supuestos que puedes corregir:")
        lines.extend("- " + assumption for assumption in draft["assumptions"])
        if not draft["assumptions"]:
            lines.append(
                "No se declararon; esto no demuestra que todas las premisas estén comprobadas."
            )
        lines.append("Trabajo propuesto (aún sin autorización de ejecución):")
        lines.append(_json({"epics": draft["epics"], "tasks": draft["tasks"]}))
        lines.append(
            "Aceptar creará tareas pendientes. Ejecutar, revisar, aceptar resultados y publicar son decisiones distintas."
        )
        return "\n".join(lines)

    def _accept_plan(self, run):
        """Accept only the proposal offered earlier, without refreshing its hash or authorizing child execution."""
        state = self.client.observed("proposal:" + run)
        if not state.get("eligible") or not state.get("proposal"):
            raise TerminalError(
                "La propuesta observada no era elegible. Consulta /proposal antes de otra decisión."
            )
        body = {
            "proposal_sha256": state["proposal"]["proposal_sha256"],
            "context_version": state["context_version"],
        }
        result = self._post(
            "plan.accept",
            f"{self.prefix}/runs/{_identifier(run)}/project-plan/accept",
            body,
            {
                "project_id": self.project_id,
                "run_id": run,
                **body,
                "execution_started": False,
            },
        )
        return (
            "Plan aceptado: se crearon tareas pendientes; no se inició su ejecución.\n"
            + _json(result)
        )

    def _graph_revision(self, execution, *, authorize):
        """Expose corrected premises and historical evidence before a distinct exact owner adoption; never resume or silently refresh its snapshot."""
        path = f"{self.prefix}/plan-executions/{_identifier(execution)}/reauthorization"
        key = "graph-revision:" + execution
        if not authorize:
            state = self._read(key, path)
            if state.get("execution_id") != execution:
                raise TerminalError("La revisión no corresponde a la ejecución solicitada.")
            return "Revisa los cambios y las condiciones actuales. Adoptar este grafo es una decisión nueva: conserva la historia y los resultados aceptados vigentes, sustituye propuestas anteriores cuando haga falta y mantiene el despacho pausado.\n" + _json(state)
        state = self.client.observed(key)
        if not state.get("eligible") or state.get("execution_id") != execution:
            raise TerminalError("Consulta /graph-revision para revisar el cierre y el grafo actual antes de adoptarlo.")
        body = {"snapshot_sha256": state["snapshot_sha256"]}
        result = self._post("plan.reauthorize", path, body, {
            "project_id": self.project_id, "execution_id": execution,
            "plan_run_id": state["plan_run_id"], "snapshot_sha256": state["snapshot_sha256"],
            "manifest_sha256": state["manifest_sha256"],
            "authorization_revision": state["snapshot"]["previous_revision"] + 1,
            "status": "paused", "inference_started": False,
        })
        return "Grafo adoptado como una revisión nueva. Conservamos las decisiones y efectos anteriores; el despacho sigue pausado. Consulta /execution y decide después si reanudar esa revisión.\n" + _json(result)

    def _continuation(self, arguments, *, authorize):
        """Present original closed effects before granting one exact successor; the shared durable owner journal handles lost responses."""
        parts = arguments.split()
        if len(parts) != 2:
            raise TerminalError("Indica el ID de ejecución y el ID de entrega mostrados por /execution.")
        execution, delivery = parts
        path = f"{self.prefix}/plan-executions/{_identifier(execution)}/deliveries/{_identifier(delivery)}/continuation"
        key = f"continuation:{execution}:{delivery}"
        if not authorize:
            value = self._read(key, path)
            if value.get("execution_id") != execution or value.get("delivery_id") != delivery:
                raise TerminalError("La observación no corresponde a la entrega solicitada.")
            return "Una sucesora es un turno nuevo: conserva el intento, efectos y consumo anteriores. No repite automáticamente acciones ni adopta archivos privados. Si el plan está pausado, seguirá pausado.\n" + _json(value)
        state = self.client.observed(key)
        if not state.get("eligible") or state.get("execution_id") != execution or state.get("delivery_id") != delivery:
            raise TerminalError("Consulta /continuation para comprobar el cierre y las condiciones actuales de esa entrega.")
        body = {"snapshot_sha256": state["snapshot_sha256"]}
        result = self._post("plan.continue", path, body, {
            "project_id": self.project_id, "execution_id": execution,
            "predecessor_delivery_id": delivery,
            "previous_run_id": state["snapshot"]["previous_run"]["run_id"],
            "snapshot_sha256": body["snapshot_sha256"], "inference_started": False,
        })
        return "Sucesora autorizada; el intento anterior conserva su historia. El despacho y cada resultado siguen sujetos a sus controles y aceptación.\n" + _json(result)

    def _execution(self, run, command):
        """Inspect or control an original exact graph authorization; resume cannot replace failed/cancelled/uncertain attempts."""
        path = f"{self.prefix}/runs/{_identifier(run)}/project-plan/execution"
        if command == "/execution":
            value = self._read("execution:" + run, path)
            return (
                "Estado y versión del plan. Reanudar sólo continúa trabajo aún no emitido; los intentos inciertos conservan su identidad.\n"
                + _json(value)
            )
        state = self.client.observed("execution:" + run)
        execution = state.get("execution")
        if command == "/execute-plan":
            if not state.get("eligible") or execution:
                raise TerminalError(
                    "La versión observada no admite otra ejecución. Consulta /execution."
                )
            body = {"manifest_sha256": state["manifest_sha256"]}
            result = self._post(
                "plan.execute",
                path,
                body,
                {
                    "project_id": self.project_id,
                    "plan_run_id": run,
                    **body,
                    "status": "active",
                },
            )
            return (
                "Despacho autorizado para esa versión. Los prerrequisitos esperan resultados aceptados; el código no se acepta ni publica automáticamente.\n"
                + _json(result)
            )
        if not execution:
            raise TerminalError(
                "Consulta una ejecución original antes de pausarla o reanudarla."
            )
        body = {
            "manifest_sha256": execution["manifest_sha256"],
            "status": "paused" if command == "/pause-plan" else "active",
            **({"authorization_revision": execution["authorization_revision"]} if execution.get("authorization_revision") else {}),
        }
        result = self._post(
            "plan.control",
            f"{self.prefix}/plan-executions/{_identifier(execution['execution_id'])}/control",
            body,
            {
                "project_id": self.project_id,
                "plan_run_id": run,
                "execution_id": execution["execution_id"],
                **body,
            },
        )
        return (
            "Intención registrada. Consulta /execution para comprobar cada intento y su cierre; este recibo no demuestra cierre físico.\n"
            + _json(result)
        )

    def _task(self, task):
        """Show the selected task's actual context, repository choices and runs from the serving journal."""
        return _json(
            self._read("task:" + str(task), f"{self.prefix}/tasks/{task}/workspace")
        )

    def _run_task(self, arguments):
        """Admit an explicit task goal over its previously offered context and repository, never over an inferred cwd or in-memory task."""
        raw, _, prompt = arguments.partition(" ")
        task = _number(raw)
        if not prompt.strip():
            raise TerminalError("Uso: /run ID OBJETIVO; consulta /task ID antes.")
        observed = self.client.observed("task:" + str(task))
        repos = observed["repositories"]
        if len(repos) != 1:
            raise TerminalError(
                "Selecciona un único repositorio del proyecto mediante los controles de repositorio antes de iniciar desde esta terminal."
            )
        body = {
            "context_version": observed["context"]["context_version"],
            "request": prompt,
            "repository_id": repos[0]["id"],
        }
        result = self._post(
            "task.start",
            f"{self.prefix}/tasks/{task}/runs",
            body,
            {
                "project_id": self.project_id,
                "task_id": task,
                "context_version": body["context_version"],
                "prompt": prompt,
                "repository_id": repos[0]["id"],
            },
        )
        return (
            "Solicitud nativa guardada. Terminar un turno no completa ni acepta la tarea.\n"
            + _json(result)
        )

    def _result(self, run, code=False):
        """Retain the exact candidate/review/check limits shown to the owner; no conclusion is extracted from APPROVED/DONE prose."""
        key = ("code:" if code else "result:") + run
        path = f"{self.prefix}/runs/{_identifier(run)}/" + (
            "code-result" if code else "result"
        )
        return (
            "Resultado y límites conservados. Los estados de aceptación y publicación se muestran por separado.\n"
            + _json(self._read(key, path))
        )

    def _accept_result(self, arguments, code=False):
        """Bind acceptance to the observed candidate, context, review and check policy, with explicit acknowledgement of displayed limits."""
        parts = arguments.split()
        if len(parts) not in (1, 2) or (len(parts) == 2 and parts[1] != "--ack-limits"):
            raise TerminalError(
                "Indica RUN y, si reconoces los límites mostrados, --ack-limits."
            )
        run = parts[0]
        state = self.client.observed(("code:" if code else "result:") + run)
        if not state.get("eligible") or not state.get("candidate"):
            raise TerminalError(
                "El resultado observado no admite aceptación. Consulta su evidencia y estado actual."
            )
        candidate = state["candidate"]
        ack = len(parts) == 2
        if state.get("requires_acknowledgement") and not ack:
            raise TerminalError(
                "Hay límites mostrados que requieren reconocimiento explícito mediante --ack-limits."
            )
        body = {
            "context_version": candidate["context_version"]
            if code
            else candidate["scope"]["context_version"],
            "review_sha256": state["review_sha256"],
            "acknowledge_limits": ack,
            "note": None,
        }
        if code:
            body.update(
                attempt_id=candidate["attempt_id"],
                subject_sha256=state["subject_sha256"],
                check_policy_revision=state["project_check_policy"]["revision"],
            )
            expected = {
                "project_id": self.project_id,
                "run_id": run,
                "attempt_id": candidate["attempt_id"],
                "subject_sha256": state["subject_sha256"],
                "context_version": body["context_version"],
                "review_sha256": body["review_sha256"],
                "check_policy_revision": body["check_policy_revision"],
                "task_accepted": True,
                "publication_performed": False,
            }
        else:
            body.update(
                candidate_id=candidate["candidate_id"],
                candidate_sha256=candidate["candidate_sha256"],
            )
            expected = {
                "project_id": self.project_id,
                "run_id": run,
                "candidate_id": body["candidate_id"],
                "candidate_sha256": body["candidate_sha256"],
                "context_version": body["context_version"],
                "review_sha256": body["review_sha256"],
                "task_accepted": True,
                "acknowledged_limits": ack,
            }
        result = self._post(
            "code.accept" if code else "result.accept",
            f"{self.prefix}/runs/{_identifier(run)}/"
            + ("code-result/accept" if code else "result/accept"),
            body,
            expected,
        )
        return "Versión aceptada. Esta decisión no publica código.\n" + _json(result)

    def _review_code(self, run):
        """Request an independently scoped readonly review of the candidate observed earlier; review is neither acceptance nor publication."""
        state = self.client.observed("code:" + run)
        candidate = state.get("candidate")
        if (
            not state.get("candidate_current")
            or not candidate
            or not state.get("subject_sha256")
        ):
            raise TerminalError(
                "Consulta primero un candidato actual mediante /code RUN."
            )
        body = {
            "context_version": candidate["context_version"],
            "attempt_id": candidate["attempt_id"],
            "subject_sha256": state["subject_sha256"],
            "request": "Review this exact observed candidate. Explain verified evidence, concerns and limitations. Propose a review; do not accept or publish.",
        }
        result = self._post(
            "code.review",
            f"{self.prefix}/tasks/{state['task_id']}/code-reviews",
            body,
            {
                "project_id": self.project_id,
                "task_id": state["task_id"],
                "context_version": body["context_version"],
                "execution_kind": "code_review",
            },
        )
        return (
            "Revisión independiente admitida. Falta su resultado y una decisión de aceptación separada.\n"
            + _json(result)
        )

    def handle_user_message(self, message):
        """Distinguish explanatory notes from explicit typed commands; never parse chat text into work authority."""
        command, _, arguments = message.strip().partition(" ")
        if not command:
            raise TerminalError("Escribe una nota o una operación explícita.")
        if not command.startswith("/"):
            body = {
                "message": message,
                "to_agent": None,
                "to_role": "project_lead",
                "thread_id": self.client.thread(),
            }
            result = self._post(
                "note.create",
                f"/api/chat/{self.project_id}",
                body,
                {
                    "project_id": self.project_id,
                    "message": message,
                    "delivery": "recorded",
                },
            )
            text = f"Nota guardada en la conversación {result['thread_id']}; no inició agentes ni aplicó una corrección a un intento. Usa /plan o /run para solicitar trabajo explícito."
        elif command == "/plan":
            if not arguments.strip():
                raise TerminalError("Uso: /plan OBJETIVO")
            body = {"prompt": arguments, "repository_id": None}
            result = self._post(
                "plan.start",
                self.prefix + "/start",
                body,
                {
                    "run.project_id": self.project_id,
                    "run.actor_id": "native-project-planner",
                    "request.prompt": arguments,
                    "request.repository_id": None,
                },
            )
            text = f"Planificación guardada; tarea {result['planning_task_id']}, run {result['run']['run_id']}. Consulta /proposal {result['run']['run_id']}. La propuesta requerirá tu aceptación."
        elif command == "/proposal":
            text = self._proposal(arguments)
        elif command == "/accept-plan":
            text = self._accept_plan(arguments)
        elif command in ("/execution", "/execute-plan", "/pause-plan", "/resume-plan"):
            text = self._execution(arguments, command)
        elif command in ("/continuation", "/continue-delivery"):
            text = self._continuation(arguments, authorize=command == "/continue-delivery")
        elif command in ("/graph-revision", "/reauthorize-plan"):
            text = self._graph_revision(arguments, authorize=command == "/reauthorize-plan")
        elif command == "/task":
            text = self._task(_number(arguments))
        elif command == "/run":
            text = self._run_task(arguments)
        elif command == "/result":
            text = self._result(arguments)
        elif command == "/code":
            text = self._result(arguments, True)
        elif command == "/accept-result":
            text = self._accept_result(arguments)
        elif command == "/accept-code":
            text = self._accept_result(arguments, True)
        elif command == "/review-code":
            text = self._review_code(arguments)
        elif command == "/input":
            text = _json(
                self.client.get(f"{self.prefix}/runs/{_identifier(arguments)}/input")
            )
        elif command == "/tasks":
            text = _json(self.client.get(f"/api/tasks?project_id={self.project_id}"))
        elif command == "/questions":
            text = _json(self.client.get(self.prefix + "/questions"))
        elif command == "/events":
            cursor = int(arguments or "0")
            if cursor < 0:
                raise TerminalError("El cursor debe ser no negativo.")
            text = _json(
                self.client.get(self.prefix + "/runtime-events?after_id=" + str(cursor))
            )
        elif command == "/knowledge":
            cursor = int(arguments or "0")
            if cursor < 0:
                raise TerminalError("El cursor debe ser no negativo.")
            text = _json(
                self.client.get(
                    f"/api/findings-index?project_id={self.project_id}&after_id={cursor}"
                )
            )
        elif command == "/status":
            text = _json(self.get_status())
        elif command in ("/models", "/settings"):
            text = "La inferencia usa el modelo configurado por el host en INFINIBAY_RUNTIME_CONFIG (campo model). /task ID muestra la configuración disponible; /input RUN conserva el modelo realmente usado. Los antiguos LLM_MODEL/Ollama no controlan este runtime. La terminal no cambia el modelo del servidor."
        elif command == "/pending":
            text = _json(self.client.pending())
        elif command == "/retry":
            text = "Recibo de la solicitud original:\n" + _json(self.client.retry())
        elif command == "/dismiss-rejected":
            self.client.dismiss_rejected()
            text = "Decisión rechazada retirada del pendiente. Su evidencia se conserva en el estado privado."
        elif command == "/help":
            text = HELP
        else:
            raise TerminalError(
                "Comando desconocido. Usa /help; no se interpretó como una asignación."
            )
        return _plain(text)

    def get_status(self):
        """Project only actual server project/tasks; no invented in-memory roster, completion or multi-developer state."""
        return {
            "project": self.client.get(self.prefix),
            "tasks": self.client.get(f"/api/tasks?project_id={self.project_id}"),
        }

    def shutdown(self):
        """Close the terminal transport; server work and original pending intents remain owned and recoverable there."""
        self.client.close()

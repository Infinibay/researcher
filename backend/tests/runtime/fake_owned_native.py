"""Controlled generation/command protocol; actual SDK/kernel has separate checks."""

import base64
import json
import subprocess
import sys
import tomllib
from pathlib import Path

features = {}
config = {}
args = iter(sys.argv[1:])
for arg in args:
    if arg in ("--enable", "--disable"):
        features[next(args)] = arg == "--enable"
    elif arg == "-c":
        config.update(tomllib.loads(next(args)))
steps = 0
source = finding = job = report = None
planning_mode = False
plan_material = None
review_mode = False
development_mode = False
review_subject = None
code_review_mode = False
code_packet = code_file = None
native_thread_id = "owned-thread"
native_turn_id = "owned-turn"


def send(message):
    print(json.dumps(message), flush=True)


def call(name, arguments):
    """Emit a controlled tool request attributed to this fixture's native thread and turn."""
    send(
        {
            "id": "tool-" + str(steps),
            "method": "item/tool/call",
            "params": {
                "threadId": native_thread_id,
                "turnId": native_turn_id,
                "callId": "tool-" + str(steps),
                "tool": name,
                "arguments": arguments,
            },
        }
    )


def next_tool(response=None):
    """Advance controlled author or reviewer generation while using the real admitted tool bridge."""
    if planning_mode:
        return next_planning_tool(response)
    if code_review_mode:
        return next_code_review_tool(response)
    if review_mode:
        return next_review_tool(response)
    if development_mode:
        return next_development_tool(response)
    global steps, source, finding, job, report
    if response is not None:
        Path("/home/actor/.codex/fixture-progress.json").write_text(
            json.dumps({"step": steps, "response": response})
        )
        if not response["success"]:
            raise RuntimeError("Controlled tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            job = value["job_id"]
        if steps == 3 and value["status"] != "exited":
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        if steps == 4:
            source = value["source_id"]
        if steps == 5:
            finding = value["finding_id"]
        if steps == 6:
            report = value["artifact_id"]
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call(
            "researcher_python",
            {
                "operation_key": "calculation",
                "code": "from pathlib import Path; print(int(Path('fact.txt').read_text())+63)",
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 3:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 4:
        call(
            "researcher_capture_reference",
            {"operation_key": "capture", "reference_file_id": 7},
        )
    elif steps == 5:
        call(
            "researcher_finding_record",
            {
                "operation_key": "finding",
                "topic": "fixture",
                "content": "Inspected a synthetic attachment; calculation200 is separate execution evidence.",
                "evidence": [{"source_id": source, "quote": "Fixture base 137 units."}],
            },
        )
    elif steps == 6:
        call(
            "researcher_report_write",
            {
                "operation_key": "report",
                "title": "Fixture inspection",
                "content": "Inspección y cálculo acotado. El informe sigue siendo un borrador.",
                "finding_ids": [finding],
            },
        )
    elif steps == 7:
        call(
            "researcher_result_propose",
            {
                "operation_key": "deliver",
                "report_ids": [report],
                "summary": "Inspección documental y cálculo acotado.",
                "limitations": [
                    "La medición original no se repitió; el cálculo es evidencia separada."
                ],
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "answer",
                        "type": "agentMessage",
                        "text": "Borrador persistido; la tarea requiere revisión.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def next_development_tool(response=None):
    """Exercise private edits, durable job reads and fresh Ken reads without proposing research acceptance."""
    global steps, job
    if response is not None:
        assert response["success"], response
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            job = value["job_id"]
        if steps == 3 and value["status"] != "exited":
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        if steps == 4:
            assert value == 200, value
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call(
            "researcher_python",
            {
                "operation_key": "edit-private",
                "code": "from pathlib import Path;p=Path('fact.txt');p.write_text(str(int(p.read_text())+63));print(p.read_text())",
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 3:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 4:
        call("ken_read", {"path": "fact.txt"})
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "answer",
                        "type": "agentMessage",
                        "text": "Copia privada actualizada; pendiente de candidato y revisión.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def next_review_tool(response=None):
    """Exercise admitted review reads and one decision without any author mutation."""
    global steps, review_subject
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled review tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            assert value["next_offset"] is None
            review_subject = json.loads(value["content"])
        if steps == 3:
            assert "137 units" in value["content"]
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call("researcher_review_subject", {"max_chars": 20000})
    elif steps == 3:
        call(
            "researcher_source_read",
            {"source_id": review_subject["evidence"][0]["source"]["id"]},
        )
    elif steps == 4:
        call(
            "researcher_review_decide",
            {
                "operation_key": "controlled-review-decision",
                "verdict": "supported",
                "rationale": "The captured text supports the recorded count.",
                "checks": [
                    {
                        "criterion": "claim_support",
                        "outcome": "supported",
                        "explanation": "The source explicitly reports 137 units.",
                    }
                ],
                "evidence": [
                    {
                        "source_id": review_subject["evidence"][0]["source"]["id"],
                        "quote": "137 units",
                    }
                ],
                "limitations": [
                    "The original measurement was not independently repeated."
                ],
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "answer",
                        "type": "agentMessage",
                        "text": "Revisión registrada con alcance limitado; tarea sin aceptar.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def next_code_review_tool(response=None):
    """Generate controlled independent review calls; every source/proposal/Git/closure operation remains production code."""
    global steps, code_packet, code_file, job
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled code review tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 1:
            assert value == 200
        elif steps == 2:
            assert value["complete_material"]
            code_packet = value
            origin = json.loads(value["text"])["author_request"]
            assert origin["source_kind"] in (
                "owner_admission",
                "coordinated_owner_execution",
            )
            if origin["source_kind"] == "coordinated_owner_execution":
                assert origin["work_delivery_id"] and origin["plan_run_id"]
                assert len(origin["work_delivery_sha256"]) == 64
        elif steps == 3:
            assert value["complete_material"]
            actual_input = json.loads(value["text"])
            if (
                json.loads(code_packet["text"])["author_request"]["source_kind"]
                == "coordinated_owner_execution"
            ):
                original = actual_input["work_delivery"]["plan_context"][
                    "original_material"
                ]
                assert original["instruction_origin"] == "owner_message"
                assert "137 to 200" in original["owner_request"]
                assert actual_input["work_delivery"]["plan_context"]["accepted_plan"][
                    "assumptions"
                ]
            else:
                assert "137 to 200" in actual_input["request"]
        elif steps == 4:
            assert value["complete_material"] and "+200" in value["text"]
        elif steps == 5:
            assert value["text"] == "200" and value["complete_file"]
            code_file = value
        elif steps == 6:
            job = value["job_id"]
        elif steps == 7 and value["status"] != "exited":
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        elif steps == 8:
            assert value["state"] == "proposed"
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt", "include": ["source"]})
    elif steps in (2, 3, 4):
        call(
            "researcher_code_review_subject",
            {
                "section": {2: "packet", 3: "author_input", 4: "diff"}[steps],
                "max_chars": 24000,
            },
        )
    elif steps == 5:
        call("researcher_code_review_file", {"path": "fact.txt"})
    elif steps == 6:
        call(
            "researcher_python",
            {
                "operation_key": "verify-review-readonly",
                "code": "from pathlib import Path\ntry: Path('fact.txt').write_text('unsafe')\nexcept OSError: print('readonly')\nelse: raise AssertionError('review source writable')",
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 7:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 8:
        call(
            "researcher_code_review_propose",
            {
                "operation_key": "review-" + code_packet["review_run_id"] + "-proposal",
                "subject_sha256": code_packet["subject_sha256"],
                "verdict": "supported",
                "rationale": "The recorded owner request changes137 to200; the actual candidate source contains200.",
                "checks": [
                    {
                        "criterion": "requested value",
                        "outcome": "supported",
                        "explanation": "Exact candidate source and full diff show200.",
                    },
                    {
                        "criterion": "tests",
                        "outcome": "not_applicable",
                        "explanation": "This controlled fixture changes only a data value; no project-wide test execution is claimed.",
                    },
                ],
                "references": [
                    {
                        "kind": "file",
                        "path": "fact.txt",
                        "sha256": code_file["sha256"],
                        "start_line": 1,
                        "quote": "200",
                    }
                ],
                "limitations": [
                    "Scoped data-only source inspection; not task acceptance, publication or a claim of project-wide test success."
                ],
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "review-answer",
                        "type": "agentMessage",
                        "text": "Observé200 en el candidato solicitado. La revisión queda propuesta con alcance limitado; la tarea sigue sin aceptar ni publicar.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def next_planning_tool(response=None):
    """Produce a controlled justified graph through actual native host tools, with no child execution or owner approval capability."""
    global steps, plan_material
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled planning tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            assert value["next_offset"] is None
            plan_material = json.loads(value["content"])
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call("researcher_plan_context", {})
    elif steps == 3:
        call(
            "researcher_plan_propose",
            {
                "operation_key": "controlled-plan-proposal",
                "plan": {
                    "title": "Understand then improve",
                    "rationale": "Inspect observed behavior before choosing a code change.",
                    "assumptions": [
                        "The registered repository remains the intended target."
                    ],
                    "basis": [
                        {
                            "source": "owner_request",
                            "quote": plan_material["owner_request"][:80],
                        }
                    ],
                    "epics": [
                        {
                            "key": "behavior",
                            "title": "Verified behavior",
                            "description": "Understand and improve the registered code.",
                        }
                    ],
                    "tasks": [
                        {
                            "key": "inspect",
                            "epic_key": "behavior",
                            "type": "research",
                            "title": "Inspect current behavior",
                            "description": "Read relevant code and record cited evidence.",
                            "acceptance_criteria": "A supported explanation and explicit limits.",
                            "priority": 2,
                            "depends_on": [],
                        },
                        {
                            "key": "improve",
                            "epic_key": "behavior",
                            "type": "code",
                            "title": "Implement supported improvement",
                            "description": "Apply the change supported by inspection.",
                            "acceptance_criteria": "The demonstrated behavior is verified.",
                            "priority": 2,
                            "depends_on": ["inspect"],
                        },
                    ],
                },
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "plan-answer",
                        "type": "agentMessage",
                        "text": "Guardé una propuesta: primero inspeccionar el comportamiento y después aplicar el cambio respaldado. La suposición sobre el repositorio queda explícita. No creé tareas ni inicié trabajo; falta tu aceptación.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    params = message.get("params", {})
    result = {}
    if method is None:
        next_tool(message["result"])
        continue
    if method == "account/login/start":
        result = {"type": "chatgptAuthTokens"}
    elif method == "account/read":
        result = {
            "account": {"type": "chatgpt"} if features.get("code_mode_host") else None
        }
    elif method == "config/read":
        result = {
            "config": {
                "features": features,
                "mcp_servers": {},
                "forced_login_method": "chatgpt",
                "model_provider": "openai",
                "chatgpt_base_url": "https://chatgpt.com/backend-api/",
                "web_search": config.get("web_search", "disabled"),
            }
        }
    elif method == "modelProvider/capabilities/read":
        result = {
            "webSearch": not Path("search-unavailable").exists(),
            "imageGeneration": False,
        }
    elif method == "command/exec":
        output = subprocess.run(
            params["command"],
            cwd=params.get("cwd"),
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if params.get("streamStdoutStderr"):
            for stream in ("stdout", "stderr"):
                raw = getattr(output, stream).encode()
                if raw:
                    send(
                        {
                            "method": "command/exec/outputDelta",
                            "params": {
                                "processId": params["processId"],
                                "stream": stream,
                                "deltaBase64": base64.b64encode(raw).decode(),
                                "capReached": False,
                            },
                        }
                    )
            result = {"exitCode": output.returncode, "stdout": "", "stderr": ""}
        else:
            result = {
                "exitCode": output.returncode,
                "stdout": output.stdout,
                "stderr": output.stderr,
            }
    elif method == "thread/start":
        planning_mode = any(
            tool["name"] == "researcher_plan_propose" for tool in params["dynamicTools"]
        )
        code_review_mode = any(
            tool["name"] == "researcher_code_review_propose"
            for tool in params["dynamicTools"]
        )
        if code_review_mode:
            native_thread_id, native_turn_id = "code-review-thread", "code-review-turn"
        development_mode = params.get("sandbox") == "workspace-write"
        review_mode = any(
            tool["name"] == "researcher_review_decide"
            for tool in params["dynamicTools"]
        )
        Path("/home/actor/.codex/fixture-thread.json").write_text(
            json.dumps(
                {
                    "model": params["model"],
                    "cwd": params["cwd"],
                    "catalog": params["dynamicTools"],
                    "developer_instructions": params.get("developerInstructions"),
                }
            )
        )
        result = {
            "thread": {"id": native_thread_id},
            "modelProvider": "openai",
            "model": params["model"],
            "cwd": params["cwd"],
        }
    elif method == "turn/start":
        result = {"turn": {"id": native_turn_id}}
    if "id" in message:
        send({"id": message["id"], "result": result})
    if method == "turn/start":
        if Path("/run/researcher-source/.ken/hold-turn").exists():
            Path("/home/actor/.codex/turn-entered").write_text("entered")
        else:
            next_tool()

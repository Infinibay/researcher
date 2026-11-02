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
review_mode = False
review_subject = None


def send(message):
    print(json.dumps(message), flush=True)


def call(name, arguments):
    send(
        {
            "id": "tool-" + str(steps),
            "method": "item/tool/call",
            "params": {
                "threadId": "owned-thread",
                "turnId": "owned-turn",
                "callId": "tool-" + str(steps),
                "tool": name,
                "arguments": arguments,
            },
        }
    )


def next_tool(response=None):
    """Advance controlled author or reviewer generation while using the real admitted tool bridge."""
    if review_mode:
        return next_review_tool(response)
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
        call("researcher_result_propose", {
            "operation_key": "deliver", "report_ids": [report],
            "summary": "Inspección documental y cálculo acotado.",
            "limitations": ["La medición original no se repitió; el cálculo es evidencia separada."],
        })
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "owned-thread",
                    "turnId": "owned-turn",
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
                    "threadId": "owned-thread",
                    "turn": {"id": "owned-turn", "status": "completed", "error": None},
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
                    "threadId": "owned-thread",
                    "turnId": "owned-turn",
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
                    "threadId": "owned-thread",
                    "turn": {"id": "owned-turn", "status": "completed", "error": None},
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
            "thread": {"id": "owned-thread"},
            "modelProvider": "openai",
            "model": params["model"],
            "cwd": params["cwd"],
        }
    elif method == "turn/start":
        result = {"turn": {"id": "owned-turn"}}
    if "id" in message:
        send({"id": message["id"], "result": result})
    if method == "turn/start":
        if Path("/run/researcher-source/.ken/hold-turn").exists():
            Path("/home/actor/.codex/turn-entered").write_text("entered")
        else:
            next_tool()

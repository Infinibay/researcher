"""Controlled native protocol for host composition; never contacts a model."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

features = {}
args = iter(sys.argv[1:])
for arg in args:
    if arg in ("--enable", "--disable"):
        features[next(args)] = arg == "--enable"
    elif arg == "-c":
        tomllib.loads("value=" + next(args).split("=", 1)[1])
methods, catalog, results = [], [], []
stored_thread = Path("/home/actor/.codex/controlled-thread.json")


def send(message):
    print(json.dumps(message), flush=True)


def tool(name, request_id):
    send(
        {
            "id": request_id,
            "method": "item/tool/call",
            "params": {
                "threadId": "owned-thread",
                "turnId": "owned-turn",
                "callId": request_id,
                "tool": name,
                "arguments": {"path": "fact.txt"},
            },
        }
    )


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    params = request.get("params", {})
    if method is None:
        results.append(request["result"])
        if request["id"] == "ken-call":
            tool("researcher_source_read", "business-call")
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
                            "text": results[0]["contentItems"][0]["text"],
                        },
                    },
                }
            )
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "owned-thread",
                        "turn": {
                            "id": "owned-turn",
                            "status": "completed",
                            "error": None,
                        },
                    },
                }
            )
        continue
    methods.append(method)
    result = {}
    if method == "account/read":
        result = {"account": {"type": "chatgpt"}}
    elif method == "command/exec":
        process = subprocess.run(
            params["command"], capture_output=True, text=True, timeout=8, check=False
        )
        result = {
            "exitCode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
    elif method == "config/read":
        result = {
            "config": {
                "features": features,
                "mcp_servers": {},
                "forced_login_method": "chatgpt",
                "model_provider": "openai",
                "chatgpt_base_url": "https://chatgpt.com/backend-api/",
            }
        }
    elif method == "thread/start":
        catalog = params["dynamicTools"]
        stored_thread.write_text(
            json.dumps(
                {"catalog": catalog, "model": params["model"], "cwd": params["cwd"]}
            )
        )
        result = {
            "thread": {"id": "owned-thread"},
            "modelProvider": "openai",
            "model": params["model"],
            "cwd": params["cwd"],
        }
    elif method in ("thread/read", "thread/resume"):
        stored = json.loads(stored_thread.read_text())
        catalog = stored["catalog"]
        thread = {
            "id": "owned-thread",
            "cwd": stored["cwd"],
            "model": stored["model"],
            "modelProvider": "openai",
        }
        result = {
            "thread": thread,
            "modelProvider": "openai",
            "model": stored["model"],
            "cwd": stored["cwd"],
        }
    elif method == "turn/start":
        result = {"turn": {"id": "owned-turn"}}
    elif method == "test/summary":
        result = {
            "methods": methods,
            "catalog_names": [t["name"] for t in catalog],
            "results_success": [r["success"] for r in results],
        }
    if "id" in request:
        send({"id": request["id"], "result": result})
    if method == "turn/start":
        tool("ken_read", "ken-call")

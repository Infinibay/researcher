"""Controlled native protocol for host composition; never contacts a model."""

import json
import sys
import tomllib

features = {}
args = iter(sys.argv[1:])
for arg in args:
    if arg in ("--enable", "--disable"):
        features[next(args)] = arg == "--enable"
    elif arg == "-c":
        tomllib.loads("value=" + next(args).split("=", 1)[1])
methods, catalog, results = [], [], []


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
        result = {
            "thread": {"id": "owned-thread"},
            "modelProvider": "openai",
            "model": params["model"],
            "cwd": params["cwd"],
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

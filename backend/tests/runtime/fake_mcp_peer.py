"""Controlled MCP stdio server; no provider, socket or SDK dependency."""

import json
import os
import sys
from pathlib import Path


def emit(message):
    print(json.dumps({"jsonrpc": "2.0", **message}), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    result = None
    if method == "initialize":
        result = {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "controlled", "version": "1"},
        }
    elif method == "tools/list":
        result = {"tools": [{"name": "read", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        action = request["params"]["arguments"].get("action", "echo")
        if action == "invalid":
            print("PRIVATE_CANARY is not json", flush=True)
            continue
        if action == "oversized":
            print("PRIVATE_CANARY" * 1000, flush=True)
            continue
        if action == "exit":
            sys.exit(0)
        if action == "hold":
            continue
        if action == "stderr":
            sys.stderr.write("PRIVATE_CANARY" * 40000)
            sys.stderr.flush()
        result = {
            "content": [
                {
                    "type": "text",
                    "text": (
                        Path(os.environ["KEN_PROJECT_ROOT"]) / "fact.txt"
                    ).read_text(),
                }
            ],
            "isError": False,
        }
    if "id" in request and result is not None:
        emit({"id": request["id"], "result": result})

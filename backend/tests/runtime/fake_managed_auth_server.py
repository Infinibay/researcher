"""Controlled managed-mode refresh: only synthetic auth.json and RPC receipts."""

import json
import sys
from pathlib import Path

held = None
forced = 0


def send(value):
    print(json.dumps(value), flush=True)


def reply(request, result):
    send({"id": request["id"], "result": result})


for line in sys.stdin:
    request = json.loads(line)
    method = request["method"]
    params = request.get("params", {})
    if method == "initialized":
        continue
    if method == "initialize":
        reply(request, {"userAgent": "synthetic-managed-auth"})
    elif method == "account/read":
        if params.get("refreshToken"):
            forced += 1
            held = request
            send({"method": "test/refresh-started", "params": {"count": forced}})
        else:
            reply(request, {"account": {"type": "chatgpt"}, "requiresOpenaiAuth": True})
    elif method == "test/release":
        condition = params.get("condition", "rotate")
        if condition == "error":
            send(
                {
                    "id": held["id"],
                    "error": {"code": -1, "message": "SECRET-REFRESH-ERROR"},
                }
            )
        else:
            path = Path("auth.json")
            value = json.loads(path.read_text())
            if condition != "unchanged":
                value["tokens"]["access_token"] = "e30.e30.rotation" + str(forced)
            if condition == "switch":
                value["tokens"]["account_id"] = "account-B"
            path.write_text(json.dumps(value))
            reply(held, {"account": {"type": "chatgpt"}, "requiresOpenaiAuth": True})
        held = None
        reply(request, {})
    elif method == "test/summary":
        reply(request, {"forced_refreshes": forced})
    else:
        raise AssertionError("Unexpected managed credential RPC")

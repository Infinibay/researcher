"""Synthetic auth races, no provider/network and no raw token logging."""

import hashlib
import json
import sys
from pathlib import Path

state = {"methods": [], "private_responses": 0, "initial_keys": [], "response_keys": []}
account = None
held = None
initial_digest = None
phase = Path("phase").read_text() if Path("phase").exists() else "thread"


def send(value):
    print(json.dumps(value), flush=True)


def save():
    Path("wire-summary.json").write_text(json.dumps(state))


def complete():
    send(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-A",
                "turnId": "turn-A",
                "item": {"id": "answer", "type": "agentMessage", "text": "ok"},
            },
        }
    )
    send(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-A",
                "turn": {"id": "turn-A", "status": "completed", "error": None},
            },
        }
    )


def refresh(request, result):
    global held
    held = (request, result)
    send(
        {
            "id": "auth-refresh",
            "method": "account/chatgptAuthTokens/refresh",
            "params": {
                "reason": "unauthorized",
                "previousAccountId": "account-B"
                if phase == "wrong-account"
                else "account-A",
            },
        }
    )


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    params = request.get("params", {})
    if method is None:
        state["private_responses"] += 1
        value = request.get("result", {})
        state["response_keys"] = sorted(value)
        state["token_changed"] = (
            hashlib.sha256(value.get("accessToken", "").encode()).hexdigest()
            != initial_digest
        )
        save()
        original, result = held
        held = None
        send({"id": original["id"], "result": result})
        if original["method"] == "turn/start":
            complete()
        continue
    state["methods"].append(method)
    save()
    result = {}
    if method == "initialize":
        result = {"userAgent": "synthetic"}
    elif method == "initialized":
        continue
    elif method == "account/login/start":
        state["initial_keys"] = sorted(params)
        initial_digest = hashlib.sha256(
            params.get("accessToken", "").encode()
        ).hexdigest()
        account = {"type": "chatgpt"}
        result = {"type": params["type"]}
        save()
    elif method == "account/read":
        result = {"account": account, "requiresOpenaiAuth": True}
    elif method in ("thread/start", "thread/resume"):
        result = {"thread": {"id": "thread-A"}, "modelProvider": "openai"}
        if phase in ("thread", "wrong-account", "both"):
            refresh(request, result)
            continue
    elif method == "turn/start":
        result = {"turn": {"id": "turn-A", "status": "inProgress", "items": []}}
        if phase in ("turn", "both"):
            refresh(request, result)
            continue
    elif method == "test/summary":
        result = state
    elif method == "turn/interrupt":
        result = {}
    if "id" in request:
        send({"id": request["id"], "result": result})
    if method == "turn/start":
        complete()

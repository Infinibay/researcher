"""A controlled stdio peer for process, correlation and backpressure tests."""

import json
import os
import signal
import sys


def emit(message):
    print(json.dumps(message), flush=True)


held = None
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")
    if method == "echo":
        emit({"id": request_id, "result": message.get("params")})
    elif method == "notification":
        emit({"method": "item/agentMessage/delta", "params": {"delta": "Working"}})
        emit({"id": request_id, "result": {"ok": True}})
    elif method == "approval":
        held = request_id
        emit({"id": "approval-1", "method": "item/commandExecution/requestApproval", "params": {"command": "test"}})
    elif method is None and request_id == "approval-1":
        emit({"id": held, "result": message.get("result")})
    elif method == "hold":
        held = request_id
    elif method == "release":
        emit({"id": held, "result": {"late": True}})
        emit({"id": request_id, "result": {"current": True}})
    elif method == "exit":
        sys.exit(0)
    elif method == "invalid":
        print("not-json", flush=True)
    elif method == "oversized":
        print("x" * 4096, flush=True)
    elif method == "burst":
        for i in range(10):
            emit({"method": "progress", "params": {"index": i}})
        emit({"id": request_id, "result": {"ok": True}})
    elif method == "stderr":
        sys.stderr.write("diagnostic" * 40000)
        sys.stderr.flush()
        emit({"id": request_id, "result": {"ok": True}})
    elif method == "error":
        emit({"id": request_id, "error": {"code": -32602, "message": "Invalid params"}})
    elif method == "stubborn":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        emit({"id": request_id, "result": {"pid": os.getpid()}})
        while True:
            signal.pause()

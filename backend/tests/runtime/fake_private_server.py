"""Connection-level requests can precede their client's pending response."""

import json
import sys

pending = None


def send(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method in ("private", "flood"):
        pending = request["id"]
        for i in range(5 if method == "flood" else 1):
            send(
                {
                    "id": "private-" + str(i),
                    "method": "account/chatgptAuthTokens/refresh",
                    "params": {
                        "reason": "unauthorized",
                        "previousAccountId": "account-A",
                    },
                }
            )
    elif method == "private_notice":
        send(
            {
                "method": "account/chatgptAuthTokens/refresh",
                "params": {"reason": "unauthorized"},
            }
        )
        send({"id": request["id"], "result": {}})
    elif method == "echo":
        send({"id": request["id"], "result": request.get("params")})
    elif method is None and pending is not None:
        send({"method": "progress", "params": {"text": "public event"}})
        send({"id": pending, "result": {"private_response_received": True}})
        pending = None

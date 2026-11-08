"""Fixed offline readiness cell for the measured0.166 code-mode host.

Executed only by trusted host preflight inside the native kernel profile. This
is not an inference/tool loop and accepts no user program, path or credentials.
Wire V1: four-byte little-endian length followed by JSON (official pinned codec).
"""

import json
import select
import struct
import subprocess
import time


def main():
    """Exercise one fixed offline code-host cell and delegated echo, verifying closure and reaping the original child."""
    deadline = time.monotonic() + 5
    child = subprocess.Popen(
        ["/run/researcher-runtime/codex-code-mode-host"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    def send(message):
        """Write one length-prefixed compact JSON frame to the original code-host process."""
        payload = json.dumps(message, separators=(",", ":")).encode()
        child.stdin.write(struct.pack("<I", len(payload)) + payload)
        child.stdin.flush()

    def exact(count):
        """Read exactly the requested byte count before the shared readiness deadline, refusing early EOF."""
        data = bytearray()
        while len(data) < count:
            if not select.select(
                [child.stdout], [], [], max(0, deadline - time.monotonic())
            )[0]:
                raise TimeoutError("Code-mode host readiness deadline")
            chunk = child.stdout.read1(count - len(data))
            if not chunk:
                raise RuntimeError("Code-mode host closed during readiness")
            data.extend(chunk)
        return data

    def receive():
        """Decode one V1 JSON frame and reject lengths outside the fixed readiness bound."""
        length = struct.unpack("<I", exact(4))[0]
        if not 0 < length <= 65536:
            raise RuntimeError("Code-mode readiness frame exceeded limit")
        return json.loads(exact(length))

    def response(request_id):
        """Find this request's successful operation response within the bounded intervening-message count."""
        for _ in range(16):
            message = receive()
            if (
                message.get("type") == "operation/response"
                and message.get("id") == request_id
            ):
                assert message["result"]["status"] == "ok"
                return message["result"]["value"]
        raise RuntimeError("Unexpected code-mode readiness messages")

    try:
        send(
            {
                "type": "connection/hello",
                "supportedVersions": [1],
                "requiredCapabilities": ["session-cell-execution-resource-limits"],
                "optionalCapabilities": [],
            }
        )
        hello = receive()
        assert hello["type"] == "connection/ready" and hello["selectedVersion"] == 1
        send(
            {
                "type": "operation/request",
                "id": 1,
                "request": {
                    "method": "session/open",
                    "sessionId": "researcher-readiness",
                    "cellExecutionLimits": {
                        "maxYieldTimeMs": 2000,
                        "maxHeapSizeBytes": 64 * 1024**2,
                    },
                },
            }
        )
        assert response(1)["type"] == "session/ready"
        send(
            {
                "type": "operation/request",
                "id": 2,
                "request": {
                    "method": "session/execute",
                    "sessionId": "researcher-readiness",
                    "request": {
                        "tool_call_id": "readiness",
                        "enabled_tools": [
                            {
                                "name": "readiness_echo",
                                "tool_name": {
                                    "name": "readiness_echo",
                                    "namespace": None,
                                },
                                "description": "Fixed host readiness fixture",
                                "kind": "function",
                                "input_schema": {
                                    "type": "object",
                                    "properties": {"value": {"type": "integer"}},
                                    "required": ["value"],
                                },
                                "output_schema": None,
                            }
                        ],
                        "source": 'if (typeof process !== "undefined" || typeof require !== "undefined" || typeof Deno !== "undefined") throw new Error("Unexpected IO globals"); const reply=await tools.readiness_echo({value:137}); text("RESEARCHER_HOST_OK_" + (reply.value + 63));',
                        "yield_time_ms": 1000,
                        "max_output_tokens": 128,
                    },
                },
            }
        )
        started = result = delegated = False
        for _ in range(16):
            message = receive()
            if message.get("type") == "delegate/request":
                invocation = message["request"]["invocation"]
                assert (
                    message["request"]["type"] == "tool/invoke"
                    and invocation["tool_name"]["name"] == "readiness_echo"
                )
                assert invocation["input"] == {"value": 137}
                send(
                    {
                        "type": "delegate/response",
                        "id": message["id"],
                        "result": {
                            "status": "ok",
                            "value": {"type": "tool/result", "result": {"value": 137}},
                        },
                    }
                )
                delegated = True
                continue
            if message.get("id") != 2:
                continue
            assert message["result"]["status"] == "ok"
            value = message["result"]["value"]
            if message["type"] == "operation/response":
                started = value["type"] == "execution/started"
            elif message["type"] == "execute/initialResponse":
                result = (
                    "RESEARCHER_HOST_OK_200" in json.dumps(value)
                    and "Result" in value
                    and not value["Result"].get("error_text")
                )
                if not result:
                    raise RuntimeError(
                        "Code-mode readiness cell did not produce its expected result"
                    )
            if started and result:
                break
        assert started and result and delegated
        send(
            {
                "type": "operation/request",
                "id": 3,
                "request": {
                    "method": "session/shutdown",
                    "sessionId": "researcher-readiness",
                },
            }
        )
        assert response(3)["type"] == "session/closed"
        child.stdin.close()
        assert child.wait(timeout=1) == 0
        print(
            json.dumps(
                {
                    "protocol": 1,
                    "computed": 200,
                    "isolated_globals": True,
                    "session_closed": True,
                    "delegate_roundtrip": True,
                }
            )
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=1)


if __name__ == "__main__":
    main()

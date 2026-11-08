"""Verify the measured local host before admitting a native thread or turn."""

import json
import sys
from pathlib import Path

from backend.runtime.codex_rpc import RpcProtocolError


async def probe_code_mode(rpc):
    """Run the fixed offline readiness payload through the existing broker sandbox and require its exact closed-session proof."""
    payload = Path(__file__).with_name("code_mode_payload.py").read_text()
    result = await rpc.request(
        "command/exec",
        {
            "command": [
                str(Path(sys.executable).resolve(strict=True)),
                "-I",
                "-S",
                "-c",
                payload,
            ],
            "cwd": "/tmp",
            # The broker's kernel sandbox is already applied and cannot be disabled
            # by this RPC. No second nested sandbox or model-selected command exists.
            "sandboxPolicy": {"type": "externalSandbox", "networkAccess": "restricted"},
            "timeoutMs": 7000,
            "outputBytesCap": 8192,
        },
        timeout=9,
    )
    expected = {
        "protocol": 1,
        "computed": 200,
        "isolated_globals": True,
        "session_closed": True,
        "delegate_roundtrip": True,
    }
    try:
        if (
            result.get("exitCode") != 0
            or json.loads(result.get("stdout", "")) != expected
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise RpcProtocolError(
            "Code-mode host readiness failed; no native turn admitted"
        ) from None
    return expected

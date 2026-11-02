"""Collect one check worker through the original broker, with complete bounded transport and physical closure."""

import asyncio
import base64
import json
from dataclasses import dataclass
from functools import partial

from backend.runtime.contracts import RunConflict


@dataclass(frozen=True)
class RawCheckResult:
    """Owned transport evidence and collected bytes, not a test verdict or publication authority."""

    payload: dict
    operation_id: str
    execution_closed: bool
    stdout: bytes
    stderr: bytes
    junit_xml: bytes | None
    subject_sha256: str


async def run_check_worker(owner, registry, peer_id, launch):
    """Run once under its original reservation; unknown transport never triggers another payload launch."""
    endpoint = owner.check(
        registry, peer_id, operation_key="code-check:" + launch.check_id, launch=launch
    )
    wire_limit = 4 * launch.spec.output_bytes + 2 * 1024**2 + 65536
    receipt = None

    async def collect(stream, bound):
        """Drain one finite complete byte stream; a preview is not a terminal check observation."""
        output = bytearray()
        while chunk := await stream.read(65536):
            if len(output) + len(chunk) > bound:
                raise RunConflict("Check worker transport exceeded its evidence limit")
            output.extend(chunk)
        return bytes(output)

    try:
        async with asyncio.timeout(launch.spec.timeout_seconds + 5):
            await endpoint.open(limit=65536)
            output, _diagnostics = await asyncio.gather(
                collect(endpoint.stdout, wire_limit), collect(endpoint.stderr, 65536)
            )
            await asyncio.get_running_loop().run_in_executor(
                owner._peer_pool, partial(endpoint._raw.wait, timeout=3)
            )
    finally:
        finish = asyncio.create_task(endpoint.aclose(timeout=5))
        try:
            receipt = await asyncio.shield(finish)
        except asyncio.CancelledError:
            await finish
            raise
    if (
        not isinstance(receipt, dict)
        or receipt.get("execution_closed") is not True
        or receipt.get("exit_code") != 0
    ):
        raise RunConflict(
            "Check collector termination or physical closure is unconfirmed"
        )
    operation = owner.broker.journal.load().records["broker:op:" + endpoint._operation]
    manifest = operation.get("runtime_manifest", {})
    binding = operation.get("execution_binding", {})
    if (
        manifest.get("profile") != "private-candidate-check-v1"
        or binding.get("check_id") != launch.check_id
        or binding.get("spec_sha256") != launch.spec.sha256
        or operation.get("execution_closed") is not True
    ):
        raise RunConflict("Check result differs from its original admitted operation")
    try:
        payload = json.loads(output)
        if (
            not isinstance(payload, dict)
            or type(payload["output_complete"]) is not bool
            or (
                payload["exit_code"] is not None
                and type(payload["exit_code"]) is not int
            )
        ):
            raise ValueError("Invalid check observation")
        if payload.get("error") is not None and (
            not isinstance(payload["error"], str)
            or not 1 <= len(payload["error"]) <= 128
        ):
            raise ValueError("Invalid collector issue")
        stdout = base64.b64decode(payload["stdout"], validate=True)
        stderr = base64.b64decode(payload["stderr"], validate=True)
        xml = (
            base64.b64decode(payload["junit_xml"], validate=True)
            if payload["junit_xml"] is not None
            else None
        )
        if max(len(stdout), len(stderr)) > launch.spec.output_bytes or (
            xml is not None and len(xml) > 1024**2
        ):
            raise ValueError("Check evidence overflow")
    except (ValueError, KeyError, TypeError) as exc:
        raise RunConflict(
            "Check collector did not return complete typed evidence"
        ) from exc
    return RawCheckResult(
        payload,
        endpoint._operation,
        True,
        stdout,
        stderr,
        xml,
        binding["subject_sha256"],
    )

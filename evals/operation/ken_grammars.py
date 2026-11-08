"""Verify real published Ken relationships, tests and parser loading inside the installed offline worker without a generative turn."""

import argparse
import hashlib
import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path


def packet(process, request, *, timeout=30):
    """Send one MCP request and observe its original matching reply without replaying or replacing it."""
    process.stdin.write(json.dumps(request).encode() + b"\n")
    process.stdin.flush()
    if "id" not in request:
        return None
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while remaining := max(0, deadline - time.monotonic()):
            if not selector.select(remaining):
                break
            line = process.stdout.readline(1000001)
            if not line or len(line) > 1000000 or not line.endswith(b"\n"):
                raise RuntimeError("Original MCP response closed or exceeded its bound")
            response = json.loads(line)
            if response.get("id") == request["id"]:
                return response
    raise TimeoutError("Original MCP result unavailable; no retry")


def data(response):
    """Read the actual structured analysis result separately from the MCP transport status."""
    result = response["result"]
    assert not result.get("isError", False), result
    structured = result.get("structuredContent")
    return structured if structured is not None else json.loads(result["content"][0]["text"])


def main():
    """Prepare a new synthetic source and retain real parser/MCP receipts from the noneditable installed product."""
    import backend
    from backend.runtime.ken_grammars import verify_grammars
    from backend.runtime.ken_worker import KenInstallation, worker_process

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ken-command", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    source = output / "source"
    source.mkdir()
    original = ('"""Preserve observation order for callers."""\n'
                'def list_observations(records):\n    """Return observations in their original order."""\n    return list(records)\n'
                'def summarize(records):\n    """Exercise a real direct call relationship."""\n    return len(list_observations(records))\n'
                'def unrelated():\n    """Provide a negative relationship case."""\n    return 0\n')
    (source / "observations.py").write_text(original)
    (source / "test_observations.py").write_text(
        '"""Verify the observation contract."""\nfrom observations import list_observations\n'
        'def test_order():\n    """Preserve incoming order."""\n    assert list_observations([8,2]) == [8,2]\n'
    )
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.py")}
    installation = KenInstallation.inspect(args.ken_command)
    result = {"generative_turns": 0, "grammars": verify_grammars(installation.tool_root), "status": "running"}
    process = None
    try:
        with worker_process(installation, workspace=source, mode="prepare", model_cache=args.model_cache) as launch:
            with (output / "prepare.log").open("xb") as log:
                prepared = subprocess.run(launch.command, pass_fds=launch.pass_fds, env=launch.env,
                    stdout=log, stderr=subprocess.STDOUT, timeout=120, check=False)
            result["prepare_exit"] = prepared.returncode
            assert prepared.returncode == 0
        probe = '''import json,os
from tree_sitter import Parser
from tree_sitter_language_pack import get_language
names=("python","javascript","typescript","tsx","go","rust","java","c","dart")
print(json.dumps({"languages":{name:bool(Parser(get_language(name))) for name in names},"network_namespace":os.readlink("/proc/self/ns/net")}))
'''
        with worker_process(installation, workspace=source, model_cache=args.model_cache,
                payload_prefix=(str(installation.tool_root / "bin/python"), "-I", "-c", probe)) as launch:
            parsed = subprocess.run(launch.command, pass_fds=launch.pass_fds, env=launch.env,
                capture_output=True, text=True, timeout=30, check=False)
            result["parser_exit"] = parsed.returncode
            (output / "parser.json").write_text(json.dumps({"exit": parsed.returncode, "stdout": parsed.stdout, "stderr": parsed.stderr}, indent=2) + "\n")
            assert parsed.returncode == 0
            result["parsers"] = json.loads(parsed.stdout)
            assert all(result["parsers"]["languages"].values())
            assert result["parsers"]["network_namespace"] != os.readlink("/proc/self/ns/net")
        with worker_process(installation, workspace=source, model_cache=args.model_cache) as launch:
            with (output / "mcp.log").open("xb") as log:
                process = subprocess.Popen(launch.command, pass_fds=launch.pass_fds, env=launch.env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, bufsize=0)
                responses = []
                try:
                    responses.append(packet(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                        "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "offline-grammar-evaluation", "version": "1"}}}))
                    packet(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
                    for number, name, arguments in (
                        (2, "ken_related", {"target": "list_observations", "relation": "callers", "output_format": "json"}),
                        (3, "ken_related", {"target": "unrelated", "relation": "callers", "output_format": "json"}),
                        (4, "ken_find", {"scope": "tests", "query": "observations.py", "output_format": "json"}),
                    ):
                        response = packet(process, {"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
                        responses.append(response)
                        (output / "mcp.json").write_text(json.dumps(responses, indent=2) + "\n")
                    result["analyses"] = [data(value) for value in responses[1:]]
                    assert all(value["ok"] for value in result["analyses"])
                    callers, negative, tests = result["analyses"]
                    assert "summarize" in json.dumps(callers["callers"])
                    assert not negative["callers"]
                    assert any(value["path"] == "test_observations.py" for value in tests["tests"])
                    result["status"] = "verified"
                finally:
                    if process.poll() is None:
                        process.terminate()
                    result["mcp_exit"] = process.wait(timeout=15)
                    process.stdin.close()
                    process.stdout.close()
    finally:
        result["source_unchanged"] = source_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.py")}
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "generative_turns": 0, "source_unchanged": result["source_unchanged"]}))


if __name__ == "__main__":
    main()

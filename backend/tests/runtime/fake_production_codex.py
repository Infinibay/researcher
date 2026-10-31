"""Configuration/identity peer for native-factory tests; never starts an LLM."""

import json
import os
import sys
import tomllib
from pathlib import Path

if "--version" in sys.argv:
    print("codex-cli 0.166.0")
    raise SystemExit(0)
config = {"chatgpt_base_url": "https://chatgpt.com/backend-api/"}
args = iter(sys.argv[1:])
for arg in args:
    if arg == "--disable":
        config.setdefault("features", {})[next(args)] = False
    elif arg == "--enable":
        config.setdefault("features", {})[next(args)] = True
    elif arg == "-c":
        key, value = next(args).split("=", 1)
        record = config
        parts = key.split(".")
        for part in parts[:-1]:
            record = record.setdefault(part, {})
        record[parts[-1]] = tomllib.loads("value=" + value)["value"]
log = Path(os.environ["CODEX_HOME"]) / "requests.jsonl"
with log.open("a") as file:
    file.write(json.dumps({"environment_keys": sorted(os.environ)}) + "\n")
for line in sys.stdin:
    request = json.loads(line)
    with log.open("a") as file:
        file.write(json.dumps(request) + "\n")
    method = request.get("method")
    params = request.get("params", {})
    result = {}
    if method == "initialize":
        result = {"userAgent": "fake"}
    elif method == "account/read":
        result = {
            "account": {
                "type": "apiKey"
                if (Path(os.environ["CODEX_HOME"]) / "api-key-account").exists()
                else "chatgpt"
            }
        }
    elif method == "config/read":
        effective = json.loads(json.dumps(config))
        if (Path(params["cwd"]) / "unsafe-effective-config").exists():
            effective["features"]["shell_tool"] = True
        if (Path(params["cwd"]) / "normalized-defaults").exists():
            effective["chatgpt_base_url"] = "https://chatgpt.com/backend-api"
            effective["mcp_servers"]["researcher_ken"]["env_vars"] = None
        if (Path(params["cwd"]) / "untrusted-auth-endpoint").exists():
            effective["chatgpt_base_url"] = "https://untrusted.example/api"
        if (Path(params["cwd"]) / "unsafe-shell-env").exists():
            effective.setdefault("shell_environment_policy", {}).setdefault("set", {})[
                "OPENAI_API_KEY"
            ] = "SYNTHETIC_ENV_SECRET"
        if (Path(params["cwd"]) / "disabled-code-host").exists():
            effective.setdefault("features", {})["code_mode_host"] = False
        result = {"config": effective}
    elif method == "thread/read":
        result = {
            "thread": json.loads(
                (Path(os.environ["CODEX_HOME"]) / "thread-metadata.json").read_text()
            )
        }
    elif method in ("thread/start", "thread/resume"):
        result = {
            "thread": {"id": "factory-thread"},
            "modelProvider": "openai",
            "model": params["model"],
            "cwd": params["cwd"],
            "activePermissionProfile": {"id": params["permissions"]},
            "runtimeWorkspaceRoots": [params["cwd"]],
        }
    elif method == "mcpServerStatus/list":
        result = {
            "data": [
                {
                    "name": "researcher_ken",
                    "tools": {
                        name: {}
                        for name in [
                            "ken_find",
                            "ken_read",
                            "ken_recall",
                            "ken_related",
                            "ken_remember",
                        ]
                    },
                    "toolsError": None,
                }
            ],
            "nextCursor": None,
        }
    if method in ("thread/start", "thread/resume"):
        (Path(os.environ["CODEX_HOME"]) / "thread-metadata.json").write_text(
            json.dumps({"id": "factory-thread", "cwd": params["cwd"]})
        )
    if "id" in request:
        print(json.dumps({"id": request["id"], "result": result}), flush=True)

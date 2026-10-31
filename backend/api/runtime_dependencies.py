"""Serving-only runtime composition from explicit host configuration."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from backend.research.sqlite_store import SQLiteResearchStore
from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.native_inference import CodexRuntime
from backend.runtime.service import RuntimeService, WorkspaceRegistry
from backend.runtime.sqlite_runs import SQLiteRunStore


def configured_runtime(live_grants):
    """No environment setting => product reads remain available, admission is 503.

    Construction/import never opens a model or copies OAuth credentials. Paths
    and policy come from the owner, never from an admission/tool request.
    """
    name = os.environ.get("INFINIBAY_RUNTIME_CONFIG")
    if not name:
        return None
    path = Path(name).resolve(strict=True)
    if path.stat().st_size > 65536:
        raise ValueError("Runtime configuration is too large")
    config = json.loads(path.read_text())
    api = urlsplit(config["api_url"])
    if (
        api.scheme != "http"
        or api.hostname not in ("127.0.0.1", "localhost", "::1")
        or api.username is not None
        or api.password is not None
        or api.path not in ("", "/")
        or api.query
        or api.fragment
    ):
        raise ValueError("Business MCP must use the local owner API")
    from backend.tools.base.db import get_db_path

    database = get_db_path()
    paths = {
        key: Path(config[key]).resolve(strict=True)
        for key in (
            "codex_binary",
            "managed_home",
            "ken_command",
            "model_cache",
            "business_script",
            "uv_binary",
            "uv_cache",
            "workspace_root",
        )
    }
    control = Path(config["control_root"]).absolute()
    source_root = paths.pop("workspace_root")
    for host_path in (
        path,
        Path(database).resolve(),
        control.resolve(),
        paths["managed_home"],
        paths["business_script"],
    ):
        if host_path.is_relative_to(source_root):
            raise ValueError(
                "Host state and runtime code must stay outside managed sources"
            )
    native = CodexRuntime(
        **paths, control_root=control, api_url=config["api_url"], model=config["model"]
    )
    return RuntimeService(
        SQLiteRunStore(database),
        SQLiteResearchStore(database, runtime_authority=live_grants.allows),
        live_grants,
        native,
        workspaces=WorkspaceRegistry(database, source_root),
        control_root=control,
        limits=ExecutionLimits(
            **config.get(
                "limits",
                {
                    "wall_seconds": 180,
                    "no_progress_seconds": 90,
                    "max_turns": 1,
                    "max_tool_calls": 25,
                    "max_observed_tokens": 350000,
                },
            )
        ),
        max_concurrent=config.get("max_concurrent", 2),
        project_turn_limit=config.get("project_turn_limit", 20),
        project_token_limit=config.get("project_token_limit", 4000000),
    )

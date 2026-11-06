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


def _legacy_project_active(project_id):
    """Observe actual registered legacy threads for every serving native factory; absence of a flow label alone is insufficient."""
    from backend.api.flow_manager import flow_manager

    return flow_manager.is_project_running(project_id)


def configured_runtime(live_grants, *, app=None):
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
    profile = config.get("runtime_profile", "legacy-codex")
    if profile == "owned-codex-v1":
        return _configured_owned(config, path, live_grants, app)
    if profile != "legacy-codex":
        raise ValueError("Unknown runtime profile; no fallback is permitted")
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
        legacy_active=_legacy_project_active,
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


def _configured_owned(config, path, live_grants, app):
    """Validate owner configuration and compose the actual serving controller."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.contracts import text
    from backend.runtime.development_policy import parse_development_checks
    from backend.runtime.ken_worker import KenInstallation
    from backend.runtime.native_inference import _private_control
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.owned_runtime import OwnedCodexRuntime
    from backend.runtime.peer_broker import BrokerLimits
    from backend.runtime.subscription_auth import ManagedTokenFile
    from backend.tools.base.db import get_db_path

    if app is None or app.state.live_grants is not live_grants:
        raise ValueError("Owned runtime needs its actual application controller")
    if config.get("max_concurrent", 1) != 1:
        raise ValueError("One active concession per configured authority is required")
    text(config["model"], "native model", 128)
    paths = {
        key: Path(config[key]).resolve(strict=True)
        for key in (
            "codex_binary",
            "code_mode_host",
            "token_file",
            "ken_command",
            "model_cache",
            "workspace_root",
            "cgroup_parent",
        )
    }
    source_root = paths["workspace_root"]
    control = Path(config["control_root"]).absolute()
    authority = dict(config["authority"])
    database = Path(get_db_path()).resolve(strict=True)
    for supplied in (
        path,
        database,
        control.resolve(),
        *[paths[key] for key in paths if key != "workspace_root"],
        *[
            Path(authority[key]).resolve(strict=True)
            for key in ("database", "witness", "mutex")
        ],
    ):
        if supplied.is_relative_to(source_root):
            raise ValueError(
                "Host state and runtime assets must stay outside managed sources"
            )
    if not paths["cgroup_parent"].is_relative_to("/sys/fs/cgroup"):
        raise ValueError("Owned runtime requires an explicit delegated cgroup parent")
    with WitnessedAuthorityJournal(**authority) as journal:
        journal.load()
    _private_control(control)
    source_identity = (database.stat().st_dev, database.stat().st_ino)

    def source_authority(grant_id):
        try:
            current = database.stat()
            return (
                live_grants.allows(grant_id)
                and (current.st_dev, current.st_ino) == source_identity
            )
        except OSError:
            return False

    research = SQLiteResearchStore(database, runtime_authority=source_authority)
    remote_transport = None
    if config.get("remote_publication") is not None:
        from backend.runtime.remote_transport import RemoteTransportConfig

        supplied = config["remote_publication"]
        if not isinstance(supplied, dict) or set(supplied) - {
            "api_base",
            "username",
            "token_file",
            "ca_bundle",
            "resolver",
        }:
            raise ValueError("Unknown remote publication operator configuration")
        remote_network = NativeNetwork.inspect(
            resolver=supplied.get(
                "resolver", config.get("resolver", "/etc/resolv.conf")
            ),
            ca_bundle=supplied.get(
                "ca_bundle",
                config.get("ca_bundle", "/etc/ssl/certs/ca-certificates.crt"),
            ),
        )
        token_path = Path(supplied["token_file"]).resolve(strict=True)
        for host_path in (
            token_path,
            Path(remote_network.ca_bundle.path),
            Path(remote_network.resolver.path),
        ):
            if host_path.is_relative_to(source_root):
                raise ValueError(
                    "Remote credentials and trust must stay outside managed sources"
                )
        remote_transport = RemoteTransportConfig(
            supplied["api_base"], supplied["username"], token_path, remote_network
        )
        remote_transport.token()
    native = OwnedCodexRuntime(
        app=app,
        research=research,
        live_grants=live_grants,
        authority=authority,
        cgroup_parent=paths["cgroup_parent"],
        control_root=control,
        asset=CodexAsset.inspect(paths["codex_binary"]),
        code_host=CodexAsset.inspect(paths["code_mode_host"]),
        installation=KenInstallation.inspect(paths["ken_command"]),
        model_cache=paths["model_cache"],
        network=NativeNetwork.inspect(
            resolver=config.get("resolver", "/etc/resolv.conf"),
            ca_bundle=config.get("ca_bundle", "/etc/ssl/certs/ca-certificates.crt"),
        ),
        token_source=ManagedTokenFile(paths["token_file"]),
        broker_limits=BrokerLimits(**config["broker_limits"]),
        model=config["model"],
        reasoning_effort=config.get("reasoning_effort", "low"),
        web_search=config.get("web_search", "live"),
        remote_transport=remote_transport,
        development_checks=parse_development_checks(
            config.get("development_checks", [])
        ),
    )
    app.state.runtime_research_store = research
    return RuntimeService(
        SQLiteRunStore(database),
        research,
        live_grants,
        native,
        workspaces=WorkspaceRegistry(database, source_root),
        legacy_active=_legacy_project_active,
        control_root=control,
        max_concurrent=1,
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
        project_turn_limit=config.get("project_turn_limit", 20),
        project_token_limit=config.get("project_token_limit", 4000000),
    )

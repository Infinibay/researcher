"""Serving-only runtime composition from explicit host configuration."""

import json
import os
from pathlib import Path

from backend.research.sqlite_store import SQLiteResearchStore
from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.service import RuntimeService, WorkspaceRegistry
from backend.runtime.sqlite_runs import SQLiteRunStore


def _legacy_project_active(project_id):
    """Observe actual registered legacy threads for every serving native factory; absence of a flow label alone is insufficient."""
    from backend.api.flow_manager import flow_manager

    return flow_manager.is_project_running(project_id)


def configured_storage_guard(config=None, path=None):
    """Check every configured write root before startup writes; return a new-work gate.

    Legacy hosts without a storage policy remain explicitly unbounded. A supplied
    policy must have its original receipt; losing a mount never creates new data.
    """
    from backend.api.config import UPLOAD_DIR
    from backend.runtime.contracts import RunConflict
    from backend.runtime.storage_volume import configured_storage
    from backend.tools.base.db import get_db_path

    if config is None:
        name = os.environ.get('INFINIBAY_RUNTIME_CONFIG')
        if not name:
            return None
        path = Path(name).resolve(strict=True)
        if path.stat().st_size > 65536:
            raise ValueError('Runtime configuration is too large')
        config = json.loads(path.read_text())
    if 'storage' not in config and 'storage_receipt' not in config:
        return None
    if not os.environ.get('INFINIBAY_AUTH_DIR'):
        raise ValueError('Bounded storage requires an explicit local authentication directory')
    paths = (
        path, get_db_path(), config['workspace_root'], config['control_root'], UPLOAD_DIR,
        os.environ.get('INFINIBAY_DATA', '.data'), os.environ['INFINIBAY_AUTH_DIR'],
        *[config['authority'][key] for key in ('database', 'witness', 'mutex')],
    )
    volume = configured_storage(config, paths)

    def guard():
        """Reject new work with a useful message while leaving Stop independent of disk headroom."""
        try:
            volume.check(paths, admission=True)
        except (ValueError, OSError) as error:
            raise RunConflict(
                'El almacenamiento original no está disponible o cambió. '
                'No se inició trabajo nuevo; revisa el volumen antes de continuar.'
            ) from error

    return guard


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
    if not isinstance(config, dict):
        raise ValueError("Runtime configuration must be a JSON object")
    profile = config.get("runtime_profile")
    if profile == "owned-codex-v1":
        return _configured_owned(config, path, live_grants, app)
    raise ValueError(
        "An explicit runtime_profile='owned-codex-v1' is required; "
        "the legacy launcher was retired. Migrate host paths and authority "
        "using docs/architecture/owned-product-runtime.md; no fallback is permitted."
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
    storage_guard = configured_storage_guard(config, path)
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
        """Accept grants only while the original business database remains bound."""
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
        storage_guard=storage_guard,
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

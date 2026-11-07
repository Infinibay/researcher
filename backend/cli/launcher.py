"""Run an installed local API/web pair; explicit bootstrap and the API lifespan retain ownership of storage initialization and native runtime admission."""

import argparse
import importlib.util
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import quote


def prerequisites(*, api_only: bool, port: int, workspace: Path) -> list[tuple]:
    """Inspect existing data/dependencies without writes, installs, provider setup or claiming account/Ken/runtime readiness."""
    from backend.config.paths import resolve_database_path

    database = resolve_database_path(workspace)
    uri = "file:" + quote(database, safe="/") + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            recognized = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if recognized is None:
                raise ValueError("No initialized schema_migrations history")
    except (sqlite3.DatabaseError, ValueError) as error:
        raise ValueError(
            "Database startup refused. For a NEW installation run researcher-bootstrap "
            "init-db --database PATH; otherwise verify/restore existing data."
        ) from error
    if not 1 <= port <= 65535:
        raise ValueError("API port must be between 1 and 65535")
    if not api_only and port != 8000:
        raise ValueError("The web proxy targets port8000; use --api-only for another API port")
    missing = [name for name in ("uvicorn", "fastapi", "httpx", "mcp") if importlib.util.find_spec(name) is None]
    if missing:
        raise ValueError("Missing installed Python dependencies: " + ", ".join(missing) + ". Run uv sync --locked explicitly before starting.")
    os.environ["INFINIBAY_DB"] = database
    commands = [("API", [sys.executable, "-m", "uvicorn", "backend.api.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port)], workspace)]
    if not api_only:
        node = shutil.which(os.environ.get("RESEARCHER_NODE", "node"))
        vite = workspace / "frontend/node_modules/vite/bin/vite.js"
        if node is None or not vite.is_file():
            raise ValueError("Frontend prerequisites are missing. Install Node and run npm ci in frontend explicitly, or use --api-only.")
        commands.append(("web", [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"], workspace / "frontend"))
    return commands


def run_services(services: list[tuple], *, grace: float = 15) -> int:
    """Bound native services as one kernel group; inspection-only launches retain original child handles without native admission."""
    if config_path := os.environ.get('INFINIBAY_RUNTIME_CONFIG'):
        from backend.runtime.host_installation import _read_json
        from backend.runtime.service_process import DEFAULT_SERVICE_LIMITS, run_bounded_services

        try:
            config = _read_json(config_path)
            return run_bounded_services(services,cgroup_parent=config['cgroup_parent'],
                limits=config.get('service_limits',DEFAULT_SERVICE_LIMITS),state_dir=services[0][2],grace=grace)
        except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
            print(f'Bounded service launch refused: {error}. Inspect retained service and native recovery state.',file=sys.stderr)
            return 1
    children = []
    requested = 0

    def request_stop(number, _frame):
        """Defer signal cleanup until every in-flight Popen has returned its original handle."""
        nonlocal requested
        requested = 128 + number

    previous = {number: signal.signal(number, request_stop) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        for label, command, directory in services:
            if requested:
                return requested
            print(f"Starting {label} on loopback; its process validates readiness.", flush=True)
            children.append(subprocess.Popen(command, cwd=directory))
        while not requested:
            for child in children:
                code = child.poll()
                if code is not None:
                    return code if code >= 0 else 128 - code
            time.sleep(0.1)
        return requested
    except OSError as error:
        print(f"Service launch failed: {error}. No setup or retry was attempted.", file=sys.stderr)
        return 1
    finally:
        try:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
            deadline = time.monotonic() + grace
            for child in reversed(children):
                try:
                    child.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    print("A launched service exceeded shutdown grace; terminating that original child. Inspect native recovery state before resuming work.", file=sys.stderr)
                    child.kill()
                    child.wait(timeout=5)
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def main(argv=None) -> int:
    """Validate then start installed services, or show read-only checks/help; no .env execution, bootstrap, model provisioning or automatic native admission."""
    parser = argparse.ArgumentParser(description="Start already-installed local services. Setup is explicit; native account/model/Ken configuration belongs to the admitting host. Shell .env files and old .pids are not used.")
    parser.add_argument("--api-only", action="store_true", help="Run only the API; no source frontend or Node needed")
    parser.add_argument("--check", action="store_true", help="Read-only prerequisite inspection; does not prove host/account/Ken/runtime readiness")
    parser.add_argument("--port", type=int, default=8000, help="API loopback port; a different port requires --api-only")
    parser.add_argument('--installation', type=Path, help='Run a prepared native host installation; serves compiled web assets through the API')
    options = parser.parse_args(argv)
    try:
        workspace = Path.cwd()
        if options.installation is not None:
            from backend.runtime.host_installation import host_environment

            os.environ.update(host_environment(options.installation))
            workspace = options.installation.resolve(strict=True) / 'service'
            if not workspace.is_dir():
                raise ValueError('Prepared service directory is missing; inspect the installation')
        services = prerequisites(api_only=options.api_only or options.installation is not None, port=options.port, workspace=workspace)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Startup refused: {error}", file=sys.stderr)
        return 1
    if os.environ.get("INFINIBAY_RUNTIME_CONFIG"):
        print("Native runtime requested; API startup must validate its host configuration. This check does not prove account or Ken readiness.", flush=True)
    else:
        print("Inspection mode: no native runtime configured. Generation/admission remains unavailable; configure INFINIBAY_RUNTIME_CONFIG to enable it.", flush=True)
    if options.check:
        print("Read-only prerequisite checks passed; no services started.")
        return 0
    return run_services(services)


if __name__ == "__main__":
    raise SystemExit(main())

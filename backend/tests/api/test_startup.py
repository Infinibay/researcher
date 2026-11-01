"""App discovery and serving must not implicitly spend model quota."""

import os
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient


def test_importing_api_does_not_create_a_database_or_start_maintenance(tmp_path):
    database = tmp_path / "unopened" / "project.db"
    program = """
import sys, threading
from pathlib import Path
from pytest_socket import disable_socket
disable_socket(allow_unix_socket=True)
import backend.api.main
assert not Path(sys.argv[1]).exists(), 'Import created a database'
assert not any(t.name.startswith('infinibay-') for t in threading.enumerate()), 'Import started maintenance'
"""
    env = {key: value for key, value in os.environ.items() if "API_KEY" not in key}
    env.update(
        INFINIBAY_DB=str(database),
        INFINIBAY_LLM_MODEL="",
        CREWAI_TELEMETRY_DISABLED="true",
        OTEL_SDK_DISABLED="true",
    )
    result = subprocess.run(
        [sys.executable, "-c", program, str(database)],
        capture_output=True, text=True, env=env, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_serving_opens_explicitly_initialized_database_without_probing_a_model(tmp_path, monkeypatch):
    from backend.api.main import create_app
    from backend.config import llm, model_capabilities

    class UnexpectedInference(BaseException):
        pass

    def forbidden_probe(*args, **kwargs):
        raise UnexpectedInference("Serving must not call a model")

    monkeypatch.setattr(model_capabilities, "get_model_capabilities", lambda: SimpleNamespace(probed=False))
    monkeypatch.setattr(model_capabilities, "probe_model", forbidden_probe)
    monkeypatch.setattr(llm, "get_litellm_params", lambda: {"model": "openai/not-a-real-model"})
    database = tmp_path / "fresh.db"
    monkeypatch.setenv("INFINIBAY_DB", str(database))

    from backend.runtime.bootstrap import initialize_database

    app = create_app()
    assert not database.exists(), "App construction must not initialize persistence"
    initialize_database(database)
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health/ready").json() == {"ready": True}
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone() == (0,)


def test_migration_failure_is_not_hidden_by_the_api_lifespan(monkeypatch):
    from backend.api.main import create_app
    from backend.tools.base import db

    app = create_app()

    def fail(**kwargs):
        raise RuntimeError("schema migration failed")

    monkeypatch.setattr(db, "ensure_migrations", fail)
    with pytest.raises(RuntimeError, match="schema migration failed"), TestClient(app):
        pass


def test_server_entry_uses_loopback_factory_without_model_initialization(monkeypatch):
    from backend.api import run

    class UnexpectedInference(BaseException):
        pass

    def fail():
        raise UnexpectedInference("Server entry tried to initialize a model")

    launch = []
    monkeypatch.setattr(run, "setup_llm_environment", fail, raising=False)
    monkeypatch.setattr(run, "setup_file_logging", lambda: None)
    monkeypatch.setattr(run.uvicorn, "run", lambda *args, **kwargs: launch.append((args, kwargs)))

    run.main()

    assert launch[0][0] == ("backend.api.main:create_app",)
    assert launch[0][1]["factory"] is True
    assert launch[0][1]["host"] == "127.0.0.1"


async def test_lifespan_reconciles_active_flows_even_on_context_failure(monkeypatch):
    from backend.api.main import create_app, lifespan

    app = create_app()
    from backend.api.flow_manager import flow_manager

    stopped = []
    monkeypatch.setattr(flow_manager, "_flows", {42: object()})
    monkeypatch.setattr(flow_manager, "stop_project_flow", stopped.append)

    with pytest.raises(RuntimeError, match="server failure"):
        async with lifespan(app):
            raise RuntimeError("server failure")

    assert stopped == [42]

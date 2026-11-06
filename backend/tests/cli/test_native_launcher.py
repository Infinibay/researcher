"""Native startup uses existing data and direct owned child handles; setup, inference and old PID files are outside a normal launch."""

import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest


def initialized(path):
    """Create a minimal recognized read-only preflight fixture, not a current native runtime database."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO schema_migrations VALUES(54)")


def test_actual_script_help_and_check_do_not_source_env_or_run_setup(tmp_path):
    """Shell metacharacters in .env and old .pids remain inert; --check validates prerequisites without spawning services or installing anything."""
    root = Path(__file__).resolve().parents[3]
    shutil.copyfile(root / "start.sh", tmp_path / "start.sh")
    database = tmp_path / "source.db"
    initialized(database)
    before = database.read_bytes()
    marker = tmp_path / "shell-env-executed"
    (tmp_path / ".env").write_text("touch " + str(marker) + "\n")
    (tmp_path / ".pids").write_text("1\n")
    environment = dict(os.environ, INFINIBAY_DB=str(database), PYTHONPATH=str(root), RESEARCHER_PYTHON=sys.executable)
    helped = subprocess.run(["bash", str(tmp_path / "start.sh"), "--help"], env=environment, capture_output=True, text=True, timeout=10)
    assert helped.returncode == 0, helped.stdout + helped.stderr
    checked = subprocess.run(["bash", str(tmp_path / "start.sh"), "--api-only", "--check"], env=environment, capture_output=True, text=True, timeout=10)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "inspection" in checked.stdout.lower()
    assert not marker.exists()
    assert (tmp_path / ".pids").read_text() == "1\n"
    assert database.read_bytes() == before


def test_launcher_check_refuses_missing_database_without_creating_parent(tmp_path, monkeypatch, capsys):
    """A normal start never initializes missing/empty state or silently repairs a deployment."""
    from backend.cli.launcher import main

    missing = tmp_path / "missing-parent/source.db"
    monkeypatch.setenv("INFINIBAY_DB", str(missing))
    assert main(["--api-only", "--check"]) == 1
    assert not missing.parent.exists()
    assert "init-db" in capsys.readouterr().err


def test_children_stop_on_service_exit_and_preserve_an_unrelated_process(tmp_path):
    """Real subprocess handles close the still-running peer on exit and never consult old PID state to signal an unrelated child."""
    from backend.cli.launcher import run_services

    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    child_pid = tmp_path / "peer.pid"
    peer = [sys.executable, "-c", "import os,time;from pathlib import Path;Path(" + repr(str(child_pid)) + ").write_text(str(os.getpid()));time.sleep(30)"]
    failure = [sys.executable, "-c", "import time;time.sleep(.2);raise SystemExit(7)"]
    try:
        assert run_services([("peer", peer, tmp_path), ("failing", failure, tmp_path)], grace=2) == 7
        assert unrelated.poll() is None
        pid = int(child_pid.read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_launcher_sigterm_drains_its_actual_child_and_preserves_old_pid_file(tmp_path):
    """An OS signal to the launcher stops its original child, returns143 and leaves an unrelated old PID/sentinel untouched."""
    child_pid = tmp_path / "child.pid"
    child_code = "import os,time;from pathlib import Path;Path(" + repr(str(child_pid)) + ").write_text(str(os.getpid()));time.sleep(30)"
    invocation = "from backend.cli.launcher import run_services;from pathlib import Path;raise SystemExit(run_services([('fixture'," + repr([sys.executable, "-c", child_code]) + ",Path(" + repr(str(tmp_path)) + "))],grace=2))"
    sentinel = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    old = tmp_path / ".pids"
    old.write_text(str(sentinel.pid))
    owner = subprocess.Popen([sys.executable, "-c", invocation], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not child_pid.exists():
            assert owner.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        owner.send_signal(signal.SIGTERM)
        owner.communicate(timeout=5)
        assert owner.returncode == 143
        assert sentinel.poll() is None and old.read_text() == str(sentinel.pid)
        with pytest.raises(ProcessLookupError):
            os.kill(int(child_pid.read_text()), 0)
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.communicate(timeout=5)
        sentinel.terminate()
        sentinel.wait(timeout=5)

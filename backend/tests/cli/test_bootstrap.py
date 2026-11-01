"""Exercise explicit installation through the public command, without inference."""

import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "backend.cli.bootstrap", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def authority(tmp_path):
    result = cli(
        "init-authority",
        "--database-dir",
        tmp_path / "database",
        "--witness-dir",
        tmp_path / "witness",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_init_db_creates_private_usable_database_and_refuses_second_init(tmp_path):
    path = tmp_path / "nested" / "research.db"
    result = cli("init-db", "--database", path)
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('keep')")
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    before = path.read_bytes()
    repeat = cli("init-db", "--database", path)
    assert repeat.returncode != 0
    assert path.read_bytes() == before
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM projects").fetchall() == [("keep",)]


@pytest.mark.parametrize("kind", ["empty", "symlink"])
def test_init_db_never_adopts_existing_path(tmp_path, kind):
    target = tmp_path / "original"
    target.write_bytes(b"retain")
    path = tmp_path / "source.db"
    path.touch() if kind == "empty" else path.symlink_to(target)
    result = cli("init-db", "--database", path)
    assert result.returncode != 0
    assert target.read_bytes() == b"retain"
    assert path.read_bytes() == (b"" if kind == "empty" else b"retain")


def test_explicit_authority_supports_real_commit_and_reopen_without_source_db(tmp_path):
    from backend.runtime.authority_journal import WitnessedAuthorityJournal

    config = authority(tmp_path)
    for key in ("database", "witness", "mutex"):
        path = Path(config[key])
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert path.stat().st_uid == os.getuid()
    with WitnessedAuthorityJournal(**config) as journal:
        initial = journal.load()
        assert initial.sequence == 0 and initial.records == {}
        journal.commit(initial, transition_id="first", puts={"fence": 1})
    with WitnessedAuthorityJournal(**config) as journal:
        assert journal.load().records == {"fence": 1}
    assert not (tmp_path / "source.db").exists()
    first = {
        key: Path(config[key]).read_bytes() for key in ("database", "witness", "mutex")
    }
    again = cli(
        "init-authority",
        "--database-dir",
        tmp_path / "database",
        "--witness-dir",
        tmp_path / "witness",
    )
    assert again.returncode != 0
    assert all(
        Path(config[key]).read_bytes() == contents for key, contents in first.items()
    )


@pytest.mark.parametrize("kind", ["equal", "nested"])
def test_authority_roots_must_not_overlap(tmp_path, kind):
    database = tmp_path / "database"
    witness = database if kind == "equal" else database / "witness"
    result = cli("init-authority", "--database-dir", database, "--witness-dir", witness)
    assert result.returncode != 0
    assert not database.exists()


def test_missing_witness_is_not_reinitialized(tmp_path):
    from backend.runtime.authority_journal import (
        AuthorityUncertain,
        WitnessedAuthorityJournal,
    )

    config = authority(tmp_path)
    Path(config["witness"]).unlink()
    before = Path(config["database"]).read_bytes()
    with pytest.raises(AuthorityUncertain), WitnessedAuthorityJournal(**config):
        pass
    again = cli(
        "init-authority",
        "--database-dir",
        tmp_path / "database",
        "--witness-dir",
        tmp_path / "witness",
    )
    assert again.returncode != 0
    assert not Path(config["witness"]).exists()
    assert Path(config["database"]).read_bytes() == before


def test_partial_authority_failure_is_preserved_and_cannot_be_adopted(
    tmp_path, monkeypatch
):
    from backend.runtime import bootstrap
    from backend.runtime.authority_journal import (
        AuthorityUncertain,
        WitnessedAuthorityJournal,
    )

    def interrupted():
        raise RuntimeError("injected creation failure")

    monkeypatch.setattr(bootstrap, "boot_id", interrupted)
    database, witness = tmp_path / "database", tmp_path / "witness"
    with pytest.raises(RuntimeError, match="injected creation failure"):
        bootstrap.initialize_authority(database_dir=database, witness_dir=witness)
    db_path = database / "authority.db"
    assert db_path.exists() and (witness / "authority.log").read_bytes() == b""
    before = db_path.read_bytes()
    with pytest.raises(FileExistsError):
        bootstrap.initialize_authority(database_dir=database, witness_dir=witness)
    assert db_path.read_bytes() == before
    with sqlite3.connect(db_path) as conn:
        authority_id = conn.execute(
            "SELECT authority_id FROM authority_meta"
        ).fetchone()[0]
    with (
        pytest.raises(AuthorityUncertain),
        WitnessedAuthorityJournal(
            database=db_path,
            witness=witness / "authority.log",
            mutex=witness / "authority.lock",
            authority_id=authority_id,
        ) as journal,
    ):
        journal.load()


def test_explicit_cli_database_serves_twice_and_preserves_user_data(
    tmp_path, monkeypatch
):
    from starlette.testclient import TestClient

    from backend.api.main import create_app

    path = tmp_path / "installation" / "source.db"
    result = cli("init-db", "--database", path)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('preserve across serving')")
    monkeypatch.setenv("INFINIBAY_DB", str(path))
    monkeypatch.delenv("INFINIBAY_RUNTIME_CONFIG", raising=False)
    monkeypatch.setattr("backend.api.run.setup_file_logging", lambda: None)
    for _ in range(2):
        app = create_app()
        with TestClient(app, base_url="http://localhost") as client:
            response = client.get("/api/health/ready")
            assert response.status_code == 200 and response.json() == {"ready": True}
        assert app.state.local_access.key_file is None
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM projects").fetchall() == [
            ("preserve across serving",)
        ]

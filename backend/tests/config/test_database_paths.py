"""Choose one database without hiding existing project data."""

import pytest


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INFINIBAY_DB", raising=False)
    monkeypatch.delenv("INFINIBAY_DB_PATH", raising=False)
    return tmp_path


def test_new_workspace_uses_data_directory_without_creating_files(workspace):
    from backend.config.paths import resolve_database_path

    assert resolve_database_path() == str(workspace / ".data" / "infinibay.db")
    assert not (workspace / ".data").exists()


def test_existing_legacy_database_is_selected_without_moving_it(workspace):
    from backend.config.paths import resolve_database_path

    legacy = workspace / ".researcher" / "researcher.db"
    legacy.parent.mkdir()
    legacy.write_bytes(b"existing data")

    assert resolve_database_path() == str(legacy)
    assert legacy.read_bytes() == b"existing data"
    assert not (workspace / ".data").exists()


def test_multiple_databases_require_an_explicit_choice(workspace):
    from backend.config.paths import resolve_database_path

    paths = [workspace / ".data/infinibay.db", workspace / ".researcher/researcher.db"]
    for path in paths:
        path.parent.mkdir()
        path.write_bytes(b"preserve me")

    with pytest.raises(RuntimeError, match="INFINIBAY_DB") as exc:
        resolve_database_path()

    assert all(str(path) in str(exc.value) for path in paths)
    assert all(path.read_bytes() == b"preserve me" for path in paths)
    assert resolve_database_path(explicit_path=paths[0]) == str(paths[0])


def test_aliases_of_the_same_database_are_not_ambiguous(workspace):
    from backend.config.paths import resolve_database_path

    original = workspace / ".data/infinibay.db"
    original.parent.mkdir()
    original.touch()
    legacy = workspace / ".researcher/researcher.db"
    legacy.parent.mkdir()
    legacy.symlink_to(original)

    assert resolve_database_path() == str(original)


@pytest.mark.parametrize("variable", ["INFINIBAY_DB", "INFINIBAY_DB_PATH"])
def test_settings_and_database_connections_use_the_same_override(workspace, monkeypatch, variable):
    from backend.config.settings import Settings
    from backend.tools.base.db import get_db_path

    monkeypatch.setenv(variable, "chosen/project.db")
    expected = str(workspace / "chosen/project.db")

    assert Settings().DB_PATH == expected
    assert get_db_path() == expected


def test_explicit_override_wins_over_legacy_detection(workspace, monkeypatch):
    from backend.config.paths import resolve_database_path

    monkeypatch.setenv("INFINIBAY_DB", "other.db")
    assert resolve_database_path(explicit_path="chosen.db") == str(workspace / "chosen.db")

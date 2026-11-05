"""CLI work must not be preceded by an unrelated model capability probe."""

import sqlite3

import pytest
from click.testing import CliRunner


def test_single_prompt_requires_explicit_owner_context_before_runtime_work(monkeypatch):
    """No source DB/model probe is needed to reject an unscoped terminal instruction."""
    from backend.cli import main as cli

    def forbidden(*args, **kwargs):
        """Detect any old local startup or network work before owner selection."""
        raise AssertionError("Unscoped startup work")

    monkeypatch.setattr(cli, "_init_db", forbidden)
    monkeypatch.setattr(cli, "OwnerClient", forbidden)
    result = CliRunner().invoke(cli.main, ["--prompt", "Explain this task"])
    assert result.exit_code == 2
    assert "--project-id" in result.output


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_cli_startup_never_initializes_missing_or_empty_database(
    tmp_path, monkeypatch, kind
):
    from backend.cli.main import _init_db

    path = tmp_path / "not-created" / "source.db"
    if kind == "empty":
        path.parent.mkdir()
        path.touch()
    monkeypatch.setenv("INFINIBAY_DB", str(path))
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        _init_db()
    if kind == "missing":
        assert not path.parent.exists()
    else:
        assert path.read_bytes() == b""

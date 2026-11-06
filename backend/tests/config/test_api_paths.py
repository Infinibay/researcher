"""Packaged API storage belongs to the chosen data directory, never site-packages."""

import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize("selection", ["workspace", "data", "existing_uploads"])
def test_upload_selection_preserves_existing_files_without_initializing_storage(
    tmp_path, monkeypatch, selection
):
    """Resolve cold configuration away from its package and preserve an explicit old root."""
    from backend.api import config

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INFINIBAY_DATA", raising=False)
    monkeypatch.delenv("INFINIBAY_UPLOAD_BASE_DIR", raising=False)
    expected = tmp_path / ".data/uploads"
    old = tmp_path / "previous-location"
    old.mkdir()
    receipt = old / "retained.txt"
    receipt.write_bytes(b"Existing attachment: do not move")
    if selection != "workspace":
        monkeypatch.setenv("INFINIBAY_DATA", "selected-data")
        expected = tmp_path / "selected-data/uploads"
    if selection == "existing_uploads":
        monkeypatch.setenv("INFINIBAY_UPLOAD_BASE_DIR", str(old))
        expected = old

    values = runpy.run_path(config.__file__)

    assert Path(values["UPLOAD_DIR"]) == expected
    assert receipt.read_bytes() == b"Existing attachment: do not move"
    assert not (tmp_path / ".data").exists()
    assert not (tmp_path / "selected-data").exists()


def test_installed_static_assets_can_be_selected_outside_working_directory(
    tmp_path, monkeypatch
):
    """A service may serve built assets from an immutable installation directory."""
    from backend.api import config

    monkeypatch.chdir(tmp_path)
    selected = tmp_path / "installed/frontend/dist"
    monkeypatch.setenv("INFINIBAY_STATIC_DIR", str(selected))
    values = runpy.run_path(config.__file__)
    assert Path(values["STATIC_DIR"]) == selected
    assert not selected.exists()

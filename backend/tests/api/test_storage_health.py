"""Installed API health follows actual attachment storage without implicit setup."""

import pytest


@pytest.mark.parametrize("kind", ["existing", "not_created", "blocked_by_file"])
def test_health_uses_selected_upload_storage_without_creating_it(
    client, monkeypatch, tmp_path, kind
):
    """Report a usable new root or an actual blocker independently of historical /research."""
    from backend.api import config

    root = tmp_path / "attachments"
    if kind == "existing":
        root.mkdir()
    elif kind == "blocked_by_file":
        root.write_bytes(b"Preserve this existing non-directory")
    monkeypatch.setattr(config, "UPLOAD_DIR", str(root))
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"
    assert body["filesystem"] == ("error" if kind == "blocked_by_file" else "ok")
    assert body["status"] == ("degraded" if kind == "blocked_by_file" else "healthy")
    if kind == "not_created":
        assert not root.exists()
    elif kind == "blocked_by_file":
        assert root.read_bytes() == b"Preserve this existing non-directory"

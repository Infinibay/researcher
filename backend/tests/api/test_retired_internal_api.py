"""Old pod commands cannot bypass native identity, review, publication or continuity contracts through owner-authenticated routes."""

from starlette.testclient import TestClient

from backend.tests.api.test_local_access import owner_app, pair

__all__ = ["owner_app"]


def test_owner_has_no_parallel_internal_command_surface(owner_app, seeded_project, db_conn):
    """Even a paired owner cannot revive old pod commands; retained records and native interfaces remain available."""
    app, _, _ = owner_app
    endpoints = (
        ("POST", "/ask-team-lead"),
        ("POST", "/ask-project-lead"),
        ("POST", "/chat/send"),
        ("POST", "/query"),
        ("POST", "/git/create-pr"),
        ("POST", "/session-note"),
        ("GET", "/session-note"),
        ("POST", "/findings"),
        ("GET", "/findings"),
        ("POST", "/findings/1/validate"),
        ("POST", "/findings/1/reject"),
        ("POST", "/tasks/1/approve"),
        ("POST", "/tasks/1/reject"),
    )
    with TestClient(app, base_url="http://localhost") as client:
        csrf = pair(client).json()["csrf_token"]
        before = tuple(db_conn.iterdump())
        paths = client.get("/openapi.json").json()["paths"]
        assert not any(path.startswith("/api/internal") for path in paths)
        assert "/api/research-tools/task-workspace/tasks" in paths
        assert "/api/research-tools/knowledge-query" in paths
        for method, suffix in endpoints:
            response = client.request(
                method, "/api/internal" + suffix,
                headers={"X-Researcher-CSRF": csrf},
                params={"project_id": 1, "agent_id": "historical"},
                json={} if method == "POST" else None,
            )
            # An installed SPA GET fallback yields 405 for unknown POST paths.
            assert response.status_code in {404, 405}, (method, suffix, response.text)
        assert client.get("/api/projects").status_code == 200
        assert tuple(db_conn.iterdump()) == before

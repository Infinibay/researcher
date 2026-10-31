"""Delivery authority is separate from run-scoped business credentials."""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_default_api_refuses_anonymous_project_and_internal_sql_reads(seeded_project):
    from backend.api.main import create_app

    with TestClient(create_app(), base_url="http://localhost") as client:
        assert client.get("/api/projects").status_code == 401
        assert (
            client.post(
                "/api/internal/query", json={"sql_query": "SELECT * FROM projects"}
            ).status_code
            == 401
        )
        assert client.get("/openapi.json").status_code == 401
        assert client.get("/api/health/ready").json() == {"ready": True}


def test_default_websocket_refuses_anonymous_project_subscription(seeded_project):
    from backend.api.main import create_app

    with TestClient(create_app(), base_url="http://localhost") as client:
        with (
            pytest.raises(WebSocketDisconnect) as denied,
            client.websocket_connect("ws://localhost/ws?project_id=1"),
        ):
            pass
        assert denied.value.code == 1008


def test_default_api_refuses_rebound_host_and_hostile_browser_origin(seeded_project):
    from backend.api.main import create_app

    with TestClient(create_app(), base_url="http://localhost") as client:
        assert (
            client.get("/api/projects", headers={"Host": "rebound.example"}).status_code
            == 400
        )
        assert (
            client.get(
                "/api/projects", headers={"Origin": "https://hostile.example"}
            ).status_code
            == 403
        )


@pytest.fixture
def owner_app(_isolated_db):
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    now = [1000.0]
    access = LocalAccess(
        pairing_key="fixture-owner-code-that-is-not-a-real-secret",
        clock=lambda: now[0],
        session_seconds=10,
    )
    return create_app(access=access), access, now


def pair(client):
    response = client.post(
        "/api/session",
        json={"code": "fixture-owner-code-that-is-not-a-real-secret"},
        headers={"X-Researcher-Client": "web"},
    )
    assert response.status_code == 200, response.text
    return response


def test_pairing_sets_private_cookie_and_csrf_allows_owner_work(
    owner_app, seeded_project
):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/session").json() == {"authenticated": False}
        assert (
            client.post(
                "/api/session",
                json={"code": "incorrect"},
                headers={"X-Researcher-Client": "web"},
            ).status_code
            == 401
        )
        response = pair(client)
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert "Domain=" not in response.headers["set-cookie"]
        assert "session" not in response.json()  # Cookie credential is never JSON.
        csrf = response.json()["csrf_token"]
        assert client.get("/api/projects").status_code == 200
        denied = client.post("/api/projects", json={"name": "Blocked"})
        assert denied.status_code == 403
        created = client.post(
            "/api/projects", json={"name": "Owned"}, headers={"X-Researcher-CSRF": csrf}
        )
        assert created.status_code == 201, created.text
        assert client.get("/api/session").json()["csrf_token"] == csrf


def test_logout_revokes_cookie_even_if_a_copy_is_reused(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        csrf = pair(client).json()["csrf_token"]
        cookie = client.cookies.get("researcher_owner")
        assert (
            client.delete(
                "/api/session", headers={"X-Researcher-CSRF": csrf}
            ).status_code
            == 204
        )
        assert (
            client.get(
                "/api/projects", headers={"Cookie": "researcher_owner=" + cookie}
            ).status_code
            == 401
        )


def test_owner_session_expires_by_monotonic_clock_and_does_not_refresh_on_read(
    owner_app,
):
    app, _, now = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        pair(client)
        now[0] += 9
        assert client.get("/api/projects").status_code == 200
        now[0] += 2
        assert client.get("/api/projects").status_code == 401
        assert client.get("/api/session").json() == {"authenticated": False}


@pytest.mark.parametrize(
    "origin", ["https://hostile.example", "null", "http://localhost:9999"]
)
def test_cookie_and_correct_csrf_do_not_authorize_untrusted_origins(owner_app, origin):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        csrf = pair(client).json()["csrf_token"]
        assert (
            client.get("/api/projects", headers={"Origin": origin}).status_code == 403
        )
        assert (
            client.post(
                "/api/projects",
                json={"name": "Cross origin"},
                headers={"Origin": origin, "X-Researcher-CSRF": csrf},
            ).status_code
            == 403
        )
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "ws://localhost/ws?project_id=1", headers={"Origin": origin}
            ),
        ):
            pass


def test_websocket_accepts_owner_with_trusted_origin_and_closes_after_logout(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        csrf = pair(client).json()["csrf_token"]
        with client.websocket_connect(
            "ws://localhost/ws?project_id=1",
            headers={"Origin": "http://localhost:8000"},
        ) as ws:
            ws.send_text("ping")
            assert ws.receive_json() == {"type": "pong"}
            client.delete("/api/session", headers={"X-Researcher-CSRF": csrf})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()
            assert closed.value.code == 1008


def test_websocket_rejects_missing_origin_and_query_credentials(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        pair(client)
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("ws://localhost/ws?project_id=1"),
        ):
            pass
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "ws://localhost/ws?project_id=1&token=ignored",
                headers={"Origin": "http://localhost:8000"},
            ),
        ):
            pass


def test_bootstrap_is_bounded_and_requires_explicit_json_client(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        assert (
            client.post(
                "/api/session",
                json={"code": "fixture-owner-code-that-is-not-a-real-secret"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/session",
                content=b"x" * 5000,
                headers={
                    "X-Researcher-Client": "web",
                    "Content-Type": "application/json",
                },
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/session",
                data={"code": "fixture-owner-code-that-is-not-a-real-secret"},
                headers={"X-Researcher-Client": "web"},
            ).status_code
            == 415
        )


def test_tool_bearer_cannot_authorize_owner_routes_or_websocket(_isolated_db, db_conn):
    from backend.api.main import create_app
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.tests.research.test_http import credentials
    from backend.tools.base.db import ensure_migrations

    ensure_migrations(_isolated_db)
    db_conn.execute("INSERT INTO projects(id,name) VALUES(101,'Alpha'),(202,'Beta')")
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Policy','pending')"
    )
    db_conn.commit()
    headers = credentials(SQLiteResearchStore(_isolated_db))
    with TestClient(create_app(), base_url="http://localhost") as client:
        assert (
            client.get("/api/research-tools/references", headers=headers).status_code
            == 200
        )
        for path in (
            "/api/projects",
            "/api/events?project_id=202",
            "/api/artifacts?project_id=202",
        ):
            assert client.get(path, headers=headers).status_code == 401
        assert (
            client.post(
                "/api/internal/query",
                headers=headers,
                json={"sql_query": "SELECT * FROM tool_grants"},
            ).status_code
            == 401
        )
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "ws://localhost/ws?project_id=202",
                headers={**headers, "Origin": "http://localhost:8000"},
            ),
        ):
            pass


def test_startup_key_is_private_outside_workspace_and_removed_on_shutdown(
    tmp_path, monkeypatch, _isolated_db
):
    from backend.api.main import create_app

    auth = tmp_path / "control"
    monkeypatch.setenv("INFINIBAY_AUTH_DIR", str(auth))
    app = create_app()
    assert not auth.exists(), "Construction must not create credentials"
    with TestClient(app, base_url="http://localhost") as client:
        key = app.state.local_access.key_file
        assert key.parent == auth
        assert key.stat().st_mode & 0o777 == 0o600
        assert auth.stat().st_mode & 0o777 == 0o700
        code = key.read_text().strip()
        response = client.post(
            "/api/session", json={"code": code}, headers={"X-Researcher-Client": "web"}
        )
        assert response.status_code == 200
        assert code not in client.get("/api/session").text
        assert code not in client.get("/openapi.json").text
    assert not key.exists()


def test_default_owner_guard_covers_every_registered_non_tool_api_route():
    import re

    from backend.api.main import create_app

    app = create_app()
    with TestClient(app, base_url="http://localhost") as client:
        checked = []
        for path, operations in app.openapi()["paths"].items():
            if (
                not path.startswith("/api/")
                or path.startswith(("/api/session", "/api/research-tools/"))
                or path == "/api/health/ready"
            ):
                continue
            path = re.sub(r"\{[^}]+\}", "1", path)
            for method in set(operations) & {"get", "post", "put", "patch", "delete"}:
                response = client.request(method, path, json={})
                assert response.status_code == 401, (method, path, response.text)
                checked.append((method, path))
        assert len(checked) > 60, "Guard must cover the real mounted legacy API"


def test_https_pairing_uses_secure_cookie_and_restart_rejects_old_cookie(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="https://localhost") as client:
        response = pair(client)
        assert "Secure" in response.headers["set-cookie"]
        cookie = client.cookies.get("researcher_owner")
    from backend.api.main import create_app

    with TestClient(create_app(), base_url="https://localhost") as client:
        assert (
            client.get(
                "/api/projects", headers={"Cookie": "researcher_owner=" + cookie}
            ).status_code
            == 401
        )


def test_pairing_does_not_echo_credentials_in_logs_or_body(owner_app, caplog):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        response = pair(client)
        assert "fixture-owner-code-that-is-not-a-real-secret" not in response.text
        assert "fixture-owner-code-that-is-not-a-real-secret" not in caplog.text


def test_trusted_browser_preflight_is_allowed_without_owner_cookie(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        result = client.options(
            "/api/projects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-researcher-csrf",
            },
        )
        assert result.status_code == 200
        assert result.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_invalid_csrf_bytes_are_denied_without_server_error(owner_app):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        pair(client)
        response = client.post(
            "/api/projects",
            json={"name": "Bad proof"},
            headers=[(b"x-researcher-csrf", b"\xff")],
        )
        assert response.status_code == 403


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://127.0.0.1:8000"])
def test_loopback_development_urls_can_pair_owner_session(owner_app, origin):
    app, _, _ = owner_app
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/session",
            json={"code": "fixture-owner-code-that-is-not-a-real-secret"},
            headers={"Origin": origin, "X-Researcher-Client": "web"},
        )
        assert response.status_code == 200


@pytest.mark.parametrize("case", ["workspace", "public", "symlink"])
def test_serving_refuses_unsafe_owner_credential_directories(
    tmp_path, monkeypatch, case
):
    from backend.api.main import create_app

    auth = tmp_path / "control"
    if case == "workspace":
        monkeypatch.chdir(tmp_path)
    elif case == "public":
        auth.mkdir(mode=0o755)
    else:
        private = tmp_path / "private"
        private.mkdir(mode=0o700)
        auth.symlink_to(private, target_is_directory=True)
    monkeypatch.setenv("INFINIBAY_AUTH_DIR", str(auth))
    with (
        pytest.raises(ValueError, match="outside the workspace|private and user-owned"),
        TestClient(create_app(), base_url="http://localhost"),
    ):
        pass


def test_idle_websocket_expires_without_a_client_ping(owner_app):
    app, _, now = owner_app
    with TestClient(app, base_url="http://localhost") as client:
        pair(client)
        with client.websocket_connect(
            "ws://localhost/ws?project_id=1",
            headers={"Origin": "http://localhost:8000"},
        ) as ws:
            now[0] += 11
            with pytest.raises(WebSocketDisconnect) as expired:
                ws.receive_json()
            assert expired.value.code == 1008

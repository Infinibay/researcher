"""Project metadata and historical snapshots survive removal of executable flow wrappers without becoming work authority."""

import json

import pytest
from starlette.testclient import TestClient

from backend.tests.api.test_local_access import owner_app, pair

__all__ = ["owner_app"]


@pytest.fixture
def client(owner_app):
    """Use the native paired owner fixture without the obsolete cleanup monkeypatches in the historical API client."""
    app, _, _ = owner_app
    with TestClient(app, base_url="http://localhost") as connection:
        connection.headers["X-Researcher-CSRF"] = pair(connection).json()["csrf_token"]
        yield connection


def test_owner_project_records_keep_original_description_counts_and_completion_policy(client, db_conn, seeded_project):
    """Actual owner CRUD preserves original intent and project-local counts while generic status changes cannot accept a project."""
    description = "Compare these two examples before assuming the same context."
    created = client.post("/api/projects", json={"name": "Retained project", "description": description})
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert created.json()["total_tasks"] == 0
    epic = client.post("/api/epics", json={"project_id": pid, "title": "Observed work"})
    assert epic.status_code == 201, epic.text
    db_conn.execute("INSERT INTO tasks(project_id,epic_id,type,title,status)VALUES(?,?,'code','Planned work','pending')", (pid, epic.json()["id"]))
    db_conn.commit()
    viewed = client.get(f"/api/projects/{pid}").json()
    assert viewed["total_tasks"] == 1 and viewed["task_counts"] == {"pending": 1}
    assert viewed["total_epics"] == 1
    assert client.put(f"/api/projects/{pid}", json={"description": "A corrected description"}).status_code == 200
    assert db_conn.execute("SELECT original_description FROM projects WHERE id=?", (pid,)).fetchone()[0] == description
    assert client.put(f"/api/projects/{pid}", json={"status": "completed"}).status_code == 409
    assert db_conn.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()[0] != "completed"
    assert db_conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0


def test_snapshot_read_exposes_historical_origin_without_replaying_old_approval(client, db_conn, seeded_project):
    """Old completed/approved labels remain data and do not promise a resumable native checkpoint or change the current project."""
    original = json.dumps({"status": "completed", "user_approved": True, "plan": "Historical plan", "completed_tasks": 9})
    db_conn.execute("INSERT INTO flow_snapshots(project_id,flow_name,current_step,state_json)VALUES(1,'main_project_flow','old-completion',?)", (original,))
    db_conn.commit()
    response = client.get("/api/flow-state/1")
    assert response.status_code == 200, response.text
    assert response.json()["origin"] == "legacy_snapshot"
    assert response.json()["native_resume_supported"] is False
    assert response.json()["state_summary"] == {"status": "completed", "completed_tasks": 9}
    assert client.get("/api/flow-state/9999").status_code == 404
    assert db_conn.execute("SELECT state_json FROM flow_snapshots WHERE project_id=1").fetchone()[0] == original
    assert db_conn.execute("SELECT status FROM projects WHERE id=1").fetchone()[0] == "new"
    assert db_conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0

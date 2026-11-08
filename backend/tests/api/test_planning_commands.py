"""Owner planning mutations must recover exact original resources after a repeated delivery, without admitting work."""

import sqlite3

import pytest

from backend.tests.api.test_project_records import client, owner_app

__all__ = ["client", "owner_app"]


def test_repeated_group_creation_recovers_original_identity(client, db_conn, seeded_project):
    """The same owner operation must not duplicate a work group when its original response is unavailable."""
    request = {"project_id": 1, "title": "Revisar mediciones", "description": "Comparar entrada y salida.", "operation_key": "group-response-lost"}
    first = client.post("/api/epics", json=request)
    second = client.post("/api/epics", json=request)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db_conn.execute("SELECT count(*) FROM epics WHERE project_id=1 AND title=?", (request["title"],)).fetchone()[0] == 1
    assert db_conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0


def test_repeated_milestone_creation_recovers_original_identity(client, db_conn, seeded_project):
    """The original project/group must retain one milestone when an identical owner request is repeated."""
    group = client.post("/api/epics", json={"project_id": 1, "title": "Mediciones", "operation_key": "initial-group"})
    assert group.status_code == 201
    request = {"epic_id": group.json()["id"], "title": "Datos contrastados", "operation_key": "milestone-response-lost"}
    first = client.post("/api/milestones", json=request)
    second = client.post("/api/milestones", json=request)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db_conn.execute("SELECT count(*) FROM milestones WHERE epic_id=?", (request["epic_id"],)).fetchone()[0] == 1
    assert db_conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0


def test_original_key_rejects_changed_content_and_another_kind(client, db_conn, seeded_project):
    """A valid receipt cannot authorize a different group title or be reused for another operation kind."""
    body = {"project_id": 1, "title": "Original", "operation_key": "same-owner-key"}
    group = client.post("/api/epics", json=body).json()
    assert client.post("/api/epics", json={**body, "title": "Different"}).status_code == 409
    assert client.post("/api/milestones", json={"project_id": 1, "epic_id": group["id"], "title": "Different kind", "operation_key": body["operation_key"]}).status_code == 409
    assert db_conn.execute("SELECT count(*) FROM owner_planning_commands").fetchone()[0] == 1
    assert db_conn.execute("SELECT count(*) FROM milestones WHERE epic_id=?", (group["id"],)).fetchone()[0] == 0


def test_planning_keys_are_project_scoped_and_foreign_parents_are_rejected(client, db_conn, seeded_project):
    """Identical keys may describe separate projects, but a milestone cannot move its parent into another scope."""
    other = client.post("/api/projects", json={"name": "Otro proyecto"}).json()["id"]
    first = client.post("/api/epics", json={"project_id": 1, "title": "Mismo nombre", "operation_key": "shared-key"}).json()
    second = client.post("/api/epics", json={"project_id": other, "title": "Mismo nombre", "operation_key": "shared-key"}).json()
    assert first["id"] != second["id"]
    rejected = client.post("/api/milestones", json={"project_id": other, "epic_id": first["id"], "title": "Foreign", "operation_key": "foreign-parent"})
    assert rejected.status_code == 404
    assert db_conn.execute("SELECT count(*) FROM owner_planning_commands WHERE operation_key='foreign-parent'").fetchone()[0] == 0


def test_recovery_preserves_original_response_without_reverting_later_edits(client, db_conn, seeded_project):
    """Replay returns the original creation receipt while the current resource retains a later owner edit."""
    body = {"project_id": 1, "title": "Antes", "operation_key": "original-response"}
    first = client.post("/api/epics", json=body).json()
    assert client.put(f'/api/epics/{first["id"]}', json={"title": "Después"}).status_code == 200
    assert client.post("/api/epics", json=body).json() == first
    assert client.get(f'/api/epics/{first["id"]}').json()["title"] == "Después"


@pytest.mark.parametrize("kind", ["group", "milestone"])
def test_a_retired_original_resource_is_not_recreated_by_its_request(client, db_conn, seeded_project, kind):
    """Keeping the original receipt prevents replay from recreating a resource the owner subsequently removed."""
    group = client.post("/api/epics", json={"project_id": 1, "title": "Retirable", "operation_key": "retirable-group"}).json()
    if kind == "group":
        endpoint, body = "/api/epics", {"project_id": 1, "title": "Retirable", "operation_key": "retirable-group"}
        target = group
    else:
        endpoint, body = "/api/milestones", {"project_id": 1, "epic_id": group["id"], "title": "Hito", "operation_key": "retirable-milestone"}
        target = client.post(endpoint, json=body).json()
    assert client.delete(f'{endpoint}/{target["id"]}').status_code == 204
    recovered = client.post(endpoint, json=body)
    assert recovered.status_code == 409
    assert "retiró" in recovered.json()["detail"]
    assert client.get(f'{endpoint}/{target["id"]}').status_code == 404


def test_resource_and_receipt_rollback_together(client, db_conn, seeded_project):
    """An actual receipt INSERT failure rolls back the new resource and its audit event before an explicit retry."""
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import get_db_path

    before = db_conn.execute("SELECT count(*) FROM events_log").fetchone()[0]
    db_conn.execute("CREATE TRIGGER reject_planning_receipt BEFORE INSERT ON owner_planning_commands BEGIN SELECT RAISE(ABORT,'controlled receipt failure'); END")
    db_conn.commit()
    records = OwnerPlanningRecords(SQLiteRunStore(get_db_path()))
    with pytest.raises(sqlite3.IntegrityError):
        records.create_group(project_id=1, title="Atomic group", operation_key="atomic-request")
    assert db_conn.execute("SELECT count(*) FROM epics WHERE title='Atomic group'").fetchone()[0] == 0
    assert db_conn.execute("SELECT count(*) FROM owner_planning_commands").fetchone()[0] == 0
    assert db_conn.execute("SELECT count(*) FROM events_log").fetchone()[0] == before
    db_conn.execute("DROP TRIGGER reject_planning_receipt")
    db_conn.commit()
    assert records.create_group(project_id=1, title="Atomic group", operation_key="atomic-request")["id"] > 0


def test_manual_group_removal_preserves_tasks_and_dependencies(client, db_conn, seeded_project):
    """Deleting an explicitly chosen manual group detaches its members instead of deleting their work or dependency edges."""
    group = client.post("/api/epics", json={"project_id": 1, "title": "Grupo manual", "operation_key": "manual-group"}).json()["id"]
    milestone = client.post("/api/milestones", json={"project_id": 1, "epic_id": group, "title": "Hito manual", "operation_key": "manual-milestone"}).json()["id"]
    first = db_conn.execute("INSERT INTO tasks(project_id,epic_id,milestone_id,type,title,status) VALUES(1,?,?,'code','Entrada','pending')", (group, milestone)).lastrowid
    second = db_conn.execute("INSERT INTO tasks(project_id,epic_id,type,title,status) VALUES(1,?,'code','Salida','pending')", (group,)).lastrowid
    db_conn.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(?,?,'blocks')", (second, first))
    db_conn.commit()
    assert client.delete(f"/api/epics/{group}").status_code == 204
    rows = [tuple(row) for row in db_conn.execute("SELECT id,epic_id,milestone_id,status FROM tasks WHERE id IN (?,?) ORDER BY id", (first, second))]
    assert rows == [(first, None, None, "pending"), (second, None, None, "pending")]
    assert db_conn.execute("SELECT count(*) FROM task_dependencies WHERE task_id=? AND depends_on_task_id=?", (second, first)).fetchone()[0] == 1

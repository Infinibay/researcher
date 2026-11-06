"""Native project structure reads retain scoped grouping and full text without treating old labels as acceptance."""

import pytest

from backend.tests.research.test_http import credentials, research_client

__all__ = ["research_client"]
ROOT = "/api/research-tools/task-workspace/structure"


@pytest.fixture
def project_structure(db_conn):
    """Include foreign-linked historical rows to prove counts and parent attribution cannot widen project scope."""
    db_conn.execute("INSERT INTO epics(id,project_id,title,description) VALUES(91,101,'Local grouping',?),(92,202,'Foreign grouping','Secret foreign context')", ("áβ" * 900,))
    db_conn.execute("INSERT INTO milestones(id,project_id,epic_id,title,description,due_date) VALUES(81,101,91,'Local milestone','Expected deliverable','2027-01-15'),(82,202,91,'Foreign linked milestone','Secret',NULL)")
    db_conn.execute("INSERT INTO tasks(id,project_id,type,title,status,epic_id,milestone_id) VALUES(1003,101,'research','Local historical task','done',91,81),(2003,202,'research','Foreign linked task','done',91,81)")
    db_conn.commit()


def test_structure_reads_scope_counts_and_complete_original_fields(research_client, research_store, project_structure):
    """Expose own historical counts as labels, never foreign task content or proof of accepted work."""
    headers = credentials(research_store, permissions={"tasks.read"})
    assert research_client.get(ROOT + "/epics").status_code == 401
    response = research_client.get(ROOT + "/epics", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert [row["id"] for row in result["items"]] == [91]
    assert result["items"][0]["task_count"] == 1
    assert result["items"][0]["tasks_labeled_done"] == 1
    assert result["items"][0]["milestone_count"] == 1
    assert result["authorizes_work"] is False
    first = research_client.get(ROOT + "/epics/91", headers=headers, params={"max_chars":1000}).json()
    second = research_client.get(ROOT + "/epics/91", headers=headers, params={"offset":first["next_offset"]}).json()
    assert first["content"] + second["content"] == "áβ" * 900
    assert first["immutable"] is False
    milestones = research_client.get(ROOT + "/milestones", headers=headers, params={"epic_id":91}).json()["items"]
    assert len(milestones) == 1 and milestones[0]["id"] == 81
    assert milestones[0]["task_count"] == 1 and milestones[0]["epic_in_project"] is True
    assert research_client.get(ROOT + "/milestones/82", headers=headers).status_code == 404
    assert research_client.get(ROOT + "/epics/92", headers=headers).status_code == 404
    assert research_client.get(ROOT + "/epics", headers=headers, params={"epic_id":91}).status_code == 422

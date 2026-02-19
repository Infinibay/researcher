"""Tests for FastAPI routes."""

import pytest


# ── Health ──────────────────────────────────────────────────────────────


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "db" in data


# ── Projects ────────────────────────────────────────────────────────────


class TestProjects:
    def test_create_project(self, client):
        resp = client.post(
            "/api/projects",
            json={"name": "New Project", "description": "A new project"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "New Project"

    def test_list_projects(self, client, seeded_project):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert "projects" in data
        assert data["total"] >= 1

    def test_get_project(self, client, seeded_project):
        resp = client.get(f"/api/projects/{seeded_project}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == seeded_project

    def test_get_project_not_found(self, client):
        resp = client.get("/api/projects/99999")
        assert resp.status_code == 404

    def test_delete_project(self, client, seeded_project):
        resp = client.delete(f"/api/projects/{seeded_project}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get(f"/api/projects/{seeded_project}")
        assert resp.status_code == 404


# ── Epics ───────────────────────────────────────────────────────────────


class TestEpics:
    def test_create_epic(self, client, seeded_project):
        resp = client.post(
            "/api/epics",
            json={
                "project_id": seeded_project,
                "title": "New Epic",
                "description": "Description",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Epic"

    def test_list_epics(self, client, seeded_project):
        resp = client.get(f"/api/epics?project_id={seeded_project}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1


# ── Tasks ───────────────────────────────────────────────────────────────


class TestTasks:
    def test_create_task(self, client, seeded_project):
        resp = client.post(
            "/api/tasks",
            json={
                "project_id": seeded_project,
                "title": "Implement feature",
                "description": "Build the thing",
                "type": "code",
                "epic_id": 1,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "backlog"
        assert data["title"] == "Implement feature"

    def test_list_tasks_filter_by_status(self, client, seeded_project):
        # Create a task first
        client.post(
            "/api/tasks",
            json={"project_id": seeded_project, "title": "Task A"},
        )

        resp = client.get(f"/api/tasks?project_id={seeded_project}&status=backlog")
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["status"] == "backlog" for t in data)

    def test_update_task_status(self, client, seeded_project):
        # Create task
        create_resp = client.post(
            "/api/tasks",
            json={"project_id": seeded_project, "title": "Task B"},
        )
        task_id = create_resp.json()["id"]

        # Transition backlog -> pending
        resp = client.put(f"/api/tasks/{task_id}", json={"status": "pending"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_add_task_comment(self, client, seeded_project):
        # Create task
        create_resp = client.post(
            "/api/tasks",
            json={"project_id": seeded_project, "title": "Task C"},
        )
        task_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/tasks/{task_id}/comments",
            json={"content": "This is a comment", "author": "test-user"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "This is a comment"
        assert data["task_id"] == task_id


# ── Wiki ────────────────────────────────────────────────────────────────


class TestWiki:
    def test_create_wiki_page(self, client, seeded_project):
        resp = client.post(
            "/api/wiki",
            json={
                "project_id": seeded_project,
                "path": "getting-started",
                "title": "Getting Started",
                "content": "# Welcome",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["path"] == "getting-started"
        assert data["title"] == "Getting Started"

    def test_get_wiki_page(self, client, seeded_project):
        # Create page first
        client.post(
            "/api/wiki",
            json={
                "project_id": seeded_project,
                "path": "test-page",
                "content": "Test content",
            },
        )

        resp = client.get(f"/api/wiki/test-page?project_id={seeded_project}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "test-page"

    def test_wiki_page_not_found(self, client, seeded_project):
        resp = client.get(f"/api/wiki/nonexistent?project_id={seeded_project}")
        assert resp.status_code == 404


# ── Chat ────────────────────────────────────────────────────────────────


class TestChat:
    def test_send_chat_message(self, client, seeded_project):
        resp = client.post(
            f"/api/chat/{seeded_project}",
            json={"message": "Hello from user", "to_role": "project_lead"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["message"] == "Hello from user"
        assert data["from_agent"] == "user"

    def test_get_chat_messages(self, client, seeded_project):
        # Send a message first
        client.post(
            f"/api/chat/{seeded_project}",
            json={"message": "Test message"},
        )

        resp = client.get(f"/api/chat/{seeded_project}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

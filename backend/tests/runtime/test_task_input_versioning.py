"""Task edits revoke old authority even when a legacy writer uses SQL directly."""

import asyncio
import json
import sqlite3
from dataclasses import replace

import pytest

from backend.research.models import ResearchForbidden
from backend.runtime.contracts import RunConflict, StaleAttempt
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


# Omitting any of these input fields from the boundary would allow stale work.
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Revised policy"),
        ("description", "Use base 200"),
        ("type", "code"),
        ("acceptance_criteria", "Include the captured quote"),
        ("context_json", '{"base":200}'),
        ("priority", 4),
        ("estimated_complexity", "high"),
        ("branch_name", "task/revised"),
        ("assigned_to", "another-agent"),
        ("reviewer", "independent-reviewer"),
    ],
)
def test_changed_task_input_revokes_the_original_attempt(coordination, field, value):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "host")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions={"sources.read"},
        ttl_seconds=60,
    )
    c.store.bind_grant(lease, c.research.authorize(token).grant_id)
    c.conn.execute(f"UPDATE tasks SET {field}=? WHERE id=1001", (value,))
    c.conn.commit()
    snapshot = c.store.context_snapshot(101, 1001)
    assert snapshot["context_version"] == 2
    assert snapshot["task"][field] == value
    assert snapshot["task_changes"][0]["changes"][field]["after"] == value
    assert snapshot["task_changes"][0]["source_kind"] == "task_metadata"
    assert snapshot["task_changes"][0]["actor"] is None
    current = c.store.get(101, run.run_id)
    assert current.status == "reconciling" and current.fence > lease.fence
    with pytest.raises(StaleAttempt):
        c.store.heartbeat(lease)
    with pytest.raises(ResearchForbidden):
        c.research.authorize(token)
    assert c.store.context_snapshot(202, 2002)["context_version"] == 1
    assert c.store.context_snapshot(202, 2002)["task_changes"] == []


def test_edit_cannot_reuse_a_queued_request_under_old_inputs(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    c.conn.execute(
        "UPDATE tasks SET description='Base 200',title='New criteria' WHERE id=1001"
    )
    c.conn.commit()
    assert c.store.get(101, run.run_id).status == "superseded"
    with pytest.raises(RunConflict):
        c.store.claim(101, run.run_id, "host")
    with pytest.raises(RunConflict):
        c.store.admit(replace(c.spec, operation_key="stale-new-request"))
    changes = c.store.context_snapshot(101, 1001)["task_changes"]
    assert len(changes) == 1 and changes[0]["version"] == 2
    assert changes[0]["changes"] == {
        "title": {"before": "Policy", "after": "New criteria"},
        "description": {"before": None, "after": "Base 200"},
    }
    # Re-reading the old receipt remains a read; it does not regain authority.
    assert c.store.admit(c.spec).run_id == run.run_id


def test_noop_and_progress_only_updates_do_not_invalidate_work(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "host")
    c.conn.execute(
        "UPDATE tasks SET title=title,description=description,retry_count=retry_count+1 WHERE id=1001"
    )
    c.conn.commit()
    assert c.store.heartbeat(lease).fence == lease.fence
    snapshot = c.store.context_snapshot(101, 1001)
    assert snapshot["context_version"] == 1 and snapshot["task_changes"] == []


def test_edit_event_failure_rolls_back_inputs_authority_and_history(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "host")
    c.conn.execute("""CREATE TRIGGER fail_input_event BEFORE INSERT ON events_log
        WHEN new.event_type='context.task_inputs_changed'
        BEGIN SELECT RAISE(ABORT,'fixture event failure'); END""")
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="fixture event failure"):
        c.conn.execute("UPDATE tasks SET description='Must roll back' WHERE id=1001")
    c.conn.rollback()
    assert c.store.context_snapshot(101, 1001)["task"]["description"] is None
    assert c.store.context_snapshot(101, 1001)["context_version"] == 1
    assert c.store.context_snapshot(101, 1001)["task_changes"] == []
    assert c.store.heartbeat(lease).fence == lease.fence


def test_metadata_versions_interleave_with_explicit_corrections_without_fake_user_evidence(
    coordination,
):
    c = coordination
    c.conn.execute("UPDATE tasks SET description='Base 200' WHERE id=1001")
    c.conn.commit()
    version = c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=2,
        operation_key="example",
        statement="For example: 200 * 0.21 = 42",
        source_kind="user_example",
        source_reference="owner-example",
    )
    assert version == 3
    c.conn.execute(
        "UPDATE tasks SET acceptance_criteria='Verify the total' WHERE id=1001"
    )
    c.conn.commit()
    snapshot = c.store.context_snapshot(101, 1001)
    assert snapshot["context_version"] == 4
    assert [x["version"] for x in snapshot["task_changes"]] == [2, 4]
    assert [(x["version"], x["source_kind"]) for x in snapshot["corrections"]] == [
        (3, "user_example")
    ]
    assert snapshot["task"]["acceptance_criteria"] == "Verify the total"
    assert snapshot["task_changes"][0]["actor"] is None


def test_pending_question_expires_after_task_metadata_edit(coordination):
    from backend.tests.runtime.test_human_questions import setup_question

    c = coordination
    questions, _run, _lease, _scope, receipt = setup_question(c)
    c.conn.execute(
        "UPDATE tasks SET description='Changed question premise' WHERE id=1001"
    )
    c.conn.commit()
    assert (
        c.conn.execute(
            "SELECT status FROM user_requests WHERE id=?", (receipt["request_id"],)
        ).fetchone()[0]
        == "expired"
    )
    with pytest.raises(RunConflict):
        questions.answer(
            project_id=101,
            task_id=1001,
            request_id=receipt["request_id"],
            expected_version=1,
            operation_key="old-answer",
            answers={"base": "200"},
        )


async def test_edit_followed_by_native_completion_retires_superseded_without_acceptance(
    service_setup,
):
    s = service_setup
    native = ControlledInference(s)
    async with coordinator(s, native) as service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        s.c.conn.execute(
            "UPDATE tasks SET description='Revised while running' WHERE id=1001"
        )
        s.c.conn.commit()
        # Completion arrives before the periodic owner heartbeat notices the edit.
        native.release.set()
        await service.wait(run.run_id)
        assert s.c.store.get(101, run.run_id).status == "superseded"
        assert native.closed.is_set() and len(native.prompts) == 1
        assert (
            s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            != "done"
        )
        # The next explicit request gets the new criteria and their provenance.
        native.release.set()
        current = await service.submit(
            replace(s.c.spec, context_version=2, operation_key="new-request")
        )
        await service.wait(current.run_id)
        delivered = json.loads(native.prompts[-1])
        assert delivered["task"]["description"] == "Revised while running"
        assert (
            delivered["task_changes"][0]["changes"]["description"]["after"]
            == "Revised while running"
        )


async def test_owner_edit_interrupts_local_worker_and_exposes_exact_change(
    service_setup,
):
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=service,
    )
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        edited = await owner.put(
            "/api/tasks/1001", json={"description": "Use base 200"}
        )
        assert edited.status_code == 200, edited.text
        # This route knows its local owner; it must not wait for heartbeat polling.
        await asyncio.wait_for(native.interrupted.wait(), 0.5)
        await service.wait(run.run_id)
        assert s.c.store.get(101, run.run_id).status == "superseded"
        response = await owner.get("/api/projects/101/tasks/1001/workspace")
        assert response.status_code == 200, response.text
        context = response.json()["context"]
        assert context["context_version"] == 2
        assert context["task_changes"][0]["changes"]["description"] == {
            "before": None,
            "after": "Use base 200",
        }
        assert context["task_changes"][0]["actor"] is None
        assert len(native.prompts) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("epic_id", 51), ("milestone_id", 61), ("parent_task_id", 1002)],
)
def test_changing_task_hierarchy_invalidates_only_the_edited_task(
    coordination, field, value
):
    c = coordination
    c.conn.execute("INSERT INTO epics(id,project_id,title) VALUES(51,101,'Scope')")
    c.conn.execute(
        "INSERT INTO milestones(id,project_id,epic_id,title) VALUES(61,101,51,'Scope')"
    )
    c.conn.commit()
    run = c.store.admit(c.spec)
    c.conn.execute(f"UPDATE tasks SET {field}=? WHERE id=1001", (value,))
    c.conn.commit()
    assert c.store.get(101, run.run_id).status == "superseded"
    snapshot = c.store.context_snapshot(101, 1001)
    assert snapshot["context_version"] == 2
    assert snapshot["task_changes"][0]["changes"] == {
        field: {"before": None, "after": value}
    }
    assert c.store.context_snapshot(101, 1002)["context_version"] == 1


async def test_metadata_fencing_does_not_claim_physical_peer_closure(coordination):
    from backend.runtime.peer_registry import AttemptPeers

    c = coordination
    run = c.store.admit(c.spec)
    lease, peers = AttemptPeers.claim(c.store, 101, run.run_id, "host")
    c.conn.execute("UPDATE tasks SET description='Revised' WHERE id=1001")
    c.conn.commit()
    with pytest.raises(RunConflict, match="closure"):
        c.store.retire_withdrawn(lease)
    assert c.store.get(101, run.run_id).status == "reconciling"
    await peers.aclose()
    assert peers.closed()
    assert c.store.retire_withdrawn(lease).status == "superseded"

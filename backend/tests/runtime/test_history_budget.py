"""Owner history exposes every recorded attempt and the same budget used at admission."""

from dataclasses import replace

import pytest

from backend.runtime.contracts import RunNotFound
from backend.tests.runtime.test_inference_journal import reservation, reserve
from backend.tests.runtime.test_workspace_delivery import owner_client, workspace_app

__all__ = ["workspace_app"]


def history(c):
    """Create the production read adapter against the fixture's real migrated database."""
    from backend.runtime.history import RuntimeHistory

    return RuntimeHistory(c.database)


def saved_runs(c, count):
    """Retain sequential cancelled requests sharing a timestamp without dispatching inference."""
    runs = []
    for index in range(count):
        run = c.store.admit(replace(c.spec, operation_key=f"history-{index}"))
        c.store.cancel(101, run.run_id)
        runs.append(run)
    return runs


def test_task_history_crosses_thirty_with_tied_times_and_new_arrivals(coordination):
    """Older pages neither lose tied timestamps nor include new runs or other projects."""
    c = coordination
    runs = saved_runs(c, 35)
    c.store.admit(replace(c.spec, project_id=202, task_id=2002))
    before = c.conn.execute("SELECT count(*) FROM events_log").fetchone()[0]
    view = history(c)
    first = view.task_runs(101, 1001, limit=30)
    assert first["total"] == 35
    assert [item["run_id"] for item in first["items"]] == [r.run_id for r in reversed(runs[5:])]
    assert c.conn.execute("SELECT count(*) FROM events_log").fetchone()[0] == before
    c.store.admit(replace(c.spec, operation_key="arrived-during-read"))
    older = view.task_runs(101, 1001, before_seq=int(first["next_before_seq"]), limit=30)
    assert [item["run_id"] for item in older["items"]] == [r.run_id for r in reversed(runs[:5])]
    assert older["next_before_seq"] is None
    with pytest.raises(RunNotFound):
        view.task_runs(202, 1001)
    for options in ({"limit": 0}, {"limit": 101}, {"before_seq": True}, {"before_seq": -1}):
        with pytest.raises(ValueError):
            view.task_runs(101, 1001, **options)


def test_attempt_pages_keep_original_result_model_and_unknown_usage(coordination):
    """Earlier attempts retain their own receipts instead of borrowing the current attempt's values."""
    c = coordination
    run, lease = reservation(c)
    reserve(c, lease, model="current-model")
    c.store.note_inference_usage(lease, 55)
    # Seed a retained earlier receipt and a second current attempt with no dispatch.
    c.conn.execute("UPDATE runtime_attempts SET status='finished',ended_at=1001,native_result_json=? WHERE id=?",
                   ('{"native_status":"completed","summary":"Earlier draft"}', lease.attempt_id))
    c.conn.execute("INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES(?,?,'current-owner',2,'running',1030,1001)",
                   ("current-unmeasured", run.run_id))
    c.conn.execute("UPDATE runtime_runs SET current_attempt_id='current-unmeasured',fence=2 WHERE id=?", (run.run_id,))
    c.conn.commit()
    view = history(c)
    page = view.attempts(101, run.run_id, limit=1)
    assert page["total"] == 2
    current = page["items"][0]
    assert current["attempt_id"] == "current-unmeasured" and current["is_current"] is True
    assert current["observed_tokens"] is None and current["model"] is None
    remaining = view.attempts(101, run.run_id, before_seq=int(page["next_before_seq"]), limit=1)
    old = remaining["items"][0]
    assert old["attempt_id"] == lease.attempt_id and old["is_current"] is False
    assert old["result"]["summary"] == "Earlier draft"
    assert old["observed_tokens"] == 55 and old["model"] == "current-model"
    assert remaining["next_before_seq"] is None
    with pytest.raises(RunNotFound):
        view.attempts(202, run.run_id)


def test_budget_matches_conservative_admission_and_preserves_missing_measurements(coordination):
    """No measurement is unknown; partial usage retains a ceiling and overruns retain the high water."""
    c = coordination
    view = history(c)
    empty = view.budget(101)
    assert empty["policy"] is None and empty["observed_tokens"] is None
    run, lease = reservation(c)
    reserve(c, lease)
    absent = view.budget(101)
    assert absent["observed_tokens"] is None and absent["unmeasured_dispatches"] == 1
    assert absent["accounted_tokens"] == 100 and absent["remaining_tokens"] == 100
    c.store.note_inference_usage(lease, 40)
    partial = view.budget(101)
    assert partial["observed_tokens"] == 40 and partial["accounted_tokens"] == 100
    assert partial["held_tokens"] == 100 and partial["unsettled_dispatches"] == 1
    c.store.note_inference_usage(lease, 250)
    overrun = view.budget(101)
    assert overrun["accounted_tokens"] == 250 and overrun["remaining_tokens"] == 0
    assert overrun["overrun_tokens"] == 50
    c.store.settle_inference(lease, observed_tokens=250, native_status="completed")
    settled = view.budget(101)
    assert settled["held_tokens"] == 0 and settled["observed_tokens"] == 250
    assert settled["remaining_turns"] == 1
    assert view.budget(202)["used_turns"] == 0
    assert "cost_usd" not in settled and "quota" not in settled
    with pytest.raises(RunNotFound):
        view.budget(999)


async def test_owner_history_routes_are_scoped_readonly_and_available_without_runtime(coordination, workspace_app):
    """HTTP history needs the owner session and never starts inference or borrows a foreign scope."""
    c = coordination
    run = saved_runs(c, 1)[0]
    paths = ["/api/projects/101/tasks/1001/run-history", f"/api/projects/101/runs/{run.run_id}/attempts", "/api/projects/101/work-budget"]
    before = c.conn.execute("SELECT count(*) FROM events_log").fetchone()[0]
    async with workspace_app.router.lifespan_context(workspace_app), owner_client(workspace_app) as owner:
        for path in paths:
            response = await owner.get(path)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["project_id"] == 101
        assert (await owner.get(paths[0] + "?limit=0")).status_code == 422
        assert (await owner.get(paths[1].replace("/101/", "/202/"))).status_code == 404
        assert (await owner.get(paths[0].replace("/101/", "/202/"))).status_code == 404
    assert c.conn.execute("SELECT count(*) FROM events_log").fetchone()[0] == before
    assert c.conn.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0] == 0

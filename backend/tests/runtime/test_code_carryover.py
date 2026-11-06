"""Prior native candidate bytes become attributed input, never borrowed execution or acceptance authority."""

import base64
import json
from dataclasses import replace

import pytest

from backend.runtime.contracts import RunConflict, RunNotFound
from backend.tests.runtime.test_code_candidate_state import (
    candidate_state as candidate_state,  # noqa: PLC0414
)
from backend.tests.runtime.test_code_review_state import review_state as review_state  # noqa: PLC0414
from backend.tests.runtime.test_development_state import (
    development_state as development_state,  # noqa: PLC0414
)


def reuse_request(state):
    """Select exact observed data after explicit original withdrawal; storage witnesses are synthetic."""
    from backend.runtime.code_carryover import CodeCarryovers, PriorCodeTarget

    s, author, candidate, _reviews = state
    s.c.store.cancel(101, author.run_id)
    packet = CodeCarryovers(s.c.store).preview(101, 1001, author.attempt_id)
    target = PriorCodeTarget(author.attempt_id, packet["snapshot_sha256"])
    binding = s.c.store.workspace_binding(101, author.run_id)
    return s, author, candidate, packet, target, binding


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_owner_reuses_exact_prior_bytes_with_new_run_and_original_receipt(review_state):
    """Dropping prior-code admission binding would lose exact bytes on reload or silently change a retried intent."""
    from backend.runtime.code_carryover import CodeCarryovers
    from backend.runtime.sqlite_runs import SQLiteRunStore

    s, author, candidate, preview, target, binding = reuse_request(review_state)
    spec = replace(
        s.c.spec,
        operation_key="reuse-prior-code",
        context_version=author.context_version,
        prompt="Continue from these changes; explain any adaptation.",
    )
    run, created = s.c.store.admit_once(spec, binding=binding, prior_code=target)
    assert (
        created and run.run_id != author.run_id and run.execution_kind == "development"
    )
    assert run.prompt == "Continue from these changes; explain any adaptation."
    reopened = SQLiteRunStore(s.c.database)
    assert reopened.admit_once(spec, binding=binding, prior_code=target) == (run, False)
    with reopened._transaction() as conn:
        retained = CodeCarryovers.input(conn, reopened._row(conn, 101, run.run_id))
    assert retained["snapshot_sha256"] == preview["snapshot_sha256"]
    assert base64.b64decode(retained["snapshot"]["diff_base64"]) == b"diff fixture\n"
    assert retained["snapshot"]["origin"]["attempt_id"] == author.attempt_id
    assert retained["snapshot"]["origin"]["context_version"] == author.context_version
    assert retained["snapshot"]["origin"]["thread_id"] == "author-thread"
    assert retained["snapshot"]["original_input"]["request"] == s.c.spec.prompt
    assert retained["authority"] == "data_only"
    assert retained["acceptance"] == "not_granted"
    assert s.c.store.get(101, author.run_id).status == "cancelled"
    assert s.c.store.get(101, run.run_id).attempt_id is None
    assert (
        s.c.conn.execute("SELECT COUNT(*) FROM runtime_code_acceptances").fetchone()[0]
        == 0
    )
    assert candidate["diff"] == b"diff fixture\n"
    s.c.conn.execute(
        "UPDATE runtime_peers SET state='prepared' WHERE attempt_id=? AND kind='native'",
        (author.attempt_id,),
    )
    s.c.conn.commit()
    assert reopened.admit_once(spec, binding=binding, prior_code=target) == (run, False)
    with pytest.raises(RunConflict):
        reopened.admit_once(
            spec, binding=binding, prior_code=replace(target, snapshot_sha256="0" * 64)
        )


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_prior_code_keeps_obsolete_original_context_separate_from_new_requirements(
    review_state,
):
    """Reconstructing the original request from current task state would erase what the old author actually saw."""
    from backend.runtime.code_carryover import CodeCarryovers
    from backend.runtime.run_inputs import freeze_input

    s, author, _candidate, _preview, _target, binding = reuse_request(review_state)
    version = s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=author.context_version,
        operation_key="correct-before-reuse",
        statement="Keep the old API while reusing the implementation.",
        source_kind="user_message",
        source_reference="owner:correction",
    )
    preview = CodeCarryovers(s.c.store).preview(101, 1001, author.attempt_id)
    from backend.runtime.code_carryover import PriorCodeTarget

    target = PriorCodeTarget(author.attempt_id, preview["snapshot_sha256"])
    spec = replace(
        s.c.spec,
        operation_key="reuse-corrected",
        context_version=version,
        prompt="Adapt the earlier change to this correction.",
    )
    run, _ = s.c.store.admit_once(spec, binding=binding, prior_code=target)
    with s.c.store._transaction() as conn:
        frozen = freeze_input(
            conn,
            s.c.store._row(conn, 101, run.run_id),
            s.c.store._context_snapshot(conn, 101, 1001),
        )
    data = json.loads(frozen.input_text)
    assert data["context_version"] == version
    assert (
        data["prior_code"]["snapshot"]["original_input"]["context_version"]
        == author.context_version
    )
    assert data["request"] == "Adapt the earlier change to this correction."
    assert (
        data["corrections"][-1]["statement"]
        == "Keep the old API while reusing the implementation."
    )


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
@pytest.mark.parametrize(
    "fault", ["project", "task", "hash", "open_peer", "different_repository"]
)
def test_foreign_stale_or_unclosed_prior_code_cannot_admit_a_run(review_state, fault):
    """Neither a selected label nor an old preview can authorize foreign input or bypass original native closure."""

    s, author, _candidate, _preview, target, binding = reuse_request(review_state)
    spec = replace(
        s.c.spec, operation_key="bad-prior", context_version=author.context_version
    )
    if fault == "project":
        spec = replace(spec, project_id=202)
    elif fault == "task":
        spec = replace(spec, task_id=1002)
    elif fault == "hash":
        target = replace(target, snapshot_sha256="0" * 64)
    elif fault == "open_peer":
        s.c.conn.execute(
            "UPDATE runtime_peers SET state='prepared' WHERE attempt_id=? AND kind='native'",
            (author.attempt_id,),
        )
        s.c.conn.commit()
    else:
        binding = replace(binding, repository_id=12, requested_repository_id=None)
    before = s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0]
    with pytest.raises((RunConflict, RunNotFound)):
        s.c.store.admit_once(spec, binding=binding, prior_code=target)
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == before


def test_missing_original_input_is_not_reconstructed_from_current_state(review_state):
    """Historic unrecorded input remains unknown; it is not a verified native carryover packet."""
    from backend.runtime.code_carryover import CodeCarryovers

    s, author, _candidate, _reviews = review_state
    with pytest.raises(RunConflict, match="input"):
        CodeCarryovers(s.c.store).preview(101, 1001, author.attempt_id)


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
async def test_owner_http_and_chat_preserve_the_same_prior_input_intent(review_state):
    """Ignoring the selected target at either public entry would silently start unrelated work after reload or response loss."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, author, _candidate, preview, target, _binding = reuse_request(review_state)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )
    inference = ControlledInference(s)
    inference.supported_task_types = ("research", "code", "bug_fix")
    async with (
        app.router.lifespan_context(app),
        coordinator(s, inference, legacy_active=lambda _project: True) as runtime,
    ):
        app.state.runtime_service = runtime
        async with owner_client(app) as owner:
            prior_path = f"/api/projects/101/tasks/1001/prior-code/{author.attempt_id}"
            response = await owner.get(prior_path)
            assert response.status_code == 200, response.text
            assert response.json()["snapshot_sha256"] == preview["snapshot_sha256"]
            assert (
                await owner.get(prior_path.replace("tasks/1001", "tasks/1002"))
            ).status_code == 409
            selection = {
                "attempt_id": target.attempt_id,
                "snapshot_sha256": target.snapshot_sha256,
            }
            body = {
                "operation_key": "http-reuse",
                "context_version": author.context_version,
                "request": "Adapt the saved changes.",
                "repository_id": 11,
                "prior_code": selection,
            }
            path = "/api/projects/101/tasks/1001/runs"
            started = await owner.post(path, json=body)
            assert started.status_code == 202, started.text
            run = started.json()
            assert (
                run["status"] == "queued" and run["issue"]["inference_started"] is False
            )
            replay = await owner.post(path, json=body)
            assert (
                replay.status_code == 202 and replay.json()["run_id"] == run["run_id"]
            )
            wrong = await owner.post(
                path,
                json={**body, "prior_code": {**selection, "snapshot_sha256": "0" * 64}},
            )
            assert wrong.status_code == 409
            await runtime.stop(101, run["run_id"])
            chat = await owner.post(
                "/api/chat/101/instructions",
                json={
                    "task_id": 1001,
                    "operation_key": "chat-reuse",
                    "context_version": author.context_version,
                    "thread_id": "reuse-thread",
                    "message": "Rework these earlier changes.",
                    "repository_id": 11,
                    "prior_code": selection,
                },
            )
            assert chat.status_code == 202, chat.text
            assert chat.json()["message"]["message"] == "Rework these earlier changes."
            from backend.runtime.code_carryover import CodeCarryovers

            with s.c.store._transaction() as conn:
                saved = CodeCarryovers.input(
                    conn, s.c.store._row(conn, 101, chat.json()["run"]["run_id"])
                )
            assert saved["snapshot_sha256"] == preview["snapshot_sha256"]
            assert inference.prompts == []


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_complete_prior_input_over_budget_is_refused_without_truncating_history(
    review_state,
):
    """A legally large frozen conversation must not be shortened silently to make prior material fit."""
    import hashlib

    from backend.runtime.code_carryover import CodeCarryovers
    from backend.runtime.contracts import InputTooLarge

    s, author, _candidate, _reviews = review_state
    row = dict(
        s.c.conn.execute(
            "SELECT * FROM runtime_input_snapshots WHERE attempt_id=?",
            (author.attempt_id,),
        ).fetchone()
    )
    payload = json.loads(row["input_text"])
    payload["conversation"]["messages"] = [
        {"kind": "owner_note", "content": "x" * 50000} for _ in range(13)
    ]
    row["input_text"] = json.dumps(payload)
    row["input_sha256"] = hashlib.sha256(row["input_text"].encode()).hexdigest()
    # Storage-only fixture supplies a complete larger historic observation, not an executed native turn.
    s.c.conn.execute(
        "DELETE FROM runtime_input_snapshots WHERE attempt_id=?", (author.attempt_id,)
    )
    s.c.conn.execute(
        "INSERT INTO runtime_input_snapshots("
        + ",".join(row)
        + ") VALUES("
        + ",".join("?" for _ in row)
        + ")",
        tuple(row.values()),
    )
    s.c.conn.commit()
    with pytest.raises(InputTooLarge):
        CodeCarryovers(s.c.store).preview(101, 1001, author.attempt_id)
    retained = s.c.store.input_record(101, author.run_id)
    assert len(json.loads(retained["input_text"])["conversation"]["messages"]) == 13

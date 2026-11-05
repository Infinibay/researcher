"""Durable host publication admission over synthetic accepted-code witnesses; physical Git publication has separate integration coverage."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_code_acceptance import (
    code_result as code_result,  # noqa: PLC0414 -- original accepted-code storage fixture.
)
from backend.tests.runtime.test_code_acceptance import owner_intent
from backend.tests.runtime.test_code_review_records import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_review_records import (
    development_state as development_state,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_review_records import (
    review_records as review_records,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_review_records import (
    review_state as review_state,  # noqa: PLC0414 -- original fixture dependencies.
)

pytestmark = pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)


@pytest.fixture
def publication_request(code_result):
    """Accept original stored evidence and create actual metadata identities without claiming these directories are valid Git repositories."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.code_publications import (
        CodePublicationIntent,
        CodePublications,
    )

    s, _reviewer, candidate = code_result
    owner = CodeAcceptances(s.c.store)
    state = owner.state(101, candidate["run_id"])
    receipt = owner.accept(101, candidate["run_id"], owner_intent(state))
    source = json.loads(candidate["source_json"])["workspace"]
    (Path(source) / ".git").mkdir()
    (Path(candidate["workspace"]) / ".git").mkdir()
    intent = CodePublicationIntent(
        "publish-code",
        receipt["operation_key"],
        candidate["attempt_id"],
        candidate["context_version"],
        state["subject_sha256"],
        state["review_sha256"],
        "refs/heads/reviewed-change",
        None,
    )
    return s, candidate, CodePublications(s.c.store), intent


def test_publication_admission_has_own_command_only_attempt_and_preserves_acceptance(
    publication_request,
):
    """One owner intent admits once, claims new authority without reopening done, and cannot reserve model inference or native peers."""
    from backend.runtime.codex_session import ExecutionLimits
    from backend.runtime.contracts import RunConflict
    from backend.runtime.peer_registry import AttemptPeers

    s, candidate, publications, intent = publication_request
    run, created = publications.admit_once(101, candidate["run_id"], intent)
    assert created and run.execution_kind == "code_publication"
    assert publications.admit_once(101, candidate["run_id"], intent) == (run, False)
    assert s.c.store.context_snapshot(101, 1001)["task"]["status"] == "done"
    assert s.c.store.code_result_state(101, candidate["run_id"])["acceptance_current"]
    lease, peers = AttemptPeers.claim(s.c.store, 101, run.run_id, "host-publisher")
    assert lease.attempt_id != candidate["attempt_id"] and peers.ids == {}
    assert s.c.store.context_snapshot(101, 1001)["task"]["status"] == "done"
    assert s.c.store.heartbeat(lease).attempt_id == lease.attempt_id
    with pytest.raises(RunConflict, match="command"):
        peers.registry.prepare(lease, "native")
    command = peers.registry.prepare(lease, "command")
    assert s.c.store.code_result_state(101, candidate["run_id"])["acceptance_current"]
    peers.registry.close(command)
    with s.c.store._transaction() as conn:
        s.c.store._closed_peer_proof(conn, lease.attempt_id)
    with pytest.raises(RunConflict, match="host-only"):
        s.c.store.reserve_inference(
            lease,
            workspace=publications.request(101, run.run_id)["view"]["source"][
                "workspace"
            ],
            catalog_hash="a" * 64,
            limits=ExecutionLimits(60, 30, 1, 10, 100),
        )
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_publication_requires_exact_current_acceptance_and_keeps_old_receipt_after_correction(
    publication_request,
):
    """Changed acceptance observations reject before admission; context correction withdraws the new effect lease without replaying a saved request."""
    from backend.runtime.contracts import RunConflict, StaleAttempt

    s, candidate, publications, intent = publication_request
    with pytest.raises(RunConflict):
        publications.admit_once(
            101, candidate["run_id"], replace(intent, subject_sha256="0" * 64)
        )
    run, _ = publications.admit_once(101, candidate["run_id"], intent)
    lease = s.c.store.claim(101, run.run_id, "host-publisher")
    with pytest.raises(RunConflict):
        publications.admit_once(
            101, candidate["run_id"], replace(intent, target_ref="refs/heads/changed")
        )
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=intent.context_version,
        operation_key="correct-after-publication-admission",
        statement="Use a different requirement",
        source_kind="user_message",
        source_reference="owner",
    )
    with pytest.raises(StaleAttempt):
        s.c.store.heartbeat(lease)
    historical, created = publications.admit_once(101, candidate["run_id"], intent)
    assert historical.run_id == run.run_id and not created
    with pytest.raises(RunConflict):
        publications.admit_once(
            101, candidate["run_id"], replace(intent, operation_key="new-stale-publish")
        )


def test_publication_request_is_immutable_and_startup_preserves_original_records(
    publication_request,
):
    """Normal startup installs the typed publication schema, keeps accepted provenance and prevents retargeting its immutable original request."""
    import sqlite3

    from backend.tools.base.db import ensure_migrations

    s, candidate, publications, intent = publication_request
    before = s.c.store.get(101, candidate["run_id"])
    run, _ = publications.admit_once(101, candidate["run_id"], intent)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        s.c.conn.execute(
            "UPDATE runtime_code_publication_requests SET target_ref='refs/heads/other' WHERE run_id=?",
            (run.run_id,),
        )
    s.c.conn.rollback()
    ensure_migrations(s.c.database)
    assert s.c.store.get(101, candidate["run_id"]) == before
    assert publications.request(101, run.run_id)["intent"] == intent.__dict__
    assert (
        s.c.conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
        == 52
    )


async def test_owner_http_publication_admits_once_and_does_not_accept_client_authority(
    publication_request,
):
    """Actual owner/CSRF HTTP preserves one original queued request; native physical execution is covered separately."""
    from dataclasses import asdict
    from types import SimpleNamespace

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, candidate, _publications, intent = publication_request
    runtime = coordinator(
        s,
        SimpleNamespace(
            supported_task_types=("research", "code", "bug_fix"), publish_code=True
        ),
    )

    async def held(run):
        """Keep a real saved admission queued so this HTTP fixture cannot launch synthetic Git metadata."""
        return run

    runtime._schedule = held
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        path = f"/api/projects/101/runs/{candidate['run_id']}/code-publications"
        body = asdict(intent)
        assert (
            await client.post(path, json={**body, "actor_id": "client"})
        ).status_code == 422
        assert (
            await client.post(path, json=body, headers={"X-Researcher-CSRF": "invalid"})
        ).status_code == 403
        response = await client.post(path, json=body)
        assert response.status_code == 202, response.text
        original = response.json()
        assert original["request"]["intent"] == body
        repeated = await client.post(path, json=body)
        assert (
            repeated.status_code == 202
            and repeated.json()["run"]["run_id"] == original["run"]["run_id"]
        )
        read = await client.get(
            f"/api/projects/101/code-publications/{original['run']['run_id']}"
        )
        assert read.status_code == 200 and read.json()["intent"] == body
        assert (
            s.c.conn.execute(
                "SELECT count(*) FROM runtime_code_publication_requests"
            ).fetchone()[0]
            == 1
        )

"""Retire original witnessed publication domains before new readonly recovery, never infer closure from a client boolean or a local status."""

from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.code_publications import CodePublications
from backend.runtime.contracts import RunConflict
from backend.runtime.peer_broker import PeerBroker
from backend.runtime.peer_registry import PeerRegistry


def close_original_publication(authority, store, project_id, run_id, attempt_id):
    """Match global grants to original database/attempt/fence and project verified retirement before declaring that original execution closed."""
    registry = PeerRegistry(store)
    origin = registry._database_identity()
    with store._transaction() as conn:
        run = store._row(conn, project_id, run_id)
        CodePublications(store)._request(conn, project_id, run_id)
        attempt = conn.execute(
            "SELECT * FROM runtime_attempts WHERE id=? AND run_id=?",
            (attempt_id, run_id),
        ).fetchone()
        if attempt is None or run["current_attempt_id"] != attempt_id:
            raise RunConflict("Original publication attempt differs; refresh its state")
        fence = attempt["fence"]
    grants = []
    with WitnessedAuthorityJournal(**authority) as journal:
        snapshot = journal.load()
        for key, grant in snapshot.records.items():
            if (
                not key.startswith("broker:grant:")
                or grant.get("attempt_id") != attempt_id
            ):
                continue
            if (
                grant.get("database_identity"),
                grant.get("project_id"),
                grant.get("task_id"),
                grant.get("fence"),
            ) != (origin, project_id, run["task_id"], fence):
                raise RunConflict(
                    "Original global publication grant provenance differs"
                )
            grant_id = key.removeprefix("broker:grant:")
            closed = PeerBroker.recover(journal, grant_id)
            if (
                closed.get("state") != "retired"
                or closed.get("domain_removed") is not True
            ):
                raise RunConflict(
                    "Original publication domain retirement is unconfirmed"
                )
            PeerBroker.project_recovered(journal, grant_id)
            grants.append(grant_id)
        operations = [
            op
            for key, op in journal.load().records.items()
            if key.startswith("broker:op:") and op.get("grant_id") in grants
        ]
        if any(op.get("execution_closed") is not True for op in operations):
            raise RunConflict("Original publication operations have not all closed")
    with store._transaction() as conn:
        peers = [
            dict(p)
            for p in conn.execute(
                "SELECT * FROM runtime_peers WHERE attempt_id=?", (attempt_id,)
            )
        ]
    for peer in peers:
        if peer["init_pid"] is not None and not grants:
            raise RunConflict(
                "Original global domain proof is missing for a bound publication command"
            )
        if peer["state"] != "closed" and (
            peer["state"] != "prepared" or peer["init_pid"] is not None
        ):
            raise RunConflict(
                "Unwitnessed original process authority cannot be adopted"
            )
        registry.close(peer["id"])
    with store._transaction() as conn:
        store._closed_peer_proof(conn, attempt_id)
    return {
        "attempt_id": attempt_id,
        "fence": fence,
        "database_identity": origin,
        "execution_closed": True,
        "grant_ids": grants,
    }

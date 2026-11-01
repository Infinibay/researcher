"""Real private files and SQL; these tests do not provision a host actor domain."""

import fcntl
import os
import shutil
import sqlite3

import pytest

from backend.tests.runtime.authority_fixture import (
    canonical,
    digest,
    fingerprint,
    journal,
    provisioned,
)


def test_missing_authority_files_never_become_an_empty_installation(tmp_path):
    from backend.runtime.authority_journal import (
        AuthorityUncertain,
        WitnessedAuthorityJournal,
    )

    paths = {
        key: tmp_path / name
        for key, name in [
            ("database", "missing.db"),
            ("witness", "missing.log"),
            ("mutex", "missing.lock"),
        ]
    }
    with (
        pytest.raises(AuthorityUncertain),
        WitnessedAuthorityJournal(**paths, authority_id="not-provisioned") as j,
    ):
        j.load()
    assert not any(p.exists() for p in paths.values())


def test_commit_has_real_state_hash_and_reopens_without_project_database(tmp_path):
    c = provisioned(tmp_path)
    records = {"grant:a": {"attempt_id": "a", "fence": 1, "state": "reserved"}}
    with journal(c) as j:
        before = j.load()
        receipt = j.commit(before, transition_id="reserve-a", puts=records)
        assert (
            receipt.sequence == 1
            and receipt.state_hash == digest(records)
            and receipt.fresh
        )
    with journal(c) as j:
        after = j.load()
        assert (
            after.sequence == 1
            and after.records == records
            and after.state_hash == digest(records)
        )
    assert not (tmp_path / "research.db").exists()


def test_retry_recovers_original_receipt_even_after_later_commits(tmp_path):
    from backend.runtime.authority_journal import AuthorityConflict

    c = provisioned(tmp_path)
    with journal(c) as j:
        initial = j.load()
        first = j.commit(initial, transition_id="one", puts={"fence": 1})
        j.commit(j.load(), transition_id="two", puts={"fence": 2})
        replay = j.commit(initial, transition_id="one", puts={"fence": 1})
        assert not replay.fresh and replay.sequence == first.sequence
        assert j.load().records == {"fence": 2}
        with pytest.raises(AuthorityConflict):
            j.commit(initial, transition_id="one", puts={"fence": 3})


def test_stale_writer_does_not_change_either_store(tmp_path):
    from backend.runtime.authority_journal import AuthorityConflict

    c = provisioned(tmp_path)
    with journal(c) as j:
        stale = j.load()
        j.commit(stale, transition_id="one", puts={"fence": 1})
        before = fingerprint(c)
        with pytest.raises(AuthorityConflict):
            j.commit(stale, transition_id="two", puts={"fence": 2})
        assert fingerprint(c) == before


def test_put_and_delete_are_one_witnessed_transition(tmp_path):
    c = provisioned(tmp_path, {"old": {"closed": True}, "keep": "ñ"})
    with journal(c) as j:
        j.commit(
            j.load(),
            transition_id="replace",
            puts={"new": {"fence": 2}},
            deletes=("old",),
        )
        assert j.load().records == {"keep": "ñ", "new": {"fence": 2}}


@pytest.mark.parametrize("missing", ["database", "witness", "mutex"])
def test_lost_file_is_not_recreated_by_live_or_new_owner(tmp_path, missing):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    with journal(c) as existing:
        existing.load()
        getattr(c, missing).unlink()
        with pytest.raises(AuthorityUncertain):
            existing.load()
        with pytest.raises(AuthorityUncertain), journal(c) as another:
            another.load()
        assert not getattr(c, missing).exists()


@pytest.mark.parametrize("changed", ["database", "witness", "mutex"])
def test_atomic_replacement_does_not_create_another_coordination_domain(
    tmp_path, changed
):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    with journal(c) as existing:
        existing.load()
        path = getattr(c, changed)
        replacement = path.with_suffix(".replacement")
        shutil.copyfile(path, replacement)
        replacement.chmod(0o600)
        replacement.replace(path)
        with pytest.raises(AuthorityUncertain):
            existing.load()
        with pytest.raises(AuthorityUncertain), journal(c) as another:
            another.load()


def test_same_inode_database_rewind_is_detected_against_external_witness(tmp_path):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    original = c.database.read_bytes()
    inode = c.database.stat().st_ino
    with journal(c) as j:
        j.commit(
            j.load(),
            transition_id="one",
            puts={"peer:a": {"state": "bound", "init_pid": 9}},
        )
    c.database.write_bytes(original)
    assert c.database.stat().st_ino == inode
    before = fingerprint(c)
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()
    assert fingerprint(c) == before


def test_witness_rewind_is_not_repaired_by_adopting_a_newer_database(tmp_path):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    original = c.witness.read_bytes()
    with journal(c) as j:
        j.commit(j.load(), transition_id="one", puts={"fence": 1})
    c.witness.write_bytes(original)
    before = fingerprint(c)
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()
    assert fingerprint(c) == before


def test_row_tampering_with_unchanged_sequence_and_metadata_hash_is_detected(tmp_path):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path, {"grant:a": {"state": "revoked"}})
    with sqlite3.connect(c.database) as conn:
        conn.execute(
            "UPDATE authority_records SET value_json=?",
            (canonical({"state": "active"}).decode(),),
        )
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()


def test_only_unterminated_tail_is_recoverable_and_not_a_corrupt_complete_record(
    tmp_path,
):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    good = c.witness.read_bytes()
    with c.witness.open("ab") as f:
        f.write(b'{"incomplete":')
    with journal(c) as j:
        assert j.load().sequence == 0
    assert c.witness.read_bytes() == good
    with c.witness.open("ab") as f:
        f.write(b"not a record\n")
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()


def test_busy_mutex_is_not_interpreted_as_missing_authority(tmp_path):
    from backend.runtime.authority_journal import AuthorityBusy

    c = provisioned(tmp_path)
    fd = os.open(c.mutex, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = fingerprint(c)
        with journal(c) as j, pytest.raises(AuthorityBusy):
            j.load()
        assert fingerprint(c) == before
    finally:
        os.close(fd)


@pytest.mark.parametrize("changed", ["database", "witness", "mutex"])
def test_symlink_and_hardlink_authority_files_are_rejected(tmp_path, changed):
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    path = getattr(c, changed)
    alias = path.with_suffix(".alias")
    os.link(path, alias)
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()
    alias.unlink()
    path.rename(alias)
    path.symlink_to(alias)
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()


def test_changed_kernel_or_observer_cannot_adopt_a_copy(tmp_path, monkeypatch):
    from backend.runtime import authority_journal

    c = provisioned(tmp_path)
    monkeypatch.setattr(authority_journal, "boot_id", lambda: "other-host-or-boot")
    with pytest.raises(authority_journal.AuthorityUncertain), journal(c) as j:
        j.load()


@pytest.mark.parametrize("sequence", [False, 0.0, -1, "0", 2**63])
def test_invalid_expected_sequence_never_enters_the_witness(tmp_path, sequence):
    from dataclasses import replace

    c = provisioned(tmp_path)
    with journal(c) as j:
        expected = replace(j.load(), sequence=sequence)
        before = fingerprint(c)
        with pytest.raises(ValueError):
            j.commit(expected, transition_id="bad-sequence", puts={"fence": 1})
        assert fingerprint(c) == before


@pytest.mark.parametrize("field", ["format", "sequence"])
def test_boolean_format_or_sequence_is_not_an_integer_version(tmp_path, field):
    import json

    from backend.runtime.authority_journal import AuthorityUncertain
    from backend.tests.runtime.authority_fixture import envelope

    c = provisioned(tmp_path)
    payloads = [
        json.loads(line)["payload"] for line in c.witness.read_text().splitlines()
    ]
    payloads[0 if field == "format" else 1][field] = field == "format"
    records = []
    previous = None
    for payload in payloads:
        record = envelope(payload, previous)
        records.append(canonical(record) + b"\n")
        previous = record["digest"]
    c.witness.write_bytes(b"".join(records))
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()


def test_zero_length_witness_write_stops_without_spinning_or_touching_sql(
    tmp_path, monkeypatch
):
    from backend.runtime import authority_journal

    c = provisioned(tmp_path)
    with journal(c) as j:
        initial = j.load()
        before = fingerprint(c)
        calls = []

        def stalled(_fd, _data):
            calls.append(True)
            if len(calls) > 1:
                raise OSError("a stalled write must not spin")
            return 0

        with monkeypatch.context() as patch:
            patch.setattr(authority_journal.os, "write", stalled)
            with pytest.raises(authority_journal.AuthorityUncertain):
                j.commit(initial, transition_id="stalled", puts={"fence": 1})
        assert len(calls) == 1
        assert fingerprint(c) == before


@pytest.mark.parametrize(
    "bad_header", [[], {"files": None}, {"files": {"database": None}}]
)
def test_malformed_enrollment_is_uncertain_not_an_unclassified_exception(
    tmp_path, bad_header
):
    import json

    from backend.runtime.authority_journal import AuthorityUncertain
    from backend.tests.runtime.authority_fixture import envelope

    c = provisioned(tmp_path)
    payloads = [
        json.loads(line)["payload"] for line in c.witness.read_text().splitlines()
    ]
    payloads[0] = (
        bad_header if isinstance(bad_header, list) else {**payloads[0], **bad_header}
    )
    lines = []
    previous = None
    for payload in payloads:
        record = envelope(payload, previous)
        lines.append(canonical(record) + b"\n")
        previous = record["digest"]
    c.witness.write_bytes(b"".join(lines))
    before = fingerprint(c)
    with pytest.raises(AuthorityUncertain), journal(c) as j:
        j.load()
    assert fingerprint(c) == before


def test_lost_commit_sync_receipt_never_replays_the_transition(tmp_path, monkeypatch):
    import json

    from backend.runtime import authority_journal

    c = provisioned(tmp_path)
    witness_inode = c.witness.stat().st_ino
    real_fsync = os.fsync

    def unavailable_after_commit(fd):
        if os.fstat(fd).st_ino == witness_inode:
            last = json.loads(c.witness.read_bytes().splitlines()[-1])["payload"]
            if last["kind"] == "COMMIT" and last["sequence"] == 1:
                raise OSError("lost durability acknowledgment")
        return real_fsync(fd)

    with journal(c) as j:
        initial = j.load()
        with monkeypatch.context() as patch:
            patch.setattr(authority_journal.os, "fsync", unavailable_after_commit)
            with pytest.raises(authority_journal.AuthorityUncertain):
                j.commit(initial, transition_id="lost-ack", puts={"fence": 1})
            # Complete bytes alone do not let load claim durable verification.
            with pytest.raises(authority_journal.AuthorityUncertain):
                j.load()
        assert j.load().records == {"fence": 1}
        receipt = j.commit(initial, transition_id="lost-ack", puts={"fence": 1})
        assert receipt.sequence == 1 and not receipt.fresh
        assert j.load().sequence == 1
    payloads = [
        json.loads(line)["payload"] for line in c.witness.read_bytes().splitlines()
    ]
    assert sum(p["kind"] == "PREPARE" for p in payloads) == 1
    assert sum(p["kind"] == "COMMIT" and p["sequence"] == 1 for p in payloads) == 1


def test_capacity_reserves_commit_space_before_prepare_or_sql(tmp_path, monkeypatch):
    from backend.runtime import authority_journal

    reference = tmp_path / "reference"
    reference.mkdir(mode=0o700)
    r = provisioned(reference)
    with journal(r) as j:
        j.commit(j.load(), transition_id="bounded", puts={"fence": 1})
    prepare_bytes = len(r.witness.read_bytes().splitlines(keepends=True)[-2])
    c = provisioned(tmp_path)
    with journal(c) as j:
        initial = j.load()
        before = fingerprint(c)
        monkeypatch.setattr(
            authority_journal,
            "MAX_JOURNAL_BYTES",
            c.witness.stat().st_size + prepare_bytes,
        )
        with pytest.raises(authority_journal.AuthorityCapacity):
            j.commit(initial, transition_id="bounded", puts={"fence": 1})
        assert fingerprint(c) == before
        assert j.load().sequence == 0


def test_external_sql_writer_is_contention_not_a_new_authority(tmp_path):
    import sqlite3

    from backend.runtime.authority_journal import AuthorityBusy

    c = provisioned(tmp_path)
    with journal(c) as j, sqlite3.connect(c.database) as conn:
        initial = j.load()
        before = fingerprint(c)
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(AuthorityBusy):
            j.load()
        assert fingerprint(c) == before
        conn.rollback()
        assert j.load() == initial

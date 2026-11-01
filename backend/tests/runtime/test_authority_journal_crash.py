"""SIGKILL boundaries and competing processes over the witnessed storage core."""

import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests.runtime.authority_fixture import journal, provisioned


def command(c, *extra):
    return [
        sys.executable,
        "-I",
        str(Path(__file__).with_name("fake_authority_writer.py")),
        "--database",
        str(c.database),
        "--witness",
        str(c.witness),
        "--mutex",
        str(c.mutex),
        "--authority-id",
        c.authority_id,
        *extra,
    ]


def test_forked_handle_rejects_and_closes_without_waiting_on_inherited_thread_lock(
    tmp_path,
):
    c = provisioned(tmp_path)
    child = subprocess.run(
        command(c, "--phase", "fork-handle"),
        check=False,
        env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        capture_output=True,
        timeout=8,
    )
    assert child.returncode == 0, child.stderr.decode()
    assert json.loads(child.stdout)["outcome"] == "rejected-and-closed"


@pytest.mark.parametrize(
    "phase",
    [
        "before_prepare",
        "after_prepare",
        "in_sql",
        "after_sql",
        "partial_commit",
        "after_commit",
    ],
)
def test_sigkill_reconciles_storage_without_replaying_a_transition(tmp_path, phase):
    c = provisioned(tmp_path)
    with journal(c) as j:
        initial = j.load()
    child = subprocess.run(
        command(c, "--phase", phase),
        check=False,
        env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        capture_output=True,
        timeout=8,
    )
    assert child.returncode == -signal.SIGKILL, child.stderr.decode()
    with journal(c) as j:
        state = j.load()
        if phase == "before_prepare":
            assert state.sequence == 0 and state.records == {}
        else:
            assert state.sequence == 1 and state.records == {
                "grant:a": {"fence": 1, "state": "reserved"}
            }
        receipt = j.commit(
            initial,
            transition_id="claim-one",
            puts={"grant:a": {"fence": 1, "state": "reserved"}},
        )
        assert receipt.fresh == (phase == "before_prepare")
        assert j.load().sequence == 1 and "uncommitted" not in j.load().records
        assert j.load().recovered == ()
    records = [
        json.loads(line)["payload"] for line in c.witness.read_text().splitlines()
    ]
    assert sum(r["kind"] == "PREPARE" for r in records) == 1
    assert sum(r["kind"] == "COMMIT" and r["sequence"] == 1 for r in records) == 1


def test_two_processes_cannot_both_commit_from_the_same_authority_state(tmp_path):
    c = provisioned(tmp_path)
    children = [
        subprocess.Popen(
            command(c, "--barrier", "--transition", f"writer-{i}"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        for i in range(2)
    ]
    try:
        for child in children:
            assert select.select([child.stdout], [], [], 6)[0]
            assert child.stdout.readline() == b"READY\n"
        for child in children:
            child.stdin.write(b"go\n")
            child.stdin.flush()
        outcomes = []
        for child in children:
            out, err = child.communicate(timeout=8)
            assert child.returncode == 0, err.decode()
            outcomes.append(json.loads(out)["outcome"])
        assert sorted(outcomes) == ["committed", "conflict"]
        with journal(c) as j:
            assert j.load().sequence == 1
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)

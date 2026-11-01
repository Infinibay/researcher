"""Trusted crash injector over synthetic files; never a production launcher."""

import argparse
import json
import os
import select
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.runtime.authority_journal import (
    AuthorityBusy,
    AuthorityConflict,
    AuthorityUncertain,
    WitnessedAuthorityJournal,
)


def die():
    os.kill(os.getpid(), signal.SIGKILL)


def forked_handle(journal):
    """A child must reject/close its copies even if another thread held the lock."""
    held, release = threading.Event(), threading.Event()

    def hold():
        with journal._local:
            held.set()
            release.wait(5)

    owner = threading.Thread(target=hold)
    owner.start()
    assert held.wait(2)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            journal.load()
        except AuthorityUncertain:
            journal.close()
            os.write(write_fd, b"rejected-and-closed")
        os._exit(0)
    os.close(write_fd)
    try:
        if select.select([read_fd], [], [], 2)[0]:
            outcome = os.read(read_fd, 128).decode()
        else:
            outcome = "blocked-on-inherited-lock"
            os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    finally:
        os.close(read_fd)
        release.set()
        owner.join(2)
    assert journal.load().sequence == 0, "Child closed the parent's handles"
    return outcome


class CrashingJournal(WitnessedAuthorityJournal):
    phase = None

    def _append_record(self, payload, previous):
        if payload["kind"] == "PREPARE" and self.phase == "before_prepare":
            die()
        if payload["kind"] == "COMMIT" and self.phase == "partial_commit":
            os.write(self._fds["witness"], b'{"torn_commit":')
            os.fsync(self._fds["witness"])
            die()
        result = super()._append_record(payload, previous)
        if (payload["kind"], self.phase) in (
            ("PREPARE", "after_prepare"),
            ("COMMIT", "after_commit"),
        ):
            die()
        return result

    def _write_database(self, conn, prepare):
        if self.phase == "in_sql":
            conn.execute("PRAGMA cache_size=1")
            conn.execute(
                "INSERT INTO authority_records VALUES('uncommitted',?)",
                (json.dumps({"discard": "x" * 16384}),),
            )
            die()
        super()._write_database(conn, prepare)
        if self.phase == "after_sql":
            die()


def main():
    parser = argparse.ArgumentParser()
    for key in ("database", "witness", "mutex", "authority-id"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--phase", default="normal")
    parser.add_argument("--transition", default="claim-one")
    parser.add_argument("--barrier", action="store_true")
    args = parser.parse_args()
    with CrashingJournal(
        database=args.database,
        witness=args.witness,
        mutex=args.mutex,
        authority_id=args.authority_id,
    ) as journal:
        if args.phase == "fork-handle":
            print(json.dumps({"outcome": forked_handle(journal)}), flush=True)
            return
        if args.phase == "recover-peer":
            from backend.runtime.peer_process import NamespaceIdentity, close_namespace

            state = journal.load()
            peer = state.records["peer:owned"]
            reason = close_namespace(NamespaceIdentity.from_record(peer))
            journal.commit(
                state,
                transition_id="close-peer",
                puts={
                    "peer:owned": {**peer, "state": "closed", "closure_reason": reason}
                },
            )
            print(json.dumps({"outcome": "closed", "reason": reason}), flush=True)
            return
        until = time.monotonic() + 4
        while True:
            try:
                initial = journal.load()
                break
            except AuthorityBusy:
                if time.monotonic() > until:
                    raise
                time.sleep(0.01)
        journal.phase = args.phase
        if args.barrier:
            print("READY", flush=True)
            assert sys.stdin.readline() == "go\n"
        while True:
            try:
                receipt = journal.commit(
                    initial,
                    transition_id=args.transition,
                    puts={"grant:a": {"fence": 1, "state": "reserved"}},
                )
                print(
                    json.dumps({"outcome": "committed", "sequence": receipt.sequence}),
                    flush=True,
                )
                return
            except AuthorityConflict:
                print(json.dumps({"outcome": "conflict"}), flush=True)
                return
            except AuthorityBusy:
                if time.monotonic() > until:
                    raise
                time.sleep(0.01)


if __name__ == "__main__":
    main()

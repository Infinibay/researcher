"""Crash boundary over the real host broker/profile; no model or bootstrap."""

import argparse
import json
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.execution_domain import ExecutionDomain
from backend.runtime.peer_broker import PeerBroker
from backend.runtime.peer_registry import PeerRegistry
from backend.runtime.sqlite_runs import SQLiteRunStore


def main():
    parser = argparse.ArgumentParser()
    for key in ("database", "witness", "mutex", "authority-id"):
        parser.add_argument("--" + key, required=True)
    for key in ("source", "peer", "domain", "recover", "phase"):
        parser.add_argument("--" + key)
    args = parser.parse_args()
    with WitnessedAuthorityJournal(
        database=args.database,
        witness=args.witness,
        mutex=args.mutex,
        authority_id=args.authority_id,
    ) as journal:
        if args.recover:
            receipt = PeerBroker.recover(journal, args.recover)
            print(json.dumps({"state": receipt["state"]}), flush=True)
            return
        with ExecutionDomain.open(args.domain) as domain:
            broker = PeerBroker(journal, domain)
            registry = PeerRegistry(SQLiteRunStore(args.source))

            def crash():
                print(
                    json.dumps({"grant_id": broker.grant_id, "phase": args.phase}),
                    flush=True,
                )
                assert sys.stdin.readline() == "crash\n"
                os.kill(os.getpid(), signal.SIGKILL)

            if args.phase == "before-local":

                def held(*_args):
                    crash()

                registry.bind = held
            else:
                original = broker._update

                def update(operation_id, **changes):
                    if (
                        args.phase == "before-global"
                        and changes["state"] == "published"
                    ):
                        crash()
                    if changes["state"] == "released":
                        child = broker._children[operation_id]
                        assert child.stdout.readline() == b"PAYLOAD RAN\n"
                        crash()
                    return original(operation_id, **changes)

                broker._update = update
            broker.run_peer(
                registry,
                args.peer,
                operation_key="crash-boundary",
                code="print('PAYLOAD RAN',flush=True);import time;time.sleep(30)",
            )


if __name__ == "__main__":
    main()

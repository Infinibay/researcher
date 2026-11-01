"""Trusted pre-publication crash fixture; not a production broker/bootstrap."""

import argparse
import json
import os
import signal
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.execution_domain import DomainIdentity, ExecutionDomain


def main():
    parser = argparse.ArgumentParser()
    for name in ("database", "witness", "mutex", "authority-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--domain")
    parser.add_argument("--heartbeat")
    parser.add_argument("--permit")
    parser.add_argument("--late")
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    with WitnessedAuthorityJournal(
        database=args.database,
        witness=args.witness,
        mutex=args.mutex,
        authority_id=args.authority_id,
    ) as journal:
        state = journal.load()
        if args.recover:
            record = state.records["domain"]
            with ExecutionDomain.open(
                record["path"], expected=DomainIdentity(**record["identity"])
            ) as domain:
                closure = domain.retire(timeout=3)
            journal.commit(
                state,
                transition_id="domain-closed",
                puts={
                    "domain": {**record, "state": "retired", "removed": closure.removed}
                },
            )
            print(json.dumps({"removed": closure.removed}), flush=True)
            return
        with ExecutionDomain.open(args.domain) as domain:
            journal.commit(
                state,
                transition_id="domain-intent",
                puts={
                    "domain": {
                        "path": args.domain,
                        "identity": asdict(domain.identity),
                        "state": "starting",
                        "published_peers": [],
                    }
                },
            )
            # Model-free fixture for a trusted constructor before PID publication.
            # Both it and a detached child are born in the already recorded domain.
            code = """import os,sys,time
from pathlib import Path
if os.fork()==0:
 os.setsid()
 while not Path(sys.argv[2]).exists():
  Path(sys.argv[1]).write_text(str(time.monotonic_ns()))
  time.sleep(.01)
 Path(sys.argv[3]).write_text('escaped')
 os._exit(0)
print('born',flush=True)
time.sleep(30)
"""
            child = domain.spawn(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-c",
                    code,
                    args.heartbeat,
                    args.permit,
                    args.late,
                ]
            )
            assert child.stdout.readline() == b"born\n"
            print("BORN-BEFORE-PUBLICATION", flush=True)
            assert sys.stdin.readline() == "crash\n"
            os.kill(os.getpid(), signal.SIGKILL)


if __name__ == "__main__":
    main()

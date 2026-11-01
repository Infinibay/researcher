"""Inference-free explicit initialization for a NEW installation only."""

import argparse
import json
import sqlite3
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Initialize NEW installation storage. Never repair/adopt a lost or existing deployment."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    database = commands.add_parser(
        "init-db", help="Create a NEW source database; refuse every existing file"
    )
    database.add_argument("--database", required=True)
    authority = commands.add_parser(
        "init-authority", help="Create NEW authority stores; existing parents required"
    )
    authority.add_argument("--database-dir", required=True)
    authority.add_argument("--witness-dir", required=True)
    options = parser.parse_args(argv)
    # Lazy import: even --help has no database/runtime/credential side effects.
    from backend.runtime.bootstrap import initialize_authority, initialize_database

    try:
        if options.command == "init-db":
            result = {"database": str(initialize_database(options.database))}
        else:
            result = initialize_authority(
                database_dir=options.database_dir, witness_dir=options.witness_dir
            )
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
        print(
            f"Initialization refused/failed: {exc}. Keep any partial paths for inspection; "
            "do not delete existing state or retry as a repair.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

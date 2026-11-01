"""Explicit inference-free storage initialization and pinned local retrieval preparation."""

import argparse
import json
import sqlite3
import sys


def main(argv=None):
    """Run one explicit setup action; help never reads assets, initializes data or downloads."""
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
    retrieval = commands.add_parser(
        "prepare-retrieval",
        help="Prepare fixed public semantic weights; never download during serving",
    )
    retrieval.add_argument("--directory", required=True)
    retrieval.add_argument("--cache-dir", required=True)
    retrieval.add_argument("--offline", action="store_true")
    options = parser.parse_args(argv)
    # Lazy import: even --help has no database/runtime/credential side effects.
    from backend.runtime.bootstrap import initialize_authority, initialize_database

    try:
        if options.command == "prepare-retrieval":
            from backend.research.retrieval_assets import prepare

            result = prepare(
                options.directory, cache_dir=options.cache_dir, offline=options.offline
            )
        elif options.command == "init-db":
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

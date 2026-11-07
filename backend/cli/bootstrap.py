"""Explicit inference-free storage/host initialization and local resource diagnostics."""

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
    host = commands.add_parser('init-host', help='Prepare a NEW native installation using explicit existing host assets')
    host.add_argument('--directory', required=True)
    host.add_argument('--witness-dir', required=True)
    host.add_argument('--assets', required=True, help='Operator JSON with native/Ken/account/cache/cgroup paths and model')
    check = commands.add_parser('check-host', help='Verify local host resources without inference or downloads')
    check.add_argument('--directory', required=True)
    check.add_argument('--probe', action='store_true', help='Also birth and retire one fixed no-op kernel child')
    options = parser.parse_args(argv)
    # Lazy import: even --help has no database/runtime/credential side effects.
    from backend.runtime.bootstrap import initialize_authority, initialize_database

    try:
        if options.command == 'init-host':
            from backend.runtime.host_installation import initialize_host, _read_json

            result = initialize_host(options.directory, witness_dir=options.witness_dir, assets=_read_json(options.assets))
        elif options.command == 'check-host':
            from backend.runtime.host_installation import inspect_host

            result = inspect_host(options.directory, probe=options.probe)
        elif options.command == "prepare-retrieval":
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

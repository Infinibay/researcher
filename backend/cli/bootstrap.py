"""Explicit inference-free host initialization, data backup/restore and local diagnostics."""

import argparse
import json
import sqlite3
import sys


def main(argv=None, *, _in_worker=False):
    """Run one explicit local administration action; help never reads assets, initializes data or downloads."""
    parser = argparse.ArgumentParser(
        description="Initialize new storage, inspect resources, or explicitly back up and restore data. Restored execution requires separate enrollment."
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
    grammars = commands.add_parser('prepare-ken-grammars', help='Prepare pinned public parsers in the trusted Ken tool installation, without inference')
    grammars.add_argument('--ken-command', required=True)
    grammars.add_argument('--archive', required=True, help='Previously downloaded pinned Linux x86_64 grammar archive')
    host = commands.add_parser('init-host', help='Prepare a NEW native installation using explicit existing host assets')
    host.add_argument('--directory', required=True)
    host.add_argument('--witness-dir', required=True)
    host.add_argument('--assets', required=True, help='Operator JSON with native/Ken/account/cache/cgroup paths and model')
    enroll = commands.add_parser('enroll-restored-host', help='Enable a completed restore with NEW authority; copied unfinished work stays historical')
    enroll.add_argument('--directory', required=True)
    enroll.add_argument('--witness-dir', required=True)
    enroll.add_argument('--assets', required=True, help='Explicit native/Ken/account/cache/cgroup paths and model for the new host')
    check = commands.add_parser('check-host', help='Verify local host resources without inference or downloads')
    check.add_argument('--directory', required=True)
    check.add_argument('--probe', action='store_true', help='Also birth and retire one fixed no-op kernel child')
    legacy = commands.add_parser('stage-legacy-host',help='Copy legacy SQL/files into a NEW pending host using explicit storage mappings')
    legacy.add_argument('--database',required=True)
    legacy.add_argument('--storage-manifest',required=True)
    legacy.add_argument('--destination',required=True)
    legacy.add_argument('--max-bytes',type=int,default=20*1024**3)
    legacy.add_argument('--max-files',type=int,default=200000)
    legacy.add_argument('--timeout',type=int,default=300)
    for command, description in (
        ('backup-host', 'Capture consistent installation data after closing native work'),
        ('verify-backup', 'Verify every backup object, path, database and manifest'),
        ('restore-host', 'Restore data into a NEW directory; execution remains pending enrollment'),
    ):
        operation = commands.add_parser(command, help=description)
        operation.add_argument('--directory' if command == 'backup-host' else '--backup', required=True)
        if command == 'backup-host':
            operation.add_argument('--after-reboot',action='store_true',help='Explicitly archive verified old-kernel authority; never replay its work')
        if command != 'verify-backup':
            operation.add_argument('--destination', required=True)
        operation.add_argument('--max-bytes', type=int, default=20 * 1024**3)
        operation.add_argument('--max-files', type=int, default=200000)
        operation.add_argument('--timeout', type=int, default=300)
    options = parser.parse_args(argv)
    from backend.runtime.administration_process import COMMANDS, run_administration

    if options.command in COMMANDS and not _in_worker:
        try:
            return run_administration(vars(options))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f'Administrative operation refused: {exc}. No automatic retry was attempted.', file=sys.stderr)
            return 1
    # Lazy import: even --help has no database/runtime/credential side effects.
    from backend.runtime.bootstrap import initialize_authority, initialize_database

    try:
        if options.command == 'stage-legacy-host':
            from backend.runtime.legacy_import import stage_legacy_host
            from backend.runtime.host_installation import _read_json

            result=stage_legacy_host(options.database,options.destination,manifest=_read_json(options.storage_manifest),
                                     **{key:getattr(options,key) for key in ('max_bytes','max_files','timeout')})
        elif options.command in ('backup-host', 'verify-backup', 'restore-host'):
            from backend.runtime.installation_backup import backup_installation, verify_backup
            from backend.runtime.installation_restore import restore_installation

            limits = {key: getattr(options, key) for key in ('max_bytes','max_files','timeout')}
            if options.command == 'backup-host':
                result = backup_installation(options.directory, options.destination, after_reboot=options.after_reboot, **limits)
            elif options.command == 'restore-host':
                result = restore_installation(options.backup, options.destination, **limits)
            else:
                manifest = verify_backup(options.backup, **limits)
                result = {'status':'verified','snapshot_id':manifest['snapshot_id'],'entries':len(manifest['entries']),'bytes':manifest['bytes'],'execution_enrolled':False}
        elif options.command == 'enroll-restored-host':
            from backend.runtime.restored_enrollment import enroll_restored_host
            from backend.runtime.host_installation import _read_json

            result = enroll_restored_host(options.directory, witness_dir=options.witness_dir, assets=_read_json(options.assets))
        elif options.command == 'init-host':
            from backend.runtime.host_installation import initialize_host, _read_json

            result = initialize_host(options.directory, witness_dir=options.witness_dir, assets=_read_json(options.assets))
        elif options.command == 'check-host':
            from backend.runtime.host_installation import inspect_host

            result = inspect_host(options.directory, probe=options.probe)
        elif options.command == 'prepare-ken-grammars':
            from pathlib import Path

            from backend.runtime.ken_grammars import prepare_grammars
            from backend.runtime.ken_worker import KenInstallation

            installation = KenInstallation.inspect(Path(options.ken_command), require_grammars=False)
            result = prepare_grammars(installation.tool_root, options.archive)
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
    except MemoryError:
        print('Operation exceeded its memory budget. Keep partial paths and inspect completion '
              'receipts; no automatic retry or repair was attempted.', file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError, KeyError, TypeError) as exc:
        print(
            f"Operation refused/failed: {exc}. Keep any partial paths for inspection; "
            "do not delete existing state or retry as a repair.",
            file=sys.stderr,
        )
        return 1
    if _in_worker:
        from backend.runtime.administration_process import observed_limits

        result['execution_limits'] = observed_limits()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

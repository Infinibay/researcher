"""Stage explicit legacy SQL/files into a new managed host without modifying or activating the original.

Container paths require operator mappings. Original IDs, source snapshots and
raw files remain evidence; report hydration never invents review/acceptance.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from contextlib import closing
from uuid import uuid4

from backend.runtime.bootstrap import _sync_directory
from backend.runtime.host_installation import _write_new
from backend.runtime.installation_backup import _database_copy, database_receipt, new_directory
from backend.runtime.installation_restore import _git_metadata
from backend.runtime.snapshot_files import CopyBudget, copy_regular, digest_file, inventory, open_file


def _storage(manifest, destination, database):
    """Validate explicit disjoint source roots and logical prefixes before creating any output."""
    if not isinstance(manifest,dict) or set(manifest)!={'format','storage','chroma_exports'} or manifest['format']!=1:
        raise ValueError('Expected legacy storage manifest format1 with storage and chroma_exports')
    if not isinstance(manifest['storage'],list) or not isinstance(manifest['chroma_exports'],list):
        raise ValueError('Legacy storage and exports must be lists')
    roots=[]
    for row in manifest['storage']:
        if not isinstance(row,dict) or set(row)!={'name','path','stored_prefix'}:
            raise ValueError('Storage mapping requires name, path and stored_prefix')
        if not isinstance(row['name'],str) or re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',row['name']) is None:
            raise ValueError('Storage name must be a short lowercase identifier')
        source=Path(row['path']);prefix=Path(row['stored_prefix'])
        if not source.is_absolute() or not prefix.is_absolute() or '..' in prefix.parts or prefix==Path('/'):
            raise ValueError('Storage roots/prefixes must be explicit absolute non-root paths')
        source=source.resolve(strict=True)
        if not source.is_dir() or database.is_relative_to(source):
            raise ValueError('Map storage directories separately from the original database')
        if destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ValueError('Legacy destination must not overlap original storage')
        target=destination/'sources'/('legacy-'+row['name'])
        if any(row['name']==old['name'] or source.is_relative_to(old['source']) or old['source'].is_relative_to(source)
               or prefix.is_relative_to(old['prefix']) or old['prefix'].is_relative_to(prefix) for old in roots):
            raise ValueError('Legacy storage mappings must have unique names and disjoint roots/prefixes')
        roots.append({'name':row['name'],'source':source,'prefix':prefix,'target':target})
    return roots


def _mapped(value, roots):
    """Resolve an exact stored or actual absolute path through one unambiguous operator mapping."""
    path=Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Legacy registration needs an explicit absolute mapped path')
    matches=set()
    for item in roots:
        for prefix in (item['source'],item['prefix']):
            if path.is_relative_to(prefix):
                matches.add(item['target']/path.relative_to(prefix))
    if len(matches)!=1:
        raise ValueError('Legacy path has no unique explicit storage mapping')
    return matches.pop()


def _copy_storage(roots, budget):
    """Copy raw trees with stable inventories and hashes, then repair only copied Git path metadata."""
    receipts=[];total=0
    for item in roots:
        first=inventory(item['source'],budget)
        total+=len(first);budget.check(entries=total)
        item['target'].mkdir(mode=0o700)
        entries=[]
        for name,info in first.items():
            target=item['target']/name
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            entry={'path':name,'kind':info['kind'],'mode':info['mode']&0o777}
            if info['kind']=='directory':target.mkdir(exist_ok=True,mode=0o700)
            elif info['kind']=='symlink':
                entry['target']=info['target']
                # Preserve evidence; no source symlink is followed during import.
                os.symlink(info['target'],target)
            else:
                entry.update(copy_regular(item['source'],name,target,budget))
                target.chmod(entry['mode'])
            entries.append(entry)
        if inventory(item['source'],budget)!=first:
            raise ValueError('Legacy storage changed during import; partial target stays inactive')
        for entry in entries:
            if entry['kind']=='file' and digest_file(item['source'],entry['path'],budget)!={k:entry[k] for k in ('bytes','sha256')}:
                raise ValueError('Legacy storage bytes changed during import')
        receipts.append({'name':item['name'],'source':str(item['source']),'stored_prefix':str(item['prefix']),
                         'target':str(item['target']),'entries':entries})
    for item,receipt in zip(roots,receipts):
        receipt['git_path_files_repaired']=_git_metadata(item['target'],receipt['entries'],item['source'],remap=lambda value:_mapped(value,roots))
    return receipts


def _hydrate_reports(db, root, roots, budget):
    """Read only exact mapped UTF8 reports missing database content; preserve existing bodies and IDs."""
    changes=[]
    for identity,path,content in db.execute("SELECT id,file_path,content FROM artifacts WHERE type='report'").fetchall():
        if content is not None:
            continue
        source=_mapped(path,roots)
        with open_file(root,str(source.relative_to(root))) as stream:
            raw=stream.read(min(budget.max_bytes,16*1024**2)+1)
        budget.check()
        if len(raw)>min(budget.max_bytes,16*1024**2):
            raise ValueError('Legacy report exceeds the explicit16MiB hydration limit')
        body=raw.decode('utf-8')
        db.execute('UPDATE artifacts SET content=? WHERE id=? AND content IS NULL',(body,identity))
        changes.append({'artifact_id':identity,'original_path':path,'copied_path':str(source),
                        'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'review_status_created':False})
    return changes


def _registrations(db, root, roots, budget):
    """Normalize uploads and relocate current repositories/worktrees, preserving their IDs and old paths in receipts."""
    changes=[]
    for identity,project,path in db.execute('SELECT id,project_id,file_path FROM reference_files').fetchall():
        source=_mapped(path,roots)
        target=root/'uploads'/str(project)/'uploads'/('legacy-'+str(identity))
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        details=copy_regular(root,str(source.relative_to(root)),target,budget)
        db.execute('UPDATE reference_files SET file_path=?,file_size=? WHERE id=?',(str(target),details['bytes'],identity))
        changes.append({'table':'reference_files','id':identity,'original':path,'restored':str(target),**details})
    for table,column,condition in [('repositories','local_path',''),('agent_worktrees','worktree_path'," WHERE status='active'")]:
        for identity,path in db.execute(f'SELECT id,{column} FROM {table}{condition}').fetchall():
            target=_mapped(path,roots)
            if not target.is_dir() or target.is_symlink() or target.resolve()!=target:
                raise ValueError('Registered legacy repository/worktree must be a copied real directory')
            db.execute(f'UPDATE {table} SET {column}=? WHERE id=?',(str(target),identity))
            changes.append({'table':table,'id':identity,'original':path,'restored':str(target)})
    return changes


def stage_legacy_host(database, destination, *, manifest, **limits):
    """Create one pending managed installation from a locked legacy snapshot and explicitly mapped files.

    Native databases require backup-host and their independent authority evidence.
    Partial failures never publish installation.json; retry only at a NEW path.
    """
    from backend.tools.base.db import ensure_migrations

    budget=CopyBudget(**limits)
    source=Path(database).resolve(strict=True)
    supplied=Path(destination).absolute()
    output=supplied.parent.resolve(strict=True)/supplied.name
    if output==source or source.is_relative_to(output):
        raise ValueError('Import destination must preserve the original database')
    roots=_storage(manifest,output,source)
    before=source.stat()
    with closing(sqlite3.connect(source.as_uri()+'?mode=rw',uri=True,timeout=0)) as original:
        original.execute('BEGIN IMMEDIATE')
        initial=database_receipt(original,budget)
        if initial['schema_version'] is None or initial['schema_version']>17 or 'runtime_runs' in initial['tables']:
            raise ValueError('Only recognized legacy schemas through17 may be imported; native databases require backup-host with authority evidence')
        root=new_directory(output)
        for name in ('sources','control','uploads','auth','logs','service'):
            (root/name).mkdir(mode=0o700)
        snapshot=uuid4().hex
        evidence=root/'.imports'/snapshot
        evidence.mkdir(parents=True,mode=0o700)
        archived=evidence/'original.db'
        captured=_database_copy(source,archived,budget)
        budget.bytes+=archived.stat().st_size
        if captured!=initial:
            raise ValueError('Legacy database changed before snapshot capture')
        _database_copy(archived,root/'source.db',budget)
        budget.bytes+=(root/'source.db').stat().st_size
        storage=_copy_storage(roots,budget)
        after=source.stat()
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
            raise ValueError('Original legacy database identity changed while copying')
        original.rollback()
    ensure_migrations(str(root/'source.db'),existing_only=True)
    with closing(sqlite3.connect(root/'source.db')) as db, db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        reports=_hydrate_reports(db,root,roots,budget)
        registrations=_registrations(db,root,roots,budget)
        chunks=[]
        if manifest['chroma_exports']:
            from backend.runtime.legacy_chroma import import_chroma_exports

            chunks=import_chroma_exports(db,root,evidence,manifest['chroma_exports'],budget)
        current=database_receipt(db,budget)
    full={'format':1,'kind':'legacy-import','snapshot_id':snapshot,'source_database':str(source),
          'original_database':captured,'imported_database':current,'storage':storage,
          'report_hydration':reports,'relocations':registrations,'chroma_chunks':chunks,
          'source_database_snapshot':digest_file(evidence,'original.db',budget),
          'model_turns':0,'original_application_rows_modified':False,
          'sqlite_checkpoint_may_change_files':True,'old_work_replayed':False}
    _write_new(evidence/'manifest.json',full)
    details=digest_file(evidence,'manifest.json',budget)
    receipt={'format':1,'status':'pending_enrollment','kind':'legacy-import','snapshot_id':snapshot,
             'restored_root':str(root),'source_database':str(source),'import_manifest':str((evidence/'manifest.json').relative_to(root)),
             'import_manifest_sha256':details['sha256'],'model_turns':0,'old_work_replayed':False,
             'reports_hydrated':len(reports),'chroma_records':len(chunks),'source_schema':captured['schema_version'],
             'schema_version':current['schema_version']}
    _write_new(evidence/'restoration.json',receipt)
    _write_new(root/'runtime.json',{'status':'pending_enrollment','snapshot_id':snapshot})
    for directory,_,_ in os.walk(root,topdown=False,followlinks=False):
        budget.check();_sync_directory(Path(directory))
    _write_new(root/'installation.json',{'format':1,'status':'restored_pending_enrollment','snapshot_id':snapshot,
                                        'restoration':str((evidence/'restoration.json').relative_to(root))})
    _sync_directory(root)
    return receipt

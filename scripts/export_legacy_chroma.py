# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["chromadb==1.5.9"]
# ///
"""Export exact legacy Chroma records from a private snapshot, never opening the original with Chroma.

Stop old writers first. The original SQLite writer is locked while raw storage
is copied and checked. Chroma may migrate only a second disposable reader copy.
No embeddings are generated, no model is downloaded and no application database
is changed. Keep this compatibility dependency outside the serving environment.
"""

import argparse
from contextlib import ExitStack, closing
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import time
import selectors

SCRATCH_BYTES = 256 * 1024**2
LOG_BYTES = 65536


def isolated_reader(reader, output, *, bubblewrap, tenant, database, max_bytes, max_files, deadline, scratch_bytes):
    """Confine all arbitrary reader writes to one capacity-bound tmpfs and two pinned, size-limited output files."""
    stage = output / 'reader-output'
    stage.mkdir(mode=0o700)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Chroma reader deadline exhausted before dispatch')
    command = [bubblewrap, '--unshare-all', '--new-session', '--die-with-parent',
               '--cap-drop', 'ALL', '--clearenv']
    for path in ('/usr', '/bin', '/lib', '/lib64'):
        if Path(path).exists():
            command += ['--ro-bind', path, path]
    command += ['--proc', '/proc', '--dev', '/dev', '--size', str(scratch_bytes), '--tmpfs', '/work',
                '--dir', '/work/tmp', '--dir', '/work/home', '--dir', '/work/cache', '--dir', '/work/out',
                '--symlink', 'work/tmp', '/tmp']
    roots = {Path(sys.prefix), Path(sys.base_prefix), Path(sys._base_executable).parent.parent,
             Path(sys.executable).resolve().parent.parent}
    for root in sorted(roots):
        if root in {Path('/'), Path.home()}:
            raise ValueError('Reader interpreter must not expose host root or home')
        if not root.is_relative_to('/usr'):
            command += ['--ro-bind', str(root), str(root)]
    with ExitStack() as handles:
        fds = []
        for name in ('records.jsonl', 'receipt.json'):
            fd = os.open(stage/name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        for path, destination, writable in ((reader, '/input', False),
                                            (stage/'records.jsonl', '/work/out/records.jsonl', True),
                                            (stage/'receipt.json', '/work/out/receipt.json', True),
                                            (Path(__file__).resolve(), '/exporter.py', False)):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            handles.callback(os.close, fd)
            fds.append(fd)
            command += ['--bind-fd' if writable else '--ro-bind-fd', str(fd), destination]
        command += ['--remount-ro', '/dev', '--remount-ro', '/proc', '--remount-ro', '/', '--chdir', '/work']
        environment = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'HOME': '/work/home',
                       'XDG_CACHE_HOME': '/work/cache', 'TMPDIR': '/work/tmp', 'PYTHONDONTWRITEBYTECODE': '1',
                       'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                       'ANONYMIZED_TELEMETRY': 'False', 'OMP_NUM_THREADS': '1',
                       'OPENBLAS_NUM_THREADS': '1', 'RAYON_NUM_THREADS': '2',
                       'TOKIO_WORKER_THREADS': '2'}
        environment['RESEARCHER_READER_PARENT_NAMESPACES'] = json.dumps({
            name: os.stat('/proc/self/ns/' + name).st_ino for name in ('mnt', 'net', 'pid')
        })
        for key, value in environment.items():
            command += ['--setenv', key, value]
        command += ['--', sys.executable, '-I', '/exporter.py', '--reader-worker',
                    '--source', '/work/reader', '--output', '/work/out',
                    '--tenant', tenant, '--database', database,
                    '--max-bytes', str(max_bytes), '--max-files', str(max_files),
                    '--scratch-bytes', str(scratch_bytes),
                    '--timeout', str(math.ceil(remaining))]
        with (output / 'reader.log').open('xb') as log:
            child = subprocess.Popen(command, env={'PATH': os.defpath, 'LANG': 'C.UTF-8'},
                                     pass_fds=fds, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                captured = 0
                log_truncated = False
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    eof = False
                    while not eof or child.poll() is None:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Chroma reader deadline exceeded')
                        for key, _ in selector.select(min(.1, max(0, deadline-time.monotonic()))):
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                eof = True
                            else:
                                kept = chunk[:max(0, LOG_BYTES-captured)]
                                log_truncated = log_truncated or len(kept)<len(chunk)
                                log.write(kept)
                                captured += len(kept)
                    status = child.wait()
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=10)
                child.stdout.close()
        if status != 0:
            raise RuntimeError('Isolated Chroma reader failed; preserve this export and inspect reader.log')
    for name, limit in (('receipt.json', min(max_bytes, 16*1024**2)), ('records.jsonl', max_bytes)):
        info = (stage / name).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Reader output must be a bounded regular file')
    receipt = json.loads((stage / 'receipt.json').read_text())
    if (type(receipt.get('count')) is not int or not 0 <= receipt['count'] <= max_files
            or not isinstance(receipt.get('collections'), list)
            or len(receipt['collections']) > max_files):
        raise ValueError('Invalid isolated reader receipt')
    os.replace(stage / 'records.jsonl', output / 'records.jsonl')
    disabled=receipt.get('embedding_descriptors_disabled')
    if type(disabled) is not int or disabled<0:
        raise ValueError('Invalid data-only reader configuration receipt')
    return receipt['collections'], receipt['count'], log_truncated, disabled


def digest(path, *, deadline=None):
    """Stream a snapshot hash while honoring the operation deadline between bounded reads."""
    hashed=hashlib.sha256();count=0
    with path.open('rb') as stream:
        while chunk:=stream.read(1024**2):
            if deadline is not None and time.monotonic()>deadline:raise TimeoutError('Chroma hashing deadline exceeded')
            hashed.update(chunk);count+=len(chunk)
    return {'bytes':count,'sha256':hashed.hexdigest()}


def inventory(root, limit, *, deadline=None):
    """Enforce entry/time bounds while enumerating, before materializing the raw storage tree."""
    result={}
    def visit(directory):
        """Reject the first over-budget entry without sorting the rest of its directory."""
        with os.scandir(directory) as entries:
            for entry in entries:
                if deadline is not None and time.monotonic()>deadline:raise TimeoutError('Chroma inventory deadline exceeded')
                path=Path(entry.path);name=str(path.relative_to(root))
                info=entry.stat(follow_symlinks=False)
                if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                    raise ValueError('Chroma source must contain only regular files and directories')
                if name in {'chroma.sqlite3-wal','chroma.sqlite3-shm','chroma.sqlite3-journal'}:continue
                result[name]={'directory':stat.S_ISDIR(info.st_mode),'identity':(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)}
                if len(result)>limit:raise ValueError('Chroma export file limit exceeded')
                if stat.S_ISDIR(info.st_mode):visit(path)
    visit(root)
    return result


def snapshot(source, output, *, max_bytes, max_files, deadline):
    """Capture consistent SQLite and stable index files while retaining the original application rows."""
    database=source/'chroma.sqlite3'
    if database.is_symlink() or not database.is_file():raise ValueError('Expected existing regular chroma.sqlite3')
    raw=output/'source';raw.mkdir(mode=0o700)
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw',uri=True,timeout=0)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        first=inventory(source,max_files,deadline=deadline)
        total=0;files=[]
        for name,item in first.items():
            target=raw/name
            if time.monotonic()>deadline:raise TimeoutError('Chroma snapshot deadline exceeded')
            if item['directory']:target.mkdir(parents=True,exist_ok=True,mode=0o700);continue
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if name=='chroma.sqlite3':
                with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as reader, closing(sqlite3.connect(target)) as captured:
                    logical_bytes=reader.execute('PRAGMA page_count').fetchone()[0]*reader.execute('PRAGMA page_size').fetchone()[0]
                    if total+logical_bytes>max_bytes:raise ValueError('Chroma snapshot byte limit exceeded')
                    def progress(*_):
                        """Interrupt SQLite copying when the original snapshot deadline has expired."""
                        if time.monotonic()>deadline:raise TimeoutError('Chroma database snapshot deadline exceeded')
                    reader.backup(captured,pages=256,sleep=0,progress=progress)
                    captured.set_progress_handler(lambda:int(time.monotonic()>deadline),10000)
                    if captured.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('Corrupt Chroma snapshot')
                    captured.execute('PRAGMA journal_mode=DELETE')
                total+=target.stat().st_size
            else:
                if total+item['identity'][2]>max_bytes:raise ValueError('Chroma snapshot byte limit exceeded')
                fd=os.open(source/name,os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(fd,'rb') as original,target.open('xb') as copied:
                    while chunk:=original.read(1024**2):
                        if time.monotonic()>deadline:raise TimeoutError('Chroma file snapshot deadline exceeded')
                        if total+len(chunk)>max_bytes:raise ValueError('Chroma snapshot byte limit exceeded')
                        copied.write(chunk);total+=len(chunk)
            target.chmod(0o600)
            with target.open('rb') as stream:os.fsync(stream.fileno())
            files.append({'path':'source/'+name,**digest(target,deadline=deadline)})
        if inventory(source,max_files,deadline=deadline)!=first:raise ValueError('Chroma source changed while copying')
        for row in files:
            name=str(Path(row['path']).relative_to('source'))
            if name!='chroma.sqlite3' and digest(source/name,deadline=deadline)!={key:row[key] for key in ('bytes','sha256')}:
                raise ValueError('Chroma index bytes changed while copying')
        writer.rollback()
    if sum(row['bytes'] for row in files)>max_bytes:raise ValueError('Chroma snapshot actual size exceeds budget')
    return files


def disable_reader_embedding_descriptors(reader, *, deadline, max_files):
    """Disable model constructors only in disposable collection config/schema JSON, preserving raw evidence and document metadata.

This runs before importing Chroma. Its official reader still handles migrations
and pending metadata-log records; configuration from old models cannot authorize
construction of Python embedding functions during this data-only operation.
"""
    def unique_object(pairs):
        """Refuse ambiguous duplicate JSON keys instead of silently normalizing a configuration."""
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate key in persisted Chroma configuration')
            result[key]=value
        return result

    def disable(value, replacement, depth=0):
        """Walk bounded configuration trees; unrelated metadata tables are never visited."""
        if time.monotonic()>deadline:raise TimeoutError('Chroma configuration review deadline exceeded')
        if depth>64:raise ValueError('Chroma configuration nesting exceeds64levels')
        changed=0
        if isinstance(value,dict):
            for key,child in value.items():
                if key in ('embedding_function','sparse_embedding_function'):
                    if child is not None and child!=replacement:
                        value[key]=dict(replacement);changed+=1
                else:changed+=disable(child,replacement,depth+1)
        elif isinstance(value,list):
            for child in value:changed+=disable(child,replacement,depth+1)
        return changed

    changed=0
    with closing(sqlite3.connect((reader/'chroma.sqlite3').as_uri()+'?mode=rw',uri=True)) as db,db:
        db.execute('PRAGMA trusted_schema=OFF')
        db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
        table=db.execute("SELECT type FROM sqlite_master WHERE name='collections'").fetchone()
        if table!=('table',):raise ValueError('Expected original Chroma collections table')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name='collections'").fetchone():
            raise ValueError('Unexpected trigger on Chroma collection configuration')
        columns={row[1] for row in db.execute('PRAGMA table_info(collections)')}
        if 'id' not in columns:raise ValueError('Unrecognized Chroma collection identity')
        if db.execute('SELECT COUNT(*) FROM collections').fetchone()[0]>max_files:
            raise ValueError('Chroma collection limit exceeded')
        for column,disabled in (('config_json_str',{'type':'legacy'}),('schema_str',{'type':'unknown'})):
            if column not in columns:continue
            for identity,raw in db.execute(f'SELECT id,{column} FROM collections WHERE {column} IS NOT NULL ORDER BY id'):
                if not isinstance(raw,str) or len(raw.encode())>1024**2:
                    raise ValueError('Persisted Chroma configuration exceeds1MiB')
                value=json.loads(raw,object_pairs_hook=unique_object)
                if not isinstance(value,dict):raise ValueError('Persisted Chroma configuration must be an object')
                count=disable(value,disabled)
                if count:
                    db.execute(f'UPDATE collections SET {column}=? WHERE id=?',(json.dumps(value,allow_nan=False),identity))
                    changed+=count
    return changed


def read_collections(reader, output, *, tenant, database, max_bytes, max_files, deadline):
    """Read documents and metadata only inside the disposable worker; never access configuration properties or generate embeddings."""
    import chromadb
    from chromadb.config import Settings

    client=chromadb.PersistentClient(path=str(reader),tenant=tenant,database=database,settings=Settings(anonymized_telemetry=False))
    collections=[];total=0
    records=output/'records.jsonl'
    with records.open('w',encoding='utf-8') as stream:
        for found in client.list_collections():
            collection=client.get_collection(found.name,embedding_function=None)
            count=collection.count();seen=set()
            if total+count>max_files:raise ValueError('Chroma record limit exceeded')
            for offset in range(0,count,100):
                if time.monotonic()>deadline:raise TimeoutError('Chroma record export deadline exceeded')
                page=collection.get(limit=min(100,count-offset),offset=offset,include=['documents','metadatas'])
                ids=page['ids'];documents=page['documents'];metadata=page['metadatas']
                if len(ids)!=min(100,count-offset) or len(documents)!=len(ids) or len(metadata)!=len(ids):
                    raise ValueError('Chroma pagination returned incomplete aligned records')
                for identity,document,meta in zip(ids,documents,metadata):
                    if identity in seen:raise ValueError('Chroma pagination repeated an original identity')
                    seen.add(identity)
                    row={'collection':collection.name,'id':identity,'document':document,'metadata':meta}
                    encoded=json.dumps(row,ensure_ascii=True,allow_nan=False)+'\n'
                    if len(encoded.encode())>16*1024**2:raise ValueError('Chroma record exceeds16MiB export limit')
                    stream.write(encoded)
                    if stream.tell()>max_bytes:raise ValueError('Chroma text export byte limit exceeded')
            if len(seen)!=count or collection.count()!=count:raise ValueError('Chroma record count changed during export')
            collections.append({'name':collection.name,'id':str(collection.id),'metadata':collection.metadata,'count':count})
            total+=count
        stream.flush();os.fsync(stream.fileno())
    return collections, total


def export(source, output, *, tenant='default_tenant', database='default_database', max_bytes=20*1024**3, max_files=200000, timeout=300, scratch_bytes=SCRATCH_BYTES):
    """Preserve raw storage and export every selected collection record with exact text/metadata/identity."""
    if importlib.metadata.version('chromadb')!='1.5.9':raise ValueError('Use the isolated pinned chromadb1.5.9 exporter')
    if any(type(x) is not int or x<=0 for x in (max_bytes,max_files,timeout)):raise ValueError('Positive export limits required')
    if type(scratch_bytes) is not int or not 1024**2<=scratch_bytes<=2*1024**3:
        raise ValueError('Reader scratch capacity must be from1MiB to2GiB')
    bubblewrap=shutil.which('bwrap')
    if not bubblewrap:raise ValueError('Chroma export requires bubblewrap; no unsandboxed fallback')
    source=Path(source).resolve(strict=True)
    supplied=Path(output).absolute();output=supplied.parent.resolve(strict=True)/supplied.name
    if source.is_relative_to(output) or output.is_relative_to(source):raise ValueError('Export must not overlap the original Chroma directory')
    output.mkdir(mode=0o700)
    deadline=time.monotonic()+timeout
    files=snapshot(source,output,max_bytes=max_bytes,max_files=max_files,deadline=deadline)
    collections,total,log_truncated,disabled=isolated_reader(output/'source',output,bubblewrap=bubblewrap,tenant=tenant,database=database,
                                      max_bytes=max_bytes,max_files=max_files,deadline=deadline,scratch_bytes=scratch_bytes)
    records=output/'records.jsonl'
    manifest={'format':1,'kind':'researcher-chroma-export','status':'complete','reader_version':'1.5.9',
              'source_path':str(source),'tenant':tenant,'database':database,'collections':collections,
              'reader_isolation':{'network':'none','host_environment':'cleared','original_mounted':False,
                                  'writable':'capacity-bound scratch and two pinned output files','address_space_bytes':4*1024**3,
                                  'scratch_capacity_bytes':scratch_bytes,'scratch_filesystem':'tmpfs',
                                  'per_file_byte_limit':max_bytes,'reader_log_bytes':LOG_BYTES,
                                  'log_truncated':log_truncated,
                                  'embedding_descriptors_disabled':disabled,
                                  'configuration_policy':'disable embedding descriptors in disposable reader copy before importing Chroma',
                                  'aggregate_disk_quota':False,'arbitrary_reader_host_directory_writes':False},
              'records':{'path':'records.jsonl','count':total,**digest(records,deadline=deadline)},'source_files':files,
              'embedding_calls':0,'original_application_rows_modified':False,'sqlite_checkpoint_may_change_files':True}
    for directory,_,_ in os.walk(output,topdown=False):
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    with (output/'manifest.json').open('x') as stream:
        json.dump(manifest,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'status':'complete','collections':len(collections),'records':total,'embedding_calls':0,'directory':str(output)}


def main():
    """Run one explicit new-copy compatibility export without loading serving credentials or providers."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reader-worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--tenant',default='default_tenant')
    parser.add_argument('--database',default='default_database')
    parser.add_argument('--max-bytes',type=int,default=20*1024**3)
    parser.add_argument('--max-files',type=int,default=200000)
    parser.add_argument('--timeout',type=int,default=300)
    parser.add_argument('--scratch-bytes',type=int,default=SCRATCH_BYTES,
                        help='Kernel tmpfs capacity shared by the disposable reader and all temporary/cache files')
    args=parser.parse_args()
    if args.reader_worker:
        # Sanity check for the private entry, not authentication against an
        # operator who can already alter this executable or its environment.
        original=json.loads(os.environ.get('RESEARCHER_READER_PARENT_NAMESPACES','{}'))
        if (set(original)!={'mnt','net','pid'} or any(type(value) is not int or value<=0
                or os.stat('/proc/self/ns/'+name).st_ino==value for name,value in original.items())):
            raise ValueError('Internal reader requires the host-created namespaces')
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(args.max_bytes,args.max_bytes))
        resource.setrlimit(resource.RLIMIT_CPU,(args.timeout,args.timeout))
        resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
        shutil.copytree('/input',args.source)
        disabled=disable_reader_embedding_descriptors(Path(args.source),deadline=time.monotonic()+args.timeout,max_files=args.max_files)
        collections,total=read_collections(Path(args.source),Path(args.output),tenant=args.tenant,
            database=args.database,max_bytes=args.max_bytes,max_files=args.max_files,
            deadline=time.monotonic()+args.timeout)
        encoded=json.dumps({'collections':collections,'count':total,'embedding_descriptors_disabled':disabled},ensure_ascii=True,allow_nan=False)
        if len(encoded.encode())>min(args.max_bytes,16*1024**2):raise ValueError('Reader receipt too large')
        with (Path(args.output)/'receipt.json').open('w') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        return
    print(json.dumps(export(args.source,args.output,tenant=args.tenant,database=args.database,
                            max_bytes=args.max_bytes,max_files=args.max_files,timeout=args.timeout,scratch_bytes=args.scratch_bytes)))


if __name__=='__main__':
    main()

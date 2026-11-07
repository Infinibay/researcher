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
from contextlib import closing
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import time


def digest(path):
    """Hash one regular snapshot file for the portable export manifest."""
    with path.open('rb') as stream:
        return {'bytes':path.stat().st_size,'sha256':hashlib.file_digest(stream,'sha256').hexdigest()}


def inventory(root, limit):
    """List raw regular storage without following links or accepting special filesystem entries."""
    result={}
    for path in sorted(root.rglob('*')):
        info=path.lstat()
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError('Chroma source must contain only regular files and directories')
        name=str(path.relative_to(root))
        if name in {'chroma.sqlite3-wal','chroma.sqlite3-shm','chroma.sqlite3-journal'}:
            continue
        result[name]={'directory':stat.S_ISDIR(info.st_mode),'identity':(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)}
        if len(result)>limit:raise ValueError('Chroma export file limit exceeded')
    return result


def snapshot(source, output, *, max_bytes, max_files, deadline):
    """Capture consistent SQLite and stable index files while retaining the original application rows."""
    database=source/'chroma.sqlite3'
    if database.is_symlink() or not database.is_file():raise ValueError('Expected existing regular chroma.sqlite3')
    raw=output/'source';raw.mkdir(mode=0o700)
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw',uri=True,timeout=0)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        first=inventory(source,max_files)
        total=0;files=[]
        for name,item in first.items():
            target=raw/name
            if time.monotonic()>deadline:raise TimeoutError('Chroma snapshot deadline exceeded')
            if item['directory']:target.mkdir(parents=True,exist_ok=True,mode=0o700);continue
            total+=item['identity'][2]
            if total>max_bytes:raise ValueError('Chroma snapshot byte limit exceeded')
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if name=='chroma.sqlite3':
                with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as reader, closing(sqlite3.connect(target)) as captured:
                    reader.backup(captured,pages=256,sleep=0)
                    if captured.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('Corrupt Chroma snapshot')
                    captured.execute('PRAGMA journal_mode=DELETE')
            else:shutil.copyfile(source/name,target,follow_symlinks=False)
            target.chmod(0o600)
            with target.open('rb') as stream:os.fsync(stream.fileno())
            files.append({'path':'source/'+name,**digest(target)})
        if inventory(source,max_files)!=first:raise ValueError('Chroma source changed while copying')
        for row in files:
            name=str(Path(row['path']).relative_to('source'))
            if name!='chroma.sqlite3' and digest(source/name)!={key:row[key] for key in ('bytes','sha256')}:
                raise ValueError('Chroma index bytes changed while copying')
        writer.rollback()
    if sum(row['bytes'] for row in files)>max_bytes:raise ValueError('Chroma snapshot actual size exceeds budget')
    return files


def export(source, output, *, tenant='default_tenant', database='default_database', max_bytes=20*1024**3, max_files=200000, timeout=300):
    """Preserve raw storage and export every selected collection record with exact text/metadata/identity."""
    if importlib.metadata.version('chromadb')!='1.5.9':raise ValueError('Use the isolated pinned chromadb1.5.9 exporter')
    if any(type(x) is not int or x<=0 for x in (max_bytes,max_files,timeout)):raise ValueError('Positive export limits required')
    source=Path(source).resolve(strict=True)
    supplied=Path(output).absolute();output=supplied.parent.resolve(strict=True)/supplied.name
    if source.is_relative_to(output) or output.is_relative_to(source):raise ValueError('Export must not overlap the original Chroma directory')
    output.mkdir(mode=0o700)
    deadline=time.monotonic()+timeout
    files=snapshot(source,output,max_bytes=max_bytes,max_files=max_files,deadline=deadline)
    reader=output/'reader'
    shutil.copytree(output/'source',reader)
    # Only this copy is opened by Chroma; compatibility upgrades cannot touch source.
    import chromadb
    from chromadb.config import Settings

    client=chromadb.PersistentClient(path=str(reader),tenant=tenant,database=database,settings=Settings(anonymized_telemetry=False))
    collections=[];total=0
    records=output/'records.jsonl'
    with records.open('x',encoding='utf-8') as stream:
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
    manifest={'format':1,'kind':'researcher-chroma-export','status':'complete','reader_version':'1.5.9',
              'source_path':str(source),'tenant':tenant,'database':database,'collections':collections,
              'records':{'path':'records.jsonl','count':total,**digest(records)},'source_files':files,
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
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--tenant',default='default_tenant')
    parser.add_argument('--database',default='default_database')
    parser.add_argument('--max-bytes',type=int,default=20*1024**3)
    parser.add_argument('--max-files',type=int,default=200000)
    parser.add_argument('--timeout',type=int,default=300)
    args=parser.parse_args()
    print(json.dumps(export(args.source,args.output,tenant=args.tenant,database=args.database,
                            max_bytes=args.max_bytes,max_files=args.max_files,timeout=args.timeout)))


if __name__=='__main__':
    main()

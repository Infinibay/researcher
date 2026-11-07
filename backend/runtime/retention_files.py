"""Bounded archives and original-revision removal for closed private workspaces; no recursive force-delete or symlink traversal."""

import hashlib
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from uuid import uuid4

from backend.runtime.bootstrap import _sync_directory
from backend.runtime.contracts import RunConflict
from backend.runtime.development_workspace import _POLICY, git_environment
from backend.runtime.git_capsule import PrivateAllocation
from backend.runtime.snapshot_files import CopyBudget, copy_regular, digest_file, inventory, relative_name


def encoded(value):
    """Bind persisted manifests and owner intent to deterministic complete JSON."""
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def fingerprint(value):
    """Identify complete snapshot metadata/content without equating it with execution authority."""
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def directory(path, *, private=True):
    """Capture an owner-controlled root without redirection; configured ancestors may be readable, but allocation/archive roots stay private."""
    if private:
        captured=PrivateAllocation.capture(path)
        return {'path':captured.path,'device':captured.device,'inode':captured.inode,'private':True}
    path=Path(path).absolute();info=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:
        raise RunConflict('La raíz configurada debe pertenecer al operador y no permitir escritura ajena.')
    return {'path':str(path),'device':info.st_dev,'inode':info.st_ino,'private':False}


def matches_directory(path, expected):
    """Compare the original directory object even after its explicitly requested move to private disposal storage."""
    current=directory(path,private=expected.get('private',True))
    if (current['device'],current['inode'])!=(expected['device'],expected['inode']):
        raise RunConflict('La identidad de la carpeta cambió; se conserva la nueva carpeta.')


def new_directory(path):
    """Create a private new directory and persist its name; never reuse an existing entry implicitly."""
    path=Path(path);path.mkdir(mode=0o700);_sync_directory(path.parent)
    return directory(path)


def sealed_inventory(root, budget):
    """Retain every ordinary, ignored and untracked byte plus link payload, and reject concurrent changes instead of inventing a stable snapshot."""
    first=inventory(root,budget)
    items={name:dict(value) for name,value in first.items()}
    total=0
    for name,item in items.items():
        if item['kind']=='file':
            item.update(digest_file(root,name,budget));total+=item['bytes']
            if total>budget.max_bytes:raise ValueError('La copia supera el presupuesto de archivo.')
    if inventory(root,budget)!=first:
        raise RunConflict('Los archivos cambiaron durante el inventario; se conserva la copia original.')
    return items


def git_changes(root, budget):
    """Observe tracked/untracked/ignored status with a fixed credential-free Git command; a failed observation is explicitly unknown."""
    repository=Path(root)/'repository'
    if not (repository/'.git').is_dir() or (repository/'.git').is_symlink():
        return {'state':'unknown','tracked':None,'untracked':None,'ignored':None}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
        result=subprocess.run(['/usr/bin/git','--no-pager',*_POLICY,'status','--porcelain=v1','-z','--untracked-files=all','--ignored'],cwd=repository,env=git_environment('/run/researcher-retention-read'),stdout=output,stderr=error,timeout=15,check=False)
        size=output.tell();budget.check()
        if result.returncode or size>8*1024**2:return {'state':'unknown','tracked':None,'untracked':None,'ignored':None}
        output.seek(0);entries=output.read().split(b'\0');counts={'state':'observed','tracked':0,'untracked':0,'ignored':0};skip=False
        for entry in entries:
            if skip:skip=False;continue
            if not entry:continue
            kind='untracked' if entry[:2]==b'??' else 'ignored' if entry[:2]==b'!!' else 'tracked'
            counts[kind]+=1
            skip=b'R' in entry[:2] or b'C' in entry[:2]
        return counts


def verify_copy(root, items, budget):
    """Verify an archived/restored data tree by content, type, mode and link payload; original inodes never transfer to a copy."""
    actual=inventory(root,budget)
    if actual.keys()!=items.keys():raise RunConflict('El archivo de recuperación está incompleto o contiene entradas adicionales.')
    for name,expected in items.items():
        observed=actual[name]
        if any(observed.get(k)!=expected.get(k) for k in ('kind','mode','target')):
            raise RunConflict('Una entrada del archivo de recuperación cambió.')
        if expected['kind']=='file' and digest_file(root,name,budget)!={'sha256':expected['sha256'],'bytes':expected['bytes']}:
            raise RunConflict('Los bytes del archivo de recuperación no coinciden.')


def copy_snapshot(source, destination, items, temporary, budget):
    """Resume only matching completed entries; partial writes stay outside the data tree and never overwrite an existing destination."""
    destination=Path(destination);temporary=Path(temporary)
    for name,item in sorted(items.items(),key=lambda pair:(len(Path(pair[0]).parts),pair[0])):
        relative_name(name);target=destination/name;kind=item['kind']
        if os.path.lexists(target):
            info=target.lstat()
            if kind=='directory' and stat.S_ISDIR(info.st_mode) and not target.is_symlink():continue
            if kind=='symlink' and stat.S_ISLNK(info.st_mode) and os.readlink(target)==item['target']:continue
            if kind=='file' and stat.S_ISREG(info.st_mode) and digest_file(destination,name,budget)=={'sha256':item['sha256'],'bytes':item['bytes']}:continue
            raise RunConflict('El destino contiene otra revisión; no se sobrescribe.')
        if kind=='directory':target.mkdir(mode=0o700)
        elif kind=='symlink':os.symlink(item['target'],target)
        else:
            partial=temporary/str(uuid4())
            copied=copy_regular(source,name,partial,budget)
            if copied!={'sha256':item['sha256'],'bytes':item['bytes']}:
                raise RunConflict('El origen cambió durante la copia; se conserva el parcial.')
            os.chmod(partial,item['mode']);os.link(partial,target);partial.unlink()
        _sync_directory(target.parent)
    # Directory modes are applied after children are complete, preserving readonly source directories.
    for name,item in sorted(items.items(),key=lambda pair:len(Path(pair[0]).parts),reverse=True):
        if item['kind']=='directory':os.chmod(destination/name,item['mode'])
    verify_copy(destination,items,budget);_sync_directory(destination)


def remove_original(root, items, expected, budget):
    """Remove only remaining entries of the already archived original revision, retaining new/changed entries and every failed deletion."""
    matches_directory(root,expected)
    actual=inventory(root,budget)
    if not actual.keys()<=items.keys():raise RunConflict('Hay archivos nuevos; no heredan el borrado anterior.')
    for name,item in actual.items():
        original=items[name]
        keys=('kind','mode','target')
        if any(item.get(k)!=original.get(k) for k in keys):raise RunConflict('Una entrada cambió; se conserva.')
        identity=item['identity'];before=original['identity']
        if (identity[:2]!=before[:2] or (item['kind']!='directory' and identity!=before)):
            raise RunConflict('La identidad de un archivo cambió; se conserva la revisión nueva.')
        if item['kind']=='file' and digest_file(root,name,budget)!={'sha256':original['sha256'],'bytes':original['bytes']}:
            raise RunConflict('Un archivo cambió; se conserva la revisión nueva.')
    for name,item in sorted(actual.items(),key=lambda pair:len(Path(pair[0]).parts),reverse=True):
        budget.check()
        with parent_handle(root,name,items,expected) as (parent,leaf):
            observed=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
            if (observed.st_dev,observed.st_ino)!=tuple(item['identity'][:2]):raise RunConflict('Una entrada fue reemplazada; no se elimina.')
            if item['kind']=='directory':os.rmdir(leaf,dir_fd=parent)
            else:
                if [observed.st_dev,observed.st_ino,observed.st_size,observed.st_mtime_ns,observed.st_ctime_ns]!=item['identity']:
                    raise RunConflict('Un archivo cambió antes de eliminarlo; se conserva.')
                os.unlink(leaf,dir_fd=parent)
            os.fsync(parent)
    Path(root).rmdir();_sync_directory(Path(root).parent)


@contextmanager
def parent_handle(root, relative, items, expected):
    """Pin original parent directory objects so a replaced symlink cannot redirect deletion outside the archived tree."""
    parts=relative_name(relative).parts;handles=[]
    try:
        parent=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);handles.append(parent)
        info=os.fstat(parent)
        if (info.st_dev,info.st_ino)!=(expected['device'],expected['inode']):raise RunConflict('La raíz fue reemplazada; se conserva.')
        for index,part in enumerate(parts[:-1]):
            parent=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent);handles.append(parent)
            info=os.fstat(parent);original=items['/'.join(parts[:index+1])]
            if (info.st_dev,info.st_ino)!=tuple(original['identity'][:2]):raise RunConflict('Una carpeta fue reemplazada; se conserva.')
        yield parent,parts[-1]
    finally:
        for fd in reversed(handles):os.close(fd)


def move_new(source, destination):
    """Move an original allocation atomically without replacing even an empty competing destination on the supported Linux host."""
    libc=ctypes.CDLL(None,use_errno=True)
    result=libc.renameat2(-100,os.fsencode(source),-100,os.fsencode(destination),1)
    if result:
        error=ctypes.get_errno();raise OSError(error,os.strerror(error))

"""Original owner repository-setup operations before native tasks or source registrations exist.

Intent, directory identity and administrative ownership live in the project's
existing metadata transaction. A planned operation is not Git success, native
execution authority, remote ownership or an active repository registration.
"""

import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from backend.runtime.contracts import RunConflict, RunNotFound, command_key
from backend.runtime.development_workspace import _source_identity

_METADATA_KEY = 'owner_repository_operations_v1'


def _valid_branch(value):
    """Keep branch names unambiguous within fixed setup commands without accepting Git options, traversal or reserved HEAD."""
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,127}',value)) and value!='HEAD' and '..'not in value and all(p and not p.startswith('.') and not p.endswith(('.','.lock')) for p in value.split('/'))


@dataclass(frozen=True)
class SourceRequest:
    """An explicit administrative effect scope; adoption cannot secretly initialize Git and clone cannot provision or reconfigure a remote."""

    mode: str
    name: str
    path: str | None = None
    branch: str | None = None
    remote_url: str | None = None
    remote_owner: str | None = None
    private: bool | None = None
    use_configured_auth: bool = False
    remote_server: str | None = None

    def __post_init__(self):
        """Reject ambiguous effects, unsafe names/refs and credential-bearing URLs before persisting or allocating anything."""
        if self.mode not in ('create','adopt','clone','create_remote') or not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,80}',self.name) or type(self.use_configured_auth)is not bool or (self.use_configured_auth and self.mode!='clone'):
            raise ValueError('Explicit source mode and valid registration name required')
        if self.mode=='create_remote':
            if self.path is not None or self.branch is not None or self.remote_url is not None or type(self.private)is not bool or not isinstance(self.remote_owner,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,80}',self.remote_owner):
                raise ValueError('Remote creation requires explicit owner and visibility, without a local or clone effect')
            from backend.runtime.remote_publication import RemoteRepository

            if not isinstance(self.remote_server, str):
                raise ValueError('Remote creation requires an explicitly selected HTTPS server')
            RemoteRepository(self.remote_server, 1, self.remote_owner+'/'+self.name, self.remote_server.removesuffix('/api/v1')+'/'+self.remote_owner+'/'+self.name+'.git')
            return
        if self.remote_server is not None:
            raise ValueError('Remote server selection belongs only to explicit remote creation')
        if not isinstance(self.path,str) or not 1<=len(self.path.encode())<=4096 or not Path(self.path).is_absolute() or '\0' in self.path or self.private is not None or self.remote_owner is not None:
            raise ValueError('Source setup requires an explicit absolute path without remote-provisioning fields')
        if self.mode=='create' and self.branch is None:
            raise ValueError('A new local repository needs an explicit initial branch')
        if self.branch is not None and not _valid_branch(self.branch):
            raise ValueError('An unambiguous Git branch name is required')
        if self.mode=='adopt' and self.branch is not None:
            raise ValueError('Adoption cannot request a branch rewrite')
        if self.mode!='clone':
            if self.remote_url is not None:raise ValueError('Remote selection belongs only to explicit cloning')
        else:
            if not isinstance(self.remote_url,str) or len(self.remote_url)>4096 or any(ord(c)<33 or ord(c)>126 for c in self.remote_url):raise ValueError('Explicit credential-free HTTPS clone URL required')
            parsed=urlsplit(self.remote_url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or not parsed.path or parsed.path=='/':raise ValueError('Clone URLs must identify a credential-free HTTPS repository')
            _=parsed.port


@dataclass(frozen=True)
class SourceView:
    """A captured administrative directory view, deliberately without a fabricated native repository or task identity."""

    workspace: str
    device: int
    inode: int

    @classmethod
    def capture(cls,path):
        """Capture an ordinary non-redirected directory; subsequent controls must match these original kernel identities."""
        path=Path(path).absolute()
        try:
            info=path.lstat()
            if path.resolve(strict=True)!=path or not stat.S_ISDIR(info.st_mode):raise ValueError('redirected')
        except (OSError,ValueError) as error:
            raise RunConflict('La carpeta original falta o cambió; no se eligió otra.') from error
        return cls(str(path),info.st_dev,info.st_ino)

    def verify(self):
        """Reuse the existing source identity check without inventing a native registration for this administrative view."""
        return _source_identity(self)


@dataclass(frozen=True)
class SourceLease:
    """One original administrative owner/fence; no native RunSpec, AttemptLease, model permission or synthetic task is conferred."""

    project_id: int
    operation_key: str
    attempt_id: str
    owner_id: str
    fence: int
    database_identity: str


@dataclass(frozen=True)
class SourceObservation:
    """Complete point-in-time Git observations from fixed owned commands; not a permanent-health, semantic-acceptance or publication assertion."""

    head_sha: str
    tree_sha: str
    branch: str
    origin: str | None
    working_tree_clean: bool

    def __post_init__(self):
        """Require full same-format objects and avoid persisting credential-bearing origin URLs into project metadata or owner responses."""
        if any(not isinstance(v,str) or not re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})',v) for v in (self.head_sha,self.tree_sha)) or len(self.head_sha)!=len(self.tree_sha) or not _valid_branch(self.branch) or type(self.working_tree_clean)is not bool:
            raise ValueError('Complete source Git observation required')
        if self.origin is not None:
            if not isinstance(self.origin,str) or not 1<=len(self.origin)<=4096 or any(ord(c)<33 for c in self.origin):raise ValueError('Origin observation is invalid')
            parsed=urlsplit(self.origin)
            if parsed.password is not None or (parsed.scheme in ('http','https') and (parsed.username is not None or parsed.query or parsed.fragment)):
                raise RunConflict('La fuente conserva credenciales en origin. No se copiaron al registro; revisa esa configuración sin reemplazar el remoto.')


class SourceOperations:
    """Persist bounded original setup intents and directory ownership through the existing SQLite/project-metadata transaction."""

    def __init__(self,runs,*,workspaces,control_root):
        """Use the actual host source policy and private control root; merely constructing or reading this store creates no files or workers."""
        self.runs,self.workspaces,self.control_root=runs,workspaces,Path(control_root).absolute()

    def _origin(self):
        """Reuse the existing database path/device/inode identity rather than deriving authority from a copied database's labels."""
        from backend.runtime.peer_registry import PeerRegistry

        return PeerRegistry(self.runs)._database_identity()

    @staticmethod
    def _metadata(raw):
        """Preserve all unrelated project metadata and refuse malformed state instead of treating lost operation history as empty."""
        try:
            value=json.loads(raw or '{}')
            if not isinstance(value,dict):raise ValueError
            entries=value.get(_METADATA_KEY,{})
            if not isinstance(entries,dict) or len(entries)>64:raise ValueError
        except (ValueError,TypeError) as error:raise RunConflict('No se puede comprobar la historia de altas del proyecto.') from error
        return value

    @classmethod
    def has_history(cls,raw):
        """Retain administrative operations across project deletion decisions, including completed or uncertain setup history."""
        return bool(cls._metadata(raw).get(_METADATA_KEY))

    @classmethod
    def summaries(cls, raw):
        """Expose complete recorded source intentions and point-in-time observations without peer internals or an implied fresh Git check."""
        entries = cls._metadata(raw).get(_METADATA_KEY, {})
        try:
            return [{'operation_key': key, 'operation_id': row['operation_id'],
                     'mode': row['request']['mode'], 'name': row['request']['name'],
                     'path': row['request'].get('path'), 'status': row['status'],
                     'fence': row['fence'],
                     'requires_reconciliation': row['status'] not in ('completed', 'rejected', 'stopped') or (row['status'] == 'stopped' and row.get('view') is not None),
                     'repository_id': row['repository_id'], 'observation': row.get('observation'), 'remote': (row.get('receipt') or {}).get('remote'),
                     'observed_at': (row.get('receipt') or {}).get('observed_at'),
                     'observation_kind': 'recorded_not_rechecked'}
                    for key, row in sorted(entries.items())]
        except (KeyError, TypeError, AttributeError) as error:
            raise RunConflict('La historia de altas está incompleta; no se presentó como ausencia de trabajo.') from error

    @classmethod
    def assert_unreserved(cls, conn, path):
        """Reject ordinary registration or another setup overlapping an unresolved original destination under the same admission lock."""
        candidate = Path(path).resolve()
        for other in conn.execute('SELECT metadata_json FROM projects'):
            for operation in cls.summaries(other['metadata_json']):
                target = operation['path']
                if target and operation['requires_reconciliation']:
                    reserved = Path(target).resolve()
                    if candidate.is_relative_to(reserved) or reserved.is_relative_to(candidate):
                        raise RunConflict('Otra alta conserva esta carpeta como destino original; reconcilia esa operación.')

    @classmethod
    def _load(cls,conn,project):
        """Read exactly this project and its durable operation collection; a foreign or removed project is never recreated."""
        row=conn.execute('SELECT metadata_json FROM projects WHERE id=?',(project,)).fetchone()
        if row is None:raise RunNotFound('Project not found')
        return cls._metadata(row[0])

    @staticmethod
    def _save(conn,project,metadata):
        """Write the complete existing metadata object under the caller's original write lock, retaining owner creation and other domains."""
        raw=json.dumps(metadata,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        if len(raw.encode())>2*1024**2:raise RunConflict('La historia de altas supera el límite completo; no se omitieron operaciones.')
        conn.execute('UPDATE projects SET metadata_json=? WHERE id=?',(raw,project))

    @classmethod
    def _row(cls,conn,project,key):
        """Return a source operation from its exact project/key without a newest-operation fallback."""
        metadata=cls._load(conn,project);row=metadata.get(_METADATA_KEY,{}).get(key)
        if row is None:raise RunNotFound('Source operation not found')
        return metadata,row

    def read(self,project,key):
        """Read original intent and current saved phase; this does not observe Git, contact remotes or authorize retry."""
        with self.runs._transaction() as conn:return self._row(conn,project,key)[1]

    def list(self,project):
        """Read the complete bounded setup history of one project; no partial list is represented as proof of no work."""
        with self.runs._transaction() as conn:return list(self._load(conn,project).get(_METADATA_KEY,{}).values())

    def _target(self,conn,project,request):
        """Validate source scope/reservations under the admission write lock without creating a folder, initializing Git or replacing a registration."""
        if self.workspaces is None:raise RunConflict('Configura la raíz real del runtime antes de preparar una fuente.')
        root=SourceView.capture(self.workspaces.root)
        if request.path is None:return {'root':asdict(root),'parent':None,'existing':None}
        path=Path(request.path)
        if path.absolute()!=path or '..'in path.parts or path==self.workspaces.root or not path.is_relative_to(self.workspaces.root) or path.is_relative_to(self.control_root) or self.control_root.is_relative_to(path):raise RunConflict('La carpeta está fuera de la política de fuentes del host.')
        parent=SourceView.capture(path.parent)
        exists=os.path.lexists(path)
        if request.mode=='adopt':
            if not exists:raise RunConflict('La adopción necesita una carpeta existente.')
            self.workspaces._directory(conn,project,str(path));existing=asdict(SourceView.capture(path))
        else:
            if exists:raise RunConflict('Crear o clonar necesita una carpeta nueva. No se reinicia ni reemplaza el contenido existente.')
            existing=None
        for other in conn.execute("SELECT project_id,name,local_path,status FROM repositories"):
            foreign=Path(other['local_path']).resolve()
            overlap=path.is_relative_to(foreign) or foreign.is_relative_to(path)
            if overlap and (other['project_id']!=project or other['name']!=request.name or str(foreign)!=str(path) or other['status']!='active' or request.mode!='adopt'):raise RunConflict('La carpeta o el nombre pertenecen a otro registro; no se reemplazó.')
            if other['project_id']==project and other['name']==request.name and not overlap:raise RunConflict('El nombre ya identifica otra carpeta.')
        self.assert_unreserved(conn, path)
        return {'root':asdict(root),'parent':asdict(parent),'existing':existing}

    def prepare(self,project,key,request,*,remote_identity=None):
        """Persist one exact owner intent before any effect; replay returns it, while a reused key with different scope rejects."""
        command_key(key)
        if not isinstance(request,SourceRequest):raise TypeError('A typed source intent is required')
        if (request.mode=='create_remote' or request.use_configured_auth) and (not isinstance(remote_identity,str) or not re.fullmatch(r'[a-f0-9]{64}',remote_identity)):raise RunConflict('El alta remota o la clonación autenticada requieren un origen configurado explícito del host.')
        if request.mode!='create_remote' and not request.use_configured_auth and remote_identity is not None:raise RunConflict('Esta solicitud no seleccionó una credencial remota.')
        intent={'request':asdict(request),'remote_identity':remote_identity}
        with self.runs._transaction(write=True) as conn:
            metadata=self._load(conn,project);entries=metadata.setdefault(_METADATA_KEY,{})
            if key in entries:
                old=entries[key]
                if {'remote_server':None,**old['request']}!=intent['request'] or old['remote_identity']!=remote_identity:raise RunConflict('La solicitud original identifica otra alta; no se preparó un efecto distinto.')
                return old
            if len(entries)>=64:raise RunConflict('Se alcanzó el límite de altas conservadas; no se borró historia para continuar.')
            target=self._target(conn,project,request)
            row={'schema':1,'project_id':project,'operation_key':key,'operation_id':uuid4().hex,**intent,'target':target,'database_identity':self._origin(),'status':'planned','fence':0,'owner':None,'attempt_id':None,'view':None,'peers':{},'repository_id':None,'created_at':self.runs.clock()}
            entries[key]=row;self._save(conn,project,metadata);return row

    def _owned(self,conn,lease):
        """Require the original administrative owner/fence and database identity before any directory or peer control."""
        if not isinstance(lease,SourceLease):raise TypeError('Original source-operation lease required')
        metadata,row=self._row(conn,lease.project_id,lease.operation_key)
        if row['status']!='running' or (row['attempt_id'],row['owner']['owner_id'],row['fence'],row['database_identity'])!=(lease.attempt_id,lease.owner_id,lease.fence,lease.database_identity) or self._origin()!=lease.database_identity:raise RunConflict('El dueño o la fase original del alta cambió; no se repitió su efecto.')
        SourceView(**row['target']['root']).verify()
        return metadata,row

    def claim(self,project,key,owner):
        """Give one actual administrative process owner its own attempt/fence, without a native task or model invocation."""
        with self.runs._transaction(write=True) as conn:
            return self._claim(conn, project, key, owner)

    def _claim(self,conn,project,key,owner):
        """Share original source admission inside an existing transaction so HTTP ownership can be persisted atomically before its first client."""
        from backend.runtime.peer_process import boot_id,start_ticks

        command_key(owner)
        metadata,row=self._row(conn,project,key)
        if row['status']=='running' and row['owner']['owner_id']==owner:return SourceLease(project,key,row['attempt_id'],owner,row['fence'],row['database_identity'])
        if row['status']!='planned' or row['database_identity']!=self._origin():raise RunConflict('Esta alta tiene otro dueño o necesita reconciliación; no se inicia otra ejecución.')
        SourceView(**row['target']['root']).verify()
        row.update(status='running',attempt_id=uuid4().hex,fence=row['fence']+1,owner={'owner_id':owner,'pid':os.getpid(),'start_ticks':start_ticks(os.getpid()),'boot_id':boot_id()})
        self._save(conn,project,metadata)
        return SourceLease(project,key,row['attempt_id'],owner,row['fence'],row['database_identity'])

    def begin_observation(self,project,key,owner):
        """Fence an already-closed original attempt and retain its history before a new strictly readonly reconciliation; never restart its writes."""
        from backend.runtime.peer_process import boot_id,start_ticks

        command_key(owner)
        with self.runs._transaction(write=True) as conn:
            metadata,row=self._row(conn,project,key)
            if row['status'] not in ('running','needs_reconciliation') or not (row.get('closure') or {}).get('domain_removed') or any(p['state']!='closed' for p in row['peers'].values()):raise RunConflict('El cierre original aún no está confirmado o el alta ya terminó; no se abre otro intento.')
            if row['database_identity']!=self._origin():raise RunConflict('El origen del alta cambió tras una copia o restauración.')
            SourceView(**row['target']['root']).verify()
            view=row['view'];captured=view['allocation'] or {'path':view['source']['workspace'],'device':view['source']['device'],'inode':view['source']['inode']}
            source=SourceView(captured['path'],captured['device'],captured['inode']);source.verify()
            history=row.setdefault('history',[])
            if len(history)>=8:raise RunConflict('Se alcanzó el límite de observaciones conservadas; no se borró historia para reintentar.')
            history.append({key:row.get(key) for key in ('attempt_id','fence','owner','view','peers','domain','closure','observation_only','issue')})
            row.update(status='running',attempt_id=uuid4().hex,fence=row['fence']+1,owner={'owner_id':owner,'pid':os.getpid(),'start_ticks':start_ticks(os.getpid()),'boot_id':boot_id()},view={'source':asdict(source),'allocation':None},peers={},domain=None,closure=None,observation_only=True,issue=None,stop_requested=False)
            self._save(conn,project,metadata)
            return SourceLease(project,key,row['attempt_id'],owner,row['fence'],row['database_identity'])

    def allocate(self,lease):
        """Capture one original directory allocation before Git; a partial unrecorded folder is retained and never erased or guessed to be ours."""
        from backend.runtime.bootstrap import _sync_directory
        from backend.runtime.native_inference import _private_control

        with self.runs._transaction(write=True) as conn:
            metadata,row=self._owned(conn,lease)
            if row['view'] is not None:
                SourceView(**row['view']['source']).verify()
                if row['view']['allocation']:SourceView(row['view']['allocation']['path'],row['view']['allocation']['device'],row['view']['allocation']['inode']).verify()
                return row['view']
            request=SourceRequest(**row['request'])
            if request.mode=='create_remote':raise RunConflict('Una creación remota no autoriza una carpeta local.')
            SourceView(**row['target']['parent']).verify()
            if request.mode=='adopt':
                source=SourceView(**row['target']['existing']);source.verify();allocation=None
            else:
                path=Path(request.path)
                if os.path.lexists(path):raise RunConflict('El destino apareció sin una asignación confirmada. Se conserva para revisión; no se reinicia.')
                SourceView.capture(self.control_root.parent).verify();_private_control(self.control_root)
                path.mkdir(mode=0o700);_sync_directory(path);_sync_directory(path.parent)
                info=path.stat();allocation={'path':str(path),'device':info.st_dev,'inode':info.st_ino}
                base=self.control_root/'repository-operations'/row['operation_id']/lease.attempt_id
                _private_control(base);empty=base/'empty-source';empty.mkdir(mode=0o700);source=SourceView.capture(empty)
            row['view']={'source':asdict(source),'allocation':allocation};self._save(conn,lease.project_id,metadata);return row['view']

    def attach_domain(self,lease,*,grant_id,path,identity):
        """Retain the original physical domain before a setup command can be launched; another domain cannot replace an uncertain attempt."""
        with self.runs._transaction(write=True) as conn:
            metadata,row=self._owned(conn,lease)
            value={'grant_id':grant_id,'path':str(path),'identity':asdict(identity)}
            if row.get('domain') not in (None,value):raise RunConflict('El alta ya conserva otro dominio original; requiere reconciliación.')
            row['domain']=value;self._save(conn,lease.project_id,metadata)

    def register(self,lease,observation):
        """Register the actually observed directory only after original global domain closure, preserving any already-matching registration without rewriting metadata."""
        if not isinstance(observation,SourceObservation):raise TypeError('An owned source observation is required')
        with self.runs._transaction(write=True) as conn:
            metadata,row=self._owned(conn,lease);closure=row.get('closure')
            if not closure or closure.get('domain_removed')is not True or closure.get('attempt_id')!=lease.attempt_id or any(p['state']!='closed' for p in row['peers'].values()):raise RunConflict('El cierre original del alta no está confirmado; no se registró una fuente activa.')
            request=SourceRequest(**row['request']);view=row['view']
            if view is None or request.path is None:raise RunConflict('La operación no tiene una fuente local observada.')
            actual=SourceView.capture(request.path)
            captured=view['allocation'] or {'path':view['source']['workspace'],'device':view['source']['device'],'inode':view['source']['inode']}
            if asdict(actual)!={'workspace':captured['path'],'device':captured['device'],'inode':captured['inode']}:raise RunConflict('La carpeta observada fue reemplazada; no se registró otra.')
            self.workspaces._directory(conn,lease.project_id,request.path)
            if request.mode=='create' and (observation.branch!=request.branch or observation.origin is not None or not observation.working_tree_clean):raise RunConflict('La fuente nueva cambió antes del registro; conserva su contenido para revisión.')
            if request.mode=='clone' and (observation.origin!=request.remote_url or (request.branch is not None and observation.branch!=request.branch)):raise RunConflict('La copia no corresponde al origen/rama originales; no se eligió otra fuente.')
            existing=conn.execute('SELECT * FROM repositories WHERE project_id=? AND (name=? OR local_path=?)',(lease.project_id,request.name,request.path)).fetchone()
            if existing is not None:
                if existing['name']!=request.name or existing['local_path']!=request.path or existing['status']!='active':raise RunConflict('El registro cambió durante el alta; no se reemplazó.')
                repository=existing['id']
            else:
                repository=conn.execute("INSERT INTO repositories(project_id,name,local_path,default_branch,remote_url,status)VALUES(?,?,?,?,?,'active')",(lease.project_id,request.name,request.path,observation.branch,observation.origin)).lastrowid
            self.workspaces._bind(conn,lease.project_id,repository)
            receipt={'project_id':lease.project_id,'operation_key':lease.operation_key,'operation_id':row['operation_id'],'status':'completed','repository_id':repository,'request':row['request'],'observation':asdict(observation),'observed_at':self.runs.clock(),'domain_removed':True}
            row.update(status='completed',repository_id=repository,observation=asdict(observation),receipt=receipt);self._save(conn,lease.project_id,metadata)
            return receipt

    def uncertain(self,lease):
        """Retain an interrupted/failed operation and its original directories/peers; absence of a reply does not authorize another Git write."""
        with self.runs._transaction(write=True) as conn:
            metadata,row=self._row(conn,lease.project_id,lease.operation_key)
            if (row['attempt_id'],row['fence'])!=(lease.attempt_id,lease.fence):raise RunConflict('El intento original cambió.')
            if row['status']!='completed':row['status']='needs_reconciliation';self._save(conn,lease.project_id,metadata)

    def note_failure(self, project, key):
        """Expose a bounded redacted current issue while retaining the original operation, physical receipts and any partial files for explicit observation."""
        with self.runs._transaction(write=True) as conn:
            metadata, row = self._row(conn, project, key)
            if row['status'] not in ('completed', 'rejected', 'stopped') and not row.get('issue'):
                message = 'No se confirmó la creación remota. Conservamos la solicitud; observa su resultado sin volver a enviarla.' if row['request']['mode']=='create_remote' else 'No se confirmó la preparación. Conservamos la solicitud y la carpeta; observa el resultado original antes de decidir cómo continuar.'
                row.update(status='needs_reconciliation', issue={'code':'source_result_unconfirmed','message':message})
                self._save(conn, project, metadata)

    def request_stop(self, project, key, *, operation_id, fence):
        """Withdraw admission for exactly the observed administrative fence; a stale Stop cannot target a new reconciliation attempt."""
        with self.runs._transaction(write=True) as conn:
            return self.withdraw(conn, project, key, operation_id=operation_id, fence=fence)

    def request_project_stop(self, project, key, *, operation_id):
        """Resolve and withdraw the current fence atomically for a bodyless whole-project Stop whose admission fuse already covers this original operation."""
        with self.runs._transaction(write=True) as conn:
            _, row = self._row(conn, project, key)
            return self.withdraw(conn, project, key, operation_id=operation_id, fence=row['fence'])

    @classmethod
    def withdraw(cls, conn, project, key, *, operation_id, fence):
        """Withdraw one original source inside either the individual Stop or atomic whole-project Stop admission transaction."""
        metadata, row = cls._row(conn, project, key)
        if row['operation_id'] != operation_id or row['fence'] != fence:
            raise RunConflict('El intento observado cambió. Consulta la operación antes de detenerla.')
        if row['status'] not in ('completed', 'rejected', 'stopped'):
            row.update(status='cancelling', stop_requested=True)
            if row['request']['mode'] == 'create_remote':
                row['remote_withdrawn'] = True
            cls._save(conn, project, metadata)
        return row

    def settle_stop(self, project, key):
        """Record stopped only after original local closure, retaining partially written folders and uncertainty instead of asserting a remote effect was undone."""
        with self.runs._transaction(write=True) as conn:
            metadata, row = self._row(conn, project, key)
            if not row.get('stop_requested') or row['status'] == 'completed':
                return row
            closure = row.get('closure') or {}
            if row['request']['mode'] == 'create_remote':
                http = row.get('http_client') or {}
                closed = http.get('attempt_id') == row['attempt_id'] and http.get('state') == 'closed'
                issued = (row.get('remote_effect') or {}).get('issued')
                row['status'] = 'stopped' if (row['owner'] is None or closed) and not issued else 'needs_reconciliation'
                self._save(conn, project, metadata)
                return row
            unused = row['owner'] is None and row['view'] is None and not row['peers'] and not row.get('domain')
            closed = closure.get('attempt_id') == row['attempt_id'] and closure.get('domain_removed') is True and all(p['state'] == 'closed' for p in row['peers'].values())
            row['status'] = 'stopped' if unused or closed else 'needs_reconciliation'
            self._save(conn, project, metadata)
            return row

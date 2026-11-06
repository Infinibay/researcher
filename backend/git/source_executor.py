"""Administrative Git setup through the existing kernel/global broker, with original scoped receipts and no inference task or provider fallback."""

from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.git.source_capsule import SourceGitLaunch, validate_source_transport
from backend.git.source_operations import SourceObservation,SourceRequest
from backend.git.source_registry import SourcePeerRegistry
from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.broker_git import OwnedGitExecutor
from backend.runtime.broker_stdio import AsyncPeerBroker
from backend.runtime.contracts import RunConflict
from backend.runtime.development_workspace import git_environment
from backend.runtime.execution_domain import ExecutionDomain
from backend.runtime.git_capsule import PEER_ALLOCATION,GitAsset,PrivateAllocation
from backend.runtime.owned_runtime import _settled
from backend.runtime.peer_broker import PeerBroker
from backend.runtime.workspaces import PEER_WORKSPACE


class SourceGitExecutor:
    """Expose semantic fixed stages while reusing original owned Git transport, complete capture and physical closure."""

    def __init__(self,records,lease,owner,view,asset):
        """Bind actual operation/owner/views once; this object has no generic command or native run API."""
        self.records,self.lease,self.owner,self.view,self.asset=records,lease,owner,view,asset
        row=records.read(lease.project_id,lease.operation_key)
        self.request,self.operation_id=SourceRequest(**row['request']),row['operation_id']
        self.transport_identity=row['remote_identity'];self.observation_only=row.get('observation_only',False)

    async def stage(self,stage):
        """Launch at most one peer for this original stage; replay returns its receipt rather than silently reissuing an effect."""
        registry=SourcePeerRegistry(self.records,self.lease,stage)
        allocation=PrivateAllocation(**self.view['allocation'])if self.view['allocation']else None
        launch=SourceGitLaunch(self.asset,SourceGitLaunch.command(self.request,self.operation_id,stage),str(PEER_WORKSPACE if self.request.mode=='adopt' or self.observation_only else PEER_ALLOCATION),tuple(sorted(git_environment(Path('/home/actor')).items())),allocation,request=self.request,operation_id=self.operation_id,stage=stage,transport_identity=self.transport_identity,observation_only=self.observation_only)
        transport=OwnedGitExecutor(owner=self.owner,registry=registry,lease=self.lease,source=self.view['source']['workspace'],allocation=allocation.path if allocation else None,asset=self.asset)
        transport._operation_prefix='source-'+stage
        return await transport._invoke(launch,timeout=60 if launch.networked else 15)

    async def observe(self):
        """Capture an actual Git root/complete HEAD/tree/branch/status/origin without converting local credentials or a label into authority."""
        expected=str(PEER_WORKSPACE if self.request.mode=='adopt' or self.observation_only else PEER_ALLOCATION)
        root=await self.stage('root')
        if root.exit_code!=0 or root.stdout.decode().strip()!=expected:raise RunConflict('La carpeta seleccionada no es una raíz Git comprobada; no se usó un repositorio padre.')
        config=await self.stage('configuration')
        if config.exit_code!=0:raise RunConflict('No se pudo comprobar la configuración Git de la fuente.')
        for item in config.stdout.split(b'\0'):
            key=item.partition(b'\n')[0].lower()
            if key.startswith((b'credential.',b'include.',b'includeif.',b'filter.'))or key.endswith(b'.extraheader'):raise RunConflict('La configuración local contiene credenciales o helpers que necesitan revisión. Se conserva sin cambios; no se copiaron al registro.')
        values={}
        for stage in ('head','tree','branch','status','origin'):
            result=await self.stage(stage)
            if result.exit_code!=0 and not(stage=='origin'and result.exit_code==2):raise RunConflict('La fuente no tiene una revisión y rama completas comprobadas. Se conserva para revisión, sin inicialización implícita.')
            values[stage]=result.stdout.decode('utf-8').strip()
        if self.request.mode=='create':
            message=await self.stage('initial_message');files=await self.stage('initial_files')
            lines=message.stdout.decode('utf-8').splitlines()
            if message.exit_code!=0 or files.exit_code!=0 or files.stdout or not lines or lines[0] or '\n'.join(lines[1:]).strip()!=f'Initialize source ({self.operation_id})':raise RunConflict('La carpeta ya no contiene sólo la revisión inicial original. Conserva sus cambios y revisa su adopción explícita.')
        return SourceObservation(values['head'],values['tree'],values['branch'],values['origin']or None,not bool(values['status']))


@asynccontextmanager
async def source_executor(records,lease,*,authority,cgroup_parent,source_network=None,source_transport=None,broker_limits=None):
    """Retain one real administrative kernel domain through every fixed command and verified retirement, using the shared global concession."""
    view=await _settled(records.allocate,lease)
    path=Path(cgroup_parent)/('researcher-source-setup-'+uuid4().hex);path.mkdir(mode=0o700)
    with WitnessedAuthorityJournal(**authority)as journal:
        with ExecutionDomain.open(path)as domain:
            broker=PeerBroker(journal,domain,limits=broker_limits,source_network=source_network,source_transport=source_transport)
            await _settled(records.attach_domain,lease,grant_id=broker.grant_id,path=path,identity=domain.identity)
            async with AsyncPeerBroker(broker)as owner:
                yield SourceGitExecutor(records,lease,owner,view,GitAsset.inspect(Path('/usr/bin/git')))


async def execute_source(records,project,key,*,authority,cgroup_parent,source_network=None,source_transport=None,broker_limits=None):
    """Execute an original local-create/adopt/clone intent, registering only after original domain closure; exact completed retry starts nothing."""
    row=await _settled(records.read,project,key)
    if row['status']=='completed':return row['receipt']
    request=SourceRequest(**row['request'])
    if request.mode=='create_remote':raise RunConflict('La creación remota necesita su transporte de operación propio; no inicializa ni publica una fuente local.')
    if request.mode=='clone'and source_network is None:raise RunConflict('Configura los parámetros TLS/DNS del host antes de clonar.')
    validate_source_transport(request,source_transport,row['remote_identity'])
    lease=await _settled(records.claim,project,key,'source-owner-'+uuid4().hex)
    try:
        async with source_executor(records,lease,authority=authority,cgroup_parent=cgroup_parent,source_network=source_network,source_transport=source_transport,broker_limits=broker_limits)as executor:
            stages=('init','commit')if request.mode=='create'else('clone','read_index','checkout')if request.mode=='clone'else()
            for stage in stages:
                result=await executor.stage(stage)
                if result.exit_code!=0:raise RunConflict('El comando original no confirmó el alta. Se conserva la carpeta y su historia; no se reinicia ni borra.')
            observation=await executor.observe()
        return await _settled(records.register,lease,observation)
    except BaseException:
        await _settled(records.uncertain,lease)
        raise


async def reconcile_source(records,project,key,*,authority,cgroup_parent,broker_limits=None):
    """Recover original closure then observe only retained Git state in a fresh readonly domain; never repeat init/commit/clone or claim remote server termination."""
    row=await _settled(records.read,project,key)
    if row['status']=='completed':return row['receipt']
    if not row.get('domain'):raise RunConflict('El alta no conserva un dominio original comprobable. Conserva la carpeta para revisión; no se crea otro destino.')
    with WitnessedAuthorityJournal(**authority)as journal:
        grant_id=row['domain']['grant_id']
        grant=(await _settled(journal.load)).records.get('broker:grant:'+grant_id)
        if grant is None:raise RunConflict('No se encontró el recibo global original. No se dedujo cierre ni se repitió un efecto.')
        if grant['state']!='retired':await _settled(PeerBroker.recover,journal,grant_id)
        await _settled(PeerBroker.project_recovered,journal,grant_id)
    lease=await _settled(records.begin_observation,project,key,'source-observer-'+uuid4().hex)
    try:
        async with source_executor(records,lease,authority=authority,cgroup_parent=cgroup_parent,broker_limits=broker_limits)as executor:
            observation=await executor.observe()
        return await _settled(records.register,lease,observation)
    except BaseException:
        await _settled(records.uncertain,lease)
        raise

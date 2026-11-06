"""Fixed administrative Git stages in the existing sandbox; a source operation never receives arbitrary shell or native-model authority."""

from dataclasses import dataclass
import json
import hashlib
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from backend.git.source_operations import SourceRequest
from backend.runtime.broker_profile import _syscall_filter
from backend.runtime import _domain_spawn
from backend.runtime.development_workspace import _POLICY
from backend.runtime.git_capsule import PEER_ALLOCATION,GitCapsule,GitLaunch
from backend.runtime.native_network import NativeNetwork
from backend.runtime.workspaces import PEER_WORKSPACE


def validate_source_transport(request,transport,identity):
    """Bind explicit authenticated cloning to one configured HTTPS origin without sending its credential to a public or redirected destination."""
    if not request.use_configured_auth:
        if identity is not None:raise ValueError('Public source request cannot inherit remote credentials')
        return
    from backend.runtime.remote_transport import RemoteTransportConfig

    if not isinstance(transport,RemoteTransportConfig) or identity!=transport.identity:raise ValueError('Original configured clone credential origin differs')
    requested,configured=urlsplit(request.remote_url),urlsplit(transport.api_base)
    if (requested.scheme,requested.hostname,requested.port or 443)!=(configured.scheme,configured.hostname,configured.port or 443):raise ValueError('Clone URL is outside the configured credential origin')


@dataclass(frozen=True,kw_only=True)
class SourceGitLaunch(GitLaunch):
    """One exact original source request and fixed Git stage; neither callers nor a model can supply push/config/reset/cleanup arguments."""

    request: SourceRequest
    operation_id: str
    stage: str
    transport_identity: str | None = None
    observation_only: bool = False
    repair_key: str | None = None
    repair_program_sha256: str | None = None

    def __post_init__(self):
        """Match the complete argv/cwd/allocation profile before any shared broker reservation or command gate."""
        super().__post_init__()
        if not isinstance(self.request,SourceRequest) or self.request.mode=='create_remote' or len(self.operation_id)!=32 or any(c not in '0123456789abcdef' for c in self.operation_id):raise ValueError('Original administrative Git intent required')
        if self.arguments!=self.command(self.request,self.operation_id,self.stage):raise ValueError('Git arguments differ from the fixed source stage')
        if self.stage=='repair' and (self.repair_key is None or not isinstance(self.repair_program_sha256,str) or len(self.repair_program_sha256)!=64 or self.observation_only):raise ValueError('Repair needs original explicit continuation and pinned trusted driver')
        if self.stage!='repair' and self.repair_program_sha256 is not None:raise ValueError('Only the repair stage can execute its fixed driver')
        if type(self.observation_only)is not bool or (self.observation_only and self.stage in ('init','commit','clone','read_index','checkout','repair')):raise ValueError('Source observation cannot initialize, clone or write')
        if self.cwd!=str(PEER_WORKSPACE if self.request.mode=='adopt' or self.observation_only else PEER_ALLOCATION):raise ValueError('Source stage cwd differs from its exact view')
        if (self.allocation is None)!=(self.request.mode=='adopt' or self.observation_only):raise ValueError('Source stage writable allocation differs')
        if self.request.use_configured_auth and (not isinstance(self.transport_identity,str) or len(self.transport_identity)!=64):raise ValueError('Explicit configured clone origin required')
        if not self.request.use_configured_auth and self.transport_identity is not None:raise ValueError('Public source stage cannot inherit a credential')

    @staticmethod
    def command(request,operation_id,stage):
        """Describe only required original create/clone/read stages; checkout-index without force preserves unexpectedly existing files."""
        commands={
            'root':('rev-parse','--show-toplevel'),
            'head':('rev-parse','--verify','HEAD^{commit}'),
            'tree':('rev-parse','--verify','HEAD^{tree}'),
            'branch':('symbolic-ref','--quiet','--short','HEAD'),
            'status':('status','--porcelain=v1','--untracked-files=all'),
            'origin':('remote','get-url','origin'),
            'configuration':('config','--local','--null','--list'),
            'initial_message':('show','-s','--format=%P%n%B','HEAD'),
            'initial_files':('ls-tree','--full-tree','-rz','HEAD'),
        }
        if request.mode=='create':
            commands.update(init=('init','--template=','-b',request.branch,'.'),commit=('-c','user.name=Researcher owner','-c','user.email=owner@localhost','-c','commit.gpgsign=false','commit','--allow-empty','-m',f'Initialize source ({operation_id})'))
        if request.mode=='clone':
            commands.update(clone=('-c','protocol.https.allow=always','-c','http.followRedirects=false','-c','http.sslCAInfo=/run/researcher-network/ca.pem','-c','transfer.fsckObjects=true','clone','--no-hardlinks','--no-recurse-submodules','--no-checkout',*(('--branch',request.branch)if request.branch else()),'--',request.remote_url,'.'),read_index=('read-tree','HEAD'),checkout=('checkout-index','-a'))
        if request.mode in ('create','clone'):
            commands['repair']=('researcher-source-repair',)
        if stage not in commands:raise ValueError('Unsupported source Git stage')
        return (*_POLICY,*commands[stage])

    @property
    def networked(self):
        """Networking belongs only to the explicitly requested fixed HTTPS clone; observations and checkout keep sockets disabled."""
        return self.stage=='clone' or (self.stage=='repair' and self.request.mode=='clone')


class SourceGitCapsule(GitCapsule):
    """Mount only the original readonly administrative view and private allocation; optional clone networking belongs to fixed trusted Git, not model code."""

    def __init__(self,binding,launch,info_fd,*,source_network=None,source_transport=None):
        """Use only host-inspected DNS/TLS assets, with no ambient OAuth/PAT, arbitrary helper or user-supplied trust bypass."""
        if not isinstance(launch,SourceGitLaunch):raise TypeError('Fixed administrative Git launch required')
        if launch.networked and not isinstance(source_network,NativeNetwork):raise ValueError('Inspected source clone TLS/resolver configuration required')
        if not launch.observation_only:
            validate_source_transport(launch.request,source_transport,launch.transport_identity)
            if launch.request.use_configured_auth and source_network!=source_transport.network:raise ValueError('Clone trust differs from original configured origin')
        super().__init__(binding,launch,info_fd);self.source_network,self.source_transport=source_network,source_transport;self._network_fds=[]

    def _program(self):
        """Keep the configured PAT out of argv/manifests/config by reading a sealed private credential only inside the exact clone namespace."""
        program=super()._program()
        if self.launch.stage=='repair':
            from dataclasses import asdict
            from backend.runtime.development_workspace import _POLICY

            data=Path(__file__).with_name('source_repair_program.py').read_bytes()
            if len(data)>65536 or hashlib.sha256(data).hexdigest()!=self.launch.repair_program_sha256:
                raise ValueError('Pinned source repair driver changed before launch')
            code='import os,sys;os.environ.clear();os.environ.update('+repr(dict(self.launch.environment))+');os.chdir('+repr(self.launch.cwd)+');sys.argv='+repr(['source-repair',self.launch.asset.path,json.dumps(_POLICY),json.dumps(asdict(self.launch.request)),self.launch.operation_id])+";exec(compile("+repr(data)+",'<owned-source-repair>','exec'),{'__name__':'__main__'})"
            return [str(Path(sys.executable).resolve(strict=True)),'-I','-S','-c',code]
        if not(self.launch.networked and self.launch.request.use_configured_auth):return program
        code='import os,json,base64;env='+repr(dict(self.launch.environment))+";cred=json.load(open('/run/researcher-network/credential'));env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0="+repr('http.'+self.launch.request.remote_url+'.extraHeader')+",GIT_CONFIG_VALUE_0='Authorization: Basic '+base64.b64encode((cred['username']+':'+cred['token']).encode()).decode());os.chdir("+repr(self.launch.cwd)+');os.execve('+repr(self.launch.asset.path)+','+repr([self.launch.asset.path,*self.launch.arguments])+',env)'
        return [str(Path(sys.executable).resolve(strict=True)),'-I','-S','-c',code]

    def _network(self):
        """Share network only with the exact trusted clone program; this is program confinement, not a kernel destination ACL."""
        return ['--share-net']if self.launch.networked else []

    def _filter(self):
        """Retain protected-peer and namespace protections while permitting outbound sockets solely for the clone stage."""
        return _syscall_filter(network=self.launch.networked,protected_peers=True)

    def _mounts(self):
        """Pin the host-selected public CA/resolver only for HTTPS; source/control/credential directories are never broadly exposed."""
        mounts=super()._mounts()
        if self.launch.networked:
            fds=self._stack.enter_context(self.source_network.opened())
            self._network_fds.extend(fds.values())
            mounts+=['--dir','/run/researcher-network','--ro-bind-data',str(fds['resolver']),'/etc/resolv.conf','--ro-bind-data',str(fds['ca_bundle']),'/run/researcher-network/ca.pem']
            if self.launch.request.use_configured_auth:
                secret=_domain_spawn.sealed(json.dumps({'username':self.source_transport.username,'token':self.source_transport.token()}).encode());self._stack.callback(os.close,secret);self._network_fds.append(secret)
                mounts+=['--ro-bind-data',str(secret),'/run/researcher-network/credential']
        return mounts

    def __enter__(self):
        """Retain sealed trust/credential descriptors through the original gated spawn, then close them with the owning capsule."""
        super().__enter__();self.pass_fds+=tuple(self._network_fds);return self

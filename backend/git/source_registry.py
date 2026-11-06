"""Administrative command-peer registry and verified closure projection for original source-setup operations, without native runtime rows."""

from dataclasses import asdict
from uuid import uuid4

from backend.git.source_operations import SourceLease,SourceOperations,SourceView
from backend.knowledge.reviews import digest
from backend.runtime.contracts import RunConflict,RunNotFound
from backend.runtime.peer_process import NamespaceIdentity


def source_scope(row):
    """Bind the complete original request, operator configuration and captured directory views across all command stages."""
    return digest({**{key:row[key] for key in ('request','remote_identity','target','view')},'observation_only':row.get('observation_only',False)})


class SourcePeerRegistry:
    """Adapt the existing host broker protocol to a real administrative operation; no repository/task/run identity is fabricated."""

    def __init__(self,records,lease,stage):
        """Freeze one original source lease and fixed command stage; recovered instances may project closure but never prepare another stage."""
        self.records,self.lease,self.stage=records,lease,stage

    def prepare(self,lease,kind):
        """Retain one peer per original stage so response loss cannot mint another write under a different peer identity."""
        if lease!=self.lease or kind!='command' or self.stage is None:raise RunConflict('A fixed original source command is required')
        with self.records.runs._transaction(write=True) as conn:
            metadata,row=self.records._owned(conn,lease)
            peers=[p for p in row['peers'].values() if p['stage']==self.stage]
            if peers:return peers[0]['id']
            if len(row['peers'])>=32:raise RunConflict('El alta supera el límite de comandos completos; no se omitieron efectos.')
            peer=uuid4().hex
            row['peers'][peer]={'id':peer,'database_identity':lease.database_identity,'attempt_id':lease.attempt_id,'fence':lease.fence,'kind':'command','stage':self.stage,'state':'prepared','namespace':None}
            self.records._save(conn,lease.project_id,metadata);return peer

    def inspect(self,peer_id):
        """Read only an exact peer of this operation; labels from a native task cannot authorize it."""
        row=self.records.read(self.lease.project_id,self.lease.operation_key)
        peer=row['peers'].get(peer_id)
        if peer is None:raise RunNotFound('Source command not found')
        return peer

    def admission(self,peer_id,*,source_only=False):
        """Recheck actual owner/root/allocation and original stage before the shared broker can reserve its global concession."""
        with self.records.runs._transaction() as conn:
            _,row=self.records._owned(conn,self.lease);peer=row['peers'].get(peer_id)
            if peer is None or peer['state']!='prepared' or peer['stage']!=self.stage:raise RunConflict('El comando original ya cambió de fase.')
            view=row['view']
            if view is None:raise RunConflict('La asignación original aún no está confirmada.')
            binding=SourceView(**view['source']);binding.verify()
            if view['allocation']:
                a=view['allocation'];SourceView(a['path'],a['device'],a['inode']).verify()
            return {'database_identity':self.lease.database_identity,'database_path':self.records.runs.database,'attempt_id':self.lease.attempt_id,'fence':self.lease.fence,'kind':'command','project_id':self.lease.project_id,'task_id':None,'context_version':1,'execution_kind':'repository_setup','source_kind':'repository_setup','source_operation_key':self.lease.operation_key,'source_operation_id':row['operation_id'],'source_request':row['request'],'source_request_sha256':digest(row['request']),'source_scope_sha256':source_scope(row),'source_remote_identity':row['remote_identity'],'source_stage':self.stage,'source_observation_only':row.get('observation_only',False),'source_allocation':view['allocation'],'binding':binding,'source_binding':binding}

    def bind(self,peer_id,identity):
        """Persist the actual namespace identity before the broker releases G; there is no user-supplied PID or closure flag."""
        if not isinstance(identity,NamespaceIdentity):raise TypeError('Original captured namespace required')
        with self.records.runs._transaction(write=True) as conn:
            metadata,row=self.records._owned(conn,self.lease);peer=row['peers'].get(peer_id)
            if peer is None or peer['state']!='prepared' or peer['stage']!=self.stage:raise RunConflict('Source command cannot bind another execution')
            peer.update(state='bound',namespace=asdict(identity));self.records._save(conn,self.lease.project_id,metadata)

    @classmethod
    def project(cls,snapshot,grant_id,operation_id=None,*,source=None):
        """Project only the broker's witnessed closure for this administrative origin; a native closure or caller boolean cannot complete source setup."""
        grant=snapshot.records['broker:grant:'+grant_id]
        if grant.get('source_kind')!='repository_setup' or grant.get('task_id') is not None:raise RunConflict('Administrative source origin differs')
        if source is None:
            from backend.runtime.sqlite_runs import SQLiteRunStore

            records=SourceOperations(SQLiteRunStore(grant['source_database']),workspaces=None,control_root='/run/researcher-no-source-control')
        else:records=source.records
        if records._origin()!=grant['database_identity']:raise RunConflict('Source setup database origin changed')
        closed=[(key.removeprefix('broker:op:'),v) for key,v in snapshot.records.items() if key.startswith('broker:op:') and v['grant_id']==grant_id and (operation_id is None or key=='broker:op:'+operation_id)]
        if operation_id is not None and (len(closed)!=1 or closed[0][1].get('execution_closed')is not True):raise RunConflict('Original source command closure is unproven')
        projected=[]
        with records.runs._transaction(write=True) as conn:
            metadata,row=records._row(conn,grant['project_id'],grant['source_operation_key'])
            if (row['attempt_id'],row['fence'],row['database_identity'])!=(grant['attempt_id'],grant['fence'],grant['database_identity']) or row['view']['source']!=grant['workspace_binding'] or row['operation_id']!=grant['source_operation_id'] or digest(row['request'])!=grant['source_request_sha256'] or source_scope(row)!=grant['source_scope_sha256']:raise RunConflict('Original source attempt/view differs')
            for _,op in closed:
                if op.get('execution_closed')is not True:continue
                peer=row['peers'].get(op['peer_id'])
                if peer is None or peer['attempt_id']!=grant['attempt_id'] or peer['fence']!=grant['fence'] or peer['kind']!=op['kind'] or op['state']!='closed':raise RunConflict('Original source command differs')
                if peer['namespace'] is None:
                    if peer['state']=='bound' or op['gate_sent']is not False:raise RunConflict('Original source namespace binding is missing')
                elif peer['namespace']!=op['namespace']:raise RunConflict('Original source namespace differs')
                peer.update(state='closed',exit_code=op.get('exit_code'),closure_reason='broker_verified');projected.append(dict(peer))
            if grant['state']=='retired' and grant.get('domain_removed')is True:row['closure']={'grant_id':grant_id,'attempt_id':grant['attempt_id'],'domain_removed':True}
            records._save(conn,grant['project_id'],metadata)
        return tuple(projected)

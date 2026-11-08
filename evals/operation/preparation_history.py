"""Diagnose one actual bounded HTTP host while forbidding every inference request."""
import asyncio
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / '.researcher/evaluations/preparation-history-20261108'


def observe(root):
    """Read original execution identities, resource closure and actual native starts without private row contents."""
    with closing(sqlite3.connect((root/'source.db').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        return {'runs':[dict(r) for r in db.execute('SELECT id,status,issue_json FROM runtime_runs')],
                'native_starts':db.execute('SELECT COUNT(*) FROM runtime_attempts WHERE turn_id IS NOT NULL').fetchone()[0],
                'dispatches':db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0],
                'unclosed_peers':db.execute("SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0],
                'unrevoked_grants':db.execute('SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0],
                'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}


def worker(port):
    """Run the installed ASGI factory under uvloop with diagnostic guards before turn/start."""
    import logging
    import traceback
    import uvicorn
    from backend.runtime import authority_journal
    from backend.runtime.service import _failure_sites
    from backend.runtime.peer_broker import PeerBroker
    from backend.runtime.broker_inference import BrokerInferenceSession
    from backend.runtime.codex_rpc import JsonRpcClient

    def record(value):
        """Append safe static locations and observation metadata, never exception text or locals."""
        with (OUT/'diagnostics.jsonl').open('a') as stream:
            stream.write(json.dumps({'cycle':os.environ.get('RESEARCHER_PROBE_CYCLE'),**value})+'\n')

    def authority_init(self, *args):
        """Capture authority errors at their producer before cleanup can mask the original caller."""
        record({'stage':'authority_raise','type':type(self).__name__,
                'frames':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_stack()[-8:-1]]})
        RuntimeError.__init__(self,*args)

    for kind in (authority_journal.AuthorityBusy,authority_journal.AuthorityConflict):
        kind.__init__=authority_init
    from contextlib import contextmanager
    import threading
    operation=authority_journal.WitnessedAuthorityJournal._operation

    @contextmanager
    def traced_operation(self):
        """Observe actual authority handle/thread intervals without private contents or changed lock semantics."""
        label={'pid':os.getpid(),'thread':threading.get_ident(),'handle':id(self)}
        record({'stage':'authority_begin','monotonic':time.monotonic(),**label})
        try:
            with operation(self) as conn:yield conn
        finally:record({'stage':'authority_end','monotonic':time.monotonic(),**label})
    authority_journal.WitnessedAuthorityJournal._operation=traced_operation
    original=PeerBroker._run

    def traced(self,*args,**kwargs):
        """Retain the launch failure before concurrent MCP/peer cleanup executes."""
        try:return original(self,*args,**kwargs)
        except BaseException as error:
            record({'stage':'launch_failure','sites':_failure_sites(error)})
            raise
    PeerBroker._run=traced

    async def guard(self,*args,**kwargs):
        """Complete the diagnostic observation and prohibit generation before native turn reservation."""
        record({'stage':'prepared_generation_forbidden','loop':type(asyncio.get_running_loop()).__module__})
        raise RuntimeError('PreparationProbeGenerationForbidden')
    BrokerInferenceSession.run=guard
    request=JsonRpcClient.request

    async def rpc_guard(self,method,*args,**kwargs):
        """Independently reject any generation path that bypasses the facade guard."""
        if method=='turn/start':
            record({'stage':'unexpected_turn_start_blocked'})
            raise RuntimeError('PreparationProbeTurnStartForbidden')
        return await request(self,method,*args,**kwargs)
    JsonRpcClient.request=rpc_guard
    logging.getLogger('httpx').setLevel(logging.WARNING)
    uvicorn.run('backend.api.main:create_app',factory=True,host='127.0.0.1',port=port,loop='uvloop',log_level='warning')


def supervisor(root,port):
    """Use the actual production service guardian and original configured resource ceilings."""
    from backend.runtime.host_installation import host_environment
    from backend.runtime.service_process import run_bounded_services
    os.environ.update(host_environment(root))
    c=json.loads((root/'runtime.json').read_text())
    raise SystemExit(run_bounded_services([('API-diagnostic',[sys.executable,'-I',__file__,'worker',str(port)],root/'service')],
                    cgroup_parent=c['cgroup_parent'],limits=c['service_limits'],state_dir=root/'service'))


def main():
    """Observe exactly two guarded admissions separated by real service retirement and restart, preserving both histories."""
    import backend
    import httpx
    from backend.runtime.host_installation import initialize_host
    from backend.runtime.authority_journal import WitnessedAuthorityJournal

    assert Path(backend.__file__).is_relative_to(Path(sys.prefix))
    OUT.mkdir(mode=0o700)
    assets=json.loads((REPO/'.superpowers/sdd/2026-10-31-actualizacion-proyecto/host-installation-assets.json').read_text())
    assets.pop('storage',None)
    root=OUT/'host';initialize_host(root,witness_dir=OUT/'witness',assets=assets)
    source=root/'sources/observations';source.mkdir()
    item=source/'observations.py';item.write_text('"""Synthetic example only; actual records remain unspecified."""\ndef list_observations():\n    return []\n')
    second_source=root/'sources/observations-second';second_source.mkdir();(second_source/'observations.py').write_bytes(item.read_bytes())
    before=hashlib.sha256(item.read_bytes()).hexdigest()
    result={'status':'running','scope':'Two zero-generation preparations on one host, separated by API restart; compound retained-history/restart observation, not an accepted-plan reproduction.','backend':backend.__file__,'maximum_model_turns':0,'cycles':[]}
    try:
        for cycle in (1,2):
            entry={'cycle':cycle};result['cycles'].append(entry)
            with socket.socket()as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            process=None
            with (OUT/f'service-{cycle}.log').open('x')as log:
                try:
                    process=subprocess.Popen([sys.executable,'-I',__file__,'supervisor',str(root),str(port)],cwd=root/'service',stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'RESEARCHER_PROBE_CYCLE':str(cycle)})
                    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=5)as client:
                        deadline=time.monotonic()+30
                        while time.monotonic()<deadline:
                            if process.poll()is not None:raise RuntimeError('Service ended before readiness')
                            try:
                                if client.get('/api/health/ready').status_code==200:break
                            except httpx.TransportError:pass
                            time.sleep(.1)
                        else:raise TimeoutError('Readiness expired')
                        keys=list((root/'auth').glob('owner-*.key'));assert len(keys)==1
                        r=client.post('/api/session',json={'code':keys[0].read_text().strip()},headers={'X-Researcher-Client':'web'});r.raise_for_status()
                        client.headers.update({'X-Researcher-CSRF':r.json()['csrf_token'],'X-Researcher-Endpoint':r.json()['endpoint_id']})
                        key=f'history-cycle-{cycle}'
                        r=client.post('/api/projects',json={'name':f'Preparación con historia {cycle}','description':'Proponer un plan en español para documentar entradas, relaciones y salida CSV. No ejecutar tareas.','operation_key':key+'-project'});r.raise_for_status();project=r.json()['id']
                        r=client.post(f'/api/projects/{project}/sources',json={'name':'observaciones','path':str(source if cycle==1 else second_source)});r.raise_for_status();repository=r.json()['repository_id']
                        r=client.post(f'/api/projects/{project}/start',json={'repository_id':repository,'operation_key':key+'-plan','prompt':'Propón un plan en español; no ejecutes las tareas.'})
                        r.raise_for_status();entry.update(project_id=project,admission=r.json());run_id=r.json()['run']['run_id']
                        deadline=time.monotonic()+100
                        while time.monotonic()<deadline:
                            state=observe(root)
                            if len(state['runs'])==cycle and next((v['status']for v in state['runs']if v['id']==run_id),None)in ('failed','cancelled'):break
                            time.sleep(.15)
                        else:raise TimeoutError('Original preparation did not terminate')
                        entry['storage_before_shutdown']=state
                finally:
                    if process is not None:
                        if process.poll()is None:process.terminate()
                        entry['service_exit']=process.wait(timeout=30)
                    entry['storage_after_shutdown']=observe(root)
            assert entry['storage_after_shutdown']['native_starts']==0 and entry['storage_after_shutdown']['unclosed_peers']==0
            config=json.loads((root/'runtime.json').read_text())
            with WitnessedAuthorityJournal(**config['authority'])as journal:
                snapshot=journal.load()
                entry['authority']={'sequence':snapshot.sequence,'witness_bytes':Path(config['authority']['witness']).stat().st_size,'grants':[{'state':v.get('state'),'domain_removed':v.get('domain_removed')}for k,v in snapshot.records.items()if k.startswith('broker:grant:')]}
            assert all(g['state']=='retired'and g['domain_removed']is True for g in entry['authority']['grants'])
        events=[json.loads(line)for line in (OUT/'diagnostics.jsonl').read_text().splitlines()]
        result['guard_cycles']=[e['cycle']for e in events if e['stage']=='prepared_generation_forbidden']
        result['authority_errors']=[e for e in events if e['stage']=='authority_raise']
        result['source_unchanged']=hashlib.sha256(item.read_bytes()).hexdigest()==before
        assert result['guard_cycles']==['1','2'] and not any(e['stage']=='unexpected_turn_start_blocked'for e in events)
        result['status']='observed_no_contention'if not result['authority_errors']else'observed_contention'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__);raise
    finally:
        (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'cycles':len(result['cycles']),'guard_cycles':result.get('guard_cycles'),'authority_errors':result.get('authority_errors')}),flush=True)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':worker(int(sys.argv[2]))
    elif len(sys.argv)>1 and sys.argv[1]=='supervisor':supervisor(Path(sys.argv[2]),int(sys.argv[3]))
    else:main()

"""Exercise original task delivery acceptance and reopening on installed HTTP without a model.

The report and logical attempt are synthetic domain fixtures. Owner decisions,
lost-response recovery and immutable report reads use the actual installed service.
"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

from host_smoke import start, stop
from task_creation_page import seed as seed_metadata
from task_requests_page import observe as observe_task

ROOT = Path(__file__).resolve().parents[2]


def seed(host):
    """Declare one immutable illustrative input/output report under a never-launched author."""
    from backend.db.connection import connect
    from backend.research.models import RESEARCH_PERMISSIONS, EvidenceReference, FindingDraft, ReportDraft, ResultDraft, SourceDraft
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    ids = seed_metadata(host)
    source = host/'sources'/'observations'
    source.mkdir()
    (source/'observations.py').write_text('"""Synthetic fixture; no observation was measured."""\nobservations = [{"id": 7, "measurement": 12}]\n')
    with closing(connect(host/'source.db')) as db, db:
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'observaciones',?)",(str(source),))
    runs, research = SQLiteRunStore(host/'source.db'), SQLiteResearchStore(host/'source.db')
    version = runs.context_snapshot(101,ids['input'])['context_version']
    run = runs.admit(RunSpec(101,ids['input'],'researcher',version,'synthetic-delivery-request','Explica cómo una observación se convierte en una fila CSV, con entrada y salida relacionadas.','codex'),binding=WorkspaceRegistry(host/'source.db',host/'sources').bind(101,11))
    lease, peers = AttemptPeers.claim(runs,101,run.run_id,'synthetic-author-never-launched')
    try:
        runs.bind_native(lease,thread_id='synthetic-never-launched-thread',turn_id='synthetic-never-launched-turn')
        token = research.issue_grant(project_id=101,task_id=ids['input'],agent_id=lease.actor_id,permissions=set(RESEARCH_PERMISSIONS))
        scope = research.authorize(token)
        runs.bind_grant(lease,scope.grant_id)
        quote = 'La observación de ejemplo usa id=7 y measurement=12.'
        captured = research.capture_source(scope,'example-source',SourceDraft('attachment','synthetic:observation','Observación sintética',quote),intent={'synthetic_fixture':True})
        finding = research.record_finding(scope,'example-finding',FindingDraft('Relación ilustrada entre campos',quote,(EvidenceReference(captured['source_id'],quote),)))
        content = '## Propósito\n\nMostrar cómo pasar de una observación a una fila CSV. Es un ejemplo sintético, no un dato medido.\n\n## Entrada del ejemplo\n\n```json\n{"id": 7, "measurement": 12}\n```\n\n## Relación\n\nEl campo id identifica la observación. El campo measurement aporta el valor que se escribe en la columna value.\n\n## Salida esperada del ejemplo\n\n```csv\nid,value\n7,12\n```\n\n## Qué falta comprobar\n\nNo sabemos si los datos reales tienen esos campos ni si incluyen valores ausentes.'
        report = research.write_report(scope,'example-report',ReportDraft('Una observación y su fila CSV',content,(finding['finding_id'],)))
        research.propose_result(scope,'example-delivery',ResultDraft((report['artifact_id'],),'Ejemplo sintético de entrada, relación y salida.',('No se comprobaron observaciones reales.','El ejemplo no demuestra que todos los registros compartan la estructura.'),))
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.finish(lease,native_status='completed',summary='Synthetic delivery only; no model or native process was launched.')
    except BaseException:
        for peer in peers.ids.values():
            peers.registry.close(peer)
        runs.cancel(101,run.run_id)
        runs.retire_inference(lease,outcome='cancelled')
        raise
    state = runs.result_state(101,run.run_id)
    assert state['eligible'] is True and state['candidate_current'] is True
    ids.update(run=run.run_id,report=report['artifact_id'],candidate=state['candidate'])
    return ids


def observe(host, ids):
    """Observe original report bytes, decisions and task version independently of browser notices."""
    from backend.runtime.sqlite_runs import SQLiteRunStore

    value = observe_task(host)
    value['result'] = SQLiteRunStore(host/'source.db').result_state(101,ids['run'])
    with closing(sqlite3.connect(host/'source.db')) as db:
        value['report_sha256'] = hashlib.sha256(db.execute('SELECT content FROM artifacts WHERE id=?',(ids['report'],)).fetchone()[0].encode()).hexdigest()
    return value


def main():
    """Own one installed service/browser and verify two exact decisions without admitting new inference."""
    import backend
    from backend.runtime.host_installation import initialize_host

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--node',type=Path,required=True)
    args = parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use the separately installed product Python')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    assets = json.loads(args.assets.read_text())
    token = output/'synthetic-account.json'
    with token.open('x') as stream:
        os.chmod(token,0o600)
        json.dump({'auth_mode':'chatgpt','tokens':{'access_token':'synthetic.header.signature','account_id':'synthetic-task-results'}},stream)
    assets.update(token_file=str(token),static_dir=str(ROOT/'frontend/dist'))
    assets.pop('storage',None)
    host = output/'host'
    initialize_host(host,witness_dir=output/'witness',assets=assets)
    ids = seed(host)
    fixture = output/'fixture.json'
    fixture.write_text(json.dumps(ids,indent=2)+'\n')
    before = observe(host,ids)
    assert before['dispatches']==0 and before['native_starts']==1 and all(peer['state']=='closed' for peer in before['peers'])
    result = {'status':'running','model_turns':0,'synthetic_project_data':True,'synthetic_bound_turn_ids':1,'before':before,'backend':str(Path(backend.__file__).resolve()),'web_index_sha256':hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()}
    with socket.socket() as binding:
        binding.bind(('127.0.0.1',0))
        port = binding.getsockname()[1]
    process = log = None
    try:
        process,log = start(host,output,port,1)
        keys = list((host/'auth').glob('owner-*.key'))
        if len(keys)!=1:
            raise RuntimeError('Expected one private synthetic owner key')
        env = {**os.environ,'RESEARCHER_E2E_ORIGIN':f'http://127.0.0.1:{port}','RESEARCHER_E2E_OWNER_FILE':str(keys[0]),'RESEARCHER_E2E_OUTPUT':str(output/'browser'),'RESEARCHER_E2E_FIXTURE':str(fixture)}
        with (output/'browser.log').open('x') as browser_log:
            browser = subprocess.run([str(args.node.resolve(strict=True)),'tests/task-results.e2e.mjs'],cwd=ROOT/'frontend',env=env,stdout=browser_log,stderr=subprocess.STDOUT,check=False,timeout=180)
        result['browser_exit'] = browser.returncode
        assert browser.returncode==0,'Inspect original browser log'
        after = observe(host,ids)
        assert len(after['runs'])==1 and after['runs'][0]['status']=='accepted'
        assert after['result']['acceptance'] and not after['result']['acceptance_current']
        assert after['result']['candidate']==before['result']['candidate']
        assert after['report_sha256']==before['report_sha256'] and after['source_sha256']==before['source_sha256']
        assert after['dispatches']==0 and after['native_starts']==1 and after['peers']==before['peers']
        assert len(after['corrections'])==1 and after['corrections'][0]['version']==2
        task = next(row for row in after['task_records'] if row['id']==ids['input'])
        assert task['status']=='pending'
        assert all(after[key]==before[key] for key in ('groups','milestones','dependencies','owner_commands','integrity','foreign_keys'))
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            result['service_exit'] = stop(process,log)
        result['after'] = observe(host,ids)
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'receipt':str(output/'result.json')}),flush=True)


if __name__=='__main__':
    main()

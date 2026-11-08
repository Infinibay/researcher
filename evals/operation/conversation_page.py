"""Verify installed conversation reads and exact owner note/answer recovery without a generative model.

The question and its closed logical peers are explicit domain fixtures. Browser
decisions use actual owner HTTP and are observed independently in SQLite.
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

ROOT=Path(__file__).resolve().parents[2]


def seed(host):
    """Create a genuinely missing sample, one grouped question and explicit archived notes with no launched native process."""
    from backend.communication.owner_notes import OwnerNotes
    from backend.db.connection import connect
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.questions import Question,QuestionOption,QuestionSet
    from backend.runtime.sqlite_questions import SQLiteQuestionStore
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    ids=seed_metadata(host)
    source=host/'sources'/'observations';source.mkdir()
    (source/'observations.py').write_text('"""Synthetic fixture: no observed records were supplied."""\nobservations = []\n')
    with closing(connect(host/'source.db')) as db,db:
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'observaciones',?)",(str(source),))
    runs,research=SQLiteRunStore(host/'source.db'),SQLiteResearchStore(host/'source.db')
    version=runs.context_snapshot(101,ids['input'])['context_version']
    run=runs.admit(RunSpec(101,ids['input'],'researcher',version,'synthetic-question-instruction','Antes de programar el CSV, explica el objetivo, relaciona los datos de entrada con la salida y pide una muestra si falta.','codex'),conversation_thread='synthetic-question-thread',binding=WorkspaceRegistry(host/'source.db',host/'sources').bind(101,11))
    lease,peers=AttemptPeers.claim(runs,101,run.run_id,'synthetic-question-owner-never-launched')
    try:
        runs.bind_native(lease,thread_id='synthetic-never-launched-thread',turn_id='synthetic-never-launched-turn')
        token=research.issue_grant(project_id=101,task_id=ids['input'],agent_id=lease.actor_id,permissions={'questions.ask'})
        scope=research.authorize(token);runs.bind_grant(lease,scope.grant_id)
        questions=SQLiteQuestionStore(runs,research)
        result=questions.ask(scope,'synthetic-ask-sample',QuestionSet((
            Question('example','¿Puedes indicar una observación de ejemplo con sus campos?','Objetivo: convertir observaciones en CSV. No hay registros cargados; necesitamos relacionar cada campo con una columna antes de programar.',(),'{"id":7,"measurement":12} sería una entrada ilustrativa, no un dato medido.'),
            Question('column','¿Qué nombre quieres para la columna que contiene la medición?','Es una elección de salida que la fuente no establece.',(QuestionOption('output_value','value'),QuestionOption('output_measurement','measurement')),'Si eliges value, el ejemplo anterior daría las columnas id,value y la fila 7,12. Es una ilustración condicional.'),
        )))
        for peer in peers.ids.values():peers.registry.close(peer)
        assert questions.park(lease).status=='waiting_input'
    except BaseException:
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.cancel(101,run.run_id);runs.retire_inference(lease,outcome='cancelled')
        raise
    notes=OwnerNotes(runs)
    archived=notes.record(101,{'operation_key':'fixture-archive-note','message':'Ejemplo de archivo: aquí quedó una nota sobre el formato CSV.','thread_id':None,'to_agent':None,'to_role':'project_lead'})
    notes.record(202,{'operation_key':'fixture-foreign-note','message':'Nota exclusiva del proyecto separado.','thread_id':None,'to_agent':None,'to_role':'project_lead'})
    ids.update(run=run.run_id,question=result['request_id'],thread='synthetic-question-thread',archive_thread=archived['thread_id'])
    return ids


def observe(host):
    """Read original questions, note receipts and message identities without relying on UI success text."""
    value=observe_task(host)
    with closing(sqlite3.connect(host/'source.db')) as db:
        db.row_factory=sqlite3.Row
        value['questions']=[dict(row) for row in db.execute('SELECT q.request_id,q.run_id,q.thread_id,q.context_version,q.answer_context_version,q.answer_message_id,u.status,u.response FROM runtime_question_links q JOIN user_requests u ON u.id=q.request_id ORDER BY q.request_id')]
        value['notes']=[dict(row) for row in db.execute('SELECT project_id,operation_key,message_id,request_sha256,receipt_json FROM runtime_owner_notes ORDER BY project_id,operation_key')]
        value['messages']=[dict(row) for row in db.execute('SELECT id,project_id,thread_id,from_agent,message,conversation_type FROM chat_messages ORDER BY id')]
    return value


def verify(ids,before,after,evidence):
    """Prove one note and one context change from exact original HTTP bodies, with no new native admission."""
    assert len(before['runs'])==len(after['runs'])==1 and before['runs'][0]['status']=='waiting_input' and after['runs'][0]['status']=='superseded'
    assert before['dispatches']==after['dispatches']==0 and before['native_starts']==after['native_starts']==1
    assert after['peers']==before['peers'] and all(peer['state']=='closed' for peer in after['peers'])
    assert all(after[key]==before[key] for key in ('groups','milestones','tasks','task_records','dependencies','owner_commands','integrity','foreign_keys','source_sha256'))
    assert after['contexts']==[{'task_id':ids['input'],'version':2},{'task_id':ids['output'],'version':2}]
    assert len(after['notes'])==len(before['notes'])+1 and len(after['messages'])==len(before['messages'])+2
    note=evidence['notes'][0]
    stored=next(row for row in after['notes'] if row['operation_key']==note['body']['operation_key'])
    assert json.loads(stored['receipt_json'])['id']==note['receipt']['id']
    answer=evidence['answers'][0]['body']
    q=after['questions'][0]
    assert q['request_id']==ids['question'] and q['status']=='responded' and q['answer_context_version']==2
    assert json.loads(q['response'])==answer['answers']
    controls=[row for row in after['controls'] if row['operation_key']==answer['operation_key']]
    assert len(controls)==1 and json.loads(controls[0]['result_json'])=={'version':2}
    assert len([row for row in after['corrections'] if row['task_id']==ids['input'] and row['source_reference']=='question:'+str(ids['question'])])==1


def main():
    """Own one installed host/browser through terminal closure and preserve actual before/after evidence on every exit."""
    import backend
    from backend.runtime.host_installation import initialize_host

    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--node',type=Path,required=True)
    parser.add_argument('--resume-evaluation',type=Path,help='Continue only the original stopped fixture after confirmed note recovery and before any answer was sent')
    args=parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):raise RuntimeError('Use the separately installed product Python')
    output=args.output.resolve();output.mkdir(mode=0o700)
    previous=None
    if args.resume_evaluation is not None:
        previous=args.resume_evaluation.resolve(strict=True)
        original=json.loads((previous/'result.json').read_text());browser_state=json.loads((previous/'browser/evidence.json').read_text())
        host=Path(original['host_root']) if original.get('host_root') else Path(original.get('continued_from',str(previous)))/'host'
        ids=json.loads((previous/'fixture.json').read_text());before=original['before']
        assert original['status']=='failed' and original['service_exit']==143
        assert len(browser_state['notes'])==2 and len(browser_state['answers']) in (0,2) and not browser_state['errors']
        assert observe(host)==original['after']
        if browser_state['answers']:
            assert browser_state['answers'][0]==browser_state['answers'][1]
            assert original['after']['questions'][0]['status']=='responded'
            assert original['after']['contexts']==[{'task_id':ids['input'],'version':2},{'task_id':ids['output'],'version':2}]
        else:
            assert original['after']['questions'][0]['status']=='pending'
            assert original['after']['contexts']==[{'task_id':ids['input'],'version':1}]
        assert original['after']['dispatches']==0 and all(peer['state']=='closed' for peer in original['after']['peers'])
    else:
        assets=json.loads(args.assets.read_text());token=output/'synthetic-account.json'
        with token.open('x') as stream:
            os.chmod(token,0o600);json.dump({'auth_mode':'chatgpt','tokens':{'access_token':'synthetic.header.signature','account_id':'synthetic-conversation'}},stream)
        assets.update(token_file=str(token),static_dir=str(ROOT/'frontend/dist'));assets.pop('storage',None)
        host=output/'host';initialize_host(host,witness_dir=output/'witness',assets=assets)
        ids=seed(host);before=observe(host)
    fixture=output/'fixture.json';fixture.write_text(json.dumps(ids,indent=2)+'\n')
    assert before['runs'][0]['status']=='waiting_input' and all(peer['state']=='closed' for peer in before['peers'])
    result={'status':'running','model_turns':0,'synthetic_project_data':True,'synthetic_bound_turn_ids':1,'before':before,'host_root':str(host.resolve()),'backend':str(Path(backend.__file__).resolve()),'web_index_sha256':hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()}
    if previous is not None:result['continued_from']=str(previous)
    with socket.socket() as binding:binding.bind(('127.0.0.1',0));port=binding.getsockname()[1]
    process=log=None
    try:
        process,log=start(host,output,port,1)
        keys=list((host/'auth').glob('owner-*.key'))
        if len(keys)!=1:raise RuntimeError('Expected one private synthetic owner key')
        env={**os.environ,'RESEARCHER_E2E_ORIGIN':f'http://127.0.0.1:{port}','RESEARCHER_E2E_OWNER_FILE':str(keys[0]),'RESEARCHER_E2E_OUTPUT':str(output/'browser'),'RESEARCHER_E2E_FIXTURE':str(fixture)}
        if previous is not None:env['RESEARCHER_E2E_CONTINUE_EVIDENCE']=str(previous/'browser/evidence.json')
        with (output/'browser.log').open('x') as browser_log:
            browser=subprocess.run([str(args.node.resolve(strict=True)),'tests/conversation.e2e.mjs'],cwd=ROOT/'frontend',env=env,stdout=browser_log,stderr=subprocess.STDOUT,check=False,timeout=180)
        result['browser_exit']=browser.returncode
        assert browser.returncode==0,'Inspect original browser log'
        evidence=json.loads((output/'browser/evidence.json').read_text());verify(ids,before,observe(host),evidence)
        result['status']='passed'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__);raise
    finally:
        if process is not None:result['service_exit']=stop(process,log)
        result['after']=observe(host);(output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'receipt':str(output/'result.json')}),flush=True)


if __name__=='__main__':main()

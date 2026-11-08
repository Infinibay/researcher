"""Read the original parked handoff question in the installed web UI without answering or admitting another turn."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from contextlib import closing

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/operation'))
from host_smoke import start,stop


def observe(host):
    """Bind original question/context/effects and source bytes; session pairing is outside business observations."""
    with closing(sqlite3.connect((host/'source.db').resolve().as_uri()+'?mode=ro',uri=True))as db:
        db.row_factory=sqlite3.Row
        tables=('projects','tasks','task_contexts','runtime_runs','runtime_attempts','runtime_attempt_models','runtime_input_snapshots','runtime_inference_dispatches','runtime_peers','tool_grants','user_requests','runtime_question_links','chat_messages','events_log','research_reports','artifacts')
        hashes={name:hashlib.sha256(json.dumps(sorted([dict(row)for row in db.execute(f'SELECT * FROM {name}')],key=lambda row:json.dumps(row,sort_keys=True,default=str)),sort_keys=True,default=str).encode()).hexdigest()for name in tables}
        repo=Path(db.execute('SELECT local_path FROM repositories WHERE id=11').fetchone()[0])
        return {'tables':hashes,'sources':{name:hashlib.sha256((repo/name).read_bytes()).hexdigest()for name in('invoice.py','test_invoice.py','evidence.py')},'questions':[dict(row)for row in db.execute('SELECT request_id,project_id,run_id,context_version,question_set_json FROM runtime_question_links')],'peers':[dict(row)for row in db.execute('SELECT kind,state FROM runtime_peers')],'runs':[dict(row)for row in db.execute('SELECT id,status FROM runtime_runs')],'unrevoked_grants':db.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0],'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':[tuple(row)for row in db.execute('PRAGMA foreign_key_check')]}


def main():
    """Revalidate the known closed original attempt, then own one readonly service/browser lifetime and retain its unchanged state."""
    import backend

    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--arm',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--node',type=Path,required=True);args=parser.parse_args()
    assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    arm=args.arm.resolve(strict=True);original=json.loads((arm/'result.json').read_text());host=arm/'installation';before=observe(host)
    assert original['owned_backend_terminal']and original['service_exit']==-15 and original['admissions_sent']==1
    assert len(before['runs'])==len(before['questions'])==1 and before['runs'][0]['status']=='waiting_input'
    assert all(p['state']=='closed'for p in before['peers'])and before['unrevoked_grants']==0
    question=before['questions'][0];assert '50,00' in question['question_set_json']
    output=args.output.resolve();output.mkdir(mode=0o700);fixture=output/'fixture.json';fixture.write_text(json.dumps({'project':101,'task':1001,'question':question['request_id']})+'\n')
    result={'status':'running','scope':'Readonly original generated question; no owner answer or next admission.','before':before};process=log=None
    with socket.socket()as binding:binding.bind(('127.0.0.1',0));port=binding.getsockname()[1]
    try:
        process,log=start(host,output,port,2);keys=list((host/'auth').glob('owner-*.key'));assert len(keys)==1
        env={**os.environ,'RESEARCHER_E2E_ORIGIN':f'http://127.0.0.1:{port}','RESEARCHER_E2E_OWNER_FILE':str(keys[0]),'RESEARCHER_E2E_OUTPUT':str(output/'browser'),'RESEARCHER_E2E_FIXTURE':str(fixture)}
        with(output/'browser.log').open('x')as stream:browser=subprocess.run([str(args.node.resolve(strict=True)),'tests/handoff-original.e2e.mjs'],cwd=ROOT/'frontend',env=env,stdout=stream,stderr=subprocess.STDOUT,check=False,timeout=90)
        result['browser_exit']=browser.returncode;assert browser.returncode==0
        assert observe(host)==before;result['status']='passed'
    except BaseException as error:result.update(status='failed',error_type=type(error).__name__);raise
    finally:
        if process is not None:result['service_exit']=stop(process,log)
        result['after']=observe(host);(output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status']}),flush=True)


if __name__=='__main__':main()

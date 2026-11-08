"""Exercise recoverable owner task creation and truthful dependency reads on a fresh installed host.

All project data and account fields are synthetic. Browser requests reach actual
HTTP/SQLite; no native run is admitted and no model response is fabricated.
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
from planning_page import observe as planning_observe

ROOT = Path(__file__).resolve().parents[2]


def seed(host):
    """Create only synthetic project/group/task metadata before starting the installed service."""
    from backend.db.connection import connect
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.runtime.sqlite_runs import SQLiteRunStore

    with closing(connect(host / 'source.db')) as db, db:
        db.execute("INSERT INTO projects(id,name,description) VALUES(101,'Cuaderno de observaciones','Entrada: observaciones cuyo formato debe comprobarse. Salida: CSV con las columnas verificadas.'),(202,'Proyecto separado','Sin tareas del cuaderno.')")
    records = OwnerPlanningRecords(SQLiteRunStore(host / 'source.db'))
    group = records.create_group(project_id=101, title='Exportación documentada', operation_key='fixture-group')
    milestone = records.create_milestone(project_id=101, epic_id=group['id'], title='Muestra documentada', operation_key='fixture-milestone')
    first = records.create_task(project_id=101, epic_id=group['id'], milestone_id=milestone['id'], title='Leer una observación real', type='research', operation_key='fixture-input')
    second = records.create_task(project_id=101, epic_id=group['id'], title='Exportar columnas comprobadas', type='code', depends_on=[first['id']], operation_key='fixture-output')
    return {'alpha':101, 'beta':202, 'group':group['id'], 'milestone':milestone['id'], 'input':first['id'], 'output':second['id']}


def observe(host):
    """Add exact retained task metadata and hashed request/receipt identities to the independent domain observation."""
    result = planning_observe(host)
    with closing(sqlite3.connect(host / 'source.db')) as db:
        db.row_factory = sqlite3.Row
        result['task_records'] = [dict(row) for row in db.execute('SELECT id,project_id,epic_id,milestone_id,title,description,type,status,priority,estimated_complexity,created_by FROM tasks ORDER BY id')]
        result['owner_commands'] = [dict(project_id=row['project_id'],operation_key=row['operation_key'],kind=row['kind'],resource_id=row['resource_id'],request_sha256=hashlib.sha256(row['request_json'].encode()).hexdigest(),response_sha256=hashlib.sha256(row['response_json'].encode()).hexdigest()) for row in db.execute('SELECT * FROM owner_planning_commands ORDER BY project_id,operation_key')]
        result['events'] = db.execute('SELECT count(*) FROM events_log').fetchone()[0]
    return result


def main():
    """Own the installed host/browser through closure and verify one committed creation despite three deliveries."""
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
    token = output / 'synthetic-account.json'
    with token.open('x') as stream:
        os.chmod(token,0o600)
        json.dump({'auth_mode':'chatgpt','tokens':{'access_token':'synthetic.header.signature','account_id':'synthetic-task-creation'}},stream)
    assets.update(token_file=str(token),static_dir=str(ROOT/'frontend/dist'))
    assets.pop('storage',None)
    host = output/'host'
    initialize_host(host,witness_dir=output/'witness',assets=assets)
    fixture = output/'fixture.json'
    ids = seed(host)
    fixture.write_text(json.dumps(ids,indent=2)+'\n')
    before = observe(host)
    assert not before['runs'] and before['dispatches'] == before['native_starts'] == 0
    result = {'status':'running','model_turns':0,'synthetic_project_data':True,'before':before,'backend':str(Path(backend.__file__).resolve()),'web_index_sha256':hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()}
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
            browser = subprocess.run([str(args.node.resolve(strict=True)),'tests/task-creation.e2e.mjs'],cwd=ROOT/'frontend',env=env,stdout=browser_log,stderr=subprocess.STDOUT,check=False,timeout=180)
        result['browser_exit'] = browser.returncode
        assert browser.returncode == 0, 'Inspect original browser log'
        evidence = json.loads((output/'browser/evidence.json').read_text())
        created = evidence['committed'][0]['id']
        after = observe(host)
        assert after['events'] == before['events']+1
        assert [row for row in after['task_records'] if row['id']!=created] == before['task_records']
        new = next(row for row in after['task_records'] if row['id']==created)
        assert new['project_id']==101 and new['epic_id']==ids['group'] and new['milestone_id']==ids['milestone']
        assert new['estimated_complexity']=='high' and new['priority']==1 and new['type']=='documentation' and new['status']=='backlog'
        assert len(after['tasks']) == len(before['tasks'])+1
        assert [row for row in after['dependencies'] if row['task_id']!=created] == before['dependencies']
        assert [row for row in after['dependencies'] if row['task_id']==created] == [{'task_id':created,'depends_on_task_id':ids['input']}]
        assert [row for row in after['owner_commands'] if row['resource_id']!=created or row['kind']!='task.create'] == before['owner_commands']
        assert len(after['owner_commands']) == len(before['owner_commands'])+1
        assert all(after[key]==before[key] for key in ('groups','milestones','runs','peers','dispatches','native_starts','integrity','foreign_keys'))
        result.update(status='passed',created_task_id=created)
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        if process is not None:
            result['service_exit'] = stop(process,log)
        result['after'] = observe(host)
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'receipt':str(output/'result.json')}),flush=True)


if __name__=='__main__':
    main()

"""Verify one installed advisory task-note effect through reply loss, reload and exact receipt recovery."""

from contextlib import closing
import hashlib
import json

from installed_page import run_page


def seed(host):
    """Create manual tasks in isolated projects without admissions, native turn identities or copied authority."""
    from backend.db.connection import connect
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.runtime.sqlite_runs import SQLiteRunStore

    with closing(connect(host/'source.db')) as db, db:
        db.execute("INSERT INTO projects(id,name,description) VALUES(101,'Cuaderno de datos','Relacionar entradas y salidas con un ejemplo explícito.'),(202,'Proyecto separado','Otro ámbito.')")
    records = OwnerPlanningRecords(SQLiteRunStore(host/'source.db'))
    task = records.create_task(project_id=101, title='Documentar entradas y salidas', type='research', description='Antes de programar, explicar para qué sirve la exportación, qué datos entran y qué columnas salen. El ejemplo no es una medición real.', operation_key='fixture-task')
    other = records.create_task(project_id=202, title='Tarea de otro proyecto', type='research', operation_key='fixture-foreign')
    return {'alpha':101,'beta':202,'task':task['id'],'foreign':other['id']}


def observe(host):
    """Retain original task/context/run/peer/grant state separately from the sole advisory-note append."""
    from backend.db.connection import connect

    with closing(connect(host/'source.db')) as db:
        names=('projects','tasks','task_dependencies','task_contexts','runtime_runs','runtime_attempts','runtime_peers','tool_grants','events_log','runtime_inference_dispatches')
        hashes={name:hashlib.sha256(json.dumps(sorted([dict(row)for row in db.execute(f'SELECT * FROM {name}')],key=lambda row:json.dumps(row,sort_keys=True,default=str)),sort_keys=True,default=str).encode()).hexdigest()for name in names}
        return {'table_sha256':hashes,'notes':[dict(row)for row in db.execute('SELECT id,task_id,author,comment_type,content,metadata_json FROM task_comments ORDER BY id')],'runs':db.execute('SELECT count(*) FROM runtime_runs').fetchone()[0],'dispatches':db.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0],'peers':db.execute('SELECT count(*) FROM runtime_peers').fetchone()[0],'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':[tuple(row)for row in db.execute('PRAGMA foreign_key_check')]}


def verify(ids,before,after,evidence):
    """Two identical HTTP201 receipts correspond to one advisory row and zero changed work/context authority."""
    assert before['table_sha256']==after['table_sha256'] and not before['notes']
    assert after['runs']==after['dispatches']==after['peers']==0 and after['integrity']=='ok' and not after['foreign_keys']
    assert len(after['notes'])==1 and after['notes'][0]['task_id']==ids['task']
    assert len(evidence['comments'])==2 and evidence['comments'][0]==evidence['comments'][1]
    original=json.loads(after['notes'][0]['metadata_json'])['owner_comment']
    assert original['receipt']==evidence['comments'][0]['receipt']
    assert original['operation_key']==evidence['comments'][0]['body']['operation_key']


if __name__=='__main__':run_page(seed,observe,verify,'tests/task-comment.e2e.mjs',__doc__)

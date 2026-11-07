"""Observe original private-attempt closure without retiring another owner or treating copied database rows as kernel evidence."""

from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.contracts import RunConflict
from backend.runtime.peer_registry import PeerRegistry


def require_available(conn, project_id, attempt_id):
    """Reject new use of quarantined bytes within the caller's existing admission/read transaction; historical metadata remains readable."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_retention'").fetchone():
        return  # Offline supported-prefix migration fixtures; serving readiness requires the complete current schema.
    if conn.execute('SELECT 1 FROM workspace_retention WHERE project_id=? AND attempt_id=?',(project_id,attempt_id)).fetchone():
        raise RunConflict('Esta copia está en cuarentena. Recupera sus archivos como una fuente nueva; no se reutiliza su autorización anterior.')


def observed_closure(authority, store, conn, row):
    """Require witnessed retired grants and closed operations for this database/attempt/fence, including historical attempts; absence is not proof."""
    origin = PeerRegistry(store)._database_identity()
    expected = (origin,row['project_id'],row['task_id'],row['attempt_id'],row['fence'])
    grants = []
    with WitnessedAuthorityJournal(**authority) as journal:
        snapshot=journal.load()
        for key,value in snapshot.records.items():
            if key.startswith('broker:grant:') and (value.get('database_identity'),value.get('project_id'),value.get('task_id'))==expected[:3] and (value.get('state')!='retired' or value.get('domain_removed') is not True):
                raise RunConflict('El cierre físico de un consumidor de esta tarea todavía no está comprobado.')
        for key,value in snapshot.records.items():
            if not key.startswith('broker:grant:') or value.get('attempt_id')!=row['attempt_id']:
                continue
            actual=tuple(value.get(name) for name in ('database_identity','project_id','task_id','attempt_id','fence'))
            if actual!=expected or value.get('state')!='retired' or value.get('domain_removed') is not True:
                raise RunConflict('El cierre físico del intento original no está comprobado. Conserva sus archivos y resuelve primero su ejecución.')
            grants.append(key.removeprefix('broker:grant:'))
        if not grants:
            raise RunConflict('No hay un testigo local del cierre original. La copia se conserva; una restauración no hereda ese permiso.')
        operations=[value for key,value in snapshot.records.items() if key.startswith('broker:op:') and value.get('grant_id') in grants]
        for value in operations:
            if value.get('execution_closed') is not True:
                raise RunConflict('Una operación original aún no tiene cierre físico confirmado.')
    witnessed={operation.get('peer_id') for operation in operations}
    peers=conn.execute('SELECT * FROM runtime_peers WHERE attempt_id=?',(row['attempt_id'],)).fetchall()
    if any(peer['state']!='closed' or peer['database_identity']!=origin or peer['fence']!=row['fence'] or (peer['init_pid'] is not None and peer['id'] not in witnessed) for peer in peers):
        raise RunConflict('Los procesos registrados no coinciden con el cierre original.')
    return {'database_identity':origin,'attempt_id':row['attempt_id'],'fence':row['fence'],'grant_ids':grants,'execution_closed':True}

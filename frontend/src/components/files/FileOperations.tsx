/** Owner recovery of interrupted attachments without background mutation or inferred completion. @module */
import { useState } from 'react'
import { useFileOperations, useRecoverFileOperation } from '../../hooks/useFiles'
import type { FileOperation } from '../../hooks/useFiles'
import { reportTimestamp } from '../reports/presentation'

const labels: Record<FileOperation['state'], string> = { pending: 'Pendiente de comprobar', published: 'Carga registrada', deleted: 'Borrado confirmado', abandoned: 'Intento cerrado; restos conservados' }

/** Keep pending recovery visible and confirmed history optional so the current archive remains the primary task. */
export function FileOperations({ projectId }: { projectId: number }) {
  const history = useFileOperations(projectId)
  const recovery = useRecoverFileOperation(projectId)
  const [notice, setNotice] = useState(''), [showHistory, setShowHistory] = useState(false)
  const rows = [...new Map((history.data?.pages.flat() ?? []).map(row => [row.operation_key, row])).values()]
  const visibleRows = showHistory ? rows : rows.filter(row => row.state === 'pending')
  const listId = `file-operation-rows-${projectId}`
  /** Recover one original intent; no replacement upload or automatic retry is admitted here. */
  const act = (row: FileOperation, action: 'reconcile' | 'abandon') => {
    setNotice('')
    recovery.mutate({ operationKey: row.operation_key, action }, { onSuccess: result => setNotice(`${row.filename}: ${labels[result.state]}.`) })
  }
  return <section className="files-operations" aria-labelledby="file-operations-title">
    <header><div><h2 id="file-operations-title">Cargas y borrados</h2><p>Si se interrumpió una operación, comprueba aquí su resultado antes de crear otra.</p></div><button disabled={history.isFetching} onClick={() => history.refetch()}>Actualizar historial</button></header>
    {history.isPending && <p role="status">Consultando operaciones…</p>}
    {history.isError && <p role="alert">No se pudo consultar el historial. Actualízalo para comprobar las operaciones.</p>}
    {rows.length > 0 && <><p className="files-muted">Los resultados son históricos. La lista de adjuntos indica cuáles siguen disponibles.</p>{(rows.some(row => row.state !== 'pending') || history.hasNextPage) && <button aria-expanded={showHistory} aria-controls={listId} onClick={() => setShowHistory(value => !value)}>{showHistory ? 'Ocultar historial confirmado' : 'Ver historial de cargas y borrados'}</button>}<ul id={listId}>{visibleRows.map(row => <li key={row.operation_key}>
      <div><strong>{row.filename}</strong><span>{row.kind === 'upload' ? 'Carga' : 'Borrado'} · {reportTimestamp(row.created_at).label}</span></div><p>{labels[row.state]}</p>
      {row.state === 'pending' && <div className="files-operation-actions"><p>{row.kind === 'upload' ? 'Se publicará sólo si se conserva el archivo completo de este intento. Si quedó incompleto, puedes cerrar el intento; sus restos se conservarán sin aparecer como adjunto.' : 'El adjunto ya salió de la lista. Se comprobará el borrado del archivo original; si cambió o no se puede verificar, se conservará para revisión.'}</p><button disabled={recovery.isPending} onClick={() => act(row, 'reconcile')}>Comprobar y recuperar</button>{row.kind === 'upload' && <button disabled={recovery.isPending} onClick={() => act(row, 'abandon')}>Cerrar intento y conservar restos</button>}</div>}
    </li>)}</ul></>}
    {!history.isPending && !history.isError && rows.length === 0 && <p className="files-muted">Todavía no hay operaciones registradas.</p>}
    {showHistory && history.hasNextPage && <button disabled={history.isFetchingNextPage} onClick={() => history.fetchNextPage()}>Ver operaciones anteriores</button>}
    {recovery.isError && <p className="files-error" role="alert">No se pudo confirmar la operación. {recovery.error.message} Su historial se conserva.</p>}
    {notice && <p role="status">{notice}</p>}
  </section>
}

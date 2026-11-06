/** Paginated project questions retain original task/context links and explicit reply readiness. @module */
import { useQuestionInbox } from '../../hooks/useRuntime'
import type { Task } from '../../types/api'

/** Render native and legacy requests without treating an unread page or failed query as an empty inbox. */
export function QuestionInbox({ projectId, tasks, onChoose }: { projectId: number; tasks: Task[]; onChoose: (taskId: number, questionId?: number) => void }) {
  const query = useQuestionInbox(projectId)
  const items = [...new Map(query.data?.pages.flatMap(page => page.items).map(item => [item.request_id, item]) ?? []).values()]
  const total = query.data?.pages[0]?.total_pending
  return <section className="conversation-inbox" aria-labelledby="conversation-pending-title">
    <h2 id="conversation-pending-title">Preguntas pendientes</h2>
    {query.isPending && <p role="status">Consultando solicitudes…</p>}
    {query.error && <div role="alert"><p>No se pudieron recuperar las preguntas.</p><button onClick={() => query.refetch()}>Volver a consultar</button></div>}
    {total != null && <p className="conversation-count">{total} {total === 1 ? 'solicitud pendiente' : 'solicitudes pendientes'}</p>}
    {items.length === 0 && query.isSuccess && <p>No hay preguntas pendientes en este proyecto.</p>}
    <ul>{items.map(item => <li key={item.request_id} data-request-id={item.request_id}>
      {item.kind === 'native' && item.task_id != null ? <button disabled={!tasks.some(task => task.id === item.task_id)} onClick={() => onChoose(item.task_id!, item.request_id)}>
        <span className="conversation-meta">Tarea #{item.task_id} · contexto {item.context_version}</span>
        <strong>{item.questions?.[0]?.question ?? item.title}</strong>
        <span>{item.ready_for_answer ? 'Lista para responder' : item.current_context_version !== item.context_version ? 'Requiere revisar el contexto' : 'Confirmando la parada antes de responder'}</span>
      </button> : <details><summary>{item.title || 'Solicitud anterior'}</summary><p>{item.body}</p><p>Solicitud del motor anterior. No tiene un vínculo comprobado con una tarea y versión del nuevo motor.</p></details>}
    </li>)}</ul>
    {query.hasNextPage && <button disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>{query.isFetchingNextPage ? 'Consultando…' : 'Ver más pendientes'}</button>}
  </section>
}

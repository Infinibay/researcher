import type { Task } from '../../types/api'

export const taskStatusLabels: Record<string, string> = {
  backlog: 'Por planificar', pending: 'Pendiente', in_progress: 'En curso',
  review_ready: 'Para revisar', rejected: 'Requiere cambios', done: 'Completada', blocked: 'Bloqueada',
}

export function TaskQueue({ tasks, selectedTaskId, onSelect, onDelete }: {
  tasks: Task[]; selectedTaskId: number | null; onSelect: (id: number) => void; onDelete: (id: number) => void
}) {
  return <ul className="task-queue" aria-label="Lista de tareas">
    {tasks.map(task => <li key={task.id} className="task-queue-row" data-selected={selectedTaskId === task.id}>
      <button id={`task-select-${task.id}`} className="task-select" type="button" aria-current={selectedTaskId === task.id ? 'true' : undefined} aria-controls="task-detail" onClick={() => onSelect(task.id)}>
        <span className="task-queue-meta"><span>#{task.id}</span><span className="task-status" data-status={task.status}>{taskStatusLabels[task.status] ?? task.status}</span></span>
        <span className="task-queue-title">{task.title}</span>
        <span className="task-queue-meta"><span>{task.type === 'research' ? 'Investigación' : task.type}</span>{task.priority != null && <span>Prioridad {task.priority}</span>}</span>
        {task.assigned_to && <span className="task-queue-assignee">{task.assigned_to}</span>}
      </button>
      {['backlog', 'pending'].includes(task.status) && <button type="button" className="task-delete" aria-label={`Eliminar tarea #${task.id}: ${task.title}`} onClick={() => onDelete(task.id)}>Eliminar</button>}
    </li>)}
  </ul>
}

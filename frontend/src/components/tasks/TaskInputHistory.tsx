import type { TaskInputChange } from '../../api/runtime'

const fieldLabels: Record<string, string> = {
  title: 'Título', description: 'Descripción', type: 'Tipo',
  acceptance_criteria: 'Criterios de aceptación', context_json: 'Contexto de la tarea',
  priority: 'Prioridad', estimated_complexity: 'Complejidad estimada',
  branch_name: 'Rama', assigned_to: 'Responsable', reviewer: 'Revisor',
  epic_id: 'Épica', milestone_id: 'Hito', parent_task_id: 'Tarea principal',
}

export function TaskInputHistory({ changes }: { changes: TaskInputChange[] }) {
  if (!changes.length) return null
  return <details className="space-y-2 rounded-md border border-[var(--work-line)] p-3">
    <summary className="cursor-pointer font-medium text-[var(--work-ink)]">Cambios de la tarea · {changes.length}</summary>
    <p className="mt-2 text-[var(--work-muted)]">Cada edición invalida el contexto anterior. Si había una ejecución activa, su parada debe confirmarse antes de empezar otra. No se inicia trabajo automáticamente.</p>
    {changes.map(change => <section key={change.version} className="mt-3 border-t border-[var(--work-line)] pt-2" aria-label={`Edición bajo contexto ${change.version}`}>
      <p className="text-xs text-[var(--work-muted)]">Contexto {change.version} · Edición de tarea · Autor no registrado</p>
      <dl className="mt-2 space-y-3">{Object.entries(change.changes).map(([field, values]) => <div key={field}>
        <dt className="font-medium text-[var(--work-ink)]">{fieldLabels[field] ?? field}</dt>
        <dd className="mt-1 text-[var(--work-muted)]">Antes: <span className="whitespace-pre-wrap break-words">{values.before ?? 'Sin valor'}</span></dd>
        <dd className="mt-1 text-[var(--work-ink)]">Después: <span className="whitespace-pre-wrap break-words">{values.after ?? 'Sin valor'}</span></dd>
      </div>)}</dl>
    </section>)}
  </details>
}

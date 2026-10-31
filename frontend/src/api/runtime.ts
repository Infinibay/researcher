import { fetchApi } from './client.ts'

export interface RuntimeRun {
  run_id: string
  project_id: number
  task_id: number
  context_version: number
  operation_key: string
  conversation_thread_id: string | null
  status: string
  prompt: string
  result: { native_status: string; summary: string } | null
  cancel_requested: boolean
  model: string | null
}

export interface TaskWorkspace {
  context: {
    task: { title: string; description: string | null; type: string; status: string }
    context_version: number
    corrections: { version: number; statement: string; source_kind: string; source_reference: string }[]
  }
  runs: RuntimeRun[]
  repositories: { id: number; name: string; default_branch: string | null }[]
  references: { id: number; file_name: string; file_type: string | null }[]
  sources: { id: number; title: string; kind: string; sha256: string; captured_at: number; captured_for_task_id: number }[]
  reports: { id: number; title: string; status: string; created_at: string }[]
  runtime: { configured: boolean; supported_task_types: string[]; model: string | null }
}

export interface InstructionDraft {
  task_id: number
  context_version: number
  thread_id: string
  message: string
  repository_id?: number
}
export interface InstructionIntent {
  readonly projectId: number
  readonly body: Readonly<InstructionDraft & { operation_key: string }>
}

export function prepareInstruction(projectId: number, draft: InstructionDraft): InstructionIntent {
  if (![projectId, draft.task_id, draft.context_version].every(x => Number.isSafeInteger(x) && x > 0)
    || !/^[A-Za-z0-9_.:-]{1,128}$/.test(draft.thread_id)
    || !draft.message.trim() || draft.message.length > 50000
    || (draft.repository_id != null && (!Number.isSafeInteger(draft.repository_id) || draft.repository_id <= 0))) {
    throw new Error('Revisa la tarea, el contexto y el contenido de la solicitud.')
  }
  return Object.freeze({ projectId, body: Object.freeze({ ...draft, operation_key: crypto.randomUUID() }) })
}

export function sendInstruction(intent: InstructionIntent) {
  return fetchApi<{ run: RuntimeRun; message: { id: number; thread_id: string } }>(`/api/chat/${intent.projectId}/instructions`, {
    method: 'POST', body: JSON.stringify(intent.body),
  })
}

export function taskWorkspace(projectId: number, taskId: number) {
  return fetchApi<TaskWorkspace>(`/api/projects/${projectId}/tasks/${taskId}/workspace`)
}

export function stopRun(projectId: number, runId: string) {
  return fetchApi<RuntimeRun>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/stop`, { method: 'POST' })
}

export function recordCorrection(projectId: number, taskId: number, body: {
  operation_key: string; expected_version: number; statement: string; source_kind: 'user_message' | 'user_example'
}) {
  return fetchApi<{ context_version: number; application: string; inference_started: boolean }>(
    `/api/projects/${projectId}/tasks/${taskId}/context-corrections`, { method: 'POST', body: JSON.stringify(body) },
  )
}

export function sourceWindow(projectId: number, sourceId: number, offset = 0) {
  return fetchApi<{ source_id: number; title: string; sha256: string; captured_at: number;
    content: string; offset: number; next_offset: number | null; total_chars: number }>(
    `/api/projects/${projectId}/research-sources/${sourceId}?offset=${offset}&max_chars=12000`,
  )
}

export function presentRun(status: string | null) {
  switch (status) {
    case null: return { title: 'Sin ejecución', description: 'Prepara una solicitud para esta tarea.', canStart: true }
    case 'queued': return { title: 'Solicitud registrada', description: 'El trabajo todavía no comenzó.', canStart: false }
    case 'running': return { title: 'En curso', description: 'Puedes detener el trabajo o registrar una corrección.', canStart: false }
    case 'cancelling': return { title: 'Detención solicitada', description: 'Falta confirmar que terminó la ejecución.', canStart: false }
    case 'reconciling': return { title: 'Requiere comprobación', description: 'No se conocen todos los efectos. La ejecución no se repetirá automáticamente.', canStart: false }
    case 'needs_review': return { title: 'Propuesta para revisar', description: 'El resultado está disponible; falta registrar su aceptación.', canStart: false }
    case 'cancelled': return { title: 'Ejecución detenida', description: 'La detención fue confirmada. Las fuentes y borradores guardados se conservan.', canStart: true }
    case 'superseded': return { title: 'Contexto anterior', description: 'Hay una corrección registrada para la próxima ejecución.', canStart: true }
    case 'failed': return { title: 'Ejecución fallida', description: 'No se aceptó la tarea. Revisa lo ocurrido antes de enviar una nueva solicitud.', canStart: true }
    case 'accepted': return { title: 'Resultado aceptado', description: 'La aceptación quedó registrada.', canStart: false }
    default: return { title: 'Estado por comprobar', description: 'Actualiza el estado antes de enviar más trabajo.', canStart: false }
  }
}

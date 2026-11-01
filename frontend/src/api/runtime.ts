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
  questions: RuntimeQuestion[]
  runtime: { configured: boolean; supported_task_types: string[]; model: string | null }
}

export interface RuntimeQuestion {
  request_id: number
  run_id: string
  context_version: number
  questions: { id: string; question: string; why_needed: string; options: string[]; example: string }[]
  status: 'pending' | 'responded' | 'expired'
  answers: Record<string, string> | null
  answer_context_version: number | null
  ready_for_answer: boolean
}

export interface AnswerIntent {
  readonly projectId: number
  readonly taskId: number
  readonly questionId: number
  readonly body: Readonly<{ operation_key: string; expected_version: number; answers: Readonly<Record<string, string>> }>
}

export interface RecoveryInspection {
  run_id: string
  attempt_id: string | null
  fence: number
  status: string
  supported: boolean
  can_reconcile: boolean
  blocked_reason: 'missing_proof' | 'different_database' | 'different_kernel' | 'unknown_job' | null
  peers: { kind: string; state: string; reason: string | null }[]
  unknown_jobs: number
  jobs: { id: string; status: string; exit_code: number | null; output_limited: number; local_execution_closed: number }[]
  jobs_truncated: boolean
  dispatch: { model: string | null; status: string; observed_tokens: number | null; token_ceiling: number } | null
  effects: { operation_key: string; kind: string; receipt: Record<string, unknown> }[]
  effects_truncated: boolean
}

export interface RecoveryIntent {
  readonly projectId: number
  readonly taskId: number
  readonly runId: string
  readonly body: Readonly<{ operation_key: string; attempt_id: string; expected_fence: number }>
}

export function prepareRecovery(projectId: number, taskId: number, runId: string, attemptId: string, fence: number): RecoveryIntent {
  if (![projectId, taskId, fence].every(x => Number.isSafeInteger(x) && x > 0)
    || !/^[A-Za-z0-9_.:-]{1,128}$/.test(runId) || !attemptId || attemptId.length > 128) {
    throw new Error('Consulta de nuevo la ejecución antes de comprobar su cierre.')
  }
  return Object.freeze({ projectId, taskId, runId, body: Object.freeze({
    operation_key: crypto.randomUUID(), attempt_id: attemptId, expected_fence: fence,
  }) })
}

export function recoveryInspection(projectId: number, runId: string) {
  return fetchApi<RecoveryInspection>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/recovery`)
}

export function sendRecovery(intent: RecoveryIntent) {
  return fetchApi<{ status: string; local_execution_closed: true; inference_started: false; task_accepted: false }>(
    `/api/projects/${intent.projectId}/runs/${encodeURIComponent(intent.runId)}/recovery`,
    { method: 'POST', body: JSON.stringify(intent.body) },
  )
}

export function prepareAnswer(projectId: number, taskId: number, questionId: number, expectedVersion: number, answers: Record<string, string>): AnswerIntent {
  if (![projectId, taskId, questionId, expectedVersion].every(x => Number.isSafeInteger(x) && x > 0)
    || Object.keys(answers).length < 1 || Object.keys(answers).length > 3
    || Object.values(answers).some(value => !value.trim())
    || new TextEncoder().encode(JSON.stringify(answers)).length > 12000) {
    throw new Error('Responde las preguntas dentro del límite de 12.000 bytes.')
  }
  return Object.freeze({ projectId, taskId, questionId, body: Object.freeze({
    operation_key: crypto.randomUUID(), expected_version: expectedVersion, answers: Object.freeze({ ...answers }),
  }) })
}

export function sendAnswer(intent: AnswerIntent) {
  return fetchApi<{ context_version: number; application: string; inference_started: false }>(
    `/api/projects/${intent.projectId}/tasks/${intent.taskId}/questions/${intent.questionId}/answers`,
    { method: 'POST', body: JSON.stringify(intent.body) },
  )
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
    case 'waiting_input': return { title: 'Esperando tu respuesta', description: 'El trabajo está pausado y el agente ya no puede actuar en el proyecto. Tu respuesta se guardará para la próxima ejecución.', canStart: false }
    case 'needs_review': return { title: 'Propuesta para revisar', description: 'El resultado está disponible; falta registrar su aceptación.', canStart: false }
    case 'cancelled': return { title: 'Ejecución detenida', description: 'La detención fue confirmada. Las fuentes y borradores guardados se conservan.', canStart: true }
    case 'superseded': return { title: 'Contexto anterior', description: 'Hay una corrección registrada para la próxima ejecución.', canStart: true }
    case 'failed': return { title: 'Ejecución fallida', description: 'No se aceptó la tarea. Revisa lo ocurrido antes de enviar una nueva solicitud.', canStart: true }
    case 'accepted': return { title: 'Resultado aceptado', description: 'La aceptación quedó registrada.', canStart: false }
    default: return { title: 'Estado por comprobar', description: 'Actualiza el estado antes de enviar más trabajo.', canStart: false }
  }
}

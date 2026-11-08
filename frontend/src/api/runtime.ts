/** Scoped owner runtime reads and explicit durable execution controls. @module */
import { fetchApi } from './client.ts'

/** Durable runtime observation distinguishes a frozen requested pair from the model actually bound to inference. */
export interface RuntimeRun {
  execution_kind: 'research' | 'finding_review' | 'development' | 'code_review' | 'code_publication' | 'remote_publication'
  run_id: string
  project_id: number
  task_id: number
  actor_id?:string
  context_version: number
  operation_key: string
  conversation_thread_id: string | null
  status: string
  prompt: string
  result: { native_status: string; summary: string } | null
  cancel_requested: boolean
  model: string | null
  model_selection?:{model:string;reasoning_effort:string;source:string;revision:number;attempt_id:string;fence:number}|null
  fence: number
  attempt_id?: string | null
  repository_id: number | null
  repository_name: string | null
  issue: { code: string; message: string; next_action: string; inference_started: boolean | null } | null
}

/** Literal JSON metadata may include structured project context; it is data rather than a renderable React child. */
export type TaskInputValue = string | number | boolean | null | TaskInputValue[] | {[key:string]:TaskInputValue}

/** Observed metadata edits retain literal before/after data and unknown recorded authorship. */
export interface TaskInputChange {
  version: number
  source_kind: 'task_metadata'
  actor: null
  changes: Record<string, { before: TaskInputValue; after: TaskInputValue }>
}

/** Registered task inputs, owner controls and their explicit project/task scope. */
export interface TaskWorkspace {
  project_id: number
  task_id: number
  context: {
    task: { title: string; description: string | null; type: string; status: string }
    context_version: number
    corrections: { version: number; statement: string; source_kind: string; source_reference: string }[]
    task_changes: TaskInputChange[]
  }
  runs: RuntimeRun[]
  repositories: { id: number; name: string; default_branch: string | null }[]
  references: { id: number; file_name: string; file_type: string | null }[]
  sources: { id: number; title: string; kind: string; sha256: string; captured_at: number; captured_for_task_id: number }[]
  reports: { id: number; title: string; status: string; created_at: string }[]
  questions: RuntimeQuestion[]
  runtime: { configured: boolean; supported_task_types: string[]; development_task_types?: string[]; owner_controlled_task_types?: string[]; model: string | null; remote_publication?: boolean }
}

/** Keep explicit selections distinct from arbitrary user text, including text that happens to match an option ID. */
export type QuestionAnswer = string | Readonly<{ option_id: string }>

export interface RuntimeQuestion {
  request_id: number
  run_id: string
  context_version: number
  questions: { id: string; question: string; why_needed: string; options: (string | { id: string; label: string })[]; example: string }[]
  status: 'pending' | 'responded' | 'expired'
  answers: Record<string, QuestionAnswer> | null
  answer_context_version: number | null
  ready_for_answer: boolean
}

export interface QuestionInboxItem {
  request_id: number
  kind: 'native' | 'legacy'
  title: string
  body: string | null
  task_id: number | null
  task_title: string | null
  task_priority: number | null
  run_id: string | null
  thread_id: string | null
  context_version: number | null
  current_context_version: number | null
  ready_for_answer: boolean
  questions: RuntimeQuestion['questions'] | null
}

export interface QuestionInboxPage {
  items: QuestionInboxItem[]
  total_pending: number
  next_after_id: number | null
}

export type RunInputRecord = { available: false; reason: string; attempt_id: string | null } | {
  available: true
  input_text: string
  input_sha256: string
  developer_instructions: string
  instructions_sha256: string
  business_catalog: unknown[]
  native_start_observed: boolean
  model: string | null
}

export function runInput(projectId: number, runId: string) {
  return fetchApi<RunInputRecord>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/input`)
}

export interface CommandSummary {
  job_id: string
  seq: string
  run_id: string
  attempt_id: string
  context_version: number
  is_current_attempt: boolean
  operation_key: string
  status: string
  exit_code: number | null
  local_execution_closed: boolean
  cancel_requested: boolean
  output_limited: boolean
  error: string | null
  executable: string
  cwd: string
  timeout_seconds: number
  output_bytes: number
  stdout_bytes: number
  stderr_bytes: number
  output_persistence: 'terminal_receipt'
}

export interface CommandWindow {
  offset: number
  next_offset: number
  total_bytes: number
  has_more: boolean
  base64: string
  text: string
  utf8_lossy: boolean
}

export interface CommandOutput extends CommandSummary {
  argv: string[]
  stdout: CommandWindow
  stderr: CommandWindow
}

export interface CommandPage {
  run_id: string
  total: number
  next_after_seq: string | null
  items: CommandSummary[]
}

export function commandList(projectId: number, runId: string, afterSeq = '0') {
  return fetchApi<CommandPage>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/jobs?after_seq=${encodeURIComponent(afterSeq)}&limit=25`)
}

export function commandOutput(projectId: number, runId: string, jobId: string, {stdoutOffset = 0, stderrOffset = 0, maxBytes = 8192} = {}) {
  const params = new URLSearchParams({stdout_offset:String(stdoutOffset),stderr_offset:String(stderrOffset),max_bytes:String(maxBytes)})
  return fetchApi<CommandOutput>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/jobs/${encodeURIComponent(jobId)}?${params}`)
}

export function questionInbox(projectId: number, afterId = 0) {
  return fetchApi<QuestionInboxPage>(`/api/projects/${projectId}/questions?after_id=${afterId}&limit=50`)
}

export interface AnswerIntent {
  readonly projectId: number
  readonly taskId: number
  readonly questionId: number
  readonly body: Readonly<{ operation_key: string; expected_version: number; answers: Readonly<Record<string, QuestionAnswer>> }>
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

/** Freeze the exact observed answer packet, including nested selections, before a possibly uncertain HTTP write. */
export function prepareAnswer(projectId: number, taskId: number, questionId: number, expectedVersion: number, answers: Record<string, QuestionAnswer>): AnswerIntent {
  if (![projectId, taskId, questionId, expectedVersion].every(x => Number.isSafeInteger(x) && x > 0)
    || Object.keys(answers).length < 1 || Object.keys(answers).length > 3
    || Object.values(answers).some(value => typeof value === 'string' ? !value.trim()
      : !value || Object.keys(value).length !== 1 || !Object.prototype.hasOwnProperty.call(value, 'option_id') || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value.option_id))
    || new TextEncoder().encode(JSON.stringify(answers)).length > 12000) {
    throw new Error('Responde las preguntas dentro del límite de 12.000 bytes.')
  }
  return Object.freeze({ projectId, taskId, questionId, body: Object.freeze({
    operation_key: crypto.randomUUID(), expected_version: expectedVersion,
    answers: Object.freeze(Object.fromEntries(Object.entries(answers).map(([key, value]) => [key, typeof value === 'string' ? value : Object.freeze({ option_id: value.option_id })]))),
  }) })
}

export function sendAnswer(intent: AnswerIntent) {
  return fetchApi<{ context_version: number; application: string; inference_started: false }>(
    `/api/projects/${intent.projectId}/tasks/${intent.taskId}/questions/${intent.questionId}/answers`,
    { method: 'POST', body: JSON.stringify(intent.body) },
  )
}

/** Exact prior candidate observation; selected bytes remain data under fresh authority. */
export interface PriorCodeSelection {attempt_id:string;snapshot_sha256:string}
/** Owner-chosen paths in a recorded origin, without an asserted native author or Git base. */
export interface PriorFilesSelection {source_kind:'legacy_worktree'|'private_copy';source_id:string;paths:readonly string[];snapshot_sha256:string}
/** Full owner-chosen commit in a recorded branch; this selection is not an observation of captured bytes. */
export interface PriorBranchSelection {source_kind:'legacy_branch';branch_id:number;commit_sha:string}
export type PriorMaterialSelection = PriorCodeSelection | PriorFilesSelection | PriorBranchSelection
/** Historical labels are read-only suggestions; availability and original context remain unverified. */
export interface BranchInputSource {source_kind:'legacy_branch';branch_id:number;repository_id:number;branch:string;recorded_commit_sha:string|null;recorded_task_id:number|null;recorded_status:string;availability:'not_inspected'}
/** List actual branch records inside the selected project, without invoking Git or starting a model. */
export function branchInputSources(projectId:number,taskId:number) {return fetchApi<BranchInputSource[]>(`/api/projects/${projectId}/tasks/${taskId}/prior-branches`)}
export interface FileImportSource {source_kind:'legacy_worktree'|'private_copy';source_id:string;repository_id:number;label:string;recorded_status:string;task_relation:string}
export interface ImportedFile {path:string;kind:'file'|'symlink'|'missing';content_base64?:string;target_base64?:string;git_mode?:string;bytes?:number;sha256?:string}
export interface FileImportPacket {snapshot_sha256:string;snapshot:{origin:{kind:string;recorded_agent_label?:string;recorded_context_version?:number};source:{repository_id:number};original_input:Record<string,unknown>|null;original_input_status:'unknown'|'recorded';selection_scope:'selected_paths_only';files:ImportedFile[]};authority:'data_only';acceptance:'not_granted'}
/** List recorded origins without inferring a task relationship from an agent label. */
export function fileImportSources(projectId:number,taskId:number) {return fetchApi<FileImportSource[]>(`/api/projects/${projectId}/tasks/${taskId}/prior-files/sources`)}
/** Validate explicit bounded paths before preview or freezing the original owner request. */
function checkFileSelection(selection:Omit<PriorFilesSelection,'snapshot_sha256'>) {
  if(!['legacy_worktree','private_copy'].includes(selection.source_kind)||!/^[A-Za-z0-9_.:-]{1,128}$/.test(selection.source_id)||selection.source_kind==='legacy_worktree'&&!/^[1-9][0-9]*$/.test(selection.source_id)||!Array.isArray(selection.paths)||selection.paths.length<1||selection.paths.length>128||new Set(selection.paths).size!==selection.paths.length||selection.paths.some(path=>typeof path!=='string'||!path||new TextEncoder().encode(path).length>4096||path.includes('\0')||path.split('/').length>32||path.split('/').some(part=>['','.','..','.git','.ken','.worktrees'].includes(part)))) throw new Error('Elige un origen registrado y rutas relativas individuales; deja fuera los metadatos de Git y ejecución.')
}
/** Observe selected old bytes; a preview cannot admit, resume, review or accept work. */
export function previewFileImport(projectId:number,taskId:number,body:Omit<PriorFilesSelection,'snapshot_sha256'>&{repository_id:number}) {
  checkFileSelection(body)
  if(![projectId,taskId,body.repository_id].every(value=>Number.isSafeInteger(value)&&value>0))throw new Error('Consulta el proyecto, la tarea y el repositorio antes de importar archivos.')
  return fetchApi<FileImportPacket>(`/api/projects/${projectId}/tasks/${taskId}/prior-files/preview`,{method:'POST',body:JSON.stringify(body)})
}
/** Complete retained original input and patch, without inherited approval. */
export interface PriorCodePacket {
  snapshot_sha256:string
  snapshot:{origin:{run_id:string;attempt_id:string;context_version:number;repository_id:number};candidate:{base_sha:string;head_sha:string;diff_sha256:string};original_input:Record<string,unknown> & {request:string};diff_base64:string;diff_bytes:number}
  authority:'data_only';acceptance:'not_granted';publication:'not_granted'
}
/** Inspect one task's exact earlier native material; this GET cannot resume or accept it. */
export function priorCodeInput(projectId:number,taskId:number,attemptId:string) {
  return fetchApi<PriorCodePacket>(`/api/projects/${projectId}/tasks/${taskId}/prior-code/${encodeURIComponent(attemptId)}`)
}
/** Decode exact UTF-8 patch bytes for display, retaining binary data only in the original download. */
export function priorPatchText(encoded:string):string|null {
  try {return new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(atob(encoded),character=>character.charCodeAt(0)))} catch {return null}
}

/** Owner-selected request fields, distinct from any later native attempt or inferred shared context. */
export interface InstructionDraft {
  task_id: number
  context_version: number
  thread_id: string
  message: string
  repository_id?: number
  prior_code?: Readonly<PriorMaterialSelection>
}
/** Complete immutable delivery identity, including the original task/context/thread and optional material. */
export interface InstructionIntent {
  readonly projectId: number
  readonly body: Readonly<InstructionDraft & { operation_key: string }>
}

/** Freeze the complete original request and prior-code observation so uncertain sends cannot silently change intent. */
function freezeInstruction(projectId: number, draft: InstructionDraft, operationKey: string): InstructionIntent {
  if (![projectId, draft.task_id, draft.context_version].every(x => Number.isSafeInteger(x) && x > 0)
    || typeof draft.thread_id!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(draft.thread_id)
    || typeof operationKey!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(operationKey)
    || typeof draft.message!=='string' || !draft.message.trim() || draft.message.length > 50000
    || (draft.repository_id != null && (!Number.isSafeInteger(draft.repository_id) || draft.repository_id <= 0))
    || (draft.prior_code != null && ('commit_sha' in draft.prior_code ? draft.prior_code.source_kind!=='legacy_branch'||!Number.isSafeInteger(draft.prior_code.branch_id)||draft.prior_code.branch_id<=0||!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(draft.prior_code.commit_sha) : !/^[0-9a-f]{64}$/.test(draft.prior_code.snapshot_sha256)||('attempt_id' in draft.prior_code&&(!draft.prior_code.attempt_id.trim()||draft.prior_code.attempt_id.length>128))))) {
    throw new Error('Revisa la tarea, el contexto y el contenido de la solicitud.')
  }
  if(draft.prior_code&&'paths' in draft.prior_code)checkFileSelection(draft.prior_code)
  const selected=draft.prior_code?Object.freeze({...draft.prior_code,...('paths' in draft.prior_code?{paths:Object.freeze([...draft.prior_code.paths])}:{})}):undefined
  return Object.freeze({ projectId, body: Object.freeze({ ...draft, ...(selected?{prior_code:selected}:{}), operation_key: operationKey }) })
}

/** Capture a new request only when the owner prepares a fresh intent. */
export function prepareInstruction(projectId: number, draft: InstructionDraft): InstructionIntent {
  return freezeInstruction(projectId,draft,crypto.randomUUID())
}

/** Revalidate saved request bytes without generating a replacement key or changing selected prior material. */
export function restoreInstruction(intent: InstructionIntent): InstructionIntent {
  const {operation_key,...draft}=intent.body
  return freezeInstruction(intent.projectId,draft,operation_key)
}

/** Send the captured original body; callers acknowledge only the matching scoped receipt. */
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

export interface StartRetryIntent {
  readonly projectId: number
  readonly taskId: number
  readonly runId: string
  readonly body: Readonly<{ operation_key: string; expected_fence: number; context_version: number }>
}

export function prepareStartRetry(projectId: number, taskId: number, runId: string, fence: number, contextVersion: number): StartRetryIntent {
  if (![projectId, taskId, contextVersion].every(value => Number.isSafeInteger(value) && value > 0)
    || !Number.isSafeInteger(fence) || fence < 0 || !/^[A-Za-z0-9_.:-]{1,128}$/.test(runId)) throw new Error('Consulta la solicitud guardada antes de intentar iniciarla.')
  return Object.freeze({projectId, taskId, runId, body: Object.freeze({operation_key: crypto.randomUUID(), expected_fence: fence, context_version: contextVersion})})
}

export function sendStartRetry(intent: StartRetryIntent) {
  return fetchApi<RuntimeRun>(`/api/projects/${intent.projectId}/runs/${encodeURIComponent(intent.runId)}/retry-start`, {method: 'POST', body: JSON.stringify(intent.body)})
}

export function recordCorrection(projectId: number, taskId: number, body: {
  operation_key: string; expected_version: number; statement: string; source_kind: 'user_message' | 'user_example'
}) {
  return fetchApi<{ context_version: number; application: string; inference_started: boolean }>(
    `/api/projects/${projectId}/tasks/${taskId}/context-corrections`, { method: 'POST', body: JSON.stringify(body) },
  )
}

/** Read saved source text, optionally requiring the exact version named by a review. */
export function sourceWindow(projectId: number, sourceId: number, offset = 0, expectedSha?:string) {
  return fetchApi<{ project_id:number;source_id: number; title: string; locator?:string;sha256: string; captured_at: number;
    content: string; offset: number; next_offset: number | null; total_chars: number }>(
    `/api/projects/${projectId}/research-sources/${sourceId}?offset=${offset}&max_chars=12000${expectedSha?`&expected_sha256=${encodeURIComponent(expectedSha)}`:''}`,
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

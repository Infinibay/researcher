import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { prepareAnswer, prepareInstruction, prepareRecovery, presentRun, recoveryInspection, sourceWindow } from '../../api/runtime'
import type { AnswerIntent, InstructionIntent, RecoveryIntent, RuntimeQuestion } from '../../api/runtime'
import { useAnswer, useCorrection, useInstruction, useRecovery, useStopRun, useTaskWorkspace } from '../../hooks/useRuntime'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

const inputClass = 'w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm text-[var(--work-ink)] focus:outline-none focus:ring-2 focus:ring-[var(--work-accent)]'
const buttonClass = 'rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] hover:bg-[var(--work-wash)] disabled:opacity-50'

function RecoveryCard({ projectId, taskId, runId }: { projectId: number; taskId: number; runId: string }) {
  const details = useQuery({ queryKey: ['run-recovery', projectId, runId], queryFn: () => recoveryInspection(projectId, runId), retry: false, refetchInterval: 2000 })
  const recover = useRecovery()
  const intent = useRef<RecoveryIntent | null>(null)
  const stateLabels: Record<string, string> = { prepared: 'Inicio pendiente', bound: 'Cierre por comprobar', closed: 'Cierre comprobado' }
  const kindLabels: Record<string, string> = { native: 'Ejecución del agente', business: 'Herramientas del proyecto', command: 'Ejecución de comandos' }
  const effectLabels: Record<string, string> = { 'source.capture': 'Fuente capturada', 'finding.record': 'Hallazgo guardado', 'report.write': 'Informe guardado', 'question.ask': 'Pregunta guardada' }
  return <section className="space-y-2 rounded-md border border-amber-700/50 p-3" aria-label="Recuperar ejecución">
    <h4 className="font-medium text-[var(--work-ink)]">Comprobar el cierre</h4>
    <p className="text-[var(--work-muted)]">Revisaremos que esta ejecución ya no pueda actuar. Los borradores y recibos guardados se conservan. Este control no reinicia el trabajo.</p>
    {details.isPending && <p role="status">Consultando las pruebas disponibles…</p>}
    {details.error && <p role="alert">No se pudo consultar la ejecución. {details.error.message}</p>}
    {details.data && <>
      <ul className="space-y-1 text-[var(--work-ink)]">{details.data.peers.map((peer, index) => <li key={`${peer.kind}:${index}`}>{kindLabels[peer.kind] ?? 'Proceso de la ejecución'}: {stateLabels[peer.state] ?? 'Estado desconocido'}</li>)}</ul>
      {!details.data.supported && <p className="text-[var(--work-caution)]">Esta ejecución es anterior al registro de pruebas de cierre. Necesita comprobar el despliegue anterior antes de habilitar nuevo trabajo.</p>}
      {details.data.blocked_reason === 'different_database' && <p className="text-[var(--work-caution)]">Esta base se copió, trasladó o restauró. Hace falta una transferencia comprobada antes de controlar la ejecución de la instalación anterior.</p>}
      {details.data.blocked_reason === 'different_kernel' && <p className="text-[var(--work-caution)]">Cambió el entorno del servidor. No podemos deducir que la ejecución anterior se haya cerrado; hace falta comprobar su instalación de origen.</p>}
      {details.data.unknown_jobs > 0 && <p className="text-[var(--work-caution)]">Hay herramientas cuyo cierre o resultado todavía no se pudo comprobar. Sus efectos siguen pendientes de revisión.</p>}
      {details.data.dispatch && (details.data.dispatch.status === 'unknown' || details.data.dispatch.observed_tokens == null) && <p className="text-[var(--work-muted)]">El consumo final no está confirmado; se conserva el presupuesto reservado.</p>}
      {details.data.effects.length > 0 && <details><summary className="cursor-pointer text-[var(--work-ink)]">Lo que quedó guardado</summary><ul className="mt-2 space-y-1 text-[var(--work-muted)]">{details.data.effects.map(effect => <li key={effect.operation_key}>{effectLabels[effect.kind] ?? 'Operación registrada'}</li>)}</ul>{details.data.effects_truncated && <p className="text-[var(--work-muted)]">Esta vista muestra los primeros 100 recibos.</p>}</details>}
      <button className={buttonClass} disabled={recover.isPending || (!intent.current && !details.data.can_reconcile)} onClick={() => {
        if (!intent.current && details.data!.attempt_id) intent.current = prepareRecovery(projectId, taskId, runId, details.data!.attempt_id, details.data!.fence)
        if (intent.current) recover.mutate(intent.current)
      }}>{recover.isPending ? 'Comprobando y cerrando…' : intent.current ? 'Volver a consultar el mismo control' : 'Comprobar y cerrar ejecución'}</button>
    </>}
    <button className={buttonClass} onClick={() => details.refetch()}>Consultar estado</button>
    {recover.error && <p role="alert" className="text-[var(--work-error)]">No se confirmó el cierre. Volver a consultar conserva el mismo control. {recover.error.message}</p>}
    {recover.isSuccess && <p role="status" className="text-[var(--work-accent)]">Cierre comprobado. No se inició otra ejecución ni se aceptó la tarea.</p>}
  </section>
}

function QuestionCard({ projectId, taskId, question }: { projectId: number; taskId: number; question: RuntimeQuestion }) {
  const answer = useAnswer()
  const [values, setValues] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const intent = useRef<AnswerIntent | null>(null)
  const pending = question.status === 'pending'
  const submit = () => {
    try {
      if (!intent.current) intent.current = prepareAnswer(projectId, taskId, question.request_id, question.context_version, values)
      setError('')
      answer.mutate(intent.current)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Revisa las respuestas.') }
  }
  return <section className="space-y-3 rounded-md border border-[var(--work-line)] p-3" aria-label="Preguntas del agente">
    <h4 className="font-medium text-[var(--work-ink)]">{pending ? 'El agente necesita una aclaración' : question.status === 'responded' ? 'Respuesta registrada' : 'Pregunta del contexto anterior'}</h4>
    <p className="text-xs text-[var(--work-muted)]">Pregunta bajo contexto {question.context_version}{question.answer_context_version ? ` · respuesta guardada en contexto ${question.answer_context_version}` : ''}</p>
    {pending && <p className="text-[var(--work-muted)]">{question.ready_for_answer ? 'La ejecución se cerró. Responde con tus palabras o elige una opción.' : 'Se está comprobando el cierre de la ejecución. La respuesta se habilitará cuando esté confirmado.'}</p>}
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); submit() }}>
      {question.questions.map(item => <fieldset key={item.id} className="space-y-2" disabled={!pending || !question.ready_for_answer || answer.isPending || intent.current != null}>
        <legend className="whitespace-pre-wrap text-[var(--work-ink)]">{item.question}</legend>
        {item.why_needed && <p className="whitespace-pre-wrap text-[var(--work-muted)]">{item.why_needed}</p>}
        {item.example && <p className="whitespace-pre-wrap text-[var(--work-muted)]">Ejemplo: {item.example}</p>}
        {pending ? <>
          {item.options.length > 0 && <div className="flex flex-wrap gap-2">{item.options.map(option => <button type="button" key={option} className={buttonClass} aria-pressed={values[item.id] === option} onClick={() => setValues(previous => ({ ...previous, [item.id]: option }))}>{option}</button>)}</div>}
          <label className="block text-[var(--work-ink)]">Tu respuesta<textarea className={inputClass} rows={2} value={values[item.id] ?? ''} maxLength={12000} onChange={event => setValues(previous => ({ ...previous, [item.id]: event.target.value }))} /></label>
        </> : <p className="whitespace-pre-wrap text-[var(--work-ink)]">{question.answers?.[item.id] ?? 'Esta pregunta perdió vigencia; no se envió una respuesta.'}</p>}
      </fieldset>)}
      {(error || answer.error) && <div role="alert" className="space-y-2 text-[var(--work-error)]"><p>{error || `No se confirmó el guardado. Reenviar conserva las mismas respuestas. ${answer.error?.message}`}</p></div>}
      {pending && <button className={buttonClass} disabled={answer.isPending || (!intent.current && (!question.ready_for_answer || question.questions.some(item => !values[item.id]?.trim())))}>{answer.isPending ? 'Guardando…' : intent.current ? 'Reenviar las mismas respuestas' : 'Guardar respuestas'}</button>}
    </form>
    {(answer.isSuccess || question.status === 'responded') && <p role="status" className="text-[var(--work-accent)]">Respuesta guardada. Inicia trabajo cuando quieras usar el nuevo contexto; responder no inicia otra ejecución.</p>}
  </section>
}

function SourceReader({ projectId, sourceId }: { projectId: number; sourceId: number }) {
  const [offset, setOffset] = useState(0)
  const source = useQuery({ queryKey: ['owner-source', projectId, sourceId, offset], queryFn: () => sourceWindow(projectId, sourceId, offset), retry: false })
  return <section className="mt-3 space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Fuente capturada">
    {source.isPending && <p role="status">Cargando la fuente…</p>}
    {source.error && <p role="alert">No se pudo recuperar la fuente. {source.error.message}</p>}
    {source.data && <>
      <h4 className="text-sm font-medium text-[var(--work-ink)]">{source.data.title}</h4>
      <p className="text-xs text-[var(--work-muted)]">Contenido capturado · caracteres {source.data.offset + 1}–{source.data.next_offset ?? source.data.total_chars} de {source.data.total_chars}</p>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-sm text-[var(--work-ink)]">{source.data.content}</pre>
      <details className="text-xs text-[var(--work-muted)]"><summary>Identidad de la captura</summary><code className="break-all">{source.data.sha256}</code></details>
      <div className="flex gap-2">
        <button className={buttonClass} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 12000))}>Anterior</button>
        <button className={buttonClass} disabled={source.data.next_offset == null} onClick={() => setOffset(source.data!.next_offset!)}>Siguiente</button>
      </div>
    </>}
  </section>
}

export function TaskRunWorkspace({ projectId, taskId, conversationThreadId, onConversation }: {
  projectId: number; taskId: number; conversationThreadId?: string; onConversation?: (threadId: string) => void
}) {
  const workspace = useTaskWorkspace(projectId, taskId)
  const send = useInstruction()
  const stop = useStopRun(projectId, taskId)
  const correct = useCorrection(projectId, taskId)
  const [message, setMessage] = useState('')
  const [repositoryId, setRepositoryId] = useState<number | undefined>()
  const [statement, setStatement] = useState('')
  const [kind, setKind] = useState<'user_message' | 'user_example'>('user_message')
  const [sourceId, setSourceId] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const thread = useRef(crypto.randomUUID())
  const intent = useRef<InstructionIntent | null>(null)
  const correction = useRef<Parameters<typeof correct.mutate>[0] | null>(null)

  if (workspace.isPending) return <p role="status" className="text-sm text-[var(--work-muted)]">Recuperando trabajo y contexto…</p>
  if (workspace.error || !workspace.data) return <div role="alert" className="space-y-2 text-sm text-[var(--work-error)]">
    <p>No se pudo recuperar esta tarea. {workspace.error?.message}</p>
    <button className={buttonClass} onClick={() => workspace.refetch()}>Volver a consultar</button>
  </div>
  const data = workspace.data
  const active = data.runs.find(run => ['queued', 'running', 'cancelling', 'reconciling', 'waiting_input', 'needs_review'].includes(run.status))
  const current = active ?? data.runs[0] ?? null
  const state = presentRun(current?.status ?? null)
  const supported = data.runtime.supported_task_types.includes(data.context.task.type)
  const closed = ['done', 'cancelled', 'failed'].includes(data.context.task.status)
  const available = data.runtime.configured && supported && !closed
  const chooseRepository = data.repositories.length > 1 && repositoryId == null
  const sourceLabels: Record<string, string> = { user_message: 'Indicación del usuario', user_example: 'Ejemplo del usuario', tool_evidence: 'Evidencia registrada', assumption: 'Suposición' }

  const submit = () => {
    if (!intent.current) intent.current = prepareInstruction(projectId, {
      task_id: taskId, context_version: data.context.context_version,
      thread_id: conversationThreadId ?? current?.conversation_thread_id ?? thread.current,
      message: message.trim(), ...(repositoryId != null ? { repository_id: repositoryId } : {}),
    })
    send.mutate(intent.current, { onSuccess: result => {
      intent.current = null
      setMessage('')
      setNotice('Solicitud registrada. Consulta su estado para ver cuándo comienza.')
      onConversation?.(result.message.thread_id)
    } })
  }

  const saveCorrection = () => {
    if (!correction.current) correction.current = { operation_key: crypto.randomUUID(), expected_version: data.context.context_version, statement: statement.trim(), source_kind: kind }
    correct.mutate(correction.current, { onSuccess: result => {
      correction.current = null
      setStatement('')
      setNotice(`Corrección registrada en el contexto ${result.context_version}. Inicia otra ejecución cuando quieras usarla.`)
    } })
  }

  return <section className="task-execution text-sm" aria-label="Trabajo de la tarea">
    <div className="task-execution-main">
    <div className="space-y-1" role="status" aria-live="polite">
      <h3 className="font-semibold text-[var(--work-ink)]">{state.title}</h3>
      <p className="text-[var(--work-muted)]">{state.description}</p>
      <p className="text-xs text-[var(--work-muted)]">Contexto vigente: {data.context.context_version}{current ? ` · resultado bajo contexto ${current.context_version}` : ''}</p>
      {data.runtime.model && <p className="text-xs text-[var(--work-muted)]">Modelo configurado: {data.runtime.model}</p>}
      {current && <p className="text-xs text-[var(--work-muted)]">Modelo de esta ejecución: {current.model ?? 'sin registrar'}</p>}
    </div>
    {notice && <p role="status" className="text-[var(--work-accent)]">{notice}</p>}
    {!available && <p className="rounded-md border border-amber-700/50 p-3 text-[var(--work-caution)]">{closed ? 'Esta tarea está cerrada. Su historial y sus fuentes siguen disponibles.' : !data.runtime.configured ? 'Configura el motor local para iniciar trabajo. El historial y las fuentes siguen disponibles.' : 'Este tipo de tarea aún no permite iniciar trabajo. Su historial se conserva.'}</p>}
    {current && ['queued', 'running', 'cancelling', 'reconciling', 'waiting_input'].includes(current.status) && <div className="space-y-2">
      <button className={buttonClass} disabled={stop.isPending || current.status === 'cancelling'} onClick={() => stop.mutate(current.run_id)}>Detener ejecución</button>
      {stop.error && <p role="alert" className="text-[var(--work-error)]">No se confirmó la detención. Consulta el estado antes de continuar. {stop.error.message}</p>}
    </div>}
    {data.questions.map(question => <QuestionCard key={`${projectId}:${taskId}:${question.request_id}`} projectId={projectId} taskId={taskId} question={question} />)}
    {current && ['reconciling', 'cancelling'].includes(current.status) && <RecoveryCard key={`${projectId}:${current.run_id}`} projectId={projectId} taskId={taskId} runId={current.run_id} />}
    {current?.result && <section className="task-proposal space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Propuesta del agente">
      <h4 className="font-medium text-[var(--work-ink)]">{current.status === 'needs_review' ? 'Propuesta' : 'Resultado conservado'}</h4>
      <MarkdownRenderer content={current.result.summary} />
    </section>}
    <form className="space-y-2" onSubmit={event => { event.preventDefault(); submit() }}>
      <label className="block text-[var(--work-ink)]" htmlFor={`request-${taskId}`}>Solicitud para esta tarea</label>
      <textarea id={`request-${taskId}`} className={inputClass} rows={3} value={message} maxLength={50000} readOnly={intent.current != null} onChange={event => setMessage(event.target.value)} placeholder="Explica qué quieres comprobar y qué resultado necesitas. Puedes incluir un ejemplo." />
      {data.repositories.length > 1 && <label className="block space-y-1 text-[var(--work-ink)]">Repositorio
        <select className={inputClass} value={repositoryId ?? ''} disabled={intent.current != null} onChange={event => setRepositoryId(event.target.value ? Number(event.target.value) : undefined)}>
          <option value="">Elige el repositorio</option>
          {data.repositories.map(repository => <option key={repository.id} value={repository.id}>{repository.name}</option>)}
        </select>
      </label>}
      {send.error && <div role="alert" className="space-y-2 text-[var(--work-error)]">
        <p>El envío no quedó confirmado. Reenviarlo conserva la misma solicitud. {send.error.message}</p>
        <button type="button" className={buttonClass} onClick={() => { intent.current = null; send.reset(); setNotice('Revisa el historial: el envío anterior todavía puede existir.'); }}>Editar la solicitud</button>
      </div>}
      <div className="flex flex-wrap gap-2">
        <button className="rounded-md bg-[var(--work-accent-fill)] px-3 py-2 font-medium text-white hover:bg-[var(--work-accent-strong)] disabled:opacity-50" disabled={!available || !message.trim() || send.isPending || chooseRepository || (!state.canStart && !intent.current)}>{send.isPending ? 'Registrando…' : intent.current ? 'Reenviar la misma solicitud' : 'Iniciar trabajo'}</button>
        <button type="button" className={buttonClass} onClick={() => workspace.refetch()}>Consultar estado</button>
        {current && !message && <button type="button" className={buttonClass} onClick={() => setMessage(current.prompt)}>Usar solicitud anterior</button>}
      </div>
    </form>
    </div>
    <aside className="task-execution-context" aria-label="Fuentes y contexto">
    <h4>Fuentes y contexto</h4>
    <details open={data.context.corrections.length > 0} className="space-y-2 rounded-md border border-[var(--work-line)] p-3">
      <summary className="cursor-pointer font-medium text-[var(--work-ink)]">Corregir el contexto</summary>
      <p className="mt-2 text-[var(--work-muted)]">Una corrección retira el trabajo basado en el contexto anterior. Queda registrada para la próxima ejecución; no inicia otra por su cuenta.</p>
      <form className="mt-2 space-y-2" onSubmit={event => { event.preventDefault(); saveCorrection() }}>
        <label className="block text-[var(--work-ink)]">Tipo de corrección<select className={inputClass} value={kind} disabled={correction.current != null} onChange={event => setKind(event.target.value as typeof kind)}><option value="user_message">Indicación</option><option value="user_example">Ejemplo concreto</option></select></label>
        <label className="block text-[var(--work-ink)]">Qué cambia<textarea className={inputClass} rows={2} value={statement} readOnly={correction.current != null} maxLength={12000} onChange={event => setStatement(event.target.value)} /></label>
        {correct.error && <div role="alert" className="text-[var(--work-error)]"><p>No se confirmó la corrección. {correct.error.message}</p><button type="button" className={buttonClass} onClick={() => { correction.current = null; correct.reset() }}>Revisar la corrección</button></div>}
        <button className={buttonClass} disabled={!available || !statement.trim() || correct.isPending}>{correct.isPending ? 'Guardando…' : correction.current ? 'Reenviar la misma corrección' : 'Guardar corrección'}</button>
      </form>
      {data.context.corrections.map(item => <div key={item.version} className="mt-3 border-t border-[var(--work-line)] pt-2"><p className="text-xs text-[var(--work-muted)]">Contexto {item.version} · {sourceLabels[item.source_kind] ?? 'Procedencia sin clasificar'}</p><p className="whitespace-pre-wrap text-[var(--work-ink)]">{item.statement}</p></div>)}
    </details>
    <details open className="space-y-2 rounded-md border border-[var(--work-line)] p-3">
      <summary className="cursor-pointer font-medium text-[var(--work-ink)]">Fuentes y borradores</summary>
      {data.references.length > 0 && <p className="mt-2 text-[var(--work-muted)]">Adjuntos disponibles: {data.references.map(reference => reference.file_name).join(', ')}</p>}
      <ul className="mt-2 space-y-2">{data.sources.map(source => <li key={source.id}><button className="text-left text-[var(--work-accent)] underline" onClick={() => setSourceId(source.id)}>{source.title}</button> <span className="text-xs text-[var(--work-muted)]">· fuente del proyecto · {source.kind === 'attachment' ? 'adjunto capturado' : 'web capturada'}</span></li>)}</ul>
      {sourceId != null && <SourceReader key={`${projectId}:${sourceId}`} projectId={projectId} sourceId={sourceId} />}
      <ul className="mt-3 space-y-1">{data.reports.map(report => <li key={report.id}><a href={`/reports?project=${projectId}&artifact=${report.id}`} className="text-[var(--work-accent)] underline">{report.title}</a> <span className="text-xs text-[var(--work-muted)]">· {report.status === 'draft' ? 'borrador' : report.status}</span></li>)}</ul>
      {!data.sources.length && !data.reports.length && <p className="mt-2 text-[var(--work-muted)]">Todavía no hay fuentes capturadas ni borradores para mostrar.</p>}
    </details>
    {data.runs.length > 0 && <details className="rounded-md border border-[var(--work-line)] p-3"><summary className="cursor-pointer text-[var(--work-ink)]">Ejecuciones anteriores</summary><ul className="mt-2 space-y-2">{data.runs.map(run => <li key={run.run_id} className="border-t border-[var(--work-line)] pt-2"><p className="text-[var(--work-ink)]">{presentRun(run.status).title} · contexto {run.context_version}</p><p className="whitespace-pre-wrap text-[var(--work-muted)]">{run.prompt}</p></li>)}</ul></details>}
    </aside>
  </section>
}

/** Project-scoped task workbench, original native attempts, delivered results and explicit owner corrections. @module */
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { prepareInstruction, prepareRecovery, prepareStartRetry, presentRun, recoveryInspection, sourceWindow } from '../../api/runtime'
import type { RecoveryIntent, RuntimeRun, StartRetryIntent, PriorMaterialSelection } from '../../api/runtime'
import { useCorrection, useInstruction, useRecovery, useStartRetry, useStopRun, useTaskWorkspace } from '../../hooks/useRuntime'
import { QuestionCard } from '../chat/QuestionCard'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { FileImportInput } from './FileImportInput'
import { PriorCodeInput } from './PriorCodeInput'
import { BranchImportInput } from './BranchImportInput'
import { TaskInputHistory } from './TaskInputHistory'
import { RunInputRecord } from './RunInputRecord'
import { RunCommands } from './RunCommands'
import { TaskResults } from './ResultDelivery'
import { TaskCodeResults } from './CodeDelivery'
import { TaskRemotePublications } from './RemotePublications'
import { TaskProjectPlan } from './ProjectPlanDelivery'
import { TaskRunHistory } from './ExecutionHistory'
import {instructionPacket,prepareTaskCorrection,taskRequestPackets,verifyInstructionReceipt,verifyCorrectionReceipt,type TaskRequestPacket} from '../../api/taskRequests'

const inputClass = 'w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm text-[var(--work-ink)] focus:outline-hidden focus:ring-2 focus:ring-[var(--work-accent)]'
const buttonClass = 'rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] hover:bg-[var(--work-wash)] disabled:opacity-50'

/** Restore saved input independently for each mutation family; damage blocks a fresh delivery. */
function restored<K extends TaskRequestPacket['kind']>(kind:K,project:number,task:number){if(typeof window==='undefined')return {packet:null,issue:null as string|null,blocked:false};try{return {packet:taskRequestPackets.load(window.sessionStorage,kind,project,task),issue:null as string|null,blocked:false}}catch(error){return {packet:null,issue:error instanceof Error?error.message:'No se pudo recuperar la solicitud original.',blocked:true}}}

/** Retry only the already admitted original request without changing its task, repository or context. */
function QueuedStart({ projectId, taskId, run }: { projectId: number; taskId: number; run: RuntimeRun }) {
  const retry = useStartRetry()
  const intent = useRef<StartRetryIntent | null>(null)
  if (run.repository_id == null) return <p className="text-[var(--work-caution)]">Esta solicitud no guardó su repositorio. Detén la solicitud y crea otra con una selección comprobable.</p>
  return <section className="space-y-2" aria-label="Iniciar solicitud guardada">
    <details open><summary className="cursor-pointer text-[var(--work-ink)]">Solicitud guardada · contexto {run.context_version}</summary><p tabIndex={0} aria-label="Texto de la solicitud original" className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[var(--work-ink)]">{run.prompt}</p></details>
    <p className="text-[var(--work-muted)]">Este control intenta iniciar la solicitud guardada en {run.repository_name ?? `repositorio ${run.repository_id}`}. Conserva el texto de la solicitud, su versión de contexto y el repositorio admitido.</p>
    <button className={buttonClass} disabled={retry.isPending} onClick={() => {
      if (!intent.current) intent.current = prepareStartRetry(projectId, taskId, run.run_id, run.fence, run.context_version)
      retry.mutate(intent.current, {onSuccess: () => { intent.current = null }})
    }}>{retry.isPending ? 'Comprobando inicio…' : intent.current ? 'Consultar el mismo intento de inicio' : 'Reintentar inicio guardado'}</button>
    {retry.error && <p role="alert" className="text-[var(--work-error)]">No se confirmó el inicio. Consultar de nuevo conserva el mismo control. {retry.error.message}</p>}
    {retry.isSuccess && <p role="status" className="text-[var(--work-muted)]">Control registrado. Consulta el estado para saber si el trabajo pudo comenzar.</p>}
  </section>
}

/** Inspect original attempt closure without replaying work or accepting its result. */
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
      {details.data.unknown_jobs > 0 && <p className="text-[var(--work-caution)]">Hay comandos sin un resultado final confirmado. Comprobar su cierre no indica si terminaron bien ni revierte sus efectos.</p>}
      {details.data.jobs.length > 0 && <ul className="space-y-1 text-[var(--work-muted)]">{details.data.jobs.map((job, index) => <li key={job.id}>Comando {index + 1}: {job.local_execution_closed ? 'cierre comprobado' : 'cierre por comprobar'} · {job.exit_code == null ? 'resultado desconocido' : `código de salida ${job.exit_code}`}</li>)}</ul>}
      {details.data.jobs_truncated && <p className="text-[var(--work-muted)]">Esta vista muestra los primeros 25 comandos. Para recorrerlos todos y leer sus salidas, abre «Comandos y resultados guardados».</p>}
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


/** Page saved source text and preserve failures as unknown content. */
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

/** Keep execution controls and author delivery selection bound to the observed project and task. */
export function TaskRunWorkspace({ projectId, taskId, conversationThreadId, onConversation, conversation, showProposal = true }: {
  projectId: number; taskId: number; conversationThreadId?: string; onConversation?: (threadId: string) => void; conversation?: ReactNode; showProposal?: boolean
}) {
  const workspace = useTaskWorkspace(projectId, taskId)
  const send = useInstruction()
  const stop = useStopRun(projectId, taskId)
  const correct = useCorrection(projectId, taskId)
  const [instructionState,setInstructionState]=useState(()=>restored('instruction',projectId,taskId))
  const [correctionState,setCorrectionState]=useState(()=>restored('correction',projectId,taskId))
  const intent=instructionState.packet,correctionIntent=correctionState.packet?.body??null
  const alive=useRef(true)
  useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
  const [message, setMessage] = useState(intent?.body.message??'')
  const [repositoryId, setRepositoryId] = useState<number | undefined>(intent?.body.repository_id)
  const [priorCode, setPriorCode] = useState<Readonly<PriorMaterialSelection> | null>(intent?.body.prior_code??null)
  const [statement, setStatement] = useState(correctionIntent?.statement??'')
  const [kind, setKind] = useState<'user_message' | 'user_example'>(correctionIntent?.source_kind??'user_message')
  const [sourceId, setSourceId] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const [newConversation, setNewConversation] = useState(false)
  const thread = useRef(crypto.randomUUID())

  if (workspace.isPending) return <p role="status" className="text-sm text-[var(--work-muted)]">Recuperando trabajo y contexto…</p>
  if (workspace.error || !workspace.data) return <div role="alert" className="space-y-2 text-sm text-[var(--work-error)]">
    <p>No se pudo recuperar esta tarea. {workspace.error?.message}</p>
    <button className={buttonClass} onClick={() => workspace.refetch()}>Volver a consultar</button>
  </div>
  const data = workspace.data
  const active = data.runs.find(run => ['queued', 'running', 'cancelling', 'reconciling', 'waiting_input', 'needs_review'].includes(run.status))
  const current = active ?? data.runs[0] ?? null
  // Historical acceptance remains intact while a reopened context permits an explicit new request.
  const historicalAcceptance = !active && current?.status === 'accepted' && current.context_version < data.context.context_version
  const state = presentRun(historicalAcceptance ? 'superseded' : current?.status ?? null)
  const supported = data.runtime.supported_task_types.includes(data.context.task.type)
  const closed = ['done', 'cancelled', 'failed'].includes(data.context.task.status)
  const available = data.runtime.configured && supported && !closed
  const chooseRepository = data.repositories.length > 1 && repositoryId == null
  const sourceLabels: Record<string, string> = { user_message: 'Indicación del usuario', user_example: 'Ejemplo del usuario', tool_evidence: 'Evidencia registrada', assumption: 'Suposición' }

  /** Save the original request before transport; acknowledge only its exact scoped admission receipt. */
  const submit = () => {
    if(instructionState.blocked)return
    try{
      const selectedRepository=repositoryId??(data.repositories.length===1?data.repositories[0].id:undefined)
      const packet=intent??instructionPacket(prepareInstruction(projectId,{
        task_id:taskId,context_version:data.context.context_version,
        thread_id:newConversation?thread.current:conversationThreadId??current?.conversation_thread_id??thread.current,
        message:message.trim(),...(selectedRepository!=null?{repository_id:selectedRepository}:{}),
        ...(priorCode?{prior_code:priorCode}:{}),
      }))
      taskRequestPackets.save(window.sessionStorage,packet)
      setInstructionState({packet,issue:null,blocked:false})
      send.mutate(packet,{onSuccess:result=>{
        try{verifyInstructionReceipt(packet,result);taskRequestPackets.clear(window.sessionStorage,packet)}catch(error){if(alive.current)setInstructionState(state=>({...state,issue:error instanceof Error?error.message:'No se confirmó el recibo original.'}));return}
        if(!alive.current)return
        setInstructionState({packet:null,issue:null,blocked:false})
        thread.current=crypto.randomUUID();setNewConversation(false);setMessage('');setPriorCode(null)
        setNotice('Solicitud registrada. Consulta su estado para ver cuándo comienza.')
        onConversation?.(result.message.thread_id)
      }})
    }catch(error){setInstructionState(state=>({...state,issue:error instanceof Error?error.message:'No se guardó la solicitud; no se envió.'}))}
  }

  /** Persist the correction's original expected version; recovery never silently upgrades it to current context. */
  const saveCorrection = () => {
    if(correctionState.blocked)return
    try{
      const packet=correctionState.packet??prepareTaskCorrection(projectId,taskId,{expected_version:data.context.context_version,statement:statement.trim(),source_kind:kind})
      taskRequestPackets.save(window.sessionStorage,packet)
      setCorrectionState({packet,issue:null,blocked:false})
      correct.mutate(packet.body,{onSuccess:result=>{
        try{verifyCorrectionReceipt(packet,result);taskRequestPackets.clear(window.sessionStorage,packet)}catch(error){if(alive.current)setCorrectionState(state=>({...state,issue:error instanceof Error?error.message:'No se confirmó la corrección original.'}));return}
        if(!alive.current)return
        setCorrectionState({packet:null,issue:null,blocked:false});setStatement('')
        setNotice(`Corrección registrada en el contexto ${result.context_version}. Inicia otra ejecución cuando quieras usarla.`)
      }})
    }catch(error){setCorrectionState(state=>({...state,issue:error instanceof Error?error.message:'No se guardó la corrección; no se envió.'}))}
  }

  /** Discard only an explicitly chosen local copy, without cancelling, undoing or denying its server effects. */
  const discard = (kind:'instruction'|'correction') => {
    const packet=kind==='instruction'?instructionState.packet:correctionState.packet
    if(!packet)return
    try{
      taskRequestPackets.clear(window.sessionStorage,packet)
      if(kind==='instruction'){setInstructionState({packet:null,issue:null,blocked:false});send.reset()}else{setCorrectionState({packet:null,issue:null,blocked:false});correct.reset()}
      setNotice('Se retiró sólo la copia local. La solicitud anterior todavía puede existir: consulta su historial antes de preparar otra.')
    }catch(error){const issue=error instanceof Error?error.message:'No se pudo retirar la copia original.';if(kind==='instruction')setInstructionState(state=>({...state,issue}));else setCorrectionState(state=>({...state,issue}))}
  }

  return <section className="task-execution text-sm" aria-label="Trabajo de la tarea">
    <div className="task-execution-main">
    <div className="space-y-1" role="status" aria-live="polite">
      <h3 className="font-semibold text-[var(--work-ink)]">{state.title}</h3>
      <p className="text-[var(--work-muted)]">{state.description}</p>
      <p className="text-xs text-[var(--work-muted)]">Contexto vigente: {data.context.context_version}{current ? ` · resultado bajo contexto ${current.context_version}` : ''}</p>
      {data.runtime.model && <p className="text-xs text-[var(--work-muted)]">Modelo inicial del equipo: {data.runtime.model}</p>}
      {current?.model_selection&&<p className="text-xs text-[var(--work-muted)]">Elección guardada para este intento: {current.model_selection.model} · razonamiento {current.model_selection.reasoning_effort}. Cambiar la configuración no modifica esta elección.</p>}
      {current?.actor_id&&<p className="text-xs text-[var(--work-muted)]">Identificador del agente: {current.actor_id}</p>}
      {current && !['code_publication','remote_publication'].includes(current.execution_kind) && <p className="text-xs text-[var(--work-muted)]">Modelo de esta ejecución: {current.model ?? 'sin registrar'}</p>}
      {current && <p className="text-xs text-[var(--work-muted)]">Repositorio admitido: {current.repository_name ?? current.repository_id ?? 'sin registrar en este historial'}</p>}
    </div>
    {notice && <p role="status" className="text-[var(--work-accent)]">{notice}</p>}
    {conversation}
    {current?.issue && <section className="space-y-1" aria-label="Lo que ocurrió"><p className="text-[var(--work-caution)]">{current.issue.message}</p>{current.issue.inference_started === null && <p className="text-[var(--work-muted)]">No quedó confirmado si la inferencia comenzó. No la repetiremos automáticamente.</p>}</section>}
    {current?.status === 'queued' && available && <QueuedStart key={`${projectId}:${current.run_id}`} projectId={projectId} taskId={taskId} run={current} />}
    {!available && <p className="rounded-md border border-amber-700/50 p-3 text-[var(--work-caution)]">{closed ? 'Esta tarea está cerrada. Su historial y sus fuentes siguen disponibles.' : !data.runtime.configured ? 'Configura el motor local para iniciar trabajo. El historial y las fuentes siguen disponibles.' : 'Este tipo de tarea aún no permite iniciar trabajo. Su historial se conserva.'}</p>}
    {current && ['queued', 'running', 'cancelling', 'reconciling', 'waiting_input', 'needs_review'].includes(current.status) && <div className="space-y-2">
      <button className={buttonClass} disabled={stop.isPending || current.status === 'cancelling'} onClick={() => stop.mutate(current.run_id)}>Detener ejecución</button>
      {stop.error && <p role="alert" className="text-[var(--work-error)]">No se confirmó la detención. Consulta el estado antes de continuar. {stop.error.message}</p>}
    </div>}
    {data.questions.map(question => <QuestionCard key={`${projectId}:${taskId}:${question.request_id}`} projectId={projectId} taskId={taskId} question={question} />)}
    {current && !['code_publication','remote_publication'].includes(current.execution_kind) && ['reconciling', 'cancelling'].includes(current.status) && <RecoveryCard key={`${projectId}:${current.run_id}`} projectId={projectId} taskId={taskId} runId={current.run_id} />}
    {current && <RunCommands projectId={projectId} runId={current.run_id} />}
    {data.context.task.type==='plan'?<TaskProjectPlan projectId={projectId} taskId={taskId} runs={data.runs}/>:<TaskResults key={`${projectId}:${taskId}`} projectId={projectId} taskId={taskId} runs={data.runs} contextVersion={data.context.context_version} />}
    <TaskCodeResults key={`code:${projectId}:${taskId}`} projectId={projectId} taskId={taskId} runs={data.runs} contextVersion={data.context.context_version} reviewAvailable={data.runtime.configured && supported} />
    <TaskRemotePublications key={`remote:${projectId}:${taskId}`} projectId={projectId} taskId={taskId} runs={data.runs} available={data.runtime.configured && data.runtime.remote_publication===true} defaultBranch={data.repositories.find(repository=>repository.id===current?.repository_id)?.default_branch??'main'} />
    {showProposal && current?.result && <section className="task-proposal space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Propuesta del agente">
      <h4 className="font-medium text-[var(--work-ink)]">{current.status === 'needs_review' ? 'Propuesta' : 'Resultado conservado'}</h4>
      <MarkdownRenderer content={current.result.summary} />
    </section>}
    {(data.runtime.development_task_types ?? []).includes(data.context.task.type)&&<PriorCodeInput key={`prior:${projectId}:${taskId}`} projectId={projectId} taskId={taskId} runs={data.runs} selected={priorCode} locked={intent!=null||send.isPending} onSelect={setPriorCode}/>}
    {(data.runtime.development_task_types ?? []).includes(data.context.task.type)&&<FileImportInput key={`files:${projectId}:${taskId}`} projectId={projectId} taskId={taskId} selected={priorCode} locked={intent!=null||send.isPending} configured={data.runtime.configured} onSelect={setPriorCode}/>}
    {(data.runtime.development_task_types ?? []).includes(data.context.task.type)&&<BranchImportInput key={`branch:${projectId}:${taskId}`} projectId={projectId} taskId={taskId} selected={priorCode} locked={intent!=null||send.isPending} configured={data.runtime.configured} onSelect={setPriorCode}/>}
    <form className="space-y-2" onSubmit={event => { event.preventDefault(); submit() }}>
      <label className="block text-[var(--work-ink)]" htmlFor={`request-${taskId}`}>Solicitud para esta tarea</label>
      <textarea id={`request-${taskId}`} className={inputClass} rows={3} value={message} maxLength={50000} readOnly={intent != null||instructionState.blocked} onChange={event => setMessage(event.target.value)} placeholder="Explica qué quieres comprobar y qué resultado necesitas. Puedes incluir un ejemplo." />
      {!intent&&<label className="flex items-start gap-2 text-[var(--work-ink)]"><input type="checkbox" checked={newConversation} disabled={send.isPending||instructionState.blocked} onChange={event => setNewConversation(event.target.checked)} />Iniciar sin los mensajes anteriores</label>}
      {!intent&&newConversation && <p className="text-[var(--work-muted)]">Se conservan la tarea, las correcciones y las respuestas registradas. Incluye en la nueva solicitud las condiciones del historial que quieras mantener.</p>}
      {!intent&&data.repositories.length > 1 && <label className="block space-y-1 text-[var(--work-ink)]">Repositorio
        <select className={inputClass} value={repositoryId ?? ''} disabled={intent != null} onChange={event => setRepositoryId(event.target.value ? Number(event.target.value) : undefined)}>
          <option value="">Elige el repositorio</option>
          {data.repositories.map(repository => <option key={repository.id} value={repository.id}>{repository.name}</option>)}
        </select>
      </label>}
      {intent&&<p role="status">Solicitud original guardada · contexto {intent.body.context_version}. Recuperarla conserva el texto, la conversación y la selección de repositorio originales.</p>}
      {(send.error||instructionState.issue)&&<div role="alert" className="space-y-2 text-[var(--work-error)]"><p>El envío no quedó confirmado. {instructionState.issue??send.error?.message}</p><p>{intent?'La solicitud original se conserva; reenviarla usa la misma clave.':'No se envió una solicitud nueva desde este formulario.'}</p></div>}
      {intent&&<div><p>Retirar la copia no detiene ni revierte el trabajo ya admitido. Consulta primero el historial.</p><button type="button" className={buttonClass} disabled={send.isPending} onClick={()=>discard('instruction')}>Retirar copia y editar solicitud</button></div>}
      <div className="flex flex-wrap gap-2">
        <button className="rounded-md bg-[var(--work-accent-fill)] px-3 py-2 font-medium text-white hover:bg-[var(--work-accent-strong)] disabled:opacity-50" disabled={instructionState.blocked || !message.trim() || send.isPending || (!intent&&(!available||chooseRepository||!state.canStart))}>{send.isPending ? 'Registrando…' : intent ? 'Reenviar la misma solicitud' : 'Iniciar trabajo'}</button>
        <button type="button" className={buttonClass} onClick={() => workspace.refetch()}>Consultar estado</button>
        {current && !message && <button type="button" className={buttonClass} onClick={() => setMessage(current.prompt)}>Usar solicitud anterior</button>}
      </div>
    </form>
    </div>
    <aside className="task-execution-context" aria-label="Fuentes y contexto">
    <h4>Fuentes y contexto</h4>
    {current && <RunInputRecord key={`${projectId}:${current.run_id}`} projectId={projectId} runId={current.run_id} />}
    <TaskInputHistory changes={data.context.task_changes ?? []} />
    <details open={data.context.corrections.length > 0} className="space-y-2 rounded-md border border-[var(--work-line)] p-3">
      <summary className="cursor-pointer font-medium text-[var(--work-ink)]">Corregir el contexto</summary>
      <p className="mt-2 text-[var(--work-muted)]">Una corrección retira el trabajo basado en el contexto anterior. Queda registrada para la próxima ejecución; no inicia otra por su cuenta.</p>
      <form className="mt-2 space-y-2" onSubmit={event => { event.preventDefault(); saveCorrection() }}>
        <label className="block text-[var(--work-ink)]" htmlFor={`correction-kind-${taskId}`}>Tipo de corrección</label><select id={`correction-kind-${taskId}`} className={inputClass} value={kind} disabled={correctionIntent != null||correctionState.blocked} onChange={event => setKind(event.target.value as typeof kind)}><option value="user_message">Indicación</option><option value="user_example">Ejemplo concreto</option></select>
        <label className="block text-[var(--work-ink)]" htmlFor={`correction-statement-${taskId}`}>Qué cambia</label><textarea id={`correction-statement-${taskId}`} className={inputClass} rows={2} value={statement} readOnly={correctionIntent != null||correctionState.blocked} maxLength={12000} onChange={event => setStatement(event.target.value)} />
        {correctionIntent&&<p role="status">Corrección original guardada · contexto de origen {correctionIntent.expected_version}. Recuperarla conserva esa versión y el mismo texto.</p>}
        {(correct.error||correctionState.issue)&&<div role="alert" className="text-[var(--work-error)]"><p>No se confirmó la corrección. {correctionState.issue??correct.error?.message}</p><p>{correctionIntent?'Se conserva la corrección original para recuperarla.':'No se envió una corrección nueva desde este formulario.'}</p></div>}
        <button className={buttonClass} disabled={correctionState.blocked || (!correctionIntent&&!available) || !statement.trim() || correct.isPending}>{correct.isPending ? 'Guardando…' : correctionIntent ? 'Reenviar la misma corrección' : 'Guardar corrección'}</button>
        {correctionIntent&&<div><p>Retirar la copia no revierte una corrección ya registrada.</p><button type="button" className={buttonClass} disabled={correct.isPending} onClick={()=>discard('correction')}>Retirar copia y revisar corrección</button></div>}
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
    <TaskRunHistory projectId={projectId} taskId={taskId}/>
    </aside>
  </section>
}

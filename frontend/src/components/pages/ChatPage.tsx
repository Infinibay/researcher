import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/project'
import { useTasks } from '../../hooks/useTasks'
import { useChatThreads, useThreadMessages } from '../../hooks/useChat'
import { useTaskWorkspace } from '../../hooks/useRuntime'
import { TaskRunWorkspace } from '../tasks/TaskRunWorkspace'
import { ConversationTimeline } from '../chat/ConversationTimeline'
import { QuestionInbox } from '../chat/QuestionInbox'
import type { Task } from '../../types/api'
import '../../styles/tasks.css'
import '../../styles/conversation.css'

export function ChatPage() {
  const projectId = useProjectStore(state => state.activeProjectId)
  if (projectId == null) return <section className="task-workbench conversation-workbench conversation-empty"><h1>Conversación</h1><h2>Ningún proyecto seleccionado</h2><p>Selecciona un proyecto para abrir sus tareas y conversaciones.</p></section>
  return <ProjectConversation key={projectId} projectId={projectId} />
}

function ProjectConversation({ projectId }: { projectId: number }) {
  const tasks = useTasks(projectId)
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const id = Number(params.get('task'))
  const selected = tasks.data?.find(task => task.id === id && task.project_id === projectId)
  const questionId = Number(params.get('question')) || undefined
  const choose = (taskId: number, requestId?: number) => {
    const next = new URLSearchParams(params)
    next.set('task', String(taskId))
    if (requestId != null) next.set('question', String(requestId))
    else next.delete('question')
    setParams(next)
  }
  const back = () => {
    const next = new URLSearchParams(params)
    next.delete('task'); next.delete('question')
    setParams(next)
    requestAnimationFrame(() => document.getElementById(`conversation-task-${id}`)?.focus())
  }
  const visibleTasks = (tasks.data ?? []).filter(task => `${task.id} ${task.title}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <section className="task-workbench conversation-workbench" data-has-selection={selected != null}>
    <header className="conversation-page-heading"><div><h1>Conversación</h1><p>Una tarea, su conversación y el contexto de cada intervención.</p></div><Link to="/tasks">Gestionar tareas</Link></header>
    <div className="conversation-layout">
      <aside className="conversation-index" aria-label="Tareas y preguntas del proyecto">
        <QuestionInbox projectId={projectId} tasks={tasks.data ?? []} onChoose={choose} />
        <div className="conversation-task-heading"><h2>Tareas</h2><label>Buscar tarea<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Título o número" /></label></div>
        {tasks.isPending && <p role="status">Recuperando las tareas…</p>}
        {tasks.error && <div className="conversation-error" role="alert"><p>No se pudieron recuperar las tareas.</p><button onClick={() => tasks.refetch()}>Volver a consultar</button></div>}
        {tasks.data?.length === 0 && <p className="conversation-index-note">Crea una tarea en Tareas para empezar.</p>}
        {tasks.data && tasks.data.length > 0 && !visibleTasks.length && <p className="conversation-index-note">No hay tareas con esa búsqueda.</p>}
        <ul className="conversation-tasks">{visibleTasks.map(task => <li key={task.id}><button id={`conversation-task-${task.id}`} onClick={() => choose(task.id)} aria-current={selected?.id === task.id ? 'true' : undefined}><span className="conversation-meta">Tarea #{task.id}</span><strong>{task.title}</strong><span>{task.type === 'research' ? 'Investigación' : task.type}</span></button></li>)}</ul>
      </aside>
      <div className="conversation-reading">
        {selected ? <TaskConversation key={`${projectId}:${selected.id}`} projectId={projectId} task={selected} questionId={questionId} onBack={back} /> : <div className="conversation-empty"><h2>Elige una tarea</h2><p>Abre una tarea para leer su conversación, responder sus preguntas o indicar qué quieres comprobar. Seleccionarla no inicia trabajo.</p>{id > 0 && !tasks.isPending && <p>La tarea indicada no está disponible en este proyecto.</p>}</div>}
        <ProjectArchive projectId={projectId} />
      </div>
    </div>
  </section>
}

function TaskConversation({ projectId, task, questionId, onBack }: { projectId: number; task: Task; questionId?: number; onBack: () => void }) {
  const workspace = useTaskWorkspace(projectId, task.id)
  const [thread, setThread] = useState<string | null>(null)
  const title = useRef<HTMLHeadingElement>(null)
  const runs = workspace.data?.runs ?? []
  const current = runs.find(run => ['queued', 'running', 'cancelling', 'reconciling', 'waiting_input', 'needs_review'].includes(run.status)) ?? runs[0]
  const threadId = thread ?? current?.conversation_thread_id ?? null
  const history = useThreadMessages(projectId, threadId)
  const pendingRuns = new Set(workspace.data?.questions.filter(question => question.status === 'pending').map(question => question.run_id))
  const messages = (history.data ?? []).filter(message => !(message.delivery === 'question' && message.runtime_run_id && pendingRuns.has(message.runtime_run_id)))
  const proposalVisible = messages.some(message => message.project_id === projectId && message.task_id === task.id && message.runtime_run_id === current?.run_id && message.delivery === 'proposal')
  const canFocusQuestion = questionId != null && workspace.data?.questions.some(question => question.request_id === questionId) === true
  useEffect(() => {
    const target = canFocusQuestion ? document.getElementById(`runtime-question-${questionId}`) : title.current
    target?.focus()
  }, [task.id, questionId, canFocusQuestion])
  return <article className="conversation-task" aria-labelledby={`conversation-title-${task.id}`}>
    <button className="conversation-back" onClick={onBack}>Volver a tareas y preguntas</button>
    <header className="conversation-task-title"><p className="conversation-meta">Conversación · tarea #{task.id}</p><h2 id={`conversation-title-${task.id}`} ref={title} tabIndex={-1}>{task.title}</h2>{task.description && <p>{task.description}</p>}</header>
    <TaskRunWorkspace projectId={projectId} taskId={task.id} conversationThreadId={threadId ?? undefined} onConversation={setThread} showProposal={!proposalVisible} conversation={<section aria-label="Conversación de la tarea" className="conversation-exchange">
      <h3>Conversación guardada</h3>
      <p className="conversation-history-note">El próximo trabajo recibe la tarea, sus correcciones y respuestas, y los mensajes anteriores de esta conversación hasta registrar la solicitud. Las propuestas antiguas conservan su versión; verlas no las convierte en hechos comprobados. Puedes consultar la entrada de cada ejecución.</p>
      {threadId == null && <p>Todavía no hay una solicitud registrada para esta tarea.</p>}
      {threadId != null && history.isPending && <p role="status">Recuperando la conversación…</p>}
      {history.error && <div role="alert"><p>No se pudo recuperar la conversación.</p><button onClick={() => history.refetch()}>Volver a consultar</button></div>}
      {messages.length > 0 && <ConversationTimeline messages={messages} selectedTaskId={task.id} />}
      {threadId != null && history.isSuccess && !messages.length && <p>Las preguntas que requieren respuesta se muestran debajo con sus controles.</p>}
    </section>} />
  </article>
}

function ProjectArchive({ projectId }: { projectId: number }) {
  const threads = useChatThreads(projectId)
  const [selected, setSelected] = useState<string | null>(null)
  const history = useThreadMessages(projectId, selected)
  return <details className="conversation-archive"><summary>Archivo de conversaciones del proyecto</summary><p>Lectura de los hilos guardados. Abrirlos no envía mensajes ni inicia ejecuciones.</p>
    {threads.isPending && <p role="status">Recuperando los hilos…</p>}
    {threads.error && <div role="alert"><p>No se pudieron recuperar los hilos.</p><button onClick={() => threads.refetch()}>Volver a consultar</button></div>}
    {threads.data?.length === 0 && <p>Todavía no hay hilos guardados.</p>}
    <ul className="conversation-archive-index">{threads.data?.map(item => <li key={item.thread_id}><button aria-pressed={selected === item.thread_id} onClick={() => setSelected(item.thread_id)}><span>{item.last_message || 'Conversación sin mensajes'}</span><span>{item.message_count ?? 0} mensajes</span></button></li>)}</ul>
    {selected && history.isPending && <p role="status">Recuperando el hilo…</p>}
    {history.error && <div role="alert"><p>No se pudo recuperar el hilo.</p><button onClick={() => history.refetch()}>Volver a consultar</button></div>}
    {history.data && <ConversationTimeline messages={history.data} />}
  </details>
}

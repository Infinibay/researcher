import type { ChatMessage } from '../../types/api'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

function receipt(message: ChatMessage) {
  if (message.delivery === 'proposal') return message.runtime_status === 'needs_review' ? 'Propuesta para revisar' : 'Resultado conservado'
  if (message.delivery === 'instruction_admitted') return 'Solicitud registrada'
  if (message.delivery === 'question') return 'Pregunta conservada'
  if (message.delivery === 'answer') return 'Respuesta registrada'
  return 'Mensaje conservado'
}

function timestamp(value: string) {
  const normalized = /^\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?$/.test(value) ? value.replace(' ', 'T') + 'Z' : value
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? 'Fecha sin interpretar' : new Intl.DateTimeFormat('es', {dateStyle:'medium',timeStyle:'short',timeZone:'UTC'}).format(date) + ' UTC'
}

export function ConversationTimeline({ messages, selectedTaskId }: { messages: ChatMessage[]; selectedTaskId?: number }) {
  return <ol className="conversation-timeline" aria-label="Mensajes guardados">
    {messages.map(message => <li key={message.id} className="conversation-entry" data-sender={message.from_agent === 'user' ? 'user' : 'agent'}>
      <div className="conversation-entry-heading"><strong>{message.from_agent === 'user' ? 'Tú' : message.from_agent === 'researcher' ? 'Investigador' : message.from_agent}</strong>{message.created_at && <time dateTime={message.created_at}>{timestamp(message.created_at)}</time>}</div>
      <p className="conversation-receipt">{receipt(message)}{message.task_id != null ? ` · tarea #${message.task_id}` : ''}{message.context_version != null ? ` · contexto ${message.context_version}` : ''}</p>
      {selectedTaskId != null && message.task_id != null && selectedTaskId !== message.task_id && <p className="conversation-other-task">Este mensaje pertenece a otra tarea del hilo.</p>}
      <MarkdownRenderer content={message.message} />
    </li>)}
  </ol>
}

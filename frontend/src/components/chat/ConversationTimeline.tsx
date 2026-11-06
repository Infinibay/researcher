import type { ChatMessage } from '../../types/api'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

/** Name only the delivery state actually recorded by the host. */
function receipt(message: ChatMessage) {
  if (message.peer_message) return message.peer_message.delivery === 'receipt_acknowledged' ? 'Recepción reconocida' : 'Mensaje entre agentes registrado'
  if (message.delivery === 'proposal') return message.runtime_status === 'needs_review' ? 'Propuesta para revisar' : 'Resultado conservado'
  if (message.delivery === 'instruction_admitted') return 'Solicitud registrada'
  if (message.delivery === 'question') return 'Pregunta conservada'
  if (message.delivery === 'answer') return 'Respuesta registrada'
  return 'Mensaje conservado'
}

/** Render database timestamps as UTC without inventing a local timezone. */
function timestamp(value: string) {
  const normalized = /^\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?$/.test(value) ? value.replace(' ', 'T') + 'Z' : value
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? 'Fecha sin interpretar' : new Intl.DateTimeFormat('es', {dateStyle:'medium',timeStyle:'short',timeZone:'UTC'}).format(date) + ' UTC'
}

/** Show attributed peer premises and receipt limits beside the original conversation. */
function PeerContext({ message }: { message: ChatMessage }) {
  const peer = message.peer_message
  if (!peer) return null
  return <aside aria-label="Contexto del mensaje entre agentes">
    <p>Dirigido a {message.to_agent} · tarea #{peer.recipient_task_id} · contexto {peer.recipient_context_version}</p>
    {peer.parent_message_id != null && <p>En respuesta al mensaje #{peer.parent_message_id}.</p>}
    <p>{peer.delivery === 'recorded' ? 'No consta recepción. ' : ''}Comprensión y aplicación sin verificar. Este mensaje no autoriza trabajo.</p>
    {!peer.recipient_context_current && <p>El contexto del destinatario cambió después de este mensaje.</p>}
    {peer.observations.length > 0 && <><h4>Observaciones del emisor</h4><ul>{peer.observations.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
    {peer.assumptions.length > 0 && <><h4>Suposiciones del emisor</h4><ul>{peer.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
    {peer.evidence_refs.length > 0 && <p>Fuentes citadas: {peer.evidence_refs.map(source => `#${source.source_id}`).join(', ')}. La cita no verifica la interpretación.</p>}
  </aside>
}

/** Keep owner instructions, proposals and peer advisories visually distinct without implying task completion. */
export function ConversationTimeline({ messages, selectedTaskId }: { messages: ChatMessage[]; selectedTaskId?: number }) {
  return <ol className="conversation-timeline" aria-label="Mensajes guardados">
    {messages.map(message => <li key={message.id} className="conversation-entry" data-sender={message.from_agent === 'user' ? 'user' : 'agent'}>
      <div className="conversation-entry-heading"><strong>{message.from_agent === 'user' ? 'Tú' : message.from_agent === 'researcher' ? 'Investigador' : message.from_agent}</strong>{message.created_at && <time dateTime={message.created_at}>{timestamp(message.created_at)}</time>}</div>
      <p className="conversation-receipt">{receipt(message)}{message.task_id != null ? ` · tarea #${message.task_id}` : ''}{message.context_version != null ? ` · contexto ${message.context_version}` : ''}</p>
      {selectedTaskId != null && message.task_id != null && selectedTaskId !== message.task_id && <p className="conversation-other-task">Este mensaje pertenece a otra tarea del hilo.</p>}
      <MarkdownRenderer content={message.message} />
      <PeerContext message={message} />
    </li>)}
  </ol>
}

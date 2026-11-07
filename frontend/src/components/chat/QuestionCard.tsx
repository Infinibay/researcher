/** Present every question with stable option identities and retain the exact owner answer after uncertain delivery. @module */
import { useRef, useState } from 'react'
import { prepareAnswer } from '../../api/runtime'
import type { AnswerIntent, QuestionAnswer, RuntimeQuestion } from '../../api/runtime'
import { useAnswer } from '../../hooks/useRuntime'

const inputClass = 'w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm text-[var(--work-ink)] focus:outline-hidden focus:ring-2 focus:ring-[var(--work-accent)]'
const buttonClass = 'rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] hover:bg-[var(--work-wash)] disabled:opacity-50'

/** Resolve a selected label from its original question; typed input remains literal text. */
function answerText(question: RuntimeQuestion['questions'][number], answer?: QuestionAnswer): string {
  if (answer == null) return ''
  if (typeof answer === 'string') return answer
  const option = question.options.find(option => typeof option !== 'string' && option.id === answer.option_id)
  return typeof option === 'object' ? option.label : `Opción no disponible: ${answer.option_id}`
}

/** Keep multiple answers, free text, source context and retry identity together in one accessible form. */
export function QuestionCard({ projectId, taskId, question }: { projectId: number; taskId: number; question: RuntimeQuestion }) {
  const answer = useAnswer()
  const [values, setValues] = useState<Record<string, QuestionAnswer>>({})
  const [error, setError] = useState('')
  const intent = useRef<AnswerIntent | null>(null)
  const pending = question.status === 'pending'
  /** Retry the original packet after an uncertain response; changed input requires an explicit new context. */
  const submit = () => {
    try {
      if (!intent.current) intent.current = prepareAnswer(projectId, taskId, question.request_id, question.context_version, values)
      setError('')
      answer.mutate(intent.current)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Revisa las respuestas.') }
  }
  return <section id={`runtime-question-${question.request_id}`} tabIndex={-1} className="space-y-3 rounded-md border border-[var(--work-line)] p-3" aria-label="Preguntas del agente">
    <h4 className="font-medium text-[var(--work-ink)]">{pending ? 'El agente necesita una aclaración' : question.status === 'responded' ? 'Respuesta registrada' : 'Pregunta del contexto anterior'}</h4>
    <p className="text-xs text-[var(--work-muted)]">Pregunta bajo contexto {question.context_version}{question.answer_context_version ? ` · respuesta guardada en contexto ${question.answer_context_version}` : ''}</p>
    {pending && <p className="text-[var(--work-muted)]">{question.ready_for_answer ? 'La ejecución se cerró. Responde con tus palabras o elige una opción.' : 'Se está comprobando el cierre de la ejecución. La respuesta se habilitará cuando esté confirmado.'}</p>}
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); submit() }}>
      {question.questions.map(item => <fieldset key={item.id} className="space-y-2" disabled={!pending || !question.ready_for_answer || answer.isPending || intent.current != null}>
        <legend className="whitespace-pre-wrap text-[var(--work-ink)]">{item.question}</legend>
        {item.why_needed && <p className="whitespace-pre-wrap text-[var(--work-muted)]">{item.why_needed}</p>}
        {item.example && <p className="whitespace-pre-wrap text-[var(--work-muted)]">Ejemplo: {item.example}</p>}
        {pending ? <>
          {item.options.length > 0 && <div className="flex flex-wrap gap-2">{item.options.map(option => <button type="button" key={typeof option === 'string' ? option : option.id} className={buttonClass} aria-pressed={typeof option === 'string' ? values[item.id] === option : typeof values[item.id] === 'object' && (values[item.id] as { option_id: string }).option_id === option.id} onClick={() => setValues(previous => ({ ...previous, [item.id]: typeof option === 'string' ? option : { option_id: option.id } }))}>{typeof option === 'string' ? option : option.label}</button>)}</div>}
          <label className="block text-[var(--work-ink)]">Tu respuesta<textarea className={inputClass} rows={2} value={answerText(item, values[item.id])} maxLength={12000} onChange={event => setValues(previous => ({ ...previous, [item.id]: event.target.value }))} /></label>
        </> : <p className="whitespace-pre-wrap text-[var(--work-ink)]">{question.answers?.[item.id] == null ? 'Esta pregunta perdió vigencia; no se envió una respuesta.' : answerText(item, question.answers[item.id])}</p>}
      </fieldset>)}
      {(error || answer.error) && <div role="alert" className="space-y-2 text-[var(--work-error)]"><p>{error || `No se confirmó el guardado. Reenviar conserva las mismas respuestas. ${answer.error?.message}`}</p></div>}
      {pending && <button className={buttonClass} disabled={answer.isPending || (!intent.current && (!question.ready_for_answer || question.questions.some(item => !answerText(item, values[item.id]).trim())))}>{answer.isPending ? 'Guardando…' : intent.current ? 'Reenviar las mismas respuestas' : 'Guardar respuestas'}</button>}
    </form>
    {(answer.isSuccess || question.status === 'responded') && <p role="status" className="text-[var(--work-accent)]">Respuesta guardada. Inicia trabajo cuando quieras usar el nuevo contexto; responder no inicia otra ejecución.</p>}
  </section>
}


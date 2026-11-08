/** Exercise grouped human answers through the actual form and immutable submission contract. @module */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QuestionCard } from '../../src/components/chat/QuestionCard'
import type { RuntimeQuestion } from '../../src/api/runtime'

const mutation = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isSuccess: false, error: null as Error | null }))
vi.mock('../../src/hooks/useRuntime', () => ({ useAnswer: () => mutation }))

/** Retain separate values and labels, two original question IDs and an observed context. */
function question(): RuntimeQuestion {
  return { request_id: 17, run_id: 'original-run', context_version: 3, status: 'pending',
    answers: null, answer_context_version: null, ready_for_answer: true, questions: [
      { id: 'unit', question: '¿Qué unidad?', why_needed: 'Para interpretar el valor', example: '',
        options: [{ id: 'mass_kg', label: 'Kilogramos' }, { id: 'volume_l', label: 'Litros' }] },
      { id: 'scope', question: '¿Qué muestra?', why_needed: '', example: '', options: [] },
    ] }
}

describe('complete and scoped question answers', () => {
  beforeEach(() => { sessionStorage.clear();mutation.mutate.mockReset(); mutation.error = null })

  it('sends option identity plus free text and retries the exact packet after a lost reply', async () => {
    const user = userEvent.setup(), view = render(<QuestionCard projectId={101} taskId={1001} question={question()} />)
    await user.click(screen.getByRole('button', { name: 'Kilogramos' }))
    await user.type(within(screen.getByRole('group', { name: '¿Qué muestra?' })).getByRole('textbox'), 'Muestra del martes')
    await user.click(screen.getByRole('button', { name: 'Guardar respuestas' }))
    const packet = mutation.mutate.mock.calls[0][0]
    expect(packet).toMatchObject({ projectId: 101, taskId: 1001, questionId: 17,
      body: { expected_version: 3, answers: { unit: { option_id: 'mass_kg' }, scope: 'Muestra del martes' } } })
    expect(Object.isFrozen(packet.body.answers.unit)).toBe(true)
    mutation.error = new Error('Conexión interrumpida')
    view.rerender(<QuestionCard projectId={101} taskId={1001} question={question()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('No se confirmó el guardado')
    expect(screen.queryByText(/^Respuesta guardada\./)).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Reenviar las mismas respuestas' }))
    expect(mutation.mutate.mock.calls[1][0]).toBe(packet)
  })

  it('keeps typed text literal and remounts without a previous project answer', async () => {
    const user = userEvent.setup(), view = render(<QuestionCard key="101:17" projectId={101} taskId={1001} question={question()} />)
    await user.type(within(screen.getByRole('group', { name: '¿Qué unidad?' })).getByRole('textbox'), 'mass_kg')
    await user.type(within(screen.getByRole('group', { name: '¿Qué muestra?' })).getByRole('textbox'), 'Otra')
    await user.click(screen.getByRole('button', { name: 'Guardar respuestas' }))
    expect(mutation.mutate.mock.calls[0][0].body.answers.unit).toBe('mass_kg')
    view.rerender(<QuestionCard key="202:18" projectId={202} taskId={2002} question={{ ...question(), request_id: 18 }} />)
    expect(screen.getByRole('button', { name: 'Guardar respuestas' })).toBeDisabled()
    expect(screen.getAllByRole('textbox').every(input => (input as HTMLTextAreaElement).value === '')).toBe(true)
  })
})

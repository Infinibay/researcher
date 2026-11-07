/** Keep paginated pending questions visible without confusing task priority, missing scope or query failure with readiness. @module */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { QuestionInbox } from '../../src/components/chat/QuestionInbox'
import type { Task } from '../../src/types/api'

const state = vi.hoisted(() => ({ query: {} as Record<string, unknown> }))
vi.mock('../../src/hooks/useRuntime', () => ({ useQuestionInbox: () => state.query }))

it('shows both pending requests and opens the selected original task and request', async () => {
  const item = { kind: 'native', task_id: 1001, task_priority: 2, context_version: 3,
    current_context_version: 3, ready_for_answer: true }
  state.query = { data: { pages: [{ total_pending: 2, items: [
    { ...item, request_id: 17, questions: [{ question: '¿Qué unidad?' }, { question: '¿Qué muestra?' }] },
  ] }, { items: [{ ...item, task_id: 1002, request_id: 18, ready_for_answer: false, questions: [{ question: '¿Qué método?' }] }] }] },
    isSuccess: true, hasNextPage: false }
  const choose = vi.fn(), user = userEvent.setup()
  render(<QuestionInbox projectId={101} tasks={[{ id: 1001 }, { id: 1002 }] as Task[]} onChoose={choose} />)
  expect(screen.getByText('2 solicitudes pendientes')).toBeVisible()
  expect(screen.getByText('2 preguntas en esta solicitud')).toBeVisible()
  expect(screen.getByText('Confirmando la parada antes de responder')).toBeVisible()
  await user.click(screen.getByRole('button', { name: /¿Qué método\?/ }))
  expect(choose).toHaveBeenCalledWith(1002, 18)
})

it('keeps a failed or incomplete page distinct from an empty inbox', async () => {
  const fetchNextPage = vi.fn(), refetch = vi.fn(), user = userEvent.setup()
  state.query = { error: new Error('Offline'), isSuccess: false, hasNextPage: true, fetchNextPage, refetch }
  render(<QuestionInbox projectId={202} tasks={[]} onChoose={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('No se pudieron recuperar')
  expect(screen.queryByText('No hay preguntas pendientes en este proyecto.')).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Ver más pendientes' }))
  expect(fetchNextPage).toHaveBeenCalledOnce()
})

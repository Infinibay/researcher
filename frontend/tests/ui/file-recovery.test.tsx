/** Attachment recovery interactions preserve original intent and never infer completion from a failed response. @module */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { FileOperations } from '../../src/components/files/FileOperations'
import { FilesPage } from '../../src/components/pages/FilesPage'
import { useProjectStore } from '../../src/stores/project'

const transport = vi.hoisted(() => ({ ownerFetch: vi.fn() }))
vi.mock('../../src/api/session', () => transport)
const pending = { project_id: 101, operation_key: 'original-key', kind: 'upload', state: 'pending', filename: 'evidence.txt', reference_id: null, receipt: null, created_at: 1794081600, updated_at: 1794081600 }

/** Provide isolated cache and routing while exercising the real hooks and request bodies. */
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  return function Provider({ children }: { children: React.ReactNode }) {
    return <MemoryRouter><QueryClientProvider client={client}>{children}</QueryClientProvider></MemoryRouter>
  }
}

/** Return an actual JSON response so UI checks cover the existing transport error handling. */
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }) }

beforeEach(() => { vi.clearAllMocks(); useProjectStore.setState({ activeProjectId: 101 }) })

it('keeps pending recovery visible while confirmed history opens explicitly without another write', async () => {
  const user = userEvent.setup()
  const completed = Array.from({ length: 49 }, (_, index) => ({ ...pending, operation_key: `published-${index}`, filename: `completed-${index}.txt`, state: 'published' }))
  transport.ownerFetch.mockImplementation(async () => json([pending, ...completed]))
  render(<FileOperations projectId={101} />, { wrapper: wrapper() })
  expect(await screen.findByText('Pendiente de comprobar')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Comprobar y recuperar' })).toBeVisible()
  expect(screen.queryByText('completed-48.txt')).toBeNull()
  const history = screen.getByRole('button', { name: 'Ver historial de cargas y borrados' })
  expect(history).toHaveAttribute('aria-expanded', 'false')
  await user.click(history)
  expect(screen.getByText('completed-48.txt')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Ocultar historial confirmado' }))
  expect(screen.queryByText('completed-48.txt')).toBeNull()
  expect(screen.getByText('Pendiente de comprobar')).toBeVisible()
  expect(transport.ownerFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
})

it('can reach an older pending operation when the first page is entirely pending', async () => {
  const user = userEvent.setup()
  const first = Array.from({ length: 50 }, (_, index) => ({ ...pending, operation_key: `pending-${index}`, filename: `pending-${index}.txt` }))
  transport.ownerFetch.mockImplementation(async path => json(path.includes('offset=50') ? [{ ...pending, operation_key: 'older', filename: 'older.txt' }] : first))
  render(<FileOperations projectId={101} />, { wrapper: wrapper() })
  await user.click(await screen.findByRole('button', { name: 'Ver historial de cargas y borrados' }))
  await user.click(screen.getByRole('button', { name: 'Ver operaciones anteriores' }))
  expect(await screen.findByText('older.txt')).toBeVisible()
  expect(transport.ownerFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
})

it('recovers only the explicitly selected original operation and preserves project scope', async () => {
  const user = userEvent.setup()
  let row = { ...pending }
  transport.ownerFetch.mockImplementation(async (path, options) => {
    if (options?.method === 'POST') { expect(path).toBe('/api/files/operations/original-key/reconcile?project_id=101'); row = { ...row, state: 'published' }; return json(row) }
    return json([row])
  })
  render(<FileOperations projectId={101} />, { wrapper: wrapper() })
  expect(await screen.findByText('Pendiente de comprobar')).toBeVisible()
  expect(transport.ownerFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
  await user.click(screen.getByRole('button', { name: 'Actualizar historial' }))
  await user.click(screen.getByRole('button', { name: 'Comprobar y recuperar' }))
  expect(await screen.findByRole('status')).toHaveTextContent('evidence.txt: Carga registrada.')
  expect(transport.ownerFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
  expect(screen.getByText(/Los resultados son históricos/)).toBeVisible()
})

it('keeps failed recovery visible and closes only the selected incomplete upload without claiming byte deletion', async () => {
  const user = userEvent.setup()
  let row = { ...pending }
  transport.ownerFetch.mockImplementation(async (path, options) => {
    if (options?.method === 'POST') {
      if (path.includes('/reconcile')) return json({ detail: 'La carga está incompleta.' }, 422)
      expect(path).toBe('/api/files/operations/original-key/abandon?project_id=101')
      row = { ...row, state: 'abandoned' }; return json(row)
    }
    return json([row, { ...row, project_id: 202, operation_key: 'foreign', filename: 'FOREIGN SECRET' }])
  })
  render(<FileOperations projectId={101} />, { wrapper: wrapper() })
  await user.click(await screen.findByRole('button', { name: 'Comprobar y recuperar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('La carga está incompleta.')
  expect(screen.queryByText('FOREIGN SECRET')).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Cerrar intento y conservar restos' }))
  expect(await screen.findByRole('status')).toHaveTextContent('restos conservados')
  expect(transport.ownerFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(2)
})

it('reuses the upload identity after uncertain responses and changes it only when the owner changes the intent', async () => {
  const user = userEvent.setup()
  const keys: string[] = []
  transport.ownerFetch.mockImplementation(async (_path, options) => {
    if (options?.method === 'POST') { keys.push(options.body.get('operation_key')); return json({ detail: 'Response lost' }, 500) }
    return json([])
  })
  render(<FilesPage />, { wrapper: wrapper() })
  await user.upload(screen.getByLabelText('Seleccionar archivo'), new File(['original bytes'], 'evidence.txt', { type: 'text/plain' }))
  await user.click(screen.getByRole('button', { name: 'Subir archivo' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Consulta «Cargas y borrados»')
  await user.click(screen.getByRole('button', { name: 'Subir archivo' }))
  await waitFor(() => expect(keys).toHaveLength(2))
  expect(keys[0]).toBeTruthy(); expect(keys[1]).toBe(keys[0])
  await user.type(screen.getByLabelText('Descripción (opcional)'), 'Changed owner intent')
  await user.click(screen.getByRole('button', { name: 'Subir archivo' }))
  await waitFor(() => expect(keys).toHaveLength(3))
  expect(keys[2]).not.toBe(keys[0])
})

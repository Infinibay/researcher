/** Retired project mutations may finish durably without navigating a replacement project view. @module */
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ProjectsPage } from '../../src/components/pages/ProjectsPage'
import { useProjectStore } from '../../src/stores/project'

const api = vi.hoisted(() => ({ workspace: vi.fn(), create: vi.fn(), start: vi.fn(), refetch: vi.fn() }))
vi.mock('../../src/hooks/useProjects', () => ({
  useProjects: () => ({ data: { projects: [{ id: 101, name: 'Atlas', description: 'Primer proyecto', status: 'new' }, { id: 202, name: 'Beta', description: 'Otro contexto', status: 'new' }] }, refetch: api.refetch }),
  useUpdateProject: () => ({}), useDeleteProject: () => ({}), useStopProject: () => ({}),
}))
vi.mock('../../src/api/projectWorkspace', async original => ({ ...await original<typeof import('../../src/api/projectWorkspace')>(), projectWorkspace: api.workspace, sendProjectCreate: api.create }))
vi.mock('../../src/api/projectPlans', async original => ({ ...await original<typeof import('../../src/api/projectPlans')>(), startProjectPlanning: api.start }))

/** Expose the real router destination so a late success cannot hide behind an unchanged component tree. */
function Location() { const value = useLocation(); return <output aria-label="Ruta">{value.pathname}{value.search}</output> }

/** Provide actual mutation/query lifecycles while controlling only server return timing. */
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/projects']}><ProjectsPage /><Location /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  sessionStorage.clear(); vi.clearAllMocks(); useProjectStore.setState({ activeProjectId: 101 })
  api.workspace.mockImplementation(async (id: number) => ({ project_id: id, project: { id, name: id === 101 ? 'Atlas' : 'Beta', description: 'Alcance', status: 'new' }, metadata_sha256: 'a'.repeat(64), activity: [], sources: [{ repository_id: 11, name: 'source', availability: 'available' }], plans: [], reports: [], runtime_available: true, legacy_registered: false, history_present: false }))
})

it('does not redirect a new A visit when the original A planning reply arrives after A→B→A', async () => {
  let finish!: (value: unknown) => void
  api.start.mockImplementation(async () => {
    sessionStorage.setItem('researcher:project-plan-start:v1:101', '{}')
    const receipt = await new Promise(resolve => { finish = resolve })
    sessionStorage.removeItem('researcher:project-plan-start:v1:101')
    return receipt
  })
  const user = userEvent.setup(); mount()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Preparar un plan' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: 'Preparar un plan' }))
  await waitFor(() => expect(api.start).toHaveBeenCalledOnce())
  await user.click(screen.getByRole('button', { name: /^Beta/ }))
  await user.click(screen.getByRole('button', { name: /^Atlas/ }))
  await screen.findByRole('button', { name: 'Recuperar planificación original' })
  await act(async () => finish({ planning_task_id: 1001, run: { run_id: 'original-plan' } }))
  expect(screen.getByLabelText('Ruta')).toHaveTextContent(/^\/projects$/)
  expect(useProjectStore.getState().activeProjectId).toBe(101)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Preparar un plan' })).toBeEnabled())
})

it('keeps the selected project when a retired creation receives its saved resource', async () => {
  let finish!: (value: unknown) => void
  api.create.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const user = userEvent.setup(); mount()
  await user.click(screen.getByRole('button', { name: 'Nuevo proyecto' }))
  await user.type(screen.getByLabelText('Nombre del proyecto'), 'Proyecto nuevo')
  await user.click(screen.getByRole('button', { name: 'Crear proyecto' }))
  await waitFor(() => expect(api.create).toHaveBeenCalledOnce())
  await user.click(screen.getByRole('button', { name: /^Beta/ }))
  await act(async () => finish({ id: 303 }))
  expect(useProjectStore.getState().activeProjectId).toBe(202)
  expect(screen.getByLabelText('Ruta')).toHaveTextContent(/^\/projects$/)
  expect(sessionStorage.getItem('researcher:project-create:v1:0')).toBeNull()
})

it('cannot turn an obsolete recovery control into a new planning admission', async () => {
  sessionStorage.setItem('researcher:project-plan-start:v1:101', '{}')
  const user = userEvent.setup(); mount()
  const recover = await screen.findByRole('button', { name: 'Recuperar planificación original' })
  await waitFor(() => expect(recover).toBeEnabled())
  await screen.findByText(/Sin ejecución nativa activa observada/)
  sessionStorage.removeItem('researcher:project-plan-start:v1:101')
  await user.click(recover)
  expect(api.start).not.toHaveBeenCalled()
  expect(screen.getByText('La solicitud anterior ya recibió confirmación. Consulta sus planes guardados antes de iniciar otra.')).toBeVisible()
})

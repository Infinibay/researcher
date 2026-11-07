/** Repository selection preserves stable IDs across cached reads and historical review names. @module */
import { render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { RepositoriesPage } from '../../src/components/pages/RepositoriesPage'
import { useRepoBranches, useRepoTree, useFileContent } from '../../src/hooks/useGit'
import { useProjectStore } from '../../src/stores/project'

const transport = vi.hoisted(() => ({ ownerFetch: vi.fn() }))
vi.mock('../../src/api/session', () => transport)

/** Isolate the cache while retaining the actual repository hooks and page routing. */
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  return function Provider({ children }: { children: React.ReactNode }) {
    return <MemoryRouter><QueryClientProvider client={client}>{children}</QueryClientProvider></MemoryRouter>
  }
}

/** Return actual transport responses without replacing the hooks under verification. */
function json(value: unknown) { return new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } }) }

beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); useProjectStore.setState({ activeProjectId: 101 }) })

it('keeps repository identity in the transport and cache for branches, trees and file contents', async () => {
  transport.ownerFetch.mockImplementation(async (path: string) => {
    const url = new URL(path, 'http://localhost')
    expect(url.searchParams.get('project_id')).toBe('101')
    return json({ observedRepository: Number(url.searchParams.get('repository_id')) })
  })
  const { result, rerender } = renderHook(({ id }) => ({
    branches: useRepoBranches('app', 101, id),
    tree: useRepoTree('app', 101, 'a'.repeat(40), id),
    file: useFileContent('app', 101, 'original.txt', 'a'.repeat(40), id),
  }), { initialProps: { id: 11 }, wrapper: wrapper() })
  await waitFor(() => Object.values(result.current).forEach(query => expect(query.data).toEqual({ observedRepository: 11 })))
  rerender({ id: 33 })
  await waitFor(() => Object.values(result.current).forEach(query => expect(query.data).toEqual({ observedRepository: 33 })))
  expect(transport.ownerFetch).toHaveBeenCalledTimes(6)
})

it('shows reviews bound to the selected repository even after rename and hides namesakes or unresolved records', async () => {
  const user = userEvent.setup()
  const review = { id: 31, project_id: 101, repo_id: 11, repo_name: 'old-name', summary: 'Original review', status: 'pending' }
  transport.ownerFetch.mockImplementation(async (path: string) => {
    const url = new URL(path, 'http://localhost')
    if (url.pathname === '/api/git/repos') return json([{ id: 11, project_id: 101, name: 'app', local_path: '/sources/original', default_branch: 'main' }])
    if (url.pathname === '/api/projects/101/workspace') return json({ project_id: 101, project: { id: 101 }, sources: [], source_operations: [], workspace_root: '/sources', runtime_available: false })
    if (url.pathname.endsWith('/branches')) return json([{ name: 'main', last_commit_sha: 'a'.repeat(40) }])
    if (url.pathname.endsWith('/tree')) return json([])
    if (url.pathname === '/api/git/prs') return json([
      review,
      { ...review, id: 32, repo_id: 33, repo_name: 'app', summary: 'Replacement repository review' },
      { ...review, id: 33, repo_id: null, repo_name: 'app', summary: 'Unresolved repository review' },
      { ...review, id: 34, project_id: null, repo_name: 'app', summary: 'Unresolved project review' },
      { ...review, id: 35, project_id: 202, repo_name: 'app', summary: 'Foreign project review' },
    ])
    throw new Error(`Unexpected read: ${path}`)
  })
  render(<RepositoriesPage />, { wrapper: wrapper() })
  await user.click(await screen.findByRole('button', { name: /app.*original/ }))
  await user.click(screen.getByRole('button', { name: 'Revisiones' }))
  expect(await screen.findByText('Original review')).toBeVisible()
  for (const label of ['Replacement repository review', 'Unresolved repository review', 'Unresolved project review', 'Foreign project review']) expect(screen.queryByText(label)).toBeNull()
})

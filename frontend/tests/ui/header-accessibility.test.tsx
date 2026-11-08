/** Preserve visible notification labels and actual unread counts for assistive controls. @module */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { Header } from '../../src/components/layout/Header'
import { useActivityFeedStore } from '../../src/stores/activityFeed'
import { useProjectStore } from '../../src/stores/project'

vi.mock('../../src/hooks/useProjects', () => ({useProjects: () => ({data: {projects: []}}), useProject: () => ({data: null})}))
vi.mock('../../src/components/layout/ProjectExecutionControls', () => ({ProjectExecutionControls: () => null}))
vi.mock('../../src/components/layout/ModelSettingsDialog', () => ({ModelSettingsDialog: () => null}))

beforeEach(() => {
  useProjectStore.setState({activeProjectId: null})
  useActivityFeedStore.setState({unreadCount: 0, feedOpen: false})
})

it.each([[4, '4 sin leer'], [120, '99+ sin leer (120 en total)']])('names the visible unread badge and clears it on opening (%s)', async (count, suffix) => {
  useActivityFeedStore.setState({unreadCount: count})
  render(<Header />)
  const control = screen.getByRole('button', {name: `Actividad del proyecto: ${suffix}`, exact: true})
  expect(control).toHaveTextContent(count > 99 ? '99+' : String(count))
  expect(control).toHaveAttribute('aria-pressed', 'false')
  await userEvent.setup().click(control)
  expect(screen.getByRole('button', {name: 'Actividad del proyecto', exact: true})).toHaveAttribute('aria-pressed', 'true')
  expect(useActivityFeedStore.getState().unreadCount).toBe(0)
})

it('keeps a useful accessible name when there are no unread events', () => {
  render(<Header />)
  expect(screen.getByRole('button', {name: 'Actividad del proyecto', exact: true})).toHaveAttribute('aria-pressed', 'false')
})

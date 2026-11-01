import { closeOwnerSession } from '../../api/session'
import { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '../../stores/project'
import { useProjects, useProject, useStartProject, useStopProject } from '../../hooks/useProjects'
import { useActivityFeedStore } from '../../stores/activityFeed'
import { StatusDot } from '../common/StatusDot'

export function Header() {
  const { activeProjectId, setActiveProject } = useProjectStore()
  const { data } = useProjects()
  const { data: activeProject } = useProject(activeProjectId)
  const startProject = useStartProject()
  const stopProject = useStopProject()
  const [sessionError, setSessionError] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const toggleFeed = useActivityFeedStore((s) => s.toggleFeed)
  const feedOpen = useActivityFeedStore((s) => s.feedOpen)
  const unreadCount = useActivityFeedStore((s) => s.unreadCount)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setDropdownOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const projects = data?.projects ?? []
  const isRunning = activeProject?.status === 'executing'
  const projectStatus = activeProject
    ? isRunning
      ? 'active'
      : activeProject.status === 'failed'
        ? 'error'
        : 'inactive'
    : 'inactive'

  return (
    <header className="workspace-header flex h-16 shrink-0 items-center justify-between border-b border-surface-700 bg-surface-900 px-6">
      <button className="workspace-menu-toggle" popoverTarget="workspace-menu">Menú</button>
      <div className="workspace-project-select flex min-w-0 items-center gap-4" ref={ref}>
        <div className="relative">
          <button
            aria-expanded={dropdownOpen} aria-controls="project-options" aria-label="Seleccionar proyecto"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 rounded-md border border-surface-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-surface-800"
          >
            {activeProject ? (
              <>
                <StatusDot status={projectStatus} animated={isRunning} />
                {activeProject.name}
              </>
            ) : (
              <span className="text-slate-500">Elegir proyecto…</span>
            )}
            <svg className="ml-1 h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {dropdownOpen && (
            <div id="project-options" className="absolute left-0 top-full z-30 mt-1 w-64 rounded-md border border-surface-700 bg-surface-800 py-1 shadow-xl">
              {projects.length === 0 && (
                <div className="px-3 py-2 text-sm text-slate-500">No projects</div>
              )}
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setActiveProject(p.id)
                    setDropdownOpen(false)
                  }}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-700 ${
                    p.id === activeProjectId ? 'text-sky-300' : 'text-slate-300'
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {sessionError && <span role="alert" className="text-xs text-red-300">{sessionError}</span>}
        <button onClick={() => {setSessionError(''); closeOwnerSession().catch((error:Error) => setSessionError(error.message))}} className="rounded-md px-3 py-1.5 text-xs text-slate-300 hover:bg-surface-800 focus-visible:ring-2 focus-visible:ring-sky-400">Cerrar sesión</button>
        {activeProject && (
          <>
            <span className="text-xs text-slate-500">{activeProject.status}</span>
            {isRunning ? (
              <button
                onClick={() => stopProject.mutate(activeProject.id)}
                disabled={stopProject.isPending}
                className="rounded-md bg-red-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-900 disabled:opacity-50"
              >
                  Detener proyecto
              </button>
            ) : (
              <button
                onClick={() => startProject.mutate(activeProject.id)}
                disabled={startProject.isPending || activeProject.status === 'completed'}
                className="rounded-md bg-emerald-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-900 disabled:opacity-50"
              >
                  Iniciar proyecto
              </button>
            )}
          </>
        )}

        <button
          onClick={toggleFeed}
          aria-label="Actividad del proyecto" aria-pressed={feedOpen}
          className={`relative rounded-md p-1.5 text-slate-400 hover:bg-surface-800 hover:text-slate-200 ${feedOpen ? 'bg-surface-800 text-sky-400' : ''}`}
          title="Toggle activity feed"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
          </svg>
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
      </div>
    </header>
  )
}

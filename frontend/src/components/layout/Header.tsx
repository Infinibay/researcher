import { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '../../stores/project'
import { useProjects, useProject, useStartProject, useStopProject } from '../../hooks/useProjects'
import { StatusDot } from '../common/StatusDot'

export function Header() {
  const { activeProjectId, setActiveProject } = useProjectStore()
  const { data } = useProjects()
  const { data: activeProject } = useProject(activeProjectId)
  const startProject = useStartProject()
  const stopProject = useStopProject()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

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
    <header className="flex h-16 items-center justify-between border-b border-surface-700 bg-surface-900 px-6">
      <div className="flex items-center gap-4" ref={ref}>
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 rounded-md border border-surface-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-surface-800"
          >
            {activeProject ? (
              <>
                <StatusDot status={projectStatus} animated={isRunning} />
                {activeProject.name}
              </>
            ) : (
              <span className="text-slate-500">Select project...</span>
            )}
            <svg className="ml-1 h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {dropdownOpen && (
            <div className="absolute left-0 top-full z-30 mt-1 w-64 rounded-md border border-surface-700 bg-surface-800 py-1 shadow-xl">
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

      {activeProject && (
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{activeProject.status}</span>
          {isRunning ? (
            <button
              onClick={() => stopProject.mutate(activeProject.id)}
              disabled={stopProject.isPending}
              className="rounded-md bg-red-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={() => startProject.mutate(activeProject.id)}
              disabled={startProject.isPending || activeProject.status === 'completed'}
              className="rounded-md bg-emerald-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              Start
            </button>
          )}
        </div>
      )}
    </header>
  )
}

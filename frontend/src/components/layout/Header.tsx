/** Shared owner session controls and visible project selection for all product routes. @module */
import { closeOwnerSession } from '../../api/session'
import { useWikiDrafts } from '../../stores/wikiDrafts'
import { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '../../stores/project'
import { useProjects, useProject } from '../../hooks/useProjects'
import { useActivityFeedStore } from '../../stores/activityFeed'
import {ModelSettingsDialog} from './ModelSettingsDialog'
import {ProjectExecutionControls} from './ProjectExecutionControls'

/** Identify the visible project in both button text and its accessible name. */
export function Header() {
  const { activeProjectId, setActiveProject } = useProjectStore()
  const { data } = useProjects()
  const { data: activeProject } = useProject(activeProjectId)
  const [sessionError, setSessionError] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [modelSettings,setModelSettings]=useState<{projectId:number|null;projectName:string|null}|null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const toggleFeed = useActivityFeedStore((s) => s.toggleFeed)
  const feedOpen = useActivityFeedStore((s) => s.feedOpen)
  const unreadCount = useActivityFeedStore((s) => s.unreadCount)

  useEffect(() => {
    /** Close this project's selector when a click moves outside its owned region. */
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setDropdownOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  /** Discard actual temporary wiki drafts only after an explicit successful logout. */
  const closeSession = async () => {
    if (Object.values(useWikiDrafts.getState().drafts).some(draft => draft.dirty) && !window.confirm('Hay borradores pendientes. Cerrar sesión descartará el texto temporal. ¿Quieres continuar?')) return
    setSessionError('')
    try { await closeOwnerSession(); useWikiDrafts.getState().clear() }
    catch (error) { setSessionError(error instanceof Error ? error.message : 'No se pudo confirmar el cierre de sesión.') }
  }

  const projects = data?.projects ?? []

  return (
    <header className="workspace-header flex h-16 shrink-0 items-center justify-between border-b border-surface-700 bg-surface-900 px-6">
      <button className="workspace-menu-toggle" popoverTarget="workspace-menu">Menú</button>
      <div className="workspace-project-select flex min-w-0 items-center gap-4" ref={ref}>
        <div className="relative">
          <button
            aria-expanded={dropdownOpen} aria-controls="project-options" aria-label={`Seleccionar proyecto: ${activeProject?.name ?? 'Elegir proyecto…'}`}
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 rounded-md border border-surface-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-surface-800"
          >
            {activeProject ? (
              <>
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

      {activeProjectId !== null && <ProjectExecutionControls key={activeProjectId} projectId={activeProjectId}/>}
      <div className="workspace-owner-actions flex items-center gap-3">
        {sessionError && <span role="alert" className="text-xs text-red-300">{sessionError}</span>}
        <button onClick={closeSession} className="rounded-md px-3 py-1.5 text-xs text-slate-300 hover:bg-surface-800 focus-visible:ring-2 focus-visible:ring-sky-400">Cerrar sesión</button>
        <button onClick={()=>setModelSettings({projectId:activeProjectId,projectName:activeProject?.name??null})}>Modelos</button>
        {modelSettings&&<ModelSettingsDialog {...modelSettings} onClose={()=>setModelSettings(null)}/>}
        <button
          onClick={toggleFeed}
          aria-label={unreadCount > 0 ? `Actividad del proyecto: ${unreadCount > 99 ? '99+' : unreadCount} sin leer${unreadCount > 99 ? ` (${unreadCount} en total)` : ''}` : 'Actividad del proyecto'} aria-pressed={feedOpen}
          className={`relative rounded-md p-1.5 text-slate-400 hover:bg-surface-800 hover:text-slate-200 ${feedOpen ? 'bg-surface-800 text-sky-400' : ''}`}
          title="Actividad del proyecto"
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

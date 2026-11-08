/** Read saved reports, inspect provenance and navigate to task-context correction. @module */

import { useState, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/project'
import { useArtifacts, useArtifact, useArtifactEvidence } from '../../hooks/useArtifacts'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { reportDocument, reportTimestamp, artifactTypes, reportStates } from '../reports/presentation'
import { scopedEntityId } from '../../utils/projectSelection'
import type {Artifact} from '../../types/api'
import '../../styles/tasks.css'
import '../../styles/reports.css'

/** Keep original document flags separate from an exact historical owner decision and its unassessed validity. */
function statusLabel(artifact:Artifact) {
  if(artifact.owner_acceptance)return 'Aceptación guardada · vigencia por comprobar'
  if(artifact.research_status==='accepted')return 'Aceptado · estado del registro, sin decisión vinculada'
  return artifact.research_status ? reportStates[artifact.research_status] ?? artifact.research_status : artifactTypes[artifact.type] ?? artifact.type
}

/** Pair the readable UTC date with a machine timestamp when a valid date was recorded. */
function SavedDate({ value }: { value?: string | number | null }) {
  const date = reportTimestamp(value)
  return date.machine ? <time dateTime={date.machine}>{date.label}</time> : <span>{date.label}</span>
}

/** Require an explicit project and reset report state when the owner changes project. */
export function ReportsPage() {
  const projectId = useProjectStore(s => s.activeProjectId)
  if (!projectId) return <div className="task-workbench report-workbench"><section className="report-idle"><p className="task-eyebrow">INFORMES</p><h1>Elige un proyecto para consultar sus informes</h1><p>Selecciona el proyecto en la cabecera. Aquí podrás leer resultados guardados, contrastar sus fuentes y volver a la tarea para corregir contexto.</p></section></div>
  return <ProjectReports key={projectId} projectId={projectId} />
}

/**
 * Coordinate scoped URL selection, filtered catalog, saved Markdown and exact citations.
 * Corrections belong to the linked task; reading does not revise or accept the report.
 */
function ProjectReports({ projectId }: { projectId: number }) {
  const [params, setParams] = useSearchParams()
  const selectedId = scopedEntityId(params, projectId, 'artifact')
  const foreignLink = params.has('artifact') && Number(params.get('project')) !== projectId
  const [type, setType] = useState('all')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => { const timer = setTimeout(() => setQuery(search), 250); return () => clearTimeout(timer) }, [search])
  const catalog = useArtifacts(projectId, type === 'all' ? undefined : type, query, status || undefined)
  const detail = useArtifact(projectId, selectedId)
  const evidence = useArtifactEvidence(projectId, selectedId, detail.data?.type === 'report')
  const artifacts = [...new Map((catalog.data?.pages.flat() ?? []).map(item => [item.id, item])).values()]
  const title = useRef<HTMLHeadingElement>(null)
  const indexTitle = useRef<HTMLHeadingElement>(null)
  const previous = useRef(selectedId)
  useEffect(() => {
    if (selectedId != null && detail.data?.id === selectedId) title.current?.focus()
    else if (selectedId == null && previous.current != null) (document.getElementById(`report-select-${previous.current}`) ?? indexTitle.current)?.focus()
    previous.current = selectedId
  }, [selectedId, detail.data?.id])
  const choose = (id: number | null) => setParams(id == null ? {} : { project: String(projectId), artifact: String(id) })
  const selected = detail.data
  const citations = evidence.data?.pages.flatMap(page => page.evidence) ?? []
  const totalCitations = evidence.data?.pages[0]?.total_evidence
  const contentHash = evidence.data?.pages[0]?.content_sha256
  return <div className="task-workbench report-workbench" data-has-selection={selectedId != null}>
    <div className="report-layout">
      <section className="report-index" aria-label="Lista de informes y archivos guardados">
        <header className="report-index-header">
          <h2 tabIndex={-1} ref={indexTitle}>Informes</h2>
          <p>Resultados guardados de tu proyecto.</p>
          {foreignLink && <p role="status" className="report-link-warning">Este enlace corresponde a otro proyecto. Elige ese proyecto en la cabecera o abre un informe de la lista actual.</p>}
          <div className="report-types" role="group" aria-label="Tipo de archivo">
            {['all', ...Object.keys(artifactTypes)].map(value => <button type="button" key={value} aria-pressed={type === value} onClick={() => setType(value)}>{value === 'all' ? 'Todos' : artifactTypes[value]}</button>)}
          </div>
          <label>Buscar en informes<input type="search" maxLength={200} value={search} onChange={event => setSearch(event.target.value)} placeholder="Título o descripción" /></label>
          <label>Estado<select value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos los estados</option><option value="draft">Borradores</option><option value="accepted">Aceptados</option><option value="superseded">Sustituidos</option></select></label>
        </header>
        {catalog.isPending ? <p className="report-message" role="status">Consultando informes…</p> : catalog.isError && !catalog.data ? <div className="report-message report-error" role="alert"><p>No se pudo consultar la lista.</p><button className="task-secondary" onClick={() => catalog.refetch()}>Volver a consultar</button></div> : <>
          <ul className="report-list">{artifacts.map(item => <li key={item.id}><button id={`report-select-${item.id}`} type="button" aria-current={selectedId === item.id ? 'true' : undefined} onClick={() => choose(item.id)}>
            <strong>{item.title ?? item.file_path}</strong><span className="report-row-meta"><span className="report-status" data-status={item.research_status ?? 'unknown'}>{statusLabel(item)}</span></span><SavedDate value={item.created_at} />
            {item.description && <span className="report-row-description">{item.description}</span>}
          </button></li>)}</ul>
          {artifacts.length === 0 && <p className="report-message">No hay archivos con estos filtros. Puedes cambiar el tipo, el estado o la búsqueda.</p>}
          <div className="report-index-footer"><p>{artifacts.length} archivos mostrados</p>{catalog.hasNextPage && <button type="button" className="task-secondary" disabled={catalog.isFetchingNextPage} onClick={() => catalog.fetchNextPage()}>{catalog.isFetchingNextPage ? 'Consultando…' : 'Mostrar más archivos'}</button>}{catalog.isFetchNextPageError && <p role="alert">No se pudo consultar la siguiente página. Puedes volver a intentarlo.</p>}</div>
        </>}
      </section>
      <section className="report-reader" aria-label="Lectura del informe">
        {selectedId == null ? <div className="report-idle"><p className="task-eyebrow">LECTURA Y PROCEDENCIA</p><h1>Elige un informe para leerlo</h1><p>Su contenido y sus fuentes se conservan. Un borrador necesita revisión; abrirlo no lo acepta ni inicia trabajo.</p></div> : <>
          <button className="report-back" onClick={() => choose(null)}>Todos los informes</button>
          {detail.isPending ? <p className="report-message" role="status">Cargando el informe…</p> : detail.isError ? <div className="report-message report-error" role="alert"><h1>No se pudo cargar el informe</h1><p>Puede no estar disponible en este proyecto. Vuelve a consultar o regresa a la lista.</p><button className="task-secondary" onClick={() => detail.refetch()}>Volver a consultar</button></div> : selected && <>
            <header className="report-heading">
              <div><p className="task-eyebrow">{selected.type === 'report' ? 'INFORME GUARDADO' : 'ARCHIVO GUARDADO'}</p><h1 ref={title} tabIndex={-1}>{selected.title ?? selected.file_path}</h1><div className="report-meta"><span className="report-status" data-status={selected.research_status ?? 'unknown'}>{selected.owner_acceptance||selected.research_status?statusLabel(selected):'Sin revisión registrada'}</span><SavedDate value={selected.created_at} /></div></div>
              {selected.task_id && <Link className="report-primary report-action-desktop" to={`/tasks?project=${projectId}&task=${selected.task_id}&fromArtifact=${selected.id}`}>Ver tarea y corregir contexto</Link>}
            </header>
            {selected.owner_acceptance&&<section className="report-document-footer" aria-label="Aceptación del resultado">
              <p>Este informe formó parte de un resultado con aceptación guardada para el contexto {selected.owner_acceptance.context_version}. Su vigencia actual se comprueba en la tarea original.</p>
              <p>Estado del documento original: {selected.research_status?reportStates[selected.research_status]??selected.research_status:'Sin estado registrado'}.</p>
              {selected.owner_acceptance.matches_current_content===false&&<p role="alert">El contenido actual no coincide con la versión aceptada. Consulta la decisión y su informe original antes de usarlo.</p>}
              <Link to={`/tasks?project=${projectId}&task=${selected.owner_acceptance.task_id}&fromArtifact=${selected.id}`}>Ver aceptación en la tarea original</Link>
              <details><summary>Identidad de la aceptación</summary><p>Ejecución original: {selected.owner_acceptance.run_id}</p><p>SHA-256 de la versión aceptada</p><code>{selected.owner_acceptance.report_sha256}</code></details>
            </section>}
            <div className="report-document-layout">
              <article className="report-document" aria-label="Contenido guardado">
                {selected.content ? selected.type === 'report' ? <MarkdownRenderer content={reportDocument(selected.content, selected.title ?? selected.file_path)} /> : <pre><code>{selected.content}</code></pre> : <p>No hay contenido guardado para este archivo.</p>}
                <footer className="report-document-footer"><p>Este documento conserva su contenido guardado. Una corrección se registra en la tarea; abrirla no inicia una ejecución ni acepta este resultado.</p>{!selected.task_id && <p>No hay una tarea vinculada registrada para este archivo.</p>}</footer>
              </article>
              {selected.type === 'report' && <aside className="report-evidence" aria-labelledby="report-evidence-title"><h2 id="report-evidence-title">Fuentes del informe</h2>
                {evidence.isPending ? <p role="status">Consultando citas guardadas…</p> : evidence.isError && !evidence.data ? <div role="alert" className="report-error"><p>No se pudieron consultar las fuentes.</p><button className="task-secondary" onClick={() => evidence.refetch()}>Volver a consultar fuentes</button></div> : <>
                  <p className="report-provenance-note">{totalCitations ?? 0} citas registradas. Son capturas guardadas; no una comprobación nueva de las fuentes.</p>
                  {citations.length === 0 ? <p>No hay citas registradas para este archivo. Las menciones en el texto no equivalen a procedencia verificada.</p> : <ol className="report-citations">{citations.map((item, index) => <li key={`${item.finding_id}:${item.source_id}:${item.quote}`}><h3><span>{index + 1}.</span> {item.title || `Fuente ${item.source_id}`}</h3><p className="report-source-kind">{item.kind === 'attachment' ? 'Adjunto capturado' : 'Web capturada'} · Fuente #{item.source_id}</p><blockquote>{item.quote}</blockquote><details><summary>Datos de captura</summary><dl><dt>Ubicación registrada</dt><dd>{item.locator}</dd><dt>Capturada</dt><dd><SavedDate value={item.captured_at} /></dd><dt>SHA-256 del texto capturado</dt><dd>{item.sha256}</dd><dt>Hallazgo vinculado</dt><dd>#{item.finding_id} · {item.finding_status === 'provisional' ? 'provisional' : item.finding_status}</dd></dl></details></li>)}</ol>}
                  {evidence.hasNextPage && <button className="task-secondary" disabled={evidence.isFetchingNextPage} onClick={() => evidence.fetchNextPage()}>{evidence.isFetchingNextPage ? 'Consultando…' : 'Mostrar más citas'}</button>}
                  {evidence.isFetchNextPageError && <p role="alert">No se pudo consultar la siguiente página de citas. Puedes volver a intentarlo.</p>}
                  {contentHash && <details className="report-hash"><summary>Identidad del informe guardado</summary><p>SHA-256 registrado al crearlo</p><code>{contentHash}</code></details>}
                </>}
              </aside>}
            </div>
            {selected.task_id && <Link className="report-primary report-action-mobile" to={`/tasks?project=${projectId}&task=${selected.task_id}&fromArtifact=${selected.id}`}>Ver tarea y corregir contexto</Link>}
          </>}
        </>}
      </section>
    </div>
  </div>
}

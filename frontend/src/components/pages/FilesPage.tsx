/** Reference archive and owner inspector: upload, exact download and explicit text/PDF preview. @module */
import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/project'
import { useFiles, useFile, useFilePreview, useUploadFile, useDeleteFile, downloadReference } from '../../hooks/useFiles'
import type { ReferenceFile } from '../../types/api'
import { scopedEntityId } from '../../utils/projectSelection'
import { formatFileSize } from '../../utils/file'
import { reportTimestamp } from '../reports/presentation'
import { FileOperations } from '../files/FileOperations'
import '../../styles/tasks.css'
import '../../styles/files.css'

/** Render SQLite's UTC upload date without guessing the owner's timezone. */
function UploadDate({ value }: { value?: string | number | null }) {
  const date = reportTimestamp(value)
  return date.machine ? <time dateTime={date.machine}>{date.label}</time> : <span>{date.label}</span>
}

/** Require a visible project and discard local upload/preview state on project changes. */
export function FilesPage() {
  const projectId = useProjectStore(s => s.activeProjectId)
  if (!projectId) return <div className="task-workbench files-workbench"><section className="files-idle"><h1>Elige un proyecto para consultar sus archivos</h1><p>Selecciona el proyecto en la cabecera. Aquí podrás guardar adjuntos y consultar su texto sin iniciar una investigación.</p></section></div>
  return <ProjectFiles key={projectId} projectId={projectId} />
}

/** Keep catalog, deep-link scope and keyboard navigation tied to the selected project. */
function ProjectFiles({ projectId }: { projectId: number }) {
  const [params, setParams] = useSearchParams()
  const selectedId = scopedEntityId(params, projectId, 'file')
  const foreignLink = params.has('file') && Number(params.get('project')) !== projectId
  const [search, setSearch] = useState(''), [query, setQuery] = useState('')
  useEffect(() => { const timer = setTimeout(() => setQuery(search), 250); return () => clearTimeout(timer) }, [search])
  const catalog = useFiles(projectId, query)
  const detail = useFile(projectId, selectedId)
  const files = [...new Map((catalog.data?.pages.flat() ?? []).map(file => [file.id, file])).values()]
  const title = useRef<HTMLHeadingElement>(null), listTitle = useRef<HTMLHeadingElement>(null)
  const previous = useRef(selectedId)
  useEffect(() => {
    if (selectedId != null && detail.data?.id === selectedId) title.current?.focus()
    else if (selectedId == null && previous.current != null) (document.getElementById(`file-select-${previous.current}`) ?? listTitle.current)?.focus()
    previous.current = selectedId
  }, [selectedId, detail.data?.id])
  /** Select only a file in the visible project, retaining a shareable route. */
  const choose = (id: number | null) => setParams(id == null ? {} : { project: String(projectId), file: String(id) })
  return <div className="task-workbench files-workbench" data-has-selection={selectedId != null}>
    <header className="files-heading"><div><h1>Archivos de referencia</h1><p>Adjuntos de este proyecto. Subir un archivo no inicia una investigación.</p></div><Link to={`/tasks?project=${projectId}`}>Ver tareas del proyecto</Link></header>
    <div className="files-uploader"><FileUpload projectId={projectId} onUploaded={file => choose(file.id)} /></div>
    <FileOperations projectId={projectId} />
    {foreignLink && <p role="status" className="files-warning">Este enlace corresponde a otro proyecto. Elige ese proyecto en la cabecera o abre un adjunto de la lista actual.</p>}
    <div className="files-layout">
      <section className="files-index" aria-label="Archivos del proyecto">
        <h2 className="sr-only" ref={listTitle} tabIndex={-1}>Lista de archivos</h2>
        <label className="files-search">Buscar archivos<input type="search" maxLength={200} value={search} onChange={event => setSearch(event.target.value)} placeholder="Nombre o descripción" /></label>
        {catalog.isPending ? <p role="status" className="files-message">Consultando archivos…</p> : catalog.isError && !catalog.data ? <div className="files-message files-error" role="alert"><p>No se pudo consultar la lista.</p><button onClick={() => catalog.refetch()}>Volver a consultar</button></div> : <>
          <div className="files-columns" aria-hidden="true"><span>Nombre · más recientes primero</span><span>Tipo</span><span>Tamaño</span><span>Fecha de subida</span></div>
          <ul className="files-list">{files.map(file => <li key={file.id}><button type="button" id={`file-select-${file.id}`} aria-current={selectedId === file.id ? 'true' : undefined} onClick={() => choose(file.id)}>
            <span className="files-row-name"><strong>{file.filename}</strong>{file.description && <span>{file.description}</span>}</span><span className="files-row-type">{file.mime_type === 'application/pdf' ? 'PDF' : file.mime_type?.startsWith('text/') ? 'Texto' : file.mime_type ?? 'Tipo sin registrar'}</span><span>{file.file_size == null ? 'Sin tamaño registrado' : formatFileSize(file.file_size)}</span><UploadDate value={file.uploaded_at} />
          </button></li>)}</ul>
          {files.length === 0 && <p className="files-message">{query ? 'No hay adjuntos con esta búsqueda. Prueba otro nombre o descripción.' : 'Todavía no hay adjuntos. Puedes subir el primero desde el formulario.'}</p>}
          <footer className="files-list-footer"><p>{files.length} adjuntos mostrados</p>{catalog.hasNextPage && <button disabled={catalog.isFetchingNextPage} onClick={() => catalog.fetchNextPage()}>{catalog.isFetchingNextPage ? 'Consultando…' : 'Mostrar más archivos'}</button>}{catalog.isError && <p role="alert">No se pudo actualizar la lista. <button onClick={() => catalog.refetch()}>Volver a consultar</button></p>}</footer>
        </>}
      </section>
      <section className="files-inspector" aria-label="Detalle del adjunto">
        {selectedId == null ? <div className="files-idle"><h2>Elige un archivo</h2><p>Consulta sus datos, descarga el original o extrae una previa de texto.</p><AttachmentNote /></div> : <><button className="files-back" onClick={() => choose(null)}>Todos los archivos</button>{detail.isPending ? <p role="status">Consultando el adjunto…</p> : detail.isError ? <div className="files-error" role="alert"><h2>No se pudo cargar el adjunto</h2><p>Puede no estar disponible en este proyecto.</p><button onClick={() => detail.refetch()}>Volver a consultar</button></div> : detail.data && <FileInspector key={detail.data.id} file={detail.data} titleRef={title} onDeleted={() => choose(null)} onUpload={() => { choose(null); setTimeout(() => document.getElementById('file-upload-title')?.focus(), 0) }} />}</>}
      </section>
    </div>
  </div>
}

/** Explicit multipart submission, including multi-file rejection and recoverable errors. */
function FileUpload({ projectId, onUploaded }: { projectId: number; onUploaded: (file: ReferenceFile) => void }) {
  const upload = useUploadFile()
  const input = useRef<HTMLInputElement>(null)
  const operationKey = useRef('')
  const [file, setFile] = useState<File | null>(null), [description, setDescription] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState(''), [dragging, setDragging] = useState(false)
  /** Validate the entire selection rather than silently uploading its first item. */
  const select = (list: FileList | null) => {
    operationKey.current = ''
    setError(''); setNotice(''); upload.reset()
    if (!list?.length) return
    if (list.length !== 1) { setFile(null); setError('Selecciona un solo archivo por subida.'); return }
    if (list[0].size > 1_000_000) { setFile(null); setError('El archivo supera el límite de 1.000.000 bytes.'); return }
    setFile(list[0])
  }
  /** Submit once after owner confirmation; retain the file when the result fails. */
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!file || upload.isPending) return
    operationKey.current ||= crypto.randomUUID()
    upload.mutate({ projectId, file, operationKey: operationKey.current, description: description.trim() || undefined }, { onSuccess: result => { setFile(null); setDescription(''); operationKey.current = ''; if (input.current) input.current.value = ''; setNotice(`Carga registrada: ${result.filename}. Su disponibilidad actual se muestra en la lista.`); onUploaded(result) } })
  }
  return <form onSubmit={submit} aria-labelledby="file-upload-title"><h2 id="file-upload-title" tabIndex={-1}>Subir archivo</h2><div className="files-upload-fields">
    <div className="files-drop" data-dragging={dragging} onDragOver={event => { event.preventDefault(); if (!upload.isPending) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!upload.isPending) select(event.dataTransfer.files) }}>
      <p>Arrastra un archivo aquí o <button type="button" disabled={upload.isPending} onClick={() => input.current?.click()}>selecciona un archivo</button></p>
      <input ref={input} type="file" aria-label="Seleccionar archivo" className="sr-only" tabIndex={-1} disabled={upload.isPending} onChange={event => select(event.target.files)} />
      <p className="files-muted">Un archivo por vez · hasta 1.000.000 bytes. Previa disponible para texto UTF-8, PDF con texto, DOCX, CSV, JSON y XML.</p>
      {file && <p className="files-picked">{file.name} · {formatFileSize(file.size)}</p>}
    </div>
    <div className="files-upload-submit"><label>Descripción (opcional)<input value={description} maxLength={2000} disabled={upload.isPending} onChange={event => { operationKey.current = ''; setDescription(event.target.value) }} placeholder="Para qué servirá este adjunto" /></label><button className="files-primary" disabled={!file || upload.isPending} type="submit">{upload.isPending ? 'Guardando adjunto…' : 'Subir archivo'}</button></div>
  </div>{(error || upload.isError) && <p className="files-error" role="alert">{error || upload.error?.message} {upload.isError && 'Consulta «Cargas y borrados» para recuperar este intento. Repetir el mismo envío conserva su identidad.'}</p>}{notice && <p role="status">{notice}</p>}</form>
}

/** Explain the attachment/preview/source distinction using a concrete citation example. */
function AttachmentNote() {
  return <aside className="files-note"><h3>Adjunto, previa y fuente</h3><p>El adjunto es el archivo guardado. La previa extrae su texto para consultarlo; no guarda una fuente para citar.</p><p>Por ejemplo, una tarea puede capturar una versión del PDF y citar su página 2. Esa captura conserva el texto utilizado; no valida sus conclusiones.</p></aside>
}

/** Read exact metadata and a manually requested preview, without inferring agent read history. */
function FileInspector({ file, titleRef, onDeleted, onUpload }: { file: ReferenceFile; titleRef: React.RefObject<HTMLHeadingElement | null>; onDeleted: () => void; onUpload: () => void }) {
  const preview = useFilePreview(file.project_id, file.id)
  const remove = useDeleteFile()
  const [confirm, setConfirm] = useState(false), [downloading, setDownloading] = useState(false), [downloadError, setDownloadError] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { if (confirm) dialog.current?.showModal(); else dialog.current?.close() }, [confirm])
  /** Keep Tab/Shift-Tab inside the modal, including Chromium's browser-chrome boundary. */
  const keepDialogFocus = (event: KeyboardEvent<HTMLDialogElement>) => {
    if (event.key !== 'Tab') return
    const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')]
    const first = buttons[0], last = buttons[buttons.length - 1]
    if (!first) { event.preventDefault(); event.currentTarget.focus(); return }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }
  /** Keep binary errors in the inspector and avoid a raw JSON error in another tab. */
  const download = async () => { setDownloading(true); setDownloadError(''); try { await downloadReference(file) } catch (error) { setDownloadError(error instanceof Error ? error.message : 'No se pudo descargar el adjunto.') } finally { setDownloading(false) } }
  return <>
    <header className="files-detail-heading"><p className="task-eyebrow">ARCHIVOS DE REFERENCIA</p><h2 ref={titleRef} tabIndex={-1}>{file.filename}</h2><span className="files-badge">Adjunto registrado</span>{file.description && <p>{file.description}</p>}</header>
    <dl className="files-metadata"><dt>Referencia</dt><dd>#{file.id}</dd><dt>Tipo de archivo</dt><dd>{file.mime_type ?? 'Sin registrar'}</dd><dt>Tamaño</dt><dd>{file.file_size == null ? 'Sin registrar' : formatFileSize(file.file_size)}</dd><dt>Fecha de subida</dt><dd><UploadDate value={file.uploaded_at} /></dd></dl>
    <div className="files-actions"><button className="files-primary" disabled={downloading} onClick={download}>{downloading ? 'Preparando descarga…' : 'Descargar original'}</button><button className="files-delete" onClick={() => { remove.reset(); setConfirm(true) }}>Eliminar adjunto</button>{downloadError && <p role="alert" className="files-error">{downloadError}</p>}</div>
    <section className="files-preview" aria-labelledby={`preview-title-${file.id}`}><h3 id={`preview-title-${file.id}`}>Previa de texto</h3><p>No comprueba si una tarea leyó este adjunto. Abrir esta vista no inicia una investigación.</p><button className="files-secondary" disabled={preview.isFetching} onClick={() => preview.refetch()}>{preview.isFetching ? 'Extrayendo texto…' : preview.data ? 'Volver a extraer previa' : 'Extraer previa'}</button>
      {preview.isError && <p role="alert" className="files-error">No se pudo extraer la previa. Comprueba el formato y el tamaño; los PDF deben tener texto sin cifrar y los documentos deben ser válidos. Puedes descargar el original. {preview.data && 'Se conserva debajo la previa anterior; no es una extracción nueva.'}</p>}
      {preview.data && <><p className="files-preview-caption">Previa extraída · <UploadDate value={preview.data.previewed_at} />. No es una fuente guardada ni una validación.</p>{preview.data.provenance.extraction === 'pypdf-text-v1' && <p>El texto conserva marcas de página. No se hace OCR ni se verifica el orden visual de tablas o imágenes.</p>}{typeof preview.data.provenance.format === 'string' && <p>Texto normalizado: las citas corresponden a esta extracción, no al formato original. Las marcas indican dónde se extrajo cada fragmento.</p>}{preview.data.provenance.format === 'csv' && <p>La primera fila se conserva y se interpreta como encabezados: es una suposición. Se distinguen las celdas vacías de los valores que faltan.</p>}{preview.data.provenance.format === 'docx' && <p>Se extraen párrafos del cuerpo y texto de las tablas. Se omiten imágenes, notas, encabezados y pies de página; no se comprueba el diseño visual.</p>}{Array.isArray(preview.data.provenance.pages_without_text) && preview.data.provenance.pages_without_text.length > 0 && <p>Páginas sin texto extraíble: {preview.data.provenance.pages_without_text.join(', ')}. Pueden necesitar OCR; la previa conserva sus marcas de página.</p>}<pre tabIndex={0} aria-label="Texto extraído del adjunto">{preview.data.content}</pre><details><summary>Procedencia de esta previa</summary><dl className="files-metadata"><dt>Hash SHA-256 del texto</dt><dd>{preview.data.content_sha256}</dd>{typeof preview.data.provenance.byte_sha256 === 'string' && <><dt>Hash SHA-256 del archivo</dt><dd>{preview.data.provenance.byte_sha256}</dd></>}{typeof preview.data.provenance.page_count === 'number' && <><dt>Páginas del PDF</dt><dd>{preview.data.provenance.page_count}</dd></>}</dl></details></>}
    </section>
    <button className="files-upload-mobile" onClick={onUpload}>Subir otro archivo</button><AttachmentNote /><Link className="files-task-link" to={`/tasks?project=${file.project_id}`}>Ver tareas del proyecto</Link><p className="files-muted">Para usarlo en una tarea, indica el nombre o la referencia #{file.id} en sus instrucciones.</p>
    <dialog ref={dialog} tabIndex={-1} onKeyDown={keepDialogFocus} className="files-dialog" aria-labelledby="file-delete-title" onCancel={event => { if (remove.isPending) event.preventDefault(); else setConfirm(false) }}><h2 id="file-delete-title">Eliminar adjunto</h2><p>Se eliminará «{file.filename}» (referencia #{file.id}) de este proyecto. Las capturas y los informes ya guardados se conservan.</p>{remove.isError && <p role="alert" className="files-error">No se pudo confirmar el borrado. Vuelve a consultar antes de repetirlo.</p>}<div><button autoFocus disabled={remove.isPending} onClick={() => setConfirm(false)}>Conservar adjunto</button><button className="files-danger" disabled={remove.isPending} onClick={() => remove.mutate({ projectId: file.project_id, fileId: file.id }, { onSuccess: () => { setConfirm(false); onDeleted() } })}>{remove.isPending ? 'Eliminando…' : 'Eliminar definitivamente'}</button></div></dialog>
  </>
}

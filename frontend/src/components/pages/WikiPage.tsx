/** Explicitly scoped wiki notebook, retained versions and recoverable revision-guarded drafts. @module */
import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/project'
import { useWikiDrafts } from '../../stores/wikiDrafts'
import { useProject } from '../../hooks/useProjects'
import { useWikiPages, useWikiPage, useSaveWiki, useDeleteWikiPage, useWikiHistory, useWikiRevision } from '../../hooks/useWiki'
import type { WikiNamespace, WikiPage as Page } from '../../types/api'
import { ApiError } from '../../api/client'
import { changeWikiDraft, rebaseWikiDraft, scopedWiki, wikiDraft } from '../wiki/presentation'
import type { WikiDraft } from '../wiki/presentation'
import { reportDocument, reportTimestamp } from '../reports/presentation'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import '../../styles/tasks.css'
import '../../styles/wiki.css'

/** Use the existing reader's explicit UTC convention, with unknown dates left unknown. */
function WikiDate({value}:{value?:string|null}) {
  const date=reportTimestamp(value)
  return date.machine?<time dateTime={date.machine}>{date.label}</time>:<span>{date.label}</span>
}

/** Keep the visible project authoritative; saved drafts live beyond a workspace remount. */
export function WikiPage() {
  const projectId=useProjectStore(s=>s.activeProjectId)
  if(!projectId)return <div className="task-workbench wiki-workbench"><section className="wiki-idle"><h1>Elige un proyecto para consultar sus documentos</h1><p>Selecciona el proyecto en la cabecera. La biblioteca global se elige explícitamente dentro de la lista.</p></section></div>
  return <WikiWorkspace key={projectId} projectId={projectId}/>
}

/** Own URL selection and discard stale navigation callbacks without redirecting a new project/view. */
function WikiWorkspace({projectId}:{projectId:number}) {
  const [params,setParams]=useSearchParams()
  const {data:project}=useProject(projectId)
  const namespace:WikiNamespace=params.get('namespace')==='global'?'global':'project'
  const invalidNamespace=params.has('namespace')&&!['project','global'].includes(params.get('namespace')!)
  const foreign=params.has('project')&&Number(params.get('project'))!==projectId
  const invalidIdentity=params.has('pageId')&&(!Number.isSafeInteger(Number(params.get('pageId')))||Number(params.get('pageId'))<=0)
  const ready=!foreign&&!invalidNamespace&&!invalidIdentity
  const path=params.get('path')??params.get('page')
  const rawOffset=Number(params.get('offset')??0),offset=Number.isSafeInteger(rawOffset)&&rawOffset>=0?rawOffset:0
  const [search,setSearch]=useState(''),[query,setQuery]=useState(''),[notice,setNotice]=useState('')
  const drafts=useWikiDrafts(s=>s.drafts),put=useWikiDrafts(s=>s.put)
  const draftKey=params.get('draft'),candidate=draftKey?drafts[draftKey]:undefined
  const draft=candidate?.projectId===projectId&&candidate.namespace===namespace?candidate:undefined
  const index=useWikiPages(ready?projectId:null,namespace,query)
  const detail=useWikiPage(ready?projectId:null,namespace,path,offset)
  const requestedId=Number(params.get('pageId')??0)
  const page=ready&&scopedWiki(detail.data,projectId,namespace,path??undefined)&&(!requestedId||detail.data.id===requestedId)&&typeof detail.data.content==='string'?detail.data:undefined
  const indexHeading=useRef<HTMLHeadingElement>(null)
  const title=namespace==='global'?'Biblioteca global':`Proyecto ${project?.name??projectId}`
  const stamp=`${projectId}:${namespace}:${path}:${draftKey}:${offset}`
  const active=useRef(stamp),mounted=useRef(true);active.current=stamp
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
  useEffect(()=>{if(ready&&!path&&!draftKey)indexHeading.current?.focus()},[ready,path,draftKey])

  /** Update route identity before late mutation receipts can navigate an abandoned view. */
  const select=(selectedPath:string|null,id?:number,key?:string,scope:WikiNamespace=namespace)=>{
    active.current='navigating'
    const next=new URLSearchParams({project:String(projectId),namespace:scope})
    if(selectedPath!=null)next.set('path',selectedPath)
    if(id)next.set('pageId',String(id))
    if(key)next.set('draft',key)
    setParams(next)
  }
  /** Reuse an existing draft instead of erasing it when its editor is reopened. */
  const edit=(selected?:Page)=>{
    const fresh=wikiDraft(projectId,namespace,selected)
    const chosen=drafts[fresh.key]?.dirty?drafts[fresh.key]:fresh
    put(chosen)
    select(chosen.pageId?chosen.path:null,chosen.pageId??undefined,chosen.key)
  }
  /** A receipt confirms its revision; it must not take over a different selected document. */
  const saved=(result:Page)=>{
    if(!mounted.current||active.current!==stamp||useProjectStore.getState().activeProjectId!==projectId)return
    setNotice(`Se confirmó el guardado de «${result.title}», revisión ${result.revision}.`)
    select(result.path,result.id)
  }
  const rows=index.data?.pages.flatMap(part=>part.pages).filter(row=>scopedWiki(row,projectId,namespace))??[]
  const showDetail=!!path||!!draft
  if(!ready)return <div className="task-workbench wiki-workbench"><section className="wiki-idle"><h1>{foreign?'Este enlace corresponde a otro proyecto':invalidNamespace?'Este enlace usa un ámbito desconocido':'Este enlace no identifica una página válida'}</h1><p>Cambia el proyecto en la cabecera o vuelve a la lista del proyecto actual. No se abrió el documento de otro proyecto.</p><button className="wiki-primary" onClick={()=>select(null,undefined,undefined,'project')}>Documentos del proyecto actual</button><DraftRecovery/></section></div>
  return <div className="task-workbench wiki-workbench" data-detail={showDetail}>
    <nav className="wiki-index" aria-label="Documentos y ámbito">
      <header>{showDetail?<h2 ref={indexHeading} tabIndex={-1}>Documentos</h2>:<h1 ref={indexHeading} tabIndex={-1}>Documentos</h1>}<button className="wiki-primary" onClick={()=>edit()}><span aria-hidden="true">＋ </span>Nueva página</button></header>
      <form onSubmit={(event)=>{event.preventDefault();setQuery(search.trim())}} className="wiki-search"><label>Buscar en los documentos<input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Palabras o frase"/></label><button type="submit">Buscar</button></form>
      <p className="wiki-muted wiki-search-note">Búsqueda por palabras; no comprueba ausencia de ideas similares.</p>
      <div className="wiki-scope"><label htmlFor="wiki-namespace">Mostrar páginas de</label><select id="wiki-namespace" value={namespace} onChange={event=>{setSearch('');setQuery('');select(null,undefined,undefined,event.target.value as WikiNamespace)}}><option value="project">Este proyecto</option><option value="global">Biblioteca global</option></select></div>
      <p className="wiki-scope-note">{namespace==='global'?'Las páginas globales están disponibles desde otros proyectos.':'Las páginas de este proyecto son independientes de la biblioteca global.'}</p>
      {query&&<p className="wiki-filter">Consulta: «{query}» <button onClick={()=>{setQuery('');setSearch('')}}>Quitar búsqueda</button></p>}
      {index.isError&&<div role="alert" className="wiki-error"><p>No se pudo consultar la lista.{rows.length>0?' La lista anterior puede estar desactualizada.':''}</p><button onClick={()=>index.refetch()}>Volver a consultar</button></div>}
      {index.isPending&&<p role="status">Consultando documentos…</p>}
      {!index.isPending&&!index.isError&&!rows.length&&<p className="wiki-list-empty">{query?'No hubo resultados para esta consulta. Prueba otras palabras; no es una prueba de ausencia.':'Todavía no hay páginas en este ámbito. Puedes crear la primera.'}</p>}
      <ul className="wiki-page-list">{rows.map(row=><li key={row.id}><button aria-current={path===row.path&&!draft?'page':undefined} onClick={()=>select(row.path,row.id)}><strong>{row.title}</strong><span>{row.path}</span><small>Revisión {row.revision}</small></button></li>)}</ul>
      {index.hasNextPage&&<button disabled={index.isFetchingNextPage} onClick={()=>index.fetchNextPage()}>{index.isFetchingNextPage?'Consultando…':'Cargar más páginas'}</button>}
      <DraftRecovery/>
    </nav>
    <section className="wiki-pane" aria-label="Documento y edición">
      {showDetail&&<button className="wiki-back" onClick={()=>select(null)}>‹ Volver a documentos</button>}
      {notice&&<p className="wiki-notice" role="status">{notice}</p>}
      {draftKey&&!draft&&<p className="wiki-error" role="alert">El borrador temporal ya no está disponible en esta ventana. Puedes consultar la página guardada o iniciar otro borrador.</p>}
      {draft?<WikiEditor key={draft.key} draft={draft} scopeLabel={title} onSaved={saved} onClose={()=>select(draft.pageId?draft.path:null,draft.pageId??undefined)}/>:path?
        detail.isPending?<p role="status">Consultando la página…</p>:!page?<section className="wiki-idle"><h1>No se pudo consultar la página</h1><p>No se mostró un documento de otro ámbito. Comprueba el enlace o vuelve a consultar.</p><button onClick={()=>detail.refetch()}>Volver a consultar</button>{requestedId>0&&<WikiVersions projectId={projectId} namespace={namespace} pageId={requestedId}/>}</section>:
          <WikiReader key={`${namespace}:${page.id}`} page={page} projectId={projectId} scopeLabel={title} onEdit={()=>edit(page)} onDeleted={()=>{if(mounted.current&&active.current===stamp){setNotice(`Se eliminó «${page.title}»; sus versiones y fuentes capturadas se conservan.`);select(null)}}} onWindow={next=>{const updated=new URLSearchParams(params);updated.set('offset',String(next));active.current='navigating';setParams(updated)}}/>
        :<section className="wiki-idle"><h2>Documentos del proyecto</h2><p>Elige una página o crea una nota. La biblioteca conserva contexto y decisiones; una nota no valida un resultado científico.</p></section>}
    </section>
  </div>
}

/** Offer explicit recovery across projects without exposing other draft titles until expanded. */
function DraftRecovery() {
  const drafts=useWikiDrafts(s=>s.drafts),setProject=useProjectStore(s=>s.setActiveProject)
  const [,setParams]=useSearchParams()
  const entries=Object.values(drafts).filter(draft=>draft.dirty)
  if(!entries.length)return null
  return <details className="wiki-drafts"><summary>Borradores en esta ventana ({entries.length})</summary><p>Se conservan al cambiar de página o proyecto. Son copias temporales; consulta la página para comprobar lo que quedó guardado.</p><ul>{entries.map(draft=><li key={draft.key}><button onClick={()=>{setProject(draft.projectId);setParams(new URLSearchParams({project:String(draft.projectId),namespace:draft.namespace,draft:draft.key,...(draft.pageId?{path:draft.path,pageId:String(draft.pageId)}:{})}))}}>{draft.title||'Borrador sin título'} · {draft.namespace==='global'?'Biblioteca global':`Proyecto ${draft.projectId}`}</button></li>)}</ul></details>
}

/** Read exact saved Markdown and reveal version history or a deliberate guarded delete. */
function WikiReader({page,projectId,scopeLabel,onEdit,onDeleted,onWindow}:{page:Page;projectId:number;scopeLabel:string;onEdit:()=>void;onDeleted:()=>void;onWindow:(offset:number)=>void}) {
  const [deleting,setDeleting]=useState(false),[versionsOpen,setVersionsOpen]=useState(false)
  const heading=useRef<HTMLHeadingElement>(null)
  useEffect(()=>{heading.current?.focus()},[page.id,page.namespace,page.path])
  const complete=(page.offset??0)===0&&page.next_offset==null
  return <article className="wiki-reader">
    <header className="wiki-document-heading"><p className="wiki-eyebrow">{scopeLabel} · {page.path}</p><h1 ref={heading} tabIndex={-1}>{page.title}</h1><div className="wiki-document-meta"><span>{scopeLabel}</span><span>Revisión {page.revision}</span><WikiDate value={page.updated_at}/></div><div className="wiki-actions"><button className="wiki-primary" disabled={!complete} onClick={onEdit}>Editar</button><button aria-expanded={versionsOpen} aria-controls="wiki-version-panel" onClick={()=>setVersionsOpen(!versionsOpen)}>Ver versiones</button><details className="wiki-more"><summary>Más opciones</summary><button className="wiki-quiet" onClick={()=>setDeleting(true)}>Eliminar página</button></details></div></header>
    {page.namespace==='global'&&<p className="wiki-scope-banner">Este documento es global y está disponible desde otros proyectos. Una edición aquí cambia esa página global.</p>}
    {versionsOpen&&<WikiVersions projectId={projectId} namespace={page.namespace} pageId={page.id} forceOpen/>}
    <div className="wiki-document">{page.content?<MarkdownRenderer content={reportDocument(page.content,page.title)}/>:<p>Esta página todavía no tiene texto.</p>}</div>
    {!complete&&<div className="wiki-continuation"><p>Esta vista muestra solo una parte. Lee el resto antes de interpretar el documento completo; la edición está deshabilitada.</p>{(page.offset??0)>0&&<button onClick={()=>onWindow(0)}>Primera parte</button>}{page.next_offset!=null&&<button onClick={()=>onWindow(page.next_offset!)}>Continuar lectura</button>}</div>}
    <p className="wiki-context-note">Este documento conserva contexto; no es una validación científica. Leerlo aquí no crea una fuente de investigación para citar.</p>
    {deleting&&<WikiDeleteDialog page={page} projectId={projectId} onClose={()=>setDeleting(false)} onDeleted={onDeleted}/>}
  </article>
}

/** Preserve full draft text and scope through errors; any overwrite base change is an explicit comparison. */
function WikiEditor({draft,scopeLabel,onSaved,onClose}:{draft:WikiDraft;scopeLabel:string;onSaved:(page:Page)=>void;onClose:()=>void}) {
  const put=useWikiDrafts(s=>s.put),remove=useWikiDrafts(s=>s.remove)
  const save=useSaveWiki(),current=useWikiPage(draft.projectId,draft.namespace,draft.path||null,0,false)
  const [comparison,setComparison]=useState<Page|null>(null),[compareError,setCompareError]=useState(''),[comparing,setComparing]=useState(false)
  const heading=useRef<HTMLHeadingElement>(null)
  useEffect(()=>{heading.current?.focus()},[])
  const bytes=new TextEncoder().encode(draft.content).length
  const valid=!!draft.path.trim()&&!!draft.title.trim()&&bytes<=200000
  /** Save the owned draft unchanged on retry; clear only the receipt's still-matching intent. */
  const submit=(event:FormEvent)=>{event.preventDefault();if(!valid||!draft.dirty||save.isPending)return
    save.mutate(draft,{onSuccess:result=>{if(useWikiDrafts.getState().drafts[draft.key]?.operationKey===draft.operationKey)remove(draft.key);onSaved(result)}})
  }
  /** A fresh successful read supplies a comparison, never an automatic rebase or content merge. */
  const compare=async()=>{setComparing(true);setCompareError('');const result=await current.refetch();setComparing(false)
    if(result.isError||!scopedWiki(result.data,draft.projectId,draft.namespace,draft.path)){setComparison(null);setCompareError('No se pudo consultar la versión guardada. Tu borrador sigue disponible.');return}setComparison(result.data)
  }
  /** Keep edit fields and intent together; no mutable project selector contributes to this request. */
  const change=(field:'path'|'title'|'content'|'parentPath',value:string)=>{put(changeWikiDraft(draft,{[field]:field==='parentPath'?(value||null):value}));save.reset()}
  return <section className="wiki-editor"><p className="wiki-eyebrow">{scopeLabel}</p><h1 ref={heading} tabIndex={-1}>{draft.pageId?'Editar documento':'Nueva página'}</h1><p>{draft.pageId?`Borrador de la revisión ${draft.revision}.`:'Se creará una página nueva en el ámbito indicado.'} El texto se conserva al cambiar de página o proyecto.</p>
    {draft.namespace==='global'&&<p className="wiki-scope-banner">Guardar afecta a la biblioteca global, disponible desde otros proyectos.</p>}
    <form onSubmit={submit}><fieldset disabled={save.isPending}><legend className="sr-only">Contenido del borrador</legend><label>Ruta, por ejemplo arquitectura/contexto<input value={draft.path} readOnly={draft.pageId!=null} maxLength={512} onChange={event=>change('path',event.target.value)}/></label><details><summary>Organización del documento</summary><label>Página superior, opcional<input value={draft.parentPath??''} onChange={event=>change('parentPath',event.target.value)}/></label><p>La página superior debe existir en este mismo ámbito. Dejar el campo vacío quita esa relación.</p></details><label>Título<input value={draft.title} maxLength={1200} onChange={event=>change('title',event.target.value)}/></label><div className="wiki-body-field"><label htmlFor="wiki-body">Texto en Markdown</label><textarea id="wiki-body" value={draft.content} onChange={event=>change('content',event.target.value)} rows={18}/></div><p className={bytes>200000?'wiki-error':'wiki-muted'}>{bytes.toLocaleString('es-AR')} / 200.000 bytes de texto</p><div className="wiki-actions"><button className="wiki-primary" type="submit" disabled={!valid||!draft.dirty||save.isPending}>{save.isPending?'Guardando…':'Guardar página'}</button><button type="button" onClick={onClose}>Cerrar editor y conservar borrador</button></div></fieldset></form>
    {save.isError&&<div className="wiki-error" role="alert"><p>{save.error instanceof ApiError&&save.error.status===409?'La página o el intento cambió. Conservamos tu borrador; compara antes de decidir qué guardar.':'No se pudo confirmar el guardado. Conservamos tu borrador; puedes consultar la versión guardada y repetir el mismo intento sin cambiar su texto.'}</p><details><summary>Detalle del error</summary><p>{save.error.message}</p></details></div>}
    {draft.path&&<button disabled={comparing||save.isPending} onClick={compare}>{comparing?'Consultando versión…':'Comparar con la versión guardada'}</button>}
    {compareError&&<p role="alert" className="wiki-error">{compareError}</p>}
    {comparison&&<section className="wiki-comparison"><h2>Versión consultada · revisión {comparison.revision}</h2><p>{comparison.title}</p><p>Página superior consultada: {comparison.parent_path??'Sin página superior'}. En tu borrador: {draft.parentPath??'Sin página superior'}.</p><pre tabIndex={0} aria-label="Texto de la versión consultada">{comparison.content}</pre>{comparison.next_offset!=null?<p>La comparación está incompleta; no puede usarse como base de edición.</p>:comparison.id===draft.pageId?<><p>Preparar tu borrador sobre esta revisión conservará el título, el texto y la página superior de tu borrador. Al guardar, reemplazará la versión consultada; no combina cambios automáticamente.</p><button disabled={save.isPending} onClick={()=>{put(rebaseWikiDraft(draft,comparison));setComparison(null);save.reset()}}>Preparar mi borrador sobre la revisión {comparison.revision}</button></>:<p>La ruta identifica otra página. Conserva el borrador y elige una ruta nueva; no se reemplaza esa página automáticamente.</p>}</section>}
    <details className="wiki-draft-discard"><summary>Descartar este borrador</summary><p>Se perderán los cambios sin guardar de este borrador.</p><button disabled={save.isPending} onClick={()=>{remove(draft.key);onClose()}}>Descartar cambios sin guardar</button></details><p className="wiki-muted">Borrador temporal en esta ventana. No se guarda en el navegador ni en el servidor hasta pulsar Guardar página.</p>
  </section>
}

/** Load retained revision metadata/text lazily, with independent continuation and no editor mutation. */
function WikiVersions({projectId,namespace,pageId,forceOpen=false}:{projectId:number;namespace:WikiNamespace;pageId:number;forceOpen?:boolean}) {
  const [open,setOpen]=useState(false),[revision,setRevision]=useState<number|null>(null),[offset,setOffset]=useState(0)
  const history=useWikiHistory(projectId,namespace,pageId,open||forceOpen),text=useWikiRevision(projectId,namespace,pageId,revision,offset)
  const row=text.data,scoped=row?.page_id===pageId&&row.namespace===namespace&&(namespace==='global'?row.project_id===null:row.project_id===projectId)&&row.revision===revision
  return <section className="wiki-versions" id="wiki-version-panel">{!forceOpen&&<button aria-expanded={open} onClick={()=>setOpen(!open)}>Ver versiones</button>}{(open||forceOpen)&&<div><h2>Versiones guardadas</h2><p>Una versión histórica puede diferir del documento actual.</p>{history.data?.pages.some(part=>part.revisions.some(item=>item.origin==='legacy_snapshot'))&&<p>La versión importada conserva el estado que existía al actualizar el sistema; no reconstruye cambios anteriores ni supone quién escribió el texto.</p>}{history.isPending&&<p role="status">Consultando versiones…</p>}{history.isError&&<div role="alert"><p>No se pudo consultar el historial.</p><button onClick={()=>history.refetch()}>Volver a consultar</button></div>}<ul>{history.data?.pages.filter(part=>part.namespace===namespace).flatMap(part=>part.revisions).filter(item=>item.page_id===pageId).map(item=><li key={item.revision}><button onClick={()=>{setRevision(item.revision);setOffset(0)}}>Ver texto de revisión {item.revision}</button><WikiDate value={item.recorded_at}/><span>{item.actor??'Autor no registrado'}</span></li>)}</ul>{history.hasNextPage&&<button disabled={history.isFetchingNextPage} onClick={()=>history.fetchNextPage()}>Más versiones</button>}{revision!=null&&<section><h3>Texto de revisión {revision}</h3>{text.isPending?<p role="status">Consultando texto…</p>:text.isError||!scoped?<p role="alert">No se pudo consultar esta revisión.</p>:<><pre tabIndex={0} aria-label={`Texto de revisión ${revision}`}>{row.content}</pre>{row.next_offset!=null&&<button onClick={()=>setOffset(row.next_offset!)}>Continuar revisión {revision}</button>}{offset>0&&<button onClick={()=>setOffset(0)}>Inicio de esta revisión</button>}</>}</section>}</div>}</section>
}

/** Confirm a specific page/revision deletion, trap focus and retain failures for safe reconciliation. */
function WikiDeleteDialog({page,projectId,onClose,onDeleted}:{page:Page;projectId:number;onClose:()=>void;onDeleted:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null),remove=useDeleteWikiPage()
  const [key]=useState(()=>crypto.randomUUID())
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null
    dialog.current?.showModal()
    return()=>{dialog.current?.close();if(previous?.isConnected)previous.focus()}
  },[])
  /** Keep keyboard focus inside the dialog, including Chromium's browser-chrome boundary. */
  const trap=(event:KeyboardEvent<HTMLDialogElement>)=>{if(event.key!=='Tab')return;const buttons=[...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')],first=buttons[0],last=buttons[buttons.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}}
  return <dialog ref={dialog} className="wiki-delete-dialog" aria-labelledby="wiki-delete-title" onKeyDown={trap} onCancel={event=>{event.preventDefault();if(!remove.isPending)onClose()}}><h2 id="wiki-delete-title">Eliminar «{page.title}»</h2><p>{page.namespace==='global'?'Biblioteca global':`Proyecto ${projectId}`} · revisión {page.revision}</p><p>Se elimina la página actual. Sus versiones y las fuentes ya capturadas se conservan. No se elimina otro documento con la misma ruta.</p>{remove.isError&&<p role="alert">No se pudo confirmar el borrado. Consulta la página antes de cambiar de intento. {remove.error.message}</p>}<div className="wiki-actions"><button autoFocus disabled={remove.isPending} onClick={onClose}>Conservar página</button><button className="wiki-danger" disabled={remove.isPending} onClick={()=>remove.mutate({projectId,page,key},{onSuccess:onDeleted})}>{remove.isPending?'Eliminando…':'Eliminar página definitivamente'}</button></div></dialog>
}

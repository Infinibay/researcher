/** Selected source explorer: project-bound registration, immutable Git reading and historical review provenance; setup never follows from merely choosing a source. @module */
import {useEffect,useMemo,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {useProjectStore} from '../../stores/project'
import {useRepos,useRepoBranches,useRepoTree,useFileContent,usePRs} from '../../hooks/useGit'
import {projectWorkspace,projectPackets,prepareProjectSource,sendProjectSource,type ProjectSourceAction} from '../../api/projectWorkspace'
import {buildRepositoryTree,completeRevision,type RepositoryNode} from '../../api/repositoryTree'
import {ApiError} from '../../api/client'
import {RepositoryFile} from '../repositories/RepositoryFile'
import {RepositoryReview} from '../repositories/RepositoryReview'
import {SourceSetup} from '../repositories/SourceSetup'
import {sourcePackets} from '../../api/sourceOperations'
import type {Repository} from '../../types/api'
import '../../styles/tasks.css'
import '../../styles/repositories.css'

/** Bind all editor/source/file/review state to the selected project, disposing it when project scope changes. */
export function RepositoriesPage(){
 const project=useProjectStore(s=>s.activeProjectId)
 return <div className="task-workbench repo-workbench"><h1 className="sr-only">Repositorios</h1>{project===null?<section className="repo-empty"><h2>Elige un proyecto</h2><p>Selecciona el proyecto en la cabecera para consultar sus fuentes, archivos y revisiones.</p></section>:<RepositoryRegister key={project} projectId={project}/>}</div>
}

/** Keep source selection by actual resource ID; missing, foreign or failed observations are never treated as a ready source. */
function RepositoryRegister({projectId}:{projectId:number}){
 const repos=useRepos(projectId),workspace=useQuery({queryKey:['project-workspace',projectId],queryFn:()=>projectWorkspace(projectId),retry:false}),client=useQueryClient()
 const [selected,setSelected]=useState<number|null>(null),[opened,setOpened]=useState(false),[registering,setRegistering]=useState(false),[settingUp,setSettingUp]=useState(false),[packetError,setPacketError]=useState('')
 useEffect(()=>{try{if(projectPackets.load(sessionStorage,'source',projectId))setRegistering(true)}catch(e){setPacketError(e instanceof Error?e.message:'No se pudo recuperar el registro.')}},[projectId])
 useEffect(()=>{try{if(sourcePackets.load(sessionStorage,projectId))setSettingUp(true)}catch(e){setPacketError(e instanceof Error?e.message:'No se pudo recuperar la preparación.')}},[projectId])
 const sources=repos.data?.filter(r=>r.project_id===projectId)??[],source=sources.find(r=>r.id===selected)
 /** Open this exact source and move focus into its reading pane after React commits it. */
 function choose(id:number){setSelected(id);setOpened(true);setRegistering(false);setSettingUp(false);requestAnimationFrame(()=>document.getElementById('repo-source-title')?.focus())}
 /** Return to the actual selected source row on a narrow viewport, without starting another read operation. */
 function back(){setOpened(false);requestAnimationFrame(()=>document.getElementById(`repo-select-${selected}`)?.focus())}
 /** Resolve one source registration receipt before refreshing both source observations and the original project register. */
 function registered(id:number){choose(id);client.invalidateQueries({queryKey:['repos',projectId]});client.invalidateQueries({queryKey:['project-workspace',projectId]})}
 return <div className="repo-layout" data-open={opened||registering||settingUp}>
  <section className="repo-register" aria-label="Fuentes del proyecto"><header><h2>Fuentes</h2><button className="repo-primary" onClick={()=>{setSettingUp(true);setRegistering(false)}}>Preparar fuente Git</button><button onClick={()=>{setRegistering(true);setSettingUp(false)}}>Registrar carpeta existente</button></header><p>Registra y explora fuentes de este proyecto. Elegir una no inicia agentes.</p>
   {repos.isPending&&<p role="status">Consultando fuentes registradas…</p>}{repos.error&&<p role="alert">No se pudo consultar el registro. {repos.error.message}</p>}{repos.data&&sources.length===0&&<p>No hay fuentes registradas en este proyecto.</p>}
   <ul>{sources.map(r=><li key={r.id}><button id={`repo-select-${r.id}`} className="repo-select" aria-pressed={selected===r.id} onClick={()=>choose(r.id)}><strong>{r.name}</strong><span className="repo-path">{r.local_path}</span><small>{workspace.data?.sources.find(s=>s.repository_id===r.id)?.availability==='available'?'Carpeta observada disponible':workspace.data?.sources.find(s=>s.repository_id===r.id)?.availability==='unavailable'?'Carpeta no disponible':'Carpeta sin comprobar'}</small></button></li>)}</ul>
   <button className="repo-link" disabled={repos.isFetching} onClick={()=>{repos.refetch();workspace.refetch()}}>Actualizar fuentes</button><p className="repo-muted">Registrar conserva una carpeta tal como está. Preparar Git permite crear, adoptar o clonar con una solicitud explícita. Una carpeta parcial conserva su operación original; no se sobrescribe para completar el registro.</p>
  </section>
  <div className="repo-reading">{packetError&&<p role="alert">{packetError}</p>}{workspace.error&&<p role="alert">No pudimos observar las carpetas. No deducimos su disponibilidad del registro.</p>}
   {settingUp?<SourceSetup projectId={projectId} root={workspace.data?.workspace_root??null} history={workspace.data?.source_operations??[]} onRegistered={registered} onClose={()=>{setSettingUp(false);setOpened(false)}}/>:registering?<SourceRegistration projectId={projectId} root={workspace.data?.workspace_root??null} available={workspace.data?.runtime_available===true} onRegistered={registered} onClose={()=>{setRegistering(false);setOpened(false)}}/>:source?<RepositoryInspector key={source.id} projectId={projectId} repository={source} onBack={back}/>:<section className="repo-empty"><h2>Una fuente, una revisión concreta</h2><p>Elige una fuente para consultar archivos o decisiones anteriores. La carpeta registrada, el objeto Git leído y la aceptación de sus cambios se comprueban por separado.</p></section>}
  </div>
 </div>
}

/** Reuse the original project source packet so a lost registration reply/reload cannot switch its directory or duplicate its resource identity. */
function SourceRegistration({projectId,root,available,onRegistered,onClose}:{projectId:number;root:string|null;available:boolean;onRegistered:(id:number)=>void;onClose:()=>void}){
 const [saved,setSaved]=useState<ProjectSourceAction|null>(null),[ready,setReady]=useState(false),[name,setName]=useState(''),[path,setPath]=useState(''),[error,setError]=useState('')
 useEffect(()=>{try{const a=projectPackets.load(sessionStorage,'source',projectId);setSaved(a);if(a){setName(a.body.name);setPath(a.body.path)}setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo recuperar la selección original.')}},[projectId])
 const register=useMutation({mutationFn:sendProjectSource,onSuccess:(r,a)=>{projectPackets.clear(sessionStorage,a);onRegistered(r.repository_id)}})
 /** Save the complete immutable selection before the first effect, and retry only that packet until resolved. */
 function submit(){try{let a=saved;if(!a){a=prepareProjectSource(projectId,name,path);projectPackets.save(sessionStorage,a);setSaved(a)}register.mutate(a)}catch(e){setError(e instanceof Error?e.message:'No se pudo conservar la solicitud.')}}
 const rejected=register.error instanceof ApiError&&[409,422].includes(register.error.status)
 return <section className="repo-registration"><button className="repo-link" onClick={onClose}>Volver a fuentes</button><h2>Registrar carpeta existente</h2><p>Selecciona una carpeta que ya existe dentro de la raíz configurada. No se crea Git, clona, cambia origin ni publica su contenido.</p>{root?<p className="repo-path">Raíz del host: {root}</p>:<p>No hay una raíz de trabajo comprobada. Configura el runtime antes de registrar una fuente.</p>}<form className="repo-form" onSubmit={e=>{e.preventDefault();submit()}}><label>Nombre del registro<input value={name} disabled={!!saved} required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,80}" onChange={e=>setName(e.target.value)}/></label><label>Ruta absoluta existente<input value={path} disabled={!!saved} required onChange={e=>setPath(e.target.value)} placeholder={root?`${root}/fuente`:'/ruta/absoluta'}/></label><button className="repo-primary" disabled={!ready||!!error||register.isPending||(!saved&&!available)}>{saved?'Recuperar registro original':'Registrar esta fuente'}</button></form>{register.error&&<p role="alert">{rejected?register.error.message:'No se confirmó el registro. Conservamos la misma selección; recuperarla no crea otra fuente.'}</p>}{saved&&rejected&&<button onClick={()=>{projectPackets.clear(sessionStorage,saved);setSaved(null);register.reset()}}>Descartar registro rechazado</button>}{error&&<p role="alert">{error}</p>}</section>
}

/** Freeze one complete branch observation for tree and blob reads; branch refresh cannot silently move an already opened source document. */
function RepositoryInspector({projectId,repository,onBack}:{projectId:number;repository:Repository;onBack:()=>void}){
 const branches=useRepoBranches(repository.name,projectId),reviews=usePRs(projectId)
 const [branch,setBranch]=useState(repository.default_branch),[revision,setRevision]=useState<string|null>(null),[file,setFile]=useState<string|null>(null),[expanded,setExpanded]=useState(new Set<string>()),[mode,setMode]=useState<'files'|'reviews'>('files'),[review,setReview]=useState<number|null>(null),[fileOpen,setFileOpen]=useState(false),[revealFile,setRevealFile]=useState(false),[revisionError,setRevisionError]=useState('')
 useEffect(()=>{if(!revision){const sha=completeRevision(branches.data?.find(b=>b.name===branch)?.last_commit_sha);if(sha)setRevision(sha)}},[branch,branches.data,revision])
 const tree=useRepoTree(repository.name,projectId,revision),blob=useFileContent(repository.name,projectId,file,revision),nodes=useMemo(()=>buildRepositoryTree(tree.data??[]),[tree.data]),entry=tree.data?.find(n=>n.path===file&&n.type==='blob'),records=reviews.data?.filter(p=>p.repo_name===repository.name&&(p.project_id==null||p.project_id===projectId))??[],selected=records.find(r=>r.id===review)
 useEffect(()=>{if(!revealFile||!fileOpen||mode!=='files'||blob.isFetching||(!blob.data&&!blob.error))return;const frame=requestAnimationFrame(()=>{const pane=document.getElementById('repo-file-pane');if(window.matchMedia('(max-width:700px)').matches)pane?.scrollIntoView({block:'start'});pane?.focus({preventScroll:true});setRevealFile(false)});return()=>cancelAnimationFrame(frame)},[revealFile,fileOpen,mode,blob.isFetching,blob.data,blob.error])
 /** Refresh the actual branch observation first; retain the old immutable read on failure instead of declaring it current. */
 async function refreshRevision(){const fresh=await branches.refetch();if(fresh.error)return;const sha=completeRevision(fresh.data?.find(b=>b.name===branch)?.last_commit_sha);if(!sha){setRevisionError('No se confirmó un commit completo de esa rama. Conservamos la lectura anterior.');return}setRevisionError('');setRevision(sha);setFile(null);setFileOpen(false)}
 /** Select a different branch explicitly; its complete head must be resolved before any tree or content query. */
 function chooseBranch(name:string){setBranch(name);setRevision(null);setFile(null);setFileOpen(false);setExpanded(new Set());setRevisionError('')}
 /** Open a tree-selected blob and move focus to its original-text/document region on mobile. */
 function chooseFile(node:RepositoryNode){setFile(node.path);setFileOpen(true);setRevealFile(true)}
 return <section className="repo-inspector" aria-label="Explorador de la fuente"><button className="repo-back repo-link" onClick={onBack}>Volver a fuentes</button><p className="repo-eyebrow">EXPLORADOR DE FUENTES</p><h2 id="repo-source-title" tabIndex={-1}>{repository.name}</h2><details className="repo-identity"><summary>Carpeta registrada y límites de la consulta</summary><p className="repo-path">{repository.local_path}</p><p className="repo-muted">La lectura Git y los remotos tienen su propia consulta. El registro de la carpeta no prueba su salud.</p></details>
 <div className="repo-revision"><label>Rama<select value={branch} onChange={e=>chooseBranch(e.target.value)}><option value={repository.default_branch}>{repository.default_branch}</option>{branches.data?.filter(b=>b.name!==repository.default_branch).map(b=><option key={b.name} value={b.name}>{b.name}</option>)}</select></label><button disabled={branches.isFetching} onClick={refreshRevision}>Actualizar revisión observada</button>{revision&&<details className="repo-identity"><summary>Revisión {revision.slice(0,12)}</summary><code>{revision}</code><p>Árbol y archivos se consultan en este mismo commit, aunque la rama avance.</p></details>}</div>
 {branches.isPending&&<p role="status">Consultando la revisión de la rama…</p>}{branches.error&&<p role="alert">No se pudo consultar Git. {branches.error.message} Una carpeta registrada puede no tener Git o una primera revisión.</p>}{revisionError&&<p role="alert">{revisionError}</p>}{branches.data&&!revision&&<p>No se confirmó un commit completo. No se eligió otra rama automáticamente.</p>}
 <div className="repo-view-switch" role="group" aria-label="Lectura de la fuente"><button aria-pressed={mode==='files'} onClick={()=>setMode('files')}>Archivo</button><button aria-pressed={mode==='reviews'} onClick={()=>setMode('reviews')}>Revisiones</button></div>
 {mode==='files'?<div className="repo-code-layout" data-file-open={fileOpen}><nav className="repo-tree" aria-label="Archivos de la revisión"><h3>Archivos</h3>{tree.isFetching&&<p role="status">Consultando el árbol…</p>}{tree.error&&<p role="alert">No se pudo consultar el árbol. {tree.error.message}</p>}{tree.data?.length===0&&<p>La revisión consultada no contiene archivos.</p>}{!revision&&<p>El árbol espera una revisión confirmada.</p>}<RepositoryTree nodes={nodes} expanded={expanded} selected={file} onChoose={chooseFile} onToggle={path=>setExpanded(previous=>{const next=new Set(previous);if(next.has(path))next.delete(path);else next.add(path);return next})}/></nav><div id="repo-file-pane" className="repo-file-pane" tabIndex={-1}><p className="repo-file-context">{repository.name} · revisión {revision?.slice(0,12)}</p><button className="repo-back repo-link" onClick={()=>{setFileOpen(false);requestAnimationFrame(()=>document.getElementById(`repo-file-${file}`)?.focus())}}>Volver a archivos</button><RepositoryFile key={`${revision}:${file}`} entry={entry} data={blob.data} pending={blob.isFetching} error={blob.error}/></div></div>:<section aria-label="Revisiones registradas"><h3>Revisiones registradas</h3><p>Estos registros pertenecen al flujo anterior. Su estado no sustituye una aceptación nativa actual.</p>{reviews.isPending&&<p role="status">Consultando revisiones…</p>}{reviews.error&&<p role="alert">No se pudieron consultar las revisiones. {reviews.error.message}</p>}{reviews.data&&records.length===0&&<p>No hay revisiones registradas para esta fuente.</p>}<ul className="repo-review-register">{records.map(r=><li key={r.id}><button aria-pressed={review===r.id} onClick={()=>setReview(r.id)}><strong>{r.summary||`PR #${r.id}`}</strong><span>Estado histórico: {r.status}</span></button></li>)}</ul>{selected&&<RepositoryReview key={selected.id} projectId={projectId} review={selected}/>}</section>}
 <p className="repo-footnote">Leer código no inicia agentes ni publica cambios.</p></section>
}

/** Use native buttons/lists with expanded state rather than an incomplete custom ARIA tree keyboard model. */
function RepositoryTree({nodes,expanded,selected,onToggle,onChoose}:{nodes:RepositoryNode[];expanded:Set<string>;selected:string|null;onToggle:(path:string)=>void;onChoose:(node:RepositoryNode)=>void}){
 return <ul>{nodes.map(n=><li key={n.path}>{n.type==='tree'?<><button aria-expanded={expanded.has(n.path)} onClick={()=>onToggle(n.path)}><span className="repo-node-kind">Carpeta</span> {n.name}</button>{expanded.has(n.path)&&<RepositoryTree nodes={n.children??[]} expanded={expanded} selected={selected} onToggle={onToggle} onChoose={onChoose}/>}</>:<button id={`repo-file-${n.path}`} aria-pressed={selected===n.path} onClick={()=>onChoose(n)}><span className="repo-node-kind">Archivo</span> {n.name}</button>}</li>)}</ul>
}

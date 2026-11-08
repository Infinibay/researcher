/** Selected project dossier: original scope, observed work and exact decisions, using the chosen visual reference and durable owner requests. @module */
import {useEffect,useRef,useState} from 'react'
import {Link,useNavigate} from 'react-router-dom'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {useProjects,useUpdateProject,useDeleteProject,useStopProject} from '../../hooks/useProjects'
import {useProjectStore} from '../../stores/project'
import {ApiError} from '../../api/client'
import {startProjectPlanning} from '../../api/projectPlans'
import {projectWorkspace,projectPackets,prepareProjectCreate,prepareProjectSource,prepareProjectStop,sendProjectCreate,sendProjectSource,sendProjectStop,type ProjectCreateAction,type ProjectSourceAction,type ProjectStopAction,type ProjectWorkspaceState} from '../../api/projectWorkspace'
import type {Project} from '../../types/api'
import '../../styles/tasks.css'
import '../../styles/projects.css'

const statuses:Record<string,string>={new:'Nuevo',planning:'Planificación',executing:'En ejecución (registro)',paused:'Pausado',completed:'Completado (registro)',cancelled:'Cancelado',failed:'Fallo registrado'}
const activityLabels:Record<string,string>={queued:'En cola',running:'Ejecutándose',waiting_input:'Espera tu respuesta',cancelling:'Cierre solicitado',reconciling:'Requiere reconciliación'}

/** Track this view's lifetime so a completed older request cannot redirect a replacement, including A→B→A. */
function useMounted(){
 const mounted=useRef(false)
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
 return mounted
}

/** Preserve global project selection while mobile alternates the same list and dossier; choosing a project never starts work. */
export function ProjectsPage(){
 const projects=useProjects(),active=useProjectStore(s=>s.activeProjectId),setActive=useProjectStore(s=>s.setActiveProject)
 const [opened,setOpened]=useState<number|null>(null),[creating,setCreating]=useState(false),[packetError,setPacketError]=useState('')
 useEffect(()=>{try{if(projectPackets.load(sessionStorage,'create',0))setCreating(true)}catch(e){setPacketError(e instanceof Error?e.message:'No se pudo recuperar la creación pendiente.')}},[])
 const selected=projects.data?.projects.find(p=>p.id===active)
 /** Move focus to the chosen real project rather than preserving a hidden mobile inspector from another scope. */
 function choose(id:number){setActive(id);setOpened(id);setCreating(false);requestAnimationFrame(()=>document.getElementById('project-dossier-title')?.focus())}
 /** Restore the original row after leaving its mobile reading pane. */
 function back(){setOpened(null);requestAnimationFrame(()=>document.getElementById(`project-select-${active}`)?.focus())}
 return <div className="task-workbench project-workbench" data-has-selection={creating||(opened===active&&active!==null)}>
  <h1 className="sr-only">Proyectos</h1>
  <div className="project-layout">
   <section className="project-register" aria-label="Lista de proyectos">
    <header><h2>Proyectos</h2><button className="project-link" onClick={()=>{setCreating(true);setOpened(null)}}>Nuevo proyecto</button></header>
    <p className="project-muted">Elige un proyecto y retoma su contexto.</p>
    {projects.isLoading&&<p role="status">Consultando proyectos guardados…</p>}
    {projects.error&&<div role="alert"><p>No se pudo consultar la lista.</p><button onClick={()=>projects.refetch()}>Volver a consultar</button></div>}
    {projects.data?.projects.length===0&&<p>No hay proyectos. Crea uno con el alcance que quieras investigar; no iniciará agentes por su cuenta.</p>}
    <ul>{projects.data?.projects.map(p=><li key={p.id}><button id={`project-select-${p.id}`} className="project-select" aria-pressed={p.id===active} onClick={()=>choose(p.id)}><strong>{p.name}</strong><span>{p.description||'Sin descripción registrada.'}</span>{p.id===active&&<small>Proyecto seleccionado</small>}</button></li>)}</ul>
    <button className="project-link" disabled={projects.isFetching} onClick={()=>projects.refetch()}>Actualizar lista</button>
   </section>
   <div className="project-reading">
    {packetError&&<p role="alert">{packetError}</p>}
    {creating?<ProjectCreation onClose={()=>setCreating(false)} onCreated={id=>{setCreating(false);choose(id);projects.refetch()}}/>:selected?<ProjectDossier key={selected.id} project={selected} onBack={back}/>:<section className="project-empty"><h2>Un contexto por proyecto</h2><p>Selecciona un proyecto para leer su alcance, consultar actividad y abrir sus planes e informes originales.</p><p>Un estado guardado no demuestra que haya un agente ejecutándose ni que un cierre siga vigente.</p></section>}
   </div>
  </div>
 </div>
}

/** One exact creation request survives reload and response loss without minting duplicate project resources. */
function ProjectCreation({onClose,onCreated}:{onClose:()=>void;onCreated:(id:number)=>void}){
 const mounted=useMounted(),client=useQueryClient()
 const [saved,setSaved]=useState<ProjectCreateAction|null>(null),[ready,setReady]=useState(false),[name,setName]=useState(''),[description,setDescription]=useState(''),[error,setError]=useState('')
 useEffect(()=>{try{const p=projectPackets.load(sessionStorage,'create',0);setSaved(p);if(p){setName(p.body.name);setDescription(p.body.description)}setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo recuperar la creación.')}},[])
 const create=useMutation({mutationFn:sendProjectCreate,onSuccess:(r,a)=>{projectPackets.clear(sessionStorage,a);client.invalidateQueries({queryKey:['projects']});if(mounted.current)onCreated(r.id)}})
 /** Store the full original name/scope before the first POST; a retry always uses that same packet. */
 function submit(){try{let a=saved;if(!a){a=prepareProjectCreate(name.trim(),description);projectPackets.save(sessionStorage,a);setSaved(a)}create.mutate(a)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la solicitud.')}}
 const rejected=create.error instanceof ApiError&&[409,422].includes(create.error.status)
 return <section className="project-dossier"><p className="project-eyebrow">NUEVO CONTEXTO</p><h2>Nuevo proyecto</h2><p>Define qué quieres investigar o construir. Crear el proyecto guarda ese alcance; no crea repositorios ni inicia inferencia.</p><form onSubmit={e=>{e.preventDefault();submit()}} className="project-form"><label>Nombre del proyecto<input value={name} maxLength={255} required disabled={!!saved} onChange={e=>setName(e.target.value)}/></label><label>Alcance inicial<textarea value={description} maxLength={50000} disabled={!!saved} onChange={e=>setDescription(e.target.value)} rows={5}/></label><div className="project-actions"><button className="project-primary" disabled={!ready||!!error||!name.trim()||create.isPending}>{saved?'Recuperar creación original':'Crear proyecto'}</button><button type="button" onClick={onClose}>Volver a proyectos</button></div></form>{create.error&&<p role="alert">{rejected?'La creación fue rechazada; revisa el alcance.':'No se confirmó la creación. Guardamos el nombre y el alcance originales; recuperar su recibo no crea un duplicado.'}</p>}{rejected&&saved&&<button onClick={()=>{projectPackets.clear(sessionStorage,saved);setSaved(null);create.reset()}}>Descartar creación rechazada</button>}{error&&<p role="alert">{error}</p>}</section>
}

/** Show only this selected project's actual observations and original decisions; forms/requests never drift when global selection changes. */
function ProjectDossier({project,onBack}:{project:Project;onBack:()=>void}){
 const mounted=useMounted()
 const client=useQueryClient(),navigate=useNavigate(),update=useUpdateProject(),remove=useDeleteProject(),legacyStop=useStopProject()
 const state=useQuery({queryKey:['project-workspace',project.id],queryFn:()=>projectWorkspace(project.id),refetchInterval:3000,retry:false})
 const [ready,setReady]=useState(false),[stopSaved,setStopSaved]=useState<ProjectStopAction|null>(null),[sourceSaved,setSourceSaved]=useState<ProjectSourceAction|null>(null),[pendingStart,setPendingStart]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[editing,setEditing]=useState(false),[editName,setEditName]=useState(''),[editDescription,setEditDescription]=useState(''),[editScope,setEditScope]=useState(''),[sourceForm,setSourceForm]=useState(false),[sourceName,setSourceName]=useState(''),[sourcePath,setSourcePath]=useState(''),[selectedSource,setSelectedSource]=useState<number|null>(null),[deleting,setDeleting]=useState(false)
 useEffect(()=>{try{setStopSaved(projectPackets.load(sessionStorage,'stop',project.id));const p=projectPackets.load(sessionStorage,'source',project.id);setSourceSaved(p);if(p){setSourceName(p.body.name);setSourcePath(p.body.path);setSourceForm(true)}setPendingStart(sessionStorage.getItem(`researcher:project-plan-start:v1:${project.id}`)!==null);setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudieron recuperar las solicitudes del proyecto.')}},[project.id])
 useEffect(()=>{try{setPendingStart(sessionStorage.getItem(`researcher:project-plan-start:v1:${project.id}`)!==null)}catch{setError('No se pudo consultar la solicitud original de planificación.')}},[project.id,state.dataUpdatedAt])
 const stop=useMutation({mutationFn:sendProjectStop,onSuccess:(_r,a)=>{projectPackets.clear(sessionStorage,a);setStopSaved(null);setNotice('Solicitud de detención guardada para esos intentos. Consulta su cierre; el recibo no demuestra que hayan terminado.');refresh()}})
 const source=useMutation({mutationFn:sendProjectSource,onSuccess:(r,a)=>{projectPackets.clear(sessionStorage,a);setSourceSaved(null);setSourceForm(false);setSelectedSource(r.repository_id);setNotice('Carpeta registrada. No se cambió ningún archivo ni remoto.');refresh()}})
 const start=useMutation({mutationFn:(repository:number|null)=>startProjectPlanning(sessionStorage,project.id,repository),onSuccess:r=>{client.invalidateQueries({queryKey:['project-workspace',project.id]});client.invalidateQueries({queryKey:['projects']});if(!mounted.current||useProjectStore.getState().activeProjectId!==project.id)return;setPendingStart(false);navigate(`/tasks?project=${project.id}&task=${r.planning_task_id}&planRun=${encodeURIComponent(r.run.run_id)}`)},onError:()=>{if(mounted.current)setPendingStart(true)}})
 /** Refresh observations without reissuing a request whose response is unknown. */
 function refresh(){state.refetch();client.invalidateQueries({queryKey:['projects']})}
 /** Freeze the displayed metadata scope so another edit cannot be silently overwritten. */
 function beginEdit(){if(!state.data)return;setEditName(state.data.project.name);setEditDescription(state.data.project.description??'');setEditScope(state.data.metadata_sha256);setEditing(true)}
 /** Keep the original source choice until it has a matching resource receipt. */
 function registerSource(){try{let a=sourceSaved;if(!a){a=prepareProjectSource(project.id,sourceName,sourcePath);projectPackets.save(sessionStorage,a);setSourceSaved(a)}source.mutate(a)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la selección.')}}
 /** Pause/withdraw only the observed work, never enumerate a new target set after response loss. */
 function requestStop(){try{let a=stopSaved;if(!a){if(!state.data?.stop)throw new Error('Consulta la actividad original antes de detener.');a=prepareProjectStop(project.id,state.data.stop);projectPackets.save(sessionStorage,a);setStopSaved(a)}stop.mutate(a)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la detención.')}}
 /** A recovery label cannot mint a new admission if another view already acknowledged its original packet. */
 function requestPlan(repository:number|null){try{if(pendingStart&&sessionStorage.getItem(`researcher:project-plan-start:v1:${project.id}`)===null){setPendingStart(false);setNotice('La solicitud anterior ya recibió confirmación. Consulta sus planes guardados antes de iniciar otra.');return}start.mutate(repository)}catch{setError('No se pudo consultar la solicitud original de planificación.')}}
 const data=state.data,sources=data?.sources??[],chosen=selectedSource??(sources.length===1?sources[0].repository_id:null),usable=sources.some(s=>s.repository_id===chosen&&s.availability==='available'),planning=data?.activity.filter(r=>data.plans.some(p=>p.run_id===r.run_id))??[],working=!!data?.activity.length,blocked=!ready||!!error
 return <section className="project-dossier" aria-label="Expediente del proyecto">
  <button className="project-back project-link" onClick={onBack}>Volver a proyectos</button><p className="project-eyebrow">EXPEDIENTE DEL PROYECTO</p><h2 id="project-dossier-title" tabIndex={-1}>{data?.project.name??project.name}</h2><p className="project-purpose">{data?.project.description||project.description||'No hay alcance registrado. Añade una descripción antes de interpretar qué debe lograrse.'}</p><p className="project-muted">Estado registrado: {statuses[data?.project.status??project.status]??project.status}. La actividad y la vigencia del cierre se consultan por separado.</p>
  <button className="project-link" disabled={!data||blocked} onClick={beginEdit}>Editar alcance</button>
  {editing&&<form className="project-form" onSubmit={e=>{e.preventDefault();update.mutate({id:project.id,name:editName,description:editDescription,expected_scope_sha256:editScope},{onSuccess:()=>{setEditing(false);setNotice('Alcance actualizado. Las propuestas anteriores conservan su contexto original.');refresh()}})}}><label>Nombre registrado<input value={editName} required maxLength={255} onChange={e=>setEditName(e.target.value)}/></label><label>Descripción actual<textarea value={editDescription} rows={4} onChange={e=>setEditDescription(e.target.value)}/></label><p className="project-muted">La descripción original se conserva; esta edición puede dejar planes e informes anteriores como historia.</p><div className="project-actions"><button className="project-primary" disabled={update.isPending||!editName.trim()}>Guardar alcance</button><button type="button" onClick={()=>setEditing(false)}>Cancelar edición</button></div>{update.error&&<p role="alert">{update.error.message}</p>}</form>}
  {state.isPending&&<p role="status">Consultando fuentes, actividad y decisiones guardadas…</p>}{state.error&&<p role="alert">No pudimos observar el proyecto. No inferimos su estado a partir de una etiqueta. {state.error.message}</p>}
  <section className="project-section"><h3>Qué sabemos ahora</h3><button className="project-link" disabled={state.isFetching} onClick={refresh}>Actualizar observación</button>
   {data&&<>{data.activity.length?<ul className="project-records">{data.activity.map(r=><li key={r.run_id}><strong>{activityLabels[r.status]??r.status}</strong><Link to={`/tasks?project=${project.id}&task=${r.task_id}`}>Abrir intento en tarea {r.task_id}</Link></li>)}</ul>:<p>Sin ejecución nativa activa observada. Esto no sustituye la revisión de resultados ni el cierre de un controlador anterior.</p>}{data.legacy_registered&&<div role="status"><p>Hay un controlador anterior registrado. Solicita su cierre y comprueba el resultado antes de planificar.</p><button disabled={legacyStop.isPending||legacyStop.isSuccess} onClick={()=>legacyStop.mutate(project.id,{onSuccess:()=>refresh()})}>Solicitar cierre del controlador anterior</button>{legacyStop.error&&<p role="alert">No se confirmó el cierre. Consulta al dueño original antes de repetir el control.</p>}</div>}</>}
   {stopSaved||data?.stop?<div className="project-control"><p>Detener pausará el despacho observado y retirará sus intentos activos. Los resultados ya cerrados y pendientes de revisión se conservan.</p><button disabled={blocked||stop.isPending} onClick={requestStop}>{stopSaved?'Recuperar la misma detención':'Solicitar detención del trabajo observado'}</button></div>:null}
   {stop.error&&<p role="alert">{stop.error instanceof ApiError&&[409,422].includes(stop.error.status)?'La actividad cambió; consulta la versión actual antes de preparar otra detención.':'No se confirmó la respuesta. Conservamos la detención original; recuperarla no detendrá trabajo nuevo.'}</p>}
   {stopSaved&&stop.error instanceof ApiError&&[409,422].includes(stop.error.status)&&<button onClick={()=>{projectPackets.clear(sessionStorage,stopSaved);setStopSaved(null);stop.reset();refresh()}}>Descartar detención rechazada</button>}
  </section>
  <section className="project-section"><h3>Fuente del trabajo</h3>{!data?<p>Fuentes pendientes de consulta; no sabemos si hay una carpeta registrada.</p>:!sources.length&&<p>No hay una carpeta registrada. Selecciona una fuente existente antes de preparar el primer plan.</p>}<ul className="project-records">{sources.map(s=><li key={s.repository_id}><strong>{s.name} · {s.availability==='available'?'carpeta disponible':s.availability==='unknown'?'sin comprobar':'no disponible'}</strong><p className="project-path">{s.path}</p><p className="project-muted">{s.message}</p></li>)}</ul>
   <button disabled={blocked||!data?.runtime_available} onClick={()=>setSourceForm(!sourceForm)}>Registrar carpeta existente</button>{!data?.runtime_available&&data&&<p>Lectura disponible; el runtime y su raíz de trabajo necesitan configuración para registrar fuentes o iniciar planificación.</p>}
   {sourceForm&&<form className="project-form" onSubmit={e=>{e.preventDefault();registerSource()}}><p>No se creará ni clonará un repositorio. Conservamos los archivos y remotos de la carpeta seleccionada. La inicialización Git es una operación distinta.</p><p className="project-path">Raíz configurada: {data?.workspace_root}</p><label>Nombre del registro<input value={sourceName} required disabled={!!sourceSaved} pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,80}" onChange={e=>setSourceName(e.target.value)}/></label><label>Ruta absoluta de la carpeta<input value={sourcePath} required disabled={!!sourceSaved} onChange={e=>setSourcePath(e.target.value)} placeholder={data?.workspace_root?`${data.workspace_root}/carpeta-existente`:'/ruta/absoluta'}/></label><button className="project-primary" disabled={blocked||source.isPending}>{sourceSaved?'Recuperar el registro original':'Registrar esta fuente'}</button>{source.error&&<p role="alert">{source.error.message} Conservamos la selección original.</p>}{sourceSaved&&source.error instanceof ApiError&&[409,422].includes(source.error.status)&&<button type="button" onClick={()=>{projectPackets.clear(sessionStorage,sourceSaved);setSourceSaved(null);source.reset()}}>Descartar registro rechazado</button>}</form>}
  </section>
  <section className="project-section"><h3>Planificar propone trabajo. Tú decides qué se ejecuta.</h3><p className="project-copy">El agente prepara tareas y dependencias a partir del alcance registrado. Aceptar el plan crea trabajo pendiente; ejecutarlo y aceptar sus resultados son decisiones distintas.</p>
   {!!planning.length&&<p>Ya hay planificación en curso. Ábrela en «Planes y decisiones» para continuar con su contexto original.</p>}
   <label className="project-source-choice">Fuente para el plan<select value={chosen??''} disabled={blocked||pendingStart||working} onChange={e=>setSelectedSource(e.target.value?Number(e.target.value):null)}><option value="">Elige una fuente</option>{sources.map(s=><option key={s.repository_id} value={s.repository_id} disabled={s.availability!=='available'}>{s.name} · {s.availability==='available'?'disponible':'sin comprobar/no disponible'}</option>)}</select></label>
   <button className="project-primary" disabled={blocked||start.isPending||(!pendingStart&&(!data?.runtime_available||!usable||working||data.legacy_registered))} onClick={()=>requestPlan(chosen)}>{pendingStart?'Recuperar planificación original':start.isPending?'Guardando solicitud…':'Preparar un plan'}</button>{working&&!pendingStart&&<p className="project-muted">Consulta el intento activo y su cierre antes de iniciar otro desde este expediente.</p>}{pendingStart&&<p>Se enviará la solicitud ya guardada, con su fuente original; no se reemplazará por una selección nueva.</p>}{start.error&&<p role="alert">No se confirmó la planificación. {start.error.message} La solicitud original se conserva.</p>}
  </section>
  <section className="project-section"><h3>Planes y decisiones guardadas</h3>{data&&!data.plans.length&&<p>No hay planes nativos guardados. No convertimos una tarea cualquiera en el plan del proyecto.</p>}<ul className="project-records">{data?.plans.map(p=><li key={p.run_id}><Link to={`/tasks?project=${project.id}&task=${p.task_id}&planRun=${encodeURIComponent(p.run_id)}`}>{p.title}</Link><p>{!p.context_current?'Contexto original cambió · consultar revisión':p.accepted?'Plan aceptado':p.proposed?'Propuesta guardada · revisar decisión':activityLabels[p.status]??p.status}</p></li>)}</ul>
   <h3>Informes de cierre</h3>{data&&!data.reports.length&&<p>No hay decisiones de cierre registradas, aunque la etiqueta del proyecto indique «completado».</p>}<ul className="project-records">{data?.reports.map(r=><li key={r.operation_key}><Link to={`/tasks?project=${project.id}&task=${r.task_id}&planRun=${encodeURIComponent(r.plan_run_id)}`}>Abrir informe aceptado y su contexto original</Link><p className="project-muted">Corresponde a una versión concreta. Al abrirlo se comprueba si el alcance y la evidencia siguen vigentes.</p></li>)}</ul>
  </section>
  <section className="project-section"><h3>Conservar o eliminar</h3>{data&&(data.history_present?<p>Este proyecto conserva historia de ejecución. Su borrado está protegido; consulta los intentos, informes y fuentes antes de decidir su conservación.</p>:<p>Se puede eliminar un proyecto sin historia de ejecución. Esta acción retira sus datos; no borra carpetas del host.</p>)}<button disabled={blocked||!data||data.history_present||data.legacy_registered||remove.isPending} onClick={()=>setDeleting(true)}>Eliminar proyecto sin historial</button>{remove.error&&<p role="alert">No se eliminó el proyecto. {remove.error.message}</p>}</section>
  <ProjectDeleteDialog open={deleting} name={project.name} working={remove.isPending} onCancel={()=>setDeleting(false)} onConfirm={()=>remove.mutate(project.id,{onSuccess:()=>setDeleting(false)})}/>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status" className="project-notice">{notice}</p>}
 </section>
}

/** Native dialog keeps keyboard focus inside an explicit destructive choice; the server rechecks active/history constraints under its write lock. */
function ProjectDeleteDialog({open,name,working,onCancel,onConfirm}:{open:boolean;name:string;working:boolean;onCancel:()=>void;onConfirm:()=>void}){
 const ref=useRef<HTMLDialogElement>(null)
 useEffect(()=>{const dialog=ref.current;if(open&&!dialog?.open)dialog?.showModal();if(!open&&dialog?.open)dialog.close();return()=>{if(dialog?.open)dialog.close()}},[open])
 return <dialog ref={ref} className="project-delete-dialog" aria-labelledby="project-delete-title" onCancel={e=>{e.preventDefault();onCancel()}}><h2 id="project-delete-title">Eliminar «{name}»</h2><p>Se eliminarán los datos de este proyecto sin historial. Las carpetas del host se conservan. El servidor rechazará la eliminación si apareció trabajo o historia desde la última consulta.</p><div className="project-actions"><button disabled={working} onClick={onCancel} autoFocus>Conservar proyecto</button><button disabled={working} onClick={onConfirm}>Eliminar definitivamente</button></div></dialog>
}

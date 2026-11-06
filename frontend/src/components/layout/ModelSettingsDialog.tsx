/** Owner model configuration within the existing workspace shell, with explicit scope, correctable inheritance and preserved failed edits. @module */
import {useEffect,useRef,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {modelScopeKey,prepareModelSetting,readModelSettings,sendModelSetting,type ModelScope,type ModelSettingView} from '../../api/modelSettings'
import '../../styles/model-settings.css'

/** Name the actual selected scope without assuming the user knows internal actor or inheritance vocabulary. */
function scopeName(source:string){if(source==='host')return 'configuración inicial del equipo';if(source==='global')return 'predeterminado global';if(source.startsWith('project:'))return `proyecto ${source.slice(8)}`;return `agente ${source.split(':').slice(2).join(':')} del proyecto ${source.split(':')[1]}`}

/** Keep the first observed revision with editable fields; background reads cannot erase the owner's draft after an uncertain save. */
function ModelEditor({scope}:{scope:ModelScope}){
 const client=useQueryClient(),key=['model-settings',modelScopeKey(scope)],query=useQuery({queryKey:key,queryFn:()=>readModelSettings(scope),retry:false})
 const [draft,setDraft]=useState<{revision:number;model:string;effort:string;inherit:boolean}|null>(null),[notice,setNotice]=useState(''),[error,setError]=useState('')
 /** Adopt fetched values only initially or after an explicit owner request to replace the current draft. */
 function load(value:ModelSettingView){const profile=value.setting.profile??value.effective;setDraft({revision:value.setting.revision,model:profile.model,effort:profile.reasoning_effort,inherit:value.setting.profile===null});setError('')}
 useEffect(()=>{if(query.data&&draft===null)load(query.data)},[query.data,draft])
 const save=useMutation({mutationFn:sendModelSetting,retry:false,onSuccess:value=>{client.setQueryData(key,value);load(value);setNotice('Configuración guardada para los nuevos intentos. El trabajo en curso conserva su elección original.')},onError:e=>{setError(`${e.message} Tu selección se conserva. Consulta el estado actual antes de decidir si vuelves a guardarla.`);query.refetch()}})
 /** Freeze the original revision and scope before saving either a complete pair or explicit inheritance. */
 function submit(){if(!draft)return;try{setError('');setNotice('');save.mutate(prepareModelSetting(scope,draft.revision,draft.inherit?null:{model:draft.model.trim(),reasoning_effort:draft.effort.trim()}))}catch(e){setError(e instanceof Error?e.message:'Revisa tu selección.')}}
 if(query.isPending)return <p role="status">Consultando esta configuración…</p>
 if(query.error&&!query.data)return <div role="alert"><p>No se pudo consultar este ámbito. {query.error.message}</p><button onClick={()=>query.refetch()}>Volver a consultar</button></div>
 const value=query.data!,catalog=value.catalog,model=catalog?.models.find(item=>item.model===draft?.model)
 return <section aria-label="Configuración del ámbito elegido" className="model-editor">
  <p className="model-scope">Editando: <strong>{scopeName(modelScopeKey(scope))}</strong></p>
  <p>Para un intento nuevo se usaría <strong>{value.effective.model}</strong>, esfuerzo <strong>{value.effective.reasoning_effort}</strong>, desde {scopeName(value.effective.source)}.</p>
  {draft&&<form onSubmit={e=>{e.preventDefault();submit()}}>
   <label className="model-inherit"><input type="checkbox" checked={draft.inherit} disabled={save.isPending} onChange={e=>setDraft({...draft,inherit:e.target.checked})}/>Heredar la configuración del nivel anterior</label>
   <div className="model-fields"><label>Identificador de modelo<input required list="observed-models" value={draft.model} disabled={draft.inherit||save.isPending} maxLength={128} onChange={e=>setDraft({...draft,model:e.target.value})}/></label><datalist id="observed-models">{catalog?.models.map(item=><option key={item.model} value={item.model}>{item.label}</option>)}</datalist>
   <label>Esfuerzo de razonamiento<input required list="observed-efforts" value={draft.effort} disabled={draft.inherit||save.isPending} maxLength={32} onChange={e=>setDraft({...draft,effort:e.target.value})}/></label><datalist id="observed-efforts">{model?.reasoning_efforts.map(effort=><option key={effort} value={effort}/>)}</datalist></div>
   <p className="model-note">{catalog?`Catálogo observado el ${new Date(catalog.observed_at*1000).toLocaleString()}. Codex comprobará de nuevo la pareja elegida antes de enviar un turno.`:'Aún no hemos observado el catálogo de esta cuenta. Puedes escribir el identificador y esfuerzo exactos de Codex; se comprobarán al iniciar. Guardar no envía un turno.'}</p>
   <div className="model-actions"><button className="model-save" disabled={save.isPending}>{save.isPending?'Guardando…':'Guardar configuración'}</button><button type="button" disabled={save.isPending||query.isFetching} onClick={()=>query.refetch()}>Consultar estado actual</button>{(error||value.setting.revision!==draft.revision)&&<button type="button" disabled={save.isPending} onClick={()=>load(value)}>Cargar valores consultados</button>}</div>
  </form>}
  {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
 </section>
}

/** Capture the project when opening; switching the main workspace cannot retarget an already open editor or its pending save. */
export function ModelSettingsDialog({projectId,projectName,onClose}:{projectId:number|null;projectName:string|null;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),[mode,setMode]=useState(projectId?'project':'global'),[actor,setActor]=useState(''),[scope,setScope]=useState<ModelScope>({projectId,actorId:null}),[error,setError]=useState('')
 useEffect(()=>{const node=dialog.current;node?.showModal();return()=>node?.close()},[])
 /** Change editors only through an explicit scope selection, never a background project selection or late query reply. */
 function choose(){try{const next={projectId:mode==='global'?null:projectId,actorId:mode==='actor'?actor.trim():null};modelScopeKey(next);setScope(next);setError('')}catch(e){setError(e instanceof Error?e.message:'Revisa el ámbito.') }}
 return <dialog ref={dialog} className="model-settings-dialog" aria-labelledby="model-settings-title" onCancel={e=>{e.preventDefault();onClose()}}>
  <div className="model-dialog-heading"><div><p className="model-eyebrow">CONFIGURACIÓN DE TRABAJO</p><h2 id="model-settings-title">Modelo y razonamiento</h2></div><button onClick={onClose} aria-label="Cerrar configuración de modelos">Cerrar</button></div>
  <p>Define con qué modelo trabajarán los próximos intentos. El agente del proyecto tiene prioridad sobre el proyecto; después se usan el valor global y el inicial del equipo.</p>
  <p className="model-note">Por ejemplo: puedes usar un modelo para investigar en este proyecto y otro para su revisor. Cambiarlo ahora no modifica un intento que ya empezó. La conexión sigue usando tu suscripción de OpenAI y Ken.</p>
  <form className="model-scope-picker" onSubmit={e=>{e.preventDefault();choose()}}><label>Ámbito<select value={mode} onChange={e=>setMode(e.target.value)}><option value="global">Predeterminado global</option>{projectId&&<><option value="project">Proyecto: {projectName||projectId}</option><option value="actor">Agente de este proyecto</option></>}</select></label>{mode==='actor'&&<label>Identificador del agente<input required value={actor} maxLength={128} onChange={e=>setActor(e.target.value)}/></label>}<button>Abrir este ámbito</button></form>
  {mode==='actor'&&<p className="model-note">Usa el identificador exacto que muestra la ejecución en Tareas. Por ejemplo, las revisiones de código solicitadas desde Tareas usan «code-reviewer». Un nombre de rol distinto no se interpreta como ese agente.</p>}
  {error&&<p role="alert">{error}</p>}<ModelEditor key={modelScopeKey(scope)} scope={scope}/>
 </dialog>
}

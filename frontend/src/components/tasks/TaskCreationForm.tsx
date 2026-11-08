/** Recoverable task metadata form with explicit original input and no automatic native execution. @module */
import {useEffect,useRef,useState,type FormEvent} from 'react'
import {taskCreationPackets,prepareTaskCreation,verifyTaskCreationReceipt,type TaskCreationDraft,type TaskCreationPacket} from '../../api/taskCreation'
import {useCreateTask} from '../../hooks/useTasks'
import type {Epic,Milestone,Task} from '../../types/api'

/** Keep damaged saved state visible and block a new request instead of inventing a replacement key. */
function initial(project:number){try{return {packet:taskCreationPackets.load(window.sessionStorage,project),issue:null as string|null,blocked:false}}catch(error){return {packet:null,issue:error instanceof Error?error.message:'No se pudo recuperar la solicitud.',blocked:true}}}

/** Capture selected metadata before delivery and preserve it across uncertain responses and reloads. */
export function TaskCreationForm({projectId,tasks,groups,milestones,onCreated,onCancel}:{projectId:number;tasks:Task[];groups:Epic[];milestones:Milestone[];onCreated:(task:number)=>void;onCancel:()=>void}){
 const [saved,setSaved]=useState(()=>initial(projectId))
 const [draft,setDraft]=useState<TaskCreationDraft>(()=>saved.packet?.body??{title:'',description:'',type:'research',priority:3,complexity:'medium',epic_id:null,milestone_id:null,depends_on:[]})
 const create=useCreateTask(),alive=useRef(true)
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
 const locked=create.isPending||!!saved.packet||saved.blocked
 /** Preserve the captured body/key on every explicit recovery; a late reply cannot retarget a different mounted project. */
 function send(packet:TaskCreationPacket){
  try{taskCreationPackets.save(window.sessionStorage,packet)}catch(error){setSaved(state=>({...state,issue:error instanceof Error?error.message:'No se guardó la solicitud; no se envió.'}));return}
  setSaved({packet,issue:null,blocked:false})
  create.mutate({...packet.body,depends_on:[...packet.body.depends_on]},{onSuccess:row=>{
   try{verifyTaskCreationReceipt(packet,row);taskCreationPackets.clear(window.sessionStorage,packet)}catch(error){if(alive.current)setSaved(state=>({...state,issue:error instanceof Error?error.message:'No se pudo confirmar el recibo original.'}));return}
   if(alive.current){setSaved({packet:null,issue:null,blocked:false});onCreated(row.id)}
  }})
 }
 /** Create a fresh key only for a new owner intent, never as a reaction to an uncertain response. */
 function submit(event:FormEvent){event.preventDefault();if(locked)return;try{send(prepareTaskCreation(projectId,{...draft,title:draft.title.trim()}))}catch(error){setSaved(state=>({...state,issue:error instanceof Error?error.message:'Revisa los datos de la tarea.'}))}}
 /** Discard only the local request after explicit choice; an existing server task remains untouched. */
 function discard(){if(!saved.packet)return;try{taskCreationPackets.clear(window.sessionStorage,saved.packet);setSaved({packet:null,issue:null,blocked:false});create.reset()}catch(error){setSaved(state=>({...state,issue:error instanceof Error?error.message:'No se pudo retirar la copia local.'}))}}
 return <form className="planning-form task-create-form" aria-label="Crear tarea" onSubmit={submit}>
  <h2>Nueva tarea</h2><p>Describe el objetivo y un ejemplo de entrada y salida. Guardar la tarea no inicia un agente.</p>
  {saved.packet&&<div role="status"><p>Solicitud original guardada: <strong>{saved.packet.body.title}</strong>.</p><p>Si se perdió la respuesta, recupera esta misma creación. El servidor devuelve su registro original.</p><p>Grupo: {saved.packet.body.epic_id??'ninguno'} · Hito: {saved.packet.body.milestone_id??'ninguno'} · Prerrequisitos: {saved.packet.body.depends_on.join(', ')||'ninguno'}.</p></div>}
  <label>Título<input autoFocus required maxLength={255} disabled={locked} value={draft.title} onChange={event=>setDraft({...draft,title:event.target.value})}/></label>
  <label>Descripción<textarea rows={4} maxLength={50000} disabled={locked} value={draft.description} onChange={event=>setDraft({...draft,description:event.target.value})}/></label>
  <label>Tipo<select disabled={locked} value={draft.type} onChange={event=>setDraft({...draft,type:event.target.value})}>{['research','investigation','experimentation','optimization','code','review','test','design','integrate','documentation','bug_fix'].map(value=><option key={value} value={value}>{value}</option>)}</select></label>
  <label>Prioridad<select disabled={locked} value={draft.priority} onChange={event=>setDraft({...draft,priority:Number(event.target.value)})}>{[1,2,3,4,5].map(value=><option key={value}>{value}</option>)}</select></label>
  <label>Complejidad<select disabled={locked} value={draft.complexity} onChange={event=>setDraft({...draft,complexity:event.target.value})}>{['trivial','low','medium','high','very_high'].map(value=><option key={value} value={value}>{value}</option>)}</select></label>
  <label>Grupo<select disabled={locked} value={draft.epic_id??''} onChange={event=>setDraft({...draft,epic_id:Number(event.target.value)||null,milestone_id:null})}><option value="">Sin grupo</option>{groups.map(group=><option key={group.id} value={group.id}>{group.title}</option>)}</select></label>
  <label>Hito<select disabled={locked} value={draft.milestone_id??''} onChange={event=>setDraft({...draft,milestone_id:Number(event.target.value)||null})}><option value="">Sin hito</option>{milestones.filter(item=>draft.epic_id===null||item.epic_id===draft.epic_id).map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
  <fieldset disabled={locked}><legend>Tareas que deben resolverse antes</legend>{tasks.map(task=><label key={task.id}><input type="checkbox" checked={draft.depends_on.includes(task.id)} onChange={event=>setDraft({...draft,depends_on:event.target.checked?[...draft.depends_on,task.id]:draft.depends_on.filter(id=>id!==task.id)})}/>{task.title}</label>)}</fieldset>
  <div className="planning-actions">{saved.packet?<button type="button" className="planning-primary" disabled={create.isPending} onClick={()=>send(saved.packet!)}>Recuperar la misma tarea</button>:<button className="planning-primary" disabled={locked||!draft.title.trim()}>Crear tarea</button>}<button type="button" onClick={onCancel}>Cerrar formulario</button></div>
  {(saved.issue||create.error)&&<div role="alert"><p>No se confirmó la creación. {saved.issue??create.error?.message}</p><p>{saved.packet?'La solicitud original se conserva. Consulta la lista o recupera la misma tarea.':'No se envió una solicitud nueva.'}</p></div>}
  {saved.packet&&<div><p>Retirar la copia local no elimina una tarea ya guardada. Consulta la lista antes de preparar otra solicitud.</p><button type="button" disabled={create.isPending} onClick={discard}>Retirar copia local</button></div>}
 </form>
}

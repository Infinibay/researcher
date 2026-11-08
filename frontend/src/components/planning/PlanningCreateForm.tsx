/** Recoverable owner metadata forms; an uncertain reply retains its original request and never initiates native work. @module */
import {useEffect,useRef,useState,type FormEvent} from 'react'
import {useCreateEpic} from '../../hooks/useEpics'
import {useCreateMilestone} from '../../hooks/useMilestones'
import {planningPackets,preparePlanningGroup,preparePlanningMilestone,type PlanningPacket} from '../../api/planningCommands'

/** Keep damaged local state visible without silently turning it into another mutation. */
function initial(kind:PlanningPacket['kind'],project:number,epic:number){try{return {packet:planningPackets.load(window.sessionStorage,kind,project,epic),issue:null as string|null,blocked:false}}catch(error){return {packet:null,issue:error instanceof Error?error.message:'No se pudo consultar la solicitud guardada.',blocked:true}}}

/** Display the original submitted input and require an explicit recovery after transport uncertainty or reload. */
export function PlanningCreateForm({kind,projectId,epicId=0,onCreated,onCancel}:{kind:PlanningPacket['kind'];projectId:number;epicId?:number;onCreated:(id:number)=>void;onCancel:()=>void}){
 const [saved,setSaved]=useState(()=>initial(kind,projectId,epicId))
 const [title,setTitle]=useState(saved.packet?.body.title??''),[description,setDescription]=useState(saved.packet?.body.description??''),[priority,setPriority]=useState(saved.packet?.kind==='group'?saved.packet.body.priority:2)
 const group=useCreateEpic(),milestone=useCreateMilestone(),alive=useRef(true)
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
 const working=group.isPending||milestone.isPending,error=saved.issue??(kind==='group'?group.error?.message:milestone.error?.message)
 /** Verify scope before clearing a retained request; a late reply cannot select another mounted project. */
 function confirmed(packet:PlanningPacket,row:{id:number;project_id?:number;epic_id?:number;operation_key?:string|null}){
  if(!Number.isSafeInteger(row.id)||row.id<1||row.project_id!==packet.projectId||row.operation_key!==packet.body.operation_key||(packet.kind==='milestone'&&row.epic_id!==packet.epicId)){if(alive.current)setSaved(state=>({...state,issue:'El recibo no corresponde a la solicitud, proyecto o grupo original. Conservamos la solicitud.'}));return}
  try{planningPackets.clear(window.sessionStorage,packet)}catch{if(alive.current)setSaved(state=>({...state,issue:'El servidor confirmó el registro, pero no pudimos retirar su copia local. Consulta el índice.'}));return}
  if(alive.current){setSaved({packet:null,issue:null,blocked:false});onCreated(row.id)}
 }
 /** Save before delivery and transmit the captured original body without changing its operation key. */
 function send(packet:PlanningPacket){
  try{planningPackets.save(window.sessionStorage,packet)}catch(error){setSaved(state=>({...state,issue:error instanceof Error?error.message:'No pudimos guardar la solicitud; no se envió.'}));return}
  setSaved({packet,issue:null,blocked:false})
  if(packet.kind==='group')group.mutate(packet.body,{onSuccess:row=>confirmed(packet,row)})
  else milestone.mutate(packet.body,{onSuccess:row=>confirmed(packet,row)})
 }
 /** Create a new intent only when no unresolved request occupies this scope. */
 function submit(event:FormEvent){event.preventDefault();if(saved.packet||saved.blocked)return;try{send(kind==='group'?preparePlanningGroup(projectId,title.trim(),description,priority):preparePlanningMilestone(projectId,epicId,title.trim()))}catch(error){setSaved(state=>({...state,issue:error instanceof Error?error.message:'Revisa los datos de la solicitud.'}))}}
 /** Discard only this local copy on explicit owner action; this cannot reverse an already committed creation. */
 function discard(){if(!saved.packet)return;try{planningPackets.clear(window.sessionStorage,saved.packet);setSaved({packet:null,issue:null,blocked:false});group.reset();milestone.reset()}catch(error){setSaved(state=>({...state,issue:error instanceof Error?error.message:'No se pudo retirar la copia local.'}))}}
 return <form className="planning-form" onSubmit={submit}>
  {kind==='group'&&<><h2>Nuevo grupo de trabajo</h2><p>Organiza un objetivo en una épica. Crear el grupo no inicia tareas ni autoriza su ejecución.</p></>}
  {saved.packet&&<div role="status"><p>Solicitud original guardada: <strong>{saved.packet.body.title}</strong>.</p><p>Si se perdió la respuesta, recupera esta misma creación. Si ya se guardó en el servidor, recibirás su registro original.</p></div>}
  <label>{kind==='group'?'Nombre del grupo':'Nombre del hito'}<input autoFocus required maxLength={255} disabled={working||!!saved.packet} value={title} onChange={event=>setTitle(event.target.value)}/></label>
  {kind==='group'&&<><label>Descripción<textarea rows={4} disabled={working||!!saved.packet} value={description} onChange={event=>setDescription(event.target.value)}/></label><label>Prioridad<select disabled={working||!!saved.packet} value={priority} onChange={event=>setPriority(Number(event.target.value))}>{[1,2,3,4,5].map(value=><option key={value} value={value}>{value}{value===1?' · más urgente':''}</option>)}</select></label></>}
  <div className="planning-actions">{saved.packet?<button type="button" className="planning-primary" disabled={working} onClick={()=>send(saved.packet!)}>Recuperar la misma creación</button>:<button className="planning-primary" disabled={!title.trim()||working||saved.blocked}>{kind==='group'?'Crear grupo':'Guardar hito'}</button>}<button type="button" onClick={onCancel}>{kind==='group'?'Cancelar':'Cancelar hito'}</button></div>
  {error&&<div role="alert"><p>{error}</p><p>{saved.packet?'La solicitud original se conserva para consultarla o recuperarla.':'En esta vista no se envió una solicitud nueva. Los datos siguen en el formulario.'}</p></div>}
  {saved.packet&&<div><p>Sólo retira la copia local si decidiste preparar otra solicitud. No deshace una creación ya realizada: consulta antes el índice y sus hitos.</p><button type="button" disabled={working} onClick={discard}>Retirar copia local</button></div>}
 </form>
}

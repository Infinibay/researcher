/** Owner notes are readable data; their labels never accept results or change native authority. @module */
import {useEffect,useRef,useState} from 'react'
import {useAddTaskComment,useTaskComments} from '../../hooks/useTasks'
import {prepareTaskComment,taskCommentPackets,verifyTaskCommentReceipt,type TaskCommentPacket} from '../../api/taskComments'
import {MarkdownRenderer} from '../common/MarkdownRenderer'
import {formatRelative} from '../../utils/date'

/** Restore only this task's original request; unreadable storage prevents another append. */
function restored(project:number,task:number){try{return {packet:typeof window==='undefined'?null:taskCommentPackets.load(window.sessionStorage,project,task),issue:'',blocked:false}}catch(error){return {packet:null as TaskCommentPacket|null,issue:error instanceof Error?error.message:'No se pudo recuperar el comentario.',blocked:true}}}

/** Scope the form lifetime so project/task navigation cannot retarget an unresolved request. */
export function TaskCommentsPanel({projectId,taskId}:{projectId:number;taskId:number}){return <TaskCommentForm key={`${projectId}:${taskId}`} projectId={projectId} taskId={taskId}/>}

/** Persist before transport, verify original receipts and keep unavailable and empty histories distinct. */
function TaskCommentForm({projectId,taskId}:{projectId:number;taskId:number}){
 const query=useTaskComments(taskId),add=useAddTaskComment()
 const [saved,setSaved]=useState(()=>restored(projectId,taskId))
 const [text,setText]=useState(()=>saved.packet?.body.content??''),[kind,setKind]=useState<string>(()=>saved.packet?.body.comment_type??'comment')
 const [issue,setIssue]=useState(''),[notice,setNotice]=useState(''),alive=useRef(true)
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
 /** Deliver the persisted original only; a late callback may clear only its exact local copy. */
 function submit(){if(saved.blocked)return;try{const packet=saved.packet??prepareTaskComment(projectId,taskId,text,kind);taskCommentPackets.save(window.sessionStorage,packet);setSaved({packet,issue:'',blocked:false});setIssue('');setNotice('');add.mutate({taskId:packet.taskId,...packet.body},{onSuccess:result=>{try{verifyTaskCommentReceipt(packet,result);taskCommentPackets.clear(window.sessionStorage,packet)}catch(error){if(alive.current)setIssue(error instanceof Error?error.message:'No se confirmó el comentario.');return}if(alive.current){setSaved({packet:null,issue:'',blocked:false});setText('');setNotice('Comentario guardado. No se inició trabajo ni se aceptó ninguna entrega.')}}})}catch(error){setIssue(`${error instanceof Error?error.message:'No se pudo guardar la copia'}; no se envió el comentario.`)}}
 return <section aria-label="Comentarios de la tarea" className="space-y-4">
  <p>Son notas guardadas. Un comentario no acepta una entrega ni retira una ejecución. Para cambiar sus instrucciones, usa «Corregir el contexto» en Trabajo.</p>
  {query.isPending&&<p role="status">Consultando comentarios…</p>}
  {query.error&&<div role="alert"><p>No se pudieron consultar los comentarios. {query.data?.length?'Se conserva la última lectura disponible.':'No se conoce la lista actual.'}</p><button className="task-secondary" onClick={()=>query.refetch()}>Volver a consultar comentarios</button></div>}
  {query.isSuccess&&query.data.length===0&&<p>No hay comentarios.</p>}
  <ol className="space-y-3">{query.data?.map(item=><li key={item.id} className="rounded-md border border-[var(--work-line)] p-3"><p className="text-sm text-[var(--work-muted)]"><strong>{item.author}</strong> · {item.comment_type}{item.created_at?` · ${formatRelative(item.created_at)}`:''}</p><MarkdownRenderer content={item.content}/></li>)}</ol>
  <form className="space-y-3" onSubmit={event=>{event.preventDefault();submit()}}>
   <label className="block" htmlFor={`task-comment-kind-${taskId}`}>Tipo de nota</label><select id={`task-comment-kind-${taskId}`} value={kind} disabled={!!saved.packet||saved.blocked} onChange={event=>setKind(event.target.value)} className="border border-[var(--work-line)] bg-[var(--work-paper)] p-2"><option value="comment">Comentario</option><option value="change_request">Nota sobre cambios</option><option value="approval">Nota de aprobación</option></select>
   <label className="block" htmlFor={`task-comment-${taskId}`}>Tu comentario</label><textarea id={`task-comment-${taskId}`} rows={3} maxLength={50000} value={text} readOnly={!!saved.packet||saved.blocked} onChange={event=>setText(event.target.value)} className="w-full border border-[var(--work-line)] bg-[var(--work-paper)] p-2"/>
   {saved.packet&&<p role="status">Comentario original sin confirmar. Reenviarlo conserva su texto, tipo, tarea y clave.</p>}
   <button className="rounded-md bg-[var(--work-accent-fill)] px-3 py-2 text-white disabled:opacity-50" disabled={saved.blocked||!text.trim()||add.isPending||(!saved.packet&&(query.isPending||!!query.error))}>{add.isPending?'Guardando…':saved.packet?'Reenviar el mismo comentario':'Guardar comentario'}</button>
   {saved.packet&&<div><p>Retirar la copia no elimina un comentario registrado. Consulta la historia antes de preparar otro.</p><button type="button" className="task-secondary" disabled={add.isPending} onClick={()=>{try{taskCommentPackets.clear(window.sessionStorage,saved.packet!);setSaved({packet:null,issue:'',blocked:false});setText('');setIssue('');add.reset()}catch(error){setIssue(error instanceof Error?error.message:'No se pudo retirar la copia.')}}}>Retirar copia del comentario</button></div>}
  </form>
  {(saved.issue||issue||add.error)&&<div role="alert"><p>{saved.issue||issue||`No se confirmó el guardado. ${add.error?.message}`}</p><button className="task-secondary" onClick={()=>query.refetch()}>Consultar comentarios guardados</button></div>}
  {notice&&<p role="status">{notice}</p>}
 </section>
}

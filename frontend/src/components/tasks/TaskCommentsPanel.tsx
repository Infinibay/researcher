/** Owner notes are readable data; their labels never accept results or change native authority. @module */
import {useState} from 'react'
import {useAddTaskComment,useTaskComments} from '../../hooks/useTasks'
import {MarkdownRenderer} from '../common/MarkdownRenderer'
import {formatRelative} from '../../utils/date'

/** Keep unavailable and empty histories distinct, and retain an unconfirmed note for explicit owner review. */
export function TaskCommentsPanel({taskId}:{taskId:number}){
 const query=useTaskComments(taskId),add=useAddTaskComment()
 const [text,setText]=useState(''),[kind,setKind]=useState('comment')
 return <section aria-label="Comentarios de la tarea" className="space-y-4">
  <p>Son notas guardadas. Un comentario no acepta una entrega ni retira una ejecución. Para cambiar sus instrucciones, usa «Corregir el contexto» en Trabajo.</p>
  {query.isPending&&<p role="status">Consultando comentarios…</p>}
  {query.error&&<div role="alert"><p>No se pudieron consultar los comentarios. {query.data?.length?'Se conserva la última lectura disponible.':'No se conoce la lista actual.'}</p><button className="task-secondary" onClick={()=>query.refetch()}>Volver a consultar comentarios</button></div>}
  {query.isSuccess&&query.data.length===0&&<p>No hay comentarios.</p>}
  <ol className="space-y-3">{query.data?.map(item=><li key={item.id} className="rounded-md border border-[var(--work-line)] p-3"><p className="text-sm text-[var(--work-muted)]"><strong>{item.author}</strong> · {item.comment_type}{item.created_at?` · ${formatRelative(item.created_at)}`:''}</p><MarkdownRenderer content={item.content}/></li>)}</ol>
  <label className="block" htmlFor={`task-comment-kind-${taskId}`}>Tipo de nota</label><select id={`task-comment-kind-${taskId}`} value={kind} onChange={event=>setKind(event.target.value)} className="border border-[var(--work-line)] bg-[var(--work-paper)] p-2"><option value="comment">Comentario</option><option value="change_request">Nota sobre cambios</option><option value="approval">Nota de aprobación</option></select>
  <label className="block" htmlFor={`task-comment-${taskId}`}>Tu comentario</label><textarea id={`task-comment-${taskId}`} rows={3} value={text} onChange={event=>setText(event.target.value)} className="w-full border border-[var(--work-line)] bg-[var(--work-paper)] p-2"/>
  <button className="rounded-md bg-[var(--work-accent-fill)] px-3 py-2 text-white disabled:opacity-50" disabled={!text.trim()||add.isPending||query.isPending||!!query.error} onClick={()=>add.mutate({taskId,author:'user',content:text,comment_type:kind},{onSuccess:()=>setText('')})}>Guardar comentario</button>
  {add.error&&<div role="alert"><p>No se confirmó el guardado. La nota podría haberse registrado; consulta la lista antes de repetirla.</p><button className="task-secondary" onClick={()=>query.refetch()}>Consultar comentarios guardados</button></div>}
 </section>
}

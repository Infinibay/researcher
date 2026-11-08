/** Inspect both relation directions and edit confirmed prerequisites without interpreting failed reads as empty data. @module */
import {useState} from 'react'
import {useSetTaskDependencies,useTaskDependencies,useTasks} from '../../hooks/useTasks'

/** Distinguish prerequisite, dependent and other relation kinds while preserving unknown original identifiers. */
export function TaskDependenciesPanel({projectId,taskId}:{projectId:number;taskId:number}){
 const relations=useTaskDependencies(taskId,true),tasks=useTasks(projectId),save=useSetTaskDependencies()
 const [editing,setEditing]=useState(false),[selected,setSelected]=useState<number[]>([])
 if(relations.isPending||tasks.isPending)return <p role="status">Consultando relaciones y tareas…</p>
 if(relations.error||tasks.error||!relations.data||!tasks.data)return <div role="alert"><p>No se pudieron consultar las relaciones. No se conoce el conjunto completo; el editor permanece cerrado.</p><button className="task-secondary" onClick={()=>{relations.refetch();tasks.refetch()}}>Volver a consultar relaciones</button></div>
 const outgoing=relations.data.filter(row=>row.task_id===taskId&&row.dependency_type==='blocks')
 const incoming=relations.data.filter(row=>row.depends_on_task_id===taskId&&row.dependency_type==='blocks')
 const other=relations.data.filter(row=>row.dependency_type!=='blocks')
 const available=tasks.data.filter(task=>task.id!==taskId).map(task=>({id:task.id,title:task.title}))
 for(const id of selected)if(!available.some(task=>task.id===id))available.push({id,title:`Tarea #${id} · nombre no disponible en este proyecto`})
 /** Use only names actually returned for this project; an unresolved ID is never a guessed title. */
 function title(id:number){return tasks.data?.find(task=>task.id===id)?.title??`Tarea #${id} · nombre no disponible en este proyecto`}
 return <section aria-label="Relaciones de la tarea" className="space-y-4">
  <h3>Esta tarea necesita antes</h3>
  {outgoing.length?<ul>{outgoing.map(row=><li key={row.depends_on_task_id}>#{row.depends_on_task_id} · {title(row.depends_on_task_id)}</li>)}</ul>:<p>No hay prerrequisitos declarados.</p>}
  <button className="task-secondary" onClick={()=>{if(!editing)setSelected(outgoing.map(row=>row.depends_on_task_id));setEditing(!editing)}}>{editing?'Cancelar edición':'Editar prerrequisitos'}</button>
  {editing&&<div className="space-y-3"><p>Guardar un cambio crea otro contexto y retira la autoridad del trabajo anterior. No inicia otra ejecución.</p><fieldset className="space-y-2"><legend>Prerrequisitos elegidos</legend>{available.map(task=><label key={task.id} className="flex items-center gap-2"><input type="checkbox" checked={selected.includes(task.id)} onChange={event=>setSelected(event.target.checked?[...selected,task.id]:selected.filter(id=>id!==task.id))}/>{task.title}</label>)}</fieldset><button className="task-secondary" disabled={save.isPending} onClick={()=>save.mutate({taskId,depends_on:selected,dependency_type:'blocks'},{onSuccess:()=>setEditing(false)})}>Guardar dependencias</button></div>}
  {save.error&&<div role="alert"><p>No se confirmó el cambio. {save.error.message}</p><button className="task-secondary" onClick={()=>relations.refetch()}>Consultar relaciones guardadas</button></div>}
  <h3>Tareas que necesitan ésta</h3>
  {incoming.length?<ul>{incoming.map(row=><li key={row.task_id}>#{row.task_id} · {title(row.task_id)}</li>)}</ul>:<p>No hay tareas dependientes declaradas.</p>}
  {!!other.length&&<section><h3>Otros vínculos guardados</h3><ul>{other.map(row=><li key={`${row.task_id}:${row.depends_on_task_id}`}>#{row.task_id} → #{row.depends_on_task_id} · {row.dependency_type==='related_to'?'Relación':row.dependency_type==='parent_of'?'Tarea subordinada':row.dependency_type}</li>)}</ul></section>}
 </section>
}

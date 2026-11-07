/** Recover committed observations and invalidate only the selected project's owner reads. @module */
import {useEffect} from 'react'
import {useQueryClient} from '@tanstack/react-query'
import {wsManager} from '../api/websocket'
import type {StreamStatus} from '../api/websocket'
import {queryBelongsToProject} from '../api/events'
import type {DurableEvent} from '../api/events'
import {useProjectStore} from '../stores/project'
import {useActivityFeedStore} from '../stores/activityFeed'
import type {AgentActivityEvent} from '../types/api'

const labels:Record<string,string>={
 'run.admitted':'Solicitud de trabajo registrada','run.claimed':'Intento de ejecución registrado',
 'run.finished':'Resultado de ejecución registrado','run.cancel_requested':'Parada solicitada',
 'run.cancelled':'Cierre de la ejecución registrado','run.accepted':'Resultado aceptado por el propietario',
 'context.corrected':'Contexto corregido para el trabajo posterior','run.issue':'Problema de ejecución registrado',
 'run.usage_observed':'Recibo de consumo registrado','run.usage_high_water':'Medición parcial de consumo registrada',
 'agent.message_recorded':'Mensaje entre agentes guardado','conversation.archived':'Conversación archivada',
 'finding.review_recorded':'Revisión documental guardada','project.completed':'Cierre del proyecto aceptado',
 'task_created':'Tarea creada','task_updated':'Tarea actualizada','task_status_changed':'Estado de tarea actualizado',
 'message_sent':'Mensaje guardado','user_request_created':'Pregunta pendiente de respuesta',
 'user_request_responded':'Respuesta guardada','wiki_updated':'Documento actualizado',
 'file_uploaded':'Archivo guardado','file_deleted':'Archivo retirado',
}

/** Present saved observations without inventing timestamps, acceptance or the model's understanding. */
export function eventToActivity(event:DurableEvent):AgentActivityEvent{
 const data=event.data??{}
 const message=typeof data.message==='string'?data.message:typeof data.summary==='string'?data.summary:null
 const label=labels[event.type]??(event.type.startsWith('run.')?'Actualización de ejecución guardada':event.type.startsWith('job.')?'Estado de comando guardado':`Evento registrado: ${event.type}`)
 return {id:event.event_id,type:event.type,timestamp:event.timestamp??'',entity_id:event.entity_id,
  content:message?`${label}: ${message}`:label,from_agent:typeof data.actor_id==='string'?data.actor_id:undefined}
}

/** Subscribe before connecting; batch cache refreshes while preserving every durable feed identity. */
export function useWebSocketSync(){
 const queryClient=useQueryClient()
 const projectId=useProjectStore(state=>state.activeProjectId)
 useEffect(()=>{
  const generation=useActivityFeedStore.getState().selectProject(projectId)
  if(projectId==null){wsManager.disconnect();return}
  let active=true
  let refresh:ReturnType<typeof setTimeout>|null=null
  const tasks=new Set<number>()
  /** Bound refetch bursts during large catch-up pages without changing event application order. */
  function scheduleRefresh(){
   if(refresh)return
   refresh=setTimeout(()=>{refresh=null;if(active)void queryClient.invalidateQueries({predicate:query=>queryBelongsToProject(query.queryKey,projectId!,tasks)});tasks.clear()},250)
  }
  /** Apply only this generation's events; cursor advancement is owned by the validated transport. */
  function receive(event:DurableEvent){
   if(!active||event.project_id!==projectId)return
   if(event.entity_type==='task'&&event.entity_id!=null)tasks.add(event.entity_id)
   useActivityFeedStore.getState().addEvent(projectId!,generation,eventToActivity(event))
   scheduleRefresh()
  }
  /** Explain reconnect/gap state and refresh current snapshots after known history loss. */
  function status(connection:StreamStatus,observedProject:number){
   if(!active||observedProject!==projectId)return
   useActivityFeedStore.getState().setConnection(projectId!,generation,connection)
   if(connection==='reset_required')scheduleRefresh()
  }
  wsManager.subscribe(receive);wsManager.subscribeStatus(status);wsManager.connect(projectId)
  return ()=>{active=false;if(refresh)clearTimeout(refresh);wsManager.unsubscribe(receive);wsManager.unsubscribeStatus(status);wsManager.disconnect()}
 },[projectId,queryClient])
}

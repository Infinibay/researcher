/** Review identity checks and Spanish explanations, separate from reported scientific judgments. @module */
import type {ReviewDetail,ReviewIntent,ReviewState} from '../../api/reviews'
import {presentRun} from '../../api/runtime'

/** Finishing a review produces attributed checks, not acceptance of the underlying task. */
export function reviewRunStatus(status:string) {
 return status==='needs_review'?{title:'Revisión terminada',description:'Inspecciona la decisión y sus límites antes de cerrar este intento. Esta revisión por sí sola no acepta la tarea.'}:presentRun(status)
}

/** Refuse cached responses from a different project, task or finding before rendering their text. */
export function scopedReview<T extends ReviewState|ReviewDetail>(value:T|undefined,projectId:number,findingId:number,taskId:number|null):T|undefined {
 return value?.project_id===projectId&&value.finding_id===findingId&&value.task_id===taskId?value:undefined
}

/** Name only the reviewer's bounded decision, without converting support into scientific certainty. */
export function reviewVerdict(verdict:string) {
 return ({supported:'Respaldado en lo comprobado',needs_revision:'Requiere cambios',inconclusive:'Sin conclusión suficiente'} as Record<string,string>)[verdict]??'Decisión no reconocida'
}

/** Translate admission constraints into an actionable account of the missing evidence or task state. */
export function reviewReason(reason:string|null) {
 const reasons:Record<string,string>={
  author_origin_unknown:'No se pudo acreditar qué intento creó esta versión. Hay que registrar una versión con procedencia antes de pedir una revisión independiente.',
  author_not_closed:'El intento autor todavía no terminó. Primero hay que esperar su cierre.',
  task_not_active_research:'Esta tarea debe estar activa y ser de investigación para admitir una revisión.',
 }
 return reasons[reason??'']??'Esta versión todavía no reúne las condiciones para admitir una revisión independiente.'
}

/** Retain an uncertain submission across reloads; validate the saved scope before offering a retry. */
export function loadReviewIntent(projectId:number,findingId:number,taskId:number|null):ReviewIntent|null {
 try {
  const raw=globalThis.sessionStorage?.getItem(`review-intent:${projectId}:${findingId}`)
  if(!raw)return null
  const value=JSON.parse(raw)
  return value.projectId===projectId&&value.findingId===findingId&&value.taskId===taskId
   &&Number.isSafeInteger(value.context_version)&&value.context_version>0
   &&typeof value.subject_sha256==='string'&&/^[a-f0-9]{64}$/.test(value.subject_sha256)
   &&typeof value.operation_key==='string'&&/^review-[a-f0-9-]{36}$/.test(value.operation_key)
   &&Number.isSafeInteger(value.repository_id)&&value.repository_id>0?value:null
 } catch {return null}
}

/** Save only the submitted identities and nonce, never the claim, source text or credentials. */
export function saveReviewIntent(projectId:number,findingId:number,intent:ReviewIntent|null) {
 try {
  const key=`review-intent:${projectId}:${findingId}`
  if(intent)globalThis.sessionStorage?.setItem(key,JSON.stringify(intent))
  else globalThis.sessionStorage?.removeItem(key)
 } catch { /* The current mounted panel still retains the original packet if storage is unavailable. */ }
}

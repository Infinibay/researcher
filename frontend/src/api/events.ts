/** Validate durable event pages and refresh only cache entries in their actual project. @module */
import type {WSEvent} from '../types/api'

/** Committed event identity is a string so large SQLite IDs survive browser transport exactly. */
export type DurableEvent=WSEvent&{event_id:string}
/** Only validated pages may advance the last-applied reconnect cursor. */
export interface AppliedEventPage {events:DurableEvent[];cursor:string;reset:boolean;hasMore:boolean}

/** Parse a canonical SQLite cursor without rounding or accepting ambiguous numeric forms. */
function cursor(value:unknown):bigint{
 if(typeof value!=='string'||! /^(0|[1-9]\d*)$/.test(value)||BigInt(value)>9223372036854775807n)throw new Error('Cursor de eventos inválido.')
 return BigInt(value)
}

/** Validate a whole page before delivering any event, preserving ordered deduplication and explicit gaps. */
export function applyEventPage(raw:unknown,projectId:number,afterId:string):AppliedEventPage{
 const page=raw as {type:string;project_id:number;after_id:string;next_after_id:string;has_more:boolean;reset_required:boolean;resume_after_id:string|null;events:DurableEvent[]}
 const current=cursor(afterId)
 if(!page||page.type!=='events.page'||page.project_id!==projectId||!Array.isArray(page.events)||page.events.length>200||typeof page.has_more!=='boolean'||typeof page.reset_required!=='boolean')throw new Error('Página de eventos inválida.')
 const after=cursor(page.after_id),next=cursor(page.next_after_id)
 if(after>current)throw new Error('Falta un tramo del historial de eventos.')
 if(page.reset_required){
  const resume=cursor(page.resume_after_id)
  if(page.events.length!==0||page.has_more)throw new Error('Restablecimiento de eventos inválido.')
  return {events:[],cursor:String(resume),reset:true,hasMore:false}
 }
 let previous=after
 for(const event of page.events){
  if(!event||event.project_id!==projectId||typeof event.type!=='string')throw new Error('Evento de otro proyecto o inválido.')
  const id=cursor(event.event_id)
  if(id<=previous)throw new Error('Historial de eventos fuera de orden.')
  previous=id
 }
 if(next!==previous||(!page.events.length&&page.has_more))throw new Error('Página de eventos incompleta.')
 return {events:page.events.filter(event=>cursor(event.event_id)>current),cursor:String(next>current?next:current),reset:false,hasMore:page.has_more}
}

const projectFirst=new Set(['project','project-workspace','tasks','epics','milestones','chat','chat-threads','thread-messages','user-requests','question-inbox','task-workspace','task-run-history','agent-runs','run-attempts','work-budget','run-input','run-recovery','owner-source','run-jobs','run-command-output','command-jobs','command-output','files','file','file-preview','artifacts','artifact','artifact-evidence','repos','repositories','prs','flow-state','project-plans','plan-execution','source-operations','source-operation','agents','code-diff','code-result','delivered-report','graph-revision','plan-continuation','prior-branch-sources','prior-code','prior-file-sources','prior-files-preview','project-completion','project-plan','project-progress','remote-publications','review-source','run-commands','run-result','source-options'])
const projectThird=new Set(['wiki','finding-registry','finding-reviews','repo-branches','repo-tree','file-content'])

/** Match declared query-key layouts, never any coincidentally equal task/repository number. */
export function queryBelongsToProject(key:readonly unknown[],projectId:number,taskIds:ReadonlySet<number>=new Set()):boolean{
 const root=key[0]
 if(root==='projects')return true
 if(root==='task')return key.length>2?key[2]===projectId:taskIds.has(key[1] as number)
 if(root==='task-comments'||root==='task-dependencies')return taskIds.has(key[1] as number)
 if(typeof root!=='string')return false
 if(projectThird.has(root))return key[2]===projectId
 return projectFirst.has(root)&&key[1]===projectId
}

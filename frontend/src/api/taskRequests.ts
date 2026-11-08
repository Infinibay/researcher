/** Durable pre-admission task requests and corrections, without inventing a run identity before admission. @module */
import {restoreInstruction,type InstructionIntent,type RuntimeRun,type recordCorrection} from './runtime.ts'

type CorrectionBody=Readonly<Parameters<typeof recordCorrection>[2]>
export type InstructionPacket=Readonly<{schema:1;kind:'instruction';projectId:number;taskId:number;body:InstructionIntent['body']}>
export type CorrectionPacket=Readonly<{schema:1;kind:'correction';projectId:number;taskId:number;body:CorrectionBody}>
export type TaskRequestPacket=InstructionPacket|CorrectionPacket
type Kind=TaskRequestPacket['kind']
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>

/** Keep requests independent across both task/project boundaries and mutation families. */
function key(kind:Kind,project:number,task:number){return `researcher:task-${kind}:v1:${project}:${task}`}

/** Reject damaged, retargeted or ambiguous stored packets before permitting any original-body delivery. */
function parse(value:unknown,kind:Kind,project:number,task:number):TaskRequestPacket{
 const p=value as TaskRequestPacket
 if(!p||p.schema!==1||p.kind!==kind||p.projectId!==project||p.taskId!==task||![project,task].every(id=>Number.isSafeInteger(id)&&id>0)||Object.keys(p).sort().join(',')!=='body,kind,projectId,schema,taskId'||!p.body||typeof p.body.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(p.body.operation_key))throw new Error('Identidad original de solicitud inválida.')
 if(p.kind==='instruction'){
  const allowed=['operation_key','task_id','context_version','thread_id','message','repository_id','prior_code']
  if(p.body.task_id!==task||Object.keys(p.body).some(field=>!allowed.includes(field)))throw new Error('Ámbito original de solicitud inválido.')
  const checked=restoreInstruction({projectId:project,body:p.body})
  return Object.freeze({...p,body:checked.body})
 }
 const b=p.body
 if(Object.keys(b).sort().join(',')!=='expected_version,operation_key,source_kind,statement'||!Number.isSafeInteger(b.expected_version)||b.expected_version<1||typeof b.statement!=='string'||!b.statement.trim()||b.statement.length>12000||!['user_message','user_example'].includes(b.source_kind))throw new Error('Corrección original inválida.')
 return Object.freeze({...p,body:Object.freeze({...b})})
}

/** Use save-before-send and exact-clear semantics under the existing installation archive prefix. */
export const taskRequestPackets={
 /** A corrupt copy blocks a new mutation instead of silently losing its original identity. */
 load<K extends Kind>(storage:Pick<Storage,'getItem'>,kind:K,project:number,task:number):Extract<TaskRequestPacket,{kind:K}>|null{
  const raw=storage.getItem(key(kind,project,task));if(raw===null)return null
  try{if(raw.length>256000)throw new Error('size');return parse(JSON.parse(raw),kind,project,task) as Extract<TaskRequestPacket,{kind:K}>}catch{throw new Error('No se pudo recuperar la solicitud original guardada. Consulta el historial antes de preparar otra.')}
 },
 /** Persist the complete immutable request before allowing its first or explicitly repeated transport. */
 save(storage:StoragePort,p:TaskRequestPacket){parse(p,p.kind,p.projectId,p.taskId);const old=this.load(storage,p.kind,p.projectId,p.taskId);if(old&&JSON.stringify(old)!==JSON.stringify(p))throw new Error('Hay una solicitud original pendiente de confirmar.');storage.setItem(key(p.kind,p.projectId,p.taskId),JSON.stringify(p))},
 /** A stale callback cannot discard a different original intent or a newer local packet. */
 clear(storage:StoragePort,p:TaskRequestPacket){if(JSON.stringify(this.load(storage,p.kind,p.projectId,p.taskId))===JSON.stringify(p))storage.removeItem(key(p.kind,p.projectId,p.taskId))},
}

/** Retain an already prepared instruction without regenerating its key or deriving a fictitious run ID. */
export function instructionPacket(intent:InstructionIntent){return parse({schema:1,kind:'instruction',projectId:intent.projectId,taskId:intent.body.task_id,body:intent.body},'instruction',intent.projectId,intent.body.task_id) as InstructionPacket}

/** Capture a fresh explicit correction in the currently observed task context. */
export function prepareTaskCorrection(project:number,task:number,draft:Omit<CorrectionBody,'operation_key'>){return parse({schema:1,kind:'correction',projectId:project,taskId:task,body:{...draft,operation_key:crypto.randomUUID()}},'correction',project,task) as CorrectionPacket}

/** Verify admission scope and original thread/text before retiring a request that may have started work. */
export function verifyInstructionReceipt(p:InstructionPacket,result:{run:RuntimeRun;message:{id:number;thread_id:string}}){const r=result.run,b=p.body;if(!r||typeof r.run_id!=='string'||!r.run_id||r.project_id!==p.projectId||r.task_id!==p.taskId||r.operation_key!==b.operation_key||r.context_version!==b.context_version||r.prompt!==b.message||r.conversation_thread_id!==b.thread_id||(b.repository_id!==undefined&&r.repository_id!==b.repository_id)||!result.message||!Number.isSafeInteger(result.message.id)||result.message.id<1||result.message.thread_id!==b.thread_id)throw new Error('El recibo no corresponde a la solicitud original; se conserva su copia.')}

/** A correction receipt advances its original context once and never claims that new inference began. */
export function verifyCorrectionReceipt(p:CorrectionPacket,result:{context_version:number;application:string;inference_started:boolean}){if(result.context_version!==p.body.expected_version+1||result.application!=='recorded_for_next_run'||result.inference_started!==false)throw new Error('El recibo no confirma la corrección original; se conserva su copia.')}

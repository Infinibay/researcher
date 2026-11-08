/** Preserve explanatory task notes with original project/task identity and no invented native run. @module */
import type {TaskComment} from '../types/api'

/** Every field is fixed before the first send, including the advisory classification. */
export type TaskCommentPacket=Readonly<{schema:1;projectId:number;taskId:number;body:Readonly<{project_id:number;operation_key:string;author:'user';content:string;comment_type:'comment'|'change_request'|'approval'}>}>
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>
/** Session enrollment archives this shared researcher prefix on installation changes. */
function key(project:number,task:number){return `researcher:task-comment:v1:${project}:${task}`}
/** Reject damaged/foreign scope and freeze literal original content before transport or recovery. */
function parse(value:unknown,project:number,task:number):TaskCommentPacket{
 const p=value as TaskCommentPacket,b=p?.body
 if(!p||p.schema!==1||p.projectId!==project||p.taskId!==task||!Number.isSafeInteger(project)||project<1||!Number.isSafeInteger(task)||task<1||Object.keys(p).sort().join(',')!=='body,projectId,schema,taskId'||!b||Object.keys(b).sort().join(',')!=='author,comment_type,content,operation_key,project_id'||b.project_id!==project||b.author!=='user'||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key)||typeof b.content!=='string'||!b.content.trim()||b.content.length>50000||!['comment','change_request','approval'].includes(b.comment_type))throw new Error('El comentario original no tiene un ámbito o contenido válido.')
 return Object.freeze({...p,body:Object.freeze({...b})})
}
/** Use save-before-send and exact-clear conventions with actual project/task identity. */
export const taskCommentPackets={
 /** Corrupt storage blocks a new note instead of silently replacing an uncertain original. */
 load(storage:Pick<Storage,'getItem'>,project:number,task:number):TaskCommentPacket|null{const raw=storage.getItem(key(project,task));if(raw===null)return null;try{if(raw.length>256000)throw new Error('size');return parse(JSON.parse(raw),project,task)}catch{throw new Error('No se pudo recuperar el comentario original. Consulta la historia antes de preparar otro.')}},
 /** Persist the whole immutable request before delivering a mutation. */
 save(storage:StoragePort,packet:TaskCommentPacket){parse(packet,packet.projectId,packet.taskId);const old=this.load(storage,packet.projectId,packet.taskId);if(old&&JSON.stringify(old)!==JSON.stringify(packet))throw new Error('Hay un comentario original sin confirmar en esta tarea.');storage.setItem(key(packet.projectId,packet.taskId),JSON.stringify(packet))},
 /** A late receipt cannot erase another intent; removing a copy never removes its server note. */
 clear(storage:StoragePort,packet:TaskCommentPacket){if(JSON.stringify(this.load(storage,packet.projectId,packet.taskId))===JSON.stringify(packet))storage.removeItem(key(packet.projectId,packet.taskId))},
}
/** Capture a new explicit note only after the owner chooses its actual destination. */
export function prepareTaskComment(project:number,task:number,content:string,kind:string){return parse({schema:1,projectId:project,taskId:task,body:{project_id:project,operation_key:crypto.randomUUID(),author:'user',content,comment_type:kind}},project,task)}
/** Only the exact scoped advisory receipt may acknowledge and retire the original local copy. */
export function verifyTaskCommentReceipt(packet:TaskCommentPacket,result:TaskComment){const b=packet.body;if(!Number.isSafeInteger(result.id)||result.id<1||result.project_id!==packet.projectId||result.task_id!==packet.taskId||result.operation_key!==b.operation_key||result.author!==b.author||result.comment_type!==b.comment_type||result.content!==b.content||result.authorizes_work!==false)throw new Error('El recibo no corresponde al comentario original; se conserva su copia.')}

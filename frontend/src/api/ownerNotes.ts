/** Durable explanatory owner notes scoped to an existing project/thread, without invented run identity or work authority. @module */
import type {ChatMessage} from '../types/api.ts'

/** Keep the original body and receipt identity independent from whichever task is currently selected. */
export type OwnerNotePacket=Readonly<{schema:1;projectId:number;threadId:string;body:Readonly<{operation_key:string;message:string;thread_id:string;to_agent:null;to_role:'project_lead'}>}>
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>
/** A note belongs to the actual thread; project/task navigation must not retarget it. */
function key(project:number,thread:string){return `researcher:owner-note:v1:${project}:${encodeURIComponent(thread)}`}
/** Validate captured scope before transport or recovery while preserving literal original text. */
function parse(value:unknown,project:number,thread:string):OwnerNotePacket{
 const p=value as OwnerNotePacket,b=p?.body
 if(!p||p.schema!==1||p.projectId!==project||p.threadId!==thread||!Number.isSafeInteger(project)||project<1||!/^[A-Za-z0-9_.:-]{1,128}$/.test(thread)||Object.keys(p).sort().join(',')!=='body,projectId,schema,threadId'||!b||Object.keys(b).sort().join(',')!=='message,operation_key,thread_id,to_agent,to_role'||b.thread_id!==thread||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key)||typeof b.message!=='string'||!b.message.trim()||b.message.length>50000||b.to_agent!==null||b.to_role!=='project_lead')throw new Error('La nota original no tiene un ámbito o contenido válido.')
 return Object.freeze({...p,body:Object.freeze({...b})})
}
/** Apply existing save-before-send/exact-clear conventions to a thread rather than a fictitious run. */
export const ownerNotePackets={
 /** Damaged storage blocks a fresh note instead of silently discarding its original key. */
 load(storage:Pick<Storage,'getItem'>,project:number,thread:string):OwnerNotePacket|null{const raw=storage.getItem(key(project,thread));if(raw===null)return null;try{if(raw.length>256000)throw new Error('size');return parse(JSON.parse(raw),project,thread)}catch{throw new Error('No se pudo recuperar la nota original. Consulta el hilo antes de preparar otra.')}},
 /** Persist the entire original request before the caller can deliver any mutation. */
 save(storage:StoragePort,packet:OwnerNotePacket){parse(packet,packet.projectId,packet.threadId);const old=this.load(storage,packet.projectId,packet.threadId);if(old&&JSON.stringify(old)!==JSON.stringify(packet))throw new Error('Hay una nota original sin confirmar en este hilo.');storage.setItem(key(packet.projectId,packet.threadId),JSON.stringify(packet))},
 /** A late receipt cannot delete another local intent or undo a saved server message. */
 clear(storage:StoragePort,packet:OwnerNotePacket){if(JSON.stringify(this.load(storage,packet.projectId,packet.threadId))===JSON.stringify(packet))storage.removeItem(key(packet.projectId,packet.threadId))},
}
/** Prepare a new explicit advisory note, with all backend defaults fixed before the first send. */
export function prepareOwnerNote(project:number,thread:string,message:string){return parse({schema:1,projectId:project,threadId:thread,body:{operation_key:crypto.randomUUID(),message,thread_id:thread,to_agent:null,to_role:'project_lead'}},project,thread)}
/** Confirm original project/thread/text/key and owner provenance before retiring its local copy. */
export function verifyOwnerNoteReceipt(packet:OwnerNotePacket,result:ChatMessage){
 if(!Number.isSafeInteger(result.id)||result.id<1||result.project_id!==packet.projectId||result.thread_id!==packet.threadId||result.operation_key!==packet.body.operation_key||result.message!==packet.body.message||result.to_role!==packet.body.to_role||result.to_agent!==null||result.from_agent!=='user'||result.delivery!=='recorded'||result.conversation_type!=='user_to_agent')throw new Error('El recibo no corresponde a la nota original; se conserva su copia.')
}

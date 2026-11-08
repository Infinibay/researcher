/** Capture and recover exact owner task metadata before delivery; creation never authorizes execution. @module */
import type {Task} from '../types/api'

export type TaskCreationDraft={title:string;description:string;type:string;epic_id:number|null;milestone_id:number|null;priority:number;complexity:string;depends_on:readonly number[]}
export type TaskCreationBody=Readonly<TaskCreationDraft&{project_id:number;operation_key:string}>
export type TaskCreationPacket=Readonly<{schema:1;projectId:number;body:TaskCreationBody}>
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>
const types=['plan','research','investigation','experimentation','optimization','code','review','test','design','integrate','documentation','bug_fix']

/** Reject damaged or foreign stored input before it can be delivered as an owner request. */
function parse(value:unknown,project:number):TaskCreationPacket{
 const p=value as TaskCreationPacket,b=p?.body
 const positive=(id:unknown)=>Number.isSafeInteger(id)&&Number(id)>0
 if(!p||p.schema!==1||p.projectId!==project||!positive(project)||Object.keys(p).sort().join(',')!=='body,projectId,schema'||!b||b.project_id!==project||Object.keys(b).sort().join(',')!=='complexity,depends_on,description,epic_id,milestone_id,operation_key,priority,project_id,title,type')throw new Error('Solicitud original de tarea inválida.')
 if(typeof b.title!=='string'||!b.title.trim()||b.title.length>255||typeof b.description!=='string'||b.description.length>50000||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key)||!types.includes(b.type)||!['trivial','low','medium','high','very_high'].includes(b.complexity)||!Number.isInteger(b.priority)||b.priority<1||b.priority>5||(b.epic_id!==null&&!positive(b.epic_id))||(b.milestone_id!==null&&!positive(b.milestone_id))||!Array.isArray(b.depends_on)||b.depends_on.some(id=>!positive(id))||new Set(b.depends_on).size!==b.depends_on.length)throw new Error('Contenido original de tarea inválido.')
 return Object.freeze({...p,body:Object.freeze({...b,depends_on:Object.freeze([...b.depends_on])})})
}

/** Isolate each project's unresolved metadata request; existing session enrollment archives this prefix. */
export const taskCreationPackets={
 /** Restore the exact original intent or block a new creation when the saved copy is damaged. */
 load(storage:Pick<Storage,'getItem'>,project:number):TaskCreationPacket|null{const raw=storage.getItem(`researcher:task-create:v1:${project}`);if(raw===null)return null;try{if(raw.length>256000)throw new Error('size');return parse(JSON.parse(raw),project)}catch{throw new Error('No se pudo recuperar la solicitud original de tarea. Consulta la lista antes de crear otra.')}},
 /** Save before transport and refuse to overwrite another unresolved creation in the same project. */
 save(storage:StoragePort,packet:TaskCreationPacket){parse(packet,packet.projectId);const old=this.load(storage,packet.projectId);if(old&&JSON.stringify(old)!==JSON.stringify(packet))throw new Error('Hay una creación de tarea pendiente de confirmar.');storage.setItem(`researcher:task-create:v1:${packet.projectId}`,JSON.stringify(packet))},
 /** Retire only the acknowledged or explicitly discarded original copy, preserving any newer intent. */
 clear(storage:StoragePort,packet:TaskCreationPacket){if(JSON.stringify(this.load(storage,packet.projectId))===JSON.stringify(packet))storage.removeItem(`researcher:task-create:v1:${packet.projectId}`)},
}

/** Capture selected fields and a new stable key only when the owner prepares a fresh creation. */
export function prepareTaskCreation(project:number,draft:TaskCreationDraft){return parse({schema:1,projectId:project,body:{...draft,project_id:project,operation_key:crypto.randomUUID()}},project)}

/** Acknowledge original creation bytes and scope, rather than treating any successful HTTP response as this task. */
export function verifyTaskCreationReceipt(packet:TaskCreationPacket,row:Pick<Task,'id'|'project_id'|'operation_key'|'title'|'description'|'type'|'epic_id'|'milestone_id'|'priority'|'estimated_complexity'>){
 const b=packet.body
 if(!Number.isSafeInteger(row.id)||row.id<1||row.project_id!==packet.projectId||row.operation_key!==b.operation_key||row.title!==b.title||row.description!==b.description||row.type!==b.type||(row.epic_id??null)!==b.epic_id||(row.milestone_id??null)!==b.milestone_id||row.priority!==b.priority||row.estimated_complexity!==b.complexity)throw new Error('El recibo no corresponde a la tarea original; se conserva su solicitud.')
}

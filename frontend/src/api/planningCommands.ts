/** Retain exact owner planning requests before delivery; storage is never reconstructed as new permission. @module */
type GroupBody={project_id:number;operation_key:string;title:string;description:string;priority:number}
type MilestoneBody={project_id:number;epic_id:number;operation_key:string;title:string;description:string;due_date:null}
export type PlanningPacket={schema:1;kind:'group';projectId:number;epicId:0;body:Readonly<GroupBody>}|{schema:1;kind:'milestone';projectId:number;epicId:number;body:Readonly<MilestoneBody>}
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>

/** Keep project, parent and kind independent so another panel cannot overwrite an unresolved request. */
function storageKey(kind:PlanningPacket['kind'],project:number,epic:number){return `researcher:planning-create:v1:${project}:${kind}:${epic}`}

/** Validate captured scope and body before any transport, including copies recovered after reload. */
function parse(value:unknown,kind:PlanningPacket['kind'],project:number,epic:number):PlanningPacket{
 const p=value as PlanningPacket
 if(!p||p.schema!==1||p.kind!==kind||p.projectId!==project||p.epicId!==epic||!Number.isSafeInteger(project)||project<1||!Number.isSafeInteger(epic)||(kind==='group'?epic!==0:epic<1)||Object.keys(p).sort().join(',')!=='body,epicId,kind,projectId,schema')throw new Error('Solicitud original de planificación inválida.')
 const b=p.body
 if(!b||b.project_id!==project||typeof b.title!=='string'||!b.title.trim()||b.title.length>255||typeof b.description!=='string'||b.description.length>50000||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key))throw new Error('Contenido de planificación inválido.')
 if(p.kind==='group'){
  if(Object.keys(b).sort().join(',')!=='description,operation_key,priority,project_id,title'||!Number.isInteger(p.body.priority)||p.body.priority<1||p.body.priority>5)throw new Error('Grupo original inválido.')
 }else if(Object.keys(b).sort().join(',')!=='description,due_date,epic_id,operation_key,project_id,title'||p.body.epic_id!==epic||p.body.due_date!==null)throw new Error('Hito original inválido.')
 return Object.freeze({...p,body:Object.freeze({...p.body})}) as PlanningPacket
}

/** Use the same save-before-send and exact-clear pattern as projectPackets, with planning-specific scope validation. */
export const planningPackets={
 /** A damaged or foreign packet blocks a fresh mutation rather than inventing another request. */
 load(storage:Pick<Storage,'getItem'>,kind:PlanningPacket['kind'],project:number,epic=0):PlanningPacket|null{const raw=storage.getItem(storageKey(kind,project,epic));if(raw===null)return null;try{if(raw.length>256000)throw new Error('size');return parse(JSON.parse(raw),kind,project,epic)}catch{throw new Error('No se pudo recuperar la solicitud original de planificación. Consulta el índice antes de crear otra.')}},
 /** Persist the immutable original before allowing its first or explicitly repeated delivery. */
 save(storage:StoragePort,p:PlanningPacket){parse(p,p.kind,p.projectId,p.epicId);const previous=this.load(storage,p.kind,p.projectId,p.epicId);if(previous&&JSON.stringify(previous)!==JSON.stringify(p))throw new Error('Hay una solicitud original pendiente para este grupo o proyecto.');storage.setItem(storageKey(p.kind,p.projectId,p.epicId),JSON.stringify(p))},
 /** Retire only the exact acknowledged or explicitly discarded local copy, preserving a newer request. */
 clear(storage:StoragePort,p:PlanningPacket){if(JSON.stringify(this.load(storage,p.kind,p.projectId,p.epicId))===JSON.stringify(p))storage.removeItem(storageKey(p.kind,p.projectId,p.epicId))},
}

/** Capture one group creation without granting execution or replacing an earlier unresolved intent. */
export function preparePlanningGroup(project:number,title:string,description:string,priority:number){return parse({schema:1,kind:'group',projectId:project,epicId:0,body:{project_id:project,operation_key:crypto.randomUUID(),title,description,priority}},'group',project,0) as Extract<PlanningPacket,{kind:'group'}>}

/** Capture a milestone in its exact original project and parent group. */
export function preparePlanningMilestone(project:number,epic:number,title:string){return parse({schema:1,kind:'milestone',projectId:project,epicId:epic,body:{project_id:project,epic_id:epic,operation_key:crypto.randomUUID(),title,description:'',due_date:null}},'milestone',project,epic) as Extract<PlanningPacket,{kind:'milestone'}>}

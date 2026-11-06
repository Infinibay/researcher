/** Actual owner project observations and original create/source/Stop packets; no saved label is treated as runtime authority. @module */
import {fetchApi} from './client.ts'
import type {Project} from '../types/api.ts'
import type {SourceSummary} from './sourceOperations.ts'

/** Source availability is an actual host directory-policy check, never a Git or remote health claim. */
export interface ProjectSource {repository_id:number;name:string;path:string;availability:'available'|'unavailable'|'unknown';message:string;git_state:'not_checked'}
/** An original scoped activity identity, not an inferred worker from project metadata. */
export interface ProjectActivity {run_id:string;task_id:number;status:string;attempt_id:string|null;context_version:number;fence:number}
/** Project plans and saved reports retain their exact original owner navigation target. */
export interface ProjectWorkspaceState {project_id:number;metadata_sha256:string;history_present:boolean;project:Project&{original_description:string|null};runtime_available:boolean;workspace_root:string|null;sources:ProjectSource[];source_operations:SourceSummary[];activity:ProjectActivity[];graphs:{execution_id:string;plan_run_id:string;task_id:number;authorization_revision:number}[];legacy_registered:boolean;plans:{run_id:string;task_id:number;title:string;status:string;accepted:number;proposed:number;context_current:boolean}[];reports:{task_id:number;plan_run_id:string;operation_key:string;report_sha256:string;accepted_at:number}[];report_validity:'not_rechecked';stop:{task_id:number|null;scope_sha256:string}|null}
/** The Stop receipt acknowledges withdrawal intent, while physical closure remains independently observed. */
export interface ProjectStopReceipt {kind:'project.stop';project_id:number;task_id:number|null;operation_key:string;scope_sha256:string;run_ids:string[];execution_ids:string[];status:'requested';closure:'unconfirmed'}
/** A source resource identity cannot imply filesystem or remote mutation. */
export interface ProjectSourceReceipt {project_id:number;repository_id:number;name:string;path:string;filesystem_changed:false;remote_changed:false}
/** Exact observed Stop request stored before sending; callers cannot provide an arbitrary target list. */
export interface ProjectStopAction {schema:1;kind:'stop';projectId:number;body:{operation_key:string;task_id:number|null;scope_sha256:string}}
/** Explicit directory selection is retried as the same idempotent resource intent. */
export interface ProjectSourceAction {schema:1;kind:'source';projectId:number;body:{name:string;path:string}}
/** Creation has no project scope until its exact request returns the original resource ID. */
export interface ProjectCreateAction {schema:1;kind:'create';projectId:0;body:{operation_key:string;name:string;description:string}}
/** Only these owner intents belong to project-local packet persistence. */
type ProjectPacket=ProjectStopAction|ProjectSourceAction|ProjectCreateAction
/** Recover the exact domain packet rather than widening a generic JSON request. */
type OfKind<K extends ProjectPacket['kind']>=Extract<ProjectPacket,{kind:K}>
/** Storage failure prevents a new mutation; requests are never reconstructed silently. */
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>

/** Validate every original body and common scope before transport or reload. */
function parse<K extends ProjectPacket['kind']>(raw:unknown,kind:K,project:number):OfKind<K>{const p=raw as ProjectPacket,b=p.body;if(!p||p.schema!==1||p.kind!==kind||p.projectId!==project||!Number.isSafeInteger(project)||(kind==='create'?project!==0:project<1)||Object.keys(p).sort().join(',')!=='body,kind,projectId,schema'||!b)throw new Error('No se pudo recuperar la solicitud original del proyecto.');
 if(p.kind==='stop'){if(Object.keys(p.body).sort().join(',')!=='operation_key,scope_sha256,task_id'||(p.body.task_id!==null&&(!Number.isSafeInteger(p.body.task_id)||p.body.task_id<1))||!/^[a-f0-9]{64}$/.test(p.body.scope_sha256)||!/^[A-Za-z0-9_.:-]{1,128}$/.test(p.body.operation_key))throw new Error('Solicitud Stop original inválida.')}
 else if(p.kind==='source'){if(Object.keys(p.body).sort().join(',')!=='name,path'||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$/.test(p.body.name)||!p.body.path.startsWith('/')||p.body.path.length>4096)throw new Error('Elige una ruta absoluta existente y un nombre de registro válido.')}
 else if(Object.keys(p.body).sort().join(',')!=='description,name,operation_key'||!p.body.name.trim()||p.body.name.length>255||typeof p.body.description!=='string'||p.body.description.length>50000||!/^[A-Za-z0-9_.:-]{1,128}$/.test(p.body.operation_key))throw new Error('Solicitud original de creación inválida.');
 return Object.freeze({...p,body:Object.freeze({...b})}) as OfKind<K>}

/** Retain pending requests independently per project/kind; resolving one cannot erase a newer intent. */
export const projectPackets={
 /** Reject damaged local data instead of issuing a new request after reload. */
 load<K extends ProjectPacket['kind']>(storage:Pick<Storage,'getItem'>,kind:K,project:number):OfKind<K>|null{const raw=storage.getItem(`researcher:project-${kind}:v1:${project}`);if(raw===null)return null;try{if(raw.length>64000)throw new Error('size');return parse(JSON.parse(raw),kind,project)}catch{throw new Error('No se pudo recuperar la solicitud del proyecto; consulta su estado antes de crear otra.')}},
 /** Persist before any effects and prevent an unresolved request from being overwritten. */
 save(storage:StoragePort,p:ProjectPacket){parse(p,p.kind,p.projectId);const old=this.load(storage,p.kind,p.projectId);if(old&&JSON.stringify(old)!==JSON.stringify(p))throw new Error('Hay una solicitud original pendiente en este proyecto.');storage.setItem(`researcher:project-${p.kind}:v1:${p.projectId}`,JSON.stringify(p))},
 /** Clear only the exact acknowledged or explicitly rejected original packet. */
 clear(storage:StoragePort,p:ProjectPacket){if(JSON.stringify(this.load(storage,p.kind,p.projectId))===JSON.stringify(p))storage.removeItem(`researcher:project-${p.kind}:v1:${p.projectId}`)},
}
/** Capture the actual observed Stop scope without inventing a task or grant. */
export function prepareProjectStop(projectId:number,scope:{task_id:number|null;scope_sha256:string}){return parse({schema:1,kind:'stop',projectId,body:{operation_key:crypto.randomUUID(),...scope}},'stop',projectId)}
/** Capture a directory resource; this capability has no remote/init/clone options. */
export function prepareProjectSource(projectId:number,name:string,path:string){return parse({schema:1,kind:'source',projectId,body:{name,path}},'source',projectId)}
/** Preserve one explicit project creation intent across uncertain replies. */
export function prepareProjectCreate(name:string,description:string){return parse({schema:1,kind:'create',projectId:0,body:{operation_key:crypto.randomUUID(),name,description}},'create',0)}
/** Read saved metadata, actual observations and original plan/report locators for this exact project. */
export async function projectWorkspace(project:number){const data=await fetchApi<ProjectWorkspaceState>(`/api/projects/${project}/workspace`);if(data.project_id!==project||data.project.id!==project)throw new Error('La observación no corresponde a este proyecto.');return data}
/** A lost Stop reply only recovers the original target set; it never stops newer work. */
export async function sendProjectStop(p:ProjectStopAction){parse(p,'stop',p.projectId);const r=await fetchApi<ProjectStopReceipt>(`/api/projects/${p.projectId}/stop`,{method:'POST',body:JSON.stringify(p.body)});if(r.kind!=='project.stop'||r.project_id!==p.projectId||r.task_id!==p.body.task_id||r.scope_sha256!==p.body.scope_sha256||r.operation_key!==p.body.operation_key||r.closure!=='unconfirmed'||r.status!=='requested')throw new Error('El recibo no corresponde al Stop original. Conservamos la solicitud.');return r}
/** Verify exact registration identity and explicit absence of filesystem/remote effects. */
export async function sendProjectSource(p:ProjectSourceAction){parse(p,'source',p.projectId);const r=await fetchApi<ProjectSourceReceipt>(`/api/projects/${p.projectId}/sources`,{method:'POST',body:JSON.stringify(p.body)});if(r.project_id!==p.projectId||r.name!==p.body.name||r.path!==p.body.path||!Number.isSafeInteger(r.repository_id)||r.repository_id<1||r.filesystem_changed!==false||r.remote_changed!==false)throw new Error('El recibo no corresponde a la fuente original. Conservamos la selección.');return r}
/** Recover the original new-project ID even when its response was lost or its metadata was edited later. */
export async function sendProjectCreate(p:ProjectCreateAction){parse(p,'create',0);const r=await fetchApi<Project&{creation:{project_id:number;request:ProjectCreateAction['body']}}>('/api/projects',{method:'POST',body:JSON.stringify(p.body)});if(!r.creation||r.creation.project_id!==r.id||r.creation.request.operation_key!==p.body.operation_key||r.creation.request.name!==p.body.name||r.creation.request.description!==p.body.description)throw new Error('El recibo no corresponde a la creación original. Conservamos la solicitud.');return r}

/** Exact administrative source intents and observations, separate from native tasks and publication. @module */
import {fetchApi} from './client.ts'

/** Remote provisioning is an explicit separate mode with server, namespace and visibility; no mode implies publication. */
export interface SourceInput {mode:'create'|'adopt'|'clone'|'create_remote';name:string;path?:string|null;branch?:string|null;remote_url?:string|null;use_configured_auth?:boolean;remote_server?:string|null;remote_owner?:string|null;private?:boolean|null}
/** A normalized request preserves every explicit choice across reply loss and reload. */
export interface SourceIntent {mode:SourceInput['mode'];name:string;path:string|null;branch:string|null;remote_url:string|null;remote_owner:string|null;private:boolean|null;use_configured_auth:boolean;remote_server:string|null}
/** Positive original server evidence is separate from a local source registration or fresh Git observation. */
export interface CreatedRemote {id:number;full_name:string;clone_url:string;api_base:string;private:boolean;namespace:{kind:'user'|'organization';id:number;name:string};marker:string}
/** Preparation is an original owner business operation, with no fabricated native task identity. */
export interface SourcePacket {schema:1;projectId:number;body:SourceIntent&{operation_key:string}}
/** Whole-project observations contain all bounded administrative history, including retained partial effects. */
export interface SourceSummary {operation_key:string;operation_id:string;mode:string;name:string;path:string|null;fence:number;status:string;requires_reconciliation:boolean;repository_id:number|null;remote?:CreatedRemote|null;observation:{head_sha:string;tree_sha:string;branch:string;origin:string|null;working_tree_clean:boolean}|null;observed_at:number|null;observation_kind:'recorded_not_rechecked'}
/** A worker handle and local domain receipt cannot prove remote rollback or the current state of Git. */
export interface SourceOperation extends SourceSummary {project_id:number;request:SourceIntent;issue:{code:string;message:string}|null;worker_active:boolean;local_closure:'confirmed'|'unconfirmed';message:string;repair?:SourceRepairIntent|null;repair_authorizations?:SourceRepairIntent[];receipt:{observation?:NonNullable<SourceSummary['observation']>;repository_id?:number;remote?:CreatedRemote;completed_after_withdrawal?:boolean;observed_at:number;repair_key?:string}|null}
/** A separate owner gesture can continue only the exactly observed original local attempt, with its own replay identity. */
export interface SourceRepairIntent {repair_key:string;operation_id:string;fence:number}
/** Keep the original source and continuation together so a reload cannot retarget another source or newer fence. */
export interface SourceRepairPacket {schema:1;source:SourcePacket;body:SourceRepairIntent}
/** A readonly history locator preserves the selected identity and known choices; it is never execution authority or a replacement pending request. */
export interface SourceHistoryTarget {projectId:number;operation_key:string;operation_id:string;mode:SourceInput['mode'];name:string;path:string|null;fence:number}
/** Use the same persistence boundary as browser storage without requiring a browser in transport tests. */
type StoragePort=Pick<Storage,'getItem'|'setItem'|'removeItem'>

/** Validate exact normalized scope before accepting persisted input or transmitting any request. */
function validate(packet:SourcePacket,project=packet.projectId):SourcePacket{
 const raw=packet?.body,b=raw?{...raw,remote_server:raw.remote_server??null}:null
 if(packet?.schema!==1||packet.projectId!==project||!Number.isSafeInteger(project)||project<1||!b||Object.keys(packet).sort().join(',')!=='body,projectId,schema'||Object.keys(b).sort().join(',')!=='branch,mode,name,operation_key,path,private,remote_owner,remote_server,remote_url,use_configured_auth'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key)||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$/.test(b.name)||!['create','adopt','clone','create_remote'].includes(b.mode)||typeof b.use_configured_auth!=='boolean')throw new Error('No se pudo recuperar la solicitud original de la fuente.')
 if(b.mode==='create_remote'){
  if(b.path!==null||b.branch!==null||b.remote_url!==null||b.use_configured_auth||typeof b.private!=='boolean'||typeof b.remote_owner!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$/.test(b.remote_owner)||typeof b.remote_server!=='string')throw new Error('Selecciona servidor, propietario y visibilidad sin mezclar una operación local.')
  let server:URL;try{server=new URL(b.remote_server)}catch{throw new Error('Selecciona un servidor HTTPS configurado.')}
  if(server.protocol!=='https:'||server.username||server.password||server.search||server.hash||!server.pathname.endsWith('/api/v1')||b.name.includes('..')||b.remote_owner.includes('..'))throw new Error('Selecciona un servidor HTTPS y un nombre remoto sin ambigüedad.')
 }else if(typeof b.path!=='string'||!b.path.startsWith('/')||b.path.length>4096||b.path.split('/').includes('..')||b.private!==null||b.remote_owner!==null||b.remote_server!==null)throw new Error('La operación local necesita su carpeta original sin elecciones de creación remota.')
 if(b.mode==='create'&&!b.branch||b.mode==='adopt'&&b.branch!==null||b.mode!=='clone'&&(b.remote_url!==null||b.use_configured_auth))throw new Error('La operación original mezcla elecciones incompatibles.')
 if(b.mode==='clone'){
  let url:URL;try{url=new URL(b.remote_url??'')}catch{throw new Error('Selecciona una URL HTTPS sin credenciales.')}
  if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash)throw new Error('Selecciona una URL HTTPS sin credenciales.')
 }
 const {operation_key,mode,name,path,branch,remote_url,remote_owner,private:visibility,remote_server,use_configured_auth}=b
 return Object.freeze({...packet,body:Object.freeze({operation_key,mode,name,path,branch,remote_url,remote_owner,private:visibility,remote_server,use_configured_auth})})
}

/** Generate an original key once, after the owner selects a mode and source; no transport is started here. */
export function prepareSource(project:number,input:SourceInput):SourcePacket{return validate({schema:1,projectId:project,body:{operation_key:crypto.randomUUID(),mode:input.mode,name:input.name,path:input.path??null,branch:input.branch||null,remote_url:input.remote_url||null,remote_owner:input.remote_owner??null,private:input.private??null,remote_server:input.remote_server??null,use_configured_auth:input.use_configured_auth??false}})}

/** Read public host configuration for deliberate server selection; no secret reference, namespace inference or remote request is exposed. */
export function sourceOptions(project:number){return fetchApi<{remote_server:string|null;remote_username:string|null}>(`/api/projects/${project}/source-operations`)}

/** Keep one unresolved original browser request per project without silently replacing it after an uncertain response. */
export const sourcePackets={
 /** Recover exact scope; corrupt state blocks a new mutation until the owner inspects server history. */
 load(storage:Pick<Storage,'getItem'>,project:number):SourcePacket|null{const raw=storage.getItem(`researcher:source-setup:v1:${project}`);if(raw===null)return null;try{if(raw.length>20000)throw new Error('size');return validate(JSON.parse(raw),project)}catch{throw new Error('No se pudo recuperar la solicitud original. Revisa la historia de fuentes antes de preparar otra.')}},
 /** Save before POST and refuse to overwrite another unacknowledged intent. */
 save(storage:StoragePort,packet:SourcePacket){validate(packet);const old=this.load(storage,packet.projectId);if(old&&JSON.stringify(old)!==JSON.stringify(packet))throw new Error('Hay una solicitud original pendiente. Consúltala antes de preparar otra.');storage.setItem(`researcher:source-setup:v1:${packet.projectId}`,JSON.stringify(packet))},
 /** Resolve only the exact request whose result the owner reviewed. */
 clear(storage:StoragePort,packet:SourcePacket){if(JSON.stringify(this.load(storage,packet.projectId))!==JSON.stringify(packet))throw new Error('La solicitud pendiente cambió; no se borró.');storage.removeItem(`researcher:source-setup:v1:${packet.projectId}`)}
}

/** Verify response attribution before using a late response or a saved operation to drive controls. */
function checked(value:SourceOperation,packet:SourcePacket){const {operation_key,...request}=packet.body;if(value.project_id!==packet.projectId||value.operation_key!==operation_key||!value.request||Object.keys(request).some(key=>value.request[key as keyof SourceIntent]!==request[key as keyof SourceIntent])||!/^[a-f0-9]{32}$/.test(value.operation_id)||!Number.isSafeInteger(value.fence)||value.fence<0)throw new Error('La respuesta no corresponde a la solicitud original de esta fuente.');return value}
/** Exact POST replay is deliberate; ordinary observation never reissues setup. */
export async function sendSource(packet:SourcePacket){validate(packet);return checked(await fetchApi<SourceOperation>(`/api/projects/${packet.projectId}/source-operations`,{method:'POST',body:JSON.stringify(packet.body)}),packet)}
/** Read without cloning, initializing, repairing or contacting a remote. */
export async function readSource(packet:SourcePacket){validate(packet);return checked(await fetchApi<SourceOperation>(`/api/projects/${packet.projectId}/source-operations/${encodeURIComponent(packet.body.operation_key)}`),packet)}

/** Validate only a bounded original history locator, without constructing an intent or inferring choices absent from the summary. */
function validateHistory(target:SourceHistoryTarget,project=target.projectId):SourceHistoryTarget{
 if(!target||Object.keys(target).sort().join(',')!=='fence,mode,name,operation_id,operation_key,path,projectId'||target.projectId!==project||!Number.isSafeInteger(project)||project<1||!/^[A-Za-z0-9_.:-]{1,128}$/.test(target.operation_key)||!/^[a-f0-9]{32}$/.test(target.operation_id)||!['create','adopt','clone','create_remote'].includes(target.mode)||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$/.test(target.name)||!Number.isSafeInteger(target.fence)||target.fence<0||(target.mode==='create_remote'?target.path!==null:typeof target.path!=='string'||!target.path.startsWith('/')||target.path.length>4096))throw new Error('No se pudo comprobar la operación original seleccionada.')
 return Object.freeze({...target})
}

/** Freeze the exact selected project/key/identity and already-known summary choices, not a newest-operation fallback. */
export function sourceHistoryTarget(project:number,item:SourceSummary):SourceHistoryTarget{return validateHistory({projectId:project,operation_key:item.operation_key,operation_id:item.operation_id,mode:item.mode as SourceInput['mode'],name:item.name,path:item.path,fence:item.fence})}

/** Recover original server choices only after matching the selected identity; a newer fence is a fresh observation and a lower one is rejected. */
export function sourcePacketFromHistory(target:SourceHistoryTarget,value:SourceOperation):SourcePacket{
 validateHistory(target)
 if(value.project_id!==target.projectId||value.operation_key!==target.operation_key||value.operation_id!==target.operation_id||value.fence<target.fence||value.mode!==target.mode||value.name!==target.name||value.path!==target.path||!value.request||value.request.mode!==target.mode||value.request.name!==target.name||value.request.path!==target.path)throw new Error('La respuesta no corresponde a la operación original seleccionada.')
 const packet=validate({schema:1,projectId:target.projectId,body:{operation_key:target.operation_key,...value.request}})
 checked(value,packet)
 return packet
}

/** Read exact original history with owner access; never prepare, repair, clone, initialize or contact its remote. */
export async function readSourceHistory(target:SourceHistoryTarget){validateHistory(target);const value=await fetchApi<SourceOperation>(`/api/projects/${target.projectId}/source-operations/${encodeURIComponent(target.operation_key)}`);sourcePacketFromHistory(target,value);return value}

/** Persist a readonly view independently of every unresolved local source and repair packet. */
export const sourceHistory={
 /** Restore a bounded locator; missing history is not inferred from corrupt storage. */
 load(storage:Pick<Storage,'getItem'>,project:number):SourceHistoryTarget|null{const raw=storage.getItem(`researcher:source-history:v1:${project}`);if(raw===null)return null;try{if(raw.length>12000)throw new Error('size');return validateHistory(JSON.parse(raw),project)}catch{throw new Error('No se pudo recuperar la vista de historia original. La solicitud pendiente se conserva.')}},
 /** Changing a view cannot overwrite a pending mutation, even when another operation is selected. */
 save(storage:Pick<Storage,'setItem'>,target:SourceHistoryTarget){validateHistory(target);storage.setItem(`researcher:source-history:v1:${target.projectId}`,JSON.stringify(target))},
 /** Clear only this exact view; another selected operation and all pending requests remain untouched. */
 clear(storage:StoragePort,target:SourceHistoryTarget){validateHistory(target);if(JSON.stringify(this.load(storage,target.projectId))!==JSON.stringify(target))throw new Error('La vista original seleccionada cambió; no se borró.');storage.removeItem(`researcher:source-history:v1:${target.projectId}`)}
}
/** Stop exactly the observed administrative fence; no task or PID is invented by the browser. */
export async function stopSource(packet:SourcePacket,observed:SourceOperation){checked(observed,packet);const value=checked(await fetchApi<SourceOperation>(`/api/projects/${packet.projectId}/source-operations/${encodeURIComponent(packet.body.operation_key)}/stop`,{method:'POST',body:JSON.stringify({operation_id:observed.operation_id,fence:observed.fence})}),packet);if(value.operation_id!==observed.operation_id||value.fence!==observed.fence)throw new Error('El recibo no corresponde al intento detenido. Consulta su estado.');return value}
/** Explicit reconciliation observes retained state only; it never repeats an initialization, commit or clone. */
export async function observeSource(packet:SourcePacket,observed?:SourceOperation){validate(packet);if(observed)checked(observed,packet);return checked(await fetchApi<SourceOperation>(`/api/projects/${packet.projectId}/source-operations/${encodeURIComponent(packet.body.operation_key)}/observe`,{method:'POST',...(observed?{body:JSON.stringify({operation_id:observed.operation_id,fence:observed.fence})}:{})}),packet)}

/** Validate a retained explicit local continuation without choosing a new fence or granting arbitrary commands. */
function validateRepair(packet:SourceRepairPacket):SourceRepairPacket{
 const source=validate(packet.source),body=packet.body
 if(packet.schema!==1||source.body.mode==='create_remote'||Object.keys(packet).sort().join(',')!=='body,schema,source'||!body||Object.keys(body).sort().join(',')!=='fence,operation_id,repair_key'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(body.repair_key)||!/^[a-f0-9]{32}$/.test(body.operation_id)||!Number.isSafeInteger(body.fence)||body.fence<0)throw new Error('No se pudo recuperar la autorización original de reparación.')
 return Object.freeze({schema:1,source,body:Object.freeze({...body})})
}

/** Freeze a separately authorized continuation after checking that the observation belongs to this exact local setup. */
export function prepareSourceRepair(source:SourcePacket,observed:SourceOperation):SourceRepairPacket{
 checked(observed,source)
 if(!['stopped','needs_reconciliation'].includes(observed.status)||observed.worker_active)throw new Error('Consulta el cierre del intento original antes de reparar.')
 return validateRepair({schema:1,source,body:{repair_key:crypto.randomUUID(),operation_id:observed.operation_id,fence:observed.fence}})
}

/** Store original repair intent before HTTP and refuse to discard an unknown continuation after reply loss. */
export const sourceRepairs={
 /** Recover only a packet belonging to this exact original source. */
 load(storage:Pick<Storage,'getItem'>,source:SourcePacket):SourceRepairPacket|null{const raw=storage.getItem(`researcher:source-repair:v1:${source.projectId}:${source.body.operation_key}`);if(raw===null)return null;try{if(raw.length>30000)throw new Error('size');const packet=validateRepair(JSON.parse(raw));if(JSON.stringify(packet.source)!==JSON.stringify(validate(source)))throw new Error('scope');return packet}catch{throw new Error('No se pudo recuperar la autorización original de reparación. Consulta la historia antes de continuar.')}},
 /** Save once before POST; replacing another pending authorization requires an explicit reviewed resolution. */
 save(storage:StoragePort,packet:SourceRepairPacket){const valid=validateRepair(packet),old=this.load(storage,valid.source);if(old&&JSON.stringify(old)!==JSON.stringify(valid))throw new Error('Hay una reparación original pendiente. Consulta su resultado antes de autorizar otra.');storage.setItem(`researcher:source-repair:v1:${valid.source.projectId}:${valid.source.body.operation_key}`,JSON.stringify(valid))},
 /** Resolve only the exact continuation the owner has reviewed. */
 clear(storage:StoragePort,packet:SourceRepairPacket){if(JSON.stringify(this.load(storage,packet.source))!==JSON.stringify(packet))throw new Error('La reparación original cambió; no se borró.');storage.removeItem(`researcher:source-repair:v1:${packet.source.projectId}:${packet.source.body.operation_key}`)}
}

/** Replay the same explicit repair authorization; a late response must contain that original authorization, independently of a newer observation fence. */
export async function sendSourceRepair(packet:SourceRepairPacket){const valid=validateRepair(packet),source=valid.source,value=checked(await fetchApi<SourceOperation>(`/api/projects/${source.projectId}/source-operations/${encodeURIComponent(source.body.operation_key)}/repair`,{method:'POST',body:JSON.stringify(valid.body)}),source);if(!value.repair_authorizations?.some(item=>item.repair_key===valid.body.repair_key&&item.operation_id===valid.body.operation_id&&item.fence===valid.body.fence))throw new Error('La respuesta no contiene la autorización original de reparación.');return value}

/** Explicit owner model policy, separate from account credentials, permissions and actual per-attempt inference provenance. @module */
import {fetchApi,buildUrl} from './client.ts'

/** Actor overrides always belong to one selected project; null/null identifies the global default. */
export interface ModelScope {projectId:number|null;actorId:string|null}
/** A whole pair is inherited or replaced together, avoiding effort values silently carried between models. */
export interface ModelProfile {model:string;reasoning_effort:string}
/** One immutable edit retains its original scope and observed revision through a lost response. */
export interface ModelSettingPacket {scope:Readonly<ModelScope>;body:Readonly<{project_id:number|null;actor_id:string|null;expected_revision:number;model:string|null;reasoning_effort:string|null}>}
/** Requested policy and a dated observed catalog are distinct from proven availability at the next attempt. */
export interface ModelSettingView {project_id:number|null;actor_id:string|null;setting:{scope:string;revision:number;profile:ModelProfile|null};effective:ModelProfile&{source:string;revision:number};catalog:null|{kind:'observed_not_rechecked';observed_at:number;models:{model:string;label:string;reasoning_efforts:string[]}[]};provider:'openai_subscription';applies_to:'new_attempts_only'}

/** Resolve a stable query/editor identity without inferring an actor's project from a role or display name. */
export function modelScopeKey(scope:ModelScope){if(scope.projectId===null){if(scope.actorId!==null)throw new Error('El ámbito del agente necesita un proyecto.');return 'global'}if(!Number.isSafeInteger(scope.projectId)||scope.projectId<1||scope.actorId!==null&&(!scope.actorId.trim()||scope.actorId.length>128))throw new Error('El ámbito de configuración no es válido.');return scope.actorId===null?`project:${scope.projectId}`:`actor:${scope.projectId}:${scope.actorId}`}

/** Require the original selected scope before accepting a late configuration read or write response. */
function checked(scope:ModelScope,value:ModelSettingView){if(value.project_id!==scope.projectId||value.actor_id!==scope.actorId||value.setting?.scope!==modelScopeKey(scope)||!Number.isSafeInteger(value.setting.revision)||value.setting.revision<0||value.provider!=='openai_subscription'||value.applies_to!=='new_attempts_only')throw new Error('La respuesta no corresponde al ámbito original de configuración.');return value}

/** Read one explicit scope; this never opens a model process or consumes a turn. */
export async function readModelSettings(scope:ModelScope){modelScopeKey(scope);return checked(scope,await fetchApi<ModelSettingView>(buildUrl('/api/model-settings',{project_id:scope.projectId,actor_id:scope.actorId})))}

/** Freeze scope, revision and a complete pair or reset before HTTP; later form changes cannot retarget this edit. */
export function prepareModelSetting(scope:ModelScope,revision:number,profile:ModelProfile|null):ModelSettingPacket{modelScopeKey(scope);if(!Number.isSafeInteger(revision)||revision<0||profile&&(!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(profile.model)||!/^[a-z][a-z0-9_]{0,31}$/.test(profile.reasoning_effort)))throw new Error('Revisa la versión, el identificador de modelo y el esfuerzo.');return Object.freeze({scope:Object.freeze({...scope}),body:Object.freeze({project_id:scope.projectId,actor_id:scope.actorId,expected_revision:revision,model:profile?.model??null,reasoning_effort:profile?.reasoning_effort??null})})}

/** Save one original optimistic revision, refusing a newer/different receipt rather than silently overwriting concurrent changes. */
export async function sendModelSetting(packet:ModelSettingPacket){const value=checked(packet.scope,await fetchApi<ModelSettingView>('/api/model-settings',{method:'PUT',body:JSON.stringify(packet.body)})),profile=value.setting.profile;if(value.setting.revision!==packet.body.expected_revision+1||(packet.body.model===null?profile!==null:profile?.model!==packet.body.model||profile.reasoning_effort!==packet.body.reasoning_effort))throw new Error('La respuesta no contiene la versión original guardada. Consulta el estado actual; conservamos tu selección.');return value}

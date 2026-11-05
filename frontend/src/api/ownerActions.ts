/** Scoped durable owner packets shared by research and code decisions. @module */

/** Storage failure prevents sending; no fallback silently abandons an uncertain intent. */
export type OwnerActionStorage = Pick<Storage,'getItem'|'setItem'|'removeItem'>
/** Common immutable identity; each domain validates its own kind and body. */
export interface OwnerAction {
  readonly schema:1; readonly kind:string; readonly projectId:number; readonly taskId:number; readonly runId:string
  readonly body: Readonly<{operation_key:string}>
}

/** Reuse packet/pointer semantics with separate stable namespaces and strict domain parsers. */
export function ownerActionStore<T extends OwnerAction>(namespace:'result'|'code'|'code-review'|'code-publication'|'publication-recovery', parse:(value:unknown)=>T) {
  /** Preserve existing research keys while preventing code/research packet collisions. */
  const key=(project:number,task:number,run:string)=>`researcher:${namespace}-action:v1:${project}:${task}:${encodeURIComponent(run)}`
  /** Keep the original run discoverable after pagination, navigation or reload. */
  const pointer=(project:number,task:number)=>`researcher:${namespace}-pending:v1:${project}:${task}`
  /** Validate common identity before the domain parser and freeze the recovered packet. */
  function load(storage:Pick<Storage,'getItem'>,project:number,task:number,run:string):T|null {
    const raw=storage.getItem(key(project,task,run))
    if(raw===null) return null
    try {
      if(raw.length>64000) throw new Error('size')
      const action=JSON.parse(raw)
      if(action.schema!==1 || action.projectId!==project || action.taskId!==task || action.runId!==run || !action.body || typeof action.body.operation_key!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(action.body.operation_key)) throw new Error('scope')
      const parsed=parse(action)
      return Object.freeze({...parsed,body:Object.freeze({...parsed.body})}) as T
    } catch {throw new Error('No se pudo recuperar la decisión guardada. Consulta el resultado antes de preparar otra.')}
  }
  /** Never reinterpret a broken pending pointer as permission to issue a fresh action. */
  function pendingRun(storage:Pick<Storage,'getItem'>,project:number,task:number):string|null {
    const raw=storage.getItem(pointer(project,task))
    if(raw===null) return null
    try {
      const value=JSON.parse(raw)
      if(typeof value.runId!=='string' || !value.runId || value.runId.length>128) throw new Error('run')
      const action=load(storage,project,task,value.runId)
      if(!action || action.body.operation_key!==value.operationKey) throw new Error('packet')
      return value.runId
    } catch {throw new Error('No se pudo recuperar la decisión pendiente de esta tarea. Consulta su historial antes de preparar otra.')}
  }
  /** Persist the complete original packet before the caller may send any mutation. */
  function save(storage:OwnerActionStorage,action:T) {
    const previous=pendingRun(storage,action.projectId,action.taskId)
    if(previous!==null && load(storage,action.projectId,action.taskId,previous)?.body.operation_key!==action.body.operation_key) throw new Error('Hay una decisión pendiente de esta tarea. Consulta su recibo antes de preparar otra.')
    storage.setItem(key(action.projectId,action.taskId,action.runId),JSON.stringify(action))
    storage.setItem(pointer(action.projectId,action.taskId),JSON.stringify({runId:action.runId,operationKey:action.body.operation_key}))
  }
  /** Remove only the resolved original packet, leaving a newer decision untouched. */
  function clear(storage:OwnerActionStorage,action:T) {
    if(load(storage,action.projectId,action.taskId,action.runId)?.body.operation_key!==action.body.operation_key) return
    const raw=storage.getItem(pointer(action.projectId,action.taskId))
    if(raw!==null && JSON.parse(raw).operationKey===action.body.operation_key) storage.removeItem(pointer(action.projectId,action.taskId))
    storage.removeItem(key(action.projectId,action.taskId,action.runId))
  }
  return {load,pendingRun,save,clear}
}

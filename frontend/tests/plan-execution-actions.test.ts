import test from 'node:test'
import assert from 'node:assert/strict'

/** Minimal real storage port for exact persisted owner actions. */
function storage(){const items=new Map<string,string>();return {getItem:(k:string)=>items.get(k)??null,setItem:(k:string,v:string)=>{items.set(k,v)},removeItem:(k:string)=>{items.delete(k)}}}

test('execution decision retains the original manifest and request across loss and reload',async()=>{
 const api=await import('../src/api/planExecution.ts'),saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 try{
  const action=api.prepareExecutionAction(101,42,'plan:a','a'.repeat(64),'execute')
  api.executionActions.save(saved,action)
  globalThis.fetch=async(url,options)=>{const body=JSON.parse(String(options?.body));sent.push([String(url),body]);if(sent.length===1)throw new TypeError('lost original response');return Response.json({project_id:101,task_id:42,plan_run_id:'plan:a',execution_id:'execution:a',operation_key:body.operation_key,manifest_sha256:body.manifest_sha256,status:'active'})}
  await assert.rejects(api.sendExecutionAction(action),/lost original/)
  const reloaded=api.executionActions.load(saved,101,42,'plan:a')!
  const receipt=await api.sendExecutionAction(reloaded)
  assert.equal(receipt.execution_id,'execution:a');assert.deepEqual(sent[0],sent[1]);api.executionActions.clear(saved,reloaded)
  assert.equal(api.executionActions.pendingRun(saved,101,42),null)
 }finally{globalThis.fetch=previous}
})

test('pause and resume identify original execution and reject unrelated receipts',async()=>{
 const api=await import('../src/api/planExecution.ts'),previous=globalThis.fetch
 try{
  const action=api.prepareExecutionAction(101,42,'plan:a','a'.repeat(64),'paused','execution:a')
  globalThis.fetch=async(url,options)=>{assert.equal(String(url),'/api/projects/101/plan-executions/execution%3Aa/control');const body=JSON.parse(String(options?.body));assert.equal(body.status,'paused');return Response.json({project_id:101,task_id:42,plan_run_id:'plan:a',execution_id:'execution:foreign',operation_key:body.operation_key,manifest_sha256:body.manifest_sha256,status:'paused'})}
  await assert.rejects(api.sendExecutionAction(action),/recibo/)
 }finally{globalThis.fetch=previous}
})

test('damaged execution packets cannot silently refresh the authorized context',async()=>{
 const api=await import('../src/api/planExecution.ts'),saved=storage()
 const action=api.prepareExecutionAction(101,42,'plan:a','a'.repeat(64),'execute')
 api.executionActions.save(saved,action)
 assert.throws(()=>api.prepareExecutionAction(101,42,'plan:a','invalid','execute'))
 assert.throws(()=>api.prepareExecutionAction(101,42,'plan:a','a'.repeat(64),'active'))
 saved.setItem('researcher:plan-execution-action:v1:101:42:plan%3Aa',JSON.stringify({...action,body:{...action.body,actor_id:'injected'}}))
 assert.throws(()=>api.executionActions.load(saved,101,42,'plan:a'))
})

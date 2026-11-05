/** Corrected graph adoption keeps the exact inspected owner decision across loss and reload. @module */
import test from 'node:test'
import assert from 'node:assert/strict'

/** Exercise the real durable-packet store through its browser-compatible storage port. */
function storage(){const values=new Map<string,string>();return {getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}}

/** Controlled preview supplies scope/evidence only; domain validation remains in the server. */
function preview(){return {project_id:101,execution_id:'exec:a',plan_run_id:'plan:a',eligible:true,snapshot_sha256:'a'.repeat(64),manifest_sha256:'b'.repeat(64),blocked_reason:'',snapshot:{previous_revision:1,changes:[],corrected_tasks:[{task_id:51},{task_id:52}],retained_results:[{task_id:51,run_id:'accepted:a'}]}}}

test('lost graph adoption response reloads identical original snapshot and revision',async()=>{
 const api=await import('../src/api/planReauthorizations.ts'),saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 try{
  const action=api.prepareGraphAction(101,42,'plan:a','exec:a',preview() as never)
  api.graphActions.save(saved,action)
  globalThis.fetch=async(url,options)=>{const body=JSON.parse(String(options?.body));sent.push([String(url),body]);if(sent.length===1)throw new TypeError('lost graph reply');return Response.json({project_id:101,plan_run_id:'plan:a',execution_id:'exec:a',authorization_revision:2,manifest_sha256:'b'.repeat(64),status:'paused',inference_started:false,deliveries:{'52':'new:a'},retained_results:[{task_id:51,run_id:'accepted:a'}],...body})}
  await assert.rejects(api.sendGraphAction(action),/lost graph reply/)
  const restored=api.graphActions.load(saved,101,42,'plan:a')!,receipt=await api.sendGraphAction(restored)
  assert.equal(receipt.authorization_revision,2);assert.deepEqual(sent[0],sent[1]);api.graphActions.clear(saved,restored);assert.equal(api.graphActions.pendingRun(saved,101,42),null)
 }finally{globalThis.fetch=previous}
})

test('unrelated or incomplete graph receipts and damaged packets stay unresolved',async()=>{
 const api=await import('../src/api/planReauthorizations.ts'),saved=storage(),previous=globalThis.fetch
 const action=api.prepareGraphAction(101,42,'plan:a','exec:a',preview() as never)
 api.graphActions.save(saved,action)
 try{
  const receipt={project_id:101,plan_run_id:'plan:a',execution_id:'exec:a',authorization_revision:2,manifest_sha256:'b'.repeat(64),status:'paused',inference_started:false,deliveries:{'52':'new:a'},retained_results:[{task_id:51,run_id:'accepted:a'}],...action.body}
  for(const edit of [{authorization_revision:3},{status:'active'},{deliveries:{}},{retained_results:[]},{manifest_sha256:'c'.repeat(64)}]){
   globalThis.fetch=async()=>Response.json({...receipt,...edit});await assert.rejects(api.sendGraphAction(action),/recibo/)
  }
  assert.notEqual(api.graphActions.load(saved,101,42,'plan:a'),null)
  saved.setItem('researcher:plan-reauthorization-action:v1:101:42:plan%3Aa',JSON.stringify({...action,body:{...action.body,tasks:[]}}))
  assert.throws(()=>api.graphActions.load(saved,101,42,'plan:a'))
 }finally{globalThis.fetch=previous}
})

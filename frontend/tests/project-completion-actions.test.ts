/** Exact whole-project closure packets survive uncertain replies; historical acceptance never authorizes another scope. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Isolate durable packet behavior without a browser or model. */
function storage(){const values=new Map<string,string>();return {getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}}

test('completion retries the exact report, owner statement and unpublished candidates after response loss',async()=>{
 const {prepareCompletion,completionActions,sendCompletion}=await import('../src/api/projectCompletion.ts')
 const action=prepareCompletion(101,42,'plan:a','a'.repeat(64),['candidate-a'],'Revisé el alcance y sus límites.'),saved=storage(),old=globalThis.fetch,sent:unknown[]=[]
 completionActions.save(saved,action)
 try{
  globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1)throw new TypeError('reply lost');return Response.json({kind:'project.completion',project_id:101,task_id:42,plan_run_id:'plan:a',...action.body,project_status:'completed',publication_performed:false,report_markdown:'Historical exact report'})}
  await assert.rejects(sendCompletion(action),/reply lost/)
  const restored=completionActions.load(saved,101,42,'plan:a')!
  assert.equal(completionActions.pendingRun(saved,101,42),'plan:a')
  await sendCompletion(restored);assert.deepEqual(sent[0],sent[1])
  assert.match(String((sent[0] as unknown[])[0]),/plan%3Aa\/project-plan\/completion\/accept$/)
 }finally{globalThis.fetch=old}
})

test('another report or acknowledgement cannot resolve the original completion decision',async()=>{
 const {prepareCompletion,sendCompletion}=await import('../src/api/projectCompletion.ts')
 const action=prepareCompletion(101,42,'plan:a','a'.repeat(64),['candidate-a'],'Revisé las limitaciones.'),old=globalThis.fetch
 try{for(const altered of [{report_sha256:'b'.repeat(64)},{acknowledged_unpublished_attempts:[]},{statement:'Different intent'},{publication_performed:true}]){
  globalThis.fetch=async()=>Response.json({kind:'project.completion',project_id:101,task_id:42,plan_run_id:'plan:a',...action.body,project_status:'completed',publication_performed:false,...altered})
  await assert.rejects(sendCompletion(action),/recibo/)
 }}finally{globalThis.fetch=old}
})

test('damaged completion proof fields are rejected on reload rather than widening owner authority',async()=>{
 const {prepareCompletion,completionActions}=await import('../src/api/projectCompletion.ts')
 const action=prepareCompletion(101,42,'plan:a','a'.repeat(64),[],'Revisé el informe.'),saved=storage()
 saved.setItem('researcher:project-completion-action:v1:101:42:plan%3Aa',JSON.stringify({...action,body:{...action.body,proof:true}}))
 assert.throws(()=>completionActions.load(saved,101,42,'plan:a'),/recuperar/)
 assert.throws(()=>prepareCompletion(101,42,'plan:a','a'.repeat(64),[],' '),/declaración/)
})

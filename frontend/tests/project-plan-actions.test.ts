/** Planning starts and explicit owner expansion retain original requests across response loss. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Exercise real packet persistence without depending on a DOM storage implementation. */
function storage(){const values=new Map<string,string>();return {getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}}

test('owner plan acceptance reload retries one exact proposal and never adopts automatic execution',async()=>{
 const {preparePlanAcceptance,planActions,sendPlanAcceptance}=await import('../src/api/projectPlans.ts')
 const action=preparePlanAcceptance(101,42,'planner:a','a'.repeat(64),3),saved=storage();planActions.save(saved,action)
 const previous=globalThis.fetch,sent:unknown[]=[]
 try{
  globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1)throw new TypeError('response lost');return Response.json({project_id:101,task_id:42,run_id:'planner:a',operation_key:action.body.operation_key,proposal_sha256:'a'.repeat(64),context_version:3,epics:{work:10},tasks:{learn:11,change:12},execution_started:false})}
  await assert.rejects(sendPlanAcceptance(action),/response lost/)
  await sendPlanAcceptance(planActions.load(saved,101,42,'planner:a')!)
  assert.deepEqual(sent[0],sent[1]);assert.match(String((sent[0] as unknown[])[0]),/planner%3Aa\/project-plan\/accept$/)
  globalThis.fetch=async()=>Response.json({project_id:101,task_id:42,run_id:'planner:a',operation_key:action.body.operation_key,proposal_sha256:'a'.repeat(64),context_version:3,epics:{},tasks:{},execution_started:true})
  await assert.rejects(sendPlanAcceptance(action),/recibo/)
 }finally{globalThis.fetch=previous}
})

test('a native project start keeps its original operation after a lost response and reload',async()=>{
 const {startProjectPlanning}=await import('../src/api/projectPlans.ts')
 const saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 try{
  globalThis.fetch=async(url,options)=>{const body=JSON.parse(String(options?.body));sent.push([String(url),body]);if(sent.length===1)throw new TypeError('lost after admission');return Response.json({request:body,planning_task_id:42,run:{project_id:101,task_id:42,run_id:'planner:a',actor_id:'native-project-planner',execution_kind:'research'}})}
  await assert.rejects(startProjectPlanning(saved,101),/lost after admission/)
  const result=await startProjectPlanning(saved,101)
  assert.equal(result.planning_task_id,42);assert.deepEqual(sent[0],sent[1])
 }finally{globalThis.fetch=previous}
})

test('plan acceptance receipt from another original version remains unresolved',async()=>{
 const {preparePlanAcceptance,sendPlanAcceptance}=await import('../src/api/projectPlans.ts')
 const action=preparePlanAcceptance(101,42,'planner:a','a'.repeat(64),3),previous=globalThis.fetch
 try{globalThis.fetch=async()=>Response.json({project_id:101,task_id:42,run_id:'planner:a',operation_key:action.body.operation_key,proposal_sha256:'b'.repeat(64),context_version:3,tasks:{change:12},epics:{work:10},execution_started:false});await assert.rejects(sendPlanAcceptance(action),/recibo/)}finally{globalThis.fetch=previous}
})

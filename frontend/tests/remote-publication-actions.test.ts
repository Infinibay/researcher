/** Original remote effects and readonly recovery preserve exact owner scope across lost responses. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

const remote={api_base:'https://forgejo.example/api/v1',repository_id:71,full_name:'owner/repo',clone_url:'https://forgejo.example/owner/repo.git'}
const observed={contextVersion:3,headSha:'a'.repeat(40)}

/** Use real packet storage semantics while keeping browser storage in memory. */
function storage(){const values=new Map<string,string>();return {getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}}

test('remote push reload retries its original destination, prior SHA and receipt identity',async()=>{
 const {prepareRemoteAction,remoteActions,sendRemoteAction}=await import('../src/api/remotePublications.ts')
 const action=prepareRemoteAction(101,24,'local:a','local:a',observed,{stage:'push',remote,target_ref:'refs/heads/reviewed-change',expected_target_sha:null})
 const saved=storage();remoteActions.save(saved,action)
 assert.equal(remoteActions.pendingRun(saved,101,24),'local:a')
 const restored=remoteActions.load(saved,101,24,'local:a')!
 assert.deepEqual(restored,action)
 const previous=globalThis.fetch,sent:unknown[]=[]
 try{
  globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1)throw new TypeError('response lost');return Response.json({run:{project_id:101,task_id:24,context_version:3,run_id:'remote:a',operation_key:action.body.operation_key,execution_kind:'remote_publication'},request:{origin_run_id:'local:a',local_publication_run_id:'local:a',stage:'push',intent:{...action.body,kind:'remote_publication.admit',origin_run_id:'local:a'},protocol:{head_sha:observed.headSha}}})}
  await assert.rejects(sendRemoteAction(restored),/response lost/)
  await sendRemoteAction(remoteActions.load(saved,101,24,'local:a')!)
  assert.deepEqual(sent[0],sent[1]);assert.match(String((sent[0] as unknown[])[0]),/runs\/local%3Aa\/remote-publications$/)
 }finally{globalThis.fetch=previous}
})

test('remote merge authorization cannot adopt a receipt from another original PR or accepted version',async()=>{
 const {prepareRemoteAction,sendRemoteAction}=await import('../src/api/remotePublications.ts')
 const action=prepareRemoteAction(101,24,'local:a','pull:a',observed,{stage:'merge'})
 const previous=globalThis.fetch
 try{
  globalThis.fetch=async()=>Response.json({run:{project_id:101,task_id:24,context_version:3,operation_key:action.body.operation_key,execution_kind:'remote_publication'},request:{origin_run_id:'pull:other',local_publication_run_id:'local:a',stage:'merge',intent:{...action.body},protocol:{push:{head_sha:observed.headSha}}}})
  await assert.rejects(sendRemoteAction(action),/recibo/)
 }finally{globalThis.fetch=previous}
})

test('remote recovery reload retains the writer attempt and fence instead of preparing another publication',async()=>{
 const {prepareRemoteRecovery,remoteRecoveryActions,sendRemoteRecovery}=await import('../src/api/remotePublications.ts')
 const action=prepareRemoteRecovery(101,24,'local:a','remote:a','writer-attempt',7)
 const saved=storage();remoteRecoveryActions.save(saved,action)
 const previous=globalThis.fetch,sent:unknown[]=[]
 try{
  globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1)throw new TypeError('response lost');return Response.json({run_id:'remote:a',source_attempt_id:'writer-attempt',recovery_operation_key:action.body.operation_key,effects_confirmed:false,observations:{push:{state:'uncertain'}}})}
  await assert.rejects(sendRemoteRecovery(action),/response lost/)
  const result=await sendRemoteRecovery(remoteRecoveryActions.load(saved,101,24,'local:a')!)
  assert.equal(result.effects_confirmed,false);assert.deepEqual(sent[0],sent[1]);assert.match(String((sent[0] as unknown[])[0]),/remote-publications\/remote%3Aa\/recovery$/)
 }finally{globalThis.fetch=previous}
})

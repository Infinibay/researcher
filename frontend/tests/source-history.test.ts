/** Original source history reopens without inventing requests or replacing another unresolved local packet. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Exercise pending intent and readonly selection through the same storage API as a real browser. */
function storage(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}

/** Model a complete recorded operation with original identity, explicit choices and separately observed current progress. */
function operation(){return {project_id:202,operation_key:'retained',operation_id:'a'.repeat(32),mode:'create',name:'retained',path:'/managed/retained',fence:2,status:'stopped',requires_reconciliation:true,repository_id:null,remote:null,observation:null,observed_at:null,observation_kind:'recorded_not_rechecked' as const,request:{mode:'create' as const,name:'retained',path:'/managed/retained',branch:'main',remote_url:null,remote_owner:null,private:null,use_configured_auth:false,remote_server:null},worker_active:false,local_closure:'confirmed' as const,issue:null,receipt:null,message:'Saved observation',repair:null,repair_authorizations:[]}}

test('original history uses only an exact GET and permits a newly observed later fence',async()=>{
 const {sourceHistoryTarget,readSourceHistory,sourcePacketFromHistory}=await import('../src/api/sourceOperations.ts')
 const value=operation(),target=sourceHistoryTarget(202,value),previous=globalThis.fetch,calls:unknown[]=[]
 try{globalThis.fetch=async(url,options)=>{calls.push([String(url),options?.method??'GET']);return Response.json({...value,fence:4})}
  const observed=await readSourceHistory(target),packet=sourcePacketFromHistory(target,observed)
  assert.equal(observed.fence,4);assert.equal(packet.body.operation_key,'retained');assert.equal(packet.body.path,'/managed/retained');assert.equal(packet.projectId,202)
  assert.deepEqual(calls,[['/api/projects/202/source-operations/retained','GET']])
 }finally{globalThis.fetch=previous}
})

test('foreign replaced stale or changed responses cannot become an original history packet',async()=>{
 const {sourceHistoryTarget,readSourceHistory}=await import('../src/api/sourceOperations.ts')
 const value=operation(),target=sourceHistoryTarget(202,value),previous=globalThis.fetch
 try{for(const change of [{project_id:101},{operation_key:'other'},{operation_id:'b'.repeat(32)},{fence:1},{request:{...value.request,path:'/managed/other'}},{request:{...value.request,name:'other'}},{request:{...value.request,mode:'adopt',branch:null}},{request:{...value.request,private:true}}]){
  globalThis.fetch=async()=>Response.json({...value,...change})
  await assert.rejects(readSourceHistory(target),/original|seleccionada|incompatible|local/)
 }}finally{globalThis.fetch=previous}
})

test('history selection and reload preserve another uncertain local request byte for byte',async()=>{
 const {prepareSource,sourcePackets,sourceHistory,sourceHistoryTarget,sourcePacketFromHistory}=await import('../src/api/sourceOperations.ts')
 const saved=storage(),pending=prepareSource(202,{mode:'create',name:'pending',path:'/managed/pending',branch:'main'}),value=operation(),target=sourceHistoryTarget(202,value)
 sourcePackets.save(saved,pending);const before=saved.getItem('researcher:source-setup:v1:202')
 sourceHistory.save(saved,target);const recovered=sourceHistory.load(saved,202)!
 assert.deepEqual(recovered,target);assert.equal(sourceHistory.load(saved,101),null)
 assert.equal(sourcePacketFromHistory(recovered,value).body.operation_key,'retained')
 sourceHistory.clear(saved,target)
 assert.equal(sourceHistory.load(saved,202),null);assert.equal(saved.getItem('researcher:source-setup:v1:202'),before)
 assert.deepEqual(sourcePackets.load(saved,202),pending)
})

test('a recovered packet stays compatible with its earlier pending repair despite server JSON field reordering',async()=>{
 const {prepareSource,sourcePackets,sourceHistoryTarget,sourcePacketFromHistory,prepareSourceRepair,sourceRepairs}=await import('../src/api/sourceOperations.ts')
 const value=operation(),source=prepareSource(202,{mode:'create',name:'retained',path:'/managed/retained',branch:'main'}),original={...source,body:{...source.body,operation_key:'retained'}},saved=storage()
 sourcePackets.save(saved,original);const repair=prepareSourceRepair(original,value);sourceRepairs.save(saved,repair)
 const request=Object.fromEntries(Object.entries(value.request).reverse()),packet=sourcePacketFromHistory(sourceHistoryTarget(202,value),{...value,request} as any)
 assert.deepEqual(sourceRepairs.load(saved,packet),repair)
 sourcePackets.clear(saved,packet);assert.equal(sourcePackets.load(saved,202),null)
})

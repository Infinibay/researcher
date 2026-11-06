/** Explicit reservation endings retain original scope through reply loss and never authorize filesystem cleanup or another adoption. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Match browser storage without coupling transport tests to a DOM. */
function storage(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}

test('release preserves one original authorization through reply loss and requires its exact closed receipt',async()=>{
 const {prepareSource,prepareSourceRelease,sourceReleases,sendSourceRelease,sourcePackets}=await import('../src/api/sourceOperations.ts')
 const source=prepareSource(202,{mode:'create',name:'retained',path:'/managed/retained',branch:'main'}),{operation_key,...request}=source.body
 const observed={project_id:202,operation_key,operation_id:'a'.repeat(32),fence:1,request,status:'stopped',worker_active:false,local_closure:'confirmed',reservation_released:false} as any
 const packet=prepareSourceRelease(source,observed),saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 sourcePackets.save(saved,source);const before=saved.getItem('researcher:source-setup:v1:202');sourceReleases.save(saved,packet)
 assert.deepEqual(sourceReleases.load(saved,source),packet)
 try{globalThis.fetch=async(_url,options)=>{sent.push(JSON.parse(String(options?.body)));if(sent.length===1)throw new TypeError('lost release reply');return Response.json({...observed,reservation_released:true,reservation_release:{project_id:202,operation_key,...packet.body,request:packet.body,preserved_path:'/managed/retained',closure_kind:'physical_domain',released_at:1}})}
  await assert.rejects(sendSourceRelease(packet),/lost release reply/)
  assert.equal((await sendSourceRelease(sourceReleases.load(saved,source)!)).reservation_released,true)
  assert.deepEqual(sent[0],sent[1]);assert.equal(saved.getItem('researcher:source-setup:v1:202'),before)
  globalThis.fetch=async()=>Response.json({...observed,reservation_released:true,reservation_release:{project_id:202,operation_key,...packet.body,release_key:'other',request:packet.body}})
  await assert.rejects(sendSourceRelease(packet),/original/)
 }finally{globalThis.fetch=previous}
 assert.throws(()=>prepareSourceRelease(source,{...observed,worker_active:true}),/detenido|original/)
 assert.throws(()=>prepareSourceRelease(source,{...observed,reservation_released:true}),/cerrada|original/)
})

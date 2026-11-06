/** Original source requests survive reload and unknown replies without borrowing another project, directory or administrative fence. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Exercise persistence boundaries with the same API as real browser storage. */
function storage(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}

test('repair authorization survives reply loss and cannot borrow a different observed source fence',async()=>{
 const {prepareSource,prepareSourceRepair,sourceRepairs,sendSourceRepair}=await import('../src/api/sourceOperations.ts')
 const source=prepareSource(202,{mode:'create',name:'retained',path:'/managed/retained',branch:'main'}),{operation_key,...request}=source.body
 const observed={project_id:202,operation_key,operation_id:'b'.repeat(32),fence:1,request,status:'stopped',worker_active:false,local_closure:'confirmed'} as any
 const packet=prepareSourceRepair(source,observed),saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 sourceRepairs.save(saved,packet);assert.deepEqual(sourceRepairs.load(saved,source),packet)
 assert.throws(()=>prepareSourceRepair(source,{...observed,operation_key:'other'}),/original/)
 try{globalThis.fetch=async(_url,options)=>{sent.push(JSON.parse(String(options?.body)));if(sent.length===1)throw new TypeError('lost repair reply');return Response.json({...observed,fence:2,repair_authorizations:[packet.body]})}
  await assert.rejects(sendSourceRepair(packet),/lost repair reply/)
  assert.equal((await sendSourceRepair(sourceRepairs.load(saved,source)!)).fence,2)
  assert.deepEqual(sent[0],sent[1]);assert.equal((sent[0] as any).fence,1)
  globalThis.fetch=async()=>Response.json({...observed,fence:2,repair_authorizations:[{...packet.body,fence:0}]})
  await assert.rejects(sendSourceRepair(packet),/original/)
  assert.throws(()=>sourceRepairs.save(saved,prepareSourceRepair(source,{...observed,fence:2})),/pendiente/)
 }finally{globalThis.fetch=previous}
})

test('remote creation retains explicit server namespace and visibility without inventing local Git scope',async()=>{
 const {prepareSource,sourcePackets,sendSource}=await import('../src/api/sourceOperations.ts')
 const input={mode:'create_remote' as const,name:'empty',remote_server:'https://forgejo.example/api/v1',remote_owner:'research',private:false}
 const packet=prepareSource(202,input),saved=storage(),previous=globalThis.fetch
 assert.equal(packet.body.path,null);assert.equal(packet.body.branch,null);assert.equal(packet.body.remote_url,null)
 sourcePackets.save(saved,packet)
 assert.deepEqual(sourcePackets.load(saved,202),packet)
 const {operation_key,...request}=packet.body
 try{globalThis.fetch=async(_url,options)=>{const sent=JSON.parse(String(options?.body));assert.equal(sent.remote_server,input.remote_server);assert.equal(sent.remote_owner,'research');assert.equal(sent.private,false);return Response.json({project_id:202,operation_key,operation_id:'a'.repeat(32),fence:1,request,status:'completed',repository_id:null,observation:null})}
  assert.equal((await sendSource(packet)).repository_id,null)
  globalThis.fetch=async()=>Response.json({project_id:202,operation_key,operation_id:'a'.repeat(32),fence:1,request:{...request,remote_server:'https://other.example/api/v1'}})
  await assert.rejects(sendSource(packet),/original/)
 }finally{globalThis.fetch=previous}
 for(const change of [{private:undefined},{remote_server:undefined},{path:'/managed/empty'},{branch:'main'},{use_configured_auth:true}])assert.throws(()=>prepareSource(202,{...input,...change}))
})

test('an uncertain source reply preserves exactly the original create request after reload',async()=>{
 const {prepareSource,sourcePackets,sendSource}=await import('../src/api/sourceOperations.ts')
 const packet=prepareSource(202,{mode:'create',name:'fresh',path:'/managed/fresh',branch:'main'}),saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 const {operation_key,...request}=packet.body
 sourcePackets.save(saved,packet)
 try{globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1)throw new TypeError('lost response');return Response.json({project_id:202,operation_key,operation_id:'a'.repeat(32),fence:1,request,status:'running',worker_active:true})}
  await assert.rejects(sendSource(packet),/lost response/)
  assert.equal((await sendSource(sourcePackets.load(saved,202)!)).status,'running')
  assert.deepEqual(sent[0],sent[1]);assert.equal(sourcePackets.load(saved,101),null)
  assert.throws(()=>sourcePackets.save(saved,prepareSource(202,{mode:'create',name:'other',path:'/managed/other',branch:'main'})),/pendiente/)
 }finally{globalThis.fetch=previous}
})

test('a reply for another source or project is rejected before it can replace the selected operation',async()=>{
 const {prepareSource,sendSource}=await import('../src/api/sourceOperations.ts')
 const packet=prepareSource(202,{mode:'adopt',name:'useful',path:'/managed/useful'}),previous=globalThis.fetch
 const {operation_key,...request}=packet.body
 try{for(const changes of [{project_id:101},{request:{...request,path:'/managed/other'}},{operation_key:'another'}]){
  globalThis.fetch=async()=>Response.json({project_id:202,operation_key,operation_id:'a'.repeat(32),fence:1,request,status:'running',worker_active:true,...changes})
  await assert.rejects(sendSource(packet),/original/)
 }}finally{globalThis.fetch=previous}
 assert.throws(()=>prepareSource(202,{mode:'clone',name:'copy',path:'/managed/copy',remote_url:'https://user:secret@example.test/repo.git'}),/credenciales/)
})

test('a project with only administrative work can preserve a task-free Stop packet',async()=>{
 const {prepareProjectStop,projectPackets,sendProjectStop}=await import('../src/api/projectWorkspace.ts')
 const packet=prepareProjectStop(202,{task_id:null,scope_sha256:'a'.repeat(64)}),saved=storage(),previous=globalThis.fetch
 projectPackets.save(saved,packet)
 try{globalThis.fetch=async()=>Response.json({kind:'project.stop',project_id:202,...packet.body,run_ids:[],execution_ids:[],source_operations:[{operation_key:'source-original'}],status:'requested',closure:'unconfirmed'})
  assert.equal((await sendProjectStop(projectPackets.load(saved,'stop',202)!)).task_id,null)
 }finally{globalThis.fetch=previous}
})

/** Preserve owner task inputs and unresolved receipts across reload without silently retargeting work. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Store pending requests independently of React rendering and network delivery. */
function storage(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}
const draft={title:'Exportar observaciones',description:'Entrada: id/value. Salida: CSV.',type:'documentation',priority:1,complexity:'high',epic_id:5,milestone_id:8,depends_on:[9]}

test('reload retains selected metadata and exact key; pending creation cannot be overwritten',async()=>{
 const {taskCreationPackets,prepareTaskCreation}=await import('../src/api/taskCreation.ts')
 const saved=storage(),packet=prepareTaskCreation(1,draft)
 taskCreationPackets.save(saved,packet)
 assert.deepEqual(taskCreationPackets.load(saved,1),packet)
 assert.equal(packet.body.complexity,'high')
 assert.throws(()=>packet.body.depends_on.push(10),TypeError)
 assert.throws(()=>taskCreationPackets.save(saved,prepareTaskCreation(1,{...draft,title:'Otro objetivo'})),/pendiente/)
 const other=prepareTaskCreation(2,draft);taskCreationPackets.save(saved,other)
 taskCreationPackets.clear(saved,packet)
 assert.deepEqual(taskCreationPackets.load(saved,2),other)
})

test('corrupt scope and changed local bodies block delivery instead of becoming new permission',async()=>{
 const {taskCreationPackets,prepareTaskCreation}=await import('../src/api/taskCreation.ts')
 const saved=storage(),packet=prepareTaskCreation(1,draft)
 saved.setItem('researcher:task-create:v1:1',JSON.stringify({...packet,body:{...packet.body,project_id:2}}))
 assert.throws(()=>taskCreationPackets.load(saved,1),/recuperar/)
 assert.throws(()=>taskCreationPackets.save(saved,packet),/recuperar/)
})

test('a late receipt only clears its exact original local packet',async()=>{
 const {taskCreationPackets,prepareTaskCreation}=await import('../src/api/taskCreation.ts')
 const saved=storage(),old=prepareTaskCreation(1,draft),fresh=prepareTaskCreation(1,{...draft,title:'Nueva intención'})
 taskCreationPackets.save(saved,fresh);taskCreationPackets.clear(saved,old)
 assert.deepEqual(taskCreationPackets.load(saved,1),fresh)
})

test('task receipt acknowledgement checks original project, key, parent and chosen values',async()=>{
 const {verifyTaskCreationReceipt,prepareTaskCreation}=await import('../src/api/taskCreation.ts')
 const packet=prepareTaskCreation(1,draft)
 const original={...packet.body,id:27,status:'backlog',estimated_complexity:'high'}
 assert.doesNotThrow(()=>verifyTaskCreationReceipt(packet,original))
 for(const changed of [{project_id:2},{operation_key:'other'},{epic_id:6},{estimated_complexity:'medium'},{title:'Another task'}])assert.throws(()=>verifyTaskCreationReceipt(packet,{...original,...changed}),/recibo/)
})

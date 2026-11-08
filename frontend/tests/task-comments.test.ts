/** Task-note identity and exact acknowledgement survive scope changes and damaged local state. @module */
import assert from 'node:assert/strict'
import test from 'node:test'
import {prepareTaskComment,taskCommentPackets,verifyTaskCommentReceipt} from '../src/api/taskComments.ts'

/** Emulate the actual session-storage operations without a browser or network. */
function memory(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}
test('task notes remain original across projects/tasks and reject receipt retargeting',()=>{
 const storage=memory(),packet=prepareTaskComment(101,7,'literal example','approval')
 taskCommentPackets.save(storage,packet)
 assert.deepEqual(taskCommentPackets.load(storage,101,7),packet)
 assert.equal(taskCommentPackets.load(storage,202,7),null);assert.equal(taskCommentPackets.load(storage,101,8),null)
 const receipt={id:9,task_id:7,project_id:101,...packet.body,authorizes_work:false as const}
 verifyTaskCommentReceipt(packet,receipt)
 for(const changed of [{project_id:202},{task_id:8},{content:'different'},{authorizes_work:true},{operation_key:'other-key'}])assert.throws(()=>verifyTaskCommentReceipt(packet,{...receipt,...changed} as typeof receipt))
 assert.equal(Object.isFrozen(packet.body),true)
})
test('another unresolved note cannot be overwritten or cleared by a late original receipt',()=>{
 const storage=memory(),first=prepareTaskComment(101,7,'first','comment'),second=prepareTaskComment(101,7,'second','comment')
 taskCommentPackets.save(storage,first);assert.throws(()=>taskCommentPackets.save(storage,second));taskCommentPackets.clear(storage,first)
 taskCommentPackets.save(storage,second);taskCommentPackets.clear(storage,first);assert.deepEqual(taskCommentPackets.load(storage,101,7),second)
})
test('corrupt or unknown stored fields block recovery rather than minting another note',()=>{
 const storage=memory(),packet=prepareTaskComment(101,7,'original','comment')
 storage.setItem('researcher:task-comment:v1:101:7','{broken');assert.throws(()=>taskCommentPackets.load(storage,101,7));assert.throws(()=>taskCommentPackets.save(storage,packet))
 storage.setItem('researcher:task-comment:v1:101:7',JSON.stringify({...packet,extra:'untrusted'}));assert.throws(()=>taskCommentPackets.load(storage,101,7))
})

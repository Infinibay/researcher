/** Original conversational packets remain scoped, immutable and distinct from work admission. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {prepareAnswerPacket,saveAnswerPacket,loadAnswerPacket,clearAnswerPacket,verifyAnswerReceipt} from '../src/api/questionAnswers.ts'
import {ownerNotePackets,prepareOwnerNote,verifyOwnerNoteReceipt} from '../src/api/ownerNotes.ts'

/** Isolate the real packet storage protocol with deterministic tab-local persistence. */
function memory(){const data=new Map<string,string>();return {data,getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>{data.set(key,value)},removeItem:(key:string)=>{data.delete(key)}}}
const question={request_id:17,run_id:'actual-original-run',context_version:3,questions:[],status:'pending' as const,answers:null,answer_context_version:null,ready_for_answer:true}
test('answer recovery preserves option identity, literal text, context and key without creating another request',()=>{
 const storage=memory(),answers={unit:{option_id:'mass_kg'},scope:'mass_kg'},p=prepareAnswerPacket(101,1001,question,answers)
 answers.unit.option_id='volume_l';saveAnswerPacket(storage,p)
 const old=loadAnswerPacket(storage,101,1001,{...question,status:'responded',ready_for_answer:false,answer_context_version:4})!
 assert.deepEqual(old,p);assert.equal(Object.isFrozen(old.body.answers.unit),true)
 assert.deepEqual(old.body.answers,{unit:{option_id:'mass_kg'},scope:'mass_kg'})
 assert.throws(()=>loadAnswerPacket(storage,101,1001,{...question,request_id:18}))
 verifyAnswerReceipt(old,{context_version:4,application:'recorded_for_next_run',inference_started:false})
 clearAnswerPacket(storage,old);assert.equal(loadAnswerPacket(storage,101,1001,question),null)
})
test('answer corruption or an unconfirmed response cannot be treated as a new context or acknowledgement',()=>{
 const storage=memory(),p=prepareAnswerPacket(101,1001,question,{unit:'Gramos'})
 saveAnswerPacket(storage,p)
 assert.throws(()=>verifyAnswerReceipt(p,{context_version:5,application:'recorded_for_next_run',inference_started:false}))
 assert.throws(()=>verifyAnswerReceipt(p,{context_version:4,application:'recorded_for_next_run',inference_started:true}))
 assert.equal(loadAnswerPacket(storage,202,1001,question),null)
 storage.setItem('researcher:question-answer-action:v1:101:1001:actual-original-run','{broken')
 assert.throws(()=>loadAnswerPacket(storage,101,1001,question))
})
test('notes recover the original thread independently of another selected project or thread',()=>{
 const storage=memory(),p=prepareOwnerNote(101,'original-thread','Una observación ilustrativa, todavía no medida.')
 ownerNotePackets.save(storage,p)
 assert.deepEqual(ownerNotePackets.load(storage,101,'original-thread'),p)
 assert.equal(ownerNotePackets.load(storage,202,'original-thread'),null)
 assert.equal(ownerNotePackets.load(storage,101,'another-thread'),null)
 const newer=prepareOwnerNote(101,'original-thread','Otra nota explícita.')
 assert.throws(()=>ownerNotePackets.save(storage,newer))
 ownerNotePackets.clear(storage,p);ownerNotePackets.save(storage,newer);ownerNotePackets.clear(storage,p)
 assert.deepEqual(ownerNotePackets.load(storage,101,'original-thread'),newer)
})
test('a note receipt must confirm the original owner message, thread, project and key',()=>{
 const p=prepareOwnerNote(101,'original-thread','No se verificó la muestra.'),receipt={id:7,project_id:101,from_agent:'user',delivery:'recorded' as const,conversation_type:'user_to_agent',...p.body}
 verifyOwnerNoteReceipt(p,receipt)
 for(const changed of [{project_id:202},{thread_id:'another-thread'},{operation_key:'another-key'},{message:'A different message'},{from_agent:'agent'}])assert.throws(()=>verifyOwnerNoteReceipt(p,{...receipt,...changed}))
})

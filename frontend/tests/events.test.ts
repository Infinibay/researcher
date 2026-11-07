/** Durable pages preserve identity, scope and ordered replay across reconnects. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {applyEventPage,queryBelongsToProject} from '../src/api/events.ts'

/** Construct a canonical committed page with exact decimal IDs. */
function page(ids:string[],after='0',project=101){return {type:'events.page',project_id:project,after_id:after,next_after_id:ids.at(-1)??after,has_more:false,reset_required:false,resume_after_id:null,reset_reason:null,events:ids.map(id=>({event_id:id,type:'run.admitted',project_id:project,data:{},timestamp:'2026-11-07 00:00:00'}))}}

test('replayed pages deduplicate exactly while retaining SQLite integers above JavaScript safe range',()=>{
 const ids=['9007199254740993','9007199254740994','9007199254740995']
 const first=applyEventPage(page(ids.slice(0,2)),101,'0')
 const resumed=applyEventPage(page(ids),101,first.cursor)
 assert.deepEqual([...first.events,...resumed.events].map(e=>e.event_id),ids)
 assert.equal(resumed.cursor,ids[2])
 assert.equal(applyEventPage(page(ids),101,ids[2]).events.length,0)
})

test('whole-page validation rejects gaps, mixed projects and out-of-order events before delivery',()=>{
 for(const value of [page(['2'],'1'),page(['2','1']),page(['1'],'0',202),{...page(['1']),next_after_id:'3'},{...page(['1']),events:[{...page(['1']).events[0],project_id:202}]}]){
  assert.throws(()=>applyEventPage(value,101,'0'))
 }
})

test('retention expiry requires snapshot refresh before resuming at an explicit floor',()=>{
 const result=applyEventPage({...page([],'2'),reset_required:true,resume_after_id:'50',reset_reason:'retention'},101,'2')
 assert.equal(result.reset,true)
 assert.equal(result.cursor,'50')
 assert.deepEqual(result.events,[])
 assert.deepEqual(applyEventPage(page(['51','52'],'50'),101,result.cursor).events.map(e=>e.event_id),['51','52'])
})

test('cache refresh targets the actual project and explicit entity instead of coincidental numeric IDs',()=>{
 assert.equal(queryBelongsToProject(['task-workspace',101,1001],101),true)
 assert.equal(queryBelongsToProject(['task-workspace',202,101],101),false)
 assert.equal(queryBelongsToProject(['finding-registry','index',101,{}],101),true)
 assert.equal(queryBelongsToProject(['wiki','page',202,'project','overview'],101),false)
 assert.equal(queryBelongsToProject(['task',1001,101],101),true)
 assert.equal(queryBelongsToProject(['task',101,202],101),false)
 assert.equal(queryBelongsToProject(['task-comments',1001],101,new Set([1001])),true)
 assert.equal(queryBelongsToProject(['task-comments',101],101,new Set([1001])),false)
})

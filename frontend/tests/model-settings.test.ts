/** Model settings requests retain explicit scope/revision and refuse mismatched receipts after unknown HTTP outcomes. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

test('model settings preserve original scope and pair through reply loss without retargeting another editor',async()=>{
 const {prepareModelSetting,sendModelSetting,readModelSettings}=await import('../src/api/modelSettings.ts')
 const scope={projectId:101,actorId:'reviewer'},profile={model:'selected-model',reasoning_effort:'high'},packet=prepareModelSetting(scope,3,profile)
 scope.projectId=202;profile.model='other-model';const previous=globalThis.fetch,sent:any[]=[]
 const view={project_id:101,actor_id:'reviewer',setting:{scope:'actor:101:reviewer',revision:4,profile:{model:'selected-model',reasoning_effort:'high'}},effective:{model:'selected-model',reasoning_effort:'high',source:'actor:101:reviewer',revision:4},catalog:null,provider:'openai_subscription',applies_to:'new_attempts_only'}
 try{globalThis.fetch=async(url,options)=>{sent.push({url:String(url),body:options?.body?JSON.parse(String(options.body)):null});if(sent.length===1)throw new TypeError('reply lost');return Response.json(view)}
  await assert.rejects(sendModelSetting(packet),/reply lost/);await sendModelSetting(packet);assert.deepEqual(sent[0],sent[1]);assert.equal(packet.body.project_id,101);assert.equal(packet.body.model,'selected-model')
  globalThis.fetch=async()=>Response.json({...view,project_id:202});await assert.rejects(sendModelSetting(packet),/ámbito|original/)
  globalThis.fetch=async()=>Response.json({...view,setting:{...view.setting,revision:5}});await assert.rejects(sendModelSetting(packet),/versión|original/)
  globalThis.fetch=async(url)=>{assert.equal(String(url),'/api/model-settings?project_id=101&actor_id=reviewer');return Response.json(view)};assert.equal((await readModelSettings({projectId:101,actorId:'reviewer'})).catalog,null)
 }finally{globalThis.fetch=previous}
 assert.throws(()=>prepareModelSetting({projectId:null,actorId:'reviewer'},0,null),/proyecto|ámbito/)
 assert.deepEqual(prepareModelSetting({projectId:202,actorId:null},1,null).body,{project_id:202,actor_id:null,expected_revision:1,model:null,reasoning_effort:null})
})

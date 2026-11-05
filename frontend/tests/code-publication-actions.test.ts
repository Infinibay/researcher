/** Publication requests retain their accepted version and destination across uncertain delivery. @module */
import assert from 'node:assert/strict'
import { test } from 'node:test'

test('publication reload and retry preserve the entire original accepted subject and destination',async()=>{
  const {prepareCodePublication,codePublicationActions,sendCodePublication}=await import('../src/api/codePublications.ts')
  const values=new Map<string,string>()
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const action=prepareCodePublication(101,24,'author:a',{acceptanceKey:'accepted-1',attemptId:'author-attempt',contextVersion:3,subjectSha:'a'.repeat(64),reviewSha:'b'.repeat(64),targetRef:'refs/heads/reviewed-change'})
  codePublicationActions.save(storage,action)
  const restored=codePublicationActions.load(storage,101,24,'author:a')!
  assert.deepEqual(restored,action)
  const sent:unknown[]=[]
  const original=globalThis.fetch
  try {
    globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1) throw new TypeError('response lost');return Response.json({run:{run_id:'publication:a',project_id:101,task_id:24,context_version:3,operation_key:action.body.operation_key,execution_kind:'code_publication'},request:{intent:action.body}})}
    await assert.rejects(sendCodePublication(restored),/response lost/)
    await sendCodePublication(codePublicationActions.load(storage,101,24,'author:a')!)
    assert.deepEqual(sent[0],sent[1])
    assert.equal((sent[0] as unknown[])[0],'/api/projects/101/runs/author%3Aa/code-publications')
  } finally {globalThis.fetch=original}
})

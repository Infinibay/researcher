/** Preserve complete tree structure and exact immutable Git identities while reading a selected source. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {buildRepositoryTree,completeRevision,matchesRepositoryFile} from '../src/api/repositoryTree.ts'

test('unordered Git entries retain implicit folders once and all selected file identities',()=>{
 const tree=buildRepositoryTree([{path:'src/deep/file.py',type:'blob',sha:'1'.repeat(40)},{path:'README.md',type:'blob',sha:'2'.repeat(40)},{path:'src',type:'tree',sha:'3'.repeat(40)},{path:'src/other.py',type:'blob',sha:'4'.repeat(40)}])
 assert.deepEqual(tree.map(n=>n.path),['src','README.md'])
 assert.deepEqual(tree[0].children?.map(n=>n.path),['src/deep','src/other.py'])
 assert.equal(tree[0].children?.[0].children?.[0].sha,'1'.repeat(40))
})
test('a selected source revision must be complete; a branch or abbreviated hash cannot masquerade as the snapshot',()=>{
 assert.equal(completeRevision('a'.repeat(40)),'a'.repeat(40))
 assert.equal(completeRevision('b'.repeat(64)),'b'.repeat(64))
 for(const ref of ['main','deadbeef','','a'.repeat(39),'f'.repeat(65)])assert.equal(completeRevision(ref),null)
})
test('a late blob response from another file or Git object is rejected before rendering',()=>{
 const entry={path:'src/report.py',type:'blob' as const,sha:'1'.repeat(40)}
 const file={path:entry.path,sha:entry.sha,content:'137',size:3}
 assert.equal(matchesRepositoryFile(entry,file),true)
 assert.equal(matchesRepositoryFile(entry,{...file,path:'other.py'}),false)
 assert.equal(matchesRepositoryFile(entry,{...file,sha:'2'.repeat(40)}),false)
 assert.equal(matchesRepositoryFile(undefined,file),false)
})

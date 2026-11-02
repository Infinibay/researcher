/** Check the chosen wiki contract before browser layout/interaction verification. @module */
import assert from 'node:assert/strict'
import {before,after,test} from 'node:test'
import {createServer,type ViteDevServer} from 'vite'
let server:ViteDevServer
let useWikiDrafts:typeof import('../src/stores/wikiDrafts.ts').useWikiDrafts
let wikiModel:typeof import('../src/components/wiki/presentation.ts')
let saveWikiRequest:typeof import('../src/hooks/useWiki.ts').saveWikiRequest
let renderWiki:(options?:{noProject?:boolean;wrongProject?:boolean;foreignCache?:boolean;global?:boolean;catalogFailure?:boolean;detailFailure?:boolean;empty?:boolean})=>string
before(async()=>{
 server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true},resolve:{alias:[{find:/^react-router-dom$/,replacement:new URL('../node_modules/react-router-dom/dist/index.mjs',import.meta.url).pathname},{find:/^react-router$/,replacement:new URL('../node_modules/react-router/dist/development/index.mjs',import.meta.url).pathname},{find:/^react-router\/dom$/,replacement:new URL('../node_modules/react-router/dist/development/dom-export.mjs',import.meta.url).pathname}]},ssr:{noExternal:[/react-router/]}})
 ;({renderWiki,wikiModel,saveWikiRequest,useWikiDrafts}=await server.ssrLoadModule('/tests/wiki-design-fixture.tsx'))
})
after(async()=>{await server?.close()})
test('wiki reader shows exact scope/revision, one title and honest contextual status',()=>{
 const html=renderWiki()
 assert.match(html,/Contexto compartido/)
 assert.match(html,/Revisión 3/)
 assert.match(html,/Proyecto Atlas/)
 assert.match(html,/Ver versiones/)
 assert.match(html,/Editar/)
 assert.match(html,/no valida|no es una validación/)
 assert.equal((html.match(/<h1[ >]/g)||[]).length,1)
 assert.match(html,/notes\/intro/)
 assert.doesNotMatch(html,/AI generated|ninguna tarea|in 3 hours|FOREIGN SECRET/)
})
test('a global document is explicitly labelled instead of appearing as local fallback',()=>{
 const html=renderWiki({global:true})
 assert.match(html,/Biblioteca global/)
 assert.match(html,/otros proyectos|todos los proyectos/)
 assert.match(html,/Revisión 3/)
})
test('foreign deep links and poisoned page cache cannot enable edits in the visible project',()=>{
 const linked=renderWiki({wrongProject:true})
 assert.match(linked,/otro proyecto/)
 assert.doesNotMatch(linked,/>Editar<|Contexto compartido/)
 const poisoned=renderWiki({foreignCache:true})
 assert.doesNotMatch(poisoned,/FOREIGN SECRET|>Editar</)
 assert.match(poisoned,/No se pudo consultar la página/)
})
test('wiki index/detail errors offer recovery and are distinct from empty documents',()=>{
 const catalog=renderWiki({catalogFailure:true})
 assert.match(catalog,/No se pudo consultar la lista/)
 assert.doesNotMatch(catalog,/Todavía no hay páginas/)
 const detail=renderWiki({detailFailure:true})
 assert.match(detail,/No se pudo consultar la página/)
 assert.match(detail,/Volver a consultar/)
})
test('empty wiki and missing project provide a concrete next action',()=>{
 assert.match(renderWiki({empty:true}),/Todavía no hay páginas/)
 assert.match(renderWiki({empty:true}),/Nueva página/)
 assert.match(renderWiki({noProject:true}),/Elige un proyecto/)
})

test('wiki retries retain intent and original project; logical paths cannot inject URL scope',()=>{
 const page={id:7,project_id:101,namespace:'project' as const,path:'notes/a?b#c',title:'Observed',content:'Draft text',revision:3,sha256:'hash',parent_path:null}
 const draft=wikiModel.wikiDraft(101,'project',page)
 const first=saveWikiRequest(draft),retry=saveWikiRequest(draft)
 const url=new URL(first.url,'http://fixture')
 assert.equal(url.searchParams.get('project_id'),'101')
 assert.equal(url.searchParams.get('namespace'),'project')
 assert.equal(decodeURIComponent(url.pathname.slice('/api/wiki/'.length)),page.path)
 assert.equal(first.body.page_id,7)
 assert.equal(first.body.expected_revision,3)
 assert.equal(first.body.operation_key,retry.body.operation_key)
 const changed=wikiModel.changeWikiDraft(draft,{content:'Different intent'})
 assert.equal(changed.projectId,101)
 assert.equal(changed.pageId,7)
 assert.notEqual(changed.operationKey,draft.operationKey)
})
test('an explicit wiki rebase cannot target a recreated or foreign page and keeps draft text',()=>{
 const page={id:7,project_id:101,namespace:'project' as const,path:'notes/intro',title:'Observed',content:'Saved text',revision:3,sha256:'hash',parent_path:null}
 const draft=wikiModel.changeWikiDraft(wikiModel.wikiDraft(101,'project',page),{content:'Unsaved text'})
 assert.throws(()=>wikiModel.rebaseWikiDraft(draft,{...page,id:8,revision:1}),/reemplazada/)
 assert.throws(()=>wikiModel.rebaseWikiDraft(draft,{...page,project_id:202}),/reemplazada/)
 const rebased=wikiModel.rebaseWikiDraft(draft,{...page,revision:4,parent_path:'current-parent'})
 assert.equal(rebased.content,'Unsaved text')
 assert.equal(rebased.revision,4)
 assert.equal(rebased.parentPath,null)
 assert.equal(rebased.projectId,101)
})

test('a late wiki receipt cannot clear a newer local intent under the same draft identity',()=>{
 const page={id:7,project_id:101,namespace:'project' as const,path:'notes/intro',title:'Observed',content:'Saved text',revision:3,sha256:'hash',parent_path:null}
 const first=wikiModel.changeWikiDraft(wikiModel.wikiDraft(101,'project',page),{content:'Submitted text'})
 const newer=wikiModel.changeWikiDraft(first,{content:'Newer local intent'})
 useWikiDrafts.getState().clear()
 try {
  useWikiDrafts.getState().put(newer)
  useWikiDrafts.getState().confirm(first.key,first.operationKey,{...page,revision:4})
  assert.equal(useWikiDrafts.getState().drafts[first.key].content,'Newer local intent')
  assert.equal(useWikiDrafts.getState().drafts[first.key].dirty,true)
  useWikiDrafts.getState().confirm(newer.key,newer.operationKey,{...page,revision:5})
  assert.equal(useWikiDrafts.getState().drafts[first.key].dirty,false)
  assert.equal(useWikiDrafts.getState().drafts[first.key].revision,5)
 } finally { useWikiDrafts.getState().clear() }
})

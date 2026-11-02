/** Verify actual Findings rendering, epistemic labels and scoped recovery before browser QA. @module */
import assert from 'node:assert/strict'
import {before,after,test} from 'node:test'
import {createServer,type ViteDevServer} from 'vite'
let server:ViteDevServer
let findingModel:typeof import('../src/components/findings/presentation')
let renderFindings:(options?:{noProject?:boolean;foreign?:boolean;poisoned?:boolean;legacy?:boolean;indexFailure?:boolean;detailFailure?:boolean;empty?:boolean;unsafe?:boolean})=>string
before(async()=>{
 server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true},resolve:{alias:[{find:/^react-router-dom$/,replacement:new URL('../node_modules/react-router-dom/dist/index.mjs',import.meta.url).pathname},{find:/^react-router$/,replacement:new URL('../node_modules/react-router/dist/development/index.mjs',import.meta.url).pathname},{find:/^react-router\/dom$/,replacement:new URL('../node_modules/react-router/dist/development/dom-export.mjs',import.meta.url).pathname}]},ssr:{noExternal:[/react-router/]}})
 ;({renderFindings,findingModel}=await server.ssrLoadModule('/tests/findings-design-fixture.tsx'))
})
after(async()=>{await server?.close()})

test('findings reader shows actual scope and evidence without invented review or confidence',()=>{
 const html=renderFindings();assert.match(html,/Proyecto Atlas/);assert.match(html,/Convención de tasas/)
 assert.match(html,/Sin revisión independiente registrada/);assert.match(html,/policy.txt/);assert.match(html,/Tax rates are fractions/)
 assert.match(html,/Ver cita/);assert.match(html,/Fecha no registrada/);assert.equal((html.match(/<h1[ >]/g)||[]).length,1)
 assert.doesNotMatch(html,/90%|Validado científicamente|AI generated|FOREIGN SECRET/)
})
test('legacy active and numeric declarations are attributed rather than promoted to validation',()=>{
 const html=renderFindings({legacy:true});assert.match(html,/estado heredado/);assert.match(html,/declarada|declarado/)
 assert.match(html,/Agent said validated/);assert.match(html,/no acredita|no demuestra/);assert.doesNotMatch(html,/90% de certeza/)
})
test('foreign deep links and foreign cached rows cannot disclose a claim in the visible project',()=>{
 const html=renderFindings({foreign:true});assert.match(html,/otro proyecto/);assert.doesNotMatch(html,/Convención de tasas|Ver cita/)
 const poisoned=renderFindings({poisoned:true});assert.doesNotMatch(poisoned,/FOREIGN SECRET|Ver cita/);assert.match(poisoned,/No se pudo/)
})
test('findings errors are recoverable and distinct from empty results',()=>{
 const index=renderFindings({indexFailure:true});assert.match(index,/No se pudo consultar la lista/);assert.match(index,/Volver a consultar/)
 const detail=renderFindings({detailFailure:true});assert.match(detail,/No se pudo consultar el hallazgo/);assert.match(detail,/Volver a consultar/)
 assert.match(renderFindings({empty:true}),/No hay hallazgos/);assert.match(renderFindings({noProject:true}),/Elige un proyecto/)
})
test('finding Markdown remains inert and never creates executable script or javascript links',()=>{
 const html=renderFindings({unsafe:true});assert.doesNotMatch(html,/<script>|href="javascript:/);assert.match(html,/no demuestra|no acredita|por sí sola/)
})

test('semantic result pages retain the same corpus and metadata revision before they can be combined',()=>{
 const base={project_id:101,corpus_count:1,finding_ids:[7],corpus_sha256:'a'.repeat(64),record_set_sha256:'b'.repeat(64),search_kind:'semantic_cosine',scientific_confidence:null,full_coverage:true,next_rank:1,matches:[{finding_id:7,topic:'Claim',excerpt:'Text',score:.8,rank:0,record_sha256:'d'.repeat(64)}]}
 assert.equal(findingModel.sameFindingCorpus([base,{...base,next_rank:null}],101),true)
 assert.equal(findingModel.sameFindingCorpus([base,{...base,record_set_sha256:'c'.repeat(64)}],101),false)
 assert.equal(findingModel.sameFindingCorpus([{...base,project_id:202}],101),false)
 assert.equal(findingModel.sameFindingCorpus([{...base,matches:[{...base.matches[0],finding_id:99}]}],101),false)
})

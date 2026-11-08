/** Verify report reading, provenance, error boundaries and scoped task navigation. @module */

import assert from 'node:assert/strict'
import { before,after,test } from 'node:test'
import { createServer,type ViteDevServer } from 'vite'
let server:ViteDevServer
let renderTaskLink:(options?:{foreignProject?:boolean;foreignTask?:boolean})=>Promise<string>
let renderReport:(options?:{detailFailure?:boolean;evidenceFailure?:boolean;legacy?:boolean;noProject?:boolean;wrongProject?:boolean;ownerAccepted?:boolean;changedBody?:boolean})=>string
before(async()=>{
  server = await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true},resolve:{alias:[{find:/^react-router-dom$/,replacement:new URL('../node_modules/react-router-dom/dist/index.mjs',import.meta.url).pathname},{find:/^react-router$/,replacement:new URL('../node_modules/react-router/dist/development/index.mjs',import.meta.url).pathname},{find:/^react-router\/dom$/,replacement:new URL('../node_modules/react-router/dist/development/dom-export.mjs',import.meta.url).pathname}]},ssr:{noExternal:[/react-router/]}})
 ;({renderReport,renderTaskLink}=await server.ssrLoadModule('/tests/report-design-fixture.tsx'))
})
after(async()=>{await server?.close()})
test('saved report reads as one document with explicit review state and a scoped correction link',()=>{
 const html=renderReport()
 assert.match(html,/Borrador · pendiente de revisión/)
 assert.match(html,/href="\/tasks\?project=101&amp;task=24&amp;fromArtifact=9"/)
 assert.match(html,/Contenido original, sin aceptar/)
 assert.equal((html.match(/<h1[ >]/g)||[]).length,1)
 assert.match(html,/Todos los informes/)
})
test('owner acceptance is historical context, separate from stored draft state and current validity',()=>{
 const html=renderReport({ownerAccepted:true})
 assert.match(html,/Aceptación guardada · vigencia por comprobar/)
 assert.match(html,/Estado del documento original: Borrador/)
 assert.match(html,/contexto 3/)
 assert.match(html,/original-author-run/)
 assert.match(html,/Ver aceptación en la tarea original/)
 assert.doesNotMatch(html,/Aceptación vigente|Validado científicamente/)
})
test('changed current bytes are never represented as the version with owner acceptance',()=>{
 const html=renderReport({ownerAccepted:true,changedBody:true})
 assert.match(html,/El contenido actual no coincide con la versión aceptada/)
 assert.match(html,/cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/)
})
test('source panel renders captured quotes safely and retains source/hash provenance',()=>{
 const html=renderReport()
 assert.match(html,/Fuentes del informe/)
 assert.match(html,/policy\.txt/)
 assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt; exact quote/)
 assert.doesNotMatch(html,/<img src="?x/)
 assert.match(html,/reference:8/)
 assert.match(html,/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/)
})
test('detail and evidence failures offer recovery without conflating missing evidence with no citations',()=>{
 const detail=renderReport({detailFailure:true})
 assert.match(detail,/role="alert"/)
 assert.match(detail,/No se pudo cargar el informe/)
 assert.match(detail,/Volver a consultar/)
 const evidence=renderReport({evidenceFailure:true})
 assert.match(evidence,/Contenido original, sin aceptar/)
 assert.match(evidence,/No se pudieron consultar las fuentes/)
 assert.doesNotMatch(evidence,/No hay citas registradas/)
})
test('legacy code artifacts remain readable and project mismatches cannot select another project report',()=>{
 const code=renderReport({legacy:true})
 assert.match(code,/<pre/)
 assert.match(code,/Contenido original, sin aceptar/)
 const mismatch=renderReport({wrongProject:true})
 assert.match(mismatch,/otro proyecto/)
 assert.doesNotMatch(mismatch,/href="\/tasks\?project=101&amp;task=24/)
 assert.match(renderReport({noProject:true}),/Elige un proyecto/)
})

test('report action opens its task and retains a scoped route back to the original report',async()=>{
 const html=await renderTaskLink()
 assert.match(html,/id="task-title-24"/)
 assert.match(html,/href="\/reports\?project=101&amp;artifact=9"/)
 const mismatch=await renderTaskLink({foreignProject:true})
 assert.doesNotMatch(mismatch,/id="task-title-24"/)
 const stale=await renderTaskLink({foreignTask:true})
 assert.doesNotMatch(stale,/OTHER PROJECT SECRET/)
})

test('the unselected report index owns the page heading even when the reader is hidden',()=>{
 const html=renderReport({wrongProject:true})
 assert.match(html,/<h1[^>]*>Informes<\/h1>/)
 assert.match(html,/<h2>Elige un informe para leerlo<\/h2>/)
 assert.equal((html.match(/<h1[ >]/g)||[]).length,1)
})

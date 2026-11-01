/** Verify owner file scope, truthful preview language and recovery before browser QA. @module */
import assert from 'node:assert/strict'
import { before,after,test } from 'node:test'
import { createServer,type ViteDevServer } from 'vite'
let server:ViteDevServer
let renderFiles:(options?:{includeHeader?:boolean;noProject?:boolean;wrongProject?:boolean;foreignCache?:boolean;detailFailure?:boolean;catalogFailure?:boolean;empty?:boolean})=>string
before(async()=>{
 server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true},resolve:{alias:[{find:/^react-router-dom$/,replacement:new URL('../node_modules/react-router-dom/dist/index.mjs',import.meta.url).pathname},{find:/^react-router$/,replacement:new URL('../node_modules/react-router/dist/development/index.mjs',import.meta.url).pathname},{find:/^react-router\/dom$/,replacement:new URL('../node_modules/react-router/dist/development/dom-export.mjs',import.meta.url).pathname}]},ssr:{noExternal:[/react-router/]}})
 ;({renderFiles}=await server.ssrLoadModule('/tests/files-design-fixture.tsx'))
})
after(async()=>{await server?.close()})
test('file inspector identifies the attachment without claiming agent reading or source capture',()=>{
 const html=renderFiles()
 assert.match(html,/Archivos de referencia/)
 assert.match(html,/política &lt;fiscal&gt;\.pdf/)
 assert.match(html,/Adjunto registrado/)
 assert.match(html,/Extraer previa/)
 assert.match(html,/no guarda una fuente para citar/i)
 assert.match(html,/href="\/tasks\?project=101"/)
 assert.equal((html.match(/<h1[ >]/g)||[]).length,1)
 assert.doesNotMatch(html,/ninguna tarea|Texto aún no consultado|<pre/)
 assert.match(html,/2026-11-01T17:39:00\.000Z/)
})
test('foreign project links and poisoned scoped cache cannot expose actionable file details',()=>{
 const html=renderFiles({wrongProject:true})
 assert.match(html,/otro proyecto/)
 assert.doesNotMatch(html,/Extraer previa|Eliminar adjunto/)
 const poisoned=renderFiles({foreignCache:true})
 assert.doesNotMatch(poisoned,/OTHER PROJECT SECRET/)
 assert.match(poisoned,/No se pudo cargar el adjunto/)
})
test('catalog and detail failures retain separate recovery instead of becoming empty lists',()=>{
 const catalog=renderFiles({catalogFailure:true})
 assert.match(catalog,/No se pudo consultar la lista/)
 assert.match(catalog,/Volver a consultar/)
 assert.doesNotMatch(catalog,/Todavía no hay adjuntos/)
 const detail=renderFiles({detailFailure:true})
 assert.match(detail,/No se pudo cargar el adjunto/)
 assert.match(detail,/Todos los archivos/)
 assert.doesNotMatch(detail,/Extraer previa/)
})
test('empty and unselected projects explain how to proceed without starting work',()=>{
 assert.match(renderFiles({empty:true}),/Todavía no hay adjuntos/)
 assert.match(renderFiles({empty:true}),/Subir archivo/)
 assert.match(renderFiles({noProject:true}),/Elige un proyecto/)
})

test('project selector accessible name contains its visible project label',()=>{
 assert.match(renderFiles({includeHeader:true}),/aria-label="Seleccionar proyecto: Atlas de prueba"/)
 assert.match(renderFiles({includeHeader:true,noProject:true}),/aria-label="Seleccionar proyecto: Elegir proyecto…"/)
})

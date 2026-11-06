/** Rendering rejects cross-object source data and preserves literal code independently of Markdown syntax. @module */
import assert from 'node:assert/strict'
import {before,after,test} from 'node:test'
import {createServer,type ViteDevServer} from 'vite'
let server:ViteDevServer,renderFile:(kind:string)=>string
before(async()=>{server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true}});({renderFile}=await server.ssrLoadModule('/tests/repository-file-design-fixture.tsx'))})
after(async()=>{await server?.close()})
test('literal code keeps its exact blob identity and cannot escape through Markdown fences or HTML',()=>{const html=renderFile('code');assert.match(html,/src\/report.py/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);assert.match(html,new RegExp('1'.repeat(40)))})
test('another blob cannot be shown below the selected file name',()=>{const html=renderFile('mismatch');assert.match(html,/no corresponde/);assert.doesNotMatch(html,/foreign-secret/)})
test('failed and pending reads remain distinct from an empty file or successful source observation',()=>{assert.match(renderFile('error'),/No se pudo leer/);assert.match(renderFile('pending'),/Consultando el archivo/);assert.doesNotMatch(renderFile('error'),/Sin archivos/)})

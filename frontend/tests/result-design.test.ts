/** Actual owner delivery UI preserves uncertainty and scientific scope. @module */
import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer, type ViteDevServer } from 'vite'
let server:ViteDevServer
let renderResult:(state?:string)=>string
before(async()=>{server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true}});({renderResult}=await server.ssrLoadModule('/tests/result-design-fixture.tsx'))})
after(async()=>{await server?.close()})
test('delivery shows attributed evidence, frozen reports and actual review limits before a decision',()=>{
 const html=renderResult()
 assert.match(html,/Resultado entregado/)
 assert.match(html,/El texto indica 137 unidades/)
 assert.match(html,/Informe &lt;documental&gt;/)
 assert.match(html,/La medición no se repitió/)
 assert.match(html,/Sin revisión independiente registrada/)
 assert.match(html,/no certifica.*informe completo/)
 assert.match(html,/<button[^>]*disabled=""[^>]*>Aceptar esta entrega<\/button>/)
 assert.match(html,/Pedir cambios/)
})
test('stale and unverifiable deliveries stay inspectable without an accept control',()=>{
 for(const state of ['stale','unknown']){
  const html=renderResult(state)
  assert.match(html,/Informe &lt;documental&gt;/)
  assert.doesNotMatch(html,/>Aceptar esta entrega<\/button>/)
  assert.match(html,state==='stale'?/cambió desde la entrega/:/No se pudo comprobar/)
 }
})
test('a completed turn without explicit delivery cannot invent a final report',()=>{
 const html=renderResult('missing')
 assert.match(html,/no seleccionó una entrega/)
 assert.doesNotMatch(html,/>Aceptar esta entrega<\/button>/)
})
test('recorded acceptance is distinct from scientific validation and remains open to correction',()=>{
 const html=renderResult('accepted')
 assert.match(html,/Aceptación registrada/)
 assert.match(html,/Uso documental/)
 assert.match(html,/no publica.*ni valida científicamente/)
 assert.match(html,/Pedir cambios/)
 assert.doesNotMatch(html,/>Aceptar esta entrega<\/button>/)
})

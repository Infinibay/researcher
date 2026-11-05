/** Code acceptance presents evidence and limitations without conflating completion with publication. @module */
import assert from 'node:assert/strict'
import { after,before,test } from 'node:test'
import { createServer,type ViteDevServer } from 'vite'
let server:ViteDevServer
let renderCodeResult:(state?:string)=>string
before(async()=>{server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true}});({renderCodeResult}=await server.ssrLoadModule('/tests/code-result-design-fixture.tsx'))})
after(async()=>{await server?.close()})
test('code delivery shows exact version, review, quoted source and explicit missing tests',()=>{
  const html=renderCodeResult()
  assert.match(html,/Código entregado/)
  assert.match(html,/Corregir total &lt;impuesto&gt;/)
  assert.match(html,/invoice.py/)
  assert.match(html,/No hay comprobaciones registradas/)
  assert.match(html,/Aceptar esta versión no la publica/)
  assert.match(html,/<button[^>]*disabled=""[^>]*>Aceptar esta versión<\/button>/)
  assert.doesNotMatch(html,/pruebas aprobadas/i)
})
test('rejected or stale reviews preserve readable evidence and prevent a new acceptance',()=>{
  for(const kind of ['rejected','stale']) {
    const html=renderCodeResult(kind)
    assert.match(html,/invoice.py/)
    assert.doesNotMatch(html,/>Aceptar esta versión<\/button>/)
    assert.match(html,kind==='rejected'?/El revisor pide cambios/:/ya no corresponde/)
  }
})
test('owner history remains distinct from publication and code correctness',()=>{
  const html=renderCodeResult('accepted')
  assert.match(html,/Aceptación registrada/)
  assert.match(html,/Acepto con estos límites/)
  assert.match(html,/Aceptar esta versión no la publica/)
  assert.doesNotMatch(html,/>Aceptar esta versión<\/button>/)
  assert.match(html,/Publicar en una rama nueva/)
})

test('a later positive review does not conceal an earlier objection on the same candidate',()=>{
  const html=renderCodeResult('disagreement')
  assert.match(html,/Respaldado por el revisor/)
  assert.match(html,/Objeción confirmada sin resolver/)
  assert.match(html,/La revisión anterior observó una tasa incorrecta/)
  assert.doesNotMatch(html,/>Aceptar esta versión<\/button>/)
})

test('an unreviewed current candidate offers an explicit independent request with no implied acceptance',()=>{
  const html=renderCodeResult('unreviewed')
  assert.match(html,/Solicitar revisión independiente/)
  assert.match(html,/otro agente.*versión.*petición original/)
  assert.match(html,/no acepta ni publica/)
  assert.doesNotMatch(html,/>Aceptar esta versión<\/button>/)
  assert.doesNotMatch(renderCodeResult('stale'),/>Solicitar revisión independiente<\/button>/)
})

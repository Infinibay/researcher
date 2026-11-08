import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { getByRole } from '@testing-library/dom'
import { after, before, test } from 'node:test'
import { createServer, type ViteDevServer } from 'vite'

let server: ViteDevServer
let renderCommand: (options?: {mode?:string;projectId?:number;list?:boolean}) => string
before(async () => {
  server=await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true}})
  ;({renderCommand}=await server.ssrLoadModule('/tests/command-output-fixture.tsx'))
})
after(async () => {await server?.close()})

test('unknown exit and registered closure are separate facts in the owner receipt', () => {
  const html=renderCommand()
  assert.match(html,/Resultado desconocido/)
  assert.match(html,/Cierre local registrado/)
  assert.match(html,/PARTIAL&lt;script&gt;/)
  assert.doesNotMatch(html,/<script>|Trabajo aceptado/)
  assert.match(html,/UTF-8/)
  assert.match(html,/base64/)
  assert.match(html,/Últimos bytes de salida estándar/)
})

test('a zero exit without closure proof does not imply validation', () => {
  const html=renderCommand({mode:'zero'})
  assert.match(html,/Código de salida 0/)
  assert.match(html,/Cierre sin comprobar/)
  assert.doesNotMatch(html,/Cierre local registrado/)
})

test('capture loss and a partial read window have distinct explanations', () => {
  const html=renderCommand({mode:'limited'})
  assert.match(html,/límite de captura/)
  assert.match(html,/resto no quedó guardado/)
  assert.match(html,/más bytes guardados/)
})

test('terminal and bidi controls are visible rather than interpreted', () => {
  const html=renderCommand({mode:'controls'})
  assert.match(html,/A\\u001b\[31m\\u000dB\\u202e/)
  assert.doesNotMatch(html,/\u001b|\u202e/)
})

test('another project never displays cached output from the previous scope', () => {
  const html=renderCommand({projectId:202})
  assert.doesNotMatch(html,/PARTIAL|calculate|Código de salida/)
  assert.match(html,/Consultando la salida/)
})

test('a failed read offers another read without a command execution control', () => {
  const html=renderCommand({mode:'error'})
  assert.match(html,/role="alert"/)
  assert.match(html,/Volver a consultar salida/)
  assert.doesNotMatch(html,/Reejecutar|Iniciar comando/)
})

test('the job list exposes pagination beyond its first page', () => {
  const html=renderCommand({list:true})
  assert.match(html,/27 comandos registrados/)
  assert.match(html,/>Siguientes comandos<\/button>/)
  assert.match(html,/contexto 2/)
  assert.match(html,/no repite/)
})

// Regresses labels that omit the visible word used for speech control.
test('output pagination names contain visible labels in both enabled and disabled streams', () => {
  const dom = new JSDOM(renderCommand())
  try {
    for (const stream of ['salida estándar', 'salida de errores']) {
      const previous = getByRole(dom.window.document.body, 'button', {name: `Anterior: bytes de ${stream}`})
      const next = getByRole(dom.window.document.body, 'button', {name: `Siguiente: bytes de ${stream}`})
      assert.equal(previous.textContent, 'Anterior')
      assert.equal(previous.hasAttribute('disabled'), true)
      assert.equal(next.textContent, 'Siguiente')
      assert.equal(next.hasAttribute('disabled'), stream === 'salida de errores')
    }
  } finally { dom.window.close() }
})

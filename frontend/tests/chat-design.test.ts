import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer, type ViteDevServer } from 'vite'

let server: ViteDevServer
let renderConversation: (options?: {failure?: boolean;empty?:boolean;foreignTask?:boolean;historyFailure?:boolean}) => string
let renderPeerConversation: (acknowledged?: boolean) => string
before(async () => {
  server = await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true},resolve:{alias:[{find:/^react-router-dom$/,replacement:new URL('../node_modules/react-router-dom/dist/index.mjs',import.meta.url).pathname},{find:/^react-router$/,replacement:new URL('../node_modules/react-router/dist/development/index.mjs',import.meta.url).pathname},{find:/^react-router\/dom$/,replacement:new URL('../node_modules/react-router/dist/development/dom-export.mjs',import.meta.url).pathname}]},ssr:{noExternal:[/react-router/]}})
  ;({renderConversation, renderPeerConversation} = await server.ssrLoadModule('/tests/chat-design-fixture.tsx'))
})
after(async () => {await server?.close()})

test('peer messages distinguish source observations, assumptions and receipt from understanding', () => {
  const html = renderPeerConversation()
  assert.match(html, /Mensaje entre agentes registrado/)
  assert.match(html, /No consta recepción/)
  assert.match(html, /Dirigido a investigador · tarea #25 · contexto 2/)
  assert.match(html, /En respuesta al mensaje #29/)
  assert.match(html, /Observaciones del emisor/)
  assert.match(html, /Suposiciones del emisor/)
  assert.match(html, /Puede referirse a masa/)
  assert.match(html, /Fuentes citadas: #7/)
  assert.match(html, /contexto del destinatario cambió/)
  const receipt = renderPeerConversation(true)
  assert.match(receipt, /Recepción reconocida/)
  assert.match(receipt, /Comprensión y aplicación sin verificar/)
  assert.match(receipt, /Este mensaje no autoriza trabajo/)
  assert.doesNotMatch(receipt, /No consta recepción|Propuesta para revisar/)
})

test('conversation shows every pending task and keeps the current exchange visible', () => {
  const html = renderConversation()
  assert.match(html,/Preguntas pendientes/)
  assert.match(html,/data-request-id="501"/)
  assert.match(html,/data-request-id="502"/)
  assert.match(html,/aria-label="Conversación de la tarea"/)
  assert.match(html,/Comprueba los reintentos/)
  assert.match(html,/Hipótesis: falta comprobar el servidor/)
  assert.match(html,/contexto 1/)
  assert.match(html,/Resultado conservado/)
  assert.match(html,/Comprobar &lt;reintentos&gt;/)
  assert.doesNotMatch(html,/AI Slop|Dis[eñ]o hecho por una AI/)
})

test('a selected native question keeps its typed choices and never enables a new start while waiting', () => {
  const html=renderConversation()
  assert.match(html,/Para limitar la revisión/)
  assert.match(html,/Elegir cliente sólo revisa esa carpeta/)
  assert.match(html,/Cliente/)
  assert.match(html,/Servidor/)
  assert.match(html,/<button[^>]*disabled=""[^>]*>Iniciar trabajo<\/button>/)
})

test('task and conversation failures stay explicit and offer a retry', () => {
  assert.match(renderConversation({failure:true}),/No se pudieron recuperar las tareas/)
  const html=renderConversation({historyFailure:true})
  assert.match(html,/No se pudo recuperar la conversación/)
  assert.match(html,/Volver a consultar/)
})

test('a foreign task URL cannot mount that task workspace or its question form', () => {
  const html=renderConversation({foreignTask:true})
  assert.match(html,/Elige una tarea/)
  assert.doesNotMatch(html,/aria-label="Conversación de la tarea"/)
  assert.doesNotMatch(html,/Guardar respuesta/)
})

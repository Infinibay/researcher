import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer, type ViteDevServer } from 'vite'

let server: ViteDevServer
let renderTask: (options?: { failure?: boolean; taskType?: string; inputChange?: boolean }) => string
before(async () => {
  server = await createServer({ configFile: false, server: { middlewareMode: true, hmr: false, ws: false, watch: null }, esbuild: { jsx: 'automatic' }, optimizeDeps: { noDiscovery: true } })
  ;({ renderTask } = await server.ssrLoadModule('/tests/task-design-fixture.tsx'))
})
after(async () => { await server?.close() })

test('the task inspector is a labelled embedded region rather than a modal overlay', () => {
  const output = renderTask()
  assert.match(output, /role="region"/)
  assert.match(output, /aria-labelledby="task-title-24"/)
  assert.doesNotMatch(output, /aria-modal="true"|fixed inset-0/)
  assert.match(output, /Comprobar &lt;reintentos&gt;/)
})

test('research opens on work, preserves the proposal context and cannot silently start again', () => {
  const output = renderTask()
  assert.match(output, /Hallazgo provisional: falta comprobar el servidor/)
  assert.match(output, /resultado bajo contexto 2/)
  assert.match(output, /Contexto vigente: 3/)
  assert.match(output, /<button[^>]*disabled=""[^>]*>Iniciar trabajo<\/button>/)
})

test('a failed task read explains the failure and retains a route back instead of an endless spinner', () => {
  const output = renderTask({ failure: true })
  assert.match(output, /role="alert"/)
  assert.match(output, /No se pudo cargar la tarea/)
  assert.match(output, /Volver a consultar/)
  assert.match(output, /Volver a tareas/)
})


test('task input history shows the concrete before/after and unknown authorship', () => {
  const output = renderTask({ inputChange: true })
  assert.match(output, /Cambios de la tarea/)
  assert.match(output, /Autor no registrado/)
  assert.match(output, /Descripción/)
  assert.match(output, /Base 100/)
  assert.match(output, /Base &lt;200&gt;/)
  assert.doesNotMatch(output, /Base <200>/)
})

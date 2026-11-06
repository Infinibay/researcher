import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer, type ViteDevServer } from 'vite'

let server: ViteDevServer
let renderTaskInputHistory: (changes: import('../src/api/runtime.ts').TaskInputChange[]) => string
let renderTask: (options?: { failure?: boolean; taskType?: string; inputChange?: boolean; inputState?: string; noRuns?: boolean }) => string
before(async () => {
  server = await createServer({ configFile: false, server: { middlewareMode: true, hmr: false, ws: false, watch: null }, esbuild: { jsx: 'automatic' }, optimizeDeps: { noDiscovery: true } })
  ;({ renderTask, renderTaskInputHistory } = await server.ssrLoadModule('/tests/task-design-fixture.tsx'))
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


test('the owner can inspect the frozen host input without mistaking it for understanding', () => {
  const html=renderTask({inputState:'recorded'})
  assert.match(html,/Entrada de esta ejecución/)
  assert.match(html,/Original request &lt;kept&gt;/)
  assert.match(html,/contexto 2/)
  assert.match(html,/1 mensajes anteriores/)
  assert.match(html,/2 mensajes de otras tareas/)
  assert.match(html,/no confirma.*comprendido/)
})

test('missing input history stays unknown and a new conversation is an explicit choice', () => {
  const html=renderTask({inputState:'unknown'})
  assert.match(html,/No hay un registro de entrada/)
  assert.match(html,/Iniciar sin los mensajes anteriores/)
  assert.match(html,/type="checkbox"/)
})

test('native task lifecycle uses explicit work controls instead of a generic done selector',()=>{
 const html=renderTask()
 assert.match(html,/<select[^>]*aria-label="Estado de la tarea"[^>]*disabled=""/)
 assert.match(html,/El estado se controla desde la pestaña Trabajo/)
})


test('structured project context edits remain readable and escaped without crashing task history',()=>{
 const html=renderTaskInputHistory([{version:4,source_kind:'task_metadata',actor:null,changes:{context_json:{before:{project_metadata:{description:'Old <claim>'}},after:{project_metadata:{description:'Inspect 138 units',flags:[true,false]}}}}}])
 assert.match(html,/Old &lt;claim&gt;/);assert.match(html,/Inspect 138 units/);assert.match(html,/project_metadata/);assert.match(html,/true/);assert.match(html,/false/);assert.doesNotMatch(html,/Old <claim>/)
})


test('a migrated technical task cannot use the old lifecycle selector before first admission',()=>{
 const html=renderTask({taskType:'optimization',noRuns:true})
 assert.match(html,/<select[^>]*aria-label="Estado de la tarea"[^>]*disabled=""/)
 assert.match(html,/El estado se controla desde la pestaña Trabajo/)
})

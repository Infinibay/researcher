/** Verify owner-visible milestone scope and historical proposal compatibility before any acceptance. @module */
import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer, type ViteDevServer } from 'vite'

let server: ViteDevServer
let renderPlan: (withMilestones?: boolean) => string
before(async () => {
  server = await createServer({configFile:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},esbuild:{jsx:'automatic'},optimizeDeps:{noDiscovery:true}})
  ;({renderPlan} = await server.ssrLoadModule('/tests/project-structure-fixture.tsx'))
})
after(async () => { await server?.close() })

test('owner review shows complete milestone grouping, proposed dates and task prerequisites', () => {
  const html = renderPlan()
  assert.match(html, /Trabajo propuesto · 2 tareas · 1 hitos/)
  assert.match(html, /Hitos de Parser checks/)
  assert.match(html, /Hito: Evidence gathered/)
  assert.match(html, /Observed cases and limits/)
  assert.match(html, /Fecha propuesta: 2027-01-15/)
  assert.match(html, /Esta fecha no programa ejecuciones/)
  assert.match(html, /Depende de: Read current behavior/)
  assert.match(html, /Demonstrated cases pass/)
  assert.doesNotMatch(html, /Aceptado|Completado/)
})

test('historical drafts without milestones keep all task content and avoid invented dates', () => {
  const html = renderPlan(false)
  assert.match(html, /Read current behavior/)
  assert.match(html, /Change the parser/)
  assert.match(html, /Exact source references/)
  assert.doesNotMatch(html, /Hito:|Fecha propuesta:/)
})

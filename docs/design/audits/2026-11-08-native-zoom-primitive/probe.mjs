/** Probe actual Chromium profile zoom without CSS zoom, emulation scale or an operator browser profile. @module */
import { createRequire } from 'node:module'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import assert from 'node:assert/strict'
const root = process.cwd()
const require = createRequire(path.join(root, 'frontend/package.json'))
const { chromium } = require('@playwright/test')
const output = path.join(root, '.superpowers/sdd/2026-10-31-actualizacion-proyecto/native-zoom-probe')
await fs.mkdir(output, {recursive: false})
const result = {status: 'running', scope: 'Browser primitive on synthetic HTML only; no product acceptance, model, account or operator profile', states: [], source: 'https://chromium.googlesource.com/chromium/src/+/lkgr/chrome/browser/ui/zoom/chrome_zoom_level_prefs.cc'}
const server = http.createServer((request, response) => {
  response.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'})
  response.end('<!doctype html><html lang="es"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prueba local</title><main><h1>Ejemplo de lectura</h1><p>Entrada: dos fuentes. Salida: una comparación con sus límites.</p><button>Consultar fuentes</button></main></html>')
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
try {
  for (const factor of [1, 2, 4]) {
    const profile = path.join(output, 'profile-' + factor)
    await fs.mkdir(path.join(profile, 'Default'), {recursive: true})
    const level = Math.log(factor) / Math.log(1.2)
    await fs.writeFile(path.join(profile, 'Default/Preferences'), JSON.stringify({partition: {default_zoom_level: {x: level}}}))
    const context = await chromium.launchPersistentContext(profile, {channel: 'chromium', headless: true, viewport: null, args: ['--window-size=1280,1024']})
    try {
      const page = await context.newPage()
      await page.goto('http://127.0.0.1:' + server.address().port)
      const metrics = await page.evaluate(() => ({innerWidth, innerHeight, outerWidth, outerHeight, devicePixelRatio, visualScale: visualViewport.scale, visualWidth: visualViewport.width, rootZoom: getComputedStyle(document.documentElement).zoom, rootTransform: getComputedStyle(document.documentElement).transform, scrollWidth: document.documentElement.scrollWidth}))
      const cdp = await context.newCDPSession(page)
      const layout = await cdp.send('Page.getLayoutMetrics')
      result.states.push({factor, preferenceLevel: level, metrics, layout, version: context.browser()?.version()})
      await page.screenshot({path: path.join(output, 'zoom-' + factor + '.png'), fullPage: true})
      assert.equal(metrics.rootZoom, '1')
      assert.equal(metrics.rootTransform, 'none')
      assert.equal(metrics.visualScale, 1)
    } finally { await context.close() }
  }
  const base = result.states[0].metrics
  for (const state of result.states) {
    assert.ok(Math.abs(base.innerWidth / state.metrics.innerWidth - state.factor) < 0.03, 'Browser zoom must change CSS viewport width by the requested factor')
    assert.ok(Math.abs(state.metrics.devicePixelRatio / base.devicePixelRatio - state.factor) < 0.03, 'Browser zoom must change the rendered pixel ratio by the same factor')
    assert.equal(state.metrics.outerWidth, base.outerWidth)
  }
  result.status = 'passed'
} catch (error) { result.error = String(error); throw error }
finally {
  await new Promise(resolve => server.close(resolve))
  await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2) + '\n')
  process.stdout.write(JSON.stringify({status: result.status, states: result.states.map(s => ({factor: s.factor, metrics: s.metrics}))}) + '\n')
}

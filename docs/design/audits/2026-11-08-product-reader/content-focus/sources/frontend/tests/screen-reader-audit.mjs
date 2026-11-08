/** Inspect real installed owner routes through Orca and completed synthesis using native X keyboard input. @module */
import { chromium, expect } from '@playwright/test'
import fs from 'node:fs/promises'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { routes } from './navigation-audit.mjs'

const exec = promisify(execFile)
const output = '/out'
const input = JSON.parse(await fs.readFile(output + '/inputs.json', 'utf8'))
const result = { status: 'running', scope: 'Real installed HTTP/SQLite and Orca/Speech Dispatcher; native X keys; ALSA null, no physical listening or human acceptance',
  routes: [], content: [], pageErrors: [], apiErrors: [] }
let browser, page

/** Send one native X key through the reader, rather than dispatching a CDP keyboard event directly to Chromium. */
async function press(key) {
  await exec('xdotool', ['key', '--clearmodifiers', '--delay', '20', key])
}

/** Capture private Xvfb browser chrome as well as page content when native menus affect reader focus. */
async function captureNative(name) {
  const script = "import sys,gi; gi.require_version('Gdk','3.0'); from gi.repository import Gdk; root=Gdk.get_default_root_window(); image=Gdk.pixbuf_get_from_window(root,0,0,root.get_width(),root.get_height()); image.savev(sys.argv[1],'png',[],[])"
  await exec('python3', ['-c', script, output + '/' + name + '.png'])
}

/** Traverse real focus order with native Tab presses and refuse to force a target's DOM focus. */
async function tabTo(target, limit = 120) {
  for (let count = 0; count <= limit; count += 1) {
    if (await target.evaluate(node => document.activeElement === node)) return count
    await press('Tab')
  }
  throw new Error('Native Tab did not reach target: ' + await target.innerText())
}

/** Retain byte offsets so an announcement from an earlier route cannot satisfy the current observation. */
async function offsets() {
  return { orca: (await fs.stat(output + '/orca-debug.log')).size,
    speech: (await fs.stat(output + '/speech-logs/speech-dispatcher.log')).size }
}

/** Normalize only whitespace/case and XML escaping, preserving the words that the reader actually sent. */
function normalize(text) {
  return text.normalize('NFC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('es')
}

/** Decode simple SSML text for polling; the independent Python verifier parses the retained XML frames. */
function ssmlText(xml) {
  return xml.replace(/<[^>]*>/g, '').replace(/&#(x[0-9a-f]+|[0-9]+);/gi, (_all, code) =>
    String.fromCodePoint(code[0].toLowerCase() === 'x' ? parseInt(code.slice(1), 16) : Number(code)))
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&')
}

/** Require a fresh Orca spoken-output event and exact phrase completed by the real speech module before another key. */
async function heard(phrase, start, mode = 'single') {
  let proof
  await expect.poll(async () => {
    const orca = (await fs.readFile(output + '/orca-debug.log')).subarray(start.orca).toString('utf8')
    const speech = (await fs.readFile(output + '/speech-logs/speech-dispatcher.log')).subarray(start.speech).toString('utf8')
    const spoken = orca.split('\n').filter(line => line.includes('SPEECH OUTPUT:'))
    const backend = [...orca.matchAll(/SPEECH DISPATCHER: Speaking ['"]?(<speak>.*?<\/speak>)/gs)]
    const readerOutput = mode === 'say-all' ? backend.map(match => ({ text: ssmlText(match[1]), record: match[0] })) :
      spoken.map(line => ({ text: line, record: line }))
    const frames = [...speech.matchAll(/Command sent to output module: \|(<speak>.*?<\/speak>)\|/gs)]
    for (const [index, frame] of frames.entries()) {
      const text = ssmlText(frame[1])
      const tail = speech.slice(frame.index + frame[0].length, frames[index + 1]?.index)
      if (normalize(text).includes(normalize(phrase)) && tail.includes('702 END')
          && readerOutput.some(item => normalize(item.text).includes(normalize(phrase)))) {
        proof = { phrase, start, mode, moduleText: text, moduleEnd: true,
          orcaOutput: readerOutput.find(item => normalize(item.text).includes(normalize(phrase))).record }
        return true
      }
    }
    return false
  }, { timeout: 15000, message: 'Fresh Orca output and completed synthesis: ' + phrase }).toBe(true)
  return proof
}

/** Require a processed Orca focus event for the actual focused content node, including a page-owned heading. */
async function readerContentFocus(start) {
  let proof, target
  await expect.poll(async () => {
    target = await page.locator('#main-content').evaluate(main => {
      const node = document.activeElement
      return main.contains(node) ? { id: node.id, tag: node.tagName.toLowerCase(),
        name: node.id ? null : (node.getAttribute('aria-label') || node.textContent.trim()) } : null
    })
    if (!target) return false
    const text = (await fs.readFile(output + '/orca-debug.log')).subarray(start.orca).toString('utf8')
    const blocks = [...text.matchAll(/vvvvv[^\n]*STATE-CHANGED:FOCUSED[^\n]*\n(.*?)\^\^\^\^\^[^\n]*STATE-CHANGED:FOCUSED[^\n]*/gsi)]
    proof = blocks.find(block => {
      const source = block[1].split(/(?:EVENT )?ANY DATA/)[0]
      const identity = target.id ? source.includes('id:' + target.id) :
        source.includes('tag:' + target.tag) && source.includes("name='" + target.name + "'")
      return identity && /states='[^']*\bfocused\b/.test(source)
    })?.[1]
    return !!proof
  }, { timeout: 5000, message: 'Orca processed focus in the current content' }).toBe(true)
  return { start, target, event: proof }
}

/** Read a control's explicitly associated label without inventing a name for unlabeled elements. */
async function controlLabel(control) {
  return control.evaluate(node => node.getAttribute('aria-label') ||
    (node.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean).map(id => document.getElementById(id)?.textContent || '').join(' ').trim() ||
    [...(node.labels || [])].map(label => label.textContent).join(' ').trim() || node.textContent.trim())
}

try {
  if (new URL(input.origin).hostname !== '127.0.0.1') throw new Error('Disposable loopback host required')
  browser = await chromium.launch({ headless: false, executablePath: '/opt/chromium/chrome',
    args: ['--force-renderer-accessibility', '--disable-dev-shm-usage', '--disable-features=Translate,TranslateUI'] })
  page = await browser.newPage({ viewport: { width: 1280, height: 900 }, locale: 'es-ES' })
  page.setDefaultTimeout(10000)
  page.on('pageerror', error => result.pageErrors.push(String(error)))
  page.on('response', response => {
    const path = new URL(response.url()).pathname
    if (path.startsWith('/api/') && response.status() >= 400) result.apiErrors.push({ path, status: response.status() })
  })
  await page.goto(input.origin + '/projects')
  await page.getByLabel('Código de acceso local').fill((await fs.readFile('/run/reader/owner.key', 'utf8')).trim())
  await page.getByRole('button', { name: 'Abrir espacio', exact: true }).click()
  await page.locator('#project-select-' + input.projectId).click()
  await expect(page.getByRole('button', { name: 'Seleccionar proyecto: Atlas comprobable' })).toBeVisible()
  await fs.writeFile(output + '/paired.json', JSON.stringify({ version: browser.version(), title: await page.title(), readerNotStarted: true }))
  await expect.poll(async () => fs.access(output + '/reader-ready.json').then(() => true, () => false), { timeout: 20000 }).toBe(true)
  const { stdout } = await exec('xdotool', ['search', '--onlyvisible', '--name', '^Researcher'])
  const windows = stdout.trim().split(/\s+/)
  await exec('xdotool', ['windowfocus', '--sync', windows.at(-1)])
  // Native browser chrome is outside the application DOM; retain it and dismiss its translation bubble normally.
  await captureNative('browser-chrome-before-escape')
  await press('Escape')
  result.browserChromeEscapeBeforeRoutes = true

  for (const [label, route, region] of routes) {
    const start = await offsets()
    const nav = page.getByRole('navigation', { name: 'Navegación principal' })
    const link = nav.getByRole('link', { name: label, exact: true })
    const tabs = await tabTo(link)
    const navigationSpeech = await heard(label, start)
    const routeStart = await offsets()
    await press('Return')
    await page.waitForURL(url => url.pathname === route)
    await expect(page.locator(region).first()).toBeVisible()
    await expect.poll(() => page.locator('#main-content').evaluate(node => node.contains(document.activeElement))).toBe(true)
    await expect(page.locator('#main-content [role="status"]').filter({ hasText: /Cargando|Consultando/ })).toHaveCount(0)
    const focusSpeech = await readerContentFocus(routeStart)
    const heading = await page.locator('#main-content').getByRole('heading', { level: 1 }).first().innerText()
    if (route === '/tasks') await captureNative('tasks-before-content-control')
    const control = page.locator('#main-content button:visible:enabled, #main-content input:visible:enabled, #main-content select:visible:enabled, #main-content textarea:visible:enabled, #main-content a[href]:visible').first()
    const controlStart = await offsets()
    const controlTabs = await tabTo(control)
    const name = await controlLabel(control)
    expect(name.trim().length).toBeGreaterThan(0)
    const controlSpeech = await heard(name, controlStart)
    const modeStart = await offsets()
    // Orca documents triple-clicking its modifier+A to force sticky browse mode before structural reading.
    await exec('xdotool', ['key', '--clearmodifiers', '--delay', '60', 'Insert+a', 'Insert+a', 'Insert+a'])
    const browseModeSpeech = await heard('Browse mode is sticky', modeStart)
    const headingStart = await offsets()
    await press('1')
    let headingSpeech
    try {
      headingSpeech = await heard(heading, headingStart)
    } catch (originalError) {
      // Diagnostic comparison never upgrades failed SPA navigation into an accepted route.
      result.headingFailure = { route, heading, focusSpeech, originalError: String(originalError) }
      const reloadStart = await offsets()
      await page.reload()
      await expect(page.locator(region).first()).toBeVisible()
      await press('Escape')
      await tabTo(page.getByRole('link', { name: 'Ir al contenido', exact: true }))
      await press('Return')
      await expect(page.locator('#main-content')).toBeFocused()
      await readerContentFocus(reloadStart)
      const reloadedHeadingStart = await offsets()
      await press('1')
      try { result.headingFailure.explicitReloadDiagnostic = await heard(heading, reloadedHeadingStart) }
      catch (reloadError) { result.headingFailure.reloadError = String(reloadError) }
      throw originalError
    }
    await page.screenshot({ path: output + '/' + (route.slice(1) || 'overview') + '.png', fullPage: true })
    result.routes.push({ label, route, tabs, navigationSpeech, focusSpeech, browseModeSpeech, heading, headingSpeech, controlTabs, controlLabel: name, controlSpeech })
    process.stdout.write(JSON.stringify({ route, heading, control: name, status: 'observed' }) + '\n')
  }

  // Inspect the retained owner correction without creating work or modifying context.
  await page.goto(input.origin + '/tasks')
  const task = page.locator('#task-select-' + input.taskId)
  await expect(task).toBeVisible()
  await tabTo(task)
  await press('Return')
  await expect(page.getByText(input.correction, { exact: true })).toBeVisible()
  const contentStart = await offsets()
  await press('KP_Add')
  for (const sentence of input.correction.split(/\.\s+/).filter(Boolean)) {
    result.content.push(await heard(sentence, contentStart, 'say-all'))
  }
  await page.screenshot({ path: output + '/owner-correction.png', fullPage: true })
  expect(result.routes).toHaveLength(routes.length)
  expect(result.pageErrors).toEqual([])
  expect(result.apiErrors).toEqual([])
  result.status = 'passed'
} catch (error) {
  result.status = 'failed'
  result.error = String(error)
  if (page && !page.isClosed()) {
    await captureNative('failure-native').catch(() => {})
    await page.screenshot({ path: output + '/failure.png', fullPage: true }).catch(() => {})
    result.focus = await page.evaluate(() => ({ path: location.pathname, tag: document.activeElement?.tagName,
      id: document.activeElement?.id, text: document.activeElement?.textContent?.slice(0, 160) })).catch(() => null)
  }
  throw error
} finally {
  if (browser) await browser.close()
  await fs.writeFile(output + '/browser-result.json', JSON.stringify(result, null, 2) + '\n')
}

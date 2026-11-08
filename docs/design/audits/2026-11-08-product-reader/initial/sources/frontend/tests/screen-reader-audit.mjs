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
async function heard(phrase, start) {
  let proof
  await expect.poll(async () => {
    const orca = (await fs.readFile(output + '/orca-debug.log')).subarray(start.orca).toString('utf8')
    const speech = (await fs.readFile(output + '/speech-logs/speech-dispatcher.log')).subarray(start.speech).toString('utf8')
    const spoken = orca.split('\n').filter(line => line.includes('SPEECH OUTPUT:'))
    const frames = [...speech.matchAll(/Command sent to output module: \|(<speak>.*?<\/speak>)\|/gs)]
    for (const [index, frame] of frames.entries()) {
      const text = ssmlText(frame[1])
      const tail = speech.slice(frame.index + frame[0].length, frames[index + 1]?.index)
      if (normalize(text).includes(normalize(phrase)) && tail.includes('702 END')
          && spoken.some(line => normalize(line).includes(normalize(phrase)))) {
        proof = { phrase, start, moduleText: text, moduleEnd: true,
          orcaOutput: spoken.find(line => normalize(line).includes(normalize(phrase))) }
        return true
      }
    }
    return false
  }, { timeout: 15000, message: 'Fresh Orca output and completed synthesis: ' + phrase }).toBe(true)
  return proof
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
    args: ['--force-renderer-accessibility', '--disable-dev-shm-usage'] })
  page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
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

  for (const [label, route, region] of routes) {
    const start = await offsets()
    const nav = page.getByRole('navigation', { name: 'Navegación principal' })
    const link = nav.getByRole('link', { name: label, exact: true })
    const tabs = await tabTo(link)
    await heard(label, start)
    await press('Return')
    await page.waitForURL(url => url.pathname === route)
    await expect(page.locator(region).first()).toBeVisible()
    await expect.poll(() => page.locator('#main-content').evaluate(node => node.contains(document.activeElement))).toBe(true)
    await expect(page.locator('#main-content [role="status"]').filter({ hasText: /Cargando|Consultando/ })).toHaveCount(0)
    const heading = await page.locator('#main-content').getByRole('heading', { level: 1 }).first().innerText()
    const headingStart = await offsets()
    await press('1')
    const headingSpeech = await heard(heading, headingStart)
    const control = page.locator('#main-content button:visible:enabled, #main-content input:visible:enabled, #main-content select:visible:enabled, #main-content textarea:visible:enabled, #main-content a[href]:visible').first()
    const controlStart = await offsets()
    const controlTabs = await tabTo(control)
    const name = await controlLabel(control)
    expect(name.trim().length).toBeGreaterThan(0)
    const controlSpeech = await heard(name, controlStart)
    await page.screenshot({ path: output + '/' + (route.slice(1) || 'overview') + '.png', fullPage: true })
    result.routes.push({ label, route, tabs, heading, headingSpeech, controlTabs, controlLabel: name, controlSpeech })
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
  await press('Insert+Down')
  for (const sentence of input.correction.split(/\.\s+/).filter(Boolean)) {
    result.content.push(await heard(sentence, contentStart))
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
    await page.screenshot({ path: output + '/failure.png', fullPage: true }).catch(() => {})
    result.focus = await page.evaluate(() => ({ path: location.pathname, tag: document.activeElement?.tagName,
      id: document.activeElement?.id, text: document.activeElement?.textContent?.slice(0, 160) })).catch(() => null)
  }
  throw error
} finally {
  if (browser) await browser.close()
  await fs.writeFile(output + '/browser-result.json', JSON.stringify(result, null, 2) + '\n')
}

/** Read-only first-pass captures, on an explicitly supplied synthetic local server. */
import { createRequire } from 'node:module'
import { readFile, writeFile, unlink } from 'node:fs/promises'
import path from 'node:path'

const require = createRequire(new URL('../../frontend/package.json', import.meta.url))
const { chromium } = require('playwright')
const { expect } = require('@playwright/test')
const AxeBuilder = require('@axe-core/playwright').default
const configPath = process.argv[2]
const config = JSON.parse(await readFile(configPath, 'utf8'))
await unlink(configPath)
const origin = new URL(config.base_url)
if (!['127.0.0.1', 'localhost'].includes(origin.hostname)) throw new Error('Only the owned local fixture server is supported')
let browser
let page
const evidence = {
  browser: null,
  viewport: config.viewport === 'mobile' ? {width:390,height:844} : {width:1440,height:1024},
  captures: [], blocked_external_origins: [], page_errors: [], assets: [], mutating_requests: [],
}
try {
  browser = await chromium.launch({channel:'chromium',headless:true,chromiumSandbox:true})
  evidence.browser = browser.version()
  const context = await browser.newContext({viewport:evidence.viewport,isMobile:config.viewport === 'mobile',hasTouch:config.viewport === 'mobile',serviceWorkers:'block',locale:'es-ES'})
  await context.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.origin === origin.origin) return route.continue()
    evidence.blocked_external_origins.push(url.origin)
    return route.abort()
  })
  await context.addCookies(config.cookies)
  page = await context.newPage()
  page.on('pageerror',error => evidence.page_errors.push(error.message.slice(0,1000)))
  page.on('request',request => {
    if (!['GET','HEAD','OPTIONS'].includes(request.method())) evidence.mutating_requests.push({method:request.method(),path:new URL(request.url()).pathname})
  })
  page.on('response',response => {
    const resource = response.request().resourceType()
    if (['script','stylesheet'].includes(resource)) evidence.assets.push({path:new URL(response.url()).pathname,status:response.status(),content_type:response.headers()['content-type']})
  })
  /** Save observed layout, accessible structure, pixels and scoped accessibility evidence. */
  async function capture(name) {
    const step = evidence.captures.length + 1
    const label = `${String(step).padStart(2,'0')}-${name}`
    const layout = await page.getByRole('banner').evaluate(header => {
      const bounds = header.getBoundingClientRect()
      return {
        height:bounds.height, cssHeight:getComputedStyle(header).height, scrollHeight:header.scrollHeight,
        controls:[...header.querySelectorAll('button')].map(button => {
          const box = button.getBoundingClientRect()
          return {
            name:button.getAttribute('aria-label') || button.textContent.trim(),
            dropdown:!!button.closest('#project-options'), insideHeader:box.bottom <= bounds.bottom,
            x:box.x, y:box.y, width:box.width, height:box.height,
          }
        }),
      }
    })
    await writeFile(path.join(config.output,label + '.layout.json'),JSON.stringify(layout,null,2))
    await writeFile(path.join(config.output,label + '.aria.yaml'),await page.locator('body').ariaSnapshot())
    await writeFile(path.join(config.output,label + '.txt'),await page.locator('body').innerText())
    await page.screenshot({path:path.join(config.output,label + '.png'),fullPage:true,animations:'disabled'})
    if (config.check && config.viewport === 'mobile' && layout.controls.some(control => !control.dropdown && !control.insideHeader)) throw new Error('Mobile header clips its controls')
    const content = await page.locator('#root').innerText()
    if (!content.trim()) {
      evidence.captures.push({step,route:new URL(page.url()).pathname,label,accepted:false,reason:'blank_app_root'})
      throw new Error('Blank application root; screenshot rejected, no accessibility success claim')
    }
    const axe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()
    await writeFile(path.join(config.output,label + '.axe.json'),JSON.stringify(axe,null,2))
    evidence.captures.push({step,route:new URL(page.url()).pathname,label,violations:axe.violations.map(v => ({id:v.id,impact:v.impact,help:v.help,node_count:v.nodes.length}))})
    if (config.check && axe.violations.length) throw new Error('Accessibility violations: ' + axe.violations.map(v => v.id).join(', '))
  }
  await page.goto(new URL('/tasks',origin).href,{waitUntil:'networkidle',timeout:15000})
  await page.getByRole('heading',{name:'Elige un proyecto para trabajar',exact:true}).waitFor()
  if (config.keyboard) {
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link',{name:'Ir al contenido',exact:true})).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('main')).toBeFocused()
    evidence.keyboard = {skip_link_first:true,skip_moves_focus_to_main:true}
  }
  await capture('tasks-initial')
  if (config.flow !== 'initial') {
    // Targets come from the preceding live ARIA snapshots, not source guesses.
    await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click()
    await capture('project-menu')
    if (['selected','inspector','commands'].includes(config.flow)) {
      await page.getByRole('button',{name:'Research ALPHA_ONLY',exact:true}).click()
      await expect(page.getByRole('button',{name:/^Seleccionar proyecto:/})).toContainText('Research ALPHA_ONLY')
      await page.getByText('Policy report',{exact:true}).waitFor()
      await capture('tasks-selected')
      if (['inspector','commands'].includes(config.flow)) {
        await page.getByRole('button',{name:'#1001 En curso Policy report Investigación Prioridad 2',exact:true}).click()
        await page.getByRole('status').filter({hasText:'Cargando la tarea…'}).waitFor({state:'hidden'})
        await page.getByRole('region',{name:'Policy report',exact:true}).waitFor()
        await page.getByRole('status').filter({hasText:'Recuperando trabajo y contexto…'}).waitFor({state:'hidden'})
        await capture('task-inspector')
        if (config.flow === 'commands') {
          await page.getByText('Comandos y resultados guardados',{exact:true}).click()
          await page.getByRole('button',{name:'Ver salida',exact:true}).waitFor()
          await capture('commands-open')
          await page.getByRole('button',{name:'Ver salida',exact:true}).click()
          await page.getByRole('region',{name:'Salida del comando seleccionado',exact:true}).waitFor()
          await page.getByRole('status').filter({hasText:'Consultando la salida guardada…'}).waitFor({state:'hidden'})
          await page.getByText(`Bytes 1–${config.stdout_bytes} de ${config.stdout_bytes} guardados`,{exact:true}).waitFor()
          await expect(page.getByRole('region',{name:'Salida estándar',exact:true})).toContainText(config.expected_stdout.trim())
          await page.getByRole('region',{name:'Salida estándar',exact:true}).scrollIntoViewIfNeeded()
          await capture('command-output')
        }
      }
      if (config.viewport === 'mobile') {
        await page.getByRole('button',{name:'Menú',exact:true}).click()
        await page.getByRole('link',{name:'Conversación',exact:true}).waitFor()
        await capture('mobile-navigation')
      }
      await page.getByRole('link',{name:'Conversación',exact:true}).click()
      await page.waitForURL(new URL('/chat',origin).href)
      await page.getByRole('heading',{name:'Conversación',exact:true}).waitFor()
      await page.getByText('Policy report',{exact:true}).waitFor()
      await page.getByRole('status').filter({hasText:'Consultando solicitudes…'}).waitFor({state:'hidden'})
      await expect(page.getByRole('heading',{name:'Conversación',exact:true})).toBeInViewport()
      if (config.keyboard) {
        await expect(page.getByRole('main')).toBeFocused()
        evidence.navigation = {main_focused:true,heading_in_viewport:true}
      }
      await capture('chat-selected')
      if (config.flow === 'commands') {
        await page.getByRole('button',{name:'Tarea #1001 Policy report Investigación',exact:true}).click()
        await expect(page.getByRole('status').filter({hasText:/^(Cargando|Recuperando|Consultando)/})).toHaveCount(0)
        await capture('chat-task')
      }
    }
  } else {
    await page.goto(new URL('/chat',origin).href,{waitUntil:'networkidle',timeout:15000})
    await page.getByRole('heading',{name:'Conversación',exact:true}).waitFor()
    await capture('chat-initial')
  }
  if (evidence.mutating_requests.length) throw new Error('Read-only flow unexpectedly submitted a mutation')
  if (evidence.page_errors.length) throw new Error('Uncaught page errors')
  if (evidence.assets.some(asset => asset.status !== 200)) throw new Error('Application asset failed to load')
  if (evidence.blocked_external_origins.length) throw new Error('Unexpected external dependency')
} catch (error) {
  evidence.failure = {name:error.name,message:error.message.slice(0,1000)}
  if (page && !page.isClosed()) {
    try {
      await writeFile(path.join(config.output,'failure.aria.yaml'),await page.locator('body').ariaSnapshot())
      await page.screenshot({path:path.join(config.output,'failure.png'),fullPage:true,animations:'disabled'})
    } catch { /* Preserve the original failure even if diagnostics cannot be saved. */ }
  }
  throw error
} finally {
  if (browser) await browser.close()
  evidence.blocked_external_origins = [...new Set(evidence.blocked_external_origins)]
  await writeFile(path.join(config.output,'capture-evidence.json'),JSON.stringify(evidence,null,2))
}
console.log(JSON.stringify(evidence))

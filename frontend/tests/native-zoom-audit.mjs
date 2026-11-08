/** Audit native Chromium zoom on real owner routes, retaining full viewport captures and keyboard evidence. @module */
import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import { routes, tabTo } from './navigation-audit.mjs'

/** Read CSS viewport, browser zoom indicators and actual focus visibility without changing geometry or scroll. */
async function geometry(page) {
  return page.evaluate(() => {
    const main = document.getElementById('main-content')
    const box = main?.getBoundingClientRect()
    const focused = document.activeElement
    const focusBox = focused?.getBoundingClientRect()
    const selector = document.querySelector('.workspace-project-select button')
    const projectLabelLines = selector && [...selector.childNodes].flatMap(node => {
      if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) return []
      const range = document.createRange()
      range.selectNodeContents(node)
      return [...range.getClientRects()].map(rect => rect.top)
    })
    const visible = focusBox && { left: Math.max(0, focusBox.left), top: Math.max(0, focusBox.top),
      right: Math.min(innerWidth, focusBox.right), bottom: Math.min(innerHeight, focusBox.bottom) }
    for (let ancestor = focused?.parentElement; ancestor && visible; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor), rect = ancestor.getBoundingClientRect()
      if (/(auto|scroll|hidden|clip)/.test(style.overflowX)) {
        visible.left = Math.max(visible.left, rect.left)
        visible.right = Math.min(visible.right, rect.right)
      }
      if (/(auto|scroll|hidden|clip)/.test(style.overflowY)) {
        visible.top = Math.max(visible.top, rect.top)
        visible.bottom = Math.min(visible.bottom, rect.bottom)
      }
    }
    return {
      innerWidth, innerHeight, outerWidth, outerHeight, dpr: devicePixelRatio,
      rootZoom: getComputedStyle(document.documentElement).zoom,
      rootTransform: getComputedStyle(document.documentElement).transform,
      visualScale: visualViewport.scale,
      projectLabelLines: new Set(projectLabelLines).size,
      document: { scrollTop: document.scrollingElement.scrollTop,
        scrollHeight: document.scrollingElement.scrollHeight, clientHeight: document.scrollingElement.clientHeight },
      documentFits: document.documentElement.scrollWidth <= innerWidth,
      main: main && { width: box.width, height: box.height, top: box.top,
        bottom: box.bottom, scrollWidth: main.scrollWidth, clientWidth: main.clientWidth,
        scrollHeight: main.scrollHeight, clientHeight: main.clientHeight, scrollTop: main.scrollTop },
      focus: { tag: focused?.tagName, id: focused?.id, inMain: !!main?.contains(focused),
        width: focusBox?.width, height: focusBox?.height,
        visibleFraction: focusBox?.width && focusBox?.height ?
          Math.max(0, visible.right - visible.left) * Math.max(0, visible.bottom - visible.top) / (focusBox.width * focusBox.height) : 0,
        intersectsViewport: !!focusBox && focusBox.bottom > 0 && focusBox.top < innerHeight
          && focusBox.right > 0 && focusBox.left < innerWidth },
    }
  })
}

/** Capture the entire physical content viewport; Playwright's default screenshot crops at native browser zoom. */
async function captureViewport(cdp, filename) {
  const layout = await cdp.send('Page.getLayoutMetrics')
  const captured = await cdp.send('Page.captureScreenshot', {
    format: 'png', fromSurface: true, captureBeyondViewport: false,
  })
  const bytes = Buffer.from(captured.data, 'base64')
  const png = { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) }
  await fs.writeFile(filename, bytes)
  expect(png.width).toBe(layout.layoutViewport.clientWidth)
  expect(png.height).toBe(layout.layoutViewport.clientHeight)
  return png
}

/** Wait for the browser's actual scroll completion before another key can race an ongoing PageDown animation. */
export async function scrollWithKeyboard(page, key) {
  await page.evaluate(() => {
    window.__researcherAuditScrollEnd = null
    document.addEventListener('scrollend', event => {
      window.__researcherAuditScrollEnd = { target: event.target.id || event.target.nodeName }
    }, { capture: true, once: true })
  })
  await page.keyboard.press(key)
  await expect.poll(() => page.evaluate(() => window.__researcherAuditScrollEnd)).not.toBeNull()
  return page.evaluate(() => window.__researcherAuditScrollEnd)
}

/** Pair a fresh browser profile and select the seeded project through keyboard-operated product controls. */
async function openWorkspace(page, origin, ownerFile, projectId) {
  await page.goto(origin + '/projects')
  const code = page.getByLabel('Código de acceso local')
  await expect(code).toBeVisible()
  await tabTo(page, code)
  await page.keyboard.type((await fs.readFile(ownerFile, 'utf8')).trim())
  await tabTo(page, page.getByRole('button', { name: 'Abrir espacio', exact: true }))
  await page.keyboard.press('Enter')
  const project = page.locator(`#project-select-${projectId}`)
  await expect(project).toBeVisible()
  await tabTo(page, project)
  await expect(project).toBeInViewport()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Seleccionar proyecto: Atlas comprobable' })).toBeVisible()
}

/** Exercise both zoom factors serially, recording route failures without conflating Axe with screen-reader acceptance. */
export async function auditNativeZoom({ origin, ownerFile, output, projectId }) {
  const directory = path.join(output, 'native-zoom')
  await fs.mkdir(directory, { recursive: false })
  const result = { status: 'running', scope: 'Native browser zoom; real installed HTTP/SQLite, keyboard, whole-page Axe; not a screen-reader or human comprehension test',
    states: [], controls: [], failures: [], apiErrors: [], pageErrors: [] }
  let context, page, cdp
  try {
    for (const factor of [2, 4]) {
      const profile = path.join(directory, `profile-${factor}`)
      await fs.mkdir(path.join(profile, 'Default'), { recursive: true })
      await fs.writeFile(path.join(profile, 'Default/Preferences'), JSON.stringify({
        partition: { default_zoom_level: { x: Math.log(factor) / Math.log(1.2) } },
      }))
      context = await chromium.launchPersistentContext(profile, {
        channel: 'chromium', headless: true, viewport: null, args: ['--window-size=1280,1024'],
      })
      page = await context.newPage()
      page.setDefaultTimeout(10000)
      page.on('pageerror', error => result.pageErrors.push({ factor, error: String(error) }))
      page.on('response', response => {
        const url = new URL(response.url())
        if (url.pathname.startsWith('/api/') && response.status() >= 400) {
          result.apiErrors.push({ factor, path: url.pathname, status: response.status() })
        }
      })
      cdp = await context.newCDPSession(page)
      await openWorkspace(page, origin, ownerFile, projectId)
      const metrics = await geometry(page)
      expect(metrics.outerWidth).toBe(1280)
      expect(metrics.outerHeight).toBe(1024)
      expect(metrics.innerWidth).toBe(1280 / factor)
      expect(metrics.dpr).toBe(factor)
      expect(metrics.rootZoom).toBe('1')
      expect(metrics.rootTransform).toBe('none')
      expect(metrics.visualScale).toBe(1)
      result.controls.push({ factor, action: 'keyboard-pairing-and-project-selection', metrics,
        browser: context.browser()?.version() })
      if (metrics.projectLabelLines > 2) result.failures.push({ factor, kind: 'short-project-label-wrap', lines: metrics.projectLabelLines })

      const skip = page.getByRole('link', { name: 'Ir al contenido', exact: true })
      await tabTo(page, skip)
      await expect(skip).toBeInViewport()
      await page.keyboard.press('Enter')
      await expect(page.locator('#main-content')).toBeFocused()
      result.controls.push({ factor, action: 'skip-link', passed: true })

      for (const [label, route, region] of routes) {
        const nav = page.getByRole('navigation', { name: 'Navegación principal' })
        if (!(await nav.isVisible())) {
          await tabTo(page, page.getByRole('button', { name: 'Menú', exact: true }))
          await page.keyboard.press('Enter')
        }
        await expect(nav).toBeVisible()
        const link = nav.getByRole('link', { name: label, exact: true })
        const tabs = await tabTo(page, link)
        await expect(link).toBeInViewport()
        await page.keyboard.press('Enter')
        await page.waitForURL(url => url.pathname === route)
        await expect(page.locator(region).first()).toBeVisible()
        await expect.poll(() => page.locator('#main-content').evaluate(main => main.contains(document.activeElement))).toBe(true)
        await expect(nav).toBeHidden()
        await expect(page.locator('#main-content [role="status"]').filter({ hasText: /Consultando|Cargando/ })).toHaveCount(0)
        const before = await geometry(page)
        const name = `${factor * 100}-${route.slice(1) || 'overview'}`
        const png = await captureViewport(cdp, path.join(directory, `${name}.png`))
        const state = { factor, route, tabs, before, png }
        result.states.push(state)
        if (!before.documentFits || before.main.scrollWidth > before.main.clientWidth + 1
            || before.main.height <= 0 || before.main.top >= before.innerHeight) {
          result.failures.push({ factor, route, kind: 'reflow', layout: before })
        }
        if (!before.focus.inMain || !before.focus.intersectsViewport) {
          result.failures.push({ factor, route, kind: 'route-focus', focus: before.focus })
        }
        // A short CSS viewport is acceptable only if overflowing main content can actually be scrolled.
        if (before.main.scrollHeight > before.main.clientHeight + 1) {
          state.keyboardScrollEnd = await scrollWithKeyboard(page, 'PageDown')
          await expect.poll(() => page.locator('#main-content').evaluate(main => main.scrollTop)).toBeGreaterThan(before.main.scrollTop)
          state.afterKeyboardScroll = await geometry(page)
          await captureViewport(cdp, path.join(directory, `${name}-scrolled.png`))
        } else if (before.document.scrollHeight > before.document.clientHeight + 1) {
          const canScrollDown = before.document.scrollTop + before.document.clientHeight < before.document.scrollHeight - 1
          state.keyboardScrollEnd = await scrollWithKeyboard(page, canScrollDown ? 'PageDown' : 'PageUp')
          await expect.poll(() => page.evaluate(() => document.scrollingElement.scrollTop)).not.toBe(before.document.scrollTop)
          state.afterKeyboardScroll = await geometry(page)
          await captureViewport(cdp, path.join(directory, `${name}-scrolled.png`))
        }
        const control = page.locator('#main-content button:visible, #main-content input:visible, #main-content select:visible, #main-content textarea:visible, #main-content a[href]:visible').first()
        if (await control.count()) {
          state.contentControlTabs = await tabTo(page, control)
          await expect(control).toBeInViewport()
          // Tab may start browser scrolling before it completes. Require the small target to settle fully in view.
          const size = await control.boundingBox()
          if (size.width <= before.innerWidth && size.height <= before.innerHeight) {
            await expect.poll(async () => (await geometry(page)).focus.visibleFraction).toBeGreaterThanOrEqual(0.99)
          }
          state.contentControlFocus = await geometry(page)
          const focus = state.contentControlFocus.focus
          if (focus.width <= before.innerWidth && focus.height <= before.innerHeight && focus.visibleFraction < 0.99) {
            result.failures.push({ factor, route, kind: 'clipped-content-control', focus })
          }
        }
        // Axe may move focus while inspecting controls. Run it only after keyboard observations.
        state.beforeAxeFocus = (await geometry(page)).focus
        const axe = await new AxeBuilder({ page }).analyze()
        state.violations = axe.violations
        state.afterAxeFocus = (await geometry(page)).focus
        if (axe.violations.length) result.failures.push({ factor, route, kind: 'axe', ids: axe.violations.map(v => v.id) })
        process.stdout.write(JSON.stringify({ factor, route, failures: result.failures.length }) + '\n')
      }
      const menu = page.getByRole('button', { name: 'Menú', exact: true })
      await tabTo(page, menu)
      await page.keyboard.press('Enter')
      await tabTo(page, page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Resumen', exact: true }))
      await page.keyboard.press('Escape')
      await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toBeHidden()
      await expect(menu).toBeFocused()
      result.controls.push({ factor, action: 'menu-escape-restores-trigger', passed: true })
      await context.close()
      context = page = cdp = null
    }
    if (result.apiErrors.length) result.failures.push({ kind: 'http', errors: result.apiErrors })
    if (result.pageErrors.length) result.failures.push({ kind: 'script', errors: result.pageErrors })
    expect(result.states).toHaveLength(routes.length * 2)
    result.status = result.failures.length ? 'failed' : 'passed'
    return result
  } catch (error) {
    result.status = 'failed'
    result.failures.push({ kind: 'interaction', error: String(error),
      geometry: page ? await geometry(page).catch(() => null) : null })
    if (cdp) await captureViewport(cdp, path.join(directory, 'failure.png')).catch(() => {})
    throw error
  } finally {
    if (context) await context.close()
    await fs.writeFile(path.join(directory, 'evidence.json'), JSON.stringify(result, null, 2) + '\n')
  }
}

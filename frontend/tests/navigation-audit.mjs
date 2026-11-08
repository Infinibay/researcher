/** Inspect keyboard navigation and narrow reflow across every real product route without initiating agent work. @module */
import { expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const routes = [
  ['Resumen', '/', '.overview-workbench'],
  ['Proyectos', '/projects', '.project-workbench'],
  ['Planificación', '/epics', '.planning-workbench'],
  ['Tareas', '/tasks', '.task-workbench'],
  ['Agentes', '/agents', '.agents-workbench'],
  ['Conversación', '/chat', '.conversation-workbench'],
  ['Documentos', '/wiki', '.wiki-workbench'],
  ['Hallazgos', '/findings', '.findings-workbench'],
  ['Informes', '/reports', '.report-workbench'],
  ['Archivos', '/files', '.files-workbench'],
  ['Repositorios', '/repositories', '.repo-workbench'],
  ['Ejecución', '/flow', '.flow-workbench'],
]

/** Reach a control with actual Tab presses, reporting inaccessible controls instead of forcing DOM focus. */
async function tabTo(page, target, limit = 100) {
  for (let presses = 0; presses <= limit; presses += 1) {
    if (await target.evaluate(node => document.activeElement === node)) return presses
    await page.keyboard.press('Tab')
  }
  throw new Error(`Control not reached after ${limit} Tab presses: ${await target.innerText()}`)
}

/** Exercise all primary routes from existing synthetic owner data; save partial evidence if a step fails. */
export async function auditNavigation(page, output) {
  const result = { scope: 'Real keyboard/HTTP navigation; 320 CSS px tests reflow, not browser zoom or a screen reader',
    states: [], controls: [], failures: [], apiErrors: [] }
  const auditDir = path.join(output, 'navigation')
  await fs.mkdir(auditDir, { recursive: false })
  const origin = new URL(page.url()).origin
  page.on('response', response => {
    const url = new URL(response.url())
    if (url.pathname.startsWith('/api/') && response.status() >= 400) {
      result.apiErrors.push({ path: url.pathname, status: response.status() })
    }
  })
  try {
    for (const width of [1440, 320]) {
      await page.setViewportSize({ width, height: 1024 })
      await page.goto(origin + '/projects')
      await expect(page.locator('.project-workbench')).toBeVisible()
      const skip = page.getByRole('link', { name: 'Ir al contenido', exact: true })
      await tabTo(page, skip)
      await expect(skip).toBeInViewport()
      await page.keyboard.press('Enter')
      await expect(page.locator('#main-content')).toBeFocused()
      result.controls.push({ width, action: 'skip-link', passed: true })

      for (const [label, route, region] of routes) {
        const nav = page.getByRole('navigation', { name: 'Navegación principal' })
        if (width === 320) {
          const menu = page.getByRole('button', { name: 'Menú', exact: true })
          await tabTo(page, menu)
          await page.keyboard.press('Enter')
          await expect(nav).toBeVisible()
        }
        const link = nav.getByRole('link', { name: label, exact: true })
        const tabs = await tabTo(page, link)
        await expect(link).toBeInViewport()
        await page.keyboard.press('Enter')
        await page.waitForURL(url => url.pathname === route)
        await expect(page.locator(region).first()).toBeVisible()
        await expect.poll(() => page.locator('#main-content').evaluate(main => main.contains(document.activeElement))).toBe(true)
        if (width === 320) await expect(nav).toBeHidden()
        // Current routes have polling: wait for loading labels, not network idleness.
        await expect(page.locator('#main-content [role="status"]').filter({ hasText: /Consultando|Cargando/ })).toHaveCount(0)
        const axe = await new AxeBuilder({ page }).analyze()
        const layout = await page.locator('#main-content').evaluate(main => {
          const rect = main.getBoundingClientRect()
          return { documentFits: document.documentElement.scrollWidth <= innerWidth,
            contentFits: main.scrollWidth <= main.clientWidth + 1, width: rect.width, height: rect.height,
            scrollWidth: main.scrollWidth, clientWidth: main.clientWidth,
            workbench: (() => {
              const node = main.firstElementChild
              if (!node) return null
              const box = node.getBoundingClientRect(), style = getComputedStyle(node)
              return { left: box.left, right: box.right, width: box.width,
                marginLeft: style.marginLeft, marginRight: style.marginRight,
                mainPaddingLeft: getComputedStyle(main).paddingLeft }
            })() }
        })
        const name = `${width}-${route.slice(1) || 'overview'}`
        await page.screenshot({ path: path.join(auditDir, `${name}.png`), fullPage: true })
        result.states.push({ name, route, width, tabs, layout, violations: axe.violations })
        if (!layout.documentFits || !layout.contentFits || layout.height < 160) {
          result.failures.push({ route, width, kind: 'reflow', layout })
        }
        if (axe.violations.length) result.failures.push({ route, width, kind: 'axe', ids: axe.violations.map(v => v.id) })
      }
      if (width === 320) {
        const menu = page.getByRole('button', { name: 'Menú', exact: true })
        await tabTo(page, menu)
        await page.keyboard.press('Enter')
        const nav = page.getByRole('navigation', { name: 'Navegación principal' })
        await tabTo(page, nav.getByRole('link', { name: 'Resumen', exact: true }))
        await page.keyboard.press('Escape')
        await expect(nav).toBeHidden()
        await expect(menu).toBeFocused()
        result.controls.push({ width, action: 'menu-escape-restores-trigger', passed: true })
      }
    }
    if (result.apiErrors.length) result.failures.push({ kind: 'http', errors: result.apiErrors })
    return result
  } catch (error) {
    result.failures.push({ kind: 'interaction', error: String(error), focus: await page.evaluate(() => ({
      tag: document.activeElement?.tagName, id: document.activeElement?.id,
      text: document.activeElement?.textContent?.slice(0, 160), path: location.pathname,
    })) })
    await page.screenshot({ path: path.join(auditDir, 'failure.png'), fullPage: true }).catch(() => {})
    throw error
  } finally {
    await fs.writeFile(path.join(auditDir, 'evidence.json'), JSON.stringify(result, null, 2) + '\n')
  }
}

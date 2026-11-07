/** Inspect actual Markdown rendering and readable failure in the installed product, using synthetic owner-authored documents. @module */
import { expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import path from 'node:path'

export const explanation = `# Corregir una decisión durante una tarea

**Una corrección guardada se aplica al siguiente intento.** No cambia lo que el intento anterior ya leyó.

Por ejemplo, pides: «Prepara la migración a PostgreSQL». Mientras el agente trabaja, corriges: «Mantengamos SQLite».

El sistema guarda tu cambio y retira la autoridad del intento que trabajaba con PostgreSQL. Una propuesta basada en esa decisión anterior ya no puede completar la tarea como si siguiera vigente.

**Para continuar:** envía una nueva solicitud para esa tarea. El nuevo intento recibe la corrección de SQLite; guardar la corrección por sí solo no inicia otro trabajo.

**Límite:** corregir no deshace automáticamente cambios que ya se guardaron. Tampoco demuestra que la futura solución funcione: eso requiere sus propias comprobaciones.

\`\`\`mermaid
flowchart TD
accTitle: La corrección separa el trabajo anterior del siguiente
accDescr: Tras corregir la decisión a SQLite, el intento que recibió PostgreSQL pierde autoridad. La corrección queda guardada para otro intento, que sólo comienza cuando envías una nueva solicitud.
A[Intento anterior: PostgreSQL] --> B[Corriges: mantener SQLite]
B --> C[Se retira la autoridad anterior]
C --> D[Corrección guardada: SQLite]
D -->|Nueva solicitud tuya| E[Nuevo intento con SQLite]
\`\`\`

## Si el dibujo está dañado

\`\`\`mermaid
flowchart LR
accTitle: Dibujo incompleto
accDescr: Este dibujo está incompleto. Conserva la explicación y permite revisar el original; no demuestra un resultado nuevo.
A --> [
\`\`\`

## Secuencia de revisión

\`\`\`mermaid
sequenceDiagram
accTitle: Una interpretación corregible
accDescr: El agente propone comparar las capturas. El usuario corrige la unidad; el agente revisa la comparación antes de concluir.
Agente->>Usuario: Propongo comparar las capturas
Usuario->>Agente: La unidad es distinta
Agente->>Usuario: Debemos revisar la comparación
\`\`\``

/** Create through the owner UI, reload from real storage and capture desktop/mobile success plus invalid-source fallback. */
export async function auditInteraction(page, output, navigate) {
  await navigate('Documentos')
  await page.getByRole('button', { name: 'Nueva página' }).click()
  await page.getByLabel('Ruta, por ejemplo arquitectura/contexto', { exact: true }).fill('interaction-example')
  await page.getByLabel('Título', { exact: true }).fill('Un resultado que puedes corregir')
  await page.getByLabel('Texto en Markdown').fill(explanation)
  const saving = page.waitForResponse(r => new URL(r.url()).pathname === '/api/wiki' && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Guardar página', exact: true }).click()
  const saved = await saving
  expect(saved.status()).toBe(201)
  const record = await saved.json()
  await page.reload()
  const document = page.locator('.wiki-document')
  const images = document.getByRole('img')
  await expect(images).toHaveCount(2)
  await expect(document.getByRole('img', { name: 'La corrección separa el trabajo anterior del siguiente' })).toBeVisible()
  await expect(document.getByRole('alert')).toContainText('No se pudo dibujar')
  await expect(document.getByText('Este dibujo está incompleto.', { exact: false }).first()).toBeVisible()
  await expect.poll(() => images.evaluateAll(items => items.every(image => image.complete && image.naturalWidth > 0))).toBe(true)
  const states = []
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1100 })
    await document.scrollIntoViewIfNeeded()
    const name = `interaction-${width}`
    await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true })
    const axe = await new AxeBuilder({ page }).include('.wiki-document').analyze()
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
    states.push({ name, width, fits, violations: axe.violations })
    expect(fits).toBe(true)
  }
  const externalRequests = []
  await page.route('**://diagram-probe.invalid/**', route => {
    externalRequests.push(route.request().url())
    return route.abort()
  })
  await page.getByRole('button', { name: '‹ Volver a documentos', exact: true }).click()
  await page.getByRole('button', { name: 'Nueva página' }).click()
  await page.getByLabel('Ruta, por ejemplo arquitectura/contexto', { exact: true }).fill('interaction-untrusted')
  await page.getByLabel('Título', { exact: true }).fill('Contenido no confiable')
  const hostile = [
    '%%{init: {"securityLevel":"loose"}}%%\nflowchart LR\naccDescr: No aceptar la configuración del documento.\nA --> B',
    'flowchart LR\naccDescr: No cargar imágenes externas.\nA@{ img: "https://diagram-probe.invalid/image.png" }',
    'flowchart LR\naccDescr: Una etiqueta no ejecuta HTML.\nA["<img src=\'//diagram-probe.invalid/track\' onerror=\'window.diagramProbe=1\'>"] --> B',
  ].map(source => '```mermaid\n' + source + '\n```').join('\n\n')
  await page.getByLabel('Texto en Markdown').fill(hostile)
  await page.getByRole('button', { name: 'Guardar página', exact: true }).click()
  await expect(document.getByRole('alert')).toHaveCount(2)
  await expect(document.getByRole('img')).toHaveCount(1)
  await expect.poll(() => document.getByRole('img').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true)
  expect(externalRequests).toEqual([])
  expect(await page.evaluate(() => window.diagramProbe)).toBeUndefined()
  expect(await document.locator('iframe,script,img[onerror]').count()).toBe(0)
  return { document_id: record.id, states, real_mermaid_images: 2, invalid_source_preserved: true,
    untrusted_diagrams: { rejected_configuration_and_external_assets: 2, inert_html_label: true, external_requests: externalRequests },
    scope: 'Owner-authored fictional example, actual saved document and Mermaid rendering; no inference or human comprehension evidence.' }
}

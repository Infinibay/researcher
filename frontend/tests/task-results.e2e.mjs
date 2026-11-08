/** Real installed owner acceptance, receipt recovery and task reopening; never start a model. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use task_results_page.py with its synthetic original delivery')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Synthetic delivered report; actual owner decisions, metadata/notes/relations and original receipt recovery without new inference',states:[],acceptances:[],corrections:[],edits:[],errors:[],checks:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 /** Commit each original decision, lose its first reply and permit only an identical recovery. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=new URL(request.url()).pathname
  if(request.method()==='POST'&&(p===`/api/projects/${ids.alpha}/runs/${ids.run}/result/accept`||p===`/api/projects/${ids.alpha}/tasks/${ids.input}/context-corrections`)){
   const rows=p.endsWith('/accept')?evidence.acceptances:evidence.corrections
   const body=request.postDataJSON(),response=await route.fetch(),receipt=await response.json()
   expect(response.status()).toBe(200)
   if(rows.length){expect(body).toEqual(rows[0].body);expect(receipt).toEqual(rows[0].receipt)}
   rows.push({body,receipt,status:response.status()})
   if(rows.length===1)return route.abort('failed')
   return route.fulfill({response})
  }
  if(request.method()==='POST'&&p.includes('/instructions'))throw new Error('This evaluation must not admit a new model request')
  if((request.method()==='PUT'&&p===`/api/tasks/${ids.input}`)||(request.method()==='POST'&&[ `/api/tasks/${ids.input}/comments`,`/api/tasks/${ids.output}/dependencies`].includes(p))){
   const response=await route.fetch(),receipt=await response.json()
   expect(response.status()).toBe(request.method()==='POST'?201:200)
   evidence.edits.push({path:p,method:request.method(),body:request.postDataJSON(),status:response.status(),receipt})
   return route.fulfill({response})
  }
  return route.continue()
 })
 /** Save actual rendered states with regional keyboard/accessibility and width observations. */
 async function capture(name,width=1440,selector){await page.setViewportSize({width,height:1024});await (selector?page.locator(selector):page.getByRole('region',{name:'Resultado entregado',exact:true})).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.task-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])}
 await page.goto(`${origin}/tasks?project=${ids.alpha}&task=${ids.input}`)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 const delivery=page.getByRole('region',{name:'Resultado entregado',exact:true})
 await expect(delivery.getByText('Ejemplo sintético de entrada, relación y salida.',{exact:true})).toBeVisible()
 await delivery.locator('summary').filter({hasText:'Una observación y su fila CSV'}).click()
 await expect(delivery.getByText('Mostrar cómo pasar de una observación a una fila CSV. Es un ejemplo sintético, no un dato medido.',{exact:true})).toBeVisible()
 await expect(delivery.getByRole('button',{name:'Aceptar esta entrega',exact:true})).toBeDisabled()
 await capture('01-original-delivery-input-output')
 await delivery.getByRole('checkbox').check()
 await delivery.getByLabel(/Nota para esta decisión/).fill('Decisión sintética para probar el recorrido; no aceptación humana ni científica.')
 await delivery.getByRole('button',{name:'Aceptar esta entrega',exact:true}).click()
 await expect(delivery.getByRole('alert')).toContainText('No quedó confirmada')
 await capture('02-acceptance-committed-reply-lost',390)
 await page.reload()
 await delivery.getByRole('button',{name:'Consultar la misma decisión',exact:true}).click()
 await expect(delivery.getByText('Aceptación registrada para esta entrega.',{exact:true})).toBeVisible()
 await expect(delivery.getByText('La decisión corresponde a la versión vigente.',{exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Iniciar trabajo',exact:true})).toBeDisabled()
 await capture('03-original-acceptance-recovered')
 const change='Añade una segunda observación de ejemplo y muestra cómo se conserva su orden en el CSV; los ejemplos siguen siendo sintéticos.'
 await delivery.getByLabel('Qué debe cambiar',{exact:true}).fill(change)
 await delivery.getByRole('button',{name:'Pedir cambios',exact:true}).click()
 await expect(delivery.getByRole('alert')).toContainText('No quedó confirmada')
 await capture('04-change-committed-reply-lost',390)
 await page.reload()
 await delivery.getByRole('button',{name:'Consultar la misma decisión',exact:true}).click()
 await expect(delivery.getByText('Cambios registrados. La próxima ejecución usará el nuevo contexto; todavía no comenzó.',{exact:true})).toBeVisible()
 await expect(delivery.getByText('Es una decisión histórica; no confirma la aceptación de los requisitos actuales.',{exact:true})).toBeVisible()
 await expect(page.getByText('Contexto vigente: 2 · resultado bajo contexto 1',{exact:true})).toBeVisible()
 await page.getByLabel('Solicitud para esta tarea',{exact:true}).fill('Usa las dos observaciones sintéticas y muestra el CSV de salida.')
 await expect(page.getByRole('button',{name:'Iniciar trabajo',exact:true})).toBeEnabled()
 await capture('05-reopened-context-explicit-new-request',390)
 await delivery.locator('summary').filter({hasText:'Una observación y su fila CSV'}).click()
 await expect(delivery.getByText('Mostrar cómo pasar de una observación a una fila CSV. Es un ejemplo sintético, no un dato medido.',{exact:true})).toBeVisible()
 await capture('06-original-report-and-historic-acceptance')
 await page.locator('.task-tabs').getByRole('button',{name:'Detalles',exact:true}).click()
 await page.getByRole('button',{name:'Editar título',exact:true}).click()
 const title='Leer una observación de ejemplo'
 await page.getByLabel('Título de la tarea',{exact:true}).fill(title)
 await page.getByLabel('Título de la tarea',{exact:true}).press('Enter')
 await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Añadir descripción',exact:true}).click()
 const description='Objetivo: explicar una transformación. Entrada sintética: id=7, measurement=12. Salida esperada: fila CSV 7,12 con columnas id,value. Falta comprobar la estructura real.'
 await page.getByLabel('Descripción de la tarea',{exact:true}).fill(description)
 await page.getByRole('button',{name:'Guardar',exact:true}).click()
 await expect(page.getByText(description,{exact:true})).toBeVisible()
 await capture('07-metadata-saved-with-keyboard-title',1440,'.task-inspector')
 await page.locator('.task-tabs').getByRole('button',{name:'Comentarios',exact:true}).click()
 const comments=page.getByRole('region',{name:'Comentarios de la tarea',exact:true})
 await comments.getByLabel('Tipo de nota',{exact:true}).selectOption('approval')
 await comments.getByLabel('Tu comentario',{exact:true}).fill('Nota sintética de lectura; esta etiqueta no acepta el contexto nuevo.')
 await comments.getByRole('button',{name:'Guardar comentario',exact:true}).click()
 await expect(comments.getByText('Nota sintética de lectura; esta etiqueta no acepta el contexto nuevo.',{exact:true})).toBeVisible()
 await capture('08-note-does-not-accept-current-task',390,'.task-inspector')
 await page.goto(`${origin}/tasks?project=${ids.alpha}&task=${ids.output}`)
 await page.locator('.task-tabs').getByRole('button',{name:'Dependencias de esta tarea',exact:true}).click()
 const relations=page.getByRole('region',{name:'Relaciones de la tarea',exact:true})
 await relations.getByRole('button',{name:'Editar prerrequisitos',exact:true}).click()
 await relations.getByRole('checkbox',{name:title,exact:true}).uncheck()
 await relations.getByRole('button',{name:'Guardar dependencias',exact:true}).click()
 await expect(relations.getByRole('button',{name:'Guardar dependencias',exact:true})).toHaveCount(0)
 await expect(relations.getByText('No hay prerrequisitos declarados.',{exact:true})).toBeVisible()
 await capture('09-explicit-dependency-removal',390,'.task-inspector')
 await relations.getByRole('button',{name:'Editar prerrequisitos',exact:true}).click()
 await relations.getByRole('checkbox',{name:title,exact:true}).check()
 await relations.getByRole('button',{name:'Guardar dependencias',exact:true}).click()
 await expect(relations.getByRole('button',{name:'Guardar dependencias',exact:true})).toHaveCount(0)
 await expect(relations.getByText(`#${ids.input} · ${title}`,{exact:true})).toBeVisible()
 await capture('10-original-direction-restored',1440,'.task-inspector')
 await page.goto(`${origin}/tasks?project=${ids.alpha}&task=${ids.input}`)
 await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible()
 await expect(page.getByText('Contexto vigente: 4 · resultado bajo contexto 1',{exact:true})).toBeVisible()
 await expect(delivery.getByText('Es una decisión histórica; no confirma la aceptación de los requisitos actuales.',{exact:true})).toBeVisible()
 expect(evidence.acceptances).toHaveLength(2);expect(evidence.corrections).toHaveLength(2);expect(evidence.errors).toEqual([])
 expect(evidence.edits).toHaveLength(5)
 evidence.checks.push('original-frozen-input-output-report','acknowledgement-required','acceptance-commit-before-reply-loss','exact-acceptance-receipt-after-reload','closed-current-acceptance-blocks-new-work','change-commit-before-reply-loss','exact-change-receipt-after-reload','historic-acceptance-retained','current-context-two-original-context-one','explicit-new-request-enabled-never-sent','original-frozen-report-retained','no-page-errors-or-regional-axe-violations')
 evidence.checks.push('keyboard-title-and-description-persist','approval-note-does-not-accept-new-context','dependency-removal-and-restoration-original-direction','metadata-context-four-historical-acceptance-still-retained')
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

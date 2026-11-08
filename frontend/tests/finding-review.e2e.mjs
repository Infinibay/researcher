/** Recover an original owner review admission and inspect its synthetic decision on actual installed HTTP. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const fixture=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
const intent=fixture.intent,ids=fixture.original
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use finding_review_page.py on its guarded synthetic installation')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Existing synthetic reviewer decision; actual exact admission recovery/Stop HTTP, no generative turn',states:[],checks:[],writes:[],faults:[],errors:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(packet=>{
  if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:packet.projectId},version:0}))
  if(!sessionStorage.getItem('review-fixture-packet-loaded')){
   sessionStorage.setItem(`review-intent:${packet.projectId}:${packet.findingId}`,JSON.stringify(packet))
   sessionStorage.setItem('review-fixture-packet-loaded','1')
  }
 },intent)
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('response',response=>{const p=new URL(response.url()).pathname,m=response.request().method();if(p.startsWith('/api/')&&m!=='GET'&&p!=='/api/session')evidence.writes.push({method:m,path:p,status:response.status()})})
 let failState=true,failSource=false
 const statePath=`/api/projects/${intent.projectId}/findings/${intent.findingId}/review-state`
 const sourcePath=`/api/projects/${intent.projectId}/research-sources/${ids.draft.source}`
 /** Read faults preserve original mutation/source identities and never substitute response bodies. */
 await page.route('**/api/**',async route=>{
  const r=route.request(),p=new URL(r.url()).pathname
  if(r.method()==='GET'&&((failState&&p===statePath)||(failSource&&p===sourcePath))){evidence.faults.push({path:p,kind:'abort-read'});return route.abort('failed')}
  return route.continue()
 })
 /** Save actual review states and regional accessibility/overflow checks. */
 async function capture(name,width=1440,selector='.findings-review'){
  await page.setViewportSize({width,height:1024});await page.locator(selector).scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true})
  const axe=await new AxeBuilder({page}).include('.findings-workbench').analyze()
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)
  evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])
 }
 /** Change project through the same global selector used by the owner. */
 async function project(from,to){await page.getByRole('button',{name:`Seleccionar proyecto: ${from}`}).click();await page.getByRole('button',{name:to,exact:true}).click()}
 await page.goto(origin+`/findings?project=${intent.projectId}&finding=${intent.findingId}`)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 const review=page.getByRole('region',{name:'Revisión independiente',exact:true})
 await expect(review.getByRole('alert').filter({hasText:'No se pudo consultar la revisión.'})).toBeVisible()
 await expect(page.getByRole('button',{name:'Reenviar la misma solicitud',exact:true})).toBeVisible()
 await capture('01-uncertain-original-request')
 failState=false
 const replay=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/projects/${intent.projectId}/tasks/${intent.taskId}/finding-reviews`&&r.request().method()==='POST')
 await page.getByRole('button',{name:'Reenviar la misma solicitud',exact:true}).click()
 const response=await replay,run=await response.json()
 expect(response.status()).toBe(202);expect(run.run_id).toBe(fixture.run);expect(run.operation_key).toBe(intent.operation_key)
 const {projectId,taskId,findingId,...body}=intent
 expect(response.request().postDataJSON()).toEqual({...body,finding_id:findingId})
 evidence.replayed={run:run.run_id,status:response.status(),operation_key:run.operation_key}
 await expect(review).toContainText('Revisión terminada')
 await expect(review.getByRole('heading',{name:'Respaldado en lo comprobado',exact:true})).toBeVisible()
 await expect(review).toContainText('Decisión sintética para probar la interfaz; no fue generada por un revisor.')
 await expect(review).toContainText('Confianza científica: sin evaluar.')
 await expect(page.getByRole('button',{name:'Reenviar la misma solicitud',exact:true})).toHaveCount(0)
 await review.getByText('Procedencia de esta revisión',{exact:true}).click()
 await expect(review).toContainText('research-reviewer')
 await expect(review).toContainText(fixture.authorAttempt)
 await capture('02-original-decision-and-provenance')
 await capture('03-mobile-decision-and-limits',390)
 failSource=true
 await review.getByRole('button',{name:'Abrir captura de la revisión',exact:true}).click()
 const source=page.getByRole('region',{name:'Captura usada en la revisión',exact:true})
 await expect(source.getByRole('alert')).toContainText('No se pudo recuperar la captura con la versión citada')
 await capture('04-review-source-read-failed',390,'.findings-source')
 failSource=false;await source.getByRole('button',{name:'Volver a consultar la captura',exact:true}).click()
 await expect(source.locator('mark')).toHaveText(ids.draft.quote)
 await capture('05-reviewed-original-source',390,'.findings-source')
 await source.getByRole('button',{name:'‹ Volver a la revisión',exact:true}).click()
 await expect(review.getByRole('button',{name:'Abrir captura de la revisión',exact:true})).toBeFocused()
 await review.getByRole('button',{name:'Cerrar intento',exact:true}).click()
 await expect(review.getByRole('button',{name:'Cerrar intento',exact:true})).toHaveCount(0)
 await expect(review.getByRole('heading',{name:'Respaldado en lo comprobado',exact:true})).toBeVisible()
 await expect(review.getByLabel('Intentos guardados')).toBeVisible()
 await capture('06-closed-review-keeps-decision',1440)
 await page.reload()
 await expect(review.getByRole('heading',{name:'Respaldado en lo comprobado',exact:true})).toBeVisible()
 expect(await page.evaluate(packet=>sessionStorage.getItem(`review-intent:${packet.projectId}:${packet.findingId}`),intent)).toBe(null)
 await project('Inventario documentado','Archivo separado')
 await expect(page.getByRole('alert')).toContainText('Este enlace corresponde a otro proyecto')
 await expect(page.locator('.findings-workbench')).not.toContainText('Ejemplo sintético: la cita guardada')
 await capture('07-foreign-project-link-not-retargeted',390,'.findings-index')
 await project('Archivo separado','Inventario documentado')
 await expect(review.getByRole('heading',{name:'Respaldado en lo comprobado',exact:true})).toBeVisible()
 await capture('08-original-project-return',1440)
 evidence.checks.push('read-error-not-empty-review','exact-existing-admission-recovered-once','same-original-run-context-and-request','decision-limits-not-scientific-certainty','reviewer-author-provenance','original-reviewed-source-and-version','source-read-failure-retry','source-focus-return','stop-original-review-keeps-decision','reload-clears-only-original-packet','foreign-link-and-project-return')
 expect(evidence.writes).toEqual([{method:'POST',path:`/api/projects/${projectId}/tasks/${taskId}/finding-reviews`,status:202},{method:'POST',path:`/api/projects/${projectId}/runs/${fixture.run}/stop`,status:202}])
 expect(evidence.errors).toEqual([]);evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

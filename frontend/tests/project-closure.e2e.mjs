/** Exact nonempty installed project report/closure and overview navigation; synthetic documentary decisions, no model work. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use project_closure_page.py and its original accepted documentary graph')
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',decisions:[],completion_reads:[],states:[],errors:[],checks:[]},browser=await chromium.launch({headless:true})
const review=process.env.RESEARCHER_E2E_REVIEW_ORIGINAL
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',error=>evidence.errors.push(String(error)))
 const endpoint=`/api/projects/${ids.alpha}/runs/${ids.run}/project-plan/completion`
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=new URL(request.url()).pathname
  if(request.method()==='GET'&&p===endpoint){const response=await route.fetch(),body=await response.json();expect(response.status()).toBe(200);evidence.completion_reads.push({report_sha256:body.report_sha256,acceptance:body.acceptance,acceptance_current:body.acceptance_current,eligible:body.eligible});return route.fulfill({response})}
  if(review&&request.method()==='POST'&&p.startsWith('/api/projects/'))throw new Error('Retained review is readonly')
  if(request.method()==='POST'&&p===endpoint+'/accept'){
   expect(evidence.decisions).toHaveLength(0)
   const body=request.postDataJSON();expect(body.report_sha256).toBe(ids.report_sha256)
   const response=await route.fetch(),receipt=await response.json();expect(response.status()).toBe(200);expect(receipt.snapshot.tasks).toHaveLength(3);expect(receipt.snapshot.deliveries).toHaveLength(2);expect(receipt.publication_performed).toBe(false)
   evidence.decisions.push({body,receipt,status:response.status()});return route.abort('failed')
  }
  if(request.method()==='POST'&&(p.startsWith('/api/tasks/')||p.startsWith('/api/projects/')||p.startsWith('/api/chat/')))throw new Error('Only the exact reviewed closure is permitted')
  return route.continue()
 })
 /** Keep each capture regional and restore viewport before the next real owner action. */
 async function capture(name,width=1440,selector='[aria-label="Informe y cierre del proyecto"]'){const previous=page.viewportSize();try{await page.setViewportSize({width,height:1024});await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include(selector).analyze(),fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);expect(fits).toBe(true);expect(axe.violations).toEqual([]);evidence.states.push({name,width,fits,violations:axe.violations})}finally{await page.setViewportSize(previous)}}
 /** Reach the actual original plan instead of accepting a different run selected by a default. */
 async function closure(){await expect(page.locator(`#task-title-${ids.task}`)).toBeVisible();await page.getByRole('button',{name:'Trabajo',exact:true}).click();const region=page.getByRole('region',{name:'Informe y cierre del proyecto',exact:true});await expect(region.getByRole('heading',{name:'Informe y cierre del proyecto',exact:true})).toBeVisible();return region}
 const url=`${origin}/tasks?project=${ids.alpha}&task=${ids.task}&planRun=${ids.run}`
 await page.goto(url);await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim());await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 let region=await closure()
 if(!review){
 await expect(region.getByRole('button',{name:'Aceptar este informe y cerrar el proyecto',exact:true})).toBeDisabled()
 await region.getByText('Leer el informe completo y sus límites',{exact:true}).click()
 const report=region.getByRole('region',{name:'Contenido completo del informe',exact:true})
 await expect(report).toContainText('Documentar una observación ilustrativa');await expect(report).toContainText('Explicar la fila CSV y sus límites');await expect(report).toContainText('No se comprobó la estructura de los registros reales.')
 await report.focus();await expect(report).toBeFocused()
 await capture('01-nonempty-original-report-and-limits')
 const statement='Acepto sólo la documentación del ejemplo y su relación de campos. No confirma mediciones reales ni implementa un exportador; esas cosas quedan fuera de este alcance sintético.'
 await region.getByLabel('Tu decisión sobre el alcance y los límites',{exact:true}).fill(statement)
 await region.getByRole('button',{name:'Aceptar este informe y cerrar el proyecto',exact:true}).click()
 await expect(region.getByRole('alert')).toContainText('No se confirmó el cierre')
 await capture('02-one-closure-committed-with-reply-lost',390)
 }else{const original=JSON.parse(await fs.readFile(review,'utf8'));evidence.decisions=original.decisions;evidence.completion_reads=original.completion_reads;evidence.states=original.states}
 const statement=evidence.decisions[0].body.statement
 await page.reload();region=await closure()
 await expect(region.getByText('Cierre aceptado para este alcance y evidencia.',{exact:true})).toBeVisible()
 await expect(region.getByRole('button',{name:'Recuperar la misma decisión de cierre',exact:true})).toHaveCount(0)
 await region.getByText('Consultar el informe aceptado originalmente',{exact:true}).click()
 await expect(region).toContainText(statement)
 await expect(region.getByRole('region',{name:'Informe histórico aceptado',exact:true})).toContainText('El ejemplo no es una medición real.')
 await capture('03-original-acceptance-recovered-through-exact-read')
 await page.goto(origin)
 const overview=page.locator('.overview-workbench'),link=overview.getByRole('link',{name:`Informe de cierre · tarea ${ids.task}`,exact:true})
 await expect(link).toHaveAttribute('href',`/tasks?project=${ids.alpha}&task=${ids.task}&planRun=${encodeURIComponent(ids.run)}`)
 await expect(overview).toContainText('Vigencia pendiente de comprobar. Abre el informe y su contexto original.')
 await capture('04-overview-original-accepted-report-link',1440,'.overview-workbench');await capture('05-mobile-overview-original-report-link',390,'.overview-workbench')
 await link.focus();await page.keyboard.press('Enter');region=await closure();await expect(region.getByText('Cierre aceptado para este alcance y evidencia.',{exact:true})).toBeVisible()
 expect(evidence.decisions).toHaveLength(1);expect(evidence.errors).toEqual([])
 evidence.checks=['three-accepted-task-evidence-records-two-causal-deliveries','original-scope-input-output-limits-present','keyboard-readable-full-report','statement-required-before-closure','one-exact-owner-closure-committed','lost-post-receipt-recovered-by-original-acceptance-read','no-second-post-for-read-recovery','original-overview-report-link','keyboard-original-plan-run-return-rechecks-current-acceptance','desktop-mobile-regional-axe-and-overflow'];evidence.status='passed'
}finally{if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{});await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')}

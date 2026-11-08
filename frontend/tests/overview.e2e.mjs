/** Installed overview reads synthetic domain history; faults affect real delivery, never invented API bodies. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use overview_page.py with a fresh synthetic host')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Real installed owner reads; synthetic domain plans/question, no model',states:[],checks:[],faults:[],writes:[],errors:[],pages:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('response',async response=>{
  const u=new URL(response.url()),method=response.request().method()
  if(!u.pathname.startsWith('/api/'))return
  if(method!=='GET'&&u.pathname!=='/api/session')evidence.writes.push({path:u.pathname,method,status:response.status()})
  if(u.pathname==='/api/projects/101/questions'&&response.ok()){
   const body=await response.json().catch(()=>null)
   if(body)evidence.pages.push({after:u.searchParams.get('after_id'),count:body.items.length,total:body.total_pending,next:body.next_after_id})
  }
 })
 const failed=new Set()
 let delayNext=false,started,release,delivered
 /** Drop requested reads or hold an actual original response across a project switch. */
 await page.route('**/api/**',async route=>{
  const u=new URL(route.request().url())
  if(route.request().method()!=='GET')return route.continue()
  if(failed.has(u.pathname)){evidence.faults.push({path:u.pathname,kind:'abort-read'});return route.abort('failed')}
  if(delayNext&&u.pathname==='/api/projects/101/workspace'){
   delayNext=false
   const response=await route.fetch()
   started();await new Promise(resolve=>{release=resolve})
   await route.fulfill({response});delivered()
   evidence.faults.push({path:u.pathname,kind:'late-original-alpha-read'})
   return
  }
  return route.continue()
 })
 /** Capture observed desktop/mobile states and bounded accessibility/layout checks. */
 async function capture(name,width=1440){
  await page.setViewportSize({width,height:1024})
  await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true})
  const axe=await new AxeBuilder({page}).include('.overview-workbench').analyze()
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)
  evidence.states.push({name,width,fits,violations:axe.violations})
  expect(fits).toBe(true);expect(axe.violations).toEqual([])
 }
 /** Choose a real project without injecting selection state into the page. */
 async function project(from,to){
  await page.getByRole('button',{name:`Seleccionar proyecto: ${from}`}).click()
  await page.getByRole('button',{name:to,exact:true}).click()
  await expect(page.getByRole('heading',{name:to,exact:true})).toBeVisible()
 }
 await page.goto(origin)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Un lugar para retomar el trabajo'})).toBeVisible()
 await expect(page.getByRole('link',{name:'Abrir proyectos',exact:true})).toHaveAttribute('href','/projects')
 await capture('01-no-selection')
 await project('Elegir proyecto…','Atlas de observaciones')
 await expect(page.getByText('7 tareas registradas · 1 marcadas como hechas.',{exact:true})).toBeVisible()
 await expect(page.getByText('Se muestran 6 de 7 tareas. Abre la lista completa para consultar el resto.',{exact:true})).toBeVisible()
 await expect(page.getByText(`${ids.questionCount} solicitudes pendientes`,{exact:true})).toBeVisible()
 const plan=page.locator('.overview-workbench').getByRole('link',{name:'Plan sintético pendiente de revisión',exact:true}).first()
 await expect(plan).toHaveAttribute('href',`/tasks?project=101&task=${ids.proposal.task}&planRun=${ids.proposal.run}`)
 await expect(page.locator('.overview-context')).toContainText('planning-fixture')
 await expect(page.locator('.overview-context')).toContainText('Carpeta disponible')
 await expect(page.locator('.overview-context')).toContainText('No hay informes de cierre aceptados registrados.')
 await capture('02-desktop-overview')
 await capture('03-mobile-attention',390)
 await page.locator('#main-content').evaluate(node=>node.scrollTo(0,node.scrollHeight))
 await capture('04-mobile-context',390)
 await page.locator('#main-content').evaluate(node=>node.scrollTo(0,0))
 await page.getByRole('button',{name:'Ver más pendientes'}).click()
 await expect(page.locator('[data-request-id]')).toHaveCount(52)
 await expect(page.getByRole('button',{name:'Ver más pendientes'})).toHaveCount(0)
 await page.locator('[data-request-id]').last().getByText('Solicitud histórica 51',{exact:true}).click()
 await expect(page.locator('[data-request-id]').last()).toContainText('No tiene un vínculo comprobado con una tarea y versión del nuevo motor')
 const question=page.locator(`[data-request-id="${ids.question.request}"] button`)
 await question.focus();await expect(question).toBeFocused();await page.keyboard.press('Enter')
 await expect(page).toHaveURL(new RegExp(`project=101&task=${ids.question.task}&question=${ids.question.request}`))
 await expect(page.locator('.conversation-workbench')).toContainText('Aclarar el formato de entrada')
 evidence.checks.push('no-selection-navigation','seven-tasks-six-visible','real-question-pagination','legacy-question-has-no-native-authority','keyboard-original-question-task-link','source-availability-read','accepted-closure-empty-state')
 await page.goto(origin);await page.setViewportSize({width:1440,height:1024})
 await expect(plan).toBeVisible();await plan.click()
 await expect(page.getByRole('heading',{name:'Plan sintético pendiente de revisión',exact:true})).toBeVisible()
 await expect(page).toHaveURL(new RegExp(`task=${ids.proposal.task}&planRun=${ids.proposal.run}`))
 await page.goto(origin)
 await page.locator('.overview-workbench').getByRole('link',{name:'Ver todas las tareas',exact:true}).click()
 await expect(page).toHaveURL(/\/tasks\?project=101$/)
 evidence.checks.push('original-plan-run-navigation','project-scoped-complete-task-list')
 failed.add('/api/tasks');failed.add('/api/projects/101/workspace');failed.add('/api/projects/101/questions')
 await page.goto(origin)
 await expect(page.getByText('No pudimos consultar el contexto del proyecto.',{exact:true})).toBeVisible()
 await expect(page.getByText('No se pudieron recuperar las preguntas.',{exact:true})).toBeVisible()
 await expect(page.getByRole('alert').filter({hasText:'No pudimos consultar las tareas.'})).toBeVisible()
 await expect(page.getByText('Todavía no hay tareas registradas.',{exact:true})).toHaveCount(0)
 await expect(page.getByText('No hay preguntas pendientes en este proyecto.',{exact:true})).toHaveCount(0)
 await expect(page.getByText('No hay planes ni tareas señalados para revisión en estas consultas.',{exact:true})).toHaveCount(0)
 await capture('05-independent-reads-failed')
 failed.clear();await page.getByRole('button',{name:'Actualizar resumen'}).click()
 await expect(page.locator('.overview-workbench').getByRole('alert')).toHaveCount(0)
 await expect(page.getByText('7 tareas registradas · 1 marcadas como hechas.',{exact:true})).toBeVisible()
 await expect(page.getByText('52 solicitudes pendientes',{exact:true})).toBeVisible()
 await page.reload();await expect(plan).toBeVisible()
 evidence.checks.push('read-errors-never-false-zero','explicit-refresh-recovery','reload-preserves-original-links')
 delayNext=true
 const began=new Promise(resolve=>{started=resolve}),arrived=new Promise(resolve=>{delivered=resolve})
 await page.reload();await began
 await project('Atlas de observaciones','Proyecto separado')
 await expect(page.getByText('Todavía no hay tareas registradas.',{exact:true})).toBeVisible()
 release();await arrived
 await expect(page.locator('.overview-workbench')).not.toContainText('Plan sintético pendiente de revisión')
 await expect(page.locator('[data-request-id]')).toHaveCount(0)
 await capture('06-empty-beta-after-late-alpha',390)
 await project('Proyecto separado','Etiquetas históricas')
 await expect(page.getByText('2 tareas registradas · 2 marcadas como hechas.',{exact:true})).toBeVisible()
 await expect(page.locator('.overview-workbench')).not.toContainText('100%')
 await expect(page.locator('.overview-workbench')).not.toContainText('Proyecto completo')
 await expect(page.locator('.overview-context')).toContainText('No hay informes de cierre aceptados registrados.')
 await capture('07-all-done-is-not-acceptance',390)
 await project('Etiquetas históricas','Atlas de observaciones')
 await expect(page.getByText('7 tareas registradas · 1 marcadas como hechas.',{exact:true})).toBeVisible()
 await capture('08-alpha-return')
 evidence.checks.push('late-original-workspace-project-isolation','empty-project-is-known-empty','done-and-project-labels-are-not-accepted-report','return-to-original-project')
 expect(evidence.pages.some(p=>p.after==='0'&&p.count===50&&p.next!=null)).toBe(true)
 expect(evidence.pages.some(p=>p.after!=='0'&&p.count===2&&p.next===null)).toBe(true)
 expect(evidence.writes).toEqual([]);expect(evidence.errors).toEqual([])
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

/** Installed agent ledger, policy recovery and Stop over explicitly synthetic native-domain history. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use agents_page.py with a fresh synthetic host')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Installed HTTP/SQLite controls; synthetic history/usage/turns, no model execution',states:[],checks:[],faults:[],writes:[],errors:[],pages:[],budgetCommits:[],stopCommits:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('response',async response=>{
  const u=new URL(response.url()),method=response.request().method()
  if(!u.pathname.startsWith('/api/'))return
  if(method!=='GET'&&u.pathname!=='/api/session')evidence.writes.push({method,path:u.pathname,status:response.status()})
  if(u.pathname==='/api/projects/101/agent-runs'&&response.ok()){
   const body=await response.json().catch(()=>null)
   if(body)evidence.pages.push({before:u.searchParams.get('before_seq'),count:body.items.length,total:body.total_runs,next:body.next_before_seq})
  }
 })
 const failed=new Set()
 let budgetLost=false,stopCalls=0,delayNext=false,started,release,delivered
 /** Inject delivery faults around actual commits without inventing success or state bodies. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),u=new URL(request.url())
  if(request.method()==='POST'&&u.pathname==='/api/projects/101/work-budget'){
   expect(budgetLost).toBe(false);budgetLost=true
   const response=await route.fetch();expect(response.status()).toBe(200)
   evidence.budgetCommits.push({request:request.postDataJSON(),receipt:await response.json()})
   return route.abort('failed')
  }
  if(request.method()==='POST'&&u.pathname===`/api/projects/101/runs/${ids.question.run}/stop`){
   stopCalls++
   if(stopCalls===1){evidence.faults.push({path:u.pathname,kind:'stop-request-not-forwarded'});return route.abort('failed')}
   expect(stopCalls).toBe(2)
   const response=await route.fetch();expect(response.status()).toBe(202)
   evidence.stopCommits.push({status:response.status(),receipt:await response.json()})
   evidence.faults.push({path:u.pathname,kind:'stop-committed-reply-lost'})
   return route.abort('failed')
  }
  if(request.method()!=='GET')return route.continue()
  if(failed.has(u.pathname)){evidence.faults.push({path:u.pathname,kind:'abort-read'});return route.abort('failed')}
  if(delayNext&&u.pathname==='/api/projects/101/agent-runs'){
   delayNext=false;const response=await route.fetch();started()
   await new Promise(resolve=>{release=resolve})
   await route.fulfill({response});delivered()
   evidence.faults.push({path:u.pathname,kind:'late-original-alpha-read'});return
  }
  return route.continue()
 })
 /** Capture real states, regional accessibility and horizontal geometry at both widths. */
 async function capture(name,width=1440,scrollTo=null){
  await page.setViewportSize({width,height:1024})
  if(scrollTo)await page.locator(scrollTo).scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true})
  const axe=await new AxeBuilder({page}).include('.agents-workbench').analyze()
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)
  evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])
 }
 /** Preserve original project scope through visible selection. */
 async function project(from,to){
  await page.getByRole('button',{name:`Seleccionar proyecto: ${from}`}).click()
  await page.getByRole('button',{name:to,exact:true}).click()
  await expect(page.getByRole('button',{name:`Seleccionar proyecto: ${to}`})).toBeVisible()
 }
 /** Open the actual run, retaining keyboard focus in its reading pane. */
 async function select(run){
  const row=page.locator(`#agent-run-${run}`)
  await row.focus();await page.keyboard.press('Enter')
  await expect(page.locator('#agent-detail-title')).toBeFocused()
 }
 await page.goto(origin+'/agents')
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Quién se ocupa del trabajo'})).toBeVisible()
 await capture('01-no-selection')
 await project('Elegir proyecto…','Atlas de observaciones')
 const budget=page.getByRole('region',{name:'Presupuesto de trabajo del proyecto'})
 await expect(budget).toContainText('55')
 await budget.getByRole('button',{name:'Revisar límites'}).click()
 await budget.getByLabel('Límite total de turnos',{exact:true}).fill('4')
 await budget.getByLabel('Límite total de tokens',{exact:true}).fill('1000')
 await budget.getByLabel('Motivo del cambio (opcional)').fill('Ensayo sintético: ampliar capacidad sin iniciar ni repetir trabajo.')
 await capture('02-budget-edit-desktop',1440,'[aria-label="Presupuesto de trabajo del proyecto"]')
 await budget.getByRole('button',{name:'Guardar límites'}).click()
 await expect(budget.getByRole('alert')).toContainText('No se confirmó el cambio')
 await capture('03-budget-committed-reply-lost',390,'[aria-label="Presupuesto de trabajo del proyecto"]')
 await page.reload()
 await budget.getByRole('button',{name:'Consultar recibo original'}).click()
 await expect(budget).toContainText('Límites guardados. No se inició trabajo')
 expect(evidence.budgetCommits).toHaveLength(1)
 expect(evidence.budgetCommits[0].receipt.inference_started).toBe(false)
 await expect(page.locator('[id^="agent-run-"]')).toHaveCount(25)
 await page.getByRole('button',{name:'Cargar ejecuciones anteriores'}).click()
 await expect(page.locator('[id^="agent-run-"]')).toHaveCount(30)
 await expect(page.getByRole('button',{name:'Cargar ejecuciones anteriores'})).toHaveCount(0)
 await select(ids.measured)
 await expect(page.locator('.agents-detail')).toContainText('synthetic-never-launched-model')
 await expect(page.locator('.agents-detail')).toContainText('55')
 await expect(page.locator('.agents-detail')).toContainText('Cuota restante y coste de la suscripción: no disponibles')
 await expect(page.getByRole('link',{name:'Abrir tarea e historial'})).toHaveAttribute('href','/tasks?project=101&task=1300')
 await page.getByText('Intentos guardados',{exact:true}).click()
 await expect(page.locator('.agents-detail')).toContainText('1 de 1 intentos guardados')
 await expect(page.locator('.agents-detail')).toContainText('Synthetic terminal fixture; no native process or model was launched.')
 await capture('04-receipted-model-and-attempt',1440,'#agent-detail-title')
 await capture('05-model-and-attempt-mobile',390,'#agent-detail-title')
 await page.getByRole('button',{name:'Volver a ejecuciones'}).click()
 await expect(page.locator(`#agent-run-${ids.measured}`)).toBeFocused()
 await select(ids.unknown)
 await expect(page.locator('.agents-detail')).toContainText('No hay una medición de consumo disponible')
 await expect(page.locator('.agents-detail')).toContainText('Sin envío registrado')
 await capture('06-unmeasured-is-unknown',390,'#agent-detail-title')
 await page.getByRole('button',{name:'Volver a ejecuciones'}).click()
 await select(ids.question.run)
 await expect(page.locator('.agents-detail')).toContainText('Espera una respuesta')
 await page.getByRole('button',{name:'Detener esta ejecución',exact:true}).click()
 await expect(page.locator('.agents-detail').getByRole('alert')).toContainText('No se confirmó la parada')
 await expect(page.locator('.agents-detail')).toContainText('Espera una respuesta')
 await capture('07-stop-delivery-uncertain',390,'.agents-control')
 await page.getByRole('button',{name:'Detener esta ejecución',exact:true}).click()
 await expect(page.locator('.agents-detail')).toContainText('Cancelada')
 await expect(page.getByRole('button',{name:'Detener esta ejecución',exact:true})).toHaveCount(0)
 await expect(page.locator('.agents-detail').getByRole('alert')).toContainText('No se confirmó la parada')
 await capture('08-stop-committed-observed-by-read',390,'.agents-control')
 expect(evidence.stopCommits).toHaveLength(1);expect(evidence.stopCommits[0].receipt.run_id).toBe(ids.question.run)
 evidence.checks.push('no-selection','budget-real-commit-read-only-recovery-after-reload','run-pagination-25-plus-5','keyboard-selection-and-return','original-task-link','original-attempt-and-model','unknown-usage-not-zero','stop-before-send-not-success','stop-after-commit-observed-by-read-not-receipt')
 failed.add('/api/projects/101/agent-runs');failed.add('/api/projects/101/work-budget')
 await page.reload()
 await expect(page.getByRole('alert').filter({hasText:'No pudimos consultar las ejecuciones.'})).toBeVisible()
 await expect(budget.getByRole('alert')).toContainText('No se pudo consultar el presupuesto')
 await expect(page.getByText('Todavía no hay ejecuciones nativas en este proyecto.',{exact:true})).toHaveCount(0)
 await capture('09-ledger-budget-read-failed')
 failed.clear();await page.getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await page.getByRole('button',{name:'Volver a consultar presupuesto',exact:true}).click()
 await expect(page.locator('.agents-workbench').getByRole('alert')).toHaveCount(0)
 await expect(page.locator('[id^="agent-run-"]')).toHaveCount(25)
 const began=new Promise(resolve=>{started=resolve}),arrived=new Promise(resolve=>{delivered=resolve})
 delayNext=true;await page.reload();await began
 await project('Atlas de observaciones','Proyecto separado')
 await expect(page.getByText('Todavía no hay ejecuciones nativas en este proyecto.',{exact:true})).toBeVisible()
 release();await arrived
 await expect(page.locator('[id^="agent-run-"]')).toHaveCount(0)
 await expect(page.locator('.agents-workbench')).not.toContainText('synthetic-history-')
 await capture('10-beta-after-late-alpha',390)
 await project('Proyecto separado','Atlas de observaciones')
 await expect(page.locator('[id^="agent-run-"]')).toHaveCount(25)
 await capture('11-alpha-return',1440,'.agents-index-heading')
 evidence.checks.push('partial-read-errors-not-empty','explicit-read-recovery','late-original-ledger-project-isolation','alpha-beta-alpha-no-selection-leak')
 expect(evidence.pages.some(p=>p.before==null&&p.count===25&&p.total===30&&p.next!=null)).toBe(true)
 expect(evidence.pages.some(p=>p.before!=null&&p.count===5&&p.next===null)).toBe(true)
 expect(evidence.writes).toEqual([]) // All three mutation replies were deliberately dropped after/before forwarding.
 expect(evidence.errors).toEqual([]);evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

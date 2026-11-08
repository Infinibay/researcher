/** Installed accepted graph and original pause receipt inspection; no new authorization or native dispatch. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use execution_page.py and its paused synthetic original graph')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Actual installed graph/receipt reads over synthetic domain history; no new execution authorization',states:[],controls:[],readFaults:[],errors:[],checks:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 let failWorkspace=false
 /** Drop only an actual original pause receipt; every other work-changing project/chat POST is forbidden. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=new URL(request.url()).pathname
  if(request.method()==='GET'&&failWorkspace&&p===`/api/projects/${ids.alpha}/workspace`){evidence.readFaults.push(p);return route.abort('failed')}
  if(request.method()==='POST'&&p===`/api/projects/${ids.alpha}/plan-executions/${ids.main.execution}/control`){
   const body=request.postDataJSON();expect(body).toEqual(ids.main.packet.body)
   const response=await route.fetch(),receipt=await response.json()
   expect(response.status()).toBe(200);expect(receipt).toEqual(ids.main.receipt)
   evidence.controls.push({body,receipt,status:response.status()})
   if(evidence.controls.length===1)return route.abort('failed')
   return route.fulfill({response})
  }
  if(request.method()==='POST'&&(p.startsWith('/api/projects/')||p.startsWith('/api/chat/')))throw new Error('This evaluation permits only the original paused control receipt')
  return route.continue()
 })
 /** A capture restores its viewport so a mobile audit cannot silently hide the next desktop control. */
 async function capture(name,width=1440,selector='.flow-detail'){
  const previous=page.viewportSize()
  try{await page.setViewportSize({width,height:1024});await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.flow-workbench').analyze(),fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])}finally{await page.setViewportSize(previous)}
 }
 /** Open only an actual accepted plan ID, without changing its execution authority. */
 async function select(plan){await page.locator(`#flow-plan-${plan.run}`).click();await expect(page.getByRole('heading',{name:plan.title,exact:true})).toBeVisible()}
 /** Open existing controls without toggling a fresh execute/resume command. */
 async function controls(){const item=page.locator('.flow-controls');if(!(await item.evaluate(element=>element.open)))await item.locator('summary').click();return page.getByRole('region',{name:'Ejecución del plan',exact:true})}
 await page.goto(`${origin}/flow`)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await select(ids.main)
 await expect(page.locator('.flow-detail')).toContainText('1 de 2 entregas actuales con resultado aceptado')
 await page.locator(`#flow-task-${ids.main.export}`).click()
 const task=page.getByRole('region',{name:'Detalle de la tarea',exact:true})
 await expect(task).toContainText('Esta entrega recibió resultados aceptados de:')
 await expect(task.getByRole('link',{name:'Documentar una observación de ejemplo',exact:true})).toHaveAttribute('href',`/tasks?project=${ids.alpha}&task=${ids.main.learn}`)
 await expect(task.getByRole('link',{name:'Abrir tarea y recuperación',exact:true})).toHaveAttribute('href',`/tasks?project=${ids.alpha}&task=${ids.main.export}`)
 await capture('01-accepted-prerequisite-and-original-handoff')
 await capture('02-mobile-evidence-inspector',390)
 await task.getByRole('button',{name:'Documentar una observación de ejemplo',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Documentar una observación de ejemplo',exact:true})).toBeFocused()
 await capture('03-prerequisite-navigation')
 expect(evidence.controls).toEqual([])
 await page.evaluate(packet=>{sessionStorage.setItem(`researcher:plan-execution-action:v1:${packet.projectId}:${packet.taskId}:${encodeURIComponent(packet.runId)}`,JSON.stringify(packet));sessionStorage.setItem(`researcher:plan-execution-pending:v1:${packet.projectId}:${packet.taskId}`,JSON.stringify({runId:packet.runId,operationKey:packet.body.operation_key}))},ids.main.packet)
 await page.reload();await select(ids.main)
 const decisions=await controls()
 await decisions.getByRole('button',{name:'Reenviar la misma decisión de ejecución',exact:true}).click()
 await expect(decisions.getByRole('alert')).toContainText('No se confirmó la decisión')
 await capture('04-original-pause-receipt-lost',390)
 await page.reload();await select(ids.main);await controls()
 await decisions.getByRole('button',{name:'Reenviar la misma decisión de ejecución',exact:true}).click()
 await expect(decisions.getByText('Decisión registrada. El estado de cada intento y su cierre se muestran por separado.',{exact:true})).toBeVisible()
 expect(await page.evaluate(packet=>sessionStorage.getItem(`researcher:plan-execution-action:v1:${packet.projectId}:${packet.taskId}:${encodeURIComponent(packet.runId)}`),ids.main.packet)).toBeNull()
 await capture('05-original-pause-recovered-without-dispatch')
 await select(ids.stale)
 await expect(page.locator('.flow-detail')).toContainText('El contexto cambió. Se conserva la historia')
 await expect(page.locator('.flow-detail')).toContainText('Dependencias no verificables con el contexto actual')
 await expect(page.locator('.flow-detail')).not.toContainText('entregas actuales con resultado aceptado')
 await capture('06-stale-graph-remains-history',390)
 await select(ids.fresh)
 await expect(page.locator('.flow-detail')).toContainText('Plan aceptado, ejecución aún no autorizada.')
 await capture('07-plan-acceptance-is-not-execution')
 failWorkspace=true
 await page.locator('.flow-plans').getByRole('button',{name:'Actualizar',exact:true}).click()
 await expect(page.locator('.flow-workbench').getByRole('alert')).toContainText('No pudimos consultar el recorrido')
 const freshControls=await controls()
 await expect(freshControls.getByRole('button',{name:'Ejecutar las 2 tareas de este plan',exact:true})).toBeDisabled()
 await capture('08-cached-read-error-disables-new-authorization',390)
 failWorkspace=false
 await page.locator('.flow-workbench').getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await expect(page.locator('.flow-workbench').getByRole('alert')).toHaveCount(0)
 await expect(freshControls.getByRole('button',{name:'Ejecutar las 2 tareas de este plan',exact:true})).toBeEnabled()
 await page.getByRole('button',{name:'Seleccionar proyecto: Cuaderno de observaciones'}).click();await page.getByRole('button',{name:'Proyecto separado',exact:true}).click()
 await expect(page.getByText('Todavía no hay planes aceptados en este proyecto.',{exact:true})).toBeVisible()
 await expect(page.locator('.flow-detail')).toHaveCount(0)
 await capture('09-project-switch-clears-original-plan',390,'.flow-workbench')
 expect(evidence.controls).toHaveLength(2);expect(evidence.errors).toEqual([])
 evidence.checks.push('real-accepted-graph-two-nodes','current-accepted-prerequisite-linked','original-typed-handoff-not-chat-guess','task-recovery-link-original-scope','keyboard-focus-on-prerequisite-navigation','reading-never-authorizes-work','exact-preexisting-pause-body-key-receipt-after-reload','local-original-packet-cleared-only-after-ack','paused-dispatch-distinct-from-physical-closure','stale-graph-not-current-progress','accepted-plan-not-execution-authority','cached-project-error-blocks-new-authorization','retry-restores-observed-controls','project-switch-clears-original-selection','desktop-mobile-no-overflow-or-regional-axe-violations')
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

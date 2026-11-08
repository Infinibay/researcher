/** Actual owner task creation, committed-reply loss and dependency read recovery against installed HTTP. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use task_creation_page.py with fresh synthetic metadata and no runs')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Real owner metadata writes/read faults; synthetic projects and no native run/model',states:[],checks:[],posts:[],committed:[],faults:[],errors:[]}
const browser=await chromium.launch({headless:true})
let page,releaseRecovery
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 let recoveryStarted,recoveryDelivered,failDependencies=false,failTasks=false
 const held=new Promise(resolve=>{recoveryStarted=resolve}),delivered=new Promise(resolve=>{recoveryDelivered=resolve})
 /** Drop only an actual committed reply, delay its exact recovery and abort actual reads without fabricating data. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),u=new URL(request.url())
  if(request.method()==='POST'&&u.pathname==='/api/tasks'){
   const body=request.postDataJSON();evidence.posts.push(body)
   const response=await route.fetch();expect(response.status()).toBe(201)
   const row=await response.json()
   if(evidence.posts.length===1){evidence.committed.push(row);evidence.faults.push({kind:'lost-after-201-commit',task:row.id});return route.abort('failed')}
   expect(evidence.posts.length).toBeLessThanOrEqual(3);expect(body).toEqual(evidence.posts[0]);expect(row).toEqual(evidence.committed[0])
   if(evidence.posts.length===2){recoveryStarted(row);await new Promise(resolve=>{releaseRecovery=resolve});await route.fulfill({response});recoveryDelivered();return}
   return route.fulfill({response})
  }
  if(request.method()==='GET'&&((failDependencies&&u.pathname===`/api/tasks/${ids.input}/dependencies`)||(failTasks&&u.pathname==='/api/tasks'&&u.searchParams.get('project_id')==='101'))){evidence.faults.push({kind:'abort-read',path:u.pathname});return route.abort('failed')}
  return route.continue()
 })
 /** Capture current workbench geometry and regional accessibility at actual desktop/mobile widths. */
 async function capture(name,width=1440){await page.setViewportSize({width,height:1024});await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.task-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])}
 /** Select a project through the owner's actual global selector. */
 async function project(from,to){await page.getByRole('button',{name:`Seleccionar proyecto: ${from}`}).click();await page.getByRole('button',{name:to,exact:true}).click();await expect(page.getByRole('button',{name:`Seleccionar proyecto: ${to}`})).toBeVisible()}
 /** Bound observation of this exact held response; a timeout never restarts a mutation. */
 async function bounded(promise){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Original response observation timed out')),15000)})])}finally{clearTimeout(timer)}}
 await page.goto(origin+'/tasks')
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Tareas',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Nueva tarea',exact:true}).click()
 const form=page.getByRole('form',{name:'Crear tarea'})
 const title='Preparar CSV con columnas comprobadas'
 const description='Objetivo: exportar las observaciones. Entrada ilustrativa: {id: 7, value: 12}. Salida deseada: cabecera id,value y fila 7,12. Primero comprobar una observación real; el ejemplo inventado no demuestra su formato.'
 await form.getByLabel('Título',{exact:true}).fill(title);await form.getByLabel('Descripción',{exact:true}).fill(description)
 await form.getByRole('combobox',{name:/^Tipo/}).selectOption('documentation');await form.getByRole('combobox',{name:/^Prioridad/}).selectOption('1');await form.getByRole('combobox',{name:/^Complejidad/}).selectOption('high')
 await form.getByRole('combobox',{name:/^Grupo/}).selectOption(String(ids.group));await form.getByRole('combobox',{name:/^Hito/}).selectOption(String(ids.milestone));await form.getByRole('checkbox',{name:'Leer una observación real',exact:true}).check()
 await capture('01-captured-input-before-delivery')
 await form.getByRole('button',{name:'Crear tarea',exact:true}).click()
 await expect(form.getByRole('alert')).toContainText('No se confirmó la creación')
 await expect(form.getByRole('button',{name:'Recuperar la misma tarea'})).toBeEnabled()
 await capture('02-original-request-after-lost-reply',390)
 await page.reload();await page.getByRole('button',{name:'Nueva tarea',exact:true}).click()
 await expect(form.getByLabel('Título',{exact:true})).toHaveValue(title);await expect(form.getByRole('combobox',{name:/^Complejidad/})).toHaveValue('high');await expect(form.getByRole('combobox',{name:/^Hito/})).toHaveValue(String(ids.milestone))
 await capture('03-reload-keeps-original-input',390)
 await form.getByRole('button',{name:'Recuperar la misma tarea'}).click()
 const receipt=await bounded(held)
 await project('Cuaderno de observaciones','Proyecto separado')
 await expect(page.getByRole('region',{name:'Elegir tarea'})).toContainText('No hay tareas con estos filtros.')
 releaseRecovery();await bounded(delivered)
 await expect(page.locator('.task-inspector')).toHaveCount(0);expect(new URL(page.url()).searchParams.has('task')).toBe(false)
 await capture('04-late-original-receipt-does-not-select-other-project',390)
 await project('Proyecto separado','Cuaderno de observaciones')
 expect(JSON.parse(await page.evaluate(()=>sessionStorage.getItem('researcher:task-create:v1:101'))).body).toEqual(evidence.posts[0])
 await page.getByRole('button',{name:'Nueva tarea',exact:true}).click()
 await form.getByRole('button',{name:'Recuperar la misma tarea'}).click()
 await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible()
 expect(await page.evaluate(()=>sessionStorage.getItem('researcher:task-create:v1:101'))).toBeNull()
 await page.getByRole('button',{name:'Detalles',exact:true}).click()
 await expect(page.locator('.task-inspector')).toContainText(description);await expect(page.locator('.task-inspector')).toContainText('high')
 await capture('05-original-task-with-selected-values')
 await page.getByRole('button',{name:'Volver a tareas',exact:true}).click()
 await page.locator(`#task-select-${receipt.id}`).focus();await page.keyboard.press('Enter')
 await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Volver a tareas',exact:true}).click()
 failDependencies=true
 await page.getByRole('button',{name:'Dependencias',exact:true}).click()
 const graph=page.getByRole('region',{name:'Mapa de dependencias'})
 await expect(graph.getByRole('alert')).toContainText('No se conoce el mapa completo')
 await expect(graph.getByRole('heading',{name:'Mapa de prerrequisitos'})).toHaveCount(0)
 await capture('06-dependency-read-failure-is-unknown',390)
 failDependencies=false;await graph.getByRole('button',{name:'Volver a consultar dependencias'}).click()
 await expect(graph.getByRole('heading',{name:'Mapa de prerrequisitos'})).toBeVisible()
 await expect(graph).toContainText(`Necesita antes: #${ids.input}`)
 await capture('07-confirmed-prerequisites')
 failTasks=true;await page.reload()
 await expect(page.getByRole('region',{name:'Elegir tarea'}).getByRole('alert')).toContainText('No se pudo consultar la lista')
 await expect(page.getByText('No hay tareas con estos filtros. Puedes crear una o cambiar los filtros.',{exact:true})).toHaveCount(0)
 await capture('08-task-list-read-error',390)
 failTasks=false;await page.getByRole('region',{name:'Elegir tarea'}).getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await expect(page.locator(`#task-select-${receipt.id}`)).toBeVisible()
 await capture('09-original-created-task-after-read-recovery')
 expect(evidence.posts).toHaveLength(3);expect(evidence.errors).toEqual([])
 evidence.checks.push('selected-complexity-and-parent-captured','actual-201-commit-before-reply-loss','same-body-and-key-after-reload','one-original-receipt','late-reply-cannot-select-other-project','unacknowledged-copy-retained-after-unmount','mounted-recovery-retires-exact-local-copy','keyboard-original-task-open','stored-goal-and-illustrative-input-output','dependency-error-not-empty-map','actual-prerequisite-recovery','task-list-error-not-empty','no-native-admission')
 evidence.status='passed'
}finally{
 if(releaseRecovery)releaseRecovery()
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

/** Real installed recovery of a pre-admitted synthetic request and one correction across Tasks/Conversation. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use task_requests_page.py with its original synthetic admission')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Existing synthetic admission recovery, actual owner Stop and context correction; no generative model',states:[],instructions:[],corrections:[],stops:[],errors:[],checks:[],readFaults:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 let failComments=false,failRelations=false
 /** Deliver captured mutations to actual HTTP and drop only their first original response after commit. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=new URL(request.url()).pathname
  if(request.method()==='GET'&&((failComments&&p===`/api/tasks/${ids.input}/comments`)||(failRelations&&p===`/api/tasks/${ids.input}/dependencies`))){evidence.readFaults.push(p);return route.abort('failed')}
  if(request.method()==='POST'&&p===`/api/chat/${ids.alpha}/instructions`){
   const body=request.postDataJSON(),response=await route.fetch(),row=await response.json()
   expect(response.status()).toBe(202);expect(body).toEqual(ids.packet.body);expect(row.run.run_id).toBe(ids.run)
   evidence.instructions.push({body,status:response.status(),run:row.run.run_id})
   if(evidence.instructions.length===1)return route.abort('failed')
   return route.fulfill({response})
  }
  if(request.method()==='POST'&&p===`/api/projects/${ids.alpha}/tasks/${ids.input}/context-corrections`){
   const body=request.postDataJSON(),response=await route.fetch(),row=await response.json()
   expect(response.status()).toBe(200)
   evidence.corrections.push({body,status:response.status(),receipt:row})
   if(evidence.corrections.length===1)return route.abort('failed')
   expect(body).toEqual(evidence.corrections[0].body);expect(row).toEqual(evidence.corrections[0].receipt)
   return route.fulfill({response})
  }
  return route.continue()
 })
 page.on('response',response=>{const p=new URL(response.url()).pathname;if(response.request().method()==='POST'&&p.endsWith('/stop'))evidence.stops.push({path:p,status:response.status()})})
 /** Capture the actual control region at each viewport; accessibility analysis remains explicitly regional. */
 async function capture(name,width=1440,selector='.task-execution'){await page.setViewportSize({width,height:1024});await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const region=page.url().includes('/chat')?'.conversation-workbench':'.task-workbench';const axe=await new AxeBuilder({page}).include(region).analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])}
 /** Open an existing disclosure only when it is closed, respecting history already shown after a correction. */
 async function disclosure(label){const summary=page.getByText(label,{exact:true}),details=summary.locator('..');if(!(await details.evaluate(el=>el.open)))await summary.click();return details}
 await page.goto(`${origin}/tasks?project=${ids.alpha}&task=${ids.input}`)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Leer una observación real',exact:true})).toBeVisible()
 // The guarded fixture belongs to this paired installation; do not inject unresolved state before enrollment.
 await page.evaluate(packet=>sessionStorage.setItem(`researcher:task-instruction:v1:${packet.projectId}:${packet.taskId}`,JSON.stringify(packet)),ids.packet)
 await page.reload()
 const instruction=page.getByLabel('Solicitud para esta tarea',{exact:true})
 await expect(instruction).toHaveValue(ids.packet.body.message)
 await expect(page.getByRole('button',{name:'Reenviar la misma solicitud',exact:true})).toBeEnabled()
 await capture('01-original-pending-request')
 await page.getByRole('button',{name:'Reenviar la misma solicitud',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('El envío no quedó confirmado')
 await capture('02-original-admission-reply-lost',390)
 await page.goto(`${origin}/chat?project=${ids.alpha}&task=${ids.input}`)
 await expect(instruction).toHaveValue(ids.packet.body.message)
 await page.getByRole('button',{name:'Reenviar la misma solicitud',exact:true}).click()
 await expect(instruction).toHaveValue('')
 expect(await page.evaluate(packet=>sessionStorage.getItem(`researcher:task-instruction:v1:${packet.projectId}:${packet.taskId}`),ids.packet)).toBeNull()
 await capture('03-original-request-recovered-in-conversation')
 const stopped=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/projects/${ids.alpha}/runs/${ids.run}/stop`&&response.request().method()==='POST')
 await page.getByRole('button',{name:'Detener ejecución',exact:true}).click()
 expect((await stopped).status()).toBe(202)
 await expect(page.getByRole('button',{name:'Detener ejecución',exact:true})).toHaveCount(0)
 await disclosure('Corregir el contexto')
 await page.getByRole('combobox',{name:/^Tipo de corrección/}).selectOption('user_example')
 const statement='Entrada del ejemplo sintético: {"id": 7, "measurement": 12}. Para el CSV, extrae measurement y escribe la columna value.'
 await page.getByLabel('Qué cambia',{exact:true}).fill(statement)
 await page.getByRole('button',{name:'Guardar corrección',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('No se confirmó la corrección')
 await capture('04-original-correction-reply-lost',390)
 await page.goto(`${origin}/tasks?project=${ids.alpha}&task=${ids.input}`)
 await disclosure('Corregir el contexto')
 await expect(page.getByLabel('Qué cambia',{exact:true})).toHaveValue(statement)
 await page.getByRole('button',{name:'Reenviar la misma corrección',exact:true}).click()
 await expect(page.getByLabel('Qué cambia',{exact:true})).toHaveValue('')
 await expect(page.getByText(`Corrección registrada en el contexto ${ids.packet.body.context_version+1}. Inicia otra ejecución cuando quieras usarla.`,{exact:true})).toBeVisible()
 expect(await page.evaluate(ids=>sessionStorage.getItem(`researcher:task-correction:v1:${ids.alpha}:${ids.input}`),ids)).toBeNull()
 await capture('05-one-correction-recovered-in-tasks')
 const history=await disclosure('Historial de ejecuciones')
 await expect(history).toContainText(ids.packet.body.message)
 await history.getByText('Intentos guardados',{exact:true}).click()
 await expect(history).toContainText('Sin envío registrado')
 await capture('06-original-history-with-unknown-model',390)
 failComments=true
 await page.locator('.task-tabs').getByRole('button',{name:'Comentarios',exact:true}).click()
 const comments=page.getByRole('region',{name:'Comentarios de la tarea'})
 await expect(comments.getByRole('alert')).toContainText('No se pudieron consultar los comentarios')
 await expect(comments.getByText('No hay comentarios.',{exact:true})).toHaveCount(0)
 await capture('07-comment-read-error-is-not-empty',390,'.task-inspector')
 failComments=false;await comments.getByRole('button',{name:'Volver a consultar comentarios',exact:true}).click()
 await expect(comments.getByText('No hay comentarios.',{exact:true})).toBeVisible()
 failRelations=true
 await page.locator('.task-tabs').getByRole('button',{name:/^Dependencias/}).click()
 await expect(page.locator('.task-inspector').getByRole('alert')).toContainText('No se pudieron consultar las relaciones')
 await expect(page.getByRole('button',{name:'Editar prerrequisitos',exact:true})).toHaveCount(0)
 await capture('08-relations-read-error-blocks-editor',390,'.task-inspector')
 failRelations=false;await page.getByRole('button',{name:'Volver a consultar relaciones',exact:true}).click()
 const relations=page.getByRole('region',{name:'Relaciones de la tarea'})
 await expect(relations).toContainText('Exportar columnas comprobadas')
 await expect(relations.getByRole('heading',{name:'Tareas que necesitan ésta',exact:true})).toBeVisible()
 await capture('09-confirmed-incoming-relations',1440,'.task-inspector')
 evidence.checks.push('comment-error-not-empty-and-retry','relation-error-blocks-editor-and-retry','explicit-incoming-relations-with-original-direction')
 await page.getByRole('button',{name:'Seleccionar proyecto: Cuaderno de observaciones'}).click();await page.getByRole('button',{name:'Proyecto separado',exact:true}).click()
 await expect(page.getByText('Este enlace corresponde a otro proyecto. Elige ese proyecto o una tarea de la lista actual.',{exact:true})).toBeVisible()
 await expect(page.locator('.task-execution')).toHaveCount(0)
 await capture('10-foreign-task-link-not-retargeted',390,'.task-workbench')
 expect(evidence.instructions).toHaveLength(2);expect(evidence.corrections).toHaveLength(2)
 expect(evidence.stops).toEqual([{path:`/api/projects/${ids.alpha}/runs/${ids.run}/stop`,status:202}]);expect(evidence.errors).toEqual([])
 evidence.checks.push('original-pre-admitted-request-recovered-not-rescheduled','same-body-key-context-thread-repository','instruction-copy-survives-tasks-to-conversation','actual-original-stop-202','correction-committed-before-reply-loss','correction-copy-survives-conversation-to-tasks','original-expected-version-retained','same-correction-receipt-not-another-revision','mounted-acknowledgements-clear-exact-packets','original-history-and-model-unknown','foreign-link-not-retargeted','no-new-native-run-or-model')
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

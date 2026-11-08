/** Installed conversation, original advisory-note and grouped-answer receipt recovery; never start inference. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use conversation_page.py with its original synthetic question')
await fs.mkdir(output,{recursive:false})
const previousEvidence=process.env.RESEARCHER_E2E_CONTINUE_EVIDENCE
const evidence=previousEvidence?JSON.parse(await fs.readFile(previousEvidence,'utf8')):{status:'running',scope:'Synthetic closed question; actual owner notes/answers and immutable receipt recovery',states:[],notes:[],answers:[],errors:[],readFaults:[],checks:[]}
if(previousEvidence){expect(evidence.notes).toHaveLength(2);expect([0,2]).toContain(evidence.answers.length);evidence.continued_from=previousEvidence}
const answersRecovered=previousEvidence&&evidence.answers.length===2
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 let failTasks=!previousEvidence,failThreads=!previousEvidence,failHistory=false
 /** Fail only chosen reads and lose the first actual committed reply of each original owner mutation. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=new URL(request.url()).pathname
  if(request.method()==='GET'&&((failTasks&&p==='/api/tasks')||(failThreads&&p===`/api/chat/${ids.alpha}/threads`)||(failHistory&&p===`/api/chat/${ids.alpha}/threads/${ids.thread}`))){evidence.readFaults.push(p);return route.abort('failed')}
  if(request.method()==='POST'&&(p===`/api/chat/${ids.alpha}`||p===`/api/projects/${ids.alpha}/tasks/${ids.input}/questions/${ids.question}/answers`)){
   const rows=p.startsWith('/api/chat/')?evidence.notes:evidence.answers,body=request.postDataJSON(),response=await route.fetch(),receipt=await response.json()
   expect(response.status()).toBe(rows===evidence.notes?201:200)
   if(rows.length){expect(body).toEqual(rows[0].body);expect(receipt).toEqual(rows[0].receipt)}
   rows.push({body,receipt,status:response.status()})
   if(rows.length===1)return route.abort('failed')
   return route.fulfill({response})
  }
  if(request.method()==='POST'&&p.endsWith('/instructions'))throw new Error('This evaluation must not admit another native request')
  return route.continue()
 })
 /** Capture actual selected regions at desktop/mobile widths; accessibility findings remain regional. */
 async function capture(name,width=1440,selector='.conversation-task'){await page.setViewportSize({width,height:1024});await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.conversation-workbench').analyze(),fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])}
 await page.goto(`${origin}/chat?project=${ids.alpha}&task=${ids.input}&question=${ids.question}`)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 const question=page.getByRole('region',{name:'Preguntas del agente',exact:true})
 if(!answersRecovered){
 if(!previousEvidence){
 await expect(page.getByText('No se pudieron recuperar las tareas.',{exact:true})).toBeVisible()
 await expect(page.getByText('Crea una tarea en Tareas para empezar.',{exact:true})).toHaveCount(0)
 await expect(page.getByText('La tarea indicada no está disponible en este proyecto.',{exact:true})).toHaveCount(0)
 await capture('01-task-read-failure-is-unknown',1440,'.conversation-index')
 failTasks=false
 await page.locator('.conversation-index').getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await expect(question.getByText('La ejecución se cerró. Responde con tus palabras o elige una opción.',{exact:true})).toBeVisible()
 await expect(page.locator(':focus')).toHaveAttribute('id',`runtime-question-${ids.question}`)
 await capture('02-original-grouped-question-and-reason')
 const archive=page.locator('.conversation-archive')
 await archive.locator('summary').click()
 await expect(archive.getByText('No se pudieron recuperar los hilos.',{exact:true})).toBeVisible()
 await expect(archive.getByText('Todavía no hay hilos guardados.',{exact:true})).toHaveCount(0)
 await capture('03-thread-list-error-is-not-empty',390,'.conversation-archive')
 failThreads=false;await archive.getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await archive.getByRole('button',{name:/Ejemplo de archivo: aquí quedó una nota/}).click()
 await expect(archive.locator('.conversation-timeline').getByText('Ejemplo de archivo: aquí quedó una nota sobre el formato CSV.',{exact:true})).toBeVisible()
 await expect(page.getByText('Nota exclusiva del proyecto separado.',{exact:true})).toHaveCount(0)
 await capture('04-readonly-original-archive',1440,'.conversation-archive')
 const note=page.getByRole('region',{name:'Nota para la conversación',exact:true})
 await note.getByLabel('Nota para este hilo',{exact:true}).fill('La observación será un ejemplo ilustrativo; todavía no es una medición real.')
 await note.getByRole('button',{name:'Guardar nota',exact:true}).click()
 await expect(note.getByRole('alert')).toContainText('No se confirmó el guardado')
 await capture('05-note-committed-reply-lost',390)
 await page.reload()
 await expect(note.getByLabel('Nota para este hilo',{exact:true})).toHaveValue('La observación será un ejemplo ilustrativo; todavía no es una medición real.')
 await note.getByRole('button',{name:'Reenviar la misma nota',exact:true}).click()
 await expect(note.getByText('Nota guardada en este hilo. No se inició ninguna ejecución.',{exact:true})).toBeVisible()
 await expect(page.getByText('Contexto vigente: 1 · resultado bajo contexto 1',{exact:true})).toBeVisible()
 await capture('06-original-note-recovered-without-context-change')
 failHistory=true;await page.reload()
 const exchange=page.getByRole('region',{name:'Conversación de la tarea',exact:true})
 await expect(exchange.getByText('No se pudo recuperar la conversación.',{exact:true})).toBeVisible()
 await expect(note).toHaveCount(0)
 await capture('07-history-failure-keeps-question-controls',390)
 failHistory=false;await exchange.getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await expect(note).toBeVisible()
 }else{
  await expect(question.getByText('La ejecución se cerró. Responde con tus palabras o elige una opción.',{exact:true})).toBeVisible()
  await expect(page.getByText('Contexto vigente: 1 · resultado bajo contexto 1',{exact:true})).toBeVisible()
 }
 await page.setViewportSize({width:1440,height:1024})
 await page.getByLabel('Buscar tarea',{exact:true}).fill('Exportar')
 await expect(page.getByRole('heading',{name:'Leer una observación real',exact:true})).toBeVisible()
 await page.getByLabel('Buscar tarea',{exact:true}).fill('')
 await page.setViewportSize({width:390,height:1024})
 await page.getByRole('button',{name:'Volver a tareas y preguntas',exact:true}).click()
 await expect(page.locator('.conversation-task')).toHaveCount(0)
 await expect(page.locator(`#conversation-task-${ids.input}`)).toBeVisible()
 await page.locator(`#conversation-task-${ids.input}`).focus();await page.keyboard.press('Enter')
 await expect(page.locator('.conversation-task')).toBeVisible()
 await expect(page.getByRole('heading',{name:'Leer una observación real',exact:true})).toBeFocused()
 await capture('08-keyboard-task-selection')
 await question.getByRole('group',{name:'¿Puedes indicar una observación de ejemplo con sus campos?',exact:true}).getByRole('textbox').fill('{"id":7,"measurement":12}')
 await question.getByRole('group',{name:'¿Qué nombre quieres para la columna que contiene la medición?',exact:true}).getByRole('button',{name:'value',exact:true}).click()
 await question.getByRole('button',{name:'Guardar respuestas',exact:true}).click()
 await expect(question.getByRole('alert')).toContainText('No se confirmó el guardado')
 await capture('09-answer-committed-reply-lost',390)
 await page.reload()
 await expect(question.getByText('Respuesta original guardada · contexto 1. Recuperarla conserva las mismas respuestas y la misma clave, aunque la pregunta ya figure respondida o vencida.',{exact:true})).toBeVisible()
 await question.getByRole('button',{name:'Reenviar las mismas respuestas',exact:true}).click()
 await expect(question.getByText('Respuesta guardada. Inicia trabajo cuando quieras usar el nuevo contexto; responder no inicia otra ejecución.',{exact:true})).toBeVisible()
 await expect(page.getByText('Contexto vigente: 2 · resultado bajo contexto 1',{exact:true})).toBeVisible()
 }else{
  await expect(question.getByText('Respuesta guardada. Inicia trabajo cuando quieras usar el nuevo contexto; responder no inicia otra ejecución.',{exact:true})).toBeVisible()
  await expect(page.getByText('Contexto vigente: 2 · resultado bajo contexto 1',{exact:true})).toBeVisible()
 }
 await page.setViewportSize({width:1440,height:1024})
 await expect(page.getByText('No hay preguntas pendientes en este proyecto.',{exact:true})).toBeVisible()
 await page.getByLabel('Solicitud para esta tarea',{exact:true}).fill('Usa el ejemplo y la columna value para explicar la salida, conservando que no es una medición real.')
 await expect(page.getByRole('button',{name:'Iniciar trabajo',exact:true})).toBeEnabled()
 await capture('10-original-answer-recovered-explicit-next-work')
 await page.getByRole('button',{name:'Seleccionar proyecto: Cuaderno de observaciones'}).click();await page.getByRole('button',{name:'Proyecto separado',exact:true}).click()
 await expect(page.getByText('La tarea indicada no está disponible en este proyecto.',{exact:true})).toBeVisible()
 await expect(page.locator('.conversation-task')).toHaveCount(0)
 await capture('11-foreign-task-link-has-no-controls',390,'.conversation-index')
 expect(evidence.notes).toHaveLength(2);expect(evidence.answers).toHaveLength(2);expect(evidence.errors).toEqual([])
 expect(evidence.answers[0].body).toMatchObject({expected_version:1,answers:{example:'{"id":7,"measurement":12}',column:{option_id:'output_value'}}})
 evidence.checks.push('task-read-error-not-absence','original-question-focus-and-reason','thread-list-error-not-empty','archive-readonly-original-thread','foreign-note-excluded','original-note-201-receipt-after-reload','note-does-not-change-context-or-start-work','history-error-keeps-original-question','filter-does-not-retarget-selected-task','keyboard-selection-focus','complete-answer-keeps-choice-id-and-literal-text','answer-commit-before-reply-loss','exact-answer-key-and-context-recovery-after-responded','pending-inbox-clears-from-server-answer','next-work-enabled-never-started','foreign-task-has-no-control','no-page-errors-overflow-or-regional-axe-violations')
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

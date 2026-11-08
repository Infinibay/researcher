/** Installed owner-comment recovery preserves one advisory note after a committed receipt is lost. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use task_comment_page.py and its original synthetic host')
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',comments:[],states:[],errors:[],checks:[]},browser=await chromium.launch({headless:true})
const review=process.env.RESEARCHER_E2E_REVIEW_ORIGINAL
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}))})
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',error=>evidence.errors.push(String(error)))
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=new URL(request.url()).pathname
  if(review&&request.method()==='POST'&&p.startsWith('/api/tasks/'))throw new Error('Retained review is readonly')
  if(request.method()==='POST'&&p===`/api/tasks/${ids.task}/comments`){
   const body=request.postDataJSON();expect(body.project_id).toBe(ids.alpha)
   const response=await route.fetch(),receipt=await response.json();expect(response.status()).toBe(201);expect(receipt.authorizes_work).toBe(false)
   evidence.comments.push({body,receipt,status:response.status()})
   if(evidence.comments.length===1)return route.abort('failed')
   expect(evidence.comments[1]).toEqual(evidence.comments[0]);return route.fulfill({response})
  }
  if(request.method()==='POST'&&(p.startsWith('/api/tasks/')||p.startsWith('/api/projects/')||p.startsWith('/api/chat/')))throw new Error('This case permits only the exact advisory task comment')
  return route.continue()
 })
 /** Restore viewport after capture so subsequent owner navigation uses an explicit known layout. */
 async function capture(name,width=1440){const previous=page.viewportSize();try{await page.setViewportSize({width,height:1024});await page.getByRole('region',{name:'Comentarios de la tarea',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('[aria-label="Comentarios de la tarea"]').analyze(),fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);expect(fits).toBe(true);expect(axe.violations).toEqual([]);evidence.states.push({name,width,fits,violations:axe.violations})}finally{await page.setViewportSize(previous)}}
 /** Open the original task's tab after navigation; a query response is never treated as owner acceptance. */
 async function comments(){await expect(page.getByRole('heading',{name:'Documentar entradas y salidas',exact:true})).toBeVisible();await page.getByRole('button',{name:'Comentarios',exact:true}).click();return page.getByRole('region',{name:'Comentarios de la tarea',exact:true})}
 await page.goto(`${origin}/tasks?project=${ids.alpha}&task=${ids.task}`)
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim());await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 let panel=await comments();if(!review)await expect(panel.getByText('No hay comentarios.',{exact:true})).toBeVisible()
 if(!review){
 const text='Entrada ilustrativa: id7 y measurement12. Salida esperada del ejemplo: columnas id,value y fila7,12. Todavía falta comprobar los registros reales.'
 await panel.getByLabel('Tu comentario',{exact:true}).fill(text);await panel.getByLabel('Tipo de nota',{exact:true}).selectOption('approval')
 await capture('01-original-task-note-before-delivery')
 await panel.getByRole('button',{name:'Guardar comentario',exact:true}).click()
 await expect(panel.getByRole('alert')).toContainText('No se confirmó el guardado')
 await capture('02-committed-note-with-lost-receipt',390)
 await page.reload();panel=await comments()
 await expect(panel.getByLabel('Tu comentario',{exact:true})).toHaveValue(text)
 await expect(panel.getByLabel('Tu comentario',{exact:true})).toHaveAttribute('readonly','')
 await expect(panel.getByLabel('Tipo de nota',{exact:true})).toHaveValue('approval')
 await expect(panel.locator('ol li')).toHaveCount(1)
 await capture('03-original-packet-restored-alongside-one-stored-note')
 await panel.getByRole('button',{name:'Reenviar el mismo comentario',exact:true}).click()
 await expect(panel.getByRole('status')).toContainText('No se inició trabajo ni se aceptó ninguna entrega')
 await expect(panel.getByLabel('Tu comentario',{exact:true})).toHaveValue('')
 expect(await page.evaluate(({alpha,task})=>sessionStorage.getItem(`researcher:task-comment:v1:${alpha}:${task}`),ids)).toBeNull()
 await expect(panel.locator('ol li')).toHaveCount(1)
 await capture('04-original-receipt-confirmed-without-another-note',390)
 }else{const original=JSON.parse(await fs.readFile(review,'utf8'));evidence.comments=original.comments;evidence.states=original.states;await expect(panel.locator('ol li')).toHaveCount(1);await expect(panel.getByLabel('Tu comentario',{exact:true})).toHaveValue('');await capture('05-original-history-readonly-after-restart')}
 await page.goto(`${origin}/tasks?project=${ids.beta}&task=${ids.task}`)
 await expect(page.getByText('Este enlace corresponde a otro proyecto. Elige ese proyecto o una tarea de la lista actual.',{exact:true})).toBeVisible()
 await expect(page.getByRole('region',{name:'Comentarios de la tarea',exact:true})).toHaveCount(0)
 expect(evidence.comments).toHaveLength(2);expect(evidence.errors).toEqual([])
 evidence.checks=['one-original-scoped-advisory-note','committed-201-reply-lost','reload-restores-literal-text-type-project-task-key','same-key-body-receipt-after-reload','exact-local-clear-after-ack','one-history-row-after-replay','approval-label-never-accepts-results','foreign-project-cannot-compose-on-original-task','desktop-mobile-no-overflow-or-regional-axe-violations'];evidence.status='passed'
}finally{if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{});await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')}

/** Global controls use native scope, preserve lost Stop packets and ignore late planning navigation across projects. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const out=path.resolve('../docs/design/audits/2026-11-06-project-controls');await fs.mkdir(out,{recursive:true})
const projects=[{id:1,name:'Atlas',status:'completed'},{id:2,name:'Beta',status:'executing'}]
let scope='a'.repeat(64),stopKey=null,stopLost=true,readError=false,legacy=false,releaseStart=null,rejectNewStop=false
const evidence={scope:'Controlled HTTP fixtures, no actual runtime or user effects.',states:[],writes:[],errors:[],checks:[]}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:1},version:0}))})
 const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 await page.route('**/api/**',async route=>{
  const r=route.request(),u=new URL(r.url()),p=u.pathname;if(!p.startsWith('/api/'))return route.continue()
  if(r.method()!=='GET')evidence.writes.push({path:p,method:r.method(),body:r.postDataJSON()})
  let body={}
  if(p==='/api/session')body={authenticated:true,csrf_token:'controls-fixture'}
  else if(p==='/api/projects')body={projects,total:2}
  else if(/^\/api\/projects\/[12]$/.test(p))body=projects[Number(p.split('/').at(-1))-1]
  else if(p.endsWith('/workspace')){
   if(readError)return route.fulfill({status:503,json:{detail:'Observación interrumpida'}})
   const id=Number(p.split('/')[3]);body={project_id:id,project:projects[id-1],metadata_sha256:'c'.repeat(64),history_present:true,runtime_available:true,workspace_root:'/workspace',sources:[],source_operations:[],activity:id===1?[{run_id:scope[0]==='a'?'old-run':'new-run',task_id:31,status:'running',attempt_id:'attempt',context_version:1,fence:1}]:[],graphs:[],legacy_registered:legacy,plans:[],reports:[],report_validity:'not_rechecked',stop:id===1?{task_id:31,scope_sha256:scope}:null}
  }else if(p.endsWith('/agent-runs'))body={project_id:Number(p.split('/')[3]),total_runs:0,total_actors:0,runtime_configured:true,items:[],next_before_seq:null}
  else if(p==='/api/projects/1/stop'){
   if(rejectNewStop)return route.fulfill({status:409,json:{detail:'La actividad observada cambió'}})
   const b=r.postDataJSON();expect(b.scope_sha256).toBe('a'.repeat(64));if(stopKey)expect(b.operation_key).toBe(stopKey);stopKey=b.operation_key
   scope='b'.repeat(64)
   if(stopLost){stopLost=false;return route.fulfill({status:503,json:{detail:'Recibo perdido'}})}
   body={kind:'project.stop',project_id:1,task_id:31,operation_key:b.operation_key,scope_sha256:b.scope_sha256,run_ids:['old-run'],execution_ids:[],status:'requested',closure:'unconfirmed'}
  }else if(p==='/api/projects/2/start'){
   await new Promise(resolve=>{releaseStart=resolve})
   body={request:r.postDataJSON(),planning_task_id:41,run:{project_id:2,task_id:41,actor_id:'native-project-planner',execution_kind:'research'}}
  }else if(p.includes('/chat')||p.includes('/tasks')||p.includes('/agents'))body=[]
  return route.fulfill({status:200,json:body})
 })
 /** Capture global control availability and reject accessibility or page-width regressions. */
 async function capture(name,width){await page.setViewportSize({width,height:1024});await page.screenshot({path:path.join(out,`${name}.png`),fullPage:true});const a=await new AxeBuilder({page}).include('.workspace-header').analyze();expect(a.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);evidence.states.push({name,width,axe:0})}
 await page.goto((process.env.CONTROLS_ORIGIN??'http://127.0.0.1:5179')+'/agents')
 await expect(page.getByRole('button',{name:'Detener trabajo observado',exact:true})).toBeVisible()
 await capture('01-completed-metadata-active-native',1440)
 await page.getByRole('button',{name:'Detener trabajo observado',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('No se confirmó la detención')
 await capture('02-stop-reply-lost',390)
 await page.reload();await page.getByRole('button',{name:'Recuperar la misma detención',exact:true}).click()
 await expect(page.getByText('Detención original registrada. El cierre de los intentos aún debe comprobarse.',{exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Detener trabajo observado',exact:true})).toBeVisible()
 expect(evidence.writes[0].body).toEqual(evidence.writes[1].body)
 await capture('03-original-stop-new-work-preserved',390)
 await page.getByRole('button',{name:'Seleccionar proyecto: Atlas'}).click();await page.getByRole('button',{name:'Beta',exact:true}).click()
 await expect(page.getByText('Sin trabajo activo registrado',{exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Detener trabajo observado',exact:true})).toHaveCount(0)
 await capture('04-executing-metadata-idle-native',1440)
 await page.getByRole('button',{name:'Planificar proyecto',exact:true}).click()
 await expect.poll(()=>Boolean(releaseStart)).toBe(true)
 await page.getByRole('button',{name:'Seleccionar proyecto: Beta'}).click();await page.getByRole('button',{name:'Atlas',exact:true}).click()
 releaseStart();await expect.poll(()=>page.evaluate(()=>sessionStorage.getItem('researcher:project-plan-start:v1:2'))).toBe(null)
 await expect(page.getByRole('button',{name:'Seleccionar proyecto: Atlas'})).toBeVisible();expect(new URL(page.url()).pathname).toBe('/agents')
 readError=true;await page.reload();await expect(page.getByText('Actividad no disponible',{exact:true})).toBeVisible()
 await expect(page.getByText('Sin trabajo activo registrado',{exact:true})).toHaveCount(0)
 await expect(page.getByRole('button',{name:'Detener trabajo observado',exact:true})).toBeDisabled()
 await capture('05-unknown-is-not-idle',390)
 readError=false;legacy=true;await page.getByRole('button',{name:'Actualizar actividad',exact:true}).click()
 await expect(page.getByRole('link',{name:'Revisar controlador anterior',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Planificar proyecto',exact:true})).toBeDisabled()
 await capture('06-legacy-requires-original-owner',390)
 legacy=false;rejectNewStop=true;await page.getByRole('button',{name:'Actualizar actividad',exact:true}).click()
 await page.getByRole('button',{name:'Detener trabajo observado',exact:true}).click()
 await expect(page.getByRole('button',{name:'Descartar detención rechazada',exact:true})).toBeVisible()
 await page.evaluate(()=>{const key='researcher:project-stop:v1:1',packet=JSON.parse(sessionStorage.getItem(key));packet.body.operation_key='new-pending-from-dossier';sessionStorage.setItem(key,JSON.stringify(packet))})
 await page.getByRole('button',{name:'Actualizar actividad',exact:true}).click()
 await expect(page.getByRole('button',{name:'Descartar detención rechazada',exact:true})).toHaveCount(0)
 await expect(page.getByRole('button',{name:'Recuperar la misma detención',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>JSON.parse(sessionStorage.getItem('researcher:project-stop:v1:1')).body.operation_key)).toBe('new-pending-from-dossier')
 await capture('07-old-rejection-cannot-discard-new-packet',390)
 evidence.checks.push('metadata-completed-does-not-hide-stop','metadata-executing-does-not-invent-activity','same-stop-after-reload-does-not-retarget-new-work','late-planning-does-not-change-selected-project','query-error-is-not-idle','legacy-teardown-remains-in-original-dossier')
 evidence.checks.push('old-rejection-cannot-discard-a-newer-dossier-packet')
 expect(evidence.writes).toHaveLength(4);expect(evidence.errors).toEqual([])
}finally{if(releaseStart)releaseStart();await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}

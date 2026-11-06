/** Exercise the overview with controlled API responses; this proves UI behavior, not backend or model correctness. */
import {chromium, expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin = process.env.OVERVIEW_ORIGIN ?? 'http://127.0.0.1:5179'
const out = path.resolve('../docs/design/audits/2026-11-06-home')
await fs.mkdir(out, {recursive:true})
const project = {id:1,name:'Atlas',description:'Comprender el buscador y contrastar sus resultados.',status:'completed'}
const tasks = [
  {id:24,project_id:1,title:'Revisar el plan de investigación',type:'plan',status:'review_ready'},
  {id:25,project_id:1,title:'Aclarar el criterio de comparación',type:'research',status:'in_progress'},
  {id:26,project_id:1,title:'Reunir las fuentes iniciales',type:'research',status:'done'},
]
const question = {request_id:7,kind:'native',title:'Criterio de comparación',body:null,task_id:25,task_title:tasks[1].title,run_id:'run-25',thread_id:'thread-25',context_version:1,current_context_version:1,ready_for_answer:true,questions:[{id:'criterion',question:'¿Qué resultado quieres comparar?',why_needed:'Define la evaluación.',options:[],example:'Precisión de los primeros resultados.'}]}
const workspace = {project_id:1,metadata_sha256:'a'.repeat(64),history_present:true,project,runtime_available:true,workspace_root:'/workspace',sources:[{repository_id:1,name:'atlas',path:'/workspace/atlas',availability:'available',message:'Carpeta disponible.',git_state:'not_checked'}],source_operations:[],activity:[{run_id:'run-25',task_id:25,status:'waiting_input',attempt_id:'attempt-25',context_version:1,fence:1}],graphs:[],legacy_registered:false,plans:[{run_id:'plan-24',task_id:24,title:tasks[0].title,status:'needs_review',accepted:0,proposed:1,context_current:true}],reports:[{task_id:24,plan_run_id:'plan-24',operation_key:'close-1',report_sha256:'b'.repeat(64),accepted_at:1793966400}],report_validity:'not_rechecked',stop:null}
const evidence={scope:'Browser with controlled API fixtures; no backend/model claims.',states:[],errors:[],writes:[],checks:[]}
const browser=await chromium.launch({headless:true})
try {
  const context=await browser.newContext({viewport:{width:1440,height:1024}})
  await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:1},version:0})))
  const page=await context.newPage()
  page.setDefaultTimeout(8000)
  let mode='normal'
  page.on('pageerror',error=>evidence.errors.push(String(error)))
  await page.route('**/api/**',async route=>{
    const request=route.request(),url=new URL(request.url()),p=url.pathname
    if(!p.startsWith('/api/'))return route.continue()
    if(request.method()!=='GET')evidence.writes.push({method:request.method(),path:p})
    let body={}
    if(p==='/api/session')body={authenticated:true,csrf_token:'browser-fixture'}
    else if(p==='/api/projects')body={projects:[project,{...project,id:2,name:'Proyecto vacío',status:'new'}],total:2}
    else if(p==='/api/projects/1')body=project
    else if(p==='/api/projects/2')body={...project,id:2,name:'Proyecto vacío',status:'new'}
    else if(/^\/api\/projects\/\d+\/tasks\/\d+\/workspace$/.test(p))body={project_id:1,task_id:25,context:{task:tasks[1],context_version:1,corrections:[],task_changes:[]},runs:[],repositories:[],references:[],sources:[],reports:[],questions:[],runtime:{configured:false,supported_task_types:[],model:null}}
    else if(p.endsWith('/workspace')&&p.includes('/projects/')){
      if(mode==='error'&&p.includes('/1/'))return route.fulfill({status:503,json:{detail:'Fixture unavailable'}})
      body=p.includes('/2/')?{...workspace,project_id:2,project:{...project,id:2,name:'Proyecto vacío'},plans:[],reports:[],activity:[],sources:[]}:workspace
    }
    else if(p==='/api/tasks')body=url.searchParams.get('project_id')==='2'?[]:mode==='all-done'?tasks.map(t=>({...t,status:'done'})):tasks
    else if(p.endsWith('/questions'))body=p.includes('/2/')?{items:[],total_pending:0,next_after_id:null}:{items:url.searchParams.get('after_id')==='7'?[{...question,request_id:8,title:'Otra pregunta'}]:[question],total_pending:2,next_after_id:url.searchParams.get('after_id')==='7'?null:7}
    else if(p.includes('/progress'))body={total_tasks:3,done:3,completion_pct:100,by_status:{done:3},blocked_tasks:[],epic_progress:[]}
    else if(p.includes('/chat')||p.includes('/epics')||p.includes('/agents'))body=[]
    return route.fulfill({status:200,json:body})
  })
  /** Capture this same loaded state and reject scoped accessibility or horizontal-overflow defects. */
  async function capture(name,width){
    await page.setViewportSize({width,height:1024})
    const file=`${name}.png`
    await page.screenshot({path:path.join(out,file),fullPage:true})
    const axe=await new AxeBuilder({page}).include('.overview-workbench').analyze()
    expect(axe.violations).toEqual([])
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    evidence.states.push({file,width,axe_violations:axe.violations.length})
  }
  await page.goto(origin)
  if(process.env.OVERVIEW_BASELINE==='1'){
    await page.getByRole('heading',{name:'Atlas',exact:true}).waitFor()
    await page.screenshot({path:path.join(out,'before.png'),fullPage:true})
  }
  await expect(page.getByRole('heading',{name:'Necesita tu atención'})).toBeVisible()
  await expect(page.getByRole('heading',{name:'Preguntas pendientes'})).toBeVisible()
  await expect(page.locator('.overview-workbench')).not.toContainText('100%')
  await expect(page.getByRole('link',{name:'Revisar el plan de investigación',exact:true}).first()).toHaveAttribute('href','/tasks?project=1&task=24&planRun=plan-24')
  await capture('01-desktop',1440)
  await capture('02-mobile',390)
  await page.locator('#main-content').evaluate(node=>node.scrollTo(0,node.scrollHeight))
  await expect(page.getByRole('heading',{name:'Decisiones guardadas'})).toBeInViewport()
  await capture('02b-mobile-context',390)
  await page.locator('#main-content').evaluate(node=>node.scrollTo(0,0))
  await page.getByRole('button',{name:'Ver más pendientes'}).click()
  await expect(page.locator('[data-request-id="8"]')).toBeVisible()
  await page.locator('[data-request-id="7"] button').click()
  expect(new URL(page.url()).searchParams.get('question')).toBe('7')
  expect(new URL(page.url()).searchParams.get('task')).toBe('25')
  evidence.checks.push('question-pagination-and-original-navigation')
  mode='error';await page.goto(origin)
  await expect(page.getByText('No pudimos consultar el contexto del proyecto.')).toBeVisible()
  await expect(page.getByRole('heading',{name:'Preguntas pendientes'})).toBeVisible()
  await capture('03-partial-error',390)
  mode='normal';await page.getByRole('button',{name:'Actualizar resumen'}).click()
  await expect(page.getByText('No pudimos consultar el contexto del proyecto.')).toHaveCount(0)
  mode='all-done';await page.reload()
  await expect(page.getByText('3 tareas registradas · 3 marcadas como hechas.')).toBeVisible()
  await expect(page.locator('.overview-workbench')).not.toContainText('100%')
  await expect(page.locator('.overview-workbench')).not.toContainText('Proyecto completo')
  evidence.checks.push('all-done-is-not-project-acceptance','partial-error-retry')
  await page.getByRole('button',{name:'Seleccionar proyecto: Atlas'}).click()
  await page.getByRole('button',{name:'Proyecto vacío',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Proyecto vacío',exact:true})).toBeVisible()
  await expect(page.getByText('Todavía no hay tareas registradas.')).toBeVisible()
  await expect(page.locator('.overview-workbench')).not.toContainText('Revisar el plan de investigación')
  await capture('04-empty-other-project',390)
  evidence.checks.push('project-switch-isolation-and-empty-state')
  await page.evaluate(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:null},version:0})))
  // The initialization hook intentionally restores project 1 on reload; a separate page covers no selection.
  const emptyContext=await browser.newContext({viewport:{width:390,height:844}})
  await emptyContext.route('**/api/session',route=>route.fulfill({status:200,json:{authenticated:true,csrf_token:'fixture'}}))
  await emptyContext.route('**/api/projects',route=>route.fulfill({status:200,json:{projects:[],total:0}}))
  const emptyPage=await emptyContext.newPage();await emptyPage.goto(origin)
  await expect(emptyPage.getByRole('heading',{name:'Un lugar para retomar el trabajo'})).toBeVisible()
  await expect(emptyPage.getByRole('link',{name:'Abrir proyectos'})).toHaveAttribute('href','/projects')
  await emptyContext.close();evidence.checks.push('no-selection-navigation')
  expect(evidence.errors).toEqual([]);expect(evidence.writes).toEqual([])
  evidence.status='passed'
} finally {
  await browser.close()
  await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

/** Inspect the original failed planning attempt through current Projects and Tasks, permitting only reads and pairing. @module */
import {chromium, expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN, output=process.env.RESEARCHER_E2E_OUTPUT
if(!origin || !output || new URL(origin).hostname!=='127.0.0.1') throw new Error('Use the retained original Projects reader')
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
const evidence={status:'running',states:[],errors:[],requests:[],forbidden:[],checks:[]}
const browser=await chromium.launch({headless:true})
await fs.mkdir(output,{recursive:false})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1100}})
 await context.addInitScript(project=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:project},version:0})),ids.project)
 const page=await context.newPage()
 page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 await page.route('**/api/**',route=>{
  const request=route.request(),pathname=new URL(request.url()).pathname,method=request.method()
  evidence.requests.push({method,path:pathname})
  if(method!=='GET' && !(method==='POST' && pathname==='/api/session')){
   evidence.forbidden.push({method,path:pathname});return route.abort('blockedbyclient')
  }
  return route.continue()
 })
 /** Capture the actual selected region at the current viewport, keeping each audit's accessibility scope explicit. */
 async function capture(name,width,selector){
  await page.setViewportSize({width,height:1100})
  await page.locator(selector).first().scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,name+'.png'),fullPage:true})
  const audit=await new AxeBuilder({page}).include(selector).analyze()
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)
  evidence.states.push({name,width,fits,violations:audit.violations})
  expect(fits).toBe(true);expect(audit.violations).toEqual([])
 }
 /** Open the original dossier and follow its exact persisted task/run link without starting planning. */
 async function openOriginal(){
  await page.goto(origin+'/projects')
  await page.locator('#project-select-'+ids.project).click()
  await expect(page.locator('#project-dossier-title')).toHaveText(ids.name)
  const href=`/tasks?project=${ids.project}&task=${ids.task}&planRun=${encodeURIComponent(ids.run)}`
  const link=page.locator(`a[href="${href}"]`)
  await expect(link).toBeVisible()
  return link
 }
 await page.goto(origin+'/projects')
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.locator('#project-select-'+ids.project)).toBeVisible()
 const firstBudget=await page.request.get(`${origin}/api/projects/${ids.project}/work-budget`)
 expect(firstBudget.status()).toBe(200);evidence.budget_before=await firstBudget.json()
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1100})
  let link=await openOriginal()
  await capture('projects-'+width,width,'.project-workbench')
  await link.click()
  await expect(page).toHaveURL(new RegExp(`task=${ids.task}.*planRun=${ids.run}`))
  await expect(page.locator('#task-title-'+ids.task)).toBeVisible()
  const issue=page.getByRole('region',{name:'Lo que ocurrió',exact:true})
  await expect(issue).toContainText(ids.issue.message)
  await capture('original-failure-'+width,width,'.task-execution')
  await page.reload();await expect(issue).toContainText(ids.issue.message)
  const response=await page.request.get(`${origin}/api/projects/${ids.project}/tasks/${ids.task}/workspace`)
  expect(response.status()).toBe(200)
  const workspace=await response.json(),run=workspace.runs.find(value=>value.run_id===ids.run)
  expect(run?.status).toBe('failed');expect(run?.issue).toMatchObject(ids.issue)
  evidence.observed_run={run_id:run.run_id,status:run.status,context_version:run.context_version,issue:run.issue}
  link=await openOriginal();await expect(link).toBeVisible()
 }
 const lastBudget=await page.request.get(`${origin}/api/projects/${ids.project}/work-budget`)
 expect(lastBudget.status()).toBe(200);evidence.budget_after=await lastBudget.json()
 expect(evidence.budget_after).toEqual(evidence.budget_before)
 expect(evidence.forbidden).toEqual([]);expect(evidence.errors).toEqual([])
 evidence.checks=['original-project-task-run-link','same-failed-attempt-after-reload','historical-issue-preserved','return-to-original-dossier','original-budget-preserved','only-get-and-pairing','desktop-mobile-no-overflow-regional-axe']
 evidence.status='passed'
}finally{
 await browser.close()
 await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}

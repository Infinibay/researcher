/** Observe one real browser planning admission while the diagnostic server forbids every generation path. @module */
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {chromium,expect} from '@playwright/test'

const origin=process.env.RESEARCHER_E2E_ORIGIN,owner=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT,project=Number(process.env.RESEARCHER_E2E_PROJECT_ID)
if(!origin||!owner||!out||!Number.isSafeInteger(project)||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use the generation-forbidden diagnostic supervisor on a NEW synthetic host')
await fs.mkdir(out,{recursive:false})
const evidence={status:'running',scope:'Real browser requests during one planning bootstrap; server guards forbid inference',admissions_sent:0,reads:[],errors:[]}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 const paired=await context.request.post(origin+'/api/session',{data:{code:(await fs.readFile(owner,'utf8')).trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}});assert.equal(paired.status(),200)
 const session=await paired.json();await context.setExtraHTTPHeaders({Origin:origin,'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id})
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),project)
 const page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 page.on('request',request=>{const url=new URL(request.url());if(request.method()==='GET'&&url.pathname.startsWith('/api/'))evidence.reads.push({path:url.pathname,at:Date.now()});if(request.method()==='POST'&&url.pathname===`/api/projects/${project}/start`){evidence.admissions_sent++;evidence.request=request.postDataJSON()}})
 await page.goto(origin+'/projects');await page.locator('#project-select-'+project).click()
 const prepare=page.getByRole('button',{name:'Preparar un plan',exact:true});await expect(prepare).toBeEnabled();await page.screenshot({path:path.join(out,'01-before-admission.png')})
 const response=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/projects/${project}/start`&&r.request().method()==='POST')
 await prepare.click();const accepted=await response;assert.equal(accepted.status(),200);evidence.admission=await accepted.json();evidence.run_id=evidence.admission.run.run_id
 await page.waitForURL(url=>url.pathname==='/tasks');await page.goto(origin+'/projects');await page.locator('#project-select-'+project).click()
 let view
 await expect.poll(async()=>{const r=await context.request.get(origin+`/api/projects/${project}/runs/${evidence.run_id}`);assert.equal(r.status(),200);view=await r.json();return ['failed','reconciling','cancelled','needs_review'].includes(view.status)},{timeout:120000,intervals:[500,1000,2000]}).toBe(true)
 evidence.terminal_status=view.status;await page.screenshot({path:path.join(out,'02-original-terminal-observation.png')})
 assert.equal(evidence.admissions_sent,1);assert.deepEqual(evidence.errors,[]);evidence.status='observed'
}catch(error){evidence.status='probe_failed';evidence.failure=String(error);throw error}
finally{await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}

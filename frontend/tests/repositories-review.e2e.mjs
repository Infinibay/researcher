/** Check actual source registration receipts, literal no-Git feedback and selection across project changes. @module */
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const origin=process.env.RESEARCHER_E2E_ORIGIN,owner=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT
const fixture=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_REPOSITORY_FIXTURE,'utf8')),original=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_REPOSITORY_RECEIPT,'utf8'))
assert.equal(original.status,'passed');const {alpha,beta}=original.identities
await fs.mkdir(out,{recursive:false})
const evidence={status:'running',states:[],errors:[],identities:{alpha,beta},scope:'Actual additional registrations only; original source setup history unchanged; no Git writes, remote calls or models'}
const browser=await chromium.launch({headless:true});let releaseLate,page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 const paired=await context.request.post(origin+'/api/session',{data:{code:(await fs.readFile(owner,'utf8')).trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}});assert.equal(paired.status(),200)
 const session=await paired.json();await context.setExtraHTTPHeaders({Origin:origin,'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id})
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),alpha)
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 /** Preserve the actual visible region and scoped geometry/accessibility observations. */
 async function capture(name,selector='.repo-reading'){await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('.repo-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width:page.viewportSize().width,fits,violations:axe.violations});assert.equal(fits,true);assert.deepEqual(axe.violations,[])}
 /** Select an actual project without issuing another registration or preparation. */
 async function project(name){await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click();await page.getByRole('button',{name:new RegExp('^'+name)}).click()}
 /** Retain exact selected directory/name before an explicit owner registration. */
 async function form(name,folder){await page.getByRole('button',{name:'Registrar carpeta existente',exact:true}).click();await page.getByLabel('Nombre del registro',{exact:true}).fill(name);await page.getByLabel('Ruta absoluta existente',{exact:true}).fill(folder)}
 await page.goto(origin+'/repositories');await form('sin-git',fixture.raw)
 let published
 const lose=async route=>{const r=await route.fetch();assert.equal(r.status(),200);published=await r.json();await route.abort('failed')}
 await page.route(`**/api/projects/${alpha}/sources`,lose);await page.getByRole('button',{name:'Registrar esta fuente',exact:true}).click();await page.getByRole('alert').waitFor();await capture('01-lost-registration-receipt')
 await page.unroute(`**/api/projects/${alpha}/sources`,lose);await page.reload();await page.getByRole('button',{name:'Recuperar registro original',exact:true}).click();await page.getByRole('heading',{name:'sin-git',exact:true}).waitFor();await page.getByRole('alert').filter({hasText:'No se pudo consultar Git.'}).waitFor();await capture('02-same-registration-without-git')
 const repos=await(await context.request.get(origin+`/api/git/repos?project_id=${alpha}`)).json();assert.equal(repos.filter(r=>r.name==='sin-git').length,1);assert.equal(repos.find(r=>r.name==='sin-git').id,published.repository_id);evidence.registration=published
 await project('Exportador independiente');await page.getByText('No hay fuentes registradas en este proyecto.',{exact:true}).waitFor();await form('original',fixture.beta.path)
 await page.getByRole('button',{name:'Registrar esta fuente',exact:true}).click();await page.getByRole('heading',{name:'original',exact:true}).waitFor();await page.getByRole('button',{name:'Archivo README.md',exact:true}).click();await expect(page.locator('.repo-document')).toContainText('Material de otro proyecto');await expect(page.locator('.repo-document')).not.toContainText('Conserva el orden original');await capture('03-independent-homonymous-source')
 await project('Exportador principal');await form('tardia',fixture.root+'/late-existing')
 let delivered;const held=new Promise(resolve=>{delivered=resolve}),gate=new Promise(resolve=>{releaseLate=resolve})
 const late=async route=>{const r=await route.fetch();assert.equal(r.status(),200);evidence.late_registration=await r.json();delivered();await gate;await route.fulfill({response:r})}
 await page.route(`**/api/projects/${alpha}/sources`,late);await page.getByRole('button',{name:'Registrar esta fuente',exact:true}).click();await held
 await project('Exportador independiente');await project('Exportador principal');await page.locator('.repo-select').filter({hasText:'original'}).click();await page.getByRole('heading',{name:'original',exact:true}).waitFor();releaseLate();await expect.poll(()=>page.evaluate(id=>sessionStorage.getItem(`researcher:project-source:v1:${id}`),alpha)).toBeNull();await page.unroute(`**/api/projects/${alpha}/sources`,late)
 await expect(page.locator('#repo-source-title')).toHaveText('original');await capture('04-late-response-keeps-current-visit')
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Carpeta src',exact:true}).click();await page.getByRole('button',{name:'Archivo catalog.py',exact:true}).click();await page.getByRole('region',{name:'Texto original de src/catalog.py',exact:true}).waitFor();await capture('05-current-code-mobile','.repo-file-pane')
 assert.deepEqual(evidence.errors,[]);evidence.status='passed'
}catch(error){evidence.status='failed';evidence.failure=String(error);if(page)await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw error}
finally{releaseLate?.();await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}

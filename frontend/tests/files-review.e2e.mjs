/** Inspect retained archive regions without repeating attachment mutations or starting inference. @module */
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const origin=process.env.RESEARCHER_E2E_ORIGIN,owner=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT,receipt=process.env.RESEARCHER_E2E_FILES_RECEIPT
if(!origin||!owner||!out||!receipt||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use the stopped synthetic Files acceptance installation and original receipt')
const fixture=JSON.parse(await fs.readFile(receipt,'utf8'));assert.equal(fixture.status,'passed')
const alpha=fixture.identities.alpha
await fs.mkdir(out,{recursive:false})
const evidence={status:'running',scope:'Read-only attachment review plus one explicit empty metadata project; zero attachment mutations or model calls',states:[],errors:[]}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:390,height:844}})
 const paired=await context.request.post(origin+'/api/session',{data:{code:(await fs.readFile(owner,'utf8')).trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}});assert.equal(paired.status(),200)
 const session=await paired.json();await context.setExtraHTTPHeaders({Origin:origin,'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id})
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),alpha)
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 /** Capture the actual visible region with scoped geometry and accessibility observations. */
 async function capture(name,selector){await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('.files-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width:page.viewportSize().width,region:selector,fits,violations:axe.violations});assert.equal(fits,true);assert.deepEqual(axe.violations,[])}
 await page.goto(origin+`/files?project=${alpha}`)
 await page.getByLabel('Buscar archivos',{exact:true}).fill('registro-00')
 await expect(page.locator('.files-list>li')).toHaveCount(1);await capture('01-current-search-result','.files-index')
 await page.getByLabel('Buscar archivos',{exact:true}).fill('sin-coincidencias-verificadas')
 await expect(page.locator('.files-list>li')).toHaveCount(0);await capture('02-current-no-search-result','.files-index')
 const selected=fixture.files.find(f=>f.name==='respuesta-perdida.txt');assert.ok(selected)
 await page.goto(origin+`/files?project=${alpha}&file=${selected.id}`)
 await page.getByRole('heading',{name:selected.name,exact:true}).waitFor();await capture('03-selected-original-mobile','.files-inspector')
 const pdf=fixture.files.find(f=>f.name==='original.pdf');assert.ok(pdf)
 await page.goto(origin+`/files?project=${alpha}&file=${pdf.id}`);await page.getByRole('heading',{name:pdf.name,exact:true}).waitFor()
 await page.getByRole('button',{name:'Extraer previa',exact:true}).click();await page.getByLabel('Texto extraído del adjunto',{exact:true}).waitFor();await capture('04-current-pdf-text-mobile','.files-preview')
 // A real metadata-only project supplies an empty catalog without fabricating business responses.
 if(process.env.RESEARCHER_E2E_EMPTY_PROJECT)evidence.empty_project=Number(process.env.RESEARCHER_E2E_EMPTY_PROJECT)
 else{const made=await context.request.post(origin+'/api/projects',{data:{name:'Archivo vacío',description:'Synthetic empty Files visual review.',operation_key:crypto.randomUUID()}});assert.equal(made.status(),201);evidence.empty_project=(await made.json()).id}
 await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click();await page.getByRole('button',{name:/^Archivo vacío/}).click()
 await expect(page.getByRole('button',{name:/^Seleccionar proyecto: Archivo vacío/})).toBeVisible()
 await page.getByText('Todavía no hay adjuntos. Puedes subir el primero desde el formulario.',{exact:true}).waitFor()
 await expect(page.locator('.files-list>li')).toHaveCount(0);await capture('05-actual-empty-mobile','.files-index')
 await page.setViewportSize({width:1440,height:1024});await capture('06-actual-empty-desktop','.files-index')
 assert.deepEqual(evidence.errors,[]);evidence.status='passed'
}catch(error){evidence.status='failed';evidence.failure=String(error);throw error}
finally{await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}

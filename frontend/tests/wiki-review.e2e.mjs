/** Complete visual evidence for current document comparison, retained text and an actual empty project. @module */
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const origin=process.env.RESEARCHER_E2E_ORIGIN,ownerFile=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT,fixtureFile=process.env.RESEARCHER_E2E_WIKI_FIXTURE
if(!origin||!ownerFile||!out||!fixtureFile||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use the retained document acceptance host and its original fixture identities')
const fixture=JSON.parse(await fs.readFile(fixtureFile,'utf8')).identities
await fs.mkdir(out,{recursive:false})
const evidence={result:'running',scope:'Actual current document comparison and retained text; one new empty metadata project, zero document writes or inference',states:[],errors:[],identities:fixture}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 const paired=await context.request.post(origin+'/api/session',{data:{code:(await fs.readFile(ownerFile,'utf8')).trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}})
 assert.equal(paired.status(),200)
 const session=await paired.json();await context.setExtraHTTPHeaders({Origin:origin,'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id})
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),fixture.alpha)
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 /** Record the visible state and scoped accessibility observations without treating them as human comprehension. */
 async function capture(name){const target=path.join(out,name+'.png');await page.screenshot({path:target,fullPage:true});const axe=await new AxeBuilder({page}).include('.wiki-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width:page.viewportSize().width,violations:axe.violations,fits});assert.equal(fits,true);assert.deepEqual(axe.violations,[])}
 const api=`${origin}/api/wiki/${encodeURIComponent('modernization/context')}?project_id=${fixture.alpha}`
 const before=await(await context.request.get(api)).json()
 await page.goto(origin+`/wiki?project=${fixture.alpha}&namespace=project&path=modernization%2Fcontext&pageId=${fixture.context}`)
 await page.getByRole('heading',{name:'Contexto compartido',exact:true}).waitFor()
 await page.getByRole('button',{name:'Editar',exact:true}).click()
 await page.getByRole('button',{name:'Comparar con la versión guardada',exact:true}).click()
 await page.getByRole('heading',{name:`Versión consultada · revisión ${before.revision}`,exact:true}).waitFor()
 await page.locator('.wiki-comparison').scrollIntoViewIfNeeded();await capture('01-current-comparison-panel')
 await page.getByRole('button',{name:'Cerrar editor y conservar borrador',exact:true}).click()
 await page.setViewportSize({width:390,height:844})
 await page.getByRole('button',{name:'Ver versiones',exact:true}).click();await page.getByRole('button',{name:'Más versiones',exact:true}).click()
 await page.getByRole('button',{name:'Ver texto de revisión 1',exact:true}).click()
 const retained=page.getByLabel('Texto de revisión 1',{exact:true});await retained.waitFor();await retained.scrollIntoViewIfNeeded();await capture('02-original-retained-text')
 assert.equal((await(await context.request.get(api)).json()).revision,before.revision)
 // Actual metadata creation supplies a genuinely empty namespace without fabricating an empty read response.
 const made=await context.request.post(origin+'/api/projects',{data:{name:'Cuaderno vacío',description:'Synthetic empty document acceptance project.',operation_key:crypto.randomUUID()}})
 assert.equal(made.status(),201);const empty=await made.json();evidence.empty_project=empty.id
 await page.reload();await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click();await page.getByRole('button',{name:/^Cuaderno vacío/}).click()
 await page.getByRole('button',{name:'Documentos del proyecto actual',exact:true}).click()
 await page.getByText('Todavía no hay páginas en este ámbito. Puedes crear la primera.',{exact:true}).waitFor()
 await expect(page.locator('.wiki-page-list>li')).toHaveCount(0);await capture('03-actual-empty-mobile')
 await page.setViewportSize({width:1440,height:1024});await capture('04-actual-empty-desktop')
 assert.deepEqual(evidence.errors,[]);evidence.result='passed'
} catch(error){evidence.result='failed';evidence.failure=String(error);throw error}
finally{await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}

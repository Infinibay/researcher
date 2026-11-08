/** Read one original generated parked question; independent money result remains visible without choosing its unresolved unit. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use the retained original handoff reader')
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8')),evidence={status:'running',states:[],errors:[],checks:[]},browser=await chromium.launch({headless:true})
await fs.mkdir(output,{recursive:false})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}});await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0})))
 const page=await context.newPage();page.on('pageerror',error=>evidence.errors.push(String(error)));page.setDefaultTimeout(15000)
 await page.route('**/api/**',route=>{if(route.request().method()!=='GET'&&new URL(route.request().url()).pathname!=='/api/session')throw new Error('Original question review cannot send answers, notes or work');return route.continue()})
 await page.goto(`${origin}/chat?project=${ids.project}&task=${ids.task}&question=${ids.question}`);await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim());await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 const card=page.locator(`#runtime-question-${ids.question}`)
 await expect(card).toBeVisible();await expect(card).toContainText('4 unidades × 12,50 €/unidad = 50,00 €');await expect(card).toContainText('resultados condicionales');await expect(card).toContainText('Ninguna copia tiene prioridad')
 await expect(card.getByRole('button',{name:'Guardar respuestas',exact:true})).toBeDisabled()
 for(const width of [1440,390]){await page.setViewportSize({width,height:1024});await card.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,`question-${width}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include(`#runtime-question-${ids.question}`).analyze(),fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);expect(fits).toBe(true);expect(axe.violations).toEqual([]);evidence.states.push({width,fits,violations:axe.violations})}
 expect(evidence.errors).toEqual([]);evidence.checks=['actual-generated-independent-result-visible','literal-basis-quantity-unit-price','conflict-no-priority-or-operational-volume','conditional-factor1000-options-visible','no-answer-no-work-admission','desktop-mobile-regional-axe-no-overflow'];evidence.status='passed'
}finally{await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')}

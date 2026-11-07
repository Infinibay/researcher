/** Exercise the actual installed owner's HTTP/WebSocket service with controlled committed events. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import {execFileSync} from 'node:child_process'

const origin=process.env.EVENT_ORIGIN,database=process.env.EVENT_DATABASE,python=process.env.EVENT_PYTHON
const out=path.resolve(process.env.EVENT_ARTIFACT_DIR)
await fs.mkdir(out,{recursive:true})
const evidence={scope:'Actual installed HTTP/WebSocket server and compiled frontend, synthetic SQLite rows, no runtime/model/account.',states:[],frames:[],connections:[],errors:[],checks:[]}
/** Commit observations through a separate SQLite connection while the browser transport runs. */
function append(count,batch,remove=-1){
 const program=`import json,sqlite3,sys\nwith sqlite3.connect(sys.argv[1]) as db:\n ids=[]\n for i in range(int(sys.argv[2])):\n  ids.append(db.execute("INSERT INTO events_log(project_id,event_type,event_source,event_data_json,created_at) VALUES(1,'evaluation.observed','evaluation',?,'2026-11-07 00:00:00')",(json.dumps({'message':sys.argv[3]+'-'+str(i)}),)).lastrowid)\n if int(sys.argv[4])>=0:db.execute('DELETE FROM events_log WHERE id=?',(ids[int(sys.argv[4])],))\nprint(json.dumps(ids))`
 return JSON.parse(execFileSync(python,['-I','-c',program,database,String(count),batch,String(remove)],{encoding:'utf8'}))
}
const initial=append(237,'initial')
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{
  localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:1},version:0}))
  // Fault injection retains actual browser sockets; it does not replace their protocol or callbacks.
  const NativeWebSocket=window.WebSocket
  window.__eventSockets=[]
  window.WebSocket=new Proxy(NativeWebSocket,{construct(Target,args){const socket=new Target(...args);window.__eventSockets.push(socket);return socket}})
 })
 const page=await context.newPage();page.setDefaultTimeout(10000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('websocket',socket=>{evidence.connections.push(socket.url());socket.on('framereceived',frame=>{const data=JSON.parse(String(frame.payload));if(data.type==='events.page')evidence.frames.push(data)})})
 const paired=await page.request.post(origin+'/api/session',{data:{code:'event-browser-fixture-code-at-least-32-characters'},headers:{'X-Researcher-Client':'web',Origin:origin}})
 expect(paired.status()).toBe(200)
 await page.goto(origin+'/agents')
 await page.getByRole('button',{name:'Actividad del proyecto'}).click()
 await expect(page.getByText('Evento registrado: evaluation.observed: initial-236',{exact:true})).toBeVisible()
 /** Capture rendered transport evidence without accepting the whole page's inherited visual design. */
 async function capture(name,width){await page.setViewportSize({width,height:1024});await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});const audit=await new AxeBuilder({page}).analyze();evidence.states.push({name,width,axe:audit.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length})),horizontal_overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)})}
 await capture('01-retained-history',1440)
 /** Close only the owned test connection; production reconnect retains its original last-applied cursor. */
 async function disconnect(){await page.evaluate(()=>window.__eventSockets.filter(socket=>socket.readyState===WebSocket.OPEN).forEach(socket=>socket.close()));await expect(page.getByRole('status').filter({hasText:'Reconectando'})).toBeVisible()}
 await disconnect()
 const later=append(251,'offline')
 await expect(page.getByText('Evento registrado: evaluation.observed: offline-250',{exact:true})).toBeVisible()
 const delivered=evidence.frames.flatMap(frame=>frame.events??[]).filter(event=>event.type==='evaluation.observed').map(event=>Number(event.event_id))
 expect(delivered).toEqual([...initial,...later])
 expect(new Set(delivered).size).toBe(delivered.length)
 expect(evidence.connections.some(url=>new URL(url).searchParams.get('after_id')===String(initial.at(-1)))).toBe(true)
 evidence.checks.push('488-events-over-multiple-pages','equal-timestamps','actual-disconnect-and-resume','no-duplicates-before-retention')
 await capture('02-reconnected-history',390)
 await disconnect()
 const retained=append(5,'retained',1)
 await expect(page.getByRole('alert').filter({hasText:'Una parte del historial'})).toBeVisible()
 await expect(page.getByText('Evento registrado: evaluation.observed: retained-4',{exact:true})).toBeVisible()
 expect(evidence.frames.some(frame=>frame.reset_required&&frame.resume_after_id===String(retained[1]))).toBe(true)
 await capture('03-retention-warning',390)
 await page.getByRole('button',{name:'Actividad del proyecto'}).click()
 await page.getByRole('button',{name:'Seleccionar proyecto: Eventos controlados'}).click()
 await page.getByRole('button',{name:'Otro proyecto',exact:true}).click()
 await page.getByRole('button',{name:'Actividad del proyecto'}).click()
 await expect(page.getByText('No hay eventos para mostrar en esta vista.')).toBeVisible()
 await expect(page.getByText('Evento registrado: evaluation.observed: retained-4',{exact:true})).toHaveCount(0)
 evidence.checks.push('explicit-retention-snapshot-required','project-switch-clears-original-observations')
 expect(evidence.errors).toEqual([])
}finally{await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}

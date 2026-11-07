/** Retention controls preserve original owner decisions and explain byte recovery without implying execution or acceptance. @module */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, expect, it, vi } from 'vitest'
import { RetainedWork } from '../../src/components/repositories/RetainedWork'
import type { RetainedWork as Copy, RetentionOperation } from '../../src/api/workspaceRetention'

const transport=vi.hoisted(()=>({ownerFetch:vi.fn()}))
vi.mock('../../src/api/session',()=>transport)
const original:Copy={project_id:101,attempt_id:'original-attempt',run_id:'original-run',task_id:1001,title:'Cambios del informe',state:'available',preparation_state:'ready',retain_until:null,archive_sha256:null,bytes:null,changes:null}

/** Isolate actual React Query caches; failed requests are not retried by the test wrapper. */
function wrapper(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}});return function Provider({children}:{children:React.ReactNode}){return <QueryClientProvider client={client}>{children}</QueryClientProvider>}}
/** Preserve real fetch response/error handling while controlling only server data. */
function json(value:unknown,status=200){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}})}
beforeEach(()=>{vi.clearAllMocks();sessionStorage.clear()})

it('requires the chosen period and acknowledgement before archiving one exact copy',async()=>{
 const user=userEvent.setup();let copy={...original};let operations:RetentionOperation[]=[]
 transport.ownerFetch.mockImplementation(async(path:string,options?:RequestInit)=>{
  if(options?.method==='POST'){
   expect(path).toBe('/api/projects/101/retained-work/original-attempt/quarantine')
   const body=JSON.parse(String(options.body));expect(body).toEqual({operation_key:expect.any(String),retention_days:3,acknowledge_unavailability:true})
   const operation:RetentionOperation={project_id:101,attempt_id:copy.attempt_id,operation_key:body.operation_key,kind:'archive',state:'completed',issue:null,receipt:{archive_sha256:'a'.repeat(64)},created_at:1794081600,updated_at:1794081600}
   operations=[operation];copy={...copy,state:'retained',archive_sha256:'a'.repeat(64),retain_until:Date.now()/1000+259200,bytes:123,changes:{state:'observed',tracked:1,untracked:1,ignored:1}}
   return json(operation)
  }
  return json(path.includes('/operations')?operations:[copy,{...copy,project_id:202,attempt_id:'foreign',title:'FOREIGN COPY'}])
 })
 render(<RetainedWork projectId={101} onClose={()=>{}}/>,{wrapper:wrapper()})
 const archive=await screen.findByRole('button',{name:'Poner en cuarentena y archivar'})
 expect(archive).toBeDisabled();expect(screen.queryByText('FOREIGN COPY')).toBeNull()
 expect(transport.ownerFetch.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(0)
 const days=screen.getByRole('spinbutton');await user.clear(days);await user.type(days,'3')
 await user.click(screen.getByRole('checkbox'));await user.click(archive)
 expect(await screen.findByText('Archivo de recuperación verificado')).toBeVisible()
 expect(screen.getByRole('button',{name:'Eliminar la copia original'})).toBeDisabled()
 expect(screen.getByText(/sin reactivar agentes ni aceptar código/)).toBeVisible()
})

it('keeps a lost response across reload and reads the original receipt without automatically resending',async()=>{
 const user=userEvent.setup();let recorded:RetentionOperation|null=null
 transport.ownerFetch.mockImplementation(async(path:string,options?:RequestInit)=>{
  if(options?.method==='POST'){
   const body=JSON.parse(String(options.body));recorded={project_id:101,attempt_id:'original-attempt',operation_key:body.operation_key,kind:'archive',state:'completed',issue:null,receipt:{bytes_deleted:false},created_at:1,updated_at:1}
   return json({detail:'Respuesta perdida'},500)
  }
  if(path.includes('/operations/'))return json(recorded)
  return json(path.includes('/operations')?[]:[original])
 })
 const first=render(<RetainedWork projectId={101} onClose={()=>{}}/>,{wrapper:wrapper()})
 await screen.findByRole('checkbox');await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:'Poner en cuarentena y archivar'}))
 expect(await screen.findByText(/Respuesta perdida/)).toBeVisible();first.unmount()
 render(<RetainedWork projectId={101} onClose={()=>{}}/>,{wrapper:wrapper()})
 expect(await screen.findByText('Solicitud sin confirmar')).toBeVisible()
 expect(transport.ownerFetch.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(1)
 await user.click(screen.getByRole('button',{name:'Consultar solicitud original'}))
 await waitFor(()=>expect(screen.queryByText('Solicitud sin confirmar')).toBeNull())
 expect(transport.ownerFetch.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(1)
})

it('restores only the observed archive and presents a fresh folder without implying publication',async()=>{
 const user=userEvent.setup();const copy={...original,state:'removed',archive_sha256:'b'.repeat(64),retain_until:1,bytes:123};let operations:RetentionOperation[]=[]
 transport.ownerFetch.mockImplementation(async(path:string,options?:RequestInit)=>{
  if(options?.method==='POST'){
   expect(path).toBe('/api/projects/101/retained-work/original-attempt/restore')
   const body=JSON.parse(String(options.body));expect(body.archive_sha256).toBe('b'.repeat(64))
   const operation:RetentionOperation={project_id:101,attempt_id:'original-attempt',operation_key:body.operation_key,kind:'restore',state:'completed',issue:null,receipt:{restored_path:'/sources/recovered-new',publication_performed:false,execution_started:false},created_at:1,updated_at:1}
   operations=[operation];return json(operation)
  }
  return json(path.includes('/operations')?operations:[copy])
 })
 render(<RetainedWork projectId={101} onClose={()=>{}}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Recuperar en carpeta nueva'}))
 expect(await screen.findByText('/sources/recovered-new')).toBeVisible()
 expect(screen.getByText(/Puedes registrar esa carpeta como una fuente nueva/)).toBeVisible()
 expect(screen.queryByRole('button',{name:'Eliminar la copia original'})).toBeNull()
})

/** Verify human continuation decisions retain exact scope across response loss and reload. @module */
import {render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {beforeEach,expect,it,vi} from 'vitest'
import {LocalWork} from '../../src/components/tasks/LocalWork'

const api=vi.hoisted(()=>({localWork:vi.fn(),sendLocalContinuation:vi.fn(),readLocalContinuation:vi.fn()}))
vi.mock('../../src/api/localWork',async original=>({...await original<typeof import('../../src/api/localWork')>(),...api}))
const operation='a'.repeat(64)
/** Give each mounted view independent cached observations. */
function wrapper(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});return function Provider({children}:{children:React.ReactNode}){return <QueryClientProvider client={client}>{children}</QueryClientProvider>}}
/** Return an exact receipt without claiming the calculation started. */
function receipt(action:any){return {project_id:action.projectId,...action.body,successor_operation_id:'b'.repeat(64),generation:1,work_started:false}}
beforeEach(()=>{sessionStorage.clear();vi.clearAllMocks();api.localWork.mockImplementation(async(id:number)=>({project_id:id,items:[{sequence:1,project_id:id,operation_id:operation,kind:'semantic',input_bytes:100,attempt_id:null,status:'unknown',observed_cpu_ms:null,cpu_ceiling_ms:3000,created_at:1,diagnosis:{code:'ready',message:'El trabajador terminó.',can_continue:true}}],next_before:null}))})

it('persists before write and recovers the original permission after reload without another POST',async()=>{
 const user=userEvent.setup();let original:any
 api.sendLocalContinuation.mockImplementation(async action=>{original=action;expect(sessionStorage.length).toBe(1);throw new TypeError('response lost')})
 api.readLocalContinuation.mockImplementation(async action=>receipt(action))
 const view=render(<LocalWork projectId={101}/>,{wrapper:wrapper()})
 await user.click(screen.getByRole('button',{name:'Revisar cálculos locales'}))
 await user.click(await screen.findByRole('button',{name:'Autorizar un nuevo cálculo'}))
 expect(screen.getByText(/próxima solicitud idéntica del usuario o de un agente/)).toBeVisible()
 await user.click(screen.getByRole('button',{name:'Guardar autorización'}))
 expect(await screen.findByText(/No se confirmó la autorización/)).toBeVisible()
 view.unmount();render(<LocalWork projectId={101}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Consultar autorización original'}))
 expect(await screen.findByText(/Autorización guardada.*No se inició/)).toBeVisible()
 expect(api.sendLocalContinuation).toHaveBeenCalledTimes(1)
 expect(api.readLocalContinuation.mock.calls[0][0]).toEqual(original)
 expect(sessionStorage.length).toBe(0)
})

it('does not offer continuation when actual process closure is unknown',async()=>{
 api.localWork.mockResolvedValue({project_id:101,items:[{sequence:1,project_id:101,operation_id:operation,kind:'pdf',input_bytes:100,status:'reserved',cpu_ceiling_ms:3000,created_at:1,diagnosis:{code:'closure_unknown',message:'No se pudo comprobar el cierre.',can_continue:false}}],next_before:null})
 const user=userEvent.setup();render(<LocalWork projectId={101}/>,{wrapper:wrapper()})
 await user.click(screen.getByRole('button',{name:'Revisar cálculos locales'}))
 expect(await screen.findByText('No se pudo comprobar el cierre.')).toBeVisible()
 expect(screen.queryByRole('button',{name:'Autorizar un nuevo cálculo'})).not.toBeInTheDocument()
 expect(api.sendLocalContinuation).not.toHaveBeenCalled()
})

it('keeps unresolved permission in its original project',async()=>{
 const user=userEvent.setup();api.sendLocalContinuation.mockRejectedValue(new TypeError('lost'))
 const view=render(<LocalWork projectId={101}/>,{wrapper:wrapper()})
 await user.click(screen.getByRole('button',{name:'Revisar cálculos locales'}))
 await user.click(await screen.findByRole('button',{name:'Autorizar un nuevo cálculo'}))
 await user.click(screen.getByRole('button',{name:'Guardar autorización'}))
 await screen.findByText(/No se confirmó la autorización/)
 view.unmount();render(<LocalWork projectId={202}/>,{wrapper:wrapper()})
 expect(screen.queryByRole('button',{name:'Consultar autorización original'})).not.toBeInTheDocument()
 expect(sessionStorage.length).toBe(1)
})

/** Project policy choices, recoverable uncertainty and immutable observed revisions. @module */
import {render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {beforeEach,expect,it,vi} from 'vitest'
import {CheckPolicyEditor} from '../../src/components/tasks/CheckPolicyEditor'
import {ApiError} from '../../src/api/client'
const api=vi.hoisted(()=>({sendCheckPolicy:vi.fn(),readCheckPolicyReceipt:vi.fn()}))
vi.mock('../../src/api/projectCheckPolicy',async original=>({...await original<typeof import('../../src/api/projectCheckPolicy')>(),...api}))
/** Supply isolated query state so recovery cannot accidentally reuse another test's result. */
function wrapper(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});return function Provider({children}:{children:React.ReactNode}){return <QueryClientProvider client={client}>{children}</QueryClientProvider>}}
/** Echo the exact request as a controlled original backend receipt. */
function receipt(action:any){return {project_id:action.projectId,...action.body,revision:action.body.expected_revision+1,inference_started:false,applies_to:'future_code_acceptances'}}
beforeEach(()=>{sessionStorage.clear();vi.clearAllMocks()})

it('explains the choice and recovers a lost response after reload without another write',async()=>{
 const user=userEvent.setup();let sent:any
 api.sendCheckPolicy.mockImplementation(async action=>{sent=action;expect(sessionStorage.length).toBe(1);throw new Error('response lost')})
 api.readCheckPolicyReceipt.mockImplementation(async action=>receipt(action))
 const view=render(<CheckPolicyEditor projectId={101} policy={{revision:0,mode:null}}/>,{wrapper:wrapper()})
 expect(screen.getByText(/Todavía no elegiste/)).toBeVisible()
 await user.click(screen.getByRole('button',{name:'Elegir política de pruebas'}))
 expect(screen.getByText(/el comando terminó bien/)).toBeVisible()
 await user.selectOptions(screen.getByLabelText('Requisito para nuevas aceptaciones'),'allow_missing')
 await user.click(screen.getByRole('button',{name:'Guardar política'}))
 expect(await screen.findByText(/No se confirmó el cambio/)).toBeVisible()
 expect(sent.body).toMatchObject({expected_revision:0,mode:'allow_missing'})
 view.unmount();render(<CheckPolicyEditor projectId={101} policy={{revision:1,mode:'allow_missing'}}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Consultar recibo de la política'}))
 expect(await screen.findByText(/Política guardada para aceptaciones nuevas/)).toBeVisible()
 expect(api.sendCheckPolicy).toHaveBeenCalledTimes(1);expect(sessionStorage.length).toBe(0)
})

it('does not silently replace the observed revision and closes only a definite rejection',async()=>{
 const user=userEvent.setup();api.sendCheckPolicy.mockRejectedValue(new ApiError(409,'La política cambió'))
 const view=render(<CheckPolicyEditor projectId={101} policy={{revision:1,mode:'require_tests'}}/>,{wrapper:wrapper()})
 await user.click(screen.getByRole('button',{name:'Elegir política de pruebas'}))
 view.rerender(<CheckPolicyEditor projectId={101} policy={{revision:2,mode:'allow_missing'}}/>)
 await user.click(screen.getByRole('button',{name:'Guardar política'}))
 await screen.findByText(/La política cambió/)
 expect(api.sendCheckPolicy.mock.calls[0][0].body.expected_revision).toBe(1)
 await user.click(screen.getByRole('button',{name:'Cerrar decisión rechazada'}))
 await user.click(screen.getByRole('button',{name:'Elegir política de pruebas'}))
 expect(screen.getByText('Revisión consultada: 2. Guardar sólo cambia el requisito del proyecto.')).toBeVisible()
})

it('sends nothing when local persistence fails and respects read-only mode',async()=>{
 const user=userEvent.setup();const view=render(<CheckPolicyEditor projectId={101} policy={{revision:0,mode:null}} readOnly/>,{wrapper:wrapper()})
 expect(screen.getByRole('button',{name:'Elegir política de pruebas'})).toBeDisabled()
 view.rerender(<CheckPolicyEditor projectId={101} policy={{revision:0,mode:null}}/>)
 await user.click(screen.getByRole('button',{name:'Elegir política de pruebas'}))
 const denied=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('Storage refused')})
 try{await user.click(screen.getByRole('button',{name:'Guardar política'}));await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Storage refused'));expect(api.sendCheckPolicy).not.toHaveBeenCalled()}finally{denied.mockRestore()}
})

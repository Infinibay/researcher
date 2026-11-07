/** Exercise explicit budget changes, uncertain replies and project isolation; backend authority has separate integration tests. @module */
import {act,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {beforeEach,expect,it,vi} from 'vitest'
import {WorkBudget} from '../../src/components/tasks/WorkBudget'
import {ApiError} from '../../src/api/client'

const api=vi.hoisted(()=>({workBudget:vi.fn(),sendBudgetChange:vi.fn(),readBudgetReceipt:vi.fn()}))
vi.mock('../../src/api/history',async original=>({...await original<typeof import('../../src/api/history')>(),workBudget:api.workBudget}))
vi.mock('../../src/api/projectBudget',async original=>({...await original<typeof import('../../src/api/projectBudget')>(),sendBudgetChange:api.sendBudgetChange,readBudgetReceipt:api.readBudgetReceipt}))
const budget={project_id:1,policy:{revision:0,turn_limit:2,token_limit:200},used_turns:1,observed_tokens:null,unmeasured_dispatches:1,unsettled_dispatches:1,accounted_tokens:100,held_tokens:100,remaining_turns:1,remaining_tokens:100,overrun_tokens:0}
/** Keep query state scoped to this test while allowing explicit component remount. */
function wrapper(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});return function Provider({children}:{children:React.ReactNode}){return <QueryClientProvider client={client}>{children}</QueryClientProvider>}}
/** Return a receipt for exactly the submitted owner packet. */
function receipt(action:any){return {project_id:action.projectId,...action.body,revision:action.body.expected_revision+1,inference_started:false}}
beforeEach(()=>{sessionStorage.clear();vi.clearAllMocks();api.workBudget.mockImplementation(async(id:number)=>({...budget,project_id:id}))})

it('saves the original packet before send and recovers a lost response after reload without another write',async()=>{
 const user=userEvent.setup();let saved:any
 api.sendBudgetChange.mockImplementation(async action=>{saved=action;expect(sessionStorage.length).toBe(1);throw new TypeError('reply lost')})
 api.readBudgetReceipt.mockImplementation(async action=>receipt(action))
 const wrap=wrapper();const view=render(<WorkBudget projectId={1}/>,{wrapper:wrap})
 await user.click(await screen.findByRole('button',{name:'Revisar límites'}))
 const tokens=screen.getByLabelText('Límite total de tokens');await user.clear(tokens);await user.type(tokens,'500')
 await user.click(screen.getByRole('button',{name:'Guardar límites'}))
 expect(await screen.findByText(/No se confirmó el cambio/)).toBeVisible()
 expect(saved.body).toMatchObject({expected_revision:0,token_limit:500,turn_limit:2})
 view.unmount();render(<WorkBudget projectId={1}/>,{wrapper:wrap})
 await user.click(await screen.findByRole('button',{name:'Consultar recibo original'}))
 expect(await screen.findByText(/Límites guardados.*No se inició trabajo/)).toBeVisible()
 expect(api.sendBudgetChange).toHaveBeenCalledTimes(1);expect(sessionStorage.length).toBe(0)
})

it('keeps a stale edit explicit and requires a new observed revision before another decision',async()=>{
 const user=userEvent.setup();api.sendBudgetChange.mockRejectedValue(new ApiError(409,'El presupuesto cambió'))
 render(<WorkBudget projectId={1}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Revisar límites'}))
 await user.click(screen.getByRole('button',{name:'Guardar límites'}))
 expect(await screen.findByText(/El presupuesto cambió/)).toBeVisible()
 expect(screen.queryByRole('button',{name:'Guardar límites'})).toBeNull()
 api.workBudget.mockResolvedValue({...budget,policy:{...budget.policy,revision:2,token_limit:600}})
 await user.click(screen.getByRole('button',{name:'Cerrar decisión rechazada'}))
 await user.click(await screen.findByRole('button',{name:'Revisar límites'}))
 expect(screen.getByLabelText('Límite total de tokens')).toHaveValue(600)
 expect(api.sendBudgetChange).toHaveBeenCalledTimes(1)
})

it('does not present a late project A receipt as a change to project B',async()=>{
 let finish!:(v:unknown)=>void;let sent:any
 api.sendBudgetChange.mockImplementation(action=>{sent=action;return new Promise(resolve=>{finish=resolve})})
 const user=userEvent.setup();const view=render(<WorkBudget projectId={1}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Revisar límites'}));await user.click(screen.getByRole('button',{name:'Guardar límites'}))
 await waitFor(()=>expect(sent.projectId).toBe(1));view.rerender(<WorkBudget projectId={2}/>)
 await screen.findByRole('button',{name:'Revisar límites'})
 await act(async()=>finish(receipt(sent)))
 expect(screen.queryByText(/Límites guardados/)).toBeNull()
 expect(api.sendBudgetChange).toHaveBeenCalledTimes(1)
})

it('does not send a budget decision when browser persistence fails',async()=>{
 const user=userEvent.setup();render(<WorkBudget projectId={1}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Revisar límites'}))
 const denied=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('Storage refused')})
 try{await user.click(screen.getByRole('button',{name:'Guardar límites'}));expect(await screen.findByRole('alert')).toHaveTextContent('Storage refused');expect(api.sendBudgetChange).not.toHaveBeenCalled()}finally{denied.mockRestore()}
})

it('shows unknown local CPU separately and preserves local totals in the original recoverable decision',async()=>{
 api.workBudget.mockResolvedValue({...budget,auxiliary:{policy:{operation_limit:20,cpu_ms_limit:60000},used_operations:1,observed_cpu_ms:null,unknown_operations:1,pending_operations:1,accounted_cpu_ms:3000,held_cpu_ms:3000,remaining_operations:19,remaining_cpu_ms:57000,input_bytes:20}})
 api.sendBudgetChange.mockRejectedValue(new Error('Respuesta perdida'))
 const user=userEvent.setup();const view=render(<WorkBudget projectId={1}/>,{wrapper:wrapper()})
 expect(await screen.findByText('Documentos y búsqueda local')).toBeVisible()
 expect(screen.getByText(/Usuario y agentes comparten/)).toBeVisible()
 expect(screen.getByText(/1 cálculos sin medición/)).toBeVisible()
 await user.click(screen.getByRole('button',{name:'Revisar límites'}))
 await user.clear(screen.getByLabelText('Límite total de cálculos locales'));await user.type(screen.getByLabelText('Límite total de cálculos locales'),'30')
 await user.click(screen.getByRole('button',{name:'Guardar límites'}))
 await screen.findByText(/Respuesta perdida/)
 const original=api.sendBudgetChange.mock.calls[0][0]
 expect(original.body.auxiliary_operation_limit).toBe(30);expect(original.body.auxiliary_cpu_ms_limit).toBe(60000)
 view.unmount();api.readBudgetReceipt.mockImplementation(async action=>receipt(action))
 render(<WorkBudget projectId={1}/>,{wrapper:wrapper()})
 await user.click(await screen.findByRole('button',{name:'Consultar recibo original'}))
 expect(await screen.findByText(/Límites guardados/)).toBeVisible()
 expect(api.readBudgetReceipt.mock.calls[0][0]).toEqual(original);expect(api.sendBudgetChange).toHaveBeenCalledTimes(1)
})

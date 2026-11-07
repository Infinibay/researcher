/** Exercise owner pagination, uncertain budget measurements and project isolation. @module */
import {act, render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient, QueryClientProvider} from '@tanstack/react-query'
import {expect, it, vi} from 'vitest'
import {TaskRunHistory, RunAttempts} from '../../src/components/tasks/ExecutionHistory'
import {WorkBudget} from '../../src/components/tasks/WorkBudget'

const api = vi.hoisted(()=>({taskRunHistory:vi.fn(),runAttempts:vi.fn(),workBudget:vi.fn()}))
vi.mock('../../src/api/history',async importOriginal=>({...await importOriginal<typeof import('../../src/api/history')>(),...api}))
vi.mock('../../src/components/tasks/RunCommands',()=>({RunCommands:()=>null}))
vi.mock('../../src/components/tasks/RunInputRecord',()=>({RunInputRecord:()=>null}))

/** Keep each test's cache independent from previous project histories. */
function wrapper(){
 const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}})
 return function Provider({children}:{children:React.ReactNode}){return <QueryClientProvider client={client}>{children}</QueryClientProvider>}
}

it('opens older task runs and earlier attempts without replacing current control state',async()=>{
 api.taskRunHistory.mockImplementation(async(project:number,_task:number,before:string|null)=>({project_id:project,task_id:11,total:2,items:[{run_id:before?'older':'latest',project_id:project,task_id:11,status:'cancelled',context_version:1,prompt:before?'Solicitud anterior':'Solicitud reciente'}],next_before_seq:before?null:'2'}))
 api.runAttempts.mockResolvedValue({project_id:1,run_id:'older',total:1,items:[{seq:'1',attempt_id:'old-attempt',is_current:false,status:'finished',model:'old-model',model_selection:null,observed_tokens:null,dispatch_status:null,result:{summary:'Borrador anterior'}}],next_before_seq:null})
 const user=userEvent.setup()
 render(<TaskRunHistory projectId={1} taskId={11}/>,{wrapper:wrapper()})
 await user.click(screen.getByText('Historial de ejecuciones'))
 expect(await screen.findByText('Solicitud reciente')).toBeVisible()
 await user.click(screen.getByRole('button',{name:'Cargar ejecuciones anteriores'}))
 expect(await screen.findByText('Solicitud anterior')).toBeVisible()
 await user.click(within(screen.getByText('Solicitud anterior').closest('li')!).getByText('Intentos guardados'))
 expect(await screen.findByText('Borrador anterior')).toBeVisible()
 expect(screen.getByText('old-model')).toBeVisible()
 expect(screen.getByText('Tokens observados: No disponible')).toBeVisible()
 expect(screen.queryByText('Tokens observados: 0')).toBeNull()
})

it('keeps an attempt read failure distinct from an empty history',async()=>{
 api.runAttempts.mockRejectedValueOnce(new Error('Conexión interrumpida')).mockResolvedValueOnce({project_id:1,run_id:'r',total:0,items:[],next_before_seq:null})
 const user=userEvent.setup()
 render(<RunAttempts projectId={1} runId="r"/>,{wrapper:wrapper()})
 await user.click(screen.getByText('Intentos guardados'))
 expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron consultar los intentos')
 expect(screen.queryByText('Sin intentos registrados.')).toBeNull()
 await user.click(screen.getByRole('button',{name:'Volver a consultar intentos'}))
 expect(await screen.findByText('Sin intentos registrados.')).toBeVisible()
})

it('does not replace project B when a late history response from A arrives',async()=>{
 let resolveA!:(value:unknown)=>void
 const late=new Promise(resolve=>{resolveA=resolve})
 api.taskRunHistory.mockImplementation((project:number)=>project===1?late:Promise.resolve({project_id:2,task_id:22,total:1,items:[{run_id:'b',project_id:2,task_id:22,status:'cancelled',context_version:1,prompt:'Trabajo de B'}],next_before_seq:null}))
 const user=userEvent.setup()
 const view=render(<TaskRunHistory projectId={1} taskId={11}/>,{wrapper:wrapper()})
 await user.click(screen.getByText('Historial de ejecuciones'))
 await waitFor(()=>expect(api.taskRunHistory).toHaveBeenCalledWith(1,11,null))
 view.rerender(<TaskRunHistory projectId={2} taskId={22}/>)
 await user.click(screen.getByText('Historial de ejecuciones'))
 expect(await screen.findByText('Trabajo de B')).toBeVisible()
 await act(async()=>resolveA({project_id:1,task_id:11,total:1,items:[{run_id:'a',project_id:1,task_id:11,status:'cancelled',context_version:1,prompt:'Trabajo de A'}],next_before_seq:null}))
 expect(screen.queryByText('Trabajo de A')).toBeNull()
 expect(screen.getByText('Trabajo de B')).toBeVisible()
 view.rerender(<TaskRunHistory projectId={1} taskId={11}/>)
 await user.click(screen.getByText('Historial de ejecuciones'))
 expect(await screen.findByText('Trabajo de A')).toBeVisible()
 expect(screen.queryByText('Trabajo de B')).toBeNull()
})

it('explains reserved capacity without turning missing usage into zero or retaining a foreign project',async()=>{
 const pending={project_id:1,policy:{turn_limit:20,token_limit:1000},used_turns:1,observed_tokens:null,unmeasured_dispatches:1,unsettled_dispatches:1,accounted_tokens:100,held_tokens:100,remaining_turns:19,remaining_tokens:900,overrun_tokens:0}
 api.workBudget.mockImplementation(async(project:number)=>project===1?pending:{...pending,project_id:2,policy:null,observed_tokens:77,held_tokens:0})
 const view=render(<WorkBudget projectId={1}/>,{wrapper:wrapper()})
 expect(await screen.findByText('No disponible')).toBeVisible()
 expect(screen.getByText(/Cuota y coste de la suscripción/)).toBeVisible()
 expect(screen.getByText(/Se mantienen reservados/)).toHaveTextContent('100')
 view.rerender(<WorkBudget projectId={2}/>)
 await waitFor(()=>expect(screen.queryByText(/Se mantienen reservados/)).toBeNull())
 expect(await screen.findByText(/Todavía no se registró un límite/)).toBeVisible()
 expect(screen.queryByText('900')).toBeNull()
})


it('distinguishes retained preparation from model dispatch and observed tokens',async()=>{
 api.workBudget.mockResolvedValue({project_id:1,policy:{turn_limit:1,token_limit:100,revision:0},used_turns:1,preparation_only:1,observed_tokens:null,unmeasured_dispatches:0,unsettled_dispatches:0,accounted_tokens:100,held_tokens:100,remaining_turns:0,remaining_tokens:0,overrun_tokens:0})
 api.runAttempts.mockResolvedValue({project_id:1,run_id:'r',total:1,items:[{seq:'1',attempt_id:'a',is_current:true,status:'reconciling',model:null,model_selection:null,preparation_token_ceiling:100,observed_tokens:null,dispatch_status:null,result:null}],next_before_seq:null})
 const user=userEvent.setup()
 render(<><WorkBudget projectId={1}/><RunAttempts projectId={1} runId="r"/></>,{wrapper:wrapper()})
 expect(await screen.findByText(/1 preparaciones sin reserva de envío/)).toHaveTextContent('no es una medición')
 await user.click(screen.getByText('Intentos guardados'))
 expect(await screen.findByText(/Preparación reservada: 100/)).toHaveTextContent('No hay envío registrado')
 expect(screen.getByText('Tokens observados: No disponible')).toBeVisible()
})

/** Historical acceptance must not prevent an explicit request for reopened current requirements. @module */
import {render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {TaskRunWorkspace} from '../../src/components/tasks/TaskRunWorkspace'

const state=vi.hoisted(()=>({context:2,taskStatus:'pending',runStatus:'accepted',runContext:1}))
vi.mock('../../src/hooks/useRuntime',async()=>{
 const original=await vi.importActual<typeof import('../../src/hooks/useRuntime')>('../../src/hooks/useRuntime')
 return {...original,useTaskWorkspace:()=>({isPending:false,error:null,refetch:vi.fn(),data:{project_id:101,task_id:1001,context:{context_version:state.context,task:{title:'Exportar observaciones',description:'Mostrar entrada y CSV esperado.',type:'research',status:state.taskStatus},corrections:[],task_changes:[]},runtime:{configured:true,supported_task_types:['research'],owner_controlled_task_types:['research']},runs:[{run_id:'original-accepted',status:state.runStatus,context_version:state.runContext,prompt:'Describir la entrada.',execution_kind:'research',result:{summary:'Original accepted summary.'}}],repositories:[{id:11,name:'observaciones'}],questions:[],references:[],sources:[],reports:[]}})}
})
vi.mock('../../src/components/tasks/ResultDelivery',()=>({TaskResults:()=>null}))
vi.mock('../../src/components/tasks/RunCommands',()=>({RunCommands:()=>null}))
vi.mock('../../src/components/tasks/RunInputRecord',()=>({RunInputRecord:()=>null}))
vi.mock('../../src/components/tasks/ExecutionHistory',()=>({TaskRunHistory:()=>null}))
vi.mock('../../src/components/tasks/CodeDelivery',()=>({TaskCodeResults:()=>null}))
vi.mock('../../src/components/tasks/RemotePublications',()=>({TaskRemotePublications:()=>null}))
const clients:QueryClient[]=[]
/** Render real request controls while unrelated history readers remain outside this test's scope. */
async function form(){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}><TaskRunWorkspace projectId={101} taskId={1001}/></QueryClientProvider>);await userEvent.setup().type(screen.getByLabelText('Solicitud para esta tarea'),'Añade una fila CSV de ejemplo.');return screen.getByRole('button',{name:'Iniciar trabajo',exact:true})}
beforeEach(()=>{sessionStorage.clear();Object.assign(state,{context:2,taskStatus:'pending',runStatus:'accepted',runContext:1})})
afterEach(()=>{clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks()})
it('allows an explicit new request after acceptance under an older context without rewriting its result',async()=>{
 expect(await form()).toBeEnabled()
 expect(screen.getByText('Original accepted summary.')).toBeVisible()
 expect(screen.getByText(/Contexto vigente: 2 · resultado bajo contexto 1/)).toBeVisible()
})
it.each(['done','cancelled','failed'])('keeps a closed %s task unavailable despite a newer context',async status=>{state.taskStatus=status;expect(await form()).toBeDisabled()})
it('does not reopen a current accepted context',async()=>{state.runContext=2;expect(await form()).toBeDisabled()})
it.each(['running','queued','reconciling','cancelling','waiting_input','needs_review'])('does not bypass original %s work even if its context is older',async status=>{state.runStatus=status;expect(await form()).toBeDisabled()})

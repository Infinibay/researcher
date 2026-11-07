/** Preserve a saved explanation without presenting it as closure or owner acceptance. @module */
import {render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {expect,it,vi} from 'vitest'
import {TaskProjectPlan} from '../../src/components/tasks/ProjectPlanDelivery'
import type {RuntimeRun} from '../../src/api/runtime'

const api=vi.hoisted(()=>({projectPlanState:vi.fn()}))
vi.mock('../../src/api/projectPlans',async original=>({...await original<typeof import('../../src/api/projectPlans')>(),...api}))

it('shows the saved explanation after interruption and waits for confirmed eligibility before offering acceptance',async()=>{
 const packet={project_id:1,task_id:11,run_id:'r',context_version:1,snapshot:{project:{name:'Research',description:null},owner_request:'Compare options',instruction_origin:'owner_message',sources:{}},proposal:{proposal_sha256:'a'.repeat(64),draft:{title:'Compare before changing',rationale:'Read the current behavior.',assumptions:[],basis:[{source:'owner_request',quote:'Compare options'}],epics:[],tasks:[]},delivery:{version:1,explanation:'Primero comparamos las opciones. Puedes corregir la premisa antes de aceptar.'}},acceptance:null,acceptance_current:false,eligible:false,blocked_reason:'Closure unconfirmed'}
 api.projectPlanState.mockResolvedValueOnce(packet).mockResolvedValue({...packet,eligible:true,blocked_reason:''})
 const user=userEvent.setup(),client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}})
 render(<QueryClientProvider client={client}><TaskProjectPlan projectId={1} taskId={11} runs={[{run_id:'r',execution_kind:'research',status:'failed'} as RuntimeRun]}/></QueryClientProvider>)
 expect(await screen.findByText(packet.proposal.delivery.explanation)).toBeVisible()
 expect(screen.queryByRole('button',{name:'Aceptar plan y crear tareas pendientes'})).toBeNull()
 await user.click(screen.getByRole('button',{name:'Consultar propuesta guardada'}))
 expect(await screen.findByRole('button',{name:'Aceptar plan y crear tareas pendientes'})).toBeEnabled()
 expect(screen.queryByText(/Plan aceptado\./)).toBeNull()
})

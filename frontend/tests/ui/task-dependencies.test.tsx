/** A failed prerequisite read must remain unknown instead of rendering an apparently complete dependency map. @module */
import {render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,expect,it,vi} from 'vitest'
import {TasksPage} from '../../src/components/pages/TasksPage'

vi.mock('../../src/stores/project',()=>({useProjectStore:(select:(s:{activeProjectId:number})=>unknown)=>select({activeProjectId:1})}))
vi.mock('../../src/hooks/useTasks',()=>({useTasks:()=>({data:[{id:7,project_id:1,title:'Entrada',type:'research',status:'pending'},{id:8,project_id:1,title:'Salida',type:'research',status:'pending'}],isLoading:false,isSuccess:true,error:null}),useDeleteTask:()=>({error:null})}))
vi.mock('../../src/hooks/useEpics',()=>({useEpics:()=>({data:[]})}))
vi.mock('../../src/hooks/useMilestones',()=>({useMilestones:()=>({data:[]})}))
vi.mock('../../src/components/tasks/TaskInspector',()=>({TaskInspector:()=>null}))
vi.mock('../../src/components/tasks/TaskCreationForm',()=>({TaskCreationForm:()=>null}))
vi.mock('../../src/api/client',()=>({fetchApi:vi.fn(async()=>{throw new Error('Lectura interrumpida')})}))
afterEach(()=>vi.unstubAllGlobals())

it('keeps the graph unavailable when one original task dependency read fails',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({detail:'Lectura interrumpida'},{status:503})))
 const query=new QueryClient({defaultOptions:{queries:{retry:false}}})
 const user=userEvent.setup()
 render(<QueryClientProvider client={query}><MemoryRouter><TasksPage/></MemoryRouter></QueryClientProvider>)
 await user.click(screen.getByRole('button',{name:'Dependencias',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron consultar las dependencias')
 expect(screen.queryByRole('heading',{name:'Mapa de prerrequisitos'})).not.toBeInTheDocument()
 expect(screen.getByRole('button',{name:'Volver a consultar dependencias'})).toBeEnabled()
 query.clear()
})

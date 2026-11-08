/** Inspector read failures cannot become empty comments or editable empty prerequisite sets. @module */
import {render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,expect,it,vi} from 'vitest'
import {TaskInspector} from '../../src/components/tasks/TaskInspector'

vi.mock('../../src/stores/project',()=>({useProjectStore:(select:(s:{activeProjectId:number})=>unknown)=>select({activeProjectId:101})}))
vi.mock('../../src/components/tasks/TaskRunWorkspace',()=>({TaskRunWorkspace:()=>null}))
vi.mock('../../src/hooks/useTasks',()=>({
 useTask:()=>({data:{id:1,project_id:101,title:'Examinar observaciones',type:'research',status:'pending'},isLoading:false,error:null}),
 useTasks:()=>({data:[{id:1,project_id:101,title:'Examinar observaciones'},{id:2,project_id:101,title:'Comprobar columnas'}],isPending:false,isSuccess:true,error:null}),
 useTaskComments:()=>({data:[],isPending:false,isSuccess:false,error:new Error('comments unavailable'),refetch:vi.fn()}),
 useTaskDependencies:()=>({data:[],isPending:false,isSuccess:false,error:new Error('dependencies unavailable'),refetch:vi.fn()}),
 useAddTaskComment:()=>({isPending:false,error:null,mutate:vi.fn()}),
 useSetTaskDependencies:()=>({isPending:false,error:null,mutate:vi.fn()}),
 useUpdateTask:()=>({isPending:false,error:null,mutate:vi.fn()}),
}))
const clients:QueryClient[]=[]
/** Supply a real query cache for the inspector's disabled workspace subscription. */
function root(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});clients.push(client);return <QueryClientProvider client={client}><TaskInspector taskId={1} onClose={()=>{}}/></QueryClientProvider>}
afterEach(()=>clients.splice(0).forEach(client=>client.clear()))

it('does not claim no comments when the latest read failed over an earlier empty snapshot',async()=>{
 const user=userEvent.setup();render(root())
 await user.click(screen.getByRole('button',{name:/^Comentarios/}))
 expect(screen.getByRole('alert')).toHaveTextContent('No se pudieron consultar los comentarios')
 expect(screen.queryByText('No hay comentarios.',{exact:true})).not.toBeInTheDocument()
 expect(screen.getByRole('button',{name:'Volver a consultar comentarios'})).toBeEnabled()
})

it('does not claim no prerequisites or offer an editor based on failed reads',async()=>{
 const user=userEvent.setup();render(root())
 await user.click(screen.getByRole('button',{name:/^Dependencias/}))
 expect(screen.getByRole('alert')).toHaveTextContent('No se pudieron consultar las relaciones')
 expect(screen.queryByText('No hay dependencias.',{exact:true})).not.toBeInTheDocument()
 expect(screen.queryByRole('button',{name:/^Editar/})).not.toBeInTheDocument()
 expect(screen.getByRole('button',{name:'Volver a consultar relaciones'})).toBeEnabled()
})

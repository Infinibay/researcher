/** Cached empty lists cannot imply a successful current read after a conversation query fails. @module */
import {render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {expect,it,vi} from 'vitest'
import {ChatPage} from '../../src/components/pages/ChatPage'

vi.mock('../../src/stores/project',()=>({useProjectStore:(select:(state:{activeProjectId:number})=>unknown)=>select({activeProjectId:101})}))
vi.mock('../../src/hooks/useTasks',()=>({useTasks:()=>({data:[],isPending:false,isSuccess:false,error:new Error('task read failed'),refetch:vi.fn()})}))
vi.mock('../../src/hooks/useChat',()=>({useChatThreads:()=>({data:[],isSuccess:false,isPending:false,error:new Error('thread read failed'),refetch:vi.fn()}),useThreadMessages:()=>({data:undefined,isSuccess:false,isPending:false,error:null})}))
vi.mock('../../src/components/chat/QuestionInbox',()=>({QuestionInbox:()=>null}))
it('preserves task and thread failures without offering cached emptiness as the current state',()=>{
 render(<MemoryRouter initialEntries={['/chat?task=1001']}><ChatPage/></MemoryRouter>)
 expect(screen.getByText('No se pudieron recuperar las tareas.')).toBeVisible()
 expect(screen.queryByText('Crea una tarea en Tareas para empezar.')).toBeNull()
 expect(screen.queryByText('Todavía no hay hilos guardados.')).toBeNull()
 expect(screen.queryByText('La tarea indicada no está disponible en este proyecto.')).toBeNull()
})

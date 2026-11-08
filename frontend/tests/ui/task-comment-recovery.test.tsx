/** Real task-note forms retain original scoped packets through lost receipts, remounts and storage failure. @module */
import {render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {TaskCommentsPanel} from '../../src/components/tasks/TaskCommentsPanel'

const clients:QueryClient[]=[]
/** Exercise real hooks, request serialization and storage with only the HTTP boundary controlled. */
function form(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}});clients.push(client);return <QueryClientProvider client={client}><TaskCommentsPanel projectId={101} taskId={7}/></QueryClientProvider>}
beforeEach(()=>sessionStorage.clear())
afterEach(()=>{clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals()})
it('recovers the same task note after a lost reply and remount even when the note already appears in history',async()=>{
 const sent:Record<string,unknown>[]=[],user=userEvent.setup();let receipt:Record<string,unknown>|null=null
 vi.stubGlobal('fetch',vi.fn(async(url,options)=>{expect(url).toBe('/api/tasks/7/comments');if(options?.method!=='POST')return Response.json(receipt?[receipt]:[]);const body=JSON.parse(String(options.body));sent.push(body);receipt??={id:9,task_id:7,created_at:'2026-11-08T10:00:00Z',authorizes_work:false,...body};if(sent.length===1)throw new TypeError('comment reply lost');return Response.json(receipt,{status:201})}))
 const first=render(form());await screen.findByText('No hay comentarios.',{exact:true})
 await user.type(screen.getByLabelText('Tu comentario'),'Entrada ilustrativa, todavía no comprobada.')
 await user.selectOptions(screen.getByLabelText('Tipo de nota'),'approval')
 await user.click(screen.getByRole('button',{name:'Guardar comentario',exact:true}))
 await screen.findByRole('alert');first.unmount();render(form())
 expect(screen.getByLabelText('Tu comentario')).toHaveValue('Entrada ilustrativa, todavía no comprobada.')
 expect(screen.getByLabelText('Tipo de nota')).toHaveValue('approval')
 await user.click(screen.getByRole('button',{name:'Reenviar el mismo comentario',exact:true}))
 await waitFor(()=>expect(screen.getByLabelText('Tu comentario')).toHaveValue(''))
 expect(sent).toHaveLength(2);expect(sent[1]).toEqual(sent[0]);expect(sent[0].project_id).toBe(101);expect(typeof sent[0].operation_key).toBe('string')
 expect(screen.getByRole('status')).toHaveTextContent('No se inició trabajo')
})
it('does not send a task comment when persisting its original packet fails',async()=>{
 const user=userEvent.setup(),posts:unknown[]=[]
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{if(options?.method==='POST'){posts.push(options.body);return Response.json({id:9})}return Response.json([])}))
 render(form());await screen.findByText('No hay comentarios.',{exact:true})
 await user.type(screen.getByLabelText('Tu comentario'),'Conservar antes de enviar.')
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('storage unavailable')})
 await user.click(screen.getByRole('button',{name:'Guardar comentario',exact:true}))
 await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('no se envió'))
 expect(posts).toEqual([]);expect(screen.getByLabelText('Tu comentario')).toHaveValue('Conservar antes de enviar.')
})

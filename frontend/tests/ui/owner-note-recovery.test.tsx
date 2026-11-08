/** Explanatory notes preserve their original thread/key through uncertain replies and never become native instructions. @module */
import {render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {OwnerNoteForm} from '../../src/components/chat/OwnerNoteForm'

const clients:QueryClient[]=[]
/** Keep actual HTTP mutation handling under an isolated observer per rendered form. */
function form(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}});clients.push(client);return <QueryClientProvider client={client}><OwnerNoteForm projectId={101} threadId="original-thread"/></QueryClientProvider>}
beforeEach(()=>sessionStorage.clear())
afterEach(()=>{clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals()})
it('recovers only the exact note from its original thread after reload and verifies its receipt',async()=>{
 const sent:Record<string,unknown>[]=[],user=userEvent.setup()
 vi.stubGlobal('fetch',vi.fn(async(url,options)=>{expect(url).toBe('/api/chat/101');const body=JSON.parse(String(options.body));sent.push(body);if(sent.length===1)throw new TypeError('note reply lost');return Response.json({id:7,project_id:101,from_agent:'user',conversation_type:'user_to_agent',delivery:'recorded',...body})}))
 const first=render(form())
 await user.type(screen.getByLabelText('Nota para este hilo'),'La muestra de ejemplo todavía no se ha medido.')
 await user.click(screen.getByRole('button',{name:'Guardar nota',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('note reply lost')
 first.unmount();render(form())
 expect(screen.getByLabelText('Nota para este hilo')).toHaveValue('La muestra de ejemplo todavía no se ha medido.')
 await user.click(screen.getByRole('button',{name:'Reenviar la misma nota',exact:true}))
 await waitFor(()=>expect(sent).toHaveLength(2))
 expect(sent[1]).toEqual(sent[0]);expect(sent[1].thread_id).toBe('original-thread')
 await waitFor(()=>expect(screen.getByLabelText('Nota para este hilo')).toHaveValue(''))
})

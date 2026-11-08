/** Answers must retain exact identity after reload even when the question already appears answered. @module */
import {render,screen,within,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {QuestionCard} from '../../src/components/chat/QuestionCard'
import type {RuntimeQuestion} from '../../src/api/runtime'

const clients:QueryClient[]=[]
const original:RuntimeQuestion={request_id:17,run_id:'original-run',context_version:3,status:'pending',answers:null,answer_context_version:null,ready_for_answer:true,questions:[{id:'unit',question:'¿Qué unidad?',why_needed:'Para interpretar la entrada.',example:'',options:[{id:'mass_kg',label:'Kilogramos'},{id:'volume_l',label:'Litros'}]}]}
/** Keep real mutation transport and React Query while isolating each render's cache. */
function form(question=original){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}});clients.push(client);return <QueryClientProvider client={client}><QuestionCard projectId={101} taskId={1001} question={question}/></QueryClientProvider>}
beforeEach(()=>sessionStorage.clear())
afterEach(()=>{clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals()})
it('recovers an original unconfirmed answer after remount with an already answered historical question',async()=>{
 const sent:unknown[]=[],user=userEvent.setup()
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{sent.push(JSON.parse(String(options.body)));if(sent.length===1)throw new TypeError('answer reply lost');return Response.json({context_version:4,application:'recorded_for_next_run',inference_started:false})}))
 const first=render(form())
 await user.click(screen.getByRole('button',{name:'Kilogramos',exact:true}))
 await user.click(screen.getByRole('button',{name:'Guardar respuestas',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('answer reply lost')
 first.unmount()
 render(form({...original,status:'responded',answers:{unit:{option_id:'mass_kg'}},answer_context_version:4,ready_for_answer:false}))
 await user.click(screen.getByRole('button',{name:'Reenviar las mismas respuestas',exact:true}))
 await waitFor(()=>expect(sent).toHaveLength(2))
 expect(sent[1]).toEqual(sent[0])
 expect(sent[1]).toMatchObject({expected_version:3,answers:{unit:{option_id:'mass_kg'}}})
 await waitFor(()=>expect(screen.queryByRole('button',{name:'Reenviar las mismas respuestas',exact:true})).toBeNull())
})
it('does not send when its original answer cannot be stored',async()=>{
 const transport=vi.fn(),user=userEvent.setup();vi.stubGlobal('fetch',transport)
 render(form())
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('storage unavailable')})
 await user.type(within(screen.getByRole('group',{name:'¿Qué unidad?'})).getByRole('textbox'),'Gramos')
 await user.click(screen.getByRole('button',{name:'Guardar respuestas',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('storage unavailable')
 expect(transport).not.toHaveBeenCalled()
})

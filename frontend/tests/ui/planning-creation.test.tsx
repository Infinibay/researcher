/** Actual form/mutation lifecycles preserve original owner intents across uncertain, foreign and late replies. @module */
import {act,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {PlanningCreateForm} from '../../src/components/planning/PlanningCreateForm'

/** Provide real mutation behavior while controlling only the network response. */
function root(project:number,onCreated:(id:number)=>void,client:QueryClient,kind:'group'|'milestone'='group',epicId=0){return <QueryClientProvider client={client}><PlanningCreateForm key={`${project}:${kind}:${epicId}`} kind={kind} projectId={project} epicId={epicId} onCreated={onCreated} onCancel={()=>{}}/></QueryClientProvider>}
/** Keep every test isolated without mutation retries or unrelated active queries. */
function queryClient(){return new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}})}

beforeEach(()=>{sessionStorage.clear()})
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})

it.each(['group','milestone'] as const)('recovers the identical original %s after a lost response and a new mount',async kind=>{
 const sent:unknown[]=[],done=vi.fn(),user=userEvent.setup()
 const epic=kind==='group'?0:12,label=kind==='group'?'Nombre del grupo':'Nombre del hito',button=kind==='group'?'Crear grupo':'Guardar hito'
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{const body=JSON.parse(String(options.body));sent.push(body);if(sent.length===1)throw new TypeError('lost reply');return Response.json({id:41,project_id:1,...body})}))
 const first=render(root(1,done,queryClient(),kind,epic))
 await user.type(screen.getByLabelText(label),'Mediciones')
 await user.click(screen.getByRole('button',{name:button,exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('lost reply')
 expect(screen.getByLabelText(label)).toBeDisabled()
 first.unmount()
 render(root(1,done,queryClient(),kind,epic))
 expect(screen.getByLabelText(label)).toHaveValue('Mediciones')
 await user.click(screen.getByRole('button',{name:'Recuperar la misma creación'}))
 await waitFor(()=>expect(done).toHaveBeenCalledWith(41))
 expect(sent).toHaveLength(2)
 expect(sent[0]).toEqual(sent[1])
 expect(sessionStorage.getItem(`researcher:planning-create:v1:1:${kind}:${epic}`)).toBeNull()
})

it('does not send a creation when its original intent cannot be saved',async()=>{
 const fetch=vi.fn(),user=userEvent.setup();vi.stubGlobal('fetch',fetch)
 render(root(1,vi.fn(),queryClient()))
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('storage blocked')})
 await user.type(screen.getByLabelText('Nombre del grupo'),'Conservar borrador')
 await user.click(screen.getByRole('button',{name:'Crear grupo',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('storage blocked')
 expect(screen.getByRole('alert')).toHaveTextContent('no se envió una solicitud nueva')
 expect(screen.getByRole('alert')).not.toHaveTextContent('original se conserva')
 expect(fetch).not.toHaveBeenCalled()
 expect(screen.getByLabelText('Nombre del grupo')).toHaveValue('Conservar borrador')
})

it('does not adopt a foreign project reply even when HTTP succeeds',async()=>{
 const done=vi.fn(),user=userEvent.setup();vi.stubGlobal('fetch',vi.fn(async()=>Response.json({id:42,project_id:2})))
 render(root(1,done,queryClient()))
 await user.type(screen.getByLabelText('Nombre del grupo'),'Proyecto original')
 await user.click(screen.getByRole('button',{name:'Crear grupo',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('no corresponde')
 expect(done).not.toHaveBeenCalled()
 expect(sessionStorage.getItem('researcher:planning-create:v1:1:group:0')).not.toBeNull()
})

it('requires the original request identity even for a reply in the same project',async()=>{
 const done=vi.fn(),user=userEvent.setup();vi.stubGlobal('fetch',vi.fn(async()=>Response.json({id:42,project_id:1,operation_key:'another-request'})))
 render(root(1,done,queryClient()))
 await user.type(screen.getByLabelText('Nombre del grupo'),'Solicitud original')
 await user.click(screen.getByRole('button',{name:'Crear grupo',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('no corresponde')
 expect(done).not.toHaveBeenCalled()
 expect(sessionStorage.getItem('researcher:planning-create:v1:1:group:0')).not.toBeNull()
})

it('keeps a new A visit when the original A reply arrives after A→B→A',async()=>{
 let finish!:(response:Response)=>void
 const sent:unknown[]=[],done=vi.fn(),user=userEvent.setup(),client=queryClient()
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{const body=JSON.parse(String(options.body));sent.push(body);if(sent.length===1)return new Promise<Response>(resolve=>{finish=resolve});return Response.json({id:41,project_id:1,...body})}))
 const view=render(root(1,done,client))
 await user.type(screen.getByLabelText('Nombre del grupo'),'Original A')
 await user.click(screen.getByRole('button',{name:'Crear grupo',exact:true}))
 await waitFor(()=>expect(sent).toHaveLength(1))
 view.rerender(root(2,done,client));expect(screen.getByLabelText('Nombre del grupo')).toHaveValue('')
 view.rerender(root(1,done,client));expect(screen.getByLabelText('Nombre del grupo')).toHaveValue('Original A')
 await act(async()=>finish(Response.json({id:41,project_id:1,...sent[0] as object})))
 expect(done).not.toHaveBeenCalled()
 await user.click(screen.getByRole('button',{name:'Recuperar la misma creación'}))
 await waitFor(()=>expect(done).toHaveBeenCalledTimes(1))
 expect(sent[0]).toEqual(sent[1])
})

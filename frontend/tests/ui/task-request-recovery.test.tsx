/** Reload must preserve original execution requests and context corrections after an uncertain delivery. @module */
import {render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {TaskRunWorkspace} from '../../src/components/tasks/TaskRunWorkspace'

const state=vi.hoisted(()=>({version:1}))
vi.mock('../../src/hooks/useRuntime',async()=>{
 const original=await vi.importActual<typeof import('../../src/hooks/useRuntime')>('../../src/hooks/useRuntime')
 return {...original,useTaskWorkspace:()=>({isPending:false,error:null,refetch:vi.fn(),data:{project_id:101,task_id:1001,context:{context_version:state.version,task:{title:'Exportar observaciones',description:'Comprobar entrada y salida.',type:'research',status:'pending'},corrections:[],task_changes:[]},runtime:{configured:true,supported_task_types:['research'],owner_controlled_task_types:['research'],model:'synthetic-never-launched'},runs:[],repositories:[{id:11,name:'observaciones',default_branch:'main'}],questions:[],references:[],sources:[],reports:[]}})}
})

const clients:QueryClient[]=[]
/** Keep mutation transport real while isolating unrelated workspace reads and polling. */
function root(){const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}});clients.push(client);return <QueryClientProvider client={client}><TaskRunWorkspace projectId={101} taskId={1001}/></QueryClientProvider>}
beforeEach(()=>{sessionStorage.clear();state.version=1})
afterEach(()=>{clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals()})

it('recovers the exact instruction after lost reply and remount even when the observed context advanced',async()=>{
 const sent:Record<string,unknown>[]=[],user=userEvent.setup()
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{const body=JSON.parse(String(options.body));sent.push(body);if(sent.length===1){state.version=2;throw new TypeError('instruction reply lost')}return Response.json({run:{run_id:'original-run',project_id:101,task_id:1001,context_version:body.context_version,operation_key:body.operation_key,prompt:body.message,conversation_thread_id:body.thread_id,repository_id:11},message:{id:7,thread_id:body.thread_id}})}))
 const first=render(root())
 await user.type(screen.getByLabelText('Solicitud para esta tarea'),'Comprobar una observación antes de exportar el CSV.')
 await user.click(screen.getByRole('button',{name:'Iniciar trabajo',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('instruction reply lost')
 first.unmount();render(root())
 expect(screen.getByLabelText('Solicitud para esta tarea')).toHaveValue('Comprobar una observación antes de exportar el CSV.')
 await user.click(screen.getByRole('button',{name:'Reenviar la misma solicitud',exact:true}))
 await waitFor(()=>expect(sent).toHaveLength(2))
 expect(sent[1]).toEqual(sent[0]);expect(sent[1].context_version).toBe(1)
 await waitFor(()=>expect(screen.getByLabelText('Solicitud para esta tarea')).toHaveValue(''))
})

it('recovers the exact original correction instead of using the newly observed context version',async()=>{
 const sent:Record<string,unknown>[]=[],user=userEvent.setup()
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{const body=JSON.parse(String(options.body));sent.push(body);if(sent.length===1){state.version=2;throw new TypeError('correction reply lost')}return Response.json({context_version:2,application:'recorded_for_next_run',inference_started:false})}))
 const first=render(root())
 await user.click(screen.getByText('Corregir el contexto',{exact:true}))
 await user.type(screen.getByLabelText('Qué cambia'),'La entrada real usa measurement, no value.')
 await user.click(screen.getByRole('button',{name:'Guardar corrección',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('correction reply lost')
 first.unmount();render(root())
 await user.click(screen.getByText('Corregir el contexto',{exact:true}))
 expect(screen.getByLabelText('Qué cambia')).toHaveValue('La entrada real usa measurement, no value.')
 await user.click(screen.getByRole('button',{name:'Reenviar la misma corrección',exact:true}))
 await waitFor(()=>expect(sent).toHaveLength(2))
 expect(sent[1]).toEqual(sent[0]);expect(sent[1].expected_version).toBe(1)
 await waitFor(()=>expect(screen.getByLabelText('Qué cambia')).toHaveValue(''))
})

it('does not deliver an instruction when its original copy cannot be saved',async()=>{
 const user=userEvent.setup(),transport=vi.fn();vi.stubGlobal('fetch',transport)
 render(root())
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('local storage blocked')})
 await user.type(screen.getByLabelText('Solicitud para esta tarea'),'Comprobar la entrada.')
 await user.click(screen.getByRole('button',{name:'Iniciar trabajo',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('local storage blocked')
 expect(screen.getByRole('alert')).toHaveTextContent('No se envió una solicitud nueva')
 expect(transport).not.toHaveBeenCalled()
})

it('does not acknowledge a successful reply belonging to another project',async()=>{
 const user=userEvent.setup()
 vi.stubGlobal('fetch',vi.fn(async(_url,options)=>{const body=JSON.parse(String(options.body));return Response.json({run:{run_id:'foreign',project_id:202,task_id:1001,context_version:body.context_version,operation_key:body.operation_key,prompt:body.message,conversation_thread_id:body.thread_id,repository_id:11},message:{id:7,thread_id:body.thread_id}})}))
 render(root())
 await user.type(screen.getByLabelText('Solicitud para esta tarea'),'Conservar esta intención.')
 await user.click(screen.getByRole('button',{name:'Iniciar trabajo',exact:true}))
 expect(await screen.findByRole('alert')).toHaveTextContent('no corresponde a la solicitud original')
 expect(sessionStorage.getItem('researcher:task-instruction:v1:101:1001')).not.toBeNull()
 expect(screen.getByLabelText('Solicitud para esta tarea')).toHaveValue('Conservar esta intención.')
})

it('blocks fresh work when a saved packet is corrupt instead of discarding it',async()=>{
 const transport=vi.fn();vi.stubGlobal('fetch',transport)
 sessionStorage.setItem('researcher:task-instruction:v1:101:1001','{broken')
 render(root())
 expect(screen.getByRole('alert')).toHaveTextContent('No se pudo recuperar la solicitud original')
 expect(screen.getByRole('button',{name:'Iniciar trabajo',exact:true})).toBeDisabled()
 expect(sessionStorage.getItem('researcher:task-instruction:v1:101:1001')).toBe('{broken')
 expect(transport).not.toHaveBeenCalled()
})

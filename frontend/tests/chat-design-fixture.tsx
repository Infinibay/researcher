import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatPage } from '../src/components/pages/ChatPage'
import { useProjectStore } from '../src/stores/project'

export function renderConversation({ failure = false, empty = false, foreignTask = false, historyFailure = false } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false, staleTime: Infinity, gcTime: Infinity } } })
  const tasks = [{id:24,project_id:101,title:'Comprobar <reintentos>',type:'research',status:'in_progress'}, {id:25,project_id:101,title:'Revisar fuentes',type:'research',status:'in_progress'}]
  if (failure) client.getQueryCache().build(client, {queryKey:['tasks',101,undefined]}).setState({status:'error',error:new Error('No disponible')})
  else client.setQueryData(['tasks',101,undefined], empty ? [] : tasks)
  const question = {request_id:501,kind:'native',title:'Carpeta',body:'¿Qué carpeta revisar?',task_id:24,task_title:tasks[0].title,run_id:'run24',context_version:2,current_context_version:2,ready_for_answer:true,thread_id:'thread24',questions:[{id:'folder',question:'¿Qué carpeta revisar?',why_needed:'Para limitar la revisión',example:'Elegir cliente sólo revisa esa carpeta.',options:['Cliente','Servidor']}]}
  client.setQueryData(['question-inbox',101], {pages:[{items: empty ? [] : [question,{...question,request_id:502,task_id:25,task_title:tasks[1].title,run_id:'run25',thread_id:'thread25'}],total_pending:empty ? 0 : 2,next_after_id:null}],pageParams:[0]})
  client.setQueryData(['task-workspace',101,24], {
    context:{task:tasks[0],context_version:2,corrections:[],task_changes:[]},
    runtime:{configured:true,supported_task_types:['research'],model:'fixture-model'},
    runs:[{run_id:'run24',project_id:101,task_id:24,conversation_thread_id:'thread24',status:'waiting_input',context_version:2,model:'fixture-model',prompt:'Comprueba los reintentos.',result:null,fence:2,repository_id:11,repository_name:'alpha',issue:null}],
    questions:[{...question,status:'pending',answers:null,answer_context_version:null}], repositories:[],references:[],sources:[],reports:[],
  })
  const messages=[{id:11,project_id:101,task_id:24,thread_id:'thread24',from_agent:'user',message:'Comprueba los reintentos.',runtime_run_id:'run24',context_version:2,delivery:'instruction_admitted'}, {id:12,project_id:101,task_id:24,thread_id:'thread24',from_agent:'researcher',message:'Hipótesis: falta comprobar el servidor.',runtime_run_id:'earlier-run',runtime_status:'superseded',context_version:1,delivery:'proposal'}]
  if (historyFailure) client.getQueryCache().build(client,{queryKey:['thread-messages',101,'thread24']}).setState({status:'error',error:new Error('No se pudo leer el hilo')})
  else client.setQueryData(['thread-messages',101,'thread24'],messages)
  client.setQueryData(['chat-threads',101],[])
  client.setQueryData(['agents',101],{agents:[]})
  client.setQueryData(['chat',101,50],[])
  client.setQueryData(['user-requests',101],{requests:[],total:0})
  const initial = useProjectStore.getInitialState()
  const previousProject = initial.activeProjectId
  initial.activeProjectId = 101
  try {
    return renderToStaticMarkup(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/chat?task=${foreignTask ? 99 : 24}`]}><ChatPage /></MemoryRouter></QueryClientProvider>)
  } finally {
    initial.activeProjectId = previousProject
    client.clear()
  }
}

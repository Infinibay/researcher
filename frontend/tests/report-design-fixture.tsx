/** Server-rendered report/task fixtures with isolated query caches and project state. @module */

import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReportsPage } from '../src/components/pages/ReportsPage'
import { useProjectStore } from '../src/stores/project'

/** Render saved content, source errors and project mismatch without HTTP or inference. */
export function renderReport({ detailFailure=false, evidenceFailure=false, legacy=false, noProject=false, wrongProject=false, ownerAccepted=false, changedBody=false }={}) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false,staleTime:Infinity,gcTime:Infinity}}})
 const initial=useProjectStore.getInitialState()
 const previous=initial.activeProjectId
 initial.activeProjectId=noProject?null:101
 const artifact={id:9,project_id:101,task_id:24,type:legacy?'code':'report',file_path:'reports/9.md',title:'Informe <guardado>',research_status:legacy?null:'draft',created_at:'2026-11-01 17:39:00',content:'# Informe <guardado>\n\nContenido original, sin aceptar.',owner_acceptance:ownerAccepted?{run_id:'original-author-run',task_id:24,context_version:3,accepted_at:1793550000,report_sha256:'c'.repeat(64),validity:'not_rechecked',matches_current_content:!changedBody}:null}
 client.setQueryData(['artifacts',101,undefined],[artifact])
 client.setQueryData(['artifacts',101,{q:''}],{pages:[[artifact]],pageParams:[0]})
 if(detailFailure)client.getQueryCache().build(client,{queryKey:['artifact',101,9]}).setState({status:'error',error:new Error('Fixture detail unavailable')})
 else client.setQueryData(['artifact',101,9],artifact)
 if(evidenceFailure)client.getQueryCache().build(client,{queryKey:['artifact-evidence',101,9]}).setState({status:'error',error:new Error('Fixture evidence unavailable')})
 else client.setQueryData(['artifact-evidence',101,9],{pages:[{artifact_id:9,project_id:101,content_sha256:'a'.repeat(64),offset:0,next_offset:null,total_evidence:1,evidence:[{finding_id:7,source_id:12,quote:'<img src=x onerror=alert(1)> exact quote',kind:'attachment',locator:'reference:8',title:'policy.txt',sha256:'b'.repeat(64),captured_at:1793550000,finding_status:'provisional'}]}],pageParams:[0]})
 try { return renderToStaticMarkup(<MemoryRouter initialEntries={[`/reports?project=${wrongProject?202:101}&artifact=9`]}><QueryClientProvider client={client}><ReportsPage /></QueryClientProvider></MemoryRouter>)
 } finally { initial.activeProjectId=previous;client.clear() }
}

/** Render a report deep link into the task inspector, including foreign-cache rejection. */
export async function renderTaskLink({ foreignProject=false, foreignTask=false }={}) {
 const {TasksPage}=await import('../src/components/pages/TasksPage')
 const client=new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false,staleTime:Infinity,gcTime:Infinity}}})
 const initial=useProjectStore.getInitialState(), previous=initial.activeProjectId
 initial.activeProjectId=101
 const task={id:24,project_id:foreignTask?202:101,type:'research',status:'in_progress',title:foreignTask?'OTHER PROJECT SECRET':'Tarea del informe'}
 client.setQueryData(['tasks',101,{}],foreignTask?[]:[task])
 client.setQueryData(['task',24],task)
 client.setQueryData(['task',24,101],task)
 client.setQueryData(['task-comments',24],[])
 client.setQueryData(['task-dependencies',24],[])
 client.setQueryData(['task-workspace',101,24],{context:{task,context_version:1,corrections:[],task_changes:[]},runtime:{configured:false,supported_task_types:['research'],model:null},runs:[],repositories:[],questions:[],references:[],sources:[],reports:[]})
 try{return renderToStaticMarkup(<MemoryRouter initialEntries={[`/tasks?project=${foreignProject?202:101}&task=24&fromArtifact=9`]}><QueryClientProvider client={client}><TasksPage /></QueryClientProvider></MemoryRouter>)}
 finally{initial.activeProjectId=previous;client.clear()}
}

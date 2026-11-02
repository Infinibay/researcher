/** Server rendering of the actual result workbench with explicit evidence states. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ResultDelivery } from '../src/components/tasks/ResultDelivery'

/** Supply actual UI data; missing and stale records never become successful decisions. */
export function renderResult(state = 'ready') {
 const client = new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity,gcTime:Infinity}}})
 const current = state === 'stale' ? false : state === 'unknown' ? null : true
 client.setQueryData(['run-result',101,'author-run'],{
  project_id:101,task_id:24,run_id:'author-run',candidate:state==='missing'?null:{candidate_id:7,candidate_sha256:'a'.repeat(64),kind:'research_reports',scope:{context_version:3},summary:'El texto indica 137 unidades.',limitations:['La medición no se repitió.'],reports:[{artifact_id:9,title:'Informe <documental>',report_type:'research',content_sha256:'c'.repeat(64),finding_ids:[5]}],finding_ids:[5],scientific_confidence:null},
  candidate_current:current,eligible:state==='ready',reason:state==='missing'?'no_explicit_delivery':state==='stale'?'candidate_dependencies_changed':null,
  reviews:{scope:'referenced_findings_only_not_whole_report_validation',items:[],issues:[{finding_id:5,reason:'no_independent_review'}],sha256:'b'.repeat(64)},review_sha256:'b'.repeat(64),review_issues:[{finding_id:5,reason:'no_independent_review'}],requires_acknowledgement:true,active_work:[],
  acceptance:state==='accepted'?{acceptance_id:12,task_accepted:true,accepted_at:1793600000,owner_note:'Uso documental.',acknowledged_limits:true}:null,acceptance_current:state==='accepted',
 })
 const html=renderToStaticMarkup(<QueryClientProvider client={client}><ResultDelivery projectId={101} taskId={24} runId="author-run" contextVersion={3}/></QueryClientProvider>)
 client.clear()
 return html
}

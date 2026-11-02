/** Render the actual selected Findings reader using isolated scoped cache data. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FindingsPage } from '../src/components/pages/FindingsPage'
import { useProjectStore } from '../src/stores/project'

/** Seed evidence, unknown/legacy assessments and failures without dispatching inference. */
export function renderFindings({noProject=false,foreign=false,poisoned=false,legacy=false,indexFailure=false,detailFailure=false,empty=false,unsafe=false}={}) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false,staleTime:Infinity,gcTime:Infinity}}})
 const initial=useProjectStore.getInitialState(),previous=initial.activeProjectId;initial.activeProjectId=noProject?null:101
 const filters={query:'',finding_type:'',status:'',min_confidence:null}
 const item={id:7,project_id:poisoned?202:101,task_id:1001,topic:poisoned?'FOREIGN SECRET':'Convención de tasas',agent_id:'researcher',created_at:null,status:legacy?'active':'provisional',finding_type:'observation',confidence:legacy?.9:null,scientific_confidence:null,review_status:legacy?'unverified_legacy':'not_recorded',validation_method:legacy?'Agent said validated':null,reproducibility_score:null,confidence_origin:legacy?'stored_declaration':'unknown',content_chars:35,content_excerpt:'La fuente explica una convención.',evidence_count:1}
 const citation={finding_id:7,source_id:3,quote:'Tax rates are fractions.',quote_chars:24,quote_offset:0,quote_truncated:false,kind:'attachment',locator:'reference:3',title:'policy.txt',sha256:'a'.repeat(64),captured_at:1,quote_is_exact:true,source_unavailable:false,finding_status:item.status}
 const detail={...item,content:unsafe?'<script>alert(1)</script>\n\n[unsafe](javascript:alert(1))':'# Convención de tasas\n\nLa fuente explica una convención.',offset:0,total_chars:35,next_offset:null,evidence:[citation],total_evidence:1,evidence_offset:0,next_evidence_offset:null}
 client.setQueryData(['project',101],{id:101,name:'Atlas'})
 const key=['finding-registry','index',101,filters]
 if(indexFailure)client.getQueryCache().build(client,{queryKey:key}).setState({status:'error',error:new Error('Index failed')})
 else client.setQueryData(key,{pages:[{project_id:poisoned?202:101,items:empty?[]:[item],next_after_id:null,total_matching:empty?0:1}],pageParams:[0]})
 const detailKey=['finding-registry','detail',101,7,0]
 if(detailFailure)client.getQueryCache().build(client,{queryKey:detailKey}).setState({status:'error',error:new Error('Detail failed')})
 else client.setQueryData(detailKey,detail)
 const evidenceKey=['finding-registry','evidence',101,7]
 client.setQueryData(evidenceKey,{pages:[{project_id:poisoned?202:101,finding_id:7,evidence:[citation],total_evidence:1,next_evidence_offset:null,evidence_offset:0}],pageParams:[0]})
 const url=empty||indexFailure?'/findings':`/findings?project=${foreign?202:101}&finding=7`
 try{return renderToStaticMarkup(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={client}><FindingsPage /></QueryClientProvider></MemoryRouter>)}
 finally{initial.activeProjectId=previous;client.clear()}
}

export * as findingModel from '../src/components/findings/presentation'

/** Render the actual selected Findings reader using isolated scoped cache data. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FindingsPage } from '../src/components/pages/FindingsPage'
import { useProjectStore } from '../src/stores/project'

/** Seed evidence, unknown/legacy assessments and failures without dispatching inference. */
export function renderFindings({noProject=false,foreign=false,poisoned=false,legacy=false,indexFailure=false,detailFailure=false,empty=false,unsafe=false,reviewed=false,staleReview=false,reviewFailure=false,foreignReview=false}={}) {
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
 const reviewItem={request_id:17,run_id:'review-run',subject_sha256:'b'.repeat(64),context_version:1,created_at:1,status:'needs_review',reviewer_actor_id:'research-reviewer',decision_id:23,verdict:'supported',reviewer_attempt_id:'review-attempt',subject_current:!staleReview,currentness_reason:staleReview?'review_subject_changed':null,operation_key:'fixture-review'}
 const reviewState={project_id:foreignReview?202:101,task_id:1001,finding_id:7,context_version:1,subject_sha256:'b'.repeat(64),reviewable:!legacy,reason:legacy?'author_origin_unknown':null,author:legacy?null:{actor_id:'researcher',attempt_id:'author-attempt'},source_count:1,report_count:1,scientific_confidence:null,active_review:reviewed?{...reviewItem,finding_id:7}:null,latest_review:reviewed?reviewItem:null,reviews:{items:reviewed?[reviewItem]:[],next_after_id:null}}
 const reviewKey=['finding-reviews','state',101,7]
 if(reviewFailure)client.getQueryCache().build(client,{queryKey:reviewKey}).setState({status:'error',error:new Error('Review unavailable')})
 else client.setQueryData(reviewKey,reviewState)
 client.setQueryData(['finding-reviews','detail',101,7,17],{...reviewItem,project_id:foreignReview?202:101,task_id:1001,finding_id:7,author_attempt_id:'author-attempt',reviewer_fence:1,scientific_confidence:null,review_scope:'reported_checks_only',decision:{verdict:'supported',rationale:foreignReview?'FOREIGN REVIEW SECRET':'La afirmación coincide con la captura.',checks:[{criterion:'claim_support',outcome:'supported',explanation:'La fuente declara una tasa fraccionaria.'}],limitations:['No se volvió a ejecutar el experimento.'],verified_evidence:[{source_id:3,source_sha256:'a'.repeat(64),quote:'Tax rates are fractions.',quote_offset:0,source:{id:3,title:'policy.txt',locator:'https://example.org/policy'}}]}})
 client.setQueryData(['task-workspace',101,1001],{project_id:101,task_id:1001,context:{task:{title:'Convención de tasas',description:null,type:'research',status:'in_progress'},context_version:1,corrections:[],task_changes:[]},runs:[],repositories:[{id:11,name:'Contexto Atlas',default_branch:'main'}],references:[],sources:[],reports:[],questions:[],runtime:{configured:true,supported_task_types:['research'],model:'controlled-fixture'}})
 const url=empty||indexFailure?'/findings':`/findings?project=${foreign?202:101}&finding=7`
 try{return renderToStaticMarkup(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={client}><FindingsPage /></QueryClientProvider></MemoryRouter>)}
 finally{initial.activeProjectId=previous;client.clear()}
}

export * as findingModel from '../src/components/findings/presentation'

/** Render actual code delivery evidence states without browser or inference doubles. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CodeDelivery } from '../src/components/tasks/CodeDelivery'

/** Supply explicit ready/rejected/stale/accepted cases for the real component. */
export function renderCodeResult(kind='ready') {
  const client=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity,gcTime:Infinity}}})
  client.setQueryData(['code-result',101,'author-code',3],{
    project_id:101,task_id:24,run_id:'author-code',candidate:{project_id:101,task_id:24,repository_id:11,run_id:'author-code',attempt_id:'author-attempt',context_version:3,fence:1,base_sha:'1'.repeat(40),head_sha:'2'.repeat(40),tree_sha:'3'.repeat(40),diff_sha256:'c'.repeat(64)},
    candidate_current:kind!=='stale',packet:{author_request:{text:'Corregir total <impuesto>.'},checks:[]},subject_sha256:'a'.repeat(64),review_sha256:'b'.repeat(64),
    review:{run_id:'review-code',attempt_id:'review-attempt',actor_id:'separate-reviewer',state:'confirmed',proposal:{verdict:kind==='rejected'?'needs_revision':'supported',rationale:'La fórmula usa una fracción.',checks:[],references:[{kind:'file',path:'invoice.py',sha256:'d'.repeat(64),start_line:5,quote:'return amount * (1 + rate)'}],limitations:['No hay suite de pruebas registrada.']}},
    eligible:kind==='ready',blockers:kind==='stale'?[{code:'review_not_current',message:'La revisión ya no corresponde al contexto actual.'}]:kind==='rejected'?[{code:'review_not_supported',message:'El revisor pide cambios.'}]:kind==='disagreement'?[{code:'review_disagreement',message:'Hay una objeción confirmada del mismo candidato sin resolver.'}]:[],
    review_issues:kind==='disagreement'?[{run_id:'earlier-review',state:'confirmed',verdict:'needs_revision',rationale:'La revisión anterior observó una tasa incorrecta.',blocking:true,message:'Una revisión posterior no borra esta objeción.'}]:[],
    checks:{limitations:[{code:'checks_absent',message:'No hay comprobaciones registradas del candidato.'}]},requires_acknowledgement:true,
    acceptance:kind==='accepted'?{operation_key:'owner-key',attempt_id:'author-attempt',subject_sha256:'a'.repeat(64),review_sha256:'b'.repeat(64),accepted_at:1793600000,note:'Acepto con estos límites.',task_accepted:true,publication_performed:false}:null,acceptance_current:kind==='accepted',
    publication:{performed:false,eligibility:'not_evaluated',message:'Aceptar esta versión no la publica.'},
  })
  const html=renderToStaticMarkup(<QueryClientProvider client={client}><CodeDelivery projectId={101} taskId={24} runId="author-code" contextVersion={3}/></QueryClientProvider>)
  client.clear()
  return html
}

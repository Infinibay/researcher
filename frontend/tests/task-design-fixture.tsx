import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TaskInspector } from '../src/components/tasks/TaskInspector'

export function renderTask({ taskType = 'research', failure = false, inputChange = false, inputState = 'none' } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false, staleTime: Infinity, gcTime: Infinity } } })
  if (failure) client.getQueryCache().build(client, { queryKey: ['task', 24] }).setState({ status: 'error', error: new Error('Fixture unavailable') })
  else client.setQueryData(['task', 24], { id: 24, project_id: 101, type: taskType, status: 'in_progress', title: 'Comprobar <reintentos>' })
  client.setQueryData(['task-comments', 24], [])
  client.setQueryData(['task-dependencies', 24], [])
  client.setQueryData(['task-workspace', 101, 24], {
    context: { context_version: 3, task: { type: taskType, status: 'in_progress' }, corrections: [], task_changes: inputChange ? [{version: 3, source_kind: 'task_metadata', actor: null, changes: {description: {before: 'Base 100', after: 'Base <200>'}}}] : [] },
    runtime: { configured: true, supported_task_types: ['research'], model: 'fixture-model' },
    runs: [{ run_id: 'fixture-run', status: 'needs_review', context_version: 2, model: 'fixture-model', prompt: 'Comprobar', result: { summary: 'Hallazgo provisional: falta comprobar el servidor.' } }],
    repositories: [], questions: [], references: [], sources: [], reports: [],
  })
  if (inputState !== 'none') client.setQueryData(['run-input', 101, 'fixture-run'], inputState === 'unknown' ? {available:false,reason:'no_record'} : {available:true,native_start_observed:true,model:'fixture-model',input_sha256:'a'.repeat(64),instructions_sha256:'b'.repeat(64),developer_instructions:'Preserve evidence strength.',business_catalog:[],input_text:JSON.stringify({context_version:2,request:'Original request <kept>',conversation:{cutoff_message_id:17,messages:[{message_id:11}],other_task_messages_excluded:2}})})
  const output = renderToStaticMarkup(<QueryClientProvider client={client}><TaskInspector taskId={24} onClose={() => {}} /></QueryClientProvider>)
  client.clear()
  return output
}

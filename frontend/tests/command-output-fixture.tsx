import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandReceipt, RunCommands } from '../src/components/tasks/RunCommands'

export function renderCommand({ mode = 'unknown', projectId = 101, list = false } = {}) {
  const client = new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false,staleTime:Infinity,gcTime:Infinity}}})
  const summary = {
    job_id:'job-a',seq:'1',run_id:'run-a',attempt_id:'attempt-a',context_version:2,
    is_current_attempt:true,operation_key:'calculate',status:mode === 'zero' ? 'exited' : 'unknown',
    exit_code:mode === 'zero' ? 0 : null,local_execution_closed:mode !== 'zero',
    cancel_requested:false,output_limited:mode === 'limited',error:null,
    executable:'python3',cwd:'.',timeout_seconds:30,output_bytes:65536,
    stdout_bytes:100,stderr_bytes:0,output_persistence:'terminal_receipt',
  }
  const bytes = mode === 'controls' ? Buffer.from('A\u001b[31m\rB\u202e')
    : mode === 'unknown' ? Buffer.concat([Buffer.from([255]),Buffer.from('PARTIAL<script>')]) : Buffer.from('PARTIAL<script>')
  const window = {offset:0,next_offset:bytes.length,total_bytes:100,has_more:true,base64:bytes.toString('base64'),text:bytes.toString('utf8'),utf8_lossy:mode === 'unknown'}
  const output = { ...summary,argv:['python3','-c',"print('<example>')"],
    stdout:window,
    stderr:{offset:0,next_offset:0,total_bytes:0,has_more:false,base64:'',text:'',utf8_lossy:false},
  }
  if (mode === 'error') client.getQueryCache().build(client,{queryKey:['command-output',101,'run-a','job-a',0,0]}).setState({status:'error',error:new Error('Unavailable')})
  else client.setQueryData(['command-output',101,'run-a','job-a',0,0], output)
  client.setQueryData(['run-commands',101,'run-a','0'], {run_id:'run-a',total:27,next_after_seq:'25',
    items:Array.from({length:25},(_,index) => ({...summary,seq:String(index+1),job_id:`job-${index+1}`}))})
  const html=renderToStaticMarkup(<QueryClientProvider client={client}>{list
    ? <RunCommands projectId={projectId} runId="run-a" />
    : <CommandReceipt projectId={projectId} runId="run-a" jobId="job-a" />}</QueryClientProvider>)
  client.clear()
  return html
}

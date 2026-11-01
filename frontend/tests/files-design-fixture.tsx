/** Render the Files owner surface with isolated project/cache state and no inference. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Header } from '../src/components/layout/Header'
import { FilesPage } from '../src/components/pages/FilesPage'
import { useProjectStore } from '../src/stores/project'

/** Exercise scoped deep links, catalog/detail errors and unsupported preview claims. */
export function renderFiles({ includeHeader=false, noProject=false, wrongProject=false, foreignCache=false, detailFailure=false, catalogFailure=false, empty=false }={}) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false,staleTime:Infinity,gcTime:Infinity}}})
 const initial=useProjectStore.getInitialState(), previous=initial.activeProjectId
 initial.activeProjectId=noProject?null:101
 client.setQueryData(['project',101],{id:101,name:'Atlas de prueba',status:'new'})
 client.setQueryData(['projects'],{projects:[{id:101,name:'Atlas de prueba',status:'new'}],total:1})
 const file={id:77,project_id:foreignCache?202:101,filename:foreignCache?'OTHER PROJECT SECRET':'política <fiscal>.pdf',file_size:962,mime_type:'application/pdf',description:'Documento de referencia.',uploaded_at:'2026-11-01 17:39:00'}
 client.setQueryData(['files',101],empty?[]:[file])
 const catalogKey=['files',101,{q:''}]
 if(catalogFailure)client.getQueryCache().build(client,{queryKey:catalogKey}).setState({status:'error',error:new Error('Catalog unavailable')})
 else client.setQueryData(catalogKey,{pages:[empty?[]:[file]],pageParams:[0]})
 if(detailFailure)client.getQueryCache().build(client,{queryKey:['file',101,77]}).setState({status:'error',error:new Error('Detail unavailable')})
 else client.setQueryData(['file',101,77],file)
 try {return renderToStaticMarkup(<MemoryRouter initialEntries={[empty||catalogFailure?'/files':`/files?project=${wrongProject?202:101}&file=77`]}><QueryClientProvider client={client}>{includeHeader && <Header />}<FilesPage /></QueryClientProvider></MemoryRouter>)}
 finally{initial.activeProjectId=previous;client.clear()}
}

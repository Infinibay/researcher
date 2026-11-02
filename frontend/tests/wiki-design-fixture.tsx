/** Render the actual Wiki page with scoped synthetic cache state and no inference. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WikiPage } from '../src/components/pages/WikiPage'
import { useProjectStore } from '../src/stores/project'

/** Isolate exact paths, explicit global scope, foreign links/cache and distinct read failures. */
export function renderWiki({noProject=false,wrongProject=false,foreignCache=false,global=false,catalogFailure=false,detailFailure=false,empty=false}={}) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false,staleTime:Infinity,gcTime:Infinity}}})
 const initial=useProjectStore.getInitialState(),previous=initial.activeProjectId
 initial.activeProjectId=noProject?null:101
 const namespace=global?'global':'project',path='notes/intro'
 const page={id:7,project_id:global?null:foreignCache?202:101,namespace,path,title:foreignCache?'FOREIGN SECRET':'Contexto compartido',content:'# Contexto compartido\n\nUna hipótesis no es una validación.\n\n## Ejemplo\n\nConservar el resultado permite corregir una interpretación.',parent_path:null,revision:3,sha256:'a'.repeat(64),updated_at:'2026-11-01 23:00:00',updated_by:null}
 client.setQueryData(['projects'],{projects:[{id:101,name:'Atlas',status:'new'}],total:1})
 client.setQueryData(['project',101],{id:101,name:'Atlas',status:'new'})
 const key=['wiki','index',101,namespace,'']
 if(catalogFailure)client.getQueryCache().build(client,{queryKey:key}).setState({status:'error',error:new Error('Catalog unavailable')})
 else client.setQueryData(key,{pages:[{pages:empty?[]:[page],next_after_id:null,namespace}],pageParams:[0]})
 const detailKey=['wiki','page',101,namespace,path]
 if(detailFailure)client.getQueryCache().build(client,{queryKey:detailKey}).setState({status:'error',error:new Error('Detail unavailable')})
 else client.setQueryData(detailKey,page)
 const url=empty||catalogFailure?'/wiki':`/wiki?project=${wrongProject?202:101}&namespace=${namespace}&path=${encodeURIComponent(path)}`
 try{return renderToStaticMarkup(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={client}><WikiPage /></QueryClientProvider></MemoryRouter>)}
 finally{initial.activeProjectId=previous;client.clear()}
}

export * as wikiModel from '../src/components/wiki/presentation'
export { saveWikiRequest } from '../src/hooks/useWiki'

export { useWikiDrafts } from '../src/stores/wikiDrafts'

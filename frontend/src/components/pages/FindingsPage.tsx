/** Selected evidence ledger: current claims, exact citations and honest review provenance. @module */
import {useEffect,useRef,useState,type FormEvent} from 'react'
import {useSearchParams} from 'react-router-dom'
import {useProjectStore} from '../../stores/project'
import {useProject} from '../../hooks/useProjects'
import {useFindings,useFindingsSearch,useFinding,useFindingEvidence,useFindingSource,useFindingLegacySources} from '../../hooks/useFindings'
import {findingLocation,findingStates,findingTypes,scopedFinding,sameFindingCorpus,type FindingFilters} from '../findings/presentation'
import type {FindingDetail,FindingEvidence} from '../../types/api'
import {reportDocument,reportTimestamp} from '../reports/presentation'
import {MarkdownRenderer} from '../common/MarkdownRenderer'
import '../../styles/tasks.css'
import '../../styles/findings.css'

/** Display only persisted dates, explicitly in UTC, with unknown dates left unknown. */
function FindingDate({value}:{value?:string|number|null}) {
 const date=reportTimestamp(value)
 return date.machine?<time dateTime={date.machine}>{date.label}</time>:<span>{date.label}</span>
}

/** Remount transient search/selection state when the visible project changes. */
export function FindingsPage() {
 const projectId=useProjectStore(state=>state.activeProjectId)
 if(!projectId)return <div className="task-workbench findings-workbench"><section className="findings-idle"><h1>Elige un proyecto para consultar sus hallazgos</h1><p>Selecciona el proyecto en la cabecera. Las afirmaciones y sus fuentes conservan ese alcance.</p></section></div>
 return <FindingsWorkspace key={projectId} projectId={projectId}/>
}

/** Keep submitted searches and cached results bound to the visible project and actual filters. */
function FindingsWorkspace({projectId}:{projectId:number}) {
 const [params,setParams]=useSearchParams()
 const location=findingLocation(params,projectId)
 const {data:project}=useProject(projectId)
 const [search,setSearch]=useState(''),[query,setQuery]=useState('')
 const [mode,setMode]=useState<'lexical'|'semantic'>('lexical')
 const [type,setType]=useState(''),[status,setStatus]=useState(''),[confidence,setConfidence]=useState('')
 const [marked,setMarked]=useState<number[]>([]),[submitted,setSubmitted]=useState<number[]>([])
 const filters:FindingFilters={query:mode==='lexical'?query:'',finding_type:type,status,min_confidence:confidence===''?null:Number(confidence)}
 const index=useFindings(location.ready?projectId:null,filters)
 const ranked=useFindingsSearch(location.ready&&mode==='semantic'?projectId:null,query,filters,submitted)
 const detail=useFinding(location.ready?projectId:null,location.id,location.offset)
 const indexHeading=useRef<HTMLHeadingElement>(null),returnId=useRef<number|null>(null)
 const indexValid=!!index.data&&index.data.pages.every(page=>page.project_id===projectId&&Array.isArray(page.items)&&page.items.every(item=>scopedFinding(item,projectId)))
 const items=indexValid?index.data!.pages.flatMap(page=>page.items):[]
 const page=location.ready&&scopedFinding(detail.data,projectId,location.id??undefined)&&typeof detail.data?.content==='string'?detail.data:undefined
 const semantic=mode==='semantic'&&query!==''
 const rankingValid=sameFindingCorpus(ranked.data?.pages,projectId)
 const seen=new Set<number>()
 const matches=rankingValid?ranked.data!.pages.flatMap(page=>page.matches).filter(match=>{if(seen.has(match.finding_id))return false;seen.add(match.finding_id);return true}):[]
 const IndexHeading=location.ready&&location.id!=null?'h2':'h1'
 useEffect(()=>{if(location.id==null&&returnId.current!=null){(document.getElementById(`finding-select-${projectId}-${returnId.current}`)??indexHeading.current)?.focus();returnId.current=null}},[location.id,projectId])

 /** Route body pages independently; current rows are not presented as retained revisions. */
 function choose(id:number|null,offset=0) {
  returnId.current=location.id
  const next=new URLSearchParams({project:String(projectId)})
  if(id!=null)next.set('finding',String(id))
  if(offset)next.set('offset',String(offset))
  setParams(next)
 }
 /** Filter edits do not launch another expensive semantic query until explicit submission. */
 function changedFilter() {if(mode==='semantic')setQuery('');setMarked([]);setSubmitted([])}
 /** Preserve the actual chosen corpus, instead of changing it as later checkboxes move. */
 function submit(event:FormEvent) {event.preventDefault();setQuery(search.trim());setSubmitted([...marked].sort((a,b)=>a-b))}
 const loading=semantic?ranked.isPending:index.isPending
 const failure=semantic?ranked.isError&&!ranked.data||!!ranked.data&&!rankingValid:index.isError&&!index.data||!!index.data&&!indexValid
 return <div className="task-workbench findings-workbench" data-detail={location.ready&&location.id!=null}>
  <section className="findings-index" aria-label="Lista de hallazgos">
   <header><IndexHeading tabIndex={-1} ref={indexHeading}>Hallazgos</IndexHeading><p>Proyecto {project?.name??projectId}</p></header>
   {!location.ready?<div className="findings-message" role="alert"><p>{location.foreign?'Este enlace corresponde a otro proyecto. Elige ese proyecto en la cabecera o vuelve a la lista actual.':'El enlace contiene una identidad o fragmento no válido.'}</p><button onClick={()=>choose(null)}>Consultar la lista actual</button></div>:<>
    <form onSubmit={submit} className="findings-search">
     <label htmlFor="finding-query">Buscar hallazgos</label><input id="finding-query" type="search" value={search} onChange={event=>setSearch(event.target.value)} maxLength={1000} placeholder="Palabras o pregunta"/>
     <label htmlFor="finding-mode">Buscar por</label><select id="finding-mode" value={mode} onChange={event=>{setMode(event.target.value as typeof mode);setQuery('');setMarked([]);setSubmitted([])}}><option value="lexical">Palabras</option><option value="semantic">Significado</option></select>
     <button className="findings-primary" type="submit">Buscar</button>
     <p>{mode==='lexical'?'Busca palabras en los títulos y textos; no comprueba ausencia de ideas similares.':'Consulta el texto completo del conjunto elegido con el modelo local. La similitud no mide certeza científica.'}</p>
     <div className="findings-filters"><div><label htmlFor="finding-type">Tipo</label><select id="finding-type" value={type} onChange={event=>{setType(event.target.value);changedFilter()}}><option value="">Todos</option>{Object.entries(findingTypes).map(([key,label])=><option key={key} value={key}>{label}</option>)}<option value="unknown">Sin tipo registrado</option></select></div><div><label htmlFor="finding-status">Estado</label><select id="finding-status" value={status} onChange={event=>{setStatus(event.target.value);changedFilter()}}><option value="">Todos</option>{Object.entries(findingStates).map(([key,label])=><option key={key} value={key}>{label}</option>)}<option value="unknown">Sin estado registrado</option></select></div></div>
     <details><summary>Confianza declarada</summary><label htmlFor="finding-confidence">Valor mínimo almacenado</label><select id="finding-confidence" value={confidence} onChange={event=>{setConfidence(event.target.value);changedFilter()}}><option value="">Sin filtro · incluye valores desconocidos</option><option value="0">0 o más</option><option value="0.5">0,5 o más</option><option value="0.8">0,8 o más</option></select><p>Son declaraciones históricas. No equivalen a una evaluación científica; el filtro numérico excluye registros sin valor.</p></details>
     {mode==='semantic'&&<p>{marked.length?`${marked.length} registros marcados para la próxima consulta.`:'Sin marcas: se consultarán todos los hallazgos que cumplan los filtros, dentro del límite indicado por el servicio.'}</p>}
    </form>
    {(semantic?ranked.isError&&ranked.data&&rankingValid:index.isError&&index.data&&indexValid)&&<p className="findings-message findings-error" role="alert">No se pudo actualizar la consulta. Se conserva el último resultado disponible; vuelve a consultarlo antes de tratarlo como actual.</p>}
    {loading?<p className="findings-message" role="status">Consultando hallazgos…</p>:failure?<div className="findings-message findings-error" role="alert"><p>{semantic?'No se pudo completar la búsqueda por significado. El modelo puede no estar preparado o el conjunto superar su límite. Acota los filtros o marca registros; no se sustituyó por búsqueda de palabras.':'No se pudo consultar la lista de hallazgos.'}</p><button onClick={()=>semantic?ranked.refetch():index.refetch()}>Volver a consultar</button></div>:<>
     {semantic?<><button onClick={()=>setQuery('')}>Elegir otros registros</button><p className="findings-count">Consulta sobre {ranked.data?.pages[0]?.corpus_count??0} registros completos{submitted.length?' seleccionados':' con estos filtros'}.</p><ul className="findings-list">{matches.map(match=><li key={match.finding_id}><button id={`finding-select-${projectId}-${match.finding_id}`} aria-current={location.id===match.finding_id?'true':undefined} onClick={()=>choose(match.finding_id)}><strong>{match.topic}</strong><span className="findings-muted">Coincidencia por significado · puntuación de similitud {match.score.toFixed(3)}</span><span className="findings-row-preview">{match.excerpt}</span></button></li>)}</ul>{!matches.length&&<p className="findings-message">No hay hallazgos en el conjunto consultado.</p>}{ranked.hasNextPage&&<button disabled={ranked.isFetchingNextPage} onClick={()=>ranked.fetchNextPage()}>Mostrar más coincidencias</button>}{ranked.isFetchNextPageError&&<div role="alert"><p>No se pudo continuar la consulta. Si cambió el conjunto, reinicia la búsqueda para no mezclar versiones.</p><button onClick={()=>ranked.restart()}>Reiniciar búsqueda</button></div>}</>:<>
      <p className="findings-count">{items.length} de {index.data?.pages[0]?.total_matching??0} registros con estos filtros</p>
      <ul className="findings-list">{items.map(item=><li key={item.id} data-selected={location.id===item.id}>{mode==='semantic'&&<label className="findings-mark"><input type="checkbox" checked={marked.includes(item.id)} onChange={event=>setMarked(current=>event.target.checked?[...current,item.id]:current.filter(id=>id!==item.id))}/>Seleccionar para búsqueda por significado: {item.topic}</label>}<button id={`finding-select-${projectId}-${item.id}`} aria-current={location.id===item.id?'true':undefined} onClick={()=>choose(item.id)}><strong>{item.topic}</strong><span className="findings-row-meta"><span>{findingTypes[item.finding_type??'']??'Tipo no registrado'}</span><span className="findings-state" data-status={item.status}>{findingStates[item.status??'']??'Estado no registrado'}</span></span><span className="findings-row-preview">{item.content_excerpt}</span><span className="findings-muted"><FindingDate value={item.created_at}/></span></button></li>)}</ul>
      {!items.length&&<p className="findings-message">No hay hallazgos con estos filtros. Prueba otros términos o consulta la lista sin filtros.</p>}
      {index.hasNextPage&&<button disabled={index.isFetchingNextPage} onClick={()=>index.fetchNextPage()}>{index.isFetchingNextPage?'Consultando…':'Mostrar más hallazgos'}</button>}{index.isFetchNextPageError&&<p role="alert">No se pudo consultar la siguiente página. Puedes volver a intentarlo.</p>}
     </>}
    </>}
   </>}
  </section>
  <section className="findings-pane" aria-label="Lector de hallazgos">
   {location.ready&&location.id!=null?<><button className="findings-back" onClick={()=>choose(null)}>‹ Volver a hallazgos</button>{page?<FindingReader key={`${projectId}:${page.id}`} projectId={projectId} projectName={project?.name??String(projectId)} page={page} chooseOffset={offset=>choose(page.id,offset)}/>:detail.isError||detail.data?<div className="findings-message findings-error" role="alert"><h1>No se pudo consultar el hallazgo</h1><p>Comprueba que pertenece al proyecto visible o vuelve a consultarlo.</p><button onClick={()=>detail.refetch()}>Volver a consultar</button></div>:<p role="status">Consultando el hallazgo…</p>}</>:<div className="findings-idle"><h2>Una afirmación, sus fuentes y lo que falta comprobar.</h2><p>Elige un hallazgo para examinar su texto y las citas capturadas. Un estado guardado o una cita exacta no demuestran por sí solos que la conclusión sea correcta.</p></div>}
  </section>
 </div>
}

/** Show actual stored claims and current citation records, leaving unknown review/author data explicit. */
function FindingReader({projectId,projectName,page,chooseOffset}:{projectId:number;projectName:string;page:FindingDetail;chooseOffset:(offset:number)=>void}) {
 const title=useRef<HTMLHeadingElement>(null),citationTrigger=useRef<string|null>(null)
 const evidence=useFindingEvidence(projectId,page.id)
 const [source,setSource]=useState<{id:number;offset:number;quote:string}|null>(null)
 const evidenceValid=!!evidence.data&&evidence.data.pages.every(part=>part.project_id===projectId&&part.finding_id===page.id&&part.evidence.every(item=>item.finding_id===page.id))
 const citations=evidenceValid?evidence.data!.pages.flatMap(part=>part.evidence):[]
 useEffect(()=>{title.current?.focus()},[page.id,page.offset])
 useEffect(()=>{if(!source&&citationTrigger.current)document.getElementById(citationTrigger.current)?.focus()},[source])
 /** Select only a cited source; start near the actual exact quotation when that offset is known. */
 function inspect(item:FindingEvidence,index:number) {
  citationTrigger.current=`finding-${projectId}-${page.id}-cite-${index}`
  setSource({id:item.source_id,offset:Math.max(0,(item.quote_offset??0)-300),quote:item.quote})
 }
 return <article className="findings-reader">
  <header className="findings-reader-heading"><p className="findings-muted">Proyecto {projectName} · hallazgo {page.id}</p><h1 tabIndex={-1} ref={title}>{page.topic}</h1><div className="findings-row-meta"><span>{findingTypes[page.finding_type??'']??'Tipo no registrado'}</span><span className="findings-state" data-status={page.status}>{findingStates[page.status??'']??'Estado no registrado'}</span><FindingDate value={page.created_at}/></div></header>
  {source?<FindingSourceReader projectId={projectId} findingId={page.id} source={source} close={()=>setSource(null)}/>:<>
   <section className="findings-assessment" aria-label="Procedencia de la evaluación"><p><strong>{page.review_status==='unverified_legacy'?'Revisión independiente no acreditada':'Sin revisión independiente registrada'}</strong></p><p>Confianza científica: sin evaluar.</p>{(page.confidence!=null||page.confidence_invalid||page.validation_method)&&<details><summary>Ver evaluación declarada · registro heredado</summary>{page.confidence!=null&&<p>Confianza declarada: {page.confidence.toLocaleString('es-AR')}.</p>}{page.confidence_invalid&&<p>El valor declarado original ({page.confidence_original}) no es un número válido entre 0 y 1.</p>}{page.validation_method&&<p>Método declarado: {page.validation_method}</p>}<p>Son declaraciones históricas; el valor y el método no acreditan una revisión independiente.</p></details>}</section>
   <section className="findings-body" aria-label="Afirmación registrada"><MarkdownRenderer content={reportDocument(page.content,page.topic)}/><p className="findings-muted">{page.total_chars?`Caracteres ${page.offset+1}–${Math.min(page.total_chars,page.offset+page.content.length)} de ${page.total_chars}.`:'El registro no contiene texto.'} Texto del registro actual.</p><div className="findings-window-nav">{page.offset>0&&<button onClick={()=>chooseOffset(Math.max(0,page.offset-12000))}>Fragmento anterior</button>}{page.next_offset!=null&&<button onClick={()=>chooseOffset(page.next_offset!)}>Siguiente fragmento</button>}</div></section>
   <section className="findings-evidence" aria-label="Fuentes citadas"><h2>Fuentes citadas</h2><p>Una cita exacta permite contrastar el texto; no demuestra por sí sola que la conclusión sea correcta.</p>
    {evidence.isPending?<p role="status">Consultando las citas…</p>:evidence.isError&&!evidence.data||evidence.data&&!evidenceValid?<div role="alert" className="findings-error"><p>No se pudieron consultar las citas.</p><button onClick={()=>evidence.refetch()}>Volver a consultar las citas</button></div>:<>
     {citations.map((item,index)=><section className="findings-citation" key={`${item.source_id}:${index}`} aria-label={`Cita ${index+1}`}><header><div><h3>{item.title??`Fuente ${item.source_id} no disponible`}</h3><p className="findings-muted">Captura {item.source_id} · <FindingDate value={item.captured_at}/></p></div><button id={`finding-${projectId}-${page.id}-cite-${index}`} className="findings-secondary" disabled={item.source_unavailable} onClick={()=>inspect(item,index)}>Ver cita</button></header><blockquote>{item.quote}</blockquote>{item.quote_truncated&&<p>La cita es más larga que la previa. Consulta la captura para recuperar el texto completo.</p>}{!item.quote_is_exact&&<p className="findings-error">Esta cita no coincide con el texto guardado o su fuente no está disponible. Hay que reconciliar el registro antes de usarla como evidencia.</p>}</section>)}
     {!citations.length&&<p>No hay citas capturadas vinculadas a este registro. Eso no demuestra ausencia de otras fuentes.</p>}
     <p className="findings-muted">{citations.length} de {evidence.data?.pages[0]?.total_evidence??0} citas mostradas.</p>{evidence.hasNextPage&&<button disabled={evidence.isFetchingNextPage} onClick={()=>evidence.fetchNextPage()}>Mostrar más citas</button>}{evidence.isFetchNextPageError&&<p role="alert">No se pudo consultar la siguiente página de citas. Puedes volver a intentarlo.</p>}
    </>}
   </section>
   <LegacyFindingSources projectId={projectId} page={page}/>
   <footer className="findings-provenance"><h2>Procedencia</h2><p>Registrado por: {page.agent_id??'Autor no registrado'}.</p><p>Proyecto {projectName}{page.task_id!=null?` · tarea ${page.task_id}`:''}.</p></footer>
  </>}
 </article>
}

/** Inspect literal saved source text and real capture identity; errors never become empty evidence. */
function FindingSourceReader({projectId,findingId,source,close}:{projectId:number;findingId:number;source:{id:number;offset:number;quote:string};close:()=>void}) {
 const [offset,setOffset]=useState(source.offset),heading=useRef<HTMLHeadingElement>(null)
 const query=useFindingSource(projectId,findingId,source.id,offset)
 const data=query.data?.project_id===projectId&&query.data.finding_id===findingId&&query.data.source_id===source.id?query.data:undefined
 useEffect(()=>{if(data)heading.current?.focus()},[data?.source_id,data?.offset])
 const quotePosition=data?.content.indexOf(source.quote)??-1
 return <section className="findings-source" aria-label="Captura citada"><button onClick={close}>‹ Volver al hallazgo</button><h2 ref={heading} tabIndex={-1}>Captura guardada</h2>{data?<>
  <h3>{data.title}</h3><p>Captura {data.source_id} · <FindingDate value={data.captured_at}/></p><p className="findings-muted">{data.locator}</p><p>Texto capturado, no una consulta al documento actual.</p>
  <pre className="findings-source-text">{quotePosition>=0?<>{data.content.slice(0,quotePosition)}<mark>{source.quote}</mark>{data.content.slice(quotePosition+source.quote.length)}</>:data.content}</pre>
  <p className="findings-muted">Caracteres {data.content.length?data.offset+1:0}–{Math.min(data.total_chars,data.offset+data.content.length)} de {data.total_chars}.</p><div className="findings-window-nav">{offset>0&&<button onClick={()=>setOffset(Math.max(0,offset-12000))}>Fragmento anterior de la captura</button>}{data.next_offset!=null&&<button onClick={()=>setOffset(data.next_offset!)}>Siguiente fragmento de la captura</button>}</div>
  <details><summary>Identidad de la captura</summary><p>SHA-256 <code>{data.sha256}</code></p><p>Una coincidencia de hash identifica el texto guardado; no acredita la validez científica de su contenido.</p></details>
 </>:query.isError||query.data?<div className="findings-error" role="alert"><p>No se pudo consultar esta captura. Puede faltar o no coincidir con su hash guardado; no se presenta como evidencia verificada.</p><button onClick={()=>query.refetch()}>Volver a consultar la captura</button></div>:<p role="status">Consultando la captura…</p>}</section>
}

/** Preserve old raw source declarations as literal historical data, independently of captured quotes. */
function LegacyFindingSources({projectId,page}:{projectId:number;page:FindingDetail}) {
 const [offset,setOffset]=useState(0)
 const query=useFindingLegacySources(projectId,page.id,offset)
 if(page.legacy_sources_json==null)return null
 const data=offset===0?{content:page.legacy_sources_json,total_chars:page.legacy_sources_total_chars,next_offset:page.legacy_sources_next_offset}:query.data?.project_id===projectId&&query.data.finding_id===page.id?query.data:undefined
 return <details className="findings-legacy-sources"><summary>Fuentes declaradas en el registro original</summary><p>Declaraciones heredadas, sin verificación adicional. No son capturas ni citas acreditadas; las direcciones no se consultan automáticamente.</p>{data?<><pre>{data.content}</pre><p>Fragmento desde el carácter {offset+1}; {data.total_chars} caracteres en total.</p><div className="findings-window-nav">{offset>0&&<button onClick={()=>setOffset(Math.max(0,offset-8000))}>Declaración anterior</button>}{data.next_offset!=null&&<button onClick={()=>setOffset(data.next_offset!)}>Siguiente fragmento de declaraciones</button>}</div></>:query.isError||query.data?<div role="alert"><p>No se pudo consultar la declaración original.</p><button onClick={()=>query.refetch()}>Volver a consultar las declaraciones</button></div>:<p role="status">Consultando la declaración…</p>}</details>
}

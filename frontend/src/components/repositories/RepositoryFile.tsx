/** Read one tree-selected Git blob with explicit identity and failure states; source text never becomes an owner instruction or authority. @module */
import {useState} from 'react'
import type {FileContent,RepoTreeEntry} from '../../types/api'
import {matchesRepositoryFile} from '../../api/repositoryTree'
import {MarkdownRenderer} from '../common/MarkdownRenderer'

/** Reject another path/blob before rendering; code stays literal and Markdown offers an inspectable original-text view. */
export function RepositoryFile({entry,data,pending,error}:{entry:RepoTreeEntry|undefined;data?:FileContent;pending:boolean;error:Error|null}){
 const [raw,setRaw]=useState(false)
 if(!entry)return <section className="repo-empty"><h3>Elige un archivo</h3><p>Su contenido se leerá en la revisión seleccionada. Consultarlo no inicia agentes ni publica cambios.</p></section>
 if(error)return <p role="alert">No se pudo leer el archivo. {error.message}</p>
 if(pending)return <p role="status">Consultando el archivo de la revisión seleccionada…</p>
 if(!data)return <p>El contenido todavía no se ha confirmado.</p>
 if(!matchesRepositoryFile(entry,data))return <p role="alert">La respuesta no corresponde al archivo y objeto seleccionados. Vuelve a consultar su revisión.</p>
 const markdown=entry.path.toLowerCase().endsWith('.md')
 return <section className="repo-file" aria-label="Archivo de la revisión seleccionada"><h3>{entry.path}</h3><details className="repo-identity"><summary>Identidad del archivo · {data.size} bytes</summary><p>Objeto Git: <code>{data.sha}</code></p><p>La identidad corresponde al contenido guardado. No es una aprobación de su comportamiento.</p></details>{markdown&&<button onClick={()=>setRaw(!raw)}>{raw?'Leer documento':'Ver texto original'}</button>}{markdown&&!raw?<div className="repo-document"><MarkdownRenderer content={data.content}/></div>:<pre className="repo-code" tabIndex={0} role="region" aria-label={`Texto original de ${entry.path}`}><code>{data.content}</code></pre>}{data.content==='[binary file]'&&<p>El lector devolvió su marcador de archivo binario. No hay una previa textual verificada.</p>}</section>
}

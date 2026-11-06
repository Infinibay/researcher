/** Render the actual source reader with explicit immutable tree/blob and failure cases. @module */
import React from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
import {RepositoryFile} from '../src/components/repositories/RepositoryFile'
/** Supply real reader props without a browser, query cache or model double. */
export function renderFile(kind:string){const entry={path:'src/report.py',type:'blob' as const,sha:'1'.repeat(40)};return renderToStaticMarkup(<RepositoryFile entry={entry} data={{path:entry.path,sha:kind==='mismatch'?'2'.repeat(40):entry.sha,content:kind==='mismatch'?'foreign-secret':'```<script>literal code</script>',size:40}} pending={kind==='pending'} error={kind==='error'?new Error('Controlled read failed'):null}/>)}

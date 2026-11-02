/** Scope and presentation rules for current findings; no status promotes a claim to truth. @module */
import type { Finding, FindingRanking } from '../../types/api'

/** Filtering treats missing declarations differently from an explicit historical numeric threshold. */
export interface FindingFilters {
  query:string; finding_type:string; status:string; min_confidence:number|null
}

export const findingTypes:Record<string,string>={observation:'Observación',hypothesis:'Hipótesis',experiment:'Experimento',proof:'Prueba (categoría declarada)',conclusion:'Conclusión'}
export const findingStates:Record<string,string>={provisional:'Provisional',active:'Activo · estado heredado',superseded:'Sustituido · estado heredado'}

/** Reject foreign cache entries before their titles, bodies or evidence can be rendered. */
export function scopedFinding(value:Finding|undefined,projectId:number,id?:number):value is Finding {
  return !!value&&value.project_id===projectId&&Number.isSafeInteger(value.id)&&value.id>0&&(!id||value.id===id)&&typeof value.topic==='string'
}

/** Parse only explicit positive decimal ids and nonnegative offsets; malformed links cannot select another row. */
export function findingLocation(params:URLSearchParams,projectId:number) {
  const rawId=params.get('finding'),rawProject=params.get('project'),rawOffset=params.get('offset')
  const id=rawId==null?null:Number(rawId),offset=rawOffset==null?0:Number(rawOffset)
  const foreign=rawProject!=null&&Number(rawProject)!==projectId
  const invalid=(rawId!=null&&(!/^[1-9]\d*$/.test(rawId)||!Number.isSafeInteger(id)))||(rawOffset!=null&&(!/^\d+$/.test(rawOffset)||!Number.isSafeInteger(offset)))||(rawProject!=null&&(!/^[1-9]\d*$/.test(rawProject)||!Number.isSafeInteger(Number(rawProject))))
  return {id,offset,foreign,invalid,ready:!foreign&&!invalid}
}

/** Never combine rank pages from different project, membership, text or metadata snapshots. */
export function sameFindingCorpus(pages:FindingRanking[]|undefined,projectId:number):boolean {
 if(!pages?.length)return false
 const first=pages[0]
 if(first.corpus_count>0&&(!/^[a-f0-9]{64}$/.test(first.corpus_sha256??'')||!/^[a-f0-9]{64}$/.test(first.record_set_sha256??'')))return false
 return pages.every(page=>page.project_id===projectId&&Array.isArray(page.finding_ids)&&Array.isArray(page.matches)&&page.corpus_sha256===first.corpus_sha256&&page.record_set_sha256===first.record_set_sha256&&page.finding_ids.length===first.finding_ids.length&&page.finding_ids.every((id,index)=>Number.isSafeInteger(id)&&id>0&&id===first.finding_ids[index])&&page.matches.every(match=>page.finding_ids.includes(match.finding_id)))
}

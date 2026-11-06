/** Complete source hierarchy and immutable Git reading identities, independent of selection timing or branch movement. @module */
import type {FileContent,RepoTreeEntry} from '../types/api'

/** A real Git entry or implied parent directory; file identities remain the original tree response. */
export interface RepositoryNode {name:string;path:string;type:'blob'|'tree';sha?:string;children?:RepositoryNode[]}

/** Preserve an unordered recursive Git tree, materializing parents once instead of depending on directory-first transport order. */
export function buildRepositoryTree(entries:RepoTreeEntry[]):RepositoryNode[]{
 const root:RepositoryNode[]=[],directories=new Map<string,RepositoryNode>()
 /** Reuse the one actual or implied directory for this path, recursively connecting its parents. */
 function directory(path:string):RepositoryNode{
  const old=directories.get(path);if(old)return old
  const parts=path.split('/'),node:RepositoryNode={name:parts[parts.length-1],path,type:'tree',children:[]};directories.set(path,node)
  if(parts.length===1)root.push(node);else directory(parts.slice(0,-1).join('/')).children!.push(node)
  return node
 }
 for(const entry of entries){
  if(entry.type==='tree'){directory(entry.path).sha=entry.sha;continue}
  const parts=entry.path.split('/'),node:RepositoryNode={...entry,name:parts[parts.length-1]}
  if(parts.length===1)root.push(node);else directory(parts.slice(0,-1).join('/')).children!.push(node)
 }
 /** Group directories first and keep names stable within each level without discarding source identities. */
 function sort(nodes:RepositoryNode[]){nodes.sort((a,b)=>a.type===b.type?a.name.localeCompare(b.name):a.type==='tree'?-1:1);for(const n of nodes)if(n.children)sort(n.children)}
 sort(root);return root
}

/** Return only a complete Git object identity; branch names and abbreviated hashes are observations requiring resolution. */
export function completeRevision(value:string|undefined):string|null{return value&&/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(value)?value:null}

/** Refuse stale/foreign file responses rather than displaying their text under another selected path or blob. */
export function matchesRepositoryFile(entry:RepoTreeEntry|undefined,file:FileContent):boolean{return entry?.type==='blob'&&entry.path===file.path&&entry.sha===file.sha}

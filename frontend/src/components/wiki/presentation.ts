/** Wiki scope, revision and draft contracts shared by UI and owner request adapters. @module */
import type { WikiPage, WikiNamespace } from '../../types/api'

/** A temporary complete edit owns its original project/namespace/id, independently of selection. */
export interface WikiDraft {
  key: string; projectId: number; namespace: WikiNamespace; pageId: number | null
  path: string; title: string; content: string; parentPath: string | null
  revision: number; operationKey: string; dirty: boolean
}

/** Reject a foreign cached page before displaying its title or enabling edits. */
export function scopedWiki(page: WikiPage | undefined, projectId: number, namespace: WikiNamespace, path?: string): page is WikiPage {
  return !!page && Number.isSafeInteger(page.id) && page.id > 0 && page.namespace === namespace && (namespace === 'global' ? page.project_id === null : page.project_id === projectId) && (!path || page.path === path) && Number.isSafeInteger(page.revision) && page.revision > 0
}

/** Keep logical path punctuation/slashes in one encoded URL rather than interpreting query/fragment. */
export function wikiPath(path: string): string { return `/api/wiki/${encodeURIComponent(path)}` }

/** Create an edit from a complete observed revision; creation never reuses an existing id. */
export function wikiDraft(projectId: number, namespace: WikiNamespace, page?: WikiPage): WikiDraft {
  return { key: page ? `edit:${projectId}:${namespace}:${page.id}` : `new:${crypto.randomUUID()}`, projectId, namespace, pageId: page?.id ?? null, path: page?.path ?? '', title: page?.title ?? '', content: page?.content ?? '', parentPath: page?.parent_path ?? null, revision: page?.revision ?? 0, operationKey: crypto.randomUUID(), dirty: false }
}

/** A changed intent receives a new key; an unchanged retry retains its original receipt identity. */
export function changeWikiDraft(draft: WikiDraft, changes: Partial<Pick<WikiDraft,'path'|'title'|'content'|'parentPath'>>): WikiDraft {
  return { ...draft, ...changes, dirty: true, operationKey: crypto.randomUUID() }
}

/** Prepare a confirmed overwrite on the same identity; preserve the actual draft, never silently merge. */
export function rebaseWikiDraft(draft: WikiDraft, page: WikiPage): WikiDraft {
  if (!scopedWiki(page, draft.projectId, draft.namespace, draft.path) || page.id !== draft.pageId) throw new Error('La página fue reemplazada; conserva el borrador como una copia.')
  return { ...draft, revision: page.revision, operationKey: crypto.randomUUID(), dirty: true }
}

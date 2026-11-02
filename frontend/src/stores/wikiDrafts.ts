/** In-memory drafts survive route/project changes; no document text is written to browser storage. @module */
import { create } from 'zustand'
import type { WikiPage } from '../types/api'
import type { WikiDraft } from '../components/wiki/presentation'

/** Explicit draft ownership prevents a changed project selector from redirecting a save. */
interface WikiDrafts {
  drafts: Record<string,WikiDraft>
  put: (draft: WikiDraft) => void
  /** Confirm only the exact submitted intent, including when its editor has unmounted. */
  confirm: (key: string, operationKey: string, page: WikiPage) => void
  remove: (key: string) => void
  clear: () => void
}

/** Retain drafts during transient session loss; explicit confirmed logout clears them. */
export const useWikiDrafts = create<WikiDrafts>(set => ({
  drafts: {},
  put: draft => set(state => ({drafts: {...Object.fromEntries(Object.entries(state.drafts).filter(([key,item]) => item.dirty || key === draft.key)),[draft.key]:draft}})),
  confirm: (key,operationKey,page) => set(state => {
    const draft=state.drafts[key]
    return !draft || draft.operationKey!==operationKey ? state : {drafts:{...state.drafts,[key]:{...draft,dirty:false,pageId:page.id,revision:page.revision}}}
  }),
  remove: key => set(state => ({drafts: Object.fromEntries(Object.entries(state.drafts).filter(([name]) => name !== key))})),
  clear: () => set({drafts:{}}),
}))

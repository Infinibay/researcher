import { useState } from 'react'
import { useProjectStore } from '../../stores/project'
import { useWikiPages, useWikiPage, useWikiSearch, useCreateWikiPage, useUpdateWikiPage, useDeleteWikiPage } from '../../hooks/useWiki'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { EmptyState } from '../common/EmptyState'
import { ConfirmDialog } from '../common/ConfirmDialog'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { WikiTree } from '../wiki/WikiTree'
import { formatRelative } from '../../utils/date'

export function WikiPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [editTitle, setEditTitle] = useState('')

  // New page form
  const [showNewPage, setShowNewPage] = useState(false)
  const [newPath, setNewPath] = useState('/')
  const [newTitle, setNewTitle] = useState('')
  const [newContent, setNewContent] = useState('')
  const [deletePath, setDeletePath] = useState<string | null>(null)

  const { data: pages, isLoading } = useWikiPages(projectId)
  const { data: page } = useWikiPage(projectId, selectedPath)
  const { data: searchResults } = useWikiSearch(projectId, searchQuery)
  const createPage = useCreateWikiPage()
  const updatePage = useUpdateWikiPage()
  const deletePage = useDeleteWikiPage()

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  const handleStartEdit = () => {
    if (!page) return
    setEditTitle(page.title)
    setEditContent(page.content ?? '')
    setEditing(true)
  }

  const handleSave = () => {
    if (!projectId || !selectedPath) return
    updatePage.mutate(
      { projectId, path: selectedPath, title: editTitle, content: editContent },
      { onSuccess: () => setEditing(false) },
    )
  }

  const handleCreatePage = () => {
    if (!projectId || !newPath.trim() || !newContent.trim()) return
    createPage.mutate(
      { project_id: projectId, path: newPath.trim(), title: newTitle.trim() || undefined, content: newContent },
      {
        onSuccess: () => {
          setSelectedPath(newPath.trim())
          setShowNewPage(false)
          setNewPath('/')
          setNewTitle('')
          setNewContent('')
        },
      },
    )
  }

  return (
    <div className="flex h-full gap-4">
      {/* Sidebar */}
      <div className="flex w-64 shrink-0 flex-col rounded-lg border border-surface-700 bg-surface-800">
        <div className="border-b border-surface-700 p-3 space-y-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search wiki..."
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
          <button
            onClick={() => setShowNewPage(!showNewPage)}
            className="w-full rounded-md bg-sky-600/20 px-2 py-1 text-xs font-medium text-sky-300 hover:bg-sky-600/30"
          >
            + New Page
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
          ) : searchQuery.length >= 2 && searchResults ? (
            <div className="py-2">
              {searchResults.length === 0 ? (
                <p className="px-3 text-xs text-slate-500">No results</p>
              ) : (
                searchResults.map((r) => (
                  <button
                    key={r.path}
                    onClick={() => { setSelectedPath(r.path); setSearchQuery('') }}
                    className="flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-surface-700/50"
                  >
                    <span className="font-medium text-slate-300">{r.title}</span>
                    {r.snippet && <span className="text-xs text-slate-500 line-clamp-1">{r.snippet}</span>}
                  </button>
                ))
              )}
            </div>
          ) : (
            <WikiTree pages={pages ?? []} selectedPath={selectedPath ?? ''} onSelect={setSelectedPath} />
          )}
        </div>
        <div className="border-t border-surface-700 p-2 text-center text-xs text-slate-600">
          {pages?.length ?? 0} pages
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col rounded-lg border border-surface-700 bg-surface-800">
        {showNewPage ? (
          <div className="p-4 space-y-3">
            <h3 className="text-lg font-semibold text-slate-200">New Page</h3>
            <input
              type="text"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              placeholder="/path/to/page"
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            />
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Page title"
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            />
            <textarea
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder="Write markdown content..."
              rows={12}
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none font-mono"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreatePage}
                disabled={!newPath.trim() || !newContent.trim() || createPage.isPending}
                className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
              >
                Create
              </button>
              <button
                onClick={() => setShowNewPage(false)}
                className="rounded-md px-4 py-2 text-sm text-slate-400 hover:bg-surface-700"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : !selectedPath || !page ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-sm text-slate-500">Select a page from the sidebar</p>
          </div>
        ) : editing ? (
          <div className="flex flex-1 flex-col p-4 space-y-3">
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 focus:border-sky-500/50 focus:outline-none"
            />
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              rows={20}
              className="flex-1 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 focus:border-sky-500/50 focus:outline-none font-mono"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={updatePage.isPending}
                className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-md px-4 py-2 text-sm text-slate-400 hover:bg-surface-700"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between border-b border-surface-700 p-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">{page.title}</h2>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>{page.path}</span>
                  {page.updated_by && <span>by {page.updated_by}</span>}
                  {page.updated_at && <span>{formatRelative(page.updated_at)}</span>}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleStartEdit}
                  className="rounded-md px-3 py-1.5 text-sm font-medium text-sky-400 hover:bg-sky-500/10"
                >
                  Edit
                </button>
                <button
                  onClick={() => setDeletePath(page.path)}
                  className="rounded-md px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/10"
                >
                  Delete
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <MarkdownRenderer content={page.content ?? ''} />
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        open={deletePath != null}
        title="Delete Wiki Page"
        message="Are you sure you want to delete this page?"
        confirmLabel="Delete"
        danger
        onConfirm={() => {
          if (deletePath && projectId) {
            deletePage.mutate(
              { projectId, path: deletePath },
              {
                onSettled: () => {
                  setDeletePath(null)
                  setSelectedPath(null)
                },
              },
            )
          }
        }}
        onCancel={() => setDeletePath(null)}
      />
    </div>
  )
}

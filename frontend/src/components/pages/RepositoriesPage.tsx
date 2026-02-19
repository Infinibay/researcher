import { useState, useMemo, useEffect, useCallback } from 'react'
import { useProjectStore } from '../../stores/project'
import {
  useRepos,
  useRepoBranches,
  useRepoTree,
  useFileContent,
  usePRs,
  usePRComments,
  useCreateRepo,
  useCreatePRComment,
} from '../../hooks/useGit'
import { useSendMessage } from '../../hooks/useChat'
import { useAgents } from '../../hooks/useAgents'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ErrorMessage } from '../common/ErrorMessage'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { formatRelative } from '../../utils/date'
import type { Repository, RepoTreeEntry, PullRequest } from '../../types/api'

// ── Tree utilities ────────────────────────────────────────────────────────────

interface TreeNode {
  name: string
  path: string
  type: 'blob' | 'tree'
  children?: TreeNode[]
}

function buildTree(entries: RepoTreeEntry[]): TreeNode[] {
  const root: TreeNode[] = []
  const dirMap = new Map<string, TreeNode>()

  // Ensure a directory node exists for the given path, creating parent
  // directories on demand so the tree is correct regardless of API ordering.
  function ensureDir(dirPath: string): TreeNode {
    const existing = dirMap.get(dirPath)
    if (existing) return existing

    const parts = dirPath.split('/')
    const name = parts[parts.length - 1]
    const node: TreeNode = { name, path: dirPath, type: 'tree', children: [] }
    dirMap.set(dirPath, node)

    if (parts.length === 1) {
      root.push(node)
    } else {
      const parentPath = parts.slice(0, -1).join('/')
      const parent = ensureDir(parentPath)
      parent.children!.push(node)
    }

    return node
  }

  for (const entry of entries) {
    const parts = entry.path.split('/')
    const name = parts[parts.length - 1]

    if (entry.type === 'tree') {
      // Reuse or create the directory node
      const dir = ensureDir(entry.path)
      // Preserve the original name in case ensureDir already created it
      dir.name = name
    } else {
      const node: TreeNode = { name, path: entry.path, type: entry.type }
      if (parts.length === 1) {
        root.push(node)
      } else {
        const parentPath = parts.slice(0, -1).join('/')
        const parent = ensureDir(parentPath)
        parent.children!.push(node)
      }
    }
  }

  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'tree' ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    for (const n of nodes) {
      if (n.children) sort(n.children)
    }
  }
  sort(root)
  return root
}

// ── File extension → language for code blocks ─────────────────────────────────

function extToLang(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'tsx', js: 'javascript', jsx: 'jsx',
    py: 'python', rs: 'rust', go: 'go', java: 'java',
    json: 'json', yaml: 'yaml', yml: 'yaml', toml: 'toml',
    md: 'markdown', css: 'css', scss: 'scss', html: 'html',
    sql: 'sql', sh: 'bash', bash: 'bash', zsh: 'bash',
    dockerfile: 'dockerfile', xml: 'xml', svg: 'xml',
  }
  return map[ext] || ''
}

// ── PR status → badge variant ─────────────────────────────────────────────────

function prStatusVariant(status: string) {
  switch (status) {
    case 'pending': return 'warning'
    case 'approved': return 'success'
    case 'merged': return 'violet'
    case 'closed': return 'neutral'
    case 'rejected': return 'error'
    default: return 'neutral'
  }
}

// ── Modal wrapper ─────────────────────────────────────────────────────────────

function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-lg border border-surface-700 bg-surface-800 p-6 shadow-xl">
        <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  )
}

// ── Create Repo Modal ─────────────────────────────────────────────────────────

function CreateRepoModal({
  open,
  projectId,
  onClose,
  onCreated,
}: {
  open: boolean
  projectId: number
  onClose: () => void
  onCreated: (repo: Repository) => void
}) {
  const [name, setName] = useState('')
  const [localPath, setLocalPath] = useState('')
  const [defaultBranch, setDefaultBranch] = useState('main')
  const createRepo = useCreateRepo()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createRepo.mutate(
      { projectId, body: { name, local_path: localPath, default_branch: defaultBranch } },
      {
        onSuccess: (repo) => {
          setName('')
          setLocalPath('')
          setDefaultBranch('main')
          onCreated(repo)
          onClose()
        },
      },
    )
  }

  return (
    <Modal open={open} title="Create Repository" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">
            Repository name (lowercase, no spaces)
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">Local path</label>
          <input
            type="text"
            value={localPath}
            onChange={(e) => setLocalPath(e.target.value)}
            required
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">Default branch</label>
          <input
            type="text"
            value={defaultBranch}
            onChange={(e) => setDefaultBranch(e.target.value)}
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm font-medium text-slate-300 hover:bg-surface-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createRepo.isPending}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {createRepo.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
        {createRepo.isError && (
          <p className="text-sm text-red-400">{(createRepo.error as Error).message}</p>
        )}
      </form>
    </Modal>
  )
}

// ── Request Repo Modal ────────────────────────────────────────────────────────

function RequestRepoModal({
  open,
  projectId,
  onClose,
}: {
  open: boolean
  projectId: number
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [justification, setJustification] = useState('')
  const [sent, setSent] = useState(false)
  const sendMessage = useSendMessage()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage.mutate(
      {
        projectId,
        to_role: 'team_lead',
        message: `Repository request: name=${name}\ndescription=${description}\njustification=${justification}`,
      },
      {
        onSuccess: () => {
          setSent(true)
          setTimeout(() => {
            setSent(false)
            setName('')
            setDescription('')
            setJustification('')
            onClose()
          }, 1500)
        },
      },
    )
  }

  return (
    <Modal open={open} title="Request Repository" onClose={onClose}>
      {sent ? (
        <p className="py-4 text-center text-sm text-emerald-400">
          Request sent to team lead.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">
              Desired repository name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">
              Why do you need this repository?
            </label>
            <textarea
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm font-medium text-slate-300 hover:bg-surface-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={sendMessage.isPending}
              className="rounded-md border border-surface-600 bg-surface-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-surface-600 disabled:opacity-50"
            >
              {sendMessage.isPending ? 'Sending...' : 'Send Request'}
            </button>
          </div>
          {sendMessage.isError && (
            <p className="text-sm text-red-400">{(sendMessage.error as Error).message}</p>
          )}
        </form>
      )}
    </Modal>
  )
}

// ── Tree Node Renderer ────────────────────────────────────────────────────────

function TreeNodeView({
  node,
  expandedDirs,
  toggleDir,
  selectedFile,
  onSelectFile,
  depth = 0,
}: {
  node: TreeNode
  expandedDirs: Set<string>
  toggleDir: (path: string) => void
  selectedFile: string | null
  onSelectFile: (entry: TreeNode) => void
  depth?: number
}) {
  const isDir = node.type === 'tree'
  const isExpanded = expandedDirs.has(node.path)
  const isSelected = selectedFile === node.path

  return (
    <>
      <button
        onClick={() => (isDir ? toggleDir(node.path) : onSelectFile(node))}
        className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm transition-colors ${
          isSelected
            ? 'bg-sky-500/20 text-sky-300'
            : 'text-slate-300 hover:bg-surface-700/50'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          <svg className="h-4 w-4 shrink-0 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            {isExpanded ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            )}
          </svg>
        ) : (
          <svg className="h-4 w-4 shrink-0 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && isExpanded && node.children?.map((child) => (
        <TreeNodeView
          key={child.path}
          node={child}
          expandedDirs={expandedDirs}
          toggleDir={toggleDir}
          selectedFile={selectedFile}
          onSelectFile={onSelectFile}
          depth={depth + 1}
        />
      ))}
    </>
  )
}

// ── PR Detail (expanded) ──────────────────────────────────────────────────────

function PRDetail({ pr }: { pr: PullRequest }) {
  const { data: comments, isLoading } = usePRComments(pr.id)
  const createComment = useCreatePRComment()
  const [draft, setDraft] = useState('')

  const handlePost = () => {
    if (!draft.trim()) return
    createComment.mutate(
      { prId: pr.id, body: draft.trim() },
      { onSuccess: () => setDraft('') },
    )
  }

  return (
    <div className="mt-2 space-y-3 border-t border-surface-700 pt-3">
      {pr.summary && (
        <p className="text-xs text-slate-400">{pr.summary}</p>
      )}

      <div className="space-y-2">
        <h5 className="text-xs font-medium text-slate-400">Comments</h5>
        {isLoading && <LoadingSpinner size="sm" />}
        {comments && comments.length === 0 && (
          <p className="text-xs text-slate-600">No comments yet.</p>
        )}
        {comments?.map((c) => (
          <div key={c.id} className="rounded border border-surface-700 bg-surface-900 p-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200">{c.author}</span>
              <span className="text-xs text-slate-600">{formatRelative(c.created_at)}</span>
            </div>
            <p className="mt-1 text-xs text-slate-300">{c.body}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          placeholder="Add a comment..."
          className="w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
        />
        <button
          onClick={handlePost}
          disabled={!draft.trim() || createComment.isPending}
          className="rounded bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {createComment.isPending ? 'Posting...' : 'Post'}
        </button>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function RepositoriesPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)

  // Left panel state
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [selectedBranch, setSelectedBranch] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showRequestModal, setShowRequestModal] = useState(false)

  // Center panel state
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())

  // Right panel state
  const [expandedPrId, setExpandedPrId] = useState<number | null>(null)

  // Determine if a team_lead agent exists for this project
  const { data: agentsData } = useAgents(projectId)
  const hasTeamLead = useMemo(
    () => agentsData?.agents?.some((a) => a.role === 'team_lead') ?? false,
    [agentsData],
  )

  // Queries
  const { data: repos, isLoading: reposLoading, error: reposError, refetch: refetchRepos } = useRepos(projectId)
  const { data: branches } = useRepoBranches(selectedRepo?.name ?? null, projectId)
  const { data: treeEntries, isLoading: treeLoading } = useRepoTree(
    selectedRepo?.name ?? null,
    projectId,
    selectedBranch,
  )
  const { data: fileContent, isLoading: fileLoading } = useFileContent(
    selectedRepo?.name ?? null,
    projectId,
    selectedFilePath,
    selectedBranch,
  )
  const { data: allPRs } = usePRs(projectId)

  // Reset branch when repo changes
  useEffect(() => {
    if (selectedRepo) {
      setSelectedBranch(selectedRepo.default_branch)
      setSelectedFilePath(null)
      setExpandedDirs(new Set())
      setExpandedPrId(null)
    }
  }, [selectedRepo])

  // Filter PRs for selected repo
  const repoPRs = useMemo(
    () => allPRs?.filter((pr) => pr.repo_name === selectedRepo?.name) ?? [],
    [allPRs, selectedRepo],
  )

  const tree = useMemo(() => (treeEntries ? buildTree(treeEntries) : []), [treeEntries])

  const toggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const handleSelectFile = useCallback((node: TreeNode) => {
    setSelectedFilePath(node.path)
  }, [])

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  return (
    <>
      <div className="flex h-full gap-4 overflow-hidden">
        {/* ── Left Panel: Repos + Branches ── */}
        <div className="flex w-64 shrink-0 flex-col overflow-hidden rounded-lg border border-surface-700 bg-surface-800">
          <div className="flex items-center justify-between border-b border-surface-700 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-100">Repositories</h2>
            <div className="flex gap-1">
              {hasTeamLead && (
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="rounded px-2 py-1 text-xs font-medium text-sky-400 hover:bg-sky-500/10"
                >
                  + Create
                </button>
              )}
              <button
                onClick={() => setShowRequestModal(true)}
                className="rounded border border-surface-600 px-2 py-1 text-xs font-medium text-slate-400 hover:bg-surface-700"
              >
                Request
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {reposLoading && (
              <div className="flex justify-center py-8"><LoadingSpinner size="sm" /></div>
            )}
            {reposError && (
              <ErrorMessage message={(reposError as Error).message} retry={() => refetchRepos()} />
            )}
            {repos && repos.length === 0 && (
              <div className="px-4 py-8 text-center text-xs text-slate-500">No repositories yet.</div>
            )}
            {repos?.map((repo) => (
              <button
                key={repo.id}
                onClick={() => setSelectedRepo(repo)}
                className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors ${
                  selectedRepo?.id === repo.id
                    ? 'bg-sky-500/20 text-sky-300'
                    : 'text-slate-300 hover:bg-surface-700/50'
                }`}
              >
                <span className="truncate">{repo.name}</span>
                <Badge variant={repo.status === 'active' ? 'success' : 'neutral'}>
                  {repo.status}
                </Badge>
              </button>
            ))}

            {/* Branches sub-section */}
            {selectedRepo && branches && branches.length > 0 && (
              <div className="border-t border-surface-700 px-4 py-3">
                <h3 className="mb-2 text-xs font-medium text-slate-400">Branches</h3>
                <div className="flex flex-wrap gap-1">
                  {branches.map((b) => (
                    <button
                      key={b.name}
                      onClick={() => {
                        setSelectedBranch(b.name)
                        setSelectedFilePath(null)
                        setExpandedDirs(new Set())
                      }}
                      title={b.last_commit_date ? formatRelative(b.last_commit_date) : undefined}
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                        selectedBranch === b.name
                          ? 'bg-sky-500/20 text-sky-300'
                          : 'bg-surface-700 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {b.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Center Panel: File Tree + Viewer ── */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-surface-700 bg-surface-800">
          {!selectedRepo ? (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState title="Select a repository" description="Choose a repository from the left panel to browse its files." />
            </div>
          ) : (
            <>
              {/* Breadcrumb */}
              <div className="flex items-center gap-1 border-b border-surface-700 px-4 py-2 text-xs text-slate-400">
                <span className="font-medium text-slate-200">{selectedRepo.name}</span>
                <span>/</span>
                <span className="text-sky-400">{selectedBranch}</span>
                {selectedFilePath && (
                  <>
                    <span>/</span>
                    <span className="text-slate-300">{selectedFilePath}</span>
                  </>
                )}
              </div>

              <div className="flex flex-1 overflow-hidden">
                {/* File tree */}
                <div className="w-56 shrink-0 overflow-y-auto border-r border-surface-700 py-1">
                  {treeLoading && (
                    <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
                  )}
                  {tree.map((node) => (
                    <TreeNodeView
                      key={node.path}
                      node={node}
                      expandedDirs={expandedDirs}
                      toggleDir={toggleDir}
                      selectedFile={selectedFilePath}
                      onSelectFile={handleSelectFile}
                    />
                  ))}
                  {!treeLoading && tree.length === 0 && (
                    <p className="px-4 py-4 text-xs text-slate-600">No files found.</p>
                  )}
                </div>

                {/* File viewer */}
                <div className="flex-1 overflow-auto p-4">
                  {!selectedFilePath ? (
                    <EmptyState title="Select a file" description="Click a file in the tree to view its contents." />
                  ) : fileLoading ? (
                    <div className="flex justify-center py-8"><LoadingSpinner size="sm" /></div>
                  ) : fileContent ? (
                    selectedFilePath.endsWith('.md') ? (
                      <MarkdownRenderer content={fileContent.content} />
                    ) : (
                      <MarkdownRenderer
                        content={`\`\`\`${extToLang(selectedFilePath)}\n${fileContent.content}\n\`\`\``}
                      />
                    )
                  ) : null}
                </div>
              </div>
            </>
          )}
        </div>

        {/* ── Right Panel: Pull Requests ── */}
        <div className="flex w-80 shrink-0 flex-col overflow-hidden rounded-lg border border-surface-700 bg-surface-800">
          <div className="border-b border-surface-700 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-100">Pull Requests</h2>
          </div>

          <div className="flex-1 overflow-y-auto">
            {!selectedRepo ? (
              <div className="px-4 py-8 text-center text-xs text-slate-500">
                Select a repository to view PRs.
              </div>
            ) : repoPRs.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-slate-500">
                No pull requests for this repository.
              </div>
            ) : (
              repoPRs.map((pr) => (
                <div key={pr.id} className="border-b border-surface-700 px-4 py-3">
                  <button
                    onClick={() => setExpandedPrId(expandedPrId === pr.id ? null : pr.id)}
                    className="flex w-full items-center justify-between text-left"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-200">{pr.branch}</p>
                      {pr.created_at && (
                        <p className="text-xs text-slate-500">{formatRelative(pr.created_at)}</p>
                      )}
                    </div>
                    <Badge variant={prStatusVariant(pr.status)}>{pr.status}</Badge>
                  </button>
                  {expandedPrId === pr.id && <PRDetail pr={pr} />}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      {projectId && (
        <>
          <CreateRepoModal
            open={showCreateModal}
            projectId={projectId}
            onClose={() => setShowCreateModal(false)}
            onCreated={(repo) => setSelectedRepo(repo)}
          />
          <RequestRepoModal
            open={showRequestModal}
            projectId={projectId}
            onClose={() => setShowRequestModal(false)}
          />
        </>
      )}
    </>
  )
}

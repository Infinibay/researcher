import { useState } from 'react'
import { useProjectStore } from '../../stores/project'
import { useFindings, useFindingsSearch } from '../../hooks/useFindings'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { formatRelative } from '../../utils/date'

const FINDING_TYPES = ['all', 'observation', 'hypothesis', 'experiment', 'proof', 'conclusion'] as const
const STATUSES = ['all', 'active', 'provisional', 'superseded'] as const

const TYPE_VARIANTS: Record<string, string> = {
  observation: 'neutral',
  hypothesis: 'info',
  experiment: 'warning',
  proof: 'success',
  conclusion: 'success',
}

const STATUS_VARIANTS: Record<string, string> = {
  active: 'success',
  provisional: 'warning',
  superseded: 'neutral',
}

export function FindingsPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState<'fts' | 'semantic'>('fts')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [minConfidence, setMinConfidence] = useState<string>('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const ftsFilters = {
    q: searchMode === 'fts' && searchQuery ? searchQuery : undefined,
    finding_type: typeFilter !== 'all' ? typeFilter : undefined,
    status: statusFilter !== 'all' ? statusFilter : undefined,
    min_confidence: minConfidence ? parseFloat(minConfidence) : undefined,
  }

  const { data: ftsResults, isLoading: ftsLoading } = useFindings(
    projectId,
    searchMode === 'fts' || !searchQuery ? ftsFilters : undefined,
  )
  const { data: semanticResults, isLoading: semanticLoading } = useFindingsSearch(
    searchMode === 'semantic' ? projectId : null,
    searchQuery,
  )

  const findings = searchMode === 'semantic' && searchQuery.length >= 3
    ? semanticResults
    : ftsResults
  const isLoading = searchMode === 'semantic' ? semanticLoading : ftsLoading

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-100">Findings</h1>

      {/* Search bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={searchMode === 'fts' ? 'Search findings...' : 'Semantic search (min 3 chars)...'}
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
        </div>
        <div className="flex rounded-md border border-surface-700 overflow-hidden">
          <button
            onClick={() => setSearchMode('fts')}
            className={`px-3 py-2 text-xs font-medium ${
              searchMode === 'fts'
                ? 'bg-sky-500/20 text-sky-300'
                : 'text-slate-400 hover:bg-surface-700'
            }`}
          >
            FTS
          </button>
          <button
            onClick={() => setSearchMode('semantic')}
            className={`px-3 py-2 text-xs font-medium ${
              searchMode === 'semantic'
                ? 'bg-sky-500/20 text-sky-300'
                : 'text-slate-400 hover:bg-surface-700'
            }`}
          >
            Semantic
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">Type:</span>
          {FINDING_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                typeFilter === t
                  ? 'bg-sky-500/20 text-sky-300'
                  : 'text-slate-400 hover:bg-surface-700'
              }`}
            >
              {t === 'all' ? 'All' : t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">Status:</span>
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                statusFilter === s
                  ? 'bg-sky-500/20 text-sky-300'
                  : 'text-slate-400 hover:bg-surface-700'
              }`}
            >
              {s === 'all' ? 'All' : s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">Min confidence:</span>
          <input
            type="number"
            value={minConfidence}
            onChange={(e) => setMinConfidence(e.target.value)}
            placeholder="0.0"
            min="0"
            max="1"
            step="0.1"
            className="w-16 rounded-md border border-surface-700 bg-surface-900 px-2 py-0.5 text-xs text-slate-300 focus:border-sky-500/50 focus:outline-none"
          />
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="flex justify-center py-8"><LoadingSpinner size="lg" /></div>
      ) : !findings || findings.length === 0 ? (
        <EmptyState title="No findings" description="No findings match your criteria." />
      ) : (
        <div className="space-y-2">
          {findings.map((f) => {
            const isExpanded = expandedId === f.id
            let sources: { url?: string; title?: string; name?: string }[] = []
            if (f.sources_json) {
              try { sources = JSON.parse(f.sources_json) } catch {}
            }

            return (
              <div key={f.id} className="rounded-lg border border-surface-700 bg-surface-800 overflow-hidden">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : f.id)}
                  className="flex w-full items-center gap-3 p-3 text-left hover:bg-surface-700/50"
                >
                  <svg
                    className={`h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path d="M6 6l8 4-8 4V6z" />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-200">{f.topic}</span>
                      {f.finding_type && (
                        <Badge variant={TYPE_VARIANTS[f.finding_type] || 'neutral'}>{f.finding_type}</Badge>
                      )}
                      {f.status && (
                        <Badge variant={STATUS_VARIANTS[f.status] || 'neutral'}>{f.status}</Badge>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-500">
                      <span>{f.agent_id}</span>
                      {f.created_at && <span>{formatRelative(f.created_at)}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {f.confidence != null && (
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-700">
                          <div
                            className="h-full rounded-full bg-emerald-500"
                            style={{ width: `${Math.round(f.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500">{Math.round(f.confidence * 100)}%</span>
                      </div>
                    )}
                    {f.similarity != null && f.similarity > 0 && (
                      <span className="text-xs text-sky-400">{Math.round(f.similarity * 100)}% match</span>
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-surface-700 p-4 space-y-3">
                    <div className="text-sm text-slate-300">
                      <MarkdownRenderer content={f.content} />
                    </div>
                    {sources.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Sources</h4>
                        <ul className="space-y-0.5">
                          {sources.map((src, i) => (
                            <li key={i} className="text-xs text-slate-400">
                              {src.url ? (
                                <a
                                  href={src.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sky-400 hover:underline"
                                >
                                  {src.title || src.name || src.url}
                                </a>
                              ) : (
                                <span>{src.title || src.name || JSON.stringify(src)}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

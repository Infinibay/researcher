import { useState } from 'react'
import { useProjectStore } from '../../stores/project'
import { useArtifacts, useArtifact } from '../../hooks/useArtifacts'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { formatRelative } from '../../utils/date'

const TYPE_FILTERS = ['all', 'report', 'code', 'data', 'diagram'] as const
const TYPE_VARIANTS: Record<string, string> = {
  report: 'info',
  code: 'warning',
  data: 'neutral',
  diagram: 'success',
}

export function ReportsPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: artifacts, isLoading } = useArtifacts(
    projectId,
    typeFilter === 'all' ? undefined : typeFilter,
  )
  const { data: detail } = useArtifact(selectedId)

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  return (
    <div className="flex h-full gap-4">
      {/* Left sidebar */}
      <div className="flex w-72 shrink-0 flex-col rounded-lg border border-surface-700 bg-surface-800">
        <div className="border-b border-surface-700 p-3 space-y-2">
          <h3 className="text-sm font-semibold text-slate-200">Reports & Artifacts</h3>
          <div className="flex flex-wrap gap-1">
            {TYPE_FILTERS.map((t) => (
              <button
                key={t}
                onClick={() => { setTypeFilter(t); setSelectedId(null) }}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                  typeFilter === t
                    ? 'bg-sky-500/20 text-sky-300'
                    : 'text-slate-400 hover:bg-surface-700 hover:text-slate-200'
                }`}
              >
                {t === 'all' ? 'All' : t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
          ) : !artifacts || artifacts.length === 0 ? (
            <p className="px-3 py-4 text-xs text-slate-500">No artifacts found</p>
          ) : (
            artifacts.map((a) => (
              <button
                key={a.id}
                onClick={() => setSelectedId(a.id)}
                className={`flex w-full flex-col items-start gap-1 border-b border-surface-700 px-3 py-2.5 text-left transition-colors ${
                  selectedId === a.id
                    ? 'bg-sky-500/10 border-l-2 border-l-sky-500'
                    : 'hover:bg-surface-700/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Badge variant={TYPE_VARIANTS[a.type] || 'neutral'}>{a.type}</Badge>
                  <span className="text-xs text-slate-500">{a.created_at ? formatRelative(a.created_at) : ''}</span>
                </div>
                <span className="text-sm font-medium text-slate-300 line-clamp-1">{a.file_path}</span>
                {a.description && (
                  <span className="text-xs text-slate-500 line-clamp-1">{a.description}</span>
                )}
              </button>
            ))
          )}
        </div>
        <div className="border-t border-surface-700 p-2 text-center text-xs text-slate-600">
          {artifacts?.length ?? 0} artifacts
        </div>
      </div>

      {/* Right panel */}
      <div className="flex flex-1 flex-col rounded-lg border border-surface-700 bg-surface-800">
        {!selectedId || !detail ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-sm text-slate-500">Select an artifact from the sidebar</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between border-b border-surface-700 p-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">{detail.file_path}</h2>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Badge variant={TYPE_VARIANTS[detail.type] || 'neutral'}>{detail.type}</Badge>
                  {detail.description && <span>{detail.description}</span>}
                  {detail.created_at && <span>{formatRelative(detail.created_at)}</span>}
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {detail.type === 'report' ? (
                <MarkdownRenderer content={detail.content ?? ''} />
              ) : (
                <pre className="overflow-x-auto rounded-md bg-surface-900 p-4 text-sm text-slate-300">
                  <code>{detail.content ?? ''}</code>
                </pre>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

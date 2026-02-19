import { useState } from 'react'
import type { WikiPage } from '../../types/api'

interface TreeNode {
  name: string
  path: string
  page?: WikiPage
  children: TreeNode[]
}

function buildTree(pages: WikiPage[]): TreeNode[] {
  const root: TreeNode[] = []
  const map = new Map<string, TreeNode>()

  const sorted = [...pages].sort((a, b) => a.path.localeCompare(b.path))

  for (const page of sorted) {
    const parts = page.path.replace(/^\//, '').split('/')
    let current = root
    let currentPath = ''

    for (let i = 0; i < parts.length; i++) {
      currentPath += '/' + parts[i]
      let node = map.get(currentPath)
      if (!node) {
        node = { name: parts[i], path: currentPath, children: [] }
        map.set(currentPath, node)
        current.push(node)
      }
      if (i === parts.length - 1) {
        node.page = page
      }
      current = node.children
    }
  }

  return root
}

function TreeItem({
  node,
  depth,
  selectedPath,
  onSelect,
}: {
  node: TreeNode
  depth: number
  selectedPath: string
  onSelect: (path: string) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children.length > 0
  const isSelected = node.path === selectedPath

  return (
    <div>
      <button
        onClick={() => {
          if (node.page) onSelect(node.path)
          if (hasChildren) setExpanded(!expanded)
        }}
        className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-sm ${
          isSelected ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400 hover:bg-surface-800 hover:text-slate-200'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren && (
          <svg
            className={`h-3 w-3 shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M6 6l8 4-8 4V6z" />
          </svg>
        )}
        {!hasChildren && <span className="w-3" />}
        <span className="truncate">{node.page?.title || node.name}</span>
      </button>
      {expanded &&
        node.children.map((child) => (
          <TreeItem
            key={child.path}
            node={child}
            depth={depth + 1}
            selectedPath={selectedPath}
            onSelect={onSelect}
          />
        ))}
    </div>
  )
}

export function WikiTree({
  pages,
  selectedPath,
  onSelect,
}: {
  pages: WikiPage[]
  selectedPath: string
  onSelect: (path: string) => void
}) {
  const tree = buildTree(pages)

  if (tree.length === 0) {
    return <div className="px-3 py-4 text-sm text-slate-500">No pages yet</div>
  }

  return (
    <div className="space-y-0.5 py-2">
      {tree.map((node) => (
        <TreeItem key={node.path} node={node} depth={0} selectedPath={selectedPath} onSelect={onSelect} />
      ))}
    </div>
  )
}

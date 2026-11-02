/** Render safe Markdown, optionally nesting document headings within an existing owner panel. @module */
import { createElement } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'

/** Keep document semantics while allowing embedded reports to respect their surrounding heading hierarchy. */
export function MarkdownRenderer({ content, headingBase }: { content: string; headingBase?: 1|2|3|4|5|6 }) {
  const headings: Components = {}
  if (headingBase) for (const level of [1,2,3,4,5,6] as const) {
    headings[`h${level}`] = ({ children }) => createElement(`h${Math.min(6, headingBase+level-1)}`, null, children)
  }
  return (
    <div className="prose prose-invert max-w-none prose-headings:text-slate-200 prose-p:text-slate-300 prose-a:text-sky-400 prose-strong:text-slate-200 prose-code:text-sky-300 prose-pre:bg-surface-900 prose-pre:border prose-pre:border-surface-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={{
          ...headings,
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target={href?.startsWith('http') ? '_blank' : undefined}
              rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
              {...props}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

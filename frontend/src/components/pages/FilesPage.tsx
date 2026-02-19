import { useState, useRef } from 'react'
import { useProjectStore } from '../../stores/project'
import { useFiles, useUploadFile, useDeleteFile, getDownloadUrl } from '../../hooks/useFiles'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ErrorMessage } from '../common/ErrorMessage'
import { EmptyState } from '../common/EmptyState'
import { ConfirmDialog } from '../common/ConfirmDialog'
import { formatFileSize } from '../../utils/file'
import { formatRelative } from '../../utils/date'

export function FilesPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data: files, isLoading, error, refetch } = useFiles(projectId)
  const uploadFile = useUploadFile()
  const deleteFile = useDeleteFile()
  const fileRef = useRef<HTMLInputElement>(null)

  const [description, setDescription] = useState('')
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }
  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
  if (error) return <ErrorMessage message={(error as Error).message} retry={() => refetch()} />

  const handleUpload = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0 || !projectId) return
    const file = fileList[0]
    uploadFile.mutate(
      { projectId, file, description: description.trim() || undefined },
      { onSuccess: () => setDescription('') },
    )
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    handleUpload(e.dataTransfer.files)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Files</h1>
      </div>

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
          dragging ? 'border-sky-500 bg-sky-500/5' : 'border-surface-700 bg-surface-800'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={(e) => handleUpload(e.target.files)}
        />
        <p className="text-sm text-slate-400">
          Drag & drop a file here or{' '}
          <button onClick={() => fileRef.current?.click()} className="font-medium text-sky-400 hover:text-sky-300">
            browse
          </button>
        </p>
        <div className="mt-2 flex items-center justify-center gap-2">
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
        </div>
        {uploadFile.isPending && (
          <div className="mt-2 flex items-center justify-center gap-2 text-sm text-sky-400">
            <LoadingSpinner size="sm" /> Uploading...
          </div>
        )}
      </div>

      {/* File list */}
      {(!files || files.length === 0) ? (
        <EmptyState title="No files" description="Upload a reference file to get started." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-surface-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-surface-700 bg-surface-900">
              <tr>
                <th className="px-4 py-3 font-medium text-slate-400">Filename</th>
                <th className="px-4 py-3 font-medium text-slate-400">Size</th>
                <th className="px-4 py-3 font-medium text-slate-400">Type</th>
                <th className="px-4 py-3 font-medium text-slate-400">Description</th>
                <th className="px-4 py-3 font-medium text-slate-400">Uploaded</th>
                <th className="px-4 py-3 font-medium text-slate-400"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-700">
              {files.map((f) => (
                <tr key={f.id} className="bg-surface-800 hover:bg-surface-700/50">
                  <td className="px-4 py-3 text-slate-200">{f.filename}</td>
                  <td className="px-4 py-3 text-slate-400">{f.file_size != null ? formatFileSize(f.file_size) : '-'}</td>
                  <td className="px-4 py-3 text-slate-400">{f.mime_type || '-'}</td>
                  <td className="px-4 py-3 text-slate-400">{f.description || '-'}</td>
                  <td className="px-4 py-3 text-slate-500">{f.uploaded_at ? formatRelative(f.uploaded_at) : '-'}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <a
                        href={getDownloadUrl(f.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-sky-400 hover:text-sky-300"
                      >
                        Download
                      </a>
                      <button
                        onClick={() => setDeleteId(f.id)}
                        className="text-xs font-medium text-red-400 hover:text-red-300"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteId != null}
        title="Delete File"
        message="Are you sure you want to delete this file?"
        confirmLabel="Delete"
        danger
        onConfirm={() => {
          if (deleteId) deleteFile.mutate(deleteId, { onSettled: () => setDeleteId(null) })
        }}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  )
}

/** Project-scoped owner attachments; previews and uploads never dispatch an agent. @module */
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ownerFetch } from '../api/session'
import { fetchApi, buildUrl, ApiError } from '../api/client'
import type { ReferenceFile } from '../types/api'

/** Ephemeral extracted revision, deliberately without a persisted source identity. */
export interface ReferencePreview {
  file_id: number
  project_id: number
  title: string
  content: string
  content_sha256: string
  provenance: Record<string, unknown>
  previewed_at: number
  persisted_source: false
}

/** Durable owner mutation history; publication receipts describe a past result, not current file availability. */
export interface FileOperation {
  project_id: number
  operation_key: string
  kind: 'upload' | 'delete'
  state: 'pending' | 'published' | 'deleted' | 'abandoned'
  filename: string
  reference_id: number | null
  created_at: number
  updated_at: number
  receipt: ReferenceFile | null
}

/** Read paged operation history without retrying filesystem effects on navigation or refocus. */
export function useFileOperations(projectId: number) {
  return useInfiniteQuery({
    queryKey: ['file-operations', projectId],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => fetchApi<FileOperation[]>(buildUrl('/api/files/operations', { project_id: projectId, offset: pageParam, limit: 50 })),
    getNextPageParam: (page, _pages, offset) => page.length === 50 ? offset + 50 : undefined,
    select: data => ({ ...data, pages: data.pages.map(page => page.filter(row => row.project_id === projectId)) }),
  })
}

/** Recover or close one original scoped operation only after an explicit owner action. */
export function useRecoverFileOperation(projectId: number) {
  const qc = useQueryClient()
  return useMutation({
    retry: false,
    mutationFn: ({ operationKey, action }: { operationKey: string; action: 'reconcile' | 'abandon' }) => fetchApi<FileOperation>(buildUrl(`/api/files/operations/${encodeURIComponent(operationKey)}/${action}`, { project_id: projectId }), { method: 'POST' }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['file-operations', projectId] })
      qc.invalidateQueries({ queryKey: ['files', projectId] })
      qc.invalidateQueries({ queryKey: ['file', projectId] })
    },
  })
}

/** Page literal filename/description matches within the visible project. */
export function useFiles(projectId: number, query = '') {
  return useInfiniteQuery({
    queryKey: ['files', projectId, { q: query }],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => fetchApi<ReferenceFile[]>(buildUrl('/api/files', { project_id: projectId, q: query, offset: pageParam, limit: 50 })),
    getNextPageParam: (page, _pages, offset) => page.length === 50 ? offset + 50 : undefined,
    select: data => ({ ...data, pages: data.pages.map(page => page.filter(file => file.project_id === projectId)) }),
  })
}

/** Resolve metadata by both project and file, rejecting even a mismatched cached row. */
export function useFile(projectId: number, fileId: number | null) {
  return useQuery({
    queryKey: ['file', projectId, fileId],
    queryFn: () => fetchApi<ReferenceFile>(buildUrl(`/api/files/${fileId}`, { project_id: projectId })),
    enabled: fileId != null,
    select: file => {
      if (file.project_id !== projectId || file.id !== fileId) throw new Error('El adjunto no pertenece al proyecto visible.')
      return file
    },
  })
}

/** Extract only on explicit refetch; never start background PDF work on navigation/focus. */
export function useFilePreview(projectId: number, fileId: number) {
  return useQuery({
    queryKey: ['file-preview', projectId, fileId],
    queryFn: () => fetchApi<ReferencePreview>(buildUrl(`/api/files/${fileId}/preview`, { project_id: projectId })),
    enabled: false,
    retry: false,
    select: preview => {
      if (preview.project_id !== projectId || preview.file_id !== fileId || preview.persisted_source !== false) throw new Error('La previa no corresponde a este adjunto.')
      return preview
    },
  })
}

/** Translate failed binary/multipart responses into bounded owner-readable errors. */
async function fileError(response: Response): Promise<ApiError> {
  const labels: Record<number, string> = { 401: 'La sesión ha caducado. Vuelve a iniciar sesión.', 404: 'El adjunto o proyecto ya no está disponible.', 413: 'El archivo supera el límite de 1.000.000 bytes.', 422: 'No se pudo procesar el archivo o su ubicación.' }
  return new ApiError(response.status, labels[response.status] ?? 'No se pudo completar la operación. Vuelve a consultar antes de repetirla.')
}

/** Upload after explicit confirmation and invalidate only the originating project's catalog. */
export function useUploadFile() {
  const qc = useQueryClient()
  return useMutation({
    retry: false,
    mutationFn: async ({ projectId, file, description, operationKey }: { projectId: number; file: File; description?: string; operationKey: string }) => {
      const form = new FormData()
      form.append('file', file)
      form.append('operation_key', operationKey)
      if (description) form.append('description', description)
      const response = await ownerFetch(buildUrl('/api/files', { project_id: projectId }), { method: 'POST', body: form })
      if (!response.ok) throw await fileError(response)
      return response.json() as Promise<ReferenceFile>
    },
    onSettled: (_file, _error, input) => {
      qc.invalidateQueries({ queryKey: ['files', input.projectId] })
      qc.invalidateQueries({ queryKey: ['file-operations', input.projectId] })
    },
  })
}

/** Delete the selected project reference; captured research revisions are separate records. */
export function useDeleteFile() {
  const qc = useQueryClient()
  return useMutation({
    retry: false,
    mutationFn: ({ projectId, fileId }: { projectId: number; fileId: number }) => fetchApi<void>(buildUrl(`/api/files/${fileId}`, { project_id: projectId }), { method: 'DELETE' }),
    onSuccess: (_result, input) => {
      qc.removeQueries({ queryKey: ['file', input.projectId, input.fileId], exact: true })
      qc.removeQueries({ queryKey: ['file-preview', input.projectId, input.fileId], exact: true })
      qc.invalidateQueries({ queryKey: ['files', input.projectId] })
    },
    onSettled: (_result, _error, input) => {
      qc.invalidateQueries({ queryKey: ['files', input.projectId] })
      qc.invalidateQueries({ queryKey: ['file-operations', input.projectId] })
      qc.invalidateQueries({ queryKey: ['file', input.projectId, input.fileId] })
    },
  })
}

/** Preserve project identity in download links, including legacy large attachments. */
export function getDownloadUrl(fileId: number, projectId: number) {
  return buildUrl(`/api/files/${fileId}/download`, { project_id: projectId })
}

/** Download exact bytes through the owner session, surfacing failures in the inspector. */
export async function downloadReference(file: ReferenceFile): Promise<void> {
  const response = await ownerFetch(getDownloadUrl(file.id, file.project_id))
  if (!response.ok) throw await fileError(response)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = file.filename
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { ReferenceFile } from '../types/api'

export function useFiles(projectId: number | null) {
  return useQuery({
    queryKey: ['files', projectId],
    queryFn: () =>
      fetchApi<ReferenceFile[]>(
        buildUrl('/api/files', { project_id: projectId! }),
      ),
    enabled: projectId != null,
  })
}

export function useFile(fileId: number | null) {
  return useQuery({
    queryKey: ['file', fileId],
    queryFn: () => fetchApi<ReferenceFile>(`/api/files/${fileId}`),
    enabled: fileId != null,
  })
}

export function useUploadFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      projectId,
      file,
      description,
    }: {
      projectId: number
      file: File
      description?: string
    }) => {
      const form = new FormData()
      form.append('file', file)
      if (description) form.append('description', description)

      const res = await fetch(
        buildUrl('/api/files', { project_id: projectId }),
        { method: 'POST', body: form },
      )
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || res.statusText)
      }
      return res.json() as Promise<ReferenceFile>
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['files'] })
    },
  })
}

export function useDeleteFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<void>(`/api/files/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['files'] })
    },
  })
}

export function getDownloadUrl(fileId: number) {
  return `/api/files/${fileId}/download`
}

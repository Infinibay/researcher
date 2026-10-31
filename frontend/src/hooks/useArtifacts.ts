import { useQuery } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Artifact } from '../types/api'

export function useArtifacts(projectId: number | null, type?: string) {
  return useQuery({
    queryKey: ['artifacts', projectId, type],
    queryFn: () =>
      fetchApi<Artifact[]>(
        buildUrl('/api/artifacts', {
          project_id: projectId!,
          type: type || undefined,
        }),
      ),
    enabled: projectId != null,
  })
}

export function useArtifact(projectId: number | null, artifactId: number | null) {
  return useQuery({
    queryKey: ['artifact', projectId, artifactId],
    queryFn: () => fetchApi<Artifact>(buildUrl(`/api/artifacts/${artifactId}`, { project_id: projectId! })),
    enabled: projectId != null && artifactId != null,
  })
}

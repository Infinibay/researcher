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

export function useArtifact(artifactId: number | null) {
  return useQuery({
    queryKey: ['artifact', artifactId],
    queryFn: () => fetchApi<Artifact>(`/api/artifacts/${artifactId}`),
    enabled: artifactId != null,
  })
}

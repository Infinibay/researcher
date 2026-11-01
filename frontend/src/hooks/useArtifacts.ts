/** Project-isolated React Query readers for saved artifacts and paged citations. @module */

import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Artifact, ArtifactEvidencePage } from '../types/api'

/** Page the filtered catalog in batches of 50, keeping each project's cache separate. */
export function useArtifacts(projectId: number | null, type?: string, q = '', status?: string) {
  return useInfiniteQuery({
    queryKey: ['artifacts', projectId, { type, q, status }],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => fetchApi<Artifact[]>(buildUrl('/api/artifacts', { project_id: projectId!, type, q: q || undefined, research_status: status, limit: 50, offset: pageParam })),
    getNextPageParam: (last, pages) => last.length === 50 ? pages.reduce((count, page) => count + page.length, 0) : undefined,
    enabled: projectId != null,
    retry: 1,
  })
}

/** Fetch one saved body only after both project and artifact selection are available. */
export function useArtifact(projectId: number | null, artifactId: number | null) {
  return useQuery({
    queryKey: ['artifact', projectId, artifactId],
    queryFn: () => fetchApi<Artifact>(buildUrl(`/api/artifacts/${artifactId}`, { project_id: projectId! })),
    enabled: projectId != null && artifactId != null,
    retry: 1,
  })
}

/** Follow server citation cursors for reports; reading never requests a fresh capture. */
export function useArtifactEvidence(projectId: number, artifactId: number | null, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ['artifact-evidence', projectId, artifactId],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => fetchApi<ArtifactEvidencePage>(buildUrl(`/api/artifacts/${artifactId}/evidence`, { project_id: projectId, offset: pageParam })),
    getNextPageParam: last => last.next_offset ?? undefined,
    enabled: enabled && artifactId != null,
    retry: 1,
  })
}

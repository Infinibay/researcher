import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type {
  Repository,
  BranchDetail,
  RepoTreeEntry,
  FileContent,
  PullRequest,
  PRComment,
} from '../types/api'

export function useRepos(projectId: number | null) {
  return useQuery({
    queryKey: ['repos', projectId],
    queryFn: () =>
      fetchApi<Repository[]>(buildUrl('/api/git/repos', { project_id: projectId! })),
    enabled: projectId != null,
  })
}

export function useRepoBranches(repoName: string | null, projectId: number | null) {
  return useQuery({
    queryKey: ['repo-branches', repoName, projectId],
    queryFn: () =>
      fetchApi<BranchDetail[]>(
        buildUrl(`/api/git/repos/${repoName}/branches`, { project_id: projectId! }),
      ),
    enabled: repoName != null && projectId != null,
  })
}

export function useRepoTree(
  repoName: string | null,
  projectId: number | null,
  ref: string | null,
) {
  return useQuery({
    queryKey: ['repo-tree', repoName, projectId, ref],
    queryFn: () =>
      fetchApi<RepoTreeEntry[]>(
        buildUrl(`/api/git/repos/${repoName}/tree`, {
          project_id: projectId!,
          ref: ref!,
        }),
      ),
    enabled: repoName != null && projectId != null && ref != null,
  })
}

export function useFileContent(
  repoName: string | null,
  projectId: number | null,
  path: string | null,
  ref: string | null,
) {
  return useQuery({
    queryKey: ['file-content', repoName, projectId, path, ref],
    queryFn: () =>
      fetchApi<FileContent>(
        buildUrl(`/api/git/repos/${repoName}/contents`, {
          project_id: projectId!,
          path: path!,
          ref: ref!,
        }),
      ),
    enabled: repoName != null && projectId != null && path != null && ref != null,
  })
}

export function usePRs(projectId: number | null) {
  return useQuery({
    queryKey: ['prs', projectId],
    queryFn: () =>
      fetchApi<PullRequest[]>(buildUrl('/api/git/prs', { project_id: projectId! })),
    enabled: projectId != null,
  })
}

export function usePRComments(prId: number | null) {
  return useQuery({
    queryKey: ['pr-comments', prId],
    queryFn: () => fetchApi<PRComment[]>(`/api/git/prs/${prId}/comments`),
    enabled: prId != null,
  })
}

export function useCreateRepo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      body,
    }: {
      projectId: number
      body: { name: string; local_path: string; default_branch?: string }
    }) =>
      fetchApi<Repository>(buildUrl('/api/git/repos', { project_id: projectId }), {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['repos', vars.projectId] })
    },
  })
}

export function useCreatePRComment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ prId, body }: { prId: number; body: string }) =>
      fetchApi<PRComment>(`/api/git/prs/${prId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body }),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['pr-comments', vars.prId] })
    },
  })
}

/** Owner-authorized repository/history readers; old PR labels do not grant native publication authority. @module */
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

/** Read only the selected project repository register; choosing a source never initializes Git. */
export function useRepos(projectId: number | null) {
  return useQuery({
    queryKey: ['repos', projectId],
    queryFn: () =>
      fetchApi<Repository[]>(buildUrl('/api/git/repos', { project_id: projectId! })),
    enabled: projectId != null,
  })
}

/** Read branch observations for one URL-encoded source; its head must be pinned before immutable file reads. */
export function useRepoBranches(repoName: string | null, projectId: number | null, repositoryId: number) {
  return useQuery({
    queryKey: ['repo-branches', repoName, projectId, repositoryId],
    queryFn: () =>
      fetchApi<BranchDetail[]>(
        buildUrl(`/api/git/repos/${encodeURIComponent(repoName!)}/branches`, { project_id: projectId!, repository_id: repositoryId }),
      ),
    enabled: repoName != null && projectId != null,
  })
}

/** Read a source tree at the caller-selected revision; query identity includes project, source and revision. */
export function useRepoTree(
  repoName: string | null,
  projectId: number | null,
  ref: string | null,
  repositoryId: number,
) {
  return useQuery({
    queryKey: ['repo-tree', repoName, projectId, repositoryId, ref],
    queryFn: () =>
      fetchApi<RepoTreeEntry[]>(
        buildUrl(`/api/git/repos/${encodeURIComponent(repoName!)}/tree`, {
          project_id: projectId!,
          repository_id: repositoryId,
          ref: ref!,
        }),
      ),
    enabled: repoName != null && projectId != null && ref != null,
  })
}

/** Read one source path under the exact project/source/revision cache key without borrowing another file response. */
export function useFileContent(
  repoName: string | null,
  projectId: number | null,
  path: string | null,
  ref: string | null,
  repositoryId: number,
) {
  return useQuery({
    queryKey: ['file-content', repoName, projectId, repositoryId, path, ref],
    queryFn: () =>
      fetchApi<FileContent>(
        buildUrl(`/api/git/repos/${encodeURIComponent(repoName!)}/contents`, {
          project_id: projectId!,
          repository_id: repositoryId,
          path: path!,
          ref: ref!,
        }),
      ),
    enabled: repoName != null && projectId != null && path != null && ref != null,
  })
}

/** Read historical PR records scoped to the selected project, without granting current acceptance. */
export function usePRs(projectId: number | null) {
  return useQuery({
    queryKey: ['prs', projectId],
    queryFn: () =>
      fetchApi<PullRequest[]>(buildUrl('/api/git/prs', { project_id: projectId! })),
    enabled: projectId != null,
  })
}

/** Documentary navigation from a historical PR; byte availability, old authorship and current native acceptance remain separate. */
export interface PROwnerEntry {
  project_id: number | null
  task: { id: number; title: string; type: string } | null
  task_type_accepts_code_input: boolean
  native_admission_run_id: string | null
  recorded_worktrees: { source_id: string; label: string; availability: string }[]
  branch_id: number | null
  branch_snapshot_import: 'requires_owned_preparation' | 'requires_branch_record'
}

/** Read only the selected PR's scoped bridge; reading never starts inference or retries an owner effect. */
export function usePROwnerEntry(prId: number) {
  return useQuery({
    queryKey: ['pr-owner-entry', prId],
    queryFn: () => fetchApi<PROwnerEntry>(`/api/git/prs/${prId}/owner-entry`),
    retry: false,
  })
}

/** Read the original remote PR discussion; failed access remains an error, not an empty thread. */
export function usePRComments(prId: number | null) {
  return useQuery({
    queryKey: ['pr-comments', prId],
    queryFn: () => fetchApi<PRComment[]>(`/api/git/prs/${prId}/comments`),
    enabled: prId != null,
  })
}

/** Retain the old generic init consumer until explicit create/adopt/clone/repair replaces its backend; the selected explorer never calls it. */
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

/** Post one explicit owner annotation and refresh that original thread; transport failure does not prove the annotation was absent. */
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

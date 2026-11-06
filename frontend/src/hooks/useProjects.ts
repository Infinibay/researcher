/** Project reads, owner mutations and the original native planning start lifecycle. @module */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { Project } from '../types/api'
import { useProjectStore } from '../stores/project'
import {useNavigate} from 'react-router-dom'
import {startProjectPlanning} from '../api/projectPlans'

/** Read the owner project register without starting any project work. */
export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => fetchApi<{ projects: Project[]; total: number }>('/api/projects'),
  })
}

/** Read exactly the selected project, keeping an absent selection idle. */
export function useProject(projectId: number | null) {
  return useQuery({
    queryKey: ['project', projectId],
    queryFn: () => fetchApi<Project>(`/api/projects/${projectId}`),
    enabled: projectId != null,
  })
}

/** Retain the compatible unkeyed creation hook; the dossier uses durable exact creation packets. */
export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      fetchApi<Project>('/api/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

/** Update only the owner-selected metadata, optionally guarding the exact scope shown by its editor. */
export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; name?: string; description?: string; status?: string; expected_scope_sha256?: string }) =>
      fetchApi<Project>(`/api/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['project', vars.id] })
    },
  })
}

/** Delete an explicitly selected unused project and clear its selection after the server confirms its history guard. */
export function useDeleteProject() {
  const qc = useQueryClient()
  const store = useProjectStore()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<void>(`/api/projects/${id}`, { method: 'DELETE' }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      if (store.activeProjectId === id) {
        store.setActiveProject(null)
      }
    },
  })
}

/** Start an original native plan and open its review only while its project remains selected. */
export function useStartProject() {
  const qc = useQueryClient(),navigate=useNavigate()
  const mutation=useMutation({
    mutationFn:(id:number)=>startProjectPlanning(sessionStorage,id),
    onSuccess:(receipt,id)=>{
      qc.invalidateQueries({queryKey:['projects']})
      qc.invalidateQueries({queryKey:['project',id]})
      qc.invalidateQueries({queryKey:['project-workspace',id]})
      if(useProjectStore.getState().activeProjectId===id)navigate(`/tasks?project=${id}&task=${receipt.planning_task_id}`)
    },
  })
  /** Expose an existing original start so reload does not disguise its retry as a fresh planning request. */
  function hasSavedStart(id:number){try{return typeof sessionStorage!=="undefined"&&sessionStorage.getItem(`researcher:project-plan-start:v1:${id}`)!==null}catch{return false}}
  return {...mutation,hasSavedStart}

}

/** Request the compatible legacy project control; native dossier Stop uses its frozen observed-target packet. */
export function useStopProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<any>(`/api/projects/${id}/stop`, { method: 'POST' }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

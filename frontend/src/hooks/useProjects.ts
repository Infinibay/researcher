/** Project reads, owner mutations and the original native planning start lifecycle. @module */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { Project } from '../types/api'
import { useProjectStore } from '../stores/project'
import {useNavigate} from 'react-router-dom'
import {startProjectPlanning} from '../api/projectPlans'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => fetchApi<{ projects: Project[]; total: number }>('/api/projects'),
  })
}

export function useProject(projectId: number | null) {
  return useQuery({
    queryKey: ['project', projectId],
    queryFn: () => fetchApi<Project>(`/api/projects/${projectId}`),
    enabled: projectId != null,
  })
}

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

export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; name?: string; description?: string; status?: string }) =>
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

/** Start one native project plan with persisted original intent and open its owner-review task, without legacy flow threads. */
export function useStartProject() {
  const qc = useQueryClient(),navigate=useNavigate(),setActiveProject=useProjectStore(state=>state.setActiveProject)
  const mutation=useMutation({
    mutationFn:(id:number)=>startProjectPlanning(sessionStorage,id),
    onSuccess:(receipt,id)=>{qc.invalidateQueries({queryKey:['projects']});qc.invalidateQueries({queryKey:['project',id]});setActiveProject(id);navigate(`/tasks?project=${id}&task=${receipt.planning_task_id}`)},
  })
  /** Expose an existing original start so reload does not disguise its retry as a fresh planning request. */
  function hasSavedStart(id:number){try{return typeof sessionStorage!=="undefined"&&sessionStorage.getItem(`researcher:project-plan-start:v1:${id}`)!==null}catch{return false}}
  return {...mutation,hasSavedStart}

}

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

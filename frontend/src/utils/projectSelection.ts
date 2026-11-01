/** Resolve deep links against the owner's visibly selected project. @module */

/** A URL may select an entity only inside the project visibly chosen by its owner. */
export function scopedEntityId(params: URLSearchParams, projectId: number | null, entity: 'artifact' | 'task' | 'fromArtifact' | 'file'): number | null {
  const id = Number(params.get(entity))
  return projectId != null && Number(params.get('project')) === projectId && Number.isSafeInteger(id) && id > 0 ? id : null
}

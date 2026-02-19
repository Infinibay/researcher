export function validateRequired(value: string): string | null {
  return value.trim() ? null : 'This field is required'
}

export function validateMinLength(value: string, min: number): string | null {
  return value.trim().length >= min ? null : `Must be at least ${min} characters`
}

export function validateMaxLength(value: string, max: number): string | null {
  return value.length <= max ? null : `Must be at most ${max} characters`
}

export function validatePath(path: string): string | null {
  if (!path.trim()) return 'Path is required'
  if (!path.startsWith('/')) return 'Path must start with /'
  if (/[^a-zA-Z0-9/_-]/.test(path)) return 'Path can only contain letters, numbers, /, _ and -'
  return null
}

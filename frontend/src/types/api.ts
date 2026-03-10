export interface Project {
  id: number
  name: string
  description?: string
  status: 'new' | 'planning' | 'executing' | 'paused' | 'completed' | 'failed'
  created_at?: string
  updated_at?: string
  completed_at?: string
  task_counts?: Record<string, number>
  total_tasks?: number
  total_epics?: number
}

export interface Epic {
  id: number
  project_id: number
  title: string
  description?: string
  status: 'open' | 'in_progress' | 'completed' | 'cancelled'
  priority: number
  created_by?: string
  created_at?: string
  updated_at?: string
  task_count?: number
  tasks_done?: number
  milestone_count?: number
}

export interface Milestone {
  id: number
  project_id: number
  epic_id: number
  title: string
  description?: string
  status: 'open' | 'in_progress' | 'completed' | 'cancelled'
  due_date?: string
  created_at?: string
  updated_at?: string
  task_count?: number
  tasks_done?: number
}

export interface Task {
  id: number
  project_id: number
  epic_id?: number
  milestone_id?: number
  type: 'code' | 'research' | 'investigation' | 'review' | 'test' | 'design' | 'integrate' | 'documentation' | 'bug_fix' | 'plan'
  status: 'backlog' | 'pending' | 'in_progress' | 'review_ready' | 'rejected' | 'done'
  title: string
  description?: string
  priority?: number
  estimated_complexity?: string
  assigned_to?: string
  reviewer?: string
  branch_name?: string
  created_by?: string
  created_at?: string
  updated_at?: string
  completed_at?: string
  retry_count?: number
}

export interface TaskComment {
  id: number
  task_id: number
  author: string
  comment_type: 'comment' | 'change_request' | 'approval'
  content: string
  created_at?: string
}

export interface TaskDependency {
  task_id: number
  depends_on_task_id: number
  dependency_type: 'blocks' | 'depends_on'
}

export interface ChatMessage {
  id: number
  project_id: number
  thread_id?: string
  from_agent: string
  to_agent?: string
  to_role?: string
  message: string
  conversation_type: string
  created_at?: string
}

export interface ChatThread {
  thread_id: string
  project_id: number
  thread_type?: string
  created_at?: string
  last_message?: string
  message_count?: number
}

export interface WikiPage {
  id?: number
  project_id?: number
  path: string
  title: string
  content?: string
  parent_path?: string
  created_by?: string
  updated_by?: string
  created_at?: string
  updated_at?: string
}

export interface WikiSearchResult {
  path: string
  title: string
  snippet?: string
  updated_at?: string
}

export interface ReferenceFile {
  id: number
  project_id: number
  filename: string
  filepath?: string
  file_size?: number
  mime_type?: string
  description?: string
  uploaded_at?: string
}

export interface EpicProgress {
  id: number
  title: string
  total: number
  done: number
  pct: number
}

export interface BlockingTaskInfo {
  id: number
  title: string
  status: string
}

export interface BlockedTask {
  id: number
  title: string
  status: string
  blocked_by: BlockingTaskInfo[]
}

export interface ProjectProgress {
  total_tasks: number
  done: number
  in_progress: number
  blocked: number
  blocked_tasks: BlockedTask[]
  completion_pct: number
  by_status: Record<string, number>
  epic_progress: EpicProgress[]
  milestone_progress: EpicProgress[]
}

export interface AgentCurrentRun {
  agent_run_id: string
  task_id: number
  task_title?: string
  started_at?: string
}

export interface AgentPerformance {
  successful_runs: number
  failed_runs: number
  total_tokens: number
  total_cost_usd: number
  avg_task_duration_s?: number
}

export interface Agent {
  agent_id: string
  name: string
  role: string
  status: 'idle' | 'active' | 'retired'
  total_runs: number
  created_at?: string
  last_active_at?: string
  current_run?: AgentCurrentRun
  performance?: AgentPerformance
}

export interface UserRequest {
  id: number
  project_id: number
  agent_id?: string
  agent_run_id?: string
  request_type: string
  title: string
  body: string
  options_json: string
  status: 'pending' | 'responded' | 'expired'
  response?: string
  created_at?: string
  responded_at?: string
}

export interface WSEvent {
  type: string
  project_id: number
  entity_type?: string
  entity_id?: number
  data?: any
  timestamp?: string
}

export interface AgentActivityEvent {
  id: string
  type: string
  timestamp: string
  from_agent?: string
  to_agent?: string
  to_role?: string
  content?: string
  kind?: string
  entity_id?: number
  task_title?: string
  branch_name?: string
}

export interface Repository {
  id: number
  project_id: number
  name: string
  local_path: string
  remote_url?: string
  default_branch: string
  status: string
  created_at?: string
}

export interface BranchDetail {
  name: string
  last_commit_sha?: string
  last_commit_message?: string
  last_commit_date?: string
  committer_name?: string
}

export interface PullRequest {
  id: number
  project_id?: number
  task_id?: number
  branch: string
  repo_name: string
  summary?: string
  status: string
  reviewer?: string
  comments?: string
  forgejo_pr_index?: number
  created_at?: string
  reviewed_at?: string
}

export interface PRComment {
  id: number
  author: string
  body: string
  created_at: string
  html_url?: string
}

export interface RepoTreeEntry {
  path: string
  type: 'blob' | 'tree'
  sha: string
  size?: number
}

export interface FileContent {
  path: string
  content: string
  sha: string
  size: number
  html_url?: string
}

export interface Finding {
  id: number
  project_id?: number
  task_id: number
  agent_run_id?: string
  topic: string
  content: string
  sources_json?: string
  confidence?: number
  agent_id: string
  status?: string
  finding_type?: string
  validation_method?: string
  reproducibility_score?: number
  created_at?: string
  similarity?: number
}

export interface Artifact {
  id: number
  project_id?: number
  task_id?: number
  type: string
  file_path: string
  description?: string
  content?: string
  created_at?: string
}

export interface FlowState {
  flow_name: string | null
  current_step: string | null
  subflow_name: string | null
  subflow_step: string | null
  state_summary: Record<string, unknown> | null
  updated_at: string | null
}

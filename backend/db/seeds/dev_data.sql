-- =============================================================================
-- PABADA v2 - Development Seed Data
-- Inserts sample data for development and testing.
-- Run after schema.sql has been applied.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Projects
-- ---------------------------------------------------------------------------
INSERT INTO projects (name, description, status, created_by, metadata_json)
VALUES (
    'Inventory API',
    'REST API for inventory management with JWT authentication, product CRUD, and category management.',
    'executing',
    'user',
    '{"framework": "FastAPI", "language": "python", "repo": "inventory-api"}'
);

INSERT INTO projects (name, description, status, created_by, metadata_json)
VALUES (
    'ML Research - Transformer Optimization',
    'Research project investigating efficient attention mechanisms for long-context transformers.',
    'planning',
    'user',
    '{"domain": "machine_learning", "target_conference": "NeurIPS 2026"}'
);

-- ---------------------------------------------------------------------------
-- Epics  (project 1)
-- ---------------------------------------------------------------------------
INSERT INTO epics (project_id, title, description, status, priority, order_index, created_by)
VALUES (1, 'Authentication System', 'JWT-based authentication with login, registration, and token refresh.', 'in_progress', 1, 1, 'team_lead');

INSERT INTO epics (project_id, title, description, status, priority, order_index, created_by)
VALUES (1, 'Product Management', 'Full CRUD operations for products with categories and search.', 'open', 2, 2, 'team_lead');

-- ---------------------------------------------------------------------------
-- Epics  (project 2)
-- ---------------------------------------------------------------------------
INSERT INTO epics (project_id, title, description, status, priority, order_index, created_by)
VALUES (2, 'Literature Review', 'Survey of existing efficient attention mechanisms.', 'open', 1, 1, 'team_lead');

-- ---------------------------------------------------------------------------
-- Milestones  (project 1, epic 1)
-- ---------------------------------------------------------------------------
INSERT INTO milestones (project_id, epic_id, title, description, status, order_index)
VALUES (1, 1, 'JWT Auth Core', 'Login and token generation endpoints.', 'in_progress', 1);

INSERT INTO milestones (project_id, epic_id, title, description, status, order_index)
VALUES (1, 1, 'Auth Middleware', 'Route protection middleware and role-based access.', 'open', 2);

-- ---------------------------------------------------------------------------
-- Milestones  (project 1, epic 2)
-- ---------------------------------------------------------------------------
INSERT INTO milestones (project_id, epic_id, title, description, status, order_index)
VALUES (1, 2, 'Product CRUD', 'Create, read, update, delete products.', 'open', 1);

-- ---------------------------------------------------------------------------
-- Milestones  (project 2, epic 3)
-- ---------------------------------------------------------------------------
INSERT INTO milestones (project_id, epic_id, title, description, status, order_index)
VALUES (2, 3, 'Survey Efficient Attention', 'Read and summarize papers on linear attention, sparse attention, and flash attention.', 'open', 1);

-- ---------------------------------------------------------------------------
-- Tasks  (project 1)
-- ---------------------------------------------------------------------------

-- Task 1: done
INSERT INTO tasks (project_id, epic_id, milestone_id, type, status, title, description, acceptance_criteria, priority, estimated_complexity, branch_name, assigned_to, reviewer, created_by, completed_at)
VALUES (1, 1, 1, 'code', 'done', 'Implement login endpoint',
    'Create POST /auth/login that validates credentials and returns JWT access + refresh tokens.',
    '- Returns 200 with tokens on valid credentials\n- Returns 401 on invalid credentials\n- Tokens include user_id and role claims',
    1, 'medium', 'task-1-implement-login', 'developer-1', 'code-reviewer-1', 'team_lead',
    DATETIME('now', '-2 days'));

-- Task 2: in_progress
INSERT INTO tasks (project_id, epic_id, milestone_id, type, status, title, description, acceptance_criteria, priority, estimated_complexity, branch_name, assigned_to, created_by)
VALUES (1, 1, 1, 'code', 'in_progress', 'Implement registration endpoint',
    'Create POST /auth/register for new user signup with email validation.',
    '- Validates email format and uniqueness\n- Hashes password with bcrypt\n- Returns 201 on success',
    1, 'medium', 'task-2-implement-registration', 'developer-1', 'team_lead');

-- Task 3: review_ready
INSERT INTO tasks (project_id, epic_id, milestone_id, type, status, title, description, acceptance_criteria, priority, estimated_complexity, branch_name, assigned_to, reviewer, created_by)
VALUES (1, 1, 1, 'code', 'review_ready', 'Implement token refresh endpoint',
    'Create POST /auth/refresh that accepts a refresh token and returns new access token.',
    '- Validates refresh token signature and expiry\n- Returns new access token\n- Rejects expired/invalid refresh tokens',
    2, 'low', 'task-3-token-refresh', 'developer-1', 'code-reviewer-1', 'team_lead');

-- Task 4: pending (depends on task 1)
INSERT INTO tasks (project_id, epic_id, milestone_id, type, status, title, description, acceptance_criteria, priority, estimated_complexity, assigned_to, created_by)
VALUES (1, 1, 2, 'code', 'pending', 'Implement auth middleware',
    'Create middleware that verifies JWT on protected routes and injects user context.',
    '- Extracts Bearer token from Authorization header\n- Verifies signature and expiry\n- Adds user object to request state',
    1, 'medium', 'developer-1', 'team_lead');

-- Task 5: backlog
INSERT INTO tasks (project_id, epic_id, milestone_id, type, status, title, description, priority, estimated_complexity, created_by)
VALUES (1, 2, 3, 'code', 'backlog', 'Implement product CRUD endpoints',
    'Create full CRUD for products: POST, GET, PUT, DELETE with pagination on list.',
    2, 'high', 'team_lead');

-- Task 6: research task for project 2
INSERT INTO tasks (project_id, epic_id, milestone_id, type, status, title, description, acceptance_criteria, priority, estimated_complexity, assigned_to, created_by)
VALUES (2, 3, 4, 'research', 'in_progress', 'Survey linear attention mechanisms',
    'Investigate linear attention variants: Performer, Linear Transformers, FNet. Compare theoretical complexity and practical benchmarks.',
    '- Cover at least 5 papers\n- Include complexity analysis O(n) vs O(n^2)\n- Benchmark comparison table',
    1, 'high', 'researcher-1', 'team_lead');

-- ---------------------------------------------------------------------------
-- Task Dependencies
-- ---------------------------------------------------------------------------
INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
VALUES (4, 1, 'blocks');

INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
VALUES (5, 4, 'blocks');

-- ---------------------------------------------------------------------------
-- Task Comments
-- ---------------------------------------------------------------------------
INSERT INTO task_comments (task_id, author, comment_type, content)
VALUES (1, 'developer-1', 'comment', 'Using PyJWT for token generation. Chose HS256 for simplicity, can upgrade to RS256 later.');

INSERT INTO task_comments (task_id, author, comment_type, content)
VALUES (1, 'code-reviewer-1', 'approval', 'LGTM. Clean implementation, good error handling. Token expiry defaults are reasonable.');

INSERT INTO task_comments (task_id, author, comment_type, content)
VALUES (3, 'code-reviewer-1', 'change_request', 'Please add rate limiting to the refresh endpoint to prevent token farming.');

INSERT INTO task_comments (task_id, author, comment_type, content)
VALUES (2, 'developer-1', 'question', 'Should we send a verification email on registration, or is that a separate task?');

INSERT INTO task_comments (task_id, author, comment_type, content)
VALUES (2, 'team_lead', 'answer', 'Email verification will be a separate task. For now, just create the account.');

-- ---------------------------------------------------------------------------
-- Branches
-- ---------------------------------------------------------------------------
INSERT INTO branches (project_id, task_id, repo_name, branch_name, base_branch, status, created_by, last_commit_hash, last_commit_at)
VALUES (1, 1, 'inventory-api', 'task-1-implement-login', 'main', 'merged', 'developer-1', 'a1b2c3d', DATETIME('now', '-2 days'));

INSERT INTO branches (project_id, task_id, repo_name, branch_name, base_branch, status, created_by, last_commit_hash, last_commit_at)
VALUES (1, 2, 'inventory-api', 'task-2-implement-registration', 'main', 'active', 'developer-1', 'e4f5g6h', DATETIME('now', '-1 hour'));

INSERT INTO branches (project_id, task_id, repo_name, branch_name, base_branch, status, created_by, last_commit_hash, last_commit_at)
VALUES (1, 3, 'inventory-api', 'task-3-token-refresh', 'main', 'active', 'developer-1', 'i7j8k9l', DATETIME('now', '-3 hours'));

-- ---------------------------------------------------------------------------
-- Reference Files
-- ---------------------------------------------------------------------------
INSERT INTO reference_files (project_id, file_name, file_path, file_type, file_size, description, uploaded_by, tags_json)
VALUES (1, 'api-spec.yaml', 'projects/1/refs/api-spec.yaml', 'application/yaml', 12400, 'OpenAPI 3.0 specification for the Inventory API.', 'user', '["api", "spec", "openapi"]');

INSERT INTO reference_files (project_id, file_name, file_path, file_type, file_size, description, uploaded_by, tags_json)
VALUES (2, 'attention-is-all-you-need.pdf', 'projects/2/refs/attention-is-all-you-need.pdf', 'application/pdf', 524000, 'Original Transformer paper (Vaswani et al., 2017).', 'user', '["paper", "transformer", "attention"]');

-- ---------------------------------------------------------------------------
-- Conversation Threads
-- ---------------------------------------------------------------------------
INSERT INTO conversation_threads (thread_id, project_id, task_id, thread_type, participants_json, status)
VALUES ('thread-task-1-review', 1, 1, 'code_review', '["developer-1", "code-reviewer-1"]', 'resolved');

INSERT INTO conversation_threads (thread_id, project_id, task_id, thread_type, participants_json, status)
VALUES ('thread-task-2-discussion', 1, 2, 'task_discussion', '["developer-1", "team_lead"]', 'active');

INSERT INTO conversation_threads (thread_id, project_id, thread_type, participants_json, status)
VALUES ('thread-project-1-general', 1, 'team_sync', '["project_lead", "team_lead", "developer-1"]', 'active');

-- ---------------------------------------------------------------------------
-- Chat Messages
-- ---------------------------------------------------------------------------
INSERT INTO chat_messages (project_id, thread_id, from_agent, to_agent, conversation_type, message, priority)
VALUES (1, 'thread-task-2-discussion', 'developer-1', 'team_lead', 'agent_to_agent',
    'Should we send a verification email on registration, or is that a separate task?', 1);

INSERT INTO chat_messages (project_id, thread_id, from_agent, to_agent, conversation_type, message, priority)
VALUES (1, 'thread-task-2-discussion', 'team_lead', 'developer-1', 'agent_to_agent',
    'Email verification will be a separate task. For now, just create the account.', 0);

INSERT INTO chat_messages (project_id, thread_id, from_agent, to_role, conversation_type, message, priority)
VALUES (1, 'thread-project-1-general', 'project_lead', NULL, 'broadcast',
    'User has approved the initial plan. Proceeding with Epic 1: Authentication System.', 2);

-- ---------------------------------------------------------------------------
-- Findings  (project 2)
-- ---------------------------------------------------------------------------
INSERT INTO findings (project_id, task_id, topic, content, sources_json, confidence, agent_id, status, finding_type)
VALUES (2, 6, 'Linear Attention Complexity',
    'Linear attention mechanisms (Performer, FNet) reduce self-attention complexity from O(n^2) to O(n) but trade off exact attention scores for approximations. Performer uses random feature maps; FNet replaces attention with FFT. Practical speedup varies: 2-5x for sequences > 2048 tokens, but accuracy drops 1-3% on downstream tasks.',
    '["https://arxiv.org/abs/2009.14794", "https://arxiv.org/abs/2105.03824"]',
    0.82, 'researcher-1', 'provisional', 'observation');

INSERT INTO findings (project_id, task_id, topic, content, sources_json, confidence, agent_id, status, finding_type)
VALUES (2, 6, 'Flash Attention Practicality',
    'Flash Attention (Dao et al., 2022) maintains exact attention while achieving 2-4x speedup via IO-aware tiling. Unlike linear attention, it does not approximate. Best suited for GPU training where memory bandwidth is the bottleneck. Widely adopted in production (PyTorch 2.0+, HuggingFace).',
    '["https://arxiv.org/abs/2205.14135", "https://arxiv.org/abs/2307.08691"]',
    0.91, 'researcher-1', 'active', 'conclusion');

-- ---------------------------------------------------------------------------
-- Agent Registry
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO agent_registry (id, role, status)
VALUES ('project_lead', 'Project Lead', 'alive');

INSERT OR IGNORE INTO agent_registry (id, role, status)
VALUES ('team_lead', 'Team Lead', 'alive');

INSERT OR IGNORE INTO agent_registry (id, role, status)
VALUES ('developer-1', 'Developer', 'alive');

INSERT OR IGNORE INTO agent_registry (id, role, status)
VALUES ('code-reviewer-1', 'Code Reviewer', 'alive');

INSERT OR IGNORE INTO agent_registry (id, role, status)
VALUES ('researcher-1', 'Researcher', 'alive');

INSERT OR IGNORE INTO agent_registry (id, role, status)
VALUES ('research-reviewer-1', 'Research Reviewer', 'alive');

-- ---------------------------------------------------------------------------
-- Roster
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO roster (agent_id, name, role, status, total_runs)
VALUES ('project_lead', 'Ada', 'Project Lead', 'active', 3);

INSERT OR IGNORE INTO roster (agent_id, name, role, status, total_runs)
VALUES ('team_lead', 'Bruno', 'Team Lead', 'active', 5);

INSERT OR IGNORE INTO roster (agent_id, name, role, status, total_runs)
VALUES ('developer-1', 'Carlos', 'Developer', 'active', 8);

INSERT OR IGNORE INTO roster (agent_id, name, role, status, total_runs)
VALUES ('code-reviewer-1', 'Diana', 'Code Reviewer', 'active', 4);

INSERT OR IGNORE INTO roster (agent_id, name, role, status, total_runs)
VALUES ('researcher-1', 'Elena', 'Researcher', 'active', 2);

INSERT OR IGNORE INTO roster (agent_id, name, role, status, total_runs)
VALUES ('research-reviewer-1', 'Felix', 'Research Reviewer', 'idle', 0);

-- ---------------------------------------------------------------------------
-- Events Log (sample)
-- ---------------------------------------------------------------------------
INSERT INTO events_log (project_id, event_type, event_source, entity_type, entity_id, event_data_json)
VALUES (1, 'project_created', 'user', 'project', 1, '{"name": "Inventory API"}');

INSERT INTO events_log (project_id, event_type, event_source, entity_type, entity_id, event_data_json)
VALUES (1, 'task_status_changed', 'system', 'task', 1, '{"old_status": "review_ready", "new_status": "done"}');

INSERT INTO events_log (project_id, event_type, event_source, entity_type, entity_id, event_data_json)
VALUES (2, 'project_created', 'user', 'project', 2, '{"name": "ML Research - Transformer Optimization"}');

-- ---------------------------------------------------------------------------
-- Knowledge  (project 2)
-- ---------------------------------------------------------------------------
INSERT INTO knowledge (project_id, category, key, value, agent_id, confidence)
VALUES (2, 'architecture', 'attention_types', 'Categorized as: exact (standard, flash), approximate (performer, linear), replacement (FNet/FFT). Flash attention is the current practical winner for exact attention.', 'researcher-1', 0.88);

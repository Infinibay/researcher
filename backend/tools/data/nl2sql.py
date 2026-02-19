"""Tool for executing read-only SQL queries against the project database."""

import logging
import re
import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool

logger = logging.getLogger(__name__)

# Statements that modify data or database structure
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REPLACE|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)

# Only SELECT and WITH (CTEs) are allowed as statement starters
_ALLOWED_STARTERS = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

_SCHEMA_DESCRIPTION = """\
Database tables (SQLite):
- projects (id, name, description, status, created_by, created_at, completed_at)
- epics (id, project_id, title, description, status, priority, order_index, created_by)
- milestones (id, project_id, epic_id, title, description, status, target_cycle, due_date)
- tasks (id, project_id, epic_id, milestone_id, parent_task_id, type, status, title, description, acceptance_criteria, priority, estimated_complexity, branch_name, assigned_to, reviewer, created_by, retry_count, created_at, completed_at)
- task_dependencies (id, task_id, depends_on_task_id, dependency_type)
- task_comments (id, task_id, author, comment_type, content, created_at)
- branches (id, project_id, task_id, repo_name, branch_name, base_branch, status, created_by, merged_at)
- repositories (id, project_id, name, local_path, remote_url, default_branch, status)
- conversation_threads (id, thread_id, project_id, task_id, thread_type, participants_json, status)
- chat_messages (id, project_id, thread_id, from_agent, to_agent, to_role, conversation_type, message, priority, created_at)
- message_reads (id, message_id, agent_id, read_at)
- reference_files (id, project_id, file_name, file_path, file_type, file_size, description, tags_json)
- findings (id, project_id, task_id, agent_run_id, topic, content, sources_json, confidence, agent_id, status, finding_type, validation_method, reproducibility_score, created_at)
- finding_deps (id, finding_id, depends_on_finding_id, relationship)
- knowledge (id, project_id, category, key, value, agent_id, confidence, created_at, updated_at)
- wiki_pages (id, project_id, path, title, content, parent_path, created_by, updated_by)
- agent_registry (id, role, task_description, container_id, status, registered_at, last_heartbeat)
- roster (agent_id, name, role, memory, status, total_runs, created_at, last_active_at)
- agent_runs (id, project_id, agent_run_id, agent_id, task_id, role, status, tokens_used, error_class, started_at, ended_at)
- agent_performance (id, agent_id, role, total_runs, successful_runs, failed_runs, total_tokens, total_cost_usd, avg_task_duration_s)
- status_updates (id, project_id, agent_id, agent_run_id, message, progress, created_at)
- events_log (id, project_id, event_type, event_source, entity_type, entity_id, event_data_json, created_at)
- artifacts (id, project_id, task_id, type, file_path, description, created_at)
- artifact_changes (id, project_id, agent_run_id, cycle, file_path, action, before_hash, after_hash, size_bytes)
- code_reviews (id, project_id, task_id, branch, agent_run_id, repo_name, summary, status, reviewer, comments)
- code_quality (id, project_id, cycle, file_path, syntax_ok, lint_issues, lint_output, test_count, test_pass, coverage)
- validation_results (id, project_id, cycle, file_path, result, error_output, attempt, file_mtime)
- processes (id, project_id, task_id, agent_run_id, command, pid, status, output_file, started_at, ended_at)
- user_requests (id, project_id, agent_id, agent_run_id, request_type, title, body, options_json, status, response)
- notices (id, project_id, title, content, priority, active, created_by, created_at, expires_at)
- brainstorm_sessions (id, project_id, topic, status, cycle, ideas_count, created_at, completed_at)
- convergence_log (id, project_id, iteration, total_tasks, completed_tasks, failed_tasks, new_tasks_this_cycle, total_findings, progress_score, strategy_note, decision, total_tokens, estimated_cost_usd)
- env_vars (id, name, value, is_secret)
- circuit_breaker (id, task_type, state, failure_count, last_failure_at, opened_at, threshold, window_seconds)
"""


class NL2SQLInput(BaseModel):
    sql_query: str = Field(
        ...,
        description="A SELECT SQL query to run against the project database.",
    )
    row_limit: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of rows to return (default 100, max 500).",
    )


class NL2SQLTool(PabadaBaseTool):
    name: str = "query_database"
    description: str = (
        "Execute a read-only SQL query against the PABADA project database. "
        "Only SELECT and WITH (CTE) statements are allowed. Use this for "
        "analytics: task progress, agent performance, finding statistics, "
        "project health metrics, etc.\n\n" + _SCHEMA_DESCRIPTION
    )
    args_schema: Type[BaseModel] = NL2SQLInput

    @staticmethod
    def _strip_sql_comments(sql: str) -> str:
        """Remove SQL comments (block and line) before keyword validation."""
        # Remove block comments /* ... */ (non-greedy, handles nested)
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        # Remove line comments -- ...
        sql = re.sub(r"--[^\n]*", " ", sql)
        return sql

    def _run(
        self,
        sql_query: str,
        row_limit: int = 100,
    ) -> str:
        # Strip comments BEFORE any validation to prevent bypass
        cleaned = self._strip_sql_comments(sql_query)

        # Validate: only SELECT/WITH allowed
        if not _ALLOWED_STARTERS.match(cleaned):
            return self._error(
                "Only SELECT and WITH (CTE) queries are allowed. "
                "Your query must start with SELECT or WITH."
            )

        # Check for forbidden keywords on comment-stripped query
        match = _FORBIDDEN_KEYWORDS.search(cleaned)
        if match:
            return self._error(
                f"Forbidden SQL keyword: {match.group(0)}. "
                "Only read-only queries (SELECT/WITH) are allowed."
            )

        # Clamp row limit
        row_limit = min(row_limit, settings.NL2SQL_MAX_ROW_LIMIT)

        # Append LIMIT if not already present (check on cleaned query)
        stripped = sql_query.rstrip().rstrip(";")
        if not re.search(r"\bLIMIT\b", cleaned, re.IGNORECASE):
            sql_query = f"{stripped} LIMIT {row_limit}"
        else:
            sql_query = stripped

        db_path = settings.DB_PATH

        try:
            # Open in read-only mode for double safety
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 5000")

            cursor = conn.execute(sql_query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(row_limit)

            result_rows = [dict(row) for row in rows]
            truncated = len(result_rows) >= row_limit

            conn.close()
        except sqlite3.OperationalError as e:
            return self._error(f"SQL error: {e}")
        except Exception as e:
            return self._error(f"Query execution failed: {e}")

        self._log_tool_usage(
            f"SQL query: {sql_query[:80]}... ({len(result_rows)} rows)"
        )

        return self._success({
            "query": sql_query,
            "column_names": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
            "truncated": truncated,
        })

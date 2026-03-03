"""Tool name mapping between CrewAI tools and Claude Code equivalents.

When ``engine=claude_code``, system prompts reference Claude Code's built-in
tools and the PABADA MCP server tools instead of PABADA's custom CrewAI tools.
"""

from __future__ import annotations

import re

# Maps PABADA CrewAI tool names → Claude Code equivalents
_CLAUDE_CODE_REFS: dict[str, str] = {
    # Code inspection
    "ReadFileTool": "Read (built-in)",
    "GlobTool": "Glob (built-in)",
    "ListDirectoryTool": "Bash: ls",
    "CodeSearchTool": "Grep (built-in)",
    # Code editing
    "EditFileTool": "Edit (built-in)",
    "WriteFileTool": "Write (built-in)",
    # Git
    "GitBranchTool": "Bash: git checkout -b ...",
    "GitCommitTool": "Bash: git add + git commit",
    "GitPushTool": "Bash: git push",
    "GitDiffTool": "Bash: git diff",
    "GitStatusTool": "Bash: git status",
    # Task management
    "TakeTaskTool": "mcp__pabada__task-take",
    "UpdateTaskStatusTool": "mcp__pabada__task-update-status",
    "GetTaskTool": "mcp__pabada__task-get",
    "ReadTasksTool": "mcp__pabada__task-list",
    "AddCommentTool": "mcp__pabada__task-add-comment",
    "CreateTaskTool": "mcp__pabada__task-create",
    "SetTaskDependenciesTool": "mcp__pabada__task-set-dependencies",
    "ApproveTaskTool": "mcp__pabada__task-approve",
    "RejectTaskTool": "mcp__pabada__task-reject",
    # Project structure
    "CreateEpicTool": "mcp__pabada__epic-create",
    "CreateMilestoneTool": "mcp__pabada__milestone-create",
    # Execution
    "ExecuteCommandTool": "Bash (built-in)",
    "CodeInterpreterTool": "Bash: python3 -c '...'",
    # Communication
    "AskTeamLeadTool": "mcp__pabada__chat-ask-team-lead",
    "AskProjectLeadTool": "mcp__pabada__chat-ask-project-lead",
    "SendMessageTool": "mcp__pabada__chat-send",
    "ReplyToUserTool": "mcp__pabada__chat-send (with to_agent='user')",
    "ReadMessagesTool": "mcp__pabada__chat-read",
    # Knowledge
    "RecordFindingTool": "mcp__pabada__finding-record",
    "ReadFindingsTool": "mcp__pabada__finding-read",
    "ReadWikiTool": "mcp__pabada__wiki-read",
    "WriteWikiTool": "mcp__pabada__wiki-write",
    # Analytics
    "NL2SQLTool": "mcp__pabada__query-database",
    # Web
    "WebSearchTool": "WebSearch (built-in)",
    "WebFetchTool": "WebFetch (built-in)",
    # Context7
    "Context7SearchTool": "mcp__plugin_context7_context7__resolve-library-id",
    "Context7DocsTool": "mcp__plugin_context7_context7__get-library-docs",
    # Semantic search
    "DirectorySearchTool": "Grep (built-in, with semantic keywords)",
    # Git PR
    "CreatePRTool": "mcp__pabada__create-pr",
    # Session
    "SaveSessionNoteTool": "mcp__pabada__session-save",
    "LoadSessionNoteTool": "mcp__pabada__session-load",
    # ── snake_case aliases (used in trimmed system prompts) ──
    "read_file": "Read (built-in)",
    "glob": "Glob (built-in)",
    "list_directory": "Bash: ls",
    "code_search": "Grep (built-in)",
    "edit_file": "Edit (built-in)",
    "write_file": "Write (built-in)",
    "git_branch": "Bash: git checkout -b ...",
    "git_commit": "Bash: git add + git commit",
    "git_push": "Bash: git push",
    "git_diff": "Bash: git diff",
    "git_status": "Bash: git status",
    "take_task": "mcp__pabada__task-take",
    "update_task_status": "mcp__pabada__task-update-status",
    "get_task": "mcp__pabada__task-get",
    "read_tasks": "mcp__pabada__task-list",
    "add_comment": "mcp__pabada__task-add-comment",
    "create_task": "mcp__pabada__task-create",
    "set_task_dependencies": "mcp__pabada__task-set-dependencies",
    "approve_task": "mcp__pabada__task-approve",
    "reject_task": "mcp__pabada__task-reject",
    "create_epic": "mcp__pabada__epic-create",
    "create_milestone": "mcp__pabada__milestone-create",
    "execute_command": "Bash (built-in)",
    "code_interpreter": "Bash: python3 -c '...'",
    "ask_team_lead": "mcp__pabada__chat-ask-team-lead",
    "ask_project_lead": "mcp__pabada__chat-ask-project-lead",
    "send_message": "mcp__pabada__chat-send",
    "reply_to_user": "mcp__pabada__chat-send (with to_agent='user')",
    "read_messages": "mcp__pabada__chat-read",
    "record_finding": "mcp__pabada__finding-record",
    "read_findings": "mcp__pabada__finding-read",
    "read_wiki": "mcp__pabada__wiki-read",
    "write_wiki": "mcp__pabada__wiki-write",
    "query_database": "mcp__pabada__query-database",
    "web_search": "WebSearch (built-in)",
    "web_fetch": "WebFetch (built-in)",
    "context7_search": "mcp__plugin_context7_context7__resolve-library-id",
    "context7_docs": "mcp__plugin_context7_context7__get-library-docs",
    "directory_search": "Grep (built-in, with semantic keywords)",
    "create_pr": "mcp__pabada__create-pr",
    "save_session_note": "mcp__pabada__session-save",
    "load_session_note": "mcp__pabada__session-load",
    "ask_user": "mcp__pabada__chat-send (with to_agent='user')",
    "create_repository": "mcp__pabada__create-repository",
    "read_reference_files": "mcp__pabada__reference-files-read",
    "read_report": "mcp__pabada__report-read",
    "update_project": "mcp__pabada__project-update",
}


def tool_ref(name: str, engine: str = "crewai") -> str:
    """Return the display name for a tool, adapted to the engine.

    For CrewAI, returns the original tool name.
    For Claude Code, returns the mapped equivalent.
    """
    if engine == "crewai":
        return name
    return _CLAUDE_CODE_REFS.get(name, name)


def adapt_prompt_for_engine(text: str, engine: str) -> str:
    """Replace CrewAI tool names in a prompt with their engine equivalents.

    Performs simple string substitution for known tool names when
    ``engine != "crewai"``. Safe to call with engine="crewai" (no-op).
    """
    if engine == "crewai":
        return text

    for crewai_name, cc_name in _CLAUDE_CODE_REFS.items():
        # Replace bold markdown references: **ToolName**
        text = text.replace(f"**{crewai_name}**", f"**{cc_name}**")
        # Replace plain references (word boundary aware)
        text = re.sub(rf'\b{re.escape(crewai_name)}\b', cc_name, text)

    return text


# ── Claude Code tools section for system prompts ─────────────────────────
# MCP tools are self-documenting via their schemas, so we only list
# the tool names grouped by category for quick reference.

CLAUDE_CODE_TOOLS_SECTION = """\
## PABADA MCP Tools

Project operations are available as MCP tools (auto-documented with schemas).
Use your standard built-in tools for files, git, and web operations.

**Task management:**
`task-get`, `task-list`, `task-create`, `task-update-status`, `task-take`,
`task-add-comment`, `task-set-dependencies`, `task-approve`, `task-reject`

**Project structure:** `epic-create`, `milestone-create`

**Communication:**
`chat-send`, `chat-read`, `chat-ask-team-lead`, `chat-ask-project-lead`

**Knowledge:**
`finding-record`, `finding-read`, `finding-validate`, `finding-reject`,
`wiki-read`, `wiki-write`

**Analytics:** `query-database`

**Git:** `create-pr`

**Session:** `session-save`, `session-load`
"""


# Regex that matches tools sections: XML <tools>...</tools> or markdown headers
_TOOLS_SECTION_RE = re.compile(
    r"(?:<tools>.*?</tools>|## (?:Available Tools|Herramientas Disponibles|Your Tools)\n.*?(?=\n## ))",
    re.DOTALL,
)


def strip_tools_section(prompt: str) -> str:
    """Replace the tools section (any language) with the MCP tools docs."""
    return _TOOLS_SECTION_RE.sub(CLAUDE_CODE_TOOLS_SECTION.rstrip(), prompt)

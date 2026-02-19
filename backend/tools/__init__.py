"""PABADA Tool Registry - exports all tools organized by category."""

from backend.tools.file import (
    ReadFileTool, WriteFileTool, EditFileTool,
    ListDirectoryTool, CodeSearchTool, GlobTool,
)
from backend.tools.git import (
    GitBranchTool, GitCommitTool, GitPushTool,
    GitDiffTool, GitStatusTool, CreatePRTool,
)
from backend.tools.task import (
    CreateTaskTool, TakeTaskTool, UpdateTaskStatusTool,
    AddCommentTool, GetTaskTool, ReadTasksTool,
    SetTaskDependenciesTool, ApproveTaskTool, RejectTaskTool,
)
from backend.tools.communication import (
    SendMessageTool, ReadMessagesTool, AskTeamLeadTool,
    AskProjectLeadTool, AskUserTool,
)
from backend.tools.web import WebSearchTool, WebFetchTool, ReadPaperTool
from backend.tools.shell import ExecuteCommandTool, CodeInterpreterTool
from backend.tools.data import NL2SQLTool
from backend.tools.rag import PDFSearchTool, DirectorySearchTool, CSVSearchTool
from backend.tools.memory import KnowledgeManagerTool
from backend.tools.knowledge import (
    RecordFindingTool, ReadFindingsTool, ValidateFindingTool,
    RejectFindingTool, ReadWikiTool, WriteWikiTool,
    WriteReportTool, ReadReportTool, SearchKnowledgeTool,
)
from backend.tools.project import (
    CreateEpicTool, CreateMilestoneTool, UpdateProjectTool,
    ReadReferenceFilesTool, CreateHypothesisTool,
)
from backend.tools.context7 import Context7SearchTool, Context7DocsTool

# ── Category dictionaries ───────────────────────────────────────────────────

FILE_TOOLS = [ReadFileTool, WriteFileTool, EditFileTool, ListDirectoryTool, CodeSearchTool, GlobTool]

GIT_TOOLS = [
    GitBranchTool, GitCommitTool, GitPushTool,
    GitDiffTool, GitStatusTool, CreatePRTool,
]

TASK_TOOLS = [
    CreateTaskTool, TakeTaskTool, UpdateTaskStatusTool,
    AddCommentTool, GetTaskTool, ReadTasksTool,
    SetTaskDependenciesTool, ApproveTaskTool, RejectTaskTool,
]

COMMUNICATION_TOOLS = [
    SendMessageTool, ReadMessagesTool, AskTeamLeadTool,
    AskProjectLeadTool, AskUserTool,
]

WEB_TOOLS = [WebSearchTool, WebFetchTool, ReadPaperTool]

SHELL_TOOLS = [ExecuteCommandTool, CodeInterpreterTool]

DATA_TOOLS = [NL2SQLTool]

RAG_TOOLS = [PDFSearchTool, DirectorySearchTool, CSVSearchTool]

CONTEXT7_TOOLS = [Context7SearchTool, Context7DocsTool]

MEMORY_TOOLS = [KnowledgeManagerTool]

KNOWLEDGE_TOOLS = [
    RecordFindingTool, ReadFindingsTool, ValidateFindingTool,
    RejectFindingTool, ReadWikiTool, WriteWikiTool,
    WriteReportTool, ReadReportTool, SearchKnowledgeTool,
]

PROJECT_TOOLS = [
    CreateEpicTool, CreateMilestoneTool, UpdateProjectTool,
    ReadReferenceFilesTool, CreateHypothesisTool,
]

ALL_TOOL_CLASSES = (
    FILE_TOOLS + GIT_TOOLS + TASK_TOOLS + COMMUNICATION_TOOLS +
    WEB_TOOLS + SHELL_TOOLS + MEMORY_TOOLS + KNOWLEDGE_TOOLS + PROJECT_TOOLS +
    DATA_TOOLS + RAG_TOOLS + CONTEXT7_TOOLS
)

# ── Role-based tool assignment ──────────────────────────────────────────────

_ROLE_TOOLS = {
    "project_lead": (
        COMMUNICATION_TOOLS + MEMORY_TOOLS +
        [UpdateProjectTool, ReadReferenceFilesTool] +
        [ReadFindingsTool, ReadWikiTool, ReadReportTool] +
        [WebSearchTool, WebFetchTool] +
        [NL2SQLTool]
    ),
    "team_lead": (
        TASK_TOOLS + COMMUNICATION_TOOLS + FILE_TOOLS + GIT_TOOLS +
        MEMORY_TOOLS + [ReadFindingsTool, ReadWikiTool] +
        [CreateEpicTool, CreateMilestoneTool] +
        [NL2SQLTool]
    ),
    "developer": (
        FILE_TOOLS + GIT_TOOLS + SHELL_TOOLS + MEMORY_TOOLS +
        [TakeTaskTool, UpdateTaskStatusTool, AddCommentTool, GetTaskTool, ReadTasksTool] +
        [SendMessageTool, ReadMessagesTool, AskTeamLeadTool] +
        [WebSearchTool, WebFetchTool] +
        [DirectorySearchTool] +
        CONTEXT7_TOOLS
    ),
    "code_reviewer": (
        FILE_TOOLS + [GitDiffTool, GitStatusTool] +
        [GetTaskTool, ReadTasksTool, ApproveTaskTool, RejectTaskTool, AddCommentTool] +
        [SendMessageTool, ReadMessagesTool] +
        MEMORY_TOOLS +
        [DirectorySearchTool] +
        CONTEXT7_TOOLS
    ),
    "researcher": (
        WEB_TOOLS + FILE_TOOLS + KNOWLEDGE_TOOLS + MEMORY_TOOLS +
        [CreateHypothesisTool] +
        [TakeTaskTool, UpdateTaskStatusTool, AddCommentTool, GetTaskTool, ReadTasksTool] +
        [SendMessageTool, ReadMessagesTool, AskTeamLeadTool] +
        [CodeInterpreterTool] + RAG_TOOLS +
        CONTEXT7_TOOLS
    ),
    "research_reviewer": (
        [ValidateFindingTool, RejectFindingTool, ReadFindingsTool] +
        [ReadWikiTool, ReadReportTool, SearchKnowledgeTool] +
        [GetTaskTool, ReadTasksTool, ApproveTaskTool, RejectTaskTool, AddCommentTool] +
        [SendMessageTool, ReadMessagesTool] +
        MEMORY_TOOLS +
        [PDFSearchTool] +
        CONTEXT7_TOOLS
    ),
}


def get_tools_for_role(role: str) -> list:
    """Return instantiated tool list for a given agent role.

    Args:
        role: One of 'project_lead', 'team_lead', 'developer',
              'code_reviewer', 'researcher', 'research_reviewer'.

    Returns:
        List of tool instances appropriate for the role.
    """
    tool_classes = _ROLE_TOOLS.get(role)
    if tool_classes is None:
        raise ValueError(
            f"Unknown role '{role}'. "
            f"Known roles: {', '.join(sorted(_ROLE_TOOLS.keys()))}"
        )
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for cls in tool_classes:
        if cls not in seen:
            seen.add(cls)
            unique.append(cls)
    return [cls() for cls in unique]


def get_all_tools() -> list:
    """Return instantiated list of all available tools."""
    return [cls() for cls in ALL_TOOL_CLASSES]

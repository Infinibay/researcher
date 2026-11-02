"""INFINIBAY Tool Registry - exports all tools organized by category."""

from backend.tools.communication import (
    AskProjectLeadTool,
    AskTeamLeadTool,
    AskUserTool,
    ReadMessagesTool,
    ReplyToUserTool,
    SendMessageTool,
)
from backend.tools.context7 import Context7DocsTool, Context7SearchTool
from backend.tools.data import NL2SQLTool
from backend.tools.file import (
    CodeSearchTool,
    EditFileTool,
    GlobTool,
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)
from backend.tools.git import (
    CreatePRTool,
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitPushTool,
    GitStatusTool,
    MergePRTool,
)
from backend.tools.knowledge import (
    ReadFindingReviewsTool,
    ReadFindingsTool,
    ReadReportTool,
    ReadWikiTool,
    RecordFindingTool,
    RejectFindingTool,
    SearchFindingsTool,
    SearchKnowledgeTool,
    SearchWikiTool,
    SummarizeFindingsTool,
    ValidateFindingTool,
    WriteReportTool,
    WriteWikiTool,
)
from backend.tools.project import (
    CreateEpicTool,
    CreateHypothesisTool,
    CreateMilestoneTool,
    CreateRepositoryTool,
    ReadEpicsTool,
    ReadMilestonesTool,
    ReadReferenceFilesTool,
    UpdateProjectTool,
)
from backend.tools.rag import (
    CSVSearchTool,
    DirectorySearchTool,
    DOCXSearchInfinibayTool,
    JSONSearchInfinibayTool,
    PDFSearchTool,
    XMLSearchInfinibayTool,
)
from backend.tools.shell import CodeInterpreterTool, ExecuteCommandTool
from backend.tools.task import (
    AddCommentTool,
    ApproveTaskTool,
    CheckDependenciesTool,
    CreateTaskTool,
    GetTaskTool,
    LoadSessionNoteTool,
    ReadCommentsTool,
    ReadTaskHistoryTool,
    ReadTasksTool,
    RejectTaskTool,
    SaveSessionNoteTool,
    SetTaskDependenciesTool,
    TakeTaskTool,
    UpdateTaskStatusTool,
)
from backend.tools.web import (
    CodeDocsSearchInfinibayTool,
    DeepWebResearchTool,
    ReadPaperTool,
    ScrapeWebsiteInfinibayTool,
    SpiderScrapeTool,
    WebFetchTool,
    WebSearchTool,
)

# ── Category dictionaries ───────────────────────────────────────────────────

FILE_TOOLS = [
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirectoryTool,
    CodeSearchTool,
    GlobTool,
]

GIT_TOOLS = [
    GitBranchTool,
    GitCommitTool,
    GitPushTool,
    GitDiffTool,
    GitStatusTool,
    CreatePRTool,
    MergePRTool,
]

TASK_TOOLS = [
    CreateTaskTool,
    TakeTaskTool,
    UpdateTaskStatusTool,
    AddCommentTool,
    ReadCommentsTool,
    GetTaskTool,
    ReadTasksTool,
    SetTaskDependenciesTool,
    ApproveTaskTool,
    RejectTaskTool,
    SaveSessionNoteTool,
    LoadSessionNoteTool,
    ReadTaskHistoryTool,
    CheckDependenciesTool,
]

COMMUNICATION_TOOLS = [
    SendMessageTool,
    ReadMessagesTool,
    AskTeamLeadTool,
    AskProjectLeadTool,
    AskUserTool,
    ReplyToUserTool,
]

WEB_TOOLS = [
    WebSearchTool,
    WebFetchTool,
    ReadPaperTool,
    DeepWebResearchTool,
    ScrapeWebsiteInfinibayTool,
    SpiderScrapeTool,
    CodeDocsSearchInfinibayTool,
]

SHELL_TOOLS = [ExecuteCommandTool, CodeInterpreterTool]

DATA_TOOLS = [NL2SQLTool]

RAG_TOOLS = [
    PDFSearchTool,
    DirectorySearchTool,
    CSVSearchTool,
    DOCXSearchInfinibayTool,
    JSONSearchInfinibayTool,
    XMLSearchInfinibayTool,
]

CONTEXT7_TOOLS = [Context7SearchTool, Context7DocsTool]

KNOWLEDGE_TOOLS = [
    RecordFindingTool,
    ReadFindingsTool,
    SearchFindingsTool,
    ValidateFindingTool,
    RejectFindingTool,
    ReadWikiTool,
    SearchWikiTool,
    WriteWikiTool,
    WriteReportTool,
    ReadReportTool,
    SearchKnowledgeTool,
    SummarizeFindingsTool,
    ReadFindingReviewsTool,
]

PROJECT_TOOLS = [
    CreateEpicTool,
    CreateMilestoneTool,
    CreateRepositoryTool,
    UpdateProjectTool,
    ReadReferenceFilesTool,
    CreateHypothesisTool,
    ReadEpicsTool,
    ReadMilestonesTool,
]

ALL_TOOL_CLASSES = (
    FILE_TOOLS
    + GIT_TOOLS
    + TASK_TOOLS
    + COMMUNICATION_TOOLS
    + WEB_TOOLS
    + SHELL_TOOLS
    + KNOWLEDGE_TOOLS
    + PROJECT_TOOLS
    + DATA_TOOLS
    + RAG_TOOLS
    + CONTEXT7_TOOLS
)

# ── Role-based tool assignment ──────────────────────────────────────────────

_ROLE_TOOLS = {
    "project_lead": (
        COMMUNICATION_TOOLS
        + [ReadFileTool, ListDirectoryTool]
        + [UpdateProjectTool, ReadReferenceFilesTool, CreateRepositoryTool]
        + [
            ReadFindingsTool,
            ReadFindingReviewsTool,
            SearchFindingsTool,
            ReadWikiTool,
            SearchWikiTool,
            ReadReportTool,
        ]
        + [WebSearchTool, WebFetchTool, ScrapeWebsiteInfinibayTool]
        + [MergePRTool]
        + [NL2SQLTool]
        + [ExecuteCommandTool, CodeInterpreterTool]
    ),
    "team_lead": (
        # Team Lead gets task management tools EXCEPT TakeTaskTool —
        # only developers/researchers claim tasks from the backlog.
        [
            CreateTaskTool,
            UpdateTaskStatusTool,
            AddCommentTool,
            ReadCommentsTool,
            GetTaskTool,
            ReadTasksTool,
            SetTaskDependenciesTool,
            ApproveTaskTool,
            RejectTaskTool,
            ReadTaskHistoryTool,
            CheckDependenciesTool,
        ]
        + COMMUNICATION_TOOLS
        + FILE_TOOLS
        + GIT_TOOLS
        + [
            ReadReferenceFilesTool,
            ReadFindingsTool,
            ReadFindingReviewsTool,
            SearchFindingsTool,
            ReadWikiTool,
            SearchWikiTool,
        ]
        + [CreateEpicTool, CreateMilestoneTool, ReadEpicsTool, ReadMilestonesTool]
        + [
            WebSearchTool,
            ScrapeWebsiteInfinibayTool,
            ExecuteCommandTool,
            CodeInterpreterTool,
        ]
        + [NL2SQLTool]
    ),
    "developer": (
        FILE_TOOLS
        + GIT_TOOLS
        + SHELL_TOOLS
        + [
            TakeTaskTool,
            UpdateTaskStatusTool,
            AddCommentTool,
            ReadCommentsTool,
            GetTaskTool,
            ReadTasksTool,
        ]
        + [
            SaveSessionNoteTool,
            LoadSessionNoteTool,
            ReadTaskHistoryTool,
            CheckDependenciesTool,
        ]
        + [SendMessageTool, ReadMessagesTool, AskTeamLeadTool, ReplyToUserTool]
        + [WebSearchTool, WebFetchTool]
        + [DirectorySearchTool, CodeDocsSearchInfinibayTool, ReadReferenceFilesTool]
        + CONTEXT7_TOOLS
    ),
    "code_reviewer": (
        FILE_TOOLS
        + [GitDiffTool, GitStatusTool]
        + [
            GetTaskTool,
            ReadTasksTool,
            ApproveTaskTool,
            RejectTaskTool,
            AddCommentTool,
            ReadCommentsTool,
        ]
        + [ReadTaskHistoryTool]
        + [SendMessageTool, ReadMessagesTool, ReplyToUserTool]
        + [DirectorySearchTool, ReadReferenceFilesTool]
        + CONTEXT7_TOOLS
        + [ExecuteCommandTool, CodeInterpreterTool]
    ),
    "researcher": (
        WEB_TOOLS
        + FILE_TOOLS
        + KNOWLEDGE_TOOLS
        + [CreateHypothesisTool, ReadReferenceFilesTool]
        + [
            TakeTaskTool,
            UpdateTaskStatusTool,
            AddCommentTool,
            ReadCommentsTool,
            GetTaskTool,
            ReadTasksTool,
        ]
        + [SaveSessionNoteTool, LoadSessionNoteTool, ReadTaskHistoryTool]
        + [SendMessageTool, ReadMessagesTool, AskTeamLeadTool, ReplyToUserTool]
        + [CodeInterpreterTool, ExecuteCommandTool]
        + RAG_TOOLS
        + CONTEXT7_TOOLS
    ),
    "research_reviewer": (
        [
            ValidateFindingTool,
            RejectFindingTool,
            ReadFindingsTool,
            ReadFindingReviewsTool,
            SearchFindingsTool,
            SummarizeFindingsTool,
            ReadFindingReviewsTool,
        ]
        + [
            ReadWikiTool,
            SearchWikiTool,
            ReadReportTool,
            SearchKnowledgeTool,
            ReadReferenceFilesTool,
        ]
        + [
            GetTaskTool,
            ReadTasksTool,
            ApproveTaskTool,
            RejectTaskTool,
            AddCommentTool,
            ReadCommentsTool,
        ]
        + [ReadTaskHistoryTool]
        + [SendMessageTool, ReadMessagesTool, ReplyToUserTool]
        + [PDFSearchTool]
        + CONTEXT7_TOOLS
        + [ExecuteCommandTool, CodeInterpreterTool]
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


# ── Task-type-specific tool subsets ──────────────────────────────────────────
#
# Use with ``build_crew(agent, prompt, task_tools=get_tools_for_task_type("implement"))``
# to narrow the tool set for a specific task, reducing confusion and improving
# tool selection speed.

_TASK_TYPE_TOOLS: dict[str, list] = {
    # Developer implementing code — needs file, git, shell, docs, web
    "implement": (
        FILE_TOOLS
        + GIT_TOOLS
        + SHELL_TOOLS
        + [UpdateTaskStatusTool, AddCommentTool, ReadCommentsTool, GetTaskTool]
        + [ReadTaskHistoryTool, CheckDependenciesTool]
        + [SendMessageTool, AskTeamLeadTool]
        + [
            WebSearchTool,
            WebFetchTool,
            DirectorySearchTool,
            CodeDocsSearchInfinibayTool,
            ReadReferenceFilesTool,
        ]
        + CONTEXT7_TOOLS
        + [SaveSessionNoteTool, LoadSessionNoteTool]
    ),
    # Developer reworking code after review — same as implement + session notes
    "rework": (
        FILE_TOOLS
        + GIT_TOOLS
        + SHELL_TOOLS
        + [UpdateTaskStatusTool, AddCommentTool, ReadCommentsTool, GetTaskTool]
        + [ReadTaskHistoryTool, CheckDependenciesTool]
        + [SendMessageTool, AskTeamLeadTool]
        + [
            WebSearchTool,
            WebFetchTool,
            DirectorySearchTool,
            CodeDocsSearchInfinibayTool,
            ReadReferenceFilesTool,
        ]
        + CONTEXT7_TOOLS
        + [SaveSessionNoteTool, LoadSessionNoteTool]
    ),
    # Code reviewer — needs read access, diff, approve/reject
    "review": (
        [
            ReadFileTool,
            ListDirectoryTool,
            CodeSearchTool,
            GlobTool,
            ReadReferenceFilesTool,
        ]
        + [GitDiffTool, GitStatusTool]
        + [
            GetTaskTool,
            ReadTasksTool,
            ApproveTaskTool,
            RejectTaskTool,
            AddCommentTool,
            ReadCommentsTool,
        ]
        + [ReadTaskHistoryTool]
        + [SendMessageTool, ReadMessagesTool]
        + [DirectorySearchTool]
        + CONTEXT7_TOOLS
        + [CodeInterpreterTool]
    ),
    # Researcher investigating — needs web, knowledge, file, code interpreter
    "research": (
        WEB_TOOLS
        + FILE_TOOLS
        + KNOWLEDGE_TOOLS
        + [CreateHypothesisTool, ReadReferenceFilesTool]
        + [GetTaskTool, UpdateTaskStatusTool, AddCommentTool, ReadCommentsTool]
        + [ReadTaskHistoryTool, SaveSessionNoteTool, LoadSessionNoteTool]
        + [SendMessageTool, AskTeamLeadTool]
        + [CodeInterpreterTool]
        + RAG_TOOLS
        + CONTEXT7_TOOLS
    ),
    # Team Lead creating plan — needs task mgmt, communication, knowledge
    "plan": (
        [GetTaskTool, ReadTasksTool]
        + [ReadTaskHistoryTool, CheckDependenciesTool]
        + COMMUNICATION_TOOLS
        + [
            ReadFindingsTool,
            ReadFindingReviewsTool,
            SearchFindingsTool,
            ReadWikiTool,
            SearchWikiTool,
            ReadReferenceFilesTool,
        ]
        + [ReadEpicsTool, ReadMilestonesTool]
        + [WebSearchTool, ExecuteCommandTool, CodeInterpreterTool, NL2SQLTool]
    ),
    # Team Lead creating tickets — needs project management tools
    "create_tickets": (
        [
            CreateTaskTool,
            UpdateTaskStatusTool,
            AddCommentTool,
            ReadCommentsTool,
            GetTaskTool,
            ReadTasksTool,
            SetTaskDependenciesTool,
        ]
        + [ReadTaskHistoryTool, CheckDependenciesTool]
        + COMMUNICATION_TOOLS
        + [CreateEpicTool, CreateMilestoneTool, ReadEpicsTool, ReadMilestonesTool]
        + [
            ReadFindingsTool,
            ReadFindingReviewsTool,
            SearchFindingsTool,
            ReadWikiTool,
            SearchWikiTool,
            ReadReportTool,
            ReadReferenceFilesTool,
        ]
        + [WebSearchTool, CodeInterpreterTool, NL2SQLTool]
    ),
    # Project Lead gathering requirements — needs communication, read access
    "requirements": (
        COMMUNICATION_TOOLS
        + [
            ReadReferenceFilesTool,
            ReadFindingsTool,
            ReadFindingReviewsTool,
            SearchFindingsTool,
            ReadWikiTool,
            SearchWikiTool,
            ReadReportTool,
        ]
        + [
            WebSearchTool,
            WebFetchTool,
            ScrapeWebsiteInfinibayTool,
            CodeInterpreterTool,
            NL2SQLTool,
        ]
    ),
}


def get_tools_for_task_type(task_type: str) -> list | None:
    """Return instantiated tool list for a specific task type.

    Args:
        task_type: One of 'implement', 'rework', 'review', 'research',
                   'plan', 'create_tickets', 'requirements'.

    Returns:
        List of tool instances, or None if task_type is unknown (caller
        should fall back to role-based tools).
    """
    tool_classes = _TASK_TYPE_TOOLS.get(task_type)
    if tool_classes is None:
        return None
    # Deduplicate while preserving order
    seen: set[type] = set()
    unique: list[type] = []
    for cls in tool_classes:
        if cls not in seen:
            seen.add(cls)
            unique.append(cls)
    return [cls() for cls in unique]

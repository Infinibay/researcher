"""Lazy compatibility exports for historical tool metadata.

Importing a database/context submodule must not initialize role tools, providers,
agent dispatch or optional legacy integrations. Explicit legacy metadata readers
still resolve the same exported names; native tools use their own scoped catalog.
"""

from importlib import import_module

_LEGACY_EXPORTS = ['ALL_TOOL_CLASSES', 'AddCommentTool', 'ApproveTaskTool', 'AskProjectLeadTool', 'AskTeamLeadTool', 'AskUserTool', 'COMMUNICATION_TOOLS', 'CONTEXT7_TOOLS', 'CSVSearchTool', 'CheckDependenciesTool', 'CodeDocsSearchInfinibayTool', 'CodeInterpreterTool', 'CodeSearchTool', 'Context7DocsTool', 'Context7SearchTool', 'CreateEpicTool', 'CreateHypothesisTool', 'CreateMilestoneTool', 'CreatePRTool', 'CreateRepositoryTool', 'CreateTaskTool', 'DATA_TOOLS', 'DOCXSearchInfinibayTool', 'DeepWebResearchTool', 'DirectorySearchTool', 'EditFileTool', 'ExecuteCommandTool', 'FILE_TOOLS', 'GIT_TOOLS', 'GetTaskTool', 'GitBranchTool', 'GitCommitTool', 'GitDiffTool', 'GitPushTool', 'GitStatusTool', 'GlobTool', 'JSONSearchInfinibayTool', 'KNOWLEDGE_TOOLS', 'ListDirectoryTool', 'LoadSessionNoteTool', 'MergePRTool', 'NL2SQLTool', 'PDFSearchTool', 'PROJECT_TOOLS', 'RAG_TOOLS', 'ReadCommentsTool', 'ReadEpicsTool', 'ReadFileTool', 'ReadFindingReviewsTool', 'ReadFindingsTool', 'ReadMessagesTool', 'ReadMilestonesTool', 'ReadPaperTool', 'ReadReferenceFilesTool', 'ReadReportTool', 'ReadTaskHistoryTool', 'ReadTasksTool', 'ReadWikiTool', 'RecordFindingTool', 'RejectFindingTool', 'RejectTaskTool', 'ReplyToUserTool', 'SHELL_TOOLS', 'SaveSessionNoteTool', 'ScrapeWebsiteInfinibayTool', 'SearchFindingsTool', 'SearchKnowledgeTool', 'SearchWikiTool', 'SendMessageTool', 'SetTaskDependenciesTool', 'SpiderScrapeTool', 'SummarizeFindingsTool', 'TASK_TOOLS', 'TakeTaskTool', 'UpdateProjectTool', 'UpdateTaskStatusTool', 'ValidateFindingTool', 'WEB_TOOLS', 'WebFetchTool', 'WebSearchTool', 'WriteFileTool', 'WriteReportTool', 'WriteWikiTool', 'XMLSearchInfinibayTool', '_ROLE_TOOLS', '_TASK_TYPE_TOOLS', 'get_all_tools', 'get_tools_for_role', 'get_tools_for_task_type']
__all__ = [name for name in _LEGACY_EXPORTS if not name.startswith("_")]


def __getattr__(name: str):
    """Load the historical catalogue only for a known explicitly requested export; unknown attributes do not initialize anything."""
    if name not in _LEGACY_EXPORTS:
        raise AttributeError(name)
    from backend.tools._legacy_access import require_legacy_extra

    require_legacy_extra()
    value = getattr(import_module("backend.tools._legacy_catalog"), name)
    globals()[name] = value
    return value


def __dir__():
    """Expose discoverable compatibility names without importing their implementations or provider dependencies."""
    return sorted(set(globals()) | set(_LEGACY_EXPORTS))

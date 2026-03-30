"""Code intelligence tools for the agent."""

from backend.tools.code_intel.find_definition import FindDefinitionTool
from backend.tools.code_intel.find_references import FindReferencesTool
from backend.tools.code_intel.list_symbols import ListSymbolsTool
from backend.tools.code_intel.search_symbols import SearchSymbolsTool
from backend.tools.code_intel.get_symbol_code import GetSymbolCodeTool
from backend.tools.code_intel.project_structure import ProjectStructureTool
from backend.tools.code_intel.edit_method import EditSymbolTool
from backend.tools.code_intel.add_method import AddSymbolTool
from backend.tools.code_intel.remove_method import RemoveSymbolTool
from backend.tools.code_intel.analyze_code import AnalyzeCodeTool
from backend.tools.code_intel.rename_symbol import RenameSymbolTool
from backend.tools.code_intel.move_symbol import MoveSymbolTool

# Backward-compat aliases
EditMethodTool = EditSymbolTool
AddMethodTool = AddSymbolTool
RemoveMethodTool = RemoveSymbolTool

__all__ = [
    "FindDefinitionTool", "FindReferencesTool",
    "ListSymbolsTool", "SearchSymbolsTool", "GetSymbolCodeTool",
    "ProjectStructureTool",
    "EditSymbolTool", "AddSymbolTool", "RemoveSymbolTool",
    "EditMethodTool", "AddMethodTool", "RemoveMethodTool",  # aliases
    "AnalyzeCodeTool",
    "RenameSymbolTool", "MoveSymbolTool",
]

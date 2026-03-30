"""Tests for new features in backend.engine.loop_tools."""

import inspect
import json
from unittest.mock import MagicMock

import pytest

from backend.engine.loop_tools import (
    ADD_NOTE_SCHEMA,
    STEP_COMPLETE_SCHEMA,
    THINK_SCHEMA,
    _METADATA_PARAMS,
    _PARAM_ALIASES,
    _TOOL_ALIASES,
    build_tool_schemas,
    execute_tool_call,
)


class TestBuildToolSchemas:
    def test_includes_pseudo_tools(self):
        schemas = build_tool_schemas([])
        names = [s["function"]["name"] for s in schemas]
        assert "step_complete" in names
        assert "add_note" in names
        assert "think" in names

    def test_add_note_schema_structure(self):
        assert ADD_NOTE_SCHEMA["type"] == "function"
        params = ADD_NOTE_SCHEMA["function"]["parameters"]
        assert "note" in params["properties"]
        assert "note" in params["required"]

    def test_think_schema_structure(self):
        assert THINK_SCHEMA["type"] == "function"
        params = THINK_SCHEMA["function"]["parameters"]
        assert "thought" in params["properties"]
        assert "thought" in params["required"]

    def test_includes_real_tools(self):
        mock_tool = MagicMock()
        mock_tool.name = "read_file"
        mock_tool.description = "Read a file"
        mock_tool.args_schema = None

        schemas = build_tool_schemas([mock_tool])
        names = [s["function"]["name"] for s in schemas]
        assert "read_file" in names
        # Plus pseudo-tools
        assert len(schemas) == 4  # 1 real + 3 pseudo


class TestExecuteToolCallAliases:
    def test_resolves_tool_alias(self):
        """edit_method should resolve to edit_symbol."""
        mock_tool = MagicMock()
        mock_tool._run = MagicMock(return_value="ok")
        # Make _run accept **kwargs
        mock_tool._run.__signature__ = None

        dispatch = {"edit_symbol": mock_tool}
        result = execute_tool_call(dispatch, "edit_method", '{"symbol_name": "foo"}')
        # Should have found the tool via alias
        assert "error" not in result.lower() or "Unknown tool" not in result

    def test_all_aliases_defined(self):
        expected_aliases = {"edit_method", "add_method", "remove_method", "write_file", "find_definition"}
        assert expected_aliases == set(_TOOL_ALIASES.keys())


class TestExecuteToolCallParamAliases:
    def test_applies_parameter_alias(self):
        """old_str should be corrected to old_string."""
        mock_tool = MagicMock()

        def _run(old_string="", new_string="", path=""):
            return f"replaced {old_string} with {new_string} in {path}"

        mock_tool._run = _run
        dispatch = {"edit_file": mock_tool}

        result = execute_tool_call(
            dispatch, "edit_file",
            json.dumps({"old_str": "foo", "new_str": "bar", "file_path": "a.py"}),
        )
        assert "foo" in result
        assert "bar" in result
        assert "a.py" in result


class TestExecuteToolCallMetadataStripping:
    def test_strips_metadata_params(self):
        mock_tool = MagicMock()

        def _run(path=""):
            return f"read {path}"

        mock_tool._run = _run
        dispatch = {"read_file": mock_tool}

        result = execute_tool_call(
            dispatch, "read_file",
            json.dumps({
                "path": "/tmp/a.py",
                "project_id": 1,
                "agent_id": "dev-1",
                "description": "reading file",
            }),
        )
        assert "read /tmp/a.py" in result

    def test_metadata_params_set(self):
        assert "project_id" in _METADATA_PARAMS
        assert "agent_id" in _METADATA_PARAMS
        assert "task_id" in _METADATA_PARAMS
        assert "session_id" in _METADATA_PARAMS


class TestExecuteToolCallMissingParams:
    def test_detects_missing_required_params(self):
        mock_tool = MagicMock()

        def _run(path, content):
            return "ok"

        mock_tool._run = _run
        dispatch = {"create_file": mock_tool}

        result = execute_tool_call(dispatch, "create_file", '{}')
        parsed = json.loads(result)
        assert "error" in parsed
        assert "requires" in parsed["error"].lower() or "required" in parsed["error"].lower()

    def test_unknown_tool_returns_error(self):
        result = execute_tool_call({}, "nonexistent_tool", '{}')
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

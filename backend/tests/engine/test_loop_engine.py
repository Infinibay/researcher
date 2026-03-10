"""Tests for the plan-execute-summarize loop engine."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.engine.loop_models import (
    ActionRecord,
    LoopPlan,
    LoopState,
    PlanStep,
    StepOperation,
    StepResult,
)


# ── Model tests ─────────────────────────────────────────────────────────────


class TestPlanStep:
    def test_defaults(self):
        step = PlanStep(index=1, description="Do something")
        assert step.status == "pending"

    def test_all_statuses(self):
        for status in ("pending", "active", "done", "skipped"):
            step = PlanStep(index=1, description="x", status=status)
            assert step.status == status


class TestStepOperation:
    def test_add(self):
        op = StepOperation(op="add", index=3, description="New step")
        assert op.op == "add"
        assert op.index == 3

    def test_remove_no_description(self):
        op = StepOperation(op="remove", index=2)
        assert op.description == ""


class TestLoopPlan:
    def test_empty_plan(self):
        plan = LoopPlan()
        assert plan.steps == []
        assert plan.active_step is None
        assert plan.render() == ""

    def test_active_step(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="done"),
            PlanStep(index=2, description="b", status="active"),
            PlanStep(index=3, description="c", status="pending"),
        ])
        assert plan.active_step is not None
        assert plan.active_step.index == 2

    def test_advance(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="active"),
            PlanStep(index=2, description="b", status="pending"),
            PlanStep(index=3, description="c", status="pending"),
        ])
        plan.advance()
        assert plan.steps[0].status == "done"
        assert plan.steps[1].status == "active"
        assert plan.steps[2].status == "pending"

    def test_advance_last_step(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="done"),
            PlanStep(index=2, description="b", status="active"),
        ])
        plan.advance()
        assert plan.steps[1].status == "done"
        assert plan.active_step is None

    def test_render(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Explore", status="done"),
            PlanStep(index=2, description="Code", status="active"),
            PlanStep(index=3, description="Test"),
        ])
        rendered = plan.render()
        assert "[done]" in rendered
        assert "[active]" in rendered
        assert "3. Test" in rendered


class TestLoopPlanApplyOperations:
    """Test structured apply_operations (add/modify/remove)."""

    def test_add_operation(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Explore", status="done"),
            PlanStep(index=2, description="Code", status="active"),
        ])
        plan.apply_operations([
            StepOperation(op="add", index=3, description="Write tests"),
            StepOperation(op="add", index=4, description="Run linter"),
        ])
        assert len(plan.steps) == 4
        assert plan.steps[2].description == "Write tests"
        assert plan.steps[2].status == "pending"
        assert plan.steps[3].description == "Run linter"

    def test_modify_operation(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Explore", status="done"),
            PlanStep(index=2, description="Code auth", status="pending"),
        ])
        plan.apply_operations([
            StepOperation(op="modify", index=2, description="Code auth AND add validation"),
        ])
        assert plan.steps[1].description == "Code auth AND add validation"
        assert plan.steps[1].status == "pending"  # status unchanged

    def test_remove_operation(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Explore", status="done"),
            PlanStep(index=2, description="Old step", status="pending"),
            PlanStep(index=3, description="Keep this", status="pending"),
        ])
        plan.apply_operations([StepOperation(op="remove", index=2)])
        assert plan.steps[1].status == "skipped"
        assert plan.steps[2].status == "pending"  # step 3 unchanged

    def test_remove_cannot_remove_done(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Done", status="done"),
        ])
        plan.apply_operations([StepOperation(op="remove", index=1)])
        assert plan.steps[0].status == "done"  # can't remove done steps

    def test_mixed_operations(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Explore", status="done"),
            PlanStep(index=2, description="Code", status="active"),
            PlanStep(index=3, description="Old test step", status="pending"),
        ])
        plan.apply_operations([
            StepOperation(op="remove", index=3),
            StepOperation(op="add", index=4, description="Write better tests"),
            StepOperation(op="add", index=5, description="Run CI"),
        ])
        assert plan.steps[2].status == "skipped"  # step 3 removed
        assert plan.steps[3].description == "Write better tests"
        assert plan.steps[4].description == "Run CI"
        assert len(plan.steps) == 5

    def test_add_replaces_existing_index(self):
        """Adding a step at an existing index replaces it."""
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Old", status="pending"),
        ])
        plan.apply_operations([StepOperation(op="add", index=1, description="New description")])
        assert len(plan.steps) == 1
        assert plan.steps[0].description == "New description"

    def test_empty_ops_no_change(self):
        plan = LoopPlan(steps=[PlanStep(index=1, description="x")])
        plan.apply_operations([])
        assert len(plan.steps) == 1

    def test_sorted_after_operations(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="done"),
        ])
        plan.apply_operations([
            StepOperation(op="add", index=5, description="Last"),
            StepOperation(op="add", index=3, description="Middle"),
        ])
        indices = [s.index for s in plan.steps]
        assert indices == [1, 3, 5]


class TestLoopPlanHasPending:
    def test_has_pending_with_pending(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="done"),
            PlanStep(index=2, description="b", status="pending"),
        ])
        assert plan.has_pending is True

    def test_has_pending_with_active(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="active"),
        ])
        assert plan.has_pending is True

    def test_no_pending_all_done(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="done"),
            PlanStep(index=2, description="b", status="skipped"),
        ])
        assert plan.has_pending is False

    def test_no_pending_empty(self):
        plan = LoopPlan()
        assert plan.has_pending is False


class TestMarkActiveDoneAndActivateNext:
    def test_mark_active_done(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="active"),
            PlanStep(index=2, description="b", status="pending"),
        ])
        plan.mark_active_done()
        assert plan.steps[0].status == "done"
        assert plan.steps[1].status == "pending"  # not activated yet

    def test_activate_next(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="done"),
            PlanStep(index=2, description="b", status="pending"),
        ])
        plan.activate_next()
        assert plan.steps[1].status == "active"

    def test_mark_then_activate(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="a", status="active"),
            PlanStep(index=2, description="b", status="pending"),
            PlanStep(index=3, description="c", status="pending"),
        ])
        plan.mark_active_done()
        plan.activate_next()
        assert plan.steps[0].status == "done"
        assert plan.steps[1].status == "active"
        assert plan.steps[2].status == "pending"


class TestStepResult:
    def test_defaults(self):
        sr = StepResult(summary="Did something")
        assert sr.status == "continue"
        assert sr.next_steps == []
        assert sr.final_answer is None

    def test_with_operations(self):
        sr = StepResult(
            summary="Found auth module",
            status="continue",
            next_steps=[
                StepOperation(op="add", index=3, description="Fix auth"),
            ],
        )
        assert len(sr.next_steps) == 1
        assert sr.next_steps[0].op == "add"


class TestLoopState:
    def test_defaults(self):
        state = LoopState()
        assert state.plan.steps == []
        assert state.history == []
        assert state.iteration_count == 0


# ── Tool tests ───────────────────────────────────────────────────────────────


class TestLoopTools:
    def _make_mock_tool(self, name="test_tool", description="A test tool", params=None):
        """Create a mock tool that looks like a InfinibayBaseTool."""
        tool = MagicMock()
        tool.name = name
        tool.description = description

        if params is None:
            # Simple schema: one required string param
            schema = MagicMock()
            schema.model_json_schema.return_value = {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The query"}},
                "required": ["query"],
            }
            tool.args_schema = schema
        else:
            schema = MagicMock()
            schema.model_json_schema.return_value = params
            tool.args_schema = schema

        return tool

    def test_tool_to_openai_schema(self):
        from backend.engine.loop_tools import tool_to_openai_schema

        tool = self._make_mock_tool()
        schema = tool_to_openai_schema(tool)

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert "query" in schema["function"]["parameters"]["properties"]

    def test_build_tool_schemas_includes_step_complete(self):
        from backend.engine.loop_tools import build_tool_schemas

        tools = [self._make_mock_tool(f"tool_{i}") for i in range(3)]
        schemas = build_tool_schemas(tools)
        # 3 agent tools + step_complete
        assert len(schemas) == 4
        assert all(s["type"] == "function" for s in schemas)
        names = [s["function"]["name"] for s in schemas]
        assert "step_complete" in names

    def test_build_tool_schemas_empty_tools(self):
        from backend.engine.loop_tools import build_tool_schemas

        schemas = build_tool_schemas([])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "step_complete"

    def test_build_tool_dispatch(self):
        from backend.engine.loop_tools import build_tool_dispatch

        tools = [self._make_mock_tool(f"tool_{i}") for i in range(3)]
        dispatch = build_tool_dispatch(tools)
        assert "tool_0" in dispatch
        assert "tool_2" in dispatch

    def test_execute_tool_call_unknown(self):
        from backend.engine.loop_tools import execute_tool_call

        result = execute_tool_call({}, "nonexistent", "{}")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_execute_tool_call_bad_json(self):
        from backend.engine.loop_tools import execute_tool_call

        tool = self._make_mock_tool()
        tool._run = MagicMock(return_value="ok")
        dispatch = {"test_tool": tool}

        result = execute_tool_call(dispatch, "test_tool", "not valid json{{{")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_execute_tool_call_success(self):
        from backend.engine.loop_tools import execute_tool_call

        tool = self._make_mock_tool()
        tool._run = MagicMock(return_value='{"result": "found it"}')
        dispatch = {"test_tool": tool}

        result = execute_tool_call(dispatch, "test_tool", '{"query": "hello"}')
        assert "found it" in result

    def test_execute_tool_call_rejects_extra_kwargs(self):
        from backend.engine.loop_tools import execute_tool_call

        def _run(query: str) -> str:
            return f"got {query}"

        tool = self._make_mock_tool()
        tool._run = _run
        dispatch = {"test_tool": tool}

        # Extra kwargs should return an error with valid param names
        result = execute_tool_call(
            dispatch, "test_tool",
            '{"query": "hello", "project_id": 1, "agent_id": "x"}',
        )
        parsed = json.loads(result)
        assert "error" in parsed
        assert "project_id" in parsed["error"]
        assert "query" in parsed["error"]  # lists valid params

    def test_execute_tool_call_exception(self):
        from backend.engine.loop_tools import execute_tool_call

        tool = self._make_mock_tool()
        tool._run = MagicMock(side_effect=ValueError("boom"))
        dispatch = {"test_tool": tool}

        result = execute_tool_call(dispatch, "test_tool", '{"query": "x"}')
        parsed = json.loads(result)
        assert "error" in parsed
        assert "boom" in parsed["error"]


# ── Context tests ────────────────────────────────────────────────────────────


class TestLoopContext:
    def test_build_system_prompt(self):
        from backend.engine.loop_context import LOOP_PROTOCOL, build_system_prompt

        prompt = build_system_prompt("You are a developer.")
        assert "You are a developer." in prompt
        assert "step_complete" in prompt
        assert LOOP_PROTOCOL in prompt

    def test_build_iteration_prompt_no_plan(self):
        from backend.engine.loop_context import build_iteration_prompt

        state = LoopState()
        prompt = build_iteration_prompt("Do the task", "A JSON result", state)
        assert "<task>" in prompt
        assert "Do the task" in prompt
        assert "No plan yet" in prompt
        assert "<expected-output>" in prompt

    def test_build_iteration_prompt_with_plan_and_history(self):
        from backend.engine.loop_context import build_iteration_prompt

        state = LoopState(
            plan=LoopPlan(steps=[
                PlanStep(index=1, description="Explore", status="done"),
                PlanStep(index=2, description="Code", status="active"),
                PlanStep(index=3, description="Test", status="pending"),
            ]),
            history=[
                ActionRecord(step_index=1, summary="Found main.py and utils.py"),
            ],
        )
        prompt = build_iteration_prompt("Build feature", "Working code", state)

        assert "<plan>" in prompt
        assert "[done] Explore" in prompt
        assert "<previous-actions>" in prompt
        assert "Found main.py" in prompt
        assert "<current-action>" in prompt
        assert "Step 2: Code" in prompt
        assert "<next-actions>" in prompt
        assert "3. Test" in prompt

    def test_build_iteration_prompt_no_expected_output(self):
        from backend.engine.loop_context import build_iteration_prompt

        state = LoopState()
        prompt = build_iteration_prompt("Do something", "", state)
        assert "<expected-output>" not in prompt


class TestBuildIterationPromptAllDone:
    """Test that build_iteration_prompt handles all-steps-done state."""

    def test_all_done_shows_completion_prompt(self):
        from backend.engine.loop_context import build_iteration_prompt

        state = LoopState(
            plan=LoopPlan(steps=[
                PlanStep(index=1, description="Explore", status="done"),
                PlanStep(index=2, description="Code", status="done"),
            ]),
            history=[
                ActionRecord(step_index=1, summary="Explored"),
                ActionRecord(step_index=2, summary="Coded"),
            ],
        )
        prompt = build_iteration_prompt("Build feature", "Working code", state)
        assert "All planned steps are complete" in prompt
        assert "step_complete" in prompt


# ── Step complete parsing tests ──────────────────────────────────────────────


class TestParseStepCompleteArgs:
    def test_basic_args(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args(json.dumps({
            "summary": "Found the auth module.",
            "status": "continue",
        }))
        assert result.summary == "Found the auth module."
        assert result.status == "continue"
        assert result.next_steps == []
        assert result.final_answer is None

    def test_done_with_final_answer(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args(json.dumps({
            "summary": "Task complete.",
            "status": "done",
            "final_answer": "Here is the final implementation.",
        }))
        assert result.status == "done"
        assert result.final_answer == "Here is the final implementation."

    def test_with_next_steps(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args(json.dumps({
            "summary": "Found the issue.",
            "status": "continue",
            "next_steps": [
                {"op": "add", "index": 3, "description": "Fix the bug"},
                {"op": "remove", "index": 2},
            ],
        }))
        assert len(result.next_steps) == 2
        assert result.next_steps[0].op == "add"
        assert result.next_steps[0].index == 3
        assert result.next_steps[0].description == "Fix the bug"
        assert result.next_steps[1].op == "remove"
        assert result.next_steps[1].index == 2

    def test_dict_input(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args({
            "summary": "Did something.",
            "status": "blocked",
        })
        assert result.status == "blocked"

    def test_bad_json(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args("not valid json{{{")
        assert "no summary" in result.summary.lower() or result.summary

    def test_empty_string(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args("")
        assert result.status == "continue"

    def test_malformed_next_steps_ignored(self):
        from backend.engine.loop_engine import _parse_step_complete_args

        result = _parse_step_complete_args(json.dumps({
            "summary": "Did something.",
            "status": "continue",
            "next_steps": [
                {"op": "add", "index": 3, "description": "Good step"},
                {"bad": "data"},  # missing op and index
                "not an object",
            ],
        }))
        assert len(result.next_steps) == 1
        assert result.next_steps[0].description == "Good step"


# ── Engine integration tests ─────────────────────────────────────────────────


def _make_llm_response(content="", tool_calls=None, total_tokens=100):
    """Build a mock litellm completion response."""
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(total_tokens=total_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_tool_call(tc_id, name, arguments):
    """Build a mock tool call object."""
    func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=tc_id, function=func)


def _make_step_complete_call(
    tc_id: str = "sc1",
    summary: str = "Step done.",
    status: str = "continue",
    next_steps: list[dict] | None = None,
    final_answer: str | None = None,
) -> SimpleNamespace:
    """Build a mock step_complete tool call."""
    args: dict = {"summary": summary, "status": status}
    if next_steps:
        args["next_steps"] = next_steps
    if final_answer:
        args["final_answer"] = final_answer
    return _make_tool_call(tc_id, "step_complete", json.dumps(args))


class TestLoopEngine:
    def _make_agent(self):
        """Create a minimal mock agent."""
        agent = MagicMock()
        agent.agent_id = "test_agent_p1"
        agent.backstory = "You are a test agent."
        agent.tools = []
        return agent

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_simple_done_in_one_step(self, mock_settings, mock_call_llm):
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        # LLM responds with step_complete(done) in one shot
        mock_call_llm.return_value = _make_llm_response(
            content="",
            tool_calls=[_make_step_complete_call(
                summary="Did everything.",
                status="done",
                next_steps=[{"op": "add", "index": 1, "description": "Do the thing"}],
                final_answer="Here is the result.",
            )],
        )

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Do the thing", "A result"),
            )

        assert "result" in result.lower()

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_multi_step_execution(self, mock_settings, mock_call_llm):
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 10
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        responses = [
            # Step 1: planning — create initial plan
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Explored the code.",
                    status="continue",
                    next_steps=[
                        {"op": "add", "index": 1, "description": "Explore"},
                        {"op": "add", "index": 2, "description": "Implement"},
                        {"op": "add", "index": 3, "description": "Test"},
                    ],
                )],
            ),
            # Step 2: implement
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Implemented the feature.",
                    status="continue",
                )],
            ),
            # Step 3: test
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="All tests pass.",
                    status="continue",
                )],
            ),
            # Step 4: done (all steps complete, LLM signals done)
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="All tests pass.",
                    status="done",
                    final_answer="All tests pass!",
                )],
            ),
        ]
        mock_call_llm.side_effect = responses

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Build a feature", "Working code"),
            )

        assert "tests pass" in result.lower() or "All tests" in result

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_tool_calling(self, mock_settings, mock_call_llm):
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        responses = [
            # Planning: create plan with step_complete
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Created plan.",
                    status="continue",
                    next_steps=[{"op": "add", "index": 1, "description": "Read main.py"}],
                )],
            ),
            # Step 1: LLM makes a tool call
            _make_llm_response(
                content="",
                tool_calls=[_make_tool_call("tc1", "read_file", '{"path": "main.py"}')],
            ),
            # Step 1 continued: LLM finishes with step_complete
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Read main.py, found entry point.",
                    status="done",
                    final_answer="Found main.py.",
                )],
            ),
        ]
        mock_call_llm.side_effect = responses

        # Mock tool
        mock_tool = MagicMock()
        mock_tool.name = "read_file"
        mock_tool.description = "Read a file"
        schema = MagicMock()
        schema.model_json_schema.return_value = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        mock_tool.args_schema = schema
        mock_tool._run = MagicMock(return_value="file contents here")

        agent = self._make_agent()
        agent.tools = [mock_tool]

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(agent, ("Read the file", "File contents"))

        mock_tool._run.assert_called_once_with(path="main.py")

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_tool_and_step_complete_in_same_response(self, mock_settings, mock_call_llm):
        """LLM can call a tool and step_complete in the same response."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        responses = [
            # Planning
            _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Plan created.",
                    status="continue",
                    next_steps=[{"op": "add", "index": 1, "description": "Read and finish"}],
                )],
            ),
            # Tool call + step_complete together
            _make_llm_response(
                content="",
                tool_calls=[
                    _make_tool_call("tc1", "read_file", '{"path": "main.py"}'),
                    _make_step_complete_call(
                        tc_id="sc2",
                        summary="Read file and done.",
                        status="done",
                        final_answer="Found it.",
                    ),
                ],
            ),
        ]
        mock_call_llm.side_effect = responses

        mock_tool = MagicMock()
        mock_tool.name = "read_file"
        mock_tool.description = "Read a file"
        schema = MagicMock()
        schema.model_json_schema.return_value = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }
        mock_tool.args_schema = schema
        mock_tool._run = MagicMock(return_value="contents")

        agent = self._make_agent()
        agent.tools = [mock_tool]

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(agent, ("Read file", "Contents"))

        mock_tool._run.assert_called_once()
        assert "Found it" in result

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_blocked_status(self, mock_settings, mock_call_llm):
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        mock_call_llm.return_value = _make_llm_response(
            content="",
            tool_calls=[_make_step_complete_call(
                summary="Missing API key.",
                status="blocked",
            )],
        )

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Call the API", "API result"),
            )

        assert "Blocked" in result
        assert "API key" in result

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_iteration_limit(self, mock_settings, mock_call_llm):
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 2
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        # Always returns continue with more steps
        mock_call_llm.return_value = _make_llm_response(
            content="",
            tool_calls=[_make_step_complete_call(
                summary="Still working.",
                status="continue",
                next_steps=[
                    {"op": "add", "index": 10, "description": "More work"},
                ],
            )],
        )

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Do a long task", "A result"),
            )

        assert "summary" in result.lower() or "still working" in result.lower()

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_history_window(self, mock_settings, mock_call_llm):
        """When LOOP_HISTORY_WINDOW > 0, only last N summaries are included."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 1

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary=f"Did step {call_count}.",
                        status="continue",
                        next_steps=[
                            {"op": "add", "index": call_count + 1, "description": f"Step {call_count + 1}"},
                        ] if call_count == 1 else [
                            {"op": "add", "index": 3, "description": "Step 3"},
                        ],
                    )],
                )
            return _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="All done.",
                    status="done",
                    final_answer="Final!",
                )],
            )

        mock_call_llm.side_effect = _side_effect

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Multi-step task", "A result"),
            )

        assert "Final" in result

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_all_done_allows_one_more_iteration(self, mock_settings, mock_call_llm):
        """When all steps done, allow one more iteration before terminating."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 10
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Planning iteration
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Created plan.",
                        status="continue",
                        next_steps=[{"op": "add", "index": 1, "description": "Do the thing"}],
                    )],
                )
            if call_count == 2:
                # Complete the only step, don't add new ones
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Did the thing.",
                        status="continue",
                    )],
                )
            # Third call: all done again — safety triggers termination
            return _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Nothing left to do.",
                    status="continue",
                )],
            )

        mock_call_llm.side_effect = _side_effect

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Quick task", "A result"),
            )

        # Should have terminated after 2 consecutive all-done iterations
        assert call_count == 3  # planning + step + safety iteration

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_next_steps_extend_plan(self, mock_settings, mock_call_llm):
        """LLM adds new steps via next_steps, plan grows incrementally."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 10
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Created initial plan.",
                        status="continue",
                        next_steps=[
                            {"op": "add", "index": 1, "description": "Explore codebase"},
                            {"op": "add", "index": 2, "description": "Read auth module"},
                        ],
                    )],
                )
            if call_count == 2:
                # Complete step 1, add step 3
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Found main.py and auth.py.",
                        status="continue",
                        next_steps=[
                            {"op": "add", "index": 3, "description": "Add JWT check to auth.py"},
                        ],
                    )],
                )
            if call_count == 3:
                # Complete step 2
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Read auth module.",
                        status="continue",
                    )],
                )
            if call_count == 4:
                # Complete step 3, declare done
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Added JWT check.",
                        status="done",
                        final_answer="All done!",
                    )],
                )
            return _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Unexpected.",
                    status="done",
                    final_answer="Unexpected",
                )],
            )

        mock_call_llm.side_effect = _side_effect

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(
                self._make_agent(),
                ("Add JWT auth", "Working auth"),
            )

        assert call_count == 4
        assert "All done" in result


# ── Forced tool_choice tests ─────────────────────────────────────────────────


class TestForcedToolChoice:
    def _make_agent(self):
        agent = MagicMock()
        agent.agent_id = "test_agent_p1"
        agent.backstory = "You are a test agent."
        agent.tools = []
        return agent

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_text_response_becomes_fallback(self, mock_settings, mock_call_llm):
        """Text response despite tool_choice=required creates fallback StepResult."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 3
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Planning: responds with step_complete
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Plan created.",
                        status="continue",
                        next_steps=[
                            {"op": "add", "index": 1, "description": "Do work"},
                            {"op": "add", "index": 2, "description": "More work"},
                        ],
                    )],
                )
            # Broken provider returns text despite required
            return _make_llm_response(content="I cannot call tools.")

        mock_call_llm.side_effect = _side_effect

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(self._make_agent(), ("Do work", "A result"))

        # Should still produce a result (fallback summaries)
        assert result

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_planning_uses_required_tool_choice(self, mock_settings, mock_call_llm):
        """Planning phase uses tool_choice=required to force step_complete."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        captured_tool_choices = []

        def _side_effect(params, messages, tools=None, tool_choice="auto"):
            captured_tool_choices.append(tool_choice)
            if len(captured_tool_choices) == 1:
                # Planning
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Plan.",
                        status="continue",
                        next_steps=[{"op": "add", "index": 1, "description": "Work"}],
                    )],
                )
            return _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Done.",
                    status="done",
                    final_answer="Finished.",
                )],
            )

        mock_call_llm.side_effect = _side_effect

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            engine.execute(self._make_agent(), ("Do work", "Done"))

        # All calls should use "required" — every response must be a tool call
        assert all(tc == "required" for tc in captured_tool_choices)

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_fallback_when_required_still_returns_text(self, mock_settings, mock_call_llm):
        """Last resort: if tool_choice=required still returns text, use it as summary."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 3
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 10
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 50
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Planning: responds properly
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Plan.",
                        status="continue",
                        next_steps=[
                            {"op": "add", "index": 1, "description": "A"},
                            {"op": "add", "index": 2, "description": "B"},
                        ],
                    )],
                )
            # Always text, even when forced — broken LLM
            return _make_llm_response(content="I cannot call tools.")

        mock_call_llm.side_effect = _side_effect

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(self._make_agent(), ("Work", "Done"))

        # Should still produce a result (fallback summary)
        assert result


# ── Repetition detection tests ────────────────────────────────────────────────


class TestRepetitionDetection:
    def _make_agent(self, tools=None):
        agent = MagicMock()
        agent.agent_id = "test_agent_p1"
        agent.backstory = "You are a test agent."
        agent.tools = tools or []
        return agent

    def _make_mock_tool(self, name="read_file"):
        tool = MagicMock()
        tool.name = name
        tool.description = f"Tool: {name}"
        schema = MagicMock()
        schema.model_json_schema.return_value = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }
        tool.args_schema = schema
        tool._run = MagicMock(return_value='{"result": "ok"}')
        return tool

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_same_tool_loop_gets_nudged(self, mock_settings, mock_call_llm):
        """Calling the same tool 3+ times triggers a nudge, then step_complete."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 20
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 100
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Planning
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Plan created.",
                        status="continue",
                        next_steps=[{"op": "add", "index": 1, "description": "Read files"}],
                    )],
                )
            if call_count <= 4:
                # 3 consecutive read_file calls (calls 2, 3, 4)
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_tool_call(f"tc{call_count}", "read_file", '{"path": "file.py"}')],
                )
            if call_count == 5:
                # After nudge, LLM calls step_complete
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Read the files.",
                        status="done",
                        final_answer="Done reading.",
                    )],
                )
            return _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(summary="x", status="done")],
            )

        mock_call_llm.side_effect = _side_effect

        mock_tool = self._make_mock_tool("read_file")
        agent = self._make_agent([mock_tool])

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(agent, ("Read files", "Contents"))

        # 3 read_file calls + nudge + step_complete = 5 LLM calls in step 1
        assert call_count == 5
        assert "Done reading" in result

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_same_tool_force_break_after_nudge_fails(self, mock_settings, mock_call_llm):
        """If nudge fails and tool keeps repeating, force break."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 20
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 100
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Planning
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Plan.",
                        status="continue",
                        next_steps=[
                            {"op": "add", "index": 1, "description": "Send messages"},
                            {"op": "add", "index": 2, "description": "More work"},
                        ],
                    )],
                )
            # Always send_message — ignores the nudge
            return _make_llm_response(
                content="",
                tool_calls=[_make_tool_call(f"tc{call_count}", "send_message", '{"message": "hi"}')],
            )

        mock_call_llm.side_effect = _side_effect

        mock_tool = self._make_mock_tool("send_message")
        agent = self._make_agent([mock_tool])

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(agent, ("Send message", "Sent"))

        # Should have been force-broken after 3 (nudge) + 2 more = 5 total
        # consecutive send_message calls
        assert "repeated send_message" in result.lower() or "interrupted" in result.lower()

    @patch("backend.engine.loop_engine._call_llm")
    @patch("backend.config.settings.settings")
    def test_different_tools_no_repetition_trigger(self, mock_settings, mock_call_llm):
        """Alternating between different tools doesn't trigger repetition detection."""
        from backend.engine.loop_engine import LoopEngine

        mock_settings.LOOP_MAX_ITERATIONS = 5
        mock_settings.LOOP_MAX_TOOL_CALLS_PER_ACTION = 20
        mock_settings.LOOP_MAX_TOTAL_TOOL_CALLS = 100
        mock_settings.LOOP_HISTORY_WINDOW = 0

        call_count = 0
        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Planning
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_step_complete_call(
                        summary="Plan.",
                        status="continue",
                        next_steps=[{"op": "add", "index": 1, "description": "Work"}],
                    )],
                )
            if call_count <= 7:
                # Alternate between two tools
                name = "read_file" if call_count % 2 == 0 else "write_file"
                return _make_llm_response(
                    content="",
                    tool_calls=[_make_tool_call(f"tc{call_count}", name, '{"path": "f.py"}')],
                )
            # Then finish
            return _make_llm_response(
                content="",
                tool_calls=[_make_step_complete_call(
                    summary="Done working.",
                    status="done",
                    final_answer="Finished.",
                )],
            )

        mock_call_llm.side_effect = _side_effect

        read_tool = self._make_mock_tool("read_file")
        write_tool = self._make_mock_tool("write_file")
        agent = self._make_agent([read_tool, write_tool])

        engine = LoopEngine()
        with patch("backend.config.llm.get_litellm_params", return_value={"model": "test"}):
            result = engine.execute(agent, ("Read and write", "Done"))

        # Should complete normally without repetition detection
        assert "Finished" in result


# ── Engine factory test ──────────────────────────────────────────────────────


class TestEngineFactory:
    def test_loop_engine_registered(self):
        from backend.engine import get_engine, reset_engine

        reset_engine()
        engine = get_engine()

        from backend.engine.loop_engine import LoopEngine
        assert isinstance(engine, LoopEngine)

        reset_engine()  # cleanup

"""Plan-execute-summarize loop engine.

Replaces the opaque CrewAI ReAct loop with a controlled cycle:
each iteration rebuilds the prompt from scratch with only system prompt +
task + plan + compact summaries of previous actions + current step.
Raw tool output is discarded after each step; only ~50-token summaries survive.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.engine.base import AgentEngine
from backend.engine.engine_logging import (
    BLUE,
    BOLD,
    DIM,
    RED,
    RESET,
    YELLOW,
    emit_loop_event,
    extract_tool_detail,
    extract_tool_error,
    log,
    log_finish,
    log_plan,
    log_prompt,
    log_start,
    log_step_done,
    log_step_start,
    log_tool,
)
from backend.engine.file_change_tracker import FileChangeTracker
from backend.engine.llm_client import (
    PERMANENT_ERRORS,
    call_llm,
    is_malformed_tool_call,
)
from backend.engine.loop_context import (
    build_iteration_prompt,
    build_system_prompt,
    build_tools_prompt_section,
)
from backend.engine.loop_models import (
    ActionRecord,
    LoopPlan,
    LoopState,
    PlanStep,
    StepResult,
)
from backend.engine.loop_tools import (
    ADD_NOTE_SCHEMA,
    STEP_COMPLETE_SCHEMA,
    build_tool_dispatch,
    build_tool_schemas,
    execute_tool_call,
)
from backend.engine.tool_call_parser import (
    ManualToolCall,
    parse_step_complete_args,
    parse_text_tool_calls,
)
from backend.engine.tool_executor import (
    batch_tool_calls,
    capture_pre_content,
    execute_tool_calls_parallel,
    maybe_emit_file_change,
    update_opened_files_cache,
)

# Max consecutive calls to the same tool before forcing a step_complete nudge
_MAX_SAME_TOOL_CONSECUTIVE = 3

# Max retries when LLM returns text instead of tool calls
_MAX_TEXT_RETRIES = 5

# Max retries for malformed tool calls before graceful degradation
_MAX_MALFORMED_RETRIES = 4

# Circuit breaker: force step_complete after this many consecutive tool errors
_MAX_CONSECUTIVE_ERRORS = 4

logger = logging.getLogger(__name__)


def _synthesize_final(state: LoopState) -> str:
    """Synthesize a final answer from accumulated history when loop exhausts iterations."""
    if not state.history:
        return "No actions were completed."

    parts = ["Task execution summary (iteration limit reached):"]
    for record in state.history:
        parts.append(f"- Step {record.step_index}: {record.summary}")
    return "\n".join(parts)


def _get_model_max_context(llm_params: dict[str, Any]) -> int:
    """Query the provider for the model's context window size.

    Returns 0 if unknown (disables context budget tracking).
    """
    model = llm_params.get("model", "")
    try:
        import litellm
        info = litellm.get_model_info(model)
        if info and "max_input_tokens" in info:
            return int(info["max_input_tokens"])
    except Exception:
        pass

    # Fallback: try Ollama /api/show
    base_url = llm_params.get("api_base", llm_params.get("base_url", ""))
    if base_url and ("ollama" in base_url or "11434" in base_url):
        try:
            import requests
            model_name = model.replace("ollama_chat/", "").replace("ollama/", "")
            resp = requests.post(
                f"{base_url.rstrip('/')}/api/show",
                json={"name": model_name},
                timeout=5,
            )
            if resp.ok:
                data = resp.json()
                params = data.get("model_info", {})
                for key in params:
                    if "context" in key.lower():
                        return int(params[key])
        except Exception:
            pass

    return 0


def _summarize_step(
    messages: list[dict[str, Any]],
    task_desc: str,
    state: LoopState,
    step_result: StepResult,
    llm_params: dict[str, Any],
) -> dict[str, Any]:
    """Use a dedicated LLM call to produce a structured step summary.

    Returns a dict with keys: summary, files_to_preload, changes_made,
    discovered, pending, anti_patterns.
    """
    from backend.config.settings import settings

    if not settings.LOOP_SUMMARIZER_ENABLED:
        return {
            "summary": step_result.summary,
            "files_to_preload": [],
            "changes_made": "",
            "discovered": "",
            "pending": "",
            "anti_patterns": "",
        }

    # Truncate step messages for the summarizer
    max_input = settings.LOOP_SUMMARIZER_MAX_INPUT_TOKENS
    step_text = _truncate_step_messages(messages, max_input)

    summarizer_prompt = (
        "You are a step summarizer. Given the tool calls and results from an agent step, "
        "produce a structured JSON summary. Be concise.\n\n"
        f"Task: {task_desc[:200]}\n"
        f"Agent's own summary: {step_result.summary}\n\n"
        f"Step transcript:\n{step_text}\n\n"
        "Respond with ONLY a JSON object:\n"
        "{\n"
        '  "summary": "1-2 sentence summary of what happened",\n'
        '  "files_to_preload": ["path1", "path2"],  // files the next step will likely need (max 5)\n'
        '  "changes_made": "what files were changed and why (empty if read-only step)",\n'
        '  "discovered": "key classes, functions, patterns, or values found",\n'
        '  "pending": "what still needs to be done",\n'
        '  "anti_patterns": "failed approaches, loops, or repeated errors to avoid"\n'
        "}"
    )

    try:
        resp = call_llm(
            llm_params,
            [
                {"role": "system", "content": "You are a concise step summarizer. Respond with JSON only."},
                {"role": "user", "content": summarizer_prompt},
            ],
        )
        content = (resp.choices[0].message.content or "").strip()

        # Extract JSON from response
        brace_start = content.find("{")
        brace_end = content.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            data = json.loads(content[brace_start:brace_end + 1])
            return {
                "summary": data.get("summary", step_result.summary),
                "files_to_preload": data.get("files_to_preload", [])[:5],
                "changes_made": data.get("changes_made", ""),
                "discovered": data.get("discovered", ""),
                "pending": data.get("pending", ""),
                "anti_patterns": data.get("anti_patterns", ""),
            }
    except Exception as exc:
        logger.debug("Step summarizer failed: %s", exc)

    return {
        "summary": step_result.summary,
        "files_to_preload": [],
        "changes_made": "",
        "discovered": "",
        "pending": "",
        "anti_patterns": "",
    }


def _truncate_step_messages(messages: list[dict[str, Any]], max_tokens: int) -> str:
    """Truncate step messages to fit within the summarizer's input budget."""
    lines: list[str] = []
    char_budget = max_tokens * 4  # ~4 chars per token

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        line = f"[{role}] {content}"
        if len(line) > 500:
            line = line[:497] + "..."
        lines.append(line)

    text = "\n".join(lines)
    if len(text) > char_budget:
        text = text[:char_budget] + "\n... (truncated)"
    return text


class LoopEngine(AgentEngine):
    """Plan-execute-summarize loop engine.

    Each iteration rebuilds the prompt from scratch with only:
    system prompt + task + plan + compact summaries + current step.
    Raw tool output exists only temporarily during a step, then is
    discarded and replaced with a structured summary.
    """

    def __init__(self) -> None:
        self._last_file_tracker: FileChangeTracker | None = None

    def get_changed_files_summary(self) -> str:
        """Return unified diffs of all changed files from the last execution."""
        if not self._last_file_tracker:
            return ""
        parts = []
        for path in self._last_file_tracker.get_all_paths():
            diff = self._last_file_tracker.get_diff(path)
            if diff:
                parts.append(diff)
        return "\n\n".join(parts)

    def has_file_changes(self) -> bool:
        """Check if any files were modified during the last execution."""
        return bool(self._last_file_tracker and self._last_file_tracker.get_all_paths())

    def get_file_change_reasons(self) -> dict[str, list[str]]:
        """Return {path: [reasons]} for all changed files."""
        if not self._last_file_tracker:
            return {}
        return {
            path: self._last_file_tracker.get_reasons(path)
            for path in self._last_file_tracker.get_all_paths()
        }

    def get_file_contents(self) -> dict[str, str]:
        """Return {path: content} for all changed files."""
        if not self._last_file_tracker:
            return {}
        result = {}
        for path in self._last_file_tracker.get_all_paths():
            try:
                with open(path) as f:
                    result[path] = f.read()
            except Exception:
                pass
        return result

    def execute(
        self,
        agent: Any,
        task_prompt: tuple[str, str],
        *,
        verbose: bool = True,
        guardrail: Any | None = None,
        guardrail_max_retries: int = 5,
        output_pydantic: type | None = None,
        task_tools: list | None = None,
        event_id: int | None = None,
        resume_state: dict | None = None,
        max_iterations: int | None = None,
        max_total_tool_calls: int | None = None,
        max_tool_calls_per_action: int | None = None,
        nudge_threshold: int | None = None,
        summarizer_enabled: bool | None = None,
        identity_override: str | None = None,
    ) -> str:
        from backend.config.llm import get_litellm_params
        from backend.config.settings import settings

        llm_params = get_litellm_params()
        if llm_params is None:
            raise RuntimeError(
                "LoopEngine requires LiteLLM parameters. "
                "Ensure INFINIBAY_LLM_MODEL is set."
            )

        # Apply settings with optional overrides
        _max_iterations = max_iterations or settings.LOOP_MAX_ITERATIONS
        _max_per_action = max_tool_calls_per_action or settings.LOOP_MAX_TOOL_CALLS_PER_ACTION
        _max_total_calls = max_total_tool_calls or settings.LOOP_MAX_TOTAL_TOOL_CALLS
        history_window = settings.LOOP_HISTORY_WINDOW
        _nudge_threshold = nudge_threshold or settings.LOOP_STEP_NUDGE_THRESHOLD

        # File change tracker
        file_tracker = FileChangeTracker()
        self._last_file_tracker = file_tracker

        # Context budget
        max_context_tokens = _get_model_max_context(llm_params)

        # Resolve tools
        tools = task_tools if task_tools is not None else getattr(agent, "tools", [])
        if task_tools is not None:
            from backend.tools.base.context import bind_tools_to_agent
            bind_tools_to_agent(task_tools, agent.agent_id)

        tool_schemas = build_tool_schemas(tools) if tools else [STEP_COMPLETE_SCHEMA, ADD_NOTE_SCHEMA]
        tool_dispatch = build_tool_dispatch(tools) if tools else {}

        # Check model capabilities for manual tool calling mode
        from backend.config.model_capabilities import get_model_capabilities
        caps = get_model_capabilities()
        manual_tc = not caps.supports_function_calling

        # Build system prompt
        system_prompt = build_system_prompt(
            agent.backstory,
            identity_override=identity_override,
        )

        # For non-FC models, embed tool descriptions in the system prompt
        if manual_tc:
            tools_section = build_tools_prompt_section(tool_schemas)
            system_prompt = f"{system_prompt}\n\n{tools_section}"
            logger.info(
                "LoopEngine [%s]: manual tool calling mode (model lacks FC support)",
                getattr(agent, "agent_id", "?"),
            )

        desc, expected = task_prompt
        agent_name = getattr(agent, "name", agent.agent_id)
        agent_role = getattr(agent, "role", "agent")

        # Read event_id / resume_state from tool context if not passed directly
        if event_id is None or resume_state is None:
            from backend.tools.base.context import get_context_for_agent
            ctx = get_context_for_agent(agent.agent_id)
            if ctx:
                event_id = event_id or ctx.event_id
                resume_state = resume_state or ctx.resume_state

        # Resume from checkpoint or start fresh
        if resume_state:
            state = LoopState.model_validate(resume_state)
            if state.plan.steps and not state.plan.active_step:
                for s in state.plan.steps:
                    if s.status == "pending":
                        s.status = "active"
                        break
            logger.info("LoopEngine: resuming from iteration %d", state.iteration_count)
        else:
            state = LoopState()

        start_iteration = state.iteration_count

        if verbose:
            log_start(agent.agent_id, agent_name, agent_role, desc, len(tools))

        consecutive_all_done = 0

        # --- Outer loop (plan-level) ---
        for iteration in range(start_iteration, _max_iterations):
            state.iteration_count = iteration + 1

            # Apply history window
            effective_state = state
            if history_window > 0 and len(state.history) > history_window:
                effective_state = state.model_copy(deep=True)
                effective_state.history = state.history[-history_window:]

            user_prompt = build_iteration_prompt(
                desc, expected, effective_state,
                max_context_tokens=max_context_tokens,
            )
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            active = state.plan.active_step
            if active:
                active_desc = active.description
            elif not state.plan.steps:
                active_desc = "Planning..."
            else:
                done_steps = [s for s in state.plan.steps if s.status == "done"]
                active_desc = f"Continuing ({done_steps[-1].description})" if done_steps else "Working..."
            if verbose:
                log_step_start(iteration + 1, active_desc)
                log_prompt(user_prompt)

            emit_loop_event("loop_step_update", agent.project_id, agent.agent_id, {
                "agent_id": agent.agent_id,
                "agent_name": agent_name,
                "iteration": iteration + 1,
                "step_description": active_desc,
                "status": "active",
                "summary": "",
                "plan_steps": [
                    {"index": s.index, "description": s.description, "status": s.status}
                    for s in state.plan.steps
                ],
                "tool_calls_step": 0,
                "tool_calls_total": state.total_tool_calls,
                "tokens_total": state.total_tokens,
            })

            # --- Inner loop (function calling within one step) ---
            step_result: StepResult | None = None
            action_tool_calls = 0
            last_tool_sig: str | None = None
            same_tool_streak = 0
            repetition_nudged = False
            consecutive_errors = 0

            is_planning = not state.plan.steps
            planning_schemas = [STEP_COMPLETE_SCHEMA]

            _malformed_retries = 0
            _text_retries = 0

            while action_tool_calls < _max_per_action and state.total_tool_calls < _max_total_calls:
                # ── LLM call ──────────────────────────────────────
                if manual_tc:
                    try:
                        response = call_llm(llm_params, messages)
                    except Exception:
                        raise

                    usage = getattr(response, "usage", None)
                    if usage:
                        state.total_tokens += getattr(usage, "total_tokens", 0)
                        state.last_prompt_tokens = getattr(usage, "prompt_tokens", 0)
                        state.last_completion_tokens = getattr(usage, "completion_tokens", 0)

                    choice = response.choices[0]
                    message = choice.message
                    raw_content = (message.content or "").strip()

                    parsed_calls = parse_text_tool_calls(raw_content)
                    if parsed_calls:
                        _malformed_retries = 0
                        _text_retries = 0
                        tool_calls = []
                        for i, pc in enumerate(parsed_calls):
                            tc_obj = ManualToolCall(
                                id=f"manual_{action_tool_calls + i}",
                                name=pc["name"],
                                arguments=(
                                    json.dumps(pc["arguments"])
                                    if isinstance(pc["arguments"], dict)
                                    else str(pc["arguments"])
                                ),
                            )
                            tool_calls.append(tc_obj)
                    else:
                        tool_calls = None
                else:
                    iter_tools = planning_schemas if is_planning else tool_schemas
                    try:
                        response = call_llm(
                            llm_params, messages, iter_tools, tool_choice="required",
                        )
                    except Exception as exc:
                        if is_malformed_tool_call(exc):
                            _malformed_retries += 1
                            log(
                                f"{YELLOW}⚠ Malformed tool call "
                                f"(attempt {_malformed_retries}/{_MAX_MALFORMED_RETRIES}): "
                                f"{str(exc)[:120]}{RESET}"
                            )
                            if _malformed_retries < _MAX_MALFORMED_RETRIES:
                                continue
                            log(f"{RED}⚠ Malformed tool calls persisted — forcing step completion{RESET}")
                            step_result = StepResult(
                                summary=(
                                    f"Step interrupted: LLM produced malformed tool calls "
                                    f"({_malformed_retries} attempts). Will retry on next step."
                                ),
                                status="continue",
                            )
                            break
                        exc_msg = str(exc).lower()
                        if any(p in exc_msg for p in PERMANENT_ERRORS):
                            log(
                                f"{YELLOW}⚠ Provider rejected function calling: "
                                f"{str(exc)[:120]} — switching to manual tool calling{RESET}"
                            )
                            manual_tc = True
                            tools_section = build_tools_prompt_section(tool_schemas)
                            system_prompt = build_system_prompt(
                                agent.backstory, identity_override=identity_override,
                            )
                            system_prompt = f"{system_prompt}\n\n{tools_section}"
                            messages[0] = {"role": "system", "content": system_prompt}
                            continue
                        raise

                    _malformed_retries = 0

                    usage = getattr(response, "usage", None)
                    if usage:
                        state.total_tokens += getattr(usage, "total_tokens", 0)
                        state.last_prompt_tokens = getattr(usage, "prompt_tokens", 0)
                        state.last_completion_tokens = getattr(usage, "completion_tokens", 0)

                    choice = response.choices[0]
                    message = choice.message
                    tool_calls = getattr(message, "tool_calls", None)

                # ── Process tool calls ────────────────────────────
                if tool_calls:
                    _text_retries = 0

                    # Separate by type: regular, step_complete, add_note, think
                    regular_calls = []
                    sc_call = None
                    note_calls = []
                    think_calls = []

                    for tc in tool_calls:
                        name = tc.function.name
                        if name == "step_complete":
                            sc_call = tc
                        elif name == "add_note":
                            note_calls.append(tc)
                        elif name == "think":
                            think_calls.append(tc)
                        else:
                            regular_calls.append(tc)

                    # Handle think calls (reasoning, doesn't count as tool call)
                    for tc in think_calls:
                        try:
                            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments or {}
                            thought = args.get("thought", "")
                            if thought and verbose:
                                log(f"{BLUE}│{RESET}  {DIM}💭 think: {thought[:150]}{RESET}")
                        except Exception:
                            pass

                    # Handle add_note calls
                    for tc in note_calls:
                        try:
                            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments or {}
                            note = args.get("note", "")
                            if note and len(state.notes) < 20:
                                state.notes.append(note)
                                state.tool_calls_since_last_note = 0
                                if verbose:
                                    log(f"{BLUE}│{RESET}  {DIM}📝 note: {note[:100]}{RESET}")
                        except Exception:
                            pass

                    # Execute regular tool calls with batching
                    if regular_calls:
                        if manual_tc:
                            messages.append({
                                "role": "assistant",
                                "content": getattr(message, "content", "") or raw_content,
                            })
                        else:
                            assistant_msg: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
                            all_tc_for_msg = regular_calls + note_calls + think_calls
                            if sc_call:
                                all_tc_for_msg.append(sc_call)
                            assistant_msg["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in all_tc_for_msg
                            ]
                            messages.append(assistant_msg)

                            # Add tool results for pseudo-tools
                            for tc in think_calls + note_calls:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": '{"status": "ok"}',
                                })

                        # Batch and execute regular tools
                        batches = batch_tool_calls(regular_calls)
                        tool_results_text: list[str] = []

                        for batch in batches:
                            # Capture pre-content for file change tracking
                            pre_contents: dict[str, str | None] = {}
                            for tc in batch:
                                pre = capture_pre_content(
                                    tc.function.name, tc.function.arguments, file_tracker,
                                )
                                pre_contents[tc.id] = pre

                            # Execute batch (parallel for reads, sequential for writes)
                            batch_results = execute_tool_calls_parallel(batch, tool_dispatch)

                            for tc, result in batch_results:
                                # Track tool errors
                                _tool_error = extract_tool_error(result)
                                if _tool_error:
                                    consecutive_errors += 1
                                else:
                                    consecutive_errors = 0

                                # File change tracking
                                maybe_emit_file_change(
                                    tc.function.name, tc.function.arguments, result,
                                    pre_contents.get(tc.id), file_tracker,
                                    agent.project_id, agent.agent_id,
                                )

                                # Update opened files cache
                                update_opened_files_cache(
                                    state, tc.function.name, tc.function.arguments, result,
                                )

                                if manual_tc:
                                    tool_results_text.append(
                                        f"[Tool: {tc.function.name}] Result:\n{result}"
                                    )
                                else:
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc.id,
                                        "content": result,
                                    })

                                action_tool_calls += 1
                                state.total_tool_calls += 1
                                state.tool_calls_since_last_note += 1

                                tool_detail = extract_tool_detail(tc.function.name, tc.function.arguments)

                                if verbose:
                                    log_tool(agent_name, iteration + 1, tc.function.name, action_tool_calls, state.total_tool_calls)
                                    if tool_detail:
                                        log(f"{BLUE}│{RESET}     {DIM}{tool_detail}{RESET}")
                                    if _tool_error:
                                        log(f"{BLUE}│{RESET}     {RED}✗ {_tool_error}{RESET}")

                                emit_loop_event("loop_tool_call", agent.project_id, agent.agent_id, {
                                    "agent_id": agent.agent_id,
                                    "agent_name": agent_name,
                                    "tool_name": tc.function.name,
                                    "tool_detail": tool_detail,
                                    "tool_error": _tool_error,
                                    "call_num": action_tool_calls,
                                    "total_calls": state.total_tool_calls,
                                    "iteration": iteration + 1,
                                })

                        # Tick opened files cache
                        state.tick_opened_files(len(regular_calls))

                        # Manual mode: send all tool results as a single user message
                        if manual_tc and tool_results_text:
                            messages.append({
                                "role": "user",
                                "content": "\n\n".join(tool_results_text),
                            })

                        # step_complete tool result
                        if sc_call and not manual_tc:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": sc_call.id,
                                "content": '{"status": "acknowledged"}',
                            })

                        # Track consecutive identical calls
                        batch_tool = regular_calls[-1].function.name
                        batch_args = regular_calls[-1].function.arguments
                        batch_sig = f"{batch_tool}:{batch_args}"
                        if batch_sig == last_tool_sig:
                            same_tool_streak += 1
                        else:
                            last_tool_sig = batch_sig
                            same_tool_streak = 1
                            repetition_nudged = False

                    elif sc_call:
                        # Only step_complete (and possibly pseudo-tools), no regular tools
                        if manual_tc:
                            messages.append({
                                "role": "assistant",
                                "content": getattr(message, "content", "") or raw_content,
                            })
                        else:
                            assistant_msg = {"role": "assistant", "content": message.content or ""}
                            all_tc_for_msg = note_calls + think_calls + [sc_call]
                            assistant_msg["tool_calls"] = [{
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            } for tc in all_tc_for_msg]
                            messages.append(assistant_msg)
                            for tc in think_calls + note_calls:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": '{"status": "ok"}',
                                })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": sc_call.id,
                                "content": '{"status": "acknowledged"}',
                            })

                    # Parse step_complete
                    if sc_call:
                        step_result = parse_step_complete_args(sc_call.function.arguments)
                        break

                    # Circuit breaker: too many consecutive errors
                    if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                        log(
                            f"{RED}⚠ {consecutive_errors} consecutive tool errors — "
                            f"forcing step completion{RESET}"
                        )
                        step_result = StepResult(
                            summary=f"Step interrupted: {consecutive_errors} consecutive tool errors.",
                            status="continue",
                        )
                        break

                    # Detect identical tool call repetition
                    _loop_tool = (last_tool_sig or "").split(":", 1)[0]
                    if same_tool_streak >= _MAX_SAME_TOOL_CONSECUTIVE and not repetition_nudged:
                        repetition_nudged = True
                        log(
                            f"{YELLOW}⚠ Identical '{_loop_tool}' call repeated "
                            f"{same_tool_streak}x — nudging step_complete{RESET}"
                        )
                        messages.append({
                            "role": "user",
                            "content": (
                                f"STOP: You have made the exact same '{_loop_tool}' call "
                                f"{same_tool_streak} times in a row with identical arguments. "
                                f"This is a loop. You MUST now call the step_complete "
                                f"tool to summarize what you've accomplished and move on."
                            ),
                        })
                        continue
                    if same_tool_streak >= _MAX_SAME_TOOL_CONSECUTIVE + 2:
                        log(
                            f"{RED}⚠ Tool loop: identical '{_loop_tool}' call "
                            f"{same_tool_streak}x — forcing step completion{RESET}"
                        )
                        step_result = StepResult(
                            summary=(
                                f"Step interrupted: identical {_loop_tool} calls "
                                f"({same_tool_streak}x) without progress."
                            ),
                            status="continue",
                        )
                        break

                    # Nudge at threshold
                    if action_tool_calls >= _nudge_threshold and action_tool_calls % _nudge_threshold == 0:
                        messages.append({
                            "role": "user",
                            "content": (
                                f"[Tool call {action_tool_calls}/{_max_per_action}] "
                                f"You have made {action_tool_calls} tool calls in this step. "
                                f"Consider calling step_complete to wrap up this step."
                            ),
                        })

                else:
                    # LLM responded with text instead of tool calls
                    content = (message.content or "").strip()
                    _text_retries += 1
                    logger.warning(
                        "LoopEngine [%s]: text instead of tool call (attempt %d/%d): %s",
                        agent.agent_id, _text_retries, _MAX_TEXT_RETRIES, content[:200],
                    )

                    if _text_retries < _MAX_TEXT_RETRIES:
                        log(
                            f"{YELLOW}⚠ Text instead of tool call "
                            f"(retry {_text_retries}/{_MAX_TEXT_RETRIES}){RESET}"
                        )
                        truncated = content[:500] + ("..." if len(content) > 500 else "")
                        messages.append({"role": "assistant", "content": content})
                        if manual_tc:
                            nudge = (
                                "Your response could not be parsed as a tool call. "
                                "You MUST respond with a JSON object containing a "
                                '"tool_calls" array. Example:\n'
                                '{"tool_calls": [{"name": "step_complete", '
                                '"arguments": {"summary": "...", "status": "continue"}}]}\n\n'
                                f"Your response was: {truncated}"
                            )
                        else:
                            nudge = (
                                "You responded with text but you MUST call a tool. "
                                f"Your response was: {truncated}\n\n"
                                "Call the appropriate tool to proceed, or call "
                                "step_complete if you are done with this step."
                            )
                        messages.append({"role": "user", "content": nudge})
                        continue

                    log(
                        f"{RED}⚠ Text {_text_retries}x — forcing step completion{RESET}"
                    )
                    if len(content) > 200:
                        content = content[:197] + "..."
                    step_result = StepResult(
                        summary=content or "Step completed (provider ignored tool_choice=required).",
                        status="continue",
                    )
                    break
            else:
                if step_result is None:
                    step_result = StepResult(
                        summary=f"Step interrupted: tool call limit reached ({action_tool_calls} calls).",
                        status="continue",
                    )
                    log(f"{RED}⚠ Inner loop exhausted after {action_tool_calls} tool calls{RESET}")

            if step_result is None:
                step_result = StepResult(summary="Step completed.", status="continue")

            # --- Step summarizer (dedicated LLM call for structured summary) ---
            summary_data = _summarize_step(messages, desc, state, step_result, llm_params)

            # --- Plan management ---
            if not state.plan.steps:
                if step_result.next_steps:
                    state.plan.apply_operations(step_result.next_steps)
                if state.plan.steps:
                    for s in state.plan.steps:
                        if s.status == "pending":
                            s.status = "active"
                            break
            else:
                state.plan.mark_active_done()
                if step_result.next_steps:
                    state.plan.apply_operations(step_result.next_steps)
                state.plan.activate_next()

            step_index = state.plan.active_step.index if state.plan.active_step else iteration + 1
            done_steps = [s for s in state.plan.steps if s.status == "done"]
            if done_steps:
                step_index = done_steps[-1].index

            state.history.append(ActionRecord(
                step_index=step_index,
                summary=summary_data["summary"],
                tool_calls_count=action_tool_calls,
                files_to_preload=summary_data.get("files_to_preload", []),
                changes_made=summary_data.get("changes_made", ""),
                discovered_context=summary_data.get("discovered", ""),
                pending_items=summary_data.get("pending", ""),
                anti_patterns=summary_data.get("anti_patterns", ""),
            ))

            # Pre-load recommended files for next step
            for preload_path in summary_data.get("files_to_preload", [])[:5]:
                try:
                    if preload_path not in state.opened_files:
                        with open(preload_path) as f:
                            content = f.read()
                        lines = content.splitlines()
                        width = len(str(len(lines)))
                        numbered = "\n".join(f"{i+1:>{width}}  {line}" for i, line in enumerate(lines))
                        state.cache_file(preload_path, numbered)
                except Exception:
                    pass

            state.current_step_index = step_index

            if verbose:
                log_step_done(iteration + 1, step_result.status, step_result.summary, action_tool_calls, state.total_tokens)
                log_plan(state.plan)

            # Emit step-done
            next_active = state.plan.active_step
            done_desc = next_active.description if next_active else (step_result.summary[:120] if step_result.summary else active_desc)
            emit_loop_event("loop_step_update", agent.project_id, agent.agent_id, {
                "agent_id": agent.agent_id,
                "agent_name": agent_name,
                "iteration": iteration + 1,
                "step_description": done_desc,
                "status": step_result.status,
                "summary": step_result.summary[:200],
                "plan_steps": [
                    {"index": s.index, "description": s.description, "status": s.status}
                    for s in state.plan.steps
                ],
                "tool_calls_step": action_tool_calls,
                "tool_calls_total": state.total_tool_calls,
                "tokens_total": state.total_tokens,
            })

            # Checkpoint
            if event_id:
                self._checkpoint(event_id, state)

            # --- Check termination ---
            if step_result.status == "done":
                file_tracker.deactivate()
                if verbose:
                    log_finish(agent_name, "done", iteration + 1, state.total_tool_calls, state.total_tokens)
                emit_loop_event("loop_finished", agent.project_id, agent.agent_id, {
                    "agent_id": agent.agent_id, "agent_name": agent_name,
                    "status": "done", "iterations": iteration + 1,
                    "tool_calls_total": state.total_tool_calls, "tokens_total": state.total_tokens,
                })
                result = step_result.final_answer or step_result.summary
                return self._apply_guardrail(
                    result, guardrail, guardrail_max_retries,
                    llm_params, system_prompt, desc, expected, state, tool_schemas, tool_dispatch,
                )

            if step_result.status == "blocked":
                file_tracker.deactivate()
                if verbose:
                    log_finish(agent_name, "blocked", iteration + 1, state.total_tool_calls, state.total_tokens)
                emit_loop_event("loop_finished", agent.project_id, agent.agent_id, {
                    "agent_id": agent.agent_id, "agent_name": agent_name,
                    "status": "blocked", "iterations": iteration + 1,
                    "tool_calls_total": state.total_tool_calls, "tokens_total": state.total_tokens,
                })
                return f"Blocked: {step_result.summary}"

            if state.plan.steps and not state.plan.has_pending:
                consecutive_all_done += 1
                if consecutive_all_done >= 2:
                    file_tracker.deactivate()
                    if verbose:
                        log_finish(agent_name, "done", iteration + 1, state.total_tool_calls, state.total_tokens)
                    emit_loop_event("loop_finished", agent.project_id, agent.agent_id, {
                        "agent_id": agent.agent_id, "agent_name": agent_name,
                        "status": "done", "iterations": iteration + 1,
                        "tool_calls_total": state.total_tool_calls, "tokens_total": state.total_tokens,
                    })
                    result = step_result.summary
                    return self._apply_guardrail(
                        result, guardrail, guardrail_max_retries,
                        llm_params, system_prompt, desc, expected, state, tool_schemas, tool_dispatch,
                    )
            else:
                consecutive_all_done = 0

        # Outer loop exhausted
        file_tracker.deactivate()
        if verbose:
            log_finish(agent_name, "exhausted", _max_iterations, state.total_tool_calls, state.total_tokens)
        emit_loop_event("loop_finished", agent.project_id, agent.agent_id, {
            "agent_id": agent.agent_id, "agent_name": agent_name,
            "status": "exhausted", "iterations": _max_iterations,
            "tool_calls_total": state.total_tool_calls, "tokens_total": state.total_tokens,
        })
        return _synthesize_final(state)

    def _checkpoint(self, event_id: int, state: LoopState) -> None:
        """Persist LoopState to agent_events.progress_json for crash recovery."""
        try:
            from backend.autonomy.events import update_event_status
            update_event_status(
                event_id,
                "in_progress",
                progress={"loop_state": state.model_dump()},
            )
        except Exception:
            logger.debug("Checkpoint failed for event %d", event_id, exc_info=True)

        # Heartbeat
        try:
            import sqlite3
            from backend.autonomy.db import execute_with_retry as _db_exec

            def _heartbeat(conn: sqlite3.Connection) -> None:
                conn.execute(
                    """UPDATE agent_loop_state
                       SET last_poll_at = CURRENT_TIMESTAMP,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE current_event_id = ?""",
                    (event_id,),
                )
                conn.commit()

            _db_exec(_heartbeat)
        except Exception:
            pass

    def _apply_guardrail(
        self,
        result: str,
        guardrail: Any | None,
        max_retries: int,
        llm_params: dict[str, Any],
        system_prompt: str,
        desc: str,
        expected: str,
        state: LoopState,
        tool_schemas: list[dict[str, Any]],
        tool_dispatch: dict[str, Any],
    ) -> str:
        """Validate result with guardrail; retry with feedback if it fails."""
        if guardrail is None:
            return result

        from backend.config.settings import settings
        max_per_action = settings.LOOP_MAX_TOOL_CALLS_PER_ACTION

        for attempt in range(max_retries):
            try:
                validation = guardrail(result)
                if isinstance(validation, tuple):
                    success, feedback = validation
                    if success:
                        return result
                    logger.info(
                        "Guardrail failed (attempt %d/%d): %s",
                        attempt + 1, max_retries, str(feedback)[:200],
                    )
                    feedback_prompt = (
                        f"Your previous output was rejected by validation.\n"
                        f"Feedback: {feedback}\n\n"
                        f"Please fix your output and try again.\n\n"
                        f"Previous output:\n{result}"
                    )
                    messages: list[dict[str, Any]] = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": feedback_prompt},
                    ]

                    step_text = ""
                    action_tool_calls = 0
                    while action_tool_calls < max_per_action:
                        response = call_llm(
                            llm_params, messages,
                            tool_schemas if tool_schemas else None,
                        )
                        choice = response.choices[0]
                        msg = choice.message
                        tc_list = getattr(msg, "tool_calls", None)
                        if tc_list:
                            assistant_msg: dict[str, Any] = {
                                "role": "assistant",
                                "content": msg.content or "",
                            }
                            assistant_msg["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in tc_list
                            ]
                            messages.append(assistant_msg)
                            for tc in tc_list:
                                if tc.function.name == "step_complete":
                                    sr = parse_step_complete_args(tc.function.arguments)
                                    step_text = sr.final_answer or sr.summary
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc.id,
                                        "content": '{"status": "acknowledged"}',
                                    })
                                    break
                                tc_result = execute_tool_call(
                                    tool_dispatch,
                                    tc.function.name,
                                    tc.function.arguments,
                                )
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": tc_result,
                                })
                                action_tool_calls += 1
                            if step_text:
                                break
                        else:
                            step_text = msg.content or ""
                            break

                    result = step_text or result
                else:
                    if validation:
                        return result
            except Exception as exc:
                logger.warning("Guardrail raised exception: %s", exc)

        return result

"""Bridge between CrewAI's internal event system and PABADA's EventBus.

CrewAI emits fine-grained events for agent execution, tool usage, LLM calls,
and flow lifecycle. This module registers a single ``BaseEventListener`` that
relays the most useful events into our EventBus → WebSocket → UI pipeline.

Usage:
    Call ``register_crewai_event_bridge()`` once at startup (e.g. in
    ``backend/api/run.py``). The listener instance MUST be kept alive at
    module level to avoid garbage collection.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from crewai.events.base_event_listener import BaseEventListener as CrewAIBaseEventListener
from crewai.events.event_types import (
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
    FlowFinishedEvent,
    FlowStartedEvent,
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)

logger = logging.getLogger(__name__)


class PabadaCrewAIEventBridge(CrewAIBaseEventListener):
    """Bridges CrewAI events into PABADA's EventBus.

    Relays agent execution, tool usage, LLM calls, and flow lifecycle
    events so they appear in the WebSocket activity feed.
    """

    def setup_listeners(self, crewai_event_bus: Any) -> None:
        """Register handlers on the CrewAI event bus."""

        # ── Agent events ─────────────────────────────────────────────

        @crewai_event_bus.on(AgentExecutionStartedEvent)
        def on_agent_start(source: Any, event: AgentExecutionStartedEvent) -> None:
            self._emit("crewai_agent_started", {
                "agent_role": getattr(event, "agent", {}).get("role", "unknown")
                if isinstance(getattr(event, "agent", None), dict)
                else str(getattr(event, "agent", "unknown")),
            })

        @crewai_event_bus.on(AgentExecutionCompletedEvent)
        def on_agent_complete(source: Any, event: AgentExecutionCompletedEvent) -> None:
            self._emit("crewai_agent_completed", {
                "agent_role": getattr(event, "agent", {}).get("role", "unknown")
                if isinstance(getattr(event, "agent", None), dict)
                else str(getattr(event, "agent", "unknown")),
            })

        @crewai_event_bus.on(AgentExecutionErrorEvent)
        def on_agent_error(source: Any, event: AgentExecutionErrorEvent) -> None:
            self._emit("crewai_agent_error", {
                "error": str(getattr(event, "error", "unknown"))[:300],
            })

        # ── Task events ──────────────────────────────────────────────

        @crewai_event_bus.on(TaskStartedEvent)
        def on_task_start(source: Any, event: TaskStartedEvent) -> None:
            task_desc = str(getattr(event, "task", ""))[:200]
            self._emit("crewai_task_started", {"description": task_desc})

        @crewai_event_bus.on(TaskCompletedEvent)
        def on_task_complete(source: Any, event: TaskCompletedEvent) -> None:
            self._emit("crewai_task_completed", {})

        @crewai_event_bus.on(TaskFailedEvent)
        def on_task_failed(source: Any, event: TaskFailedEvent) -> None:
            self._emit("crewai_task_failed", {
                "error": str(getattr(event, "error", "unknown"))[:300],
            })

        # ── Tool events ──────────────────────────────────────────────

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def on_tool_start(source: Any, event: ToolUsageStartedEvent) -> None:
            self._emit("crewai_tool_started", {
                "tool_name": str(getattr(event, "tool_name", "unknown")),
            })

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_finish(source: Any, event: ToolUsageFinishedEvent) -> None:
            self._emit("crewai_tool_finished", {
                "tool_name": str(getattr(event, "tool_name", "unknown")),
            })

        @crewai_event_bus.on(ToolUsageErrorEvent)
        def on_tool_error(source: Any, event: ToolUsageErrorEvent) -> None:
            self._emit("crewai_tool_error", {
                "tool_name": str(getattr(event, "tool_name", "unknown")),
                "error": str(getattr(event, "error", "unknown"))[:300],
            })

        # ── LLM events ───────────────────────────────────────────────

        @crewai_event_bus.on(LLMCallStartedEvent)
        def on_llm_start(source: Any, event: LLMCallStartedEvent) -> None:
            self._emit("crewai_llm_started", {})

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_complete(source: Any, event: LLMCallCompletedEvent) -> None:
            # Extract token usage if available
            usage = {}
            response = getattr(event, "response", None)
            if response and hasattr(response, "usage"):
                u = response.usage
                usage = {
                    "prompt_tokens": getattr(u, "prompt_tokens", 0),
                    "completion_tokens": getattr(u, "completion_tokens", 0),
                }
            self._emit("crewai_llm_completed", usage)

        @crewai_event_bus.on(LLMCallFailedEvent)
        def on_llm_failed(source: Any, event: LLMCallFailedEvent) -> None:
            self._emit("crewai_llm_failed", {
                "error": str(getattr(event, "error", "unknown"))[:300],
            })

        # ── Crew events ──────────────────────────────────────────────

        @crewai_event_bus.on(CrewKickoffStartedEvent)
        def on_crew_start(source: Any, event: CrewKickoffStartedEvent) -> None:
            self._emit("crewai_crew_started", {})

        @crewai_event_bus.on(CrewKickoffCompletedEvent)
        def on_crew_complete(source: Any, event: CrewKickoffCompletedEvent) -> None:
            self._emit("crewai_crew_completed", {})

        @crewai_event_bus.on(CrewKickoffFailedEvent)
        def on_crew_failed(source: Any, event: CrewKickoffFailedEvent) -> None:
            self._emit("crewai_crew_failed", {
                "error": str(getattr(event, "error", "unknown"))[:300],
            })

        # ── Flow events ──────────────────────────────────────────────

        @crewai_event_bus.on(FlowStartedEvent)
        def on_flow_start(source: Any, event: FlowStartedEvent) -> None:
            self._emit("crewai_flow_started", {
                "flow": str(getattr(event, "flow_name", "unknown")),
            })

        @crewai_event_bus.on(FlowFinishedEvent)
        def on_flow_finish(source: Any, event: FlowFinishedEvent) -> None:
            self._emit("crewai_flow_finished", {
                "flow": str(getattr(event, "flow_name", "unknown")),
            })

        logger.info("PabadaCrewAIEventBridge: registered all CrewAI event handlers")

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit a CrewAI event to the PABADA EventBus."""
        try:
            from backend.flows.event_listeners import FlowEvent, event_bus

            data["_source"] = "crewai"
            data["_timestamp"] = time.time()
            event_bus.emit(FlowEvent(
                event_type=event_type,
                project_id=0,  # CrewAI events are global, not project-scoped
                entity_type="system",
                data=data,
            ))
        except Exception:
            logger.debug(
                "PabadaCrewAIEventBridge: could not emit %s", event_type,
                exc_info=True,
            )


# Module-level instance — must stay alive to avoid GC of listeners
_bridge_instance: PabadaCrewAIEventBridge | None = None


def register_crewai_event_bridge() -> None:
    """Instantiate and register the CrewAI → PABADA event bridge.

    Safe to call multiple times; only the first call creates the bridge.
    """
    global _bridge_instance
    if _bridge_instance is not None:
        return
    _bridge_instance = PabadaCrewAIEventBridge()
    logger.info("CrewAI event bridge registered")

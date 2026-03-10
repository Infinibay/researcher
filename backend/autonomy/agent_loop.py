"""Core event-driven loop per agent — replaces AutonomyScheduler + AgentWorker.

Each agent gets a single ``AgentLoop`` that:
1. Polls ``agent_events`` for pending work
2. Uses a role-specific evaluator to pick the best event
3. Atomically claims the event
4. Dispatches to the appropriate handler
5. Marks the event completed or failed
6. Recovers in-progress events on restart

``AgentLoopManager`` manages the lifecycle of all loops for a project.

Import safety: uses ``backend.autonomy.db`` to avoid circular imports.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from typing import Any

from backend.autonomy.db import execute_with_retry
from backend.autonomy.evaluators import EvalContext, get_evaluator_for_role
from backend.autonomy.events import (
    atomic_claim_event,
    get_event_by_id,
    load_loop_state,
    poll_pending_events,
    save_loop_state,
    update_event_status,
)
from backend.autonomy.handlers import build_handler_map
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# Roles eligible for agent loops
_LOOP_ELIGIBLE_ROLES = frozenset({
    "developer", "researcher", "team_lead",
    "code_reviewer", "research_reviewer",
    "project_lead",
})


class AgentLoop:
    """Single event-driven loop per agent."""

    def __init__(self, agent_id: str, project_id: int, role: str) -> None:
        self.agent_id = agent_id
        self.project_id = project_id
        self.role = role
        self.evaluator = get_evaluator_for_role(role)
        self.handlers = build_handler_map()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # starts unpaused
        self._thread: threading.Thread | None = None

        # Timing
        self._base_interval = settings.AGENT_LOOP_POLL_INTERVAL
        self._current_interval = self._base_interval
        self._max_interval = settings.AGENT_LOOP_MAX_IDLE_INTERVAL

        # Error tracking
        self._consecutive_errors = 0
        self._error_threshold = settings.AGENT_LOOP_ERROR_THRESHOLD

        # Action budget
        self._actions_this_hour = 0
        self._hour_start = 0.0
        self._max_actions_per_hour = settings.AGENT_LOOP_MAX_ACTIONS_PER_HOUR

    def start(self) -> None:
        """Start the agent loop in a daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("AgentLoop already running for %s", self.agent_id)
            return

        self._stop_event.clear()
        self._hour_start = time.monotonic()

        self._thread = threading.Thread(
            target=self._run,
            name=f"AgentLoop-{self.agent_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "AgentLoop started for %s (role=%s, interval=%.0fs)",
            self.agent_id, self.role, self._base_interval,
        )

    def stop(self) -> None:
        """Signal the loop to stop and wait for it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("AgentLoop thread for %s did not stop in time", self.agent_id)
            self._thread = None

        # Update loop state to stopped
        try:
            save_loop_state(self.agent_id, self.project_id, None, "stopped")
        except Exception:
            pass
        logger.info("AgentLoop stopped for %s", self.agent_id)

    def pause(self) -> None:
        """Pause the loop — it will idle until resumed."""
        self._pause_event.clear()
        logger.info("AgentLoop paused for %s", self.agent_id)

    def resume(self) -> None:
        """Resume a paused loop."""
        self._pause_event.set()
        logger.info("AgentLoop resumed for %s", self.agent_id)

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Main entry point: recover then loop."""
        try:
            self._recover_in_progress()
        except Exception:
            logger.exception("AgentLoop: recovery failed for %s", self.agent_id)

        self._loop()

    def _recover_in_progress(self) -> None:
        """On startup: check for an event that was in_progress when we crashed."""
        state = load_loop_state(self.agent_id)
        if not state or not state.get("current_event_id"):
            return

        event = get_event_by_id(state["current_event_id"])
        if not event or event["status"] != "in_progress":
            # Clear stale state
            save_loop_state(self.agent_id, self.project_id, None, "idle")
            return

        # Extract LoopEngine checkpoint from progress_json for crash recovery
        progress = event.get("progress_json")
        if progress:
            try:
                progress_data = json.loads(progress) if isinstance(progress, str) else progress
                loop_state = progress_data.get("loop_state")
                if loop_state:
                    event["_resume_state"] = loop_state
            except (json.JSONDecodeError, TypeError):
                pass

        logger.info(
            "AgentLoop: recovering in-progress event %d for %s%s",
            event["id"], self.agent_id,
            " (with checkpoint)" if event.get("_resume_state") else "",
        )
        self._execute_event(event)

    def _loop(self) -> None:
        """Main loop: poll → evaluate → claim → execute → complete."""
        consecutive_idles = 0

        while not self._stop_event.is_set():
            # Block while paused (interruptible by stop)
            while not self._pause_event.is_set():
                if self._stop_event.is_set():
                    break
                self._pause_event.wait(timeout=1.0)
            if self._stop_event.is_set():
                break

            # Interruptible sleep
            self._stop_event.wait(timeout=self._current_interval)
            if self._stop_event.is_set():
                break

            # Reset hourly counter
            now = time.monotonic()
            if now - self._hour_start >= 3600:
                self._actions_this_hour = 0
                self._hour_start = now

            try:
                events = poll_pending_events(self.agent_id)
            except Exception:
                logger.exception("AgentLoop: poll failed for %s", self.agent_id)
                self._handle_error()
                continue

            if not events:
                consecutive_idles += 1
                self._current_interval = min(
                    self._base_interval * (2 ** consecutive_idles),
                    self._max_interval,
                )
                # Update poll timestamp
                try:
                    save_loop_state(self.agent_id, self.project_id, None, "idle")
                except Exception:
                    pass

                # Scavenger: after N idle polls, look for orphan tasks
                if consecutive_idles >= settings.AGENT_LOOP_SCAVENGE_AFTER_IDLES:
                    try:
                        from backend.autonomy.scavenger import Scavenger

                        created = Scavenger(self.agent_id, self.project_id, self.role).scavenge()
                        if created > 0:
                            logger.info(
                                "AgentLoop: scavenger created %d events for %s",
                                created, self.agent_id,
                            )
                            consecutive_idles = 0
                            self._current_interval = self._base_interval
                    except Exception:
                        logger.debug(
                            "AgentLoop: scavenger failed for %s",
                            self.agent_id, exc_info=True,
                        )

                continue

            # Reset backoff
            consecutive_idles = 0
            self._current_interval = self._base_interval

            # Build context for scoring
            try:
                context = EvalContext.build(self.project_id)
            except Exception:
                logger.exception("AgentLoop: context build failed for %s", self.agent_id)
                self._handle_error()
                continue

            # Pick best event
            best = self.evaluator.pick_best(events, context)
            if not best:
                continue

            # Don't process events if project isn't executing — but always
            # process user messages regardless of project status.
            if context.project_status not in ("executing", "planning"):
                if best.get("event_type") != "user_message_received":
                    continue

            # Check hourly budget
            if self._actions_this_hour >= self._max_actions_per_hour:
                logger.warning(
                    "AgentLoop: action budget exhausted for %s (%d/%d this hour)",
                    self.agent_id, self._actions_this_hour, self._max_actions_per_hour,
                )
                continue

            # Atomic claim
            if not atomic_claim_event(best["id"], self.agent_id):
                logger.debug("AgentLoop: claim failed for event %d (race)", best["id"])
                continue

            self._actions_this_hour += 1
            self._execute_event(best)

        logger.info("AgentLoop: loop exited for %s", self.agent_id)

    def _execute_event(self, event: dict[str, Any]) -> None:
        """Mark in-progress, dispatch to handler, mark completed/failed."""
        event_type = event.get("event_type", "unknown")

        handler = self.handlers.get(event_type)
        if handler is None:
            logger.warning(
                "AgentLoop: no handler for event type '%s' (event %d)",
                event_type, event["id"],
            )
            update_event_status(event["id"], "failed", error="no handler for event type")
            return

        update_event_status(event["id"], "in_progress")
        save_loop_state(self.agent_id, self.project_id, event["id"], "processing")

        # Set event_id (and resume_state if recovering) in tool context
        # so the LoopEngine can checkpoint and resume.
        from backend.tools.base.context import set_context

        ctx_kwargs: dict[str, Any] = {
            "agent_id": self.agent_id,
            "event_id": event["id"],
        }
        resume = event.get("_resume_state")
        if resume:
            ctx_kwargs["resume_state"] = resume
        set_context(**ctx_kwargs)

        try:
            handler.execute(event)
            update_event_status(event["id"], "completed")
            self._consecutive_errors = 0
            logger.info(
                "AgentLoop: event %d (%s) completed for %s",
                event["id"], event_type, self.agent_id,
            )
        except Exception as exc:
            # During shutdown, agent kills are expected — don't log as error
            from backend.engine.base import AgentKilledError

            if isinstance(exc, AgentKilledError) and self._stop_event.is_set():
                logger.info(
                    "AgentLoop: event %d (%s) interrupted by shutdown for %s",
                    event["id"], event_type, self.agent_id,
                )
                update_event_status(event["id"], "failed", error="shutdown")
            else:
                logger.exception(
                    "AgentLoop: event %d (%s) failed for %s",
                    event["id"], event_type, self.agent_id,
                )
                update_event_status(event["id"], "failed", error=str(exc)[:500])
                self._handle_error()
        finally:
            save_loop_state(self.agent_id, self.project_id, None, "idle")

    def _handle_error(self) -> None:
        """Track consecutive errors and stop if threshold exceeded."""
        self._consecutive_errors += 1
        if self._consecutive_errors >= self._error_threshold:
            logger.error(
                "AgentLoop: stopping %s after %d consecutive errors",
                self.agent_id, self._consecutive_errors,
            )
            self._stop_event.set()


# Module-level registry so flows can access loop managers without circular imports.
_loop_managers: dict[int, "AgentLoopManager"] = {}


def get_loop_manager(project_id: int) -> AgentLoopManager | None:
    """Get the AgentLoopManager for a project (if running)."""
    return _loop_managers.get(project_id)


class AgentLoopManager:
    """Manages AgentLoop lifecycle for all agents in a project."""

    def __init__(self, project_id: int) -> None:
        self.project_id = project_id
        self._loops: dict[str, AgentLoop] = {}
        self._watchdog_thread: threading.Thread | None = None
        self._watchdog_stop = threading.Event()

    def start_all(self) -> None:
        """Query the roster and start an AgentLoop for each eligible agent."""
        roster = self._get_roster()

        for entry in roster:
            agent_id = entry["agent_id"]
            role = entry["role"]

            if role not in _LOOP_ELIGIBLE_ROLES:
                continue

            if not self._is_role_enabled(role):
                logger.debug("AgentLoop: role %s disabled, skipping %s", role, agent_id)
                continue

            loop = AgentLoop(agent_id, self.project_id, role)
            loop.start()
            self._loops[agent_id] = loop

        _loop_managers[self.project_id] = self

        # Start watchdog to recover zombie events
        self._watchdog_stop.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name=f"AgentLoopWatchdog-p{self.project_id}",
            daemon=True,
        )
        self._watchdog_thread.start()

        logger.info(
            "AgentLoopManager started for project %d (%d loops)",
            self.project_id, len(self._loops),
        )

    def pause_all(self) -> None:
        """Pause all agent loops (they idle until resumed)."""
        for loop in self._loops.values():
            loop.pause()
        logger.info("AgentLoopManager: paused all loops for project %d", self.project_id)

    def resume_all(self) -> None:
        """Resume all paused agent loops."""
        for loop in self._loops.values():
            loop.resume()
        logger.info("AgentLoopManager: resumed all loops for project %d", self.project_id)

    def stop(self) -> None:
        """Stop all agent loops (signal + join)."""
        self.stop_signal()
        self.stop_join()

    def stop_signal(self) -> None:
        """Signal all loops to stop (non-blocking)."""
        self._watchdog_stop.set()
        for loop in self._loops.values():
            loop._stop_event.set()

    def stop_join(self) -> None:
        """Join all loop threads and clean up. Call after stop_signal()."""
        if self._watchdog_thread is not None:
            self._watchdog_thread.join(timeout=5.0)
            self._watchdog_thread = None
        for agent_id, loop in self._loops.items():
            loop.stop()
        self._loops.clear()
        _loop_managers.pop(self.project_id, None)
        logger.info("AgentLoopManager stopped for project %d", self.project_id)

    def _watchdog_loop(self) -> None:
        """Periodically recover zombie events and dead-agent tasks."""
        try:
            check_interval = max(float(settings.AGENT_LOOP_EVENT_TIMEOUT) / 4, 60.0)
            dead_agent_interval = max(float(settings.AGENT_LOOP_DEAD_AGENT_TIMEOUT) / 2, 60.0)
        except (TypeError, ValueError):
            check_interval = 60.0
            dead_agent_interval = 600.0
        polls_since_dead_check = 0
        dead_check_every_n = max(1, int(dead_agent_interval / check_interval))

        while not self._watchdog_stop.is_set():
            self._watchdog_stop.wait(timeout=check_interval)
            if self._watchdog_stop.is_set():
                break

            try:
                self._recover_zombie_events()
            except Exception:
                logger.debug(
                    "AgentLoopWatchdog: recovery check failed for project %d",
                    self.project_id, exc_info=True,
                )

            # Periodically check for dead agents and recover their tasks
            polls_since_dead_check += 1
            if polls_since_dead_check >= dead_check_every_n:
                polls_since_dead_check = 0
                try:
                    self._recover_dead_agent_tasks()
                except Exception:
                    logger.debug(
                        "AgentLoopWatchdog: dead agent check failed for project %d",
                        self.project_id, exc_info=True,
                    )

    def _recover_zombie_events(self) -> None:
        """Reset events stuck in in_progress beyond the timeout threshold."""
        timeout_seconds = settings.AGENT_LOOP_EVENT_TIMEOUT

        def _reset(conn: sqlite3.Connection) -> list[tuple[int, str]]:
            rows = conn.execute(
                """SELECT id, agent_id FROM agent_events
                   WHERE project_id = ?
                     AND status = 'in_progress'
                     AND started_at < datetime('now', ? || ' seconds')""",
                (self.project_id, f"-{int(timeout_seconds)}"),
            ).fetchall()

            recovered = []
            for row in rows:
                conn.execute(
                    """UPDATE agent_events SET status = 'failed',
                       error_message = 'watchdog: event exceeded timeout'
                       WHERE id = ? AND status = 'in_progress'""",
                    (row["id"],),
                )
                conn.execute(
                    """UPDATE agent_loop_state SET status = 'idle', current_event_id = NULL
                       WHERE agent_id = ? AND current_event_id = ?""",
                    (row["agent_id"], row["id"]),
                )
                recovered.append((row["id"], row["agent_id"]))
            if recovered:
                conn.commit()
            return recovered

        recovered = execute_with_retry(_reset)
        for event_id, agent_id in recovered:
            logger.warning(
                "AgentLoopWatchdog: recovered zombie event %d for %s (project %d)",
                event_id, agent_id, self.project_id,
            )

    def _recover_dead_agent_tasks(self) -> None:
        """Check for agents whose threads died and recover their tasks."""
        from backend.autonomy.liveness import find_dead_agent_tasks, recover_dead_agent_task

        dead_tasks = find_dead_agent_tasks(self.project_id)
        for dt in dead_tasks:
            agent_id = dt["agent_id"]
            task_id = dt["task_id"]
            seconds = dt.get("seconds_since_poll", 0)

            # Double-check: is the loop thread actually dead?
            loop = self._loops.get(agent_id)
            if loop is not None and loop.is_running:
                # Thread is alive — maybe last_poll_at is stale because
                # the agent is in a long-running handler. Skip.
                continue

            logger.warning(
                "AgentLoopWatchdog: agent %s is dead (no poll for %.0fs), "
                "recovering task %d '%s'",
                agent_id, seconds, task_id, dt.get("task_title", "?"),
            )
            recover_dead_agent_task(task_id, agent_id, reason="watchdog_dead_agent")

            # Try to restart the dead loop
            if loop is not None and not loop.is_running:
                try:
                    loop.start()
                    logger.info(
                        "AgentLoopWatchdog: restarted dead loop for %s", agent_id,
                    )
                except Exception:
                    logger.debug(
                        "AgentLoopWatchdog: could not restart loop for %s",
                        agent_id, exc_info=True,
                    )

    def _get_roster(self) -> list[dict[str, str]]:
        """Query roster directly to avoid circular import through agents.registry."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, str]]:
            rows = conn.execute(
                "SELECT agent_id, name, role, status FROM roster "
                "WHERE agent_id LIKE ? ESCAPE '\\' AND status != 'retired'",
                (f"%\\_p{self.project_id}",),
            ).fetchall()
            return [
                {"agent_id": r["agent_id"], "name": r["name"],
                 "role": r["role"], "status": r["status"]}
                for r in rows
            ]

        return execute_with_retry(_query)

    def _is_role_enabled(self, role: str) -> bool:
        """Check if autonomy is enabled for this role."""
        role_toggle_map = {
            "developer": "AUTONOMY_ENABLE_DEVELOPER",
            "researcher": "AUTONOMY_ENABLE_RESEARCHER",
            "team_lead": "AUTONOMY_ENABLE_TEAM_LEAD",
            "project_lead": "AUTONOMY_ENABLE_PROJECT_LEAD",
        }
        attr = role_toggle_map.get(role)
        if attr is None:
            # Roles without explicit toggles (code_reviewer, research_reviewer)
            # are enabled by default when autonomy is globally enabled
            return True
        return getattr(settings, attr, True)

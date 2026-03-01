"""CodeReviewFlow — manages the code review cycle between developer and reviewer.

Lifecycle: receive request → CI gate → review → approve/reject → rework loop until approval.
No escalation — the cycle continues until the reviewer approves.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method "X" completes or a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes next trigger
- Non-router return values are DATA only, not triggers
"""

from __future__ import annotations

import json
import logging

from crewai.flow.flow import Flow, listen, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.config.settings import settings
from backend.flows.guardrails import validate_review_verdict
from backend.flows.helpers import (
    build_crew,
    get_project_name,
    get_repo_path_for_task,
    get_task_by_id,
    increment_task_retry,
    log_flow_event,
    notify_team_lead,
    parse_ci_output,
    parse_review_result,
    record_ci_result,
    send_agent_message,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.state_models import CodeReviewState, ReviewStatus
from backend.prompts.code_reviewer import tasks as cr_tasks
from backend.prompts.developer import tasks as dev_tasks

logger = logging.getLogger(__name__)


@persist()
class CodeReviewFlow(Flow[CodeReviewState]):
    """Manages the dev/reviewer code review cycle until approval."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def receive_review_request(self):
        """Load task and branch details, prepare for review."""
        logger.info(
            "CodeReviewFlow: receive_review_request (task_id=%d, branch=%s)",
            self.state.task_id, self.state.branch_name,
        )

        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return

        self.state.task_title = task.get("title", "")
        if not self.state.project_name:
            self.state.project_name = get_project_name(self.state.project_id)
        self.state.review_status = ReviewStatus.REVIEWING
        update_task_status(self.state.task_id, "review_ready")

        log_flow_event(
            self.state.project_id, "review_started", "code_review_flow",
            "task", self.state.task_id,
            {"branch_name": self.state.branch_name},
        )

    @router("receive_review_request")
    def route_review_request(self):
        """Route based on whether review request is valid."""
        if self.state.review_status != ReviewStatus.REVIEWING:
            return "error"
        return "review_requested"

    # ── CI helpers ──────────────────────────────────────────────────────

    def _execute_ci_command(self, repo_path: str, test_cmd: str) -> dict:
        """Run the test command via direct subprocess — bypasses pod/sandbox.

        The CI gate is a flow-level check, not an agent action.  Running it
        through ExecuteCommandTool caused failures when pod mode was enabled
        because "ci_gate" is not a real agent with a registered pod.
        """
        import shlex
        import subprocess

        try:
            parts = shlex.split(test_cmd)
            result = subprocess.run(
                parts,
                shell=False,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=repo_path,
            )
            return self._handle_ci_result({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return self._handle_ci_result({"error": f"CI command timed out after 600s"})
        except FileNotFoundError:
            return self._handle_ci_result({"error": f"CI command not found: {test_cmd}"})
        except Exception as e:
            return self._handle_ci_result({"error": f"CI execution failed: {e}"})

    def _handle_ci_result(self, result: dict) -> dict:
        """Translate a raw ExecuteCommandTool result into a structured CI outcome."""
        if "error" in result:
            return {
                "ci_passed": False,
                "ci_output": result["error"],
                "test_count": 0,
                "test_pass": 0,
                "exit_code": 1,
            }

        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        exit_code = result.get("exit_code", 1)
        output = stdout + "\n" + stderr
        test_count, test_pass = parse_ci_output(output)

        return {
            # Exit 0 = tests passed, exit 5 = no tests collected (not a failure)
            "ci_passed": exit_code in (0, 5),
            "ci_output": output[:3000],
            "test_count": test_count,
            "test_pass": test_pass,
            "exit_code": exit_code,
        }

    # ── CI gate ────────────────────────────────────────────────────────────

    @listen("review_requested")
    def run_ci_gate(self):
        """Run the project test suite as an automated CI gate before review."""
        logger.info(
            "CodeReviewFlow: run_ci_gate for task %d (branch=%s)",
            self.state.task_id, self.state.branch_name,
        )

        repo_path = get_repo_path_for_task(self.state.task_id)
        if not repo_path:
            logger.warning(
                "CodeReviewFlow: no repo path found for task %d, skipping CI gate",
                self.state.task_id,
            )
            self.state.ci_passed = True
            self.state.ci_output = "No repository path found — CI gate skipped."
            return

        outcome = self._execute_ci_command(repo_path, settings.CI_TEST_COMMAND)

        self.state.ci_passed = outcome["ci_passed"]
        self.state.ci_output = outcome["ci_output"]

        record_ci_result(
            project_id=self.state.project_id,
            cycle=self.state.rejection_count,
            test_output=outcome["ci_output"],
            test_pass=outcome["test_pass"],
            test_count=outcome["test_count"],
            branch_name=self.state.branch_name,
        )

        if not outcome["ci_passed"]:
            logger.error(
                "CodeReviewFlow: CI gate tool error for task %d",
                self.state.task_id,
            )

        event_type = "ci_gate_passed" if outcome["ci_passed"] else "ci_gate_failed"
        log_flow_event(
            self.state.project_id, event_type, "code_review_flow",
            "task", self.state.task_id,
            {"test_count": outcome["test_count"], "test_pass": outcome["test_pass"],
             "returncode": outcome["exit_code"]},
        )

    @router("run_ci_gate")
    def ci_gate_router(self):
        """Route based on CI gate outcome: ci_passed or ci_failed."""
        return "ready_for_review" if self.state.ci_passed else "ci_failed"

    @listen("ci_failed")
    def handle_ci_failure(self):
        """Handle CI gate failure — notify developer, set task to rejected."""
        logger.warning(
            "CodeReviewFlow: CI gate failed for task %d, returning to developer",
            self.state.task_id,
        )

        update_task_status(self.state.task_id, "rejected")

        failure_summary = self.state.ci_output[:500]
        ci_failure_message = (
            f"CI GATE FAILED for task {self.state.task_id}.\n"
            f"Branch: {self.state.branch_name}\n\n"
            f"Test failure output:\n{failure_summary}\n\n"
            f"Next steps:\n"
            f"1. Read the test failure output above.\n"
            f"2. Fix the failing tests in your code.\n"
            f"3. Re-run the test suite to confirm all tests pass.\n"
            f"4. Commit, push, and set the task back to `review_ready`."
        )

        # Notify the Developer directly
        send_agent_message(
            project_id=self.state.project_id,
            from_agent="code_review_flow",
            to_agent=self.state.developer_id or None,
            to_role="developer" if not self.state.developer_id else None,
            message=ci_failure_message,
        )

        # Also notify Team Lead for visibility
        notify_team_lead(
            self.state.project_id,
            "code_review_flow",
            f"CI gate failed before code review for task {self.state.task_id}.\n"
            f"Branch: {self.state.branch_name}\n"
            f"Failure summary:\n{failure_summary}\n\n"
            f"Developer has been notified to fix failing tests and resubmit.",
        )

        self.state.review_status = ReviewStatus.REJECTED

        log_flow_event(
            self.state.project_id, "ci_gate_rejected", "code_review_flow",
            "task", self.state.task_id,
            {"ci_output_preview": failure_summary},
        )

    # ── Review execution ──────────────────────────────────────────────────

    @listen("ready_for_review")
    def perform_review(self):
        """Code Reviewer agent reviews the code on the branch."""
        logger.info(
            "CodeReviewFlow: perform_review for task %d (attempt %d)",
            self.state.task_id,
            self.state.rejection_count + 1,
        )

        reviewer = get_available_agent_by_role("code_reviewer", self.state.project_id)

        # Double-check claim (flow may be called directly, not only via handler)
        task_check = get_task_by_id(self.state.task_id)
        if task_check and task_check.get("reviewer") and task_check["reviewer"] not in ("", reviewer.agent_id):
            logger.info(
                "CodeReviewFlow: task %d already claimed by %s, skipping",
                self.state.task_id, task_check["reviewer"],
            )
            return
        self.state.reviewer_id = reviewer.agent_id
        reviewer.activate_context(task_id=self.state.task_id)
        run_id = reviewer.create_agent_run(self.state.task_id)
        self.state.agent_run_id = run_id

        task = get_task_by_id(self.state.task_id)
        task_title = task.get("title", "") if task else ""
        task_desc = task.get("description", "") if task else ""

        task_prompt = cr_tasks.perform_review(
            self.state.task_id, task_title,
            self.state.branch_name, task_desc,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
            rejection_count=self.state.rejection_count,
        )
        from backend.tools import get_tools_for_task_type
        crew = build_crew(
            reviewer, task_prompt,
            guardrail=validate_review_verdict,
            task_tools=get_tools_for_task_type("review"),
        )
        try:
            result = str(crew.kickoff()).strip()
        except Exception as exc:
            logger.exception("Crew execution failed in perform_review for task %d", self.state.task_id)
            reviewer.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "review_failed", "code_review_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            raise

        reviewer.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        if parse_review_result(result) == "approved":
            self.state.review_status = ReviewStatus.APPROVED
            self.state.reviewer_comments.append(f"APPROVED: {result}")
            log_flow_event(
                self.state.project_id, "review_approved", "code_review_flow",
                "task", self.state.task_id,
                {"reviewer_id": self.state.reviewer_id, "task_title": task_title,
                 "branch_name": self.state.branch_name},
            )
        else:
            feedback = result
            if ":" in result:
                feedback = result.split(":", 1)[1].strip()
            self.state.review_status = ReviewStatus.REJECTED
            self.state.reviewer_comments.append(f"REJECTED: {feedback}")
            log_flow_event(
                self.state.project_id, "review_rejected", "code_review_flow",
                "task", self.state.task_id,
                {"rejection_count": self.state.rejection_count + 1, "feedback": feedback[:200],
                 "reviewer_id": self.state.reviewer_id, "task_title": task_title,
                 "branch_name": self.state.branch_name},
            )

    # ── Review routing ────────────────────────────────────────────────────

    @router("perform_review")
    def review_outcome_router(self):
        """Route based on review outcome: approved or request rework."""
        if self.state.review_status == ReviewStatus.APPROVED:
            return "review_approved"

        # Rejected — always loop back for rework
        self.state.rejection_count += 1
        increment_task_retry(self.state.task_id)
        return "request_rework"

    # ── Rework cycle ──────────────────────────────────────────────────────

    @router("request_rework")
    def notify_developer_rework(self):
        """Developer reads feedback, applies changes, and resubmits.

        Returns "ready_for_review" → perform_review.
        The cycle continues until the reviewer approves — no escalation.
        """
        logger.info(
            "CodeReviewFlow: requesting rework for task %d (rejection %d)",
            self.state.task_id,
            self.state.rejection_count,
        )

        developer = get_agent_by_role(
            "developer", self.state.project_id,
            agent_id=self.state.developer_id,
        )
        developer.activate_context(task_id=self.state.task_id)
        run_id = developer.create_agent_run(self.state.task_id)

        latest_feedback = self.state.reviewer_comments[-1] if self.state.reviewer_comments else ""

        update_task_status(self.state.task_id, "rejected")

        task_prompt = dev_tasks.rework_code(
            self.state.task_id, self.state.rejection_count,
            latest_feedback, self.state.branch_name,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        from backend.tools import get_tools_for_task_type
        crew = build_crew(
            developer, task_prompt,
            task_tools=get_tools_for_task_type("rework"),
        )
        result = crew.kickoff()

        developer.complete_agent_run(run_id, status="completed", output_summary=str(result)[:500])

        log_flow_event(
            self.state.project_id, "rework_completed", "code_review_flow",
            "task", self.state.task_id,
            {"rejection_count": self.state.rejection_count,
             "developer_id": self.state.developer_id, "task_title": self.state.task_title,
             "branch_name": self.state.branch_name},
        )

        return "ready_for_review"

    # ── Approval finalization ─────────────────────────────────────────────

    @listen("review_approved")
    def finalize_approval(self):
        """Finalize an approved review."""
        logger.info("CodeReviewFlow: task %d approved", self.state.task_id)
        self.state.review_status = ReviewStatus.APPROVED
        update_task_status(self.state.task_id, "done")

        # Stop the reviewer's pod if running
        self._deactivate_reviewer()

        log_flow_event(
            self.state.project_id, "review_finalized", "code_review_flow",
            "task", self.state.task_id,
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: mark task as failed, notify team lead."""
        logger.error(
            "CodeReviewFlow: error state reached (task_id=%d, project_id=%d)",
            self.state.task_id, self.state.project_id,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "flow_error", "code_review_flow",
            "task", self.state.task_id,
        )
        # Stop the reviewer's pod if running
        self._deactivate_reviewer()

        notify_team_lead(
            self.state.project_id, "system",
            f"CodeReviewFlow error: task {self.state.task_id} review failed unexpectedly. "
            f"Please investigate.",
        )

    def _deactivate_reviewer(self) -> None:
        """Stop the reviewer's pod if pod mode is active."""
        try:
            reviewer = get_agent_by_role("code_reviewer", self.state.project_id)
            reviewer.deactivate()
        except Exception:
            logger.debug("Could not deactivate reviewer pod", exc_info=True)

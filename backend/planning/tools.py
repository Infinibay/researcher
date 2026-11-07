"""Host-only native planning tools: bounded original context and a typed proposal, with no task creation or execution permission."""

import asyncio
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.runtime.business_mediation import _failure, catalog_digest
from backend.runtime.contracts import DeliveryReady, RunConflict, RunNotFound


class Arguments(BaseModel):
    """Reject undeclared authority fields at the native tool boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ContextWindow(Arguments):
    """Read explicit windows rather than silently truncating original project material."""

    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=16000, ge=1, le=24000)


class PlanBasis(Arguments):
    """Attribute a literal quote to known original material; its origin is supplied by the host, not the planner."""

    source: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=4000)


class EpicProposal(Arguments):
    """A local graph label and proposed content, never a database ID or assignment."""

    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=8000)


class MilestoneProposal(EpicProposal):
    """An optional delivery grouping within an epic; a proposed calendar date is not scheduling authority."""

    epic_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
    due_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class TaskProposal(EpicProposal):
    """Propose a task, local prerequisites and optional milestone in its epic; the model cannot select actor, claim or permission."""

    epic_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
    milestone_key: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
    type: Literal["research", "investigation", "review", "code", "bug_fix", "test", "design", "integrate", "documentation", "experimentation", "optimization"]
    acceptance_criteria: str = Field(min_length=1, max_length=8000)
    priority: int = Field(ge=1, le=5)
    depends_on: list[str] = Field(max_length=32)


class PlanDraft(Arguments):
    """Complete append-only proposed graph, with separate evidence and unknown premises."""

    title: str = Field(min_length=1, max_length=256)
    rationale: str = Field(min_length=1, max_length=12000)
    assumptions: list[str] = Field(max_length=16)
    basis: list[PlanBasis] = Field(min_length=1, max_length=16)
    epics: list[EpicProposal] = Field(min_length=1, max_length=12)
    milestones: list[MilestoneProposal] = Field(default_factory=list, max_length=32)
    tasks: list[TaskProposal] = Field(min_length=1, max_length=32)


class PlanProposal(Arguments):
    """Stable original proposal identity; retry cannot replace its draft or introduce an execution command."""

    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    plan: PlanDraft


class PlanDelivery(PlanProposal):
    """Save the final explanation with its exact graph before the host ends generation."""

    explanation: str = Field(min_length=1, max_length=24000)


class PlanningTools:
    """Serialize and drain planning source/proposal operations within the original host-owned attempt."""

    def __init__(self, records, lease, *, active, settled):
        """Bind host-selected scope before constructing the native catalog; no authority is read from arguments."""
        self.records, self.lease = records, lease
        self.active, self.settled = active, settled
        self.closed = False
        self.lock = asyncio.Lock()
        self.models = {
            "researcher_plan_context": ContextWindow,
            "researcher_plan_propose": PlanProposal,
            "researcher_plan_deliver": PlanDelivery,
        }
        descriptions = {
            "researcher_plan_context": "Read original project and request material in complete explicit windows. Metadata attribution and host_default differ from a direct owner message. Unread material is unknown.",
            "researcher_plan_propose": "Save one justified bounded epic/task DAG with optional milestones, exact source quotes and separate assumptions. A task's milestone_key must name a milestone in its own epic. Optional due_date is a proposed calendar date, not an owner-agreed deadline or execution schedule. Does not create tasks, assign an agent, accept work or start execution. Retain operation_key after uncertain response.",
            "researcher_plan_deliver": "FINAL operation: atomically save the justified plan and its human-readable explanation, then end this turn without another generation. Use this instead of plan_propose for a complete delivery; an existing immutable draft cannot be replaced. Explain the result, useful example or dependencies, evidence versus assumptions and how the owner can correct it. Saving does not accept or execute the plan. The host confirms closure separately. Retain operation_key after uncertain response.",
        }
        self.catalog = [
            {
                "type": "function",
                "name": name,
                "description": descriptions[name],
                "inputSchema": model.model_json_schema(),
            }
            for name, model in self.models.items()
        ]

    @property
    def catalog_hash(self):
        """Fingerprint the exact admitted planning schema, independent of model output."""
        return catalog_digest(self.catalog)

    async def call(self, params):
        """Read original material or save a validated proposal under current authority; an interrupted tool may leave history but no new dispatch permission."""
        if self.closed or not self.active():
            return _failure(
                "Planning authority ended; inspect saved records without replay."
            )
        if (
            not isinstance(params, dict)
            or params.get("namespace") is not None
            or params.get("tool") not in self.models
            or not isinstance(params.get("arguments"), dict)
        ):
            return _failure("Unknown planning tool or invalid arguments")
        try:
            args = self.models[params["tool"]].model_validate(params["arguments"])
            async with self.lock:
                if self.closed or not self.active():
                    return _failure("Planning authority ended before dispatch")
                if isinstance(args, PlanDelivery):
                    await self.settled(
                        self.records.deliver, self.lease, args.operation_key,
                        args.plan.model_dump(exclude_unset=True), args.explanation,
                    )
                    self.closed = True
                    raise DeliveryReady(len(args.explanation.encode("utf-8")))
                elif isinstance(args, ContextWindow):
                    result = await self.settled(
                        self.records.material, self.lease, **args.model_dump()
                    )
                else:
                    result = await self.settled(
                        self.records.propose,
                        self.lease,
                        args.operation_key,
                        args.plan.model_dump(exclude_unset=True),
                    )
            if self.closed or not self.active():
                return _failure(
                    "Planning ended while the operation ran; its original proposal may be saved."
                )
            return {
                "success": True,
                "contentItems": [
                    {
                        "type": "inputText",
                        "text": json.dumps(result, ensure_ascii=False),
                    }
                ],
            }
        except (ValueError, RunConflict, RunNotFound) as error:
            return _failure(str(error))

    async def aclose(self):
        """Seal new calls first and drain the current owned worker operation before closing the native domain."""
        self.closed = True
        async with self.lock:
            pass

"""Exploratory scope, grouped observations and open questions reuse native evidence-backed reports without asserting scientific certainty."""

import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from backend.knowledge.reviews import canonical, digest
from backend.research.models import ReportDraft, ResearchForbidden, ResearchInputError

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
LongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)
]
FindingId = Annotated[int, Field(strict=True, gt=0)]


class InvestigationArea(BaseModel):
    """Group actual finding references by an explicit area; an empty reference list identifies an unresolved area rather than fabricated evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    title: ShortText
    observations: LongText
    finding_ids: list[FindingId] = Field(max_length=50)


class InvestigationSummary(BaseModel):
    """One bounded Scope/Gather/Organize/Summarize output; the author states limits and next steps without accepting work or grading scientific confidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)
    ]
    question: LongText
    scope_includes: list[ShortText] = Field(min_length=1, max_length=20)
    scope_excludes: list[ShortText] = Field(max_length=20)
    areas: list[InvestigationArea] = Field(min_length=1, max_length=20)
    conclusion: LongText
    limitations: list[ShortText] = Field(min_length=1, max_length=20)
    next_steps: list[ShortText] = Field(max_length=20)

    @model_validator(mode="after")
    def bounded_report(self):
        """Validate actual report constraints and full retained size before any write; never trim evidence silently."""
        self.report()
        if len(canonical(self.model_dump(mode="json")).encode()) > 180000:
            raise ResearchInputError(
                "Complete exploratory summary exceeds its retained size budget"
            )
        return self

    def report(self):
        """Produce canonical Markdown and exact linked findings from the same typed summary used for provenance; no secondary synthesis model runs."""
        lines = [
            "## Question and scope",
            self.question,
            "### Included",
            *["- " + item for item in self.scope_includes],
            "### Outside scope",
            *["- " + item for item in self.scope_excludes],
            "## Observations by area",
        ]
        for area in self.areas:
            lines.extend(
                [
                    "### " + area.title,
                    area.observations,
                    "Referenced findings: "
                    + (
                        ", ".join("#" + str(fid) for fid in area.finding_ids)
                        or "None recorded for this area."
                    ),
                ]
            )
        lines.extend(
            [
                "## Summary",
                self.conclusion,
                "## Limitations",
                *["- " + item for item in self.limitations],
                "## Proposed next steps",
                *["- " + item for item in self.next_steps],
            ]
        )
        return ReportDraft(
            self.title,
            "\n\n".join(lines),
            tuple(sorted({fid for area in self.areas for fid in area.finding_ids})),
            "summary",
        )


def write_summary(store, scope, key, draft):
    """Atomically write the scoped typed summary, canonical report and one original receipt under the live native investigation author's grant."""
    if not isinstance(draft, InvestigationSummary):
        raise ResearchInputError("A typed investigation summary is required")
    packet = draft.model_dump(mode="json")
    report = draft.report()

    def apply(conn):
        """Keep report/metadata/receipt in the same owner transaction; a missing artifact cannot become a delivered result."""
        from backend.knowledge.results import author_scope

        author_scope(conn, scope)
        task = conn.execute(
            "SELECT type FROM tasks WHERE project_id=? AND id=?",
            (scope.project_id, scope.task_id),
        ).fetchone()
        if task is None or task[0] != "investigation":
            raise ResearchForbidden(
                "Exploratory summaries require an admitted investigation task"
            )
        result = store._insert_report(conn, scope, report)
        conn.execute(
            "INSERT INTO research_investigation_summaries VALUES(?,?,?,?,?,?,?,?)",
            (
                result["artifact_id"],
                scope.project_id,
                scope.task_id,
                scope.context_version,
                scope.grant_id,
                key,
                canonical(packet),
                digest(packet),
            ),
        )
        return {**result, "summary_sha256": digest(packet)}

    return store._write(scope, key, "investigation.summary", packet, apply)


def verified_summary(conn, run, report_id, producer, markdown):
    """Bind typed scope and canonical report to the actual original author operation; metadata words alone cannot label an arbitrary draft as an investigation result."""
    row = conn.execute(
        "SELECT *FROM research_investigation_summaries WHERE artifact_id=? AND project_id=? AND task_id=?",
        (report_id, run["project_id"], run["task_id"]),
    ).fetchone()
    if row is None:
        raise ResearchInputError(
            "Select a typed investigation summary, not a generic report"
        )
    packet = json.loads(row["summary_json"])
    draft = InvestigationSummary.model_validate(packet)
    if (
        row["context_version"] != run["context_version"]
        or row["operation_key"] != producer["operation_key"]
        or row["producer_grant_id"] != producer["grant_id"]
        or row["summary_sha256"] != digest(packet)
        or draft.report().markdown != markdown
    ):
        raise ResearchInputError("Original investigation summary evidence changed")
    return packet

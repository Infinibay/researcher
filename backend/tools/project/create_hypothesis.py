"""Tool for creating research hypotheses (specialized finding type)."""

from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.knowledge.record_finding import RecordFindingTool


class CreateHypothesisInput(BaseModel):
    statement: str = Field(..., description="Hypothesis statement")
    rationale: str = Field(..., description="Rationale/justification for the hypothesis")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Initial confidence level (0.0 to 1.0)",
    )


class CreateHypothesisTool(InfinibayBaseTool):
    name: str = "create_hypothesis"
    description: str = (
        "Create a research hypothesis. This is a specialized finding "
        "with type 'hypothesis' that can be tested and validated."
    )
    args_schema: Type[BaseModel] = CreateHypothesisInput

    def _run(
        self, statement: str, rationale: str, confidence: float = 0.5
    ) -> str:
        # Delegate to RecordFindingTool with finding_type='hypothesis'
        finder = RecordFindingTool()
        self._bind_delegate(finder)
        return finder._run(
            title=statement,
            content=f"**Hypothesis:** {statement}\n\n**Rationale:** {rationale}",
            confidence=confidence,
            finding_type="hypothesis",
        )

"""Shared HTTP/MCP question shapes; authority stays outside these inputs."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.runtime.questions import QuestionSet, question_set


class HumanOption(BaseModel):
    """A stable machine value and a readable label for a suggested answer."""
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    label: str = Field(min_length=1, max_length=400)


class SelectedOption(BaseModel):
    """An explicit selection; free-text answers remain a separate wire type."""
    model_config = ConfigDict(extra="forbid", strict=True)
    option_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class HumanQuestion(BaseModel):
    """Validate native question inputs while accepting persisted text-only choices."""
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    question: str = Field(min_length=1, max_length=2000)
    why_needed: str = Field(default="", max_length=2000)
    options: list[str | HumanOption] = Field(default_factory=list, max_length=4)
    example: str = Field(default="", max_length=2000)

    def domain(self):
        """Reuse the same domain parser for HTTP, MCP and stored question payloads."""
        return question_set([self.model_dump()]).questions[0]


class AskUser(BaseModel):
    """Record a grouped information request without granting new runtime authority."""
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    questions: list[HumanQuestion] = Field(min_length=1, max_length=3)

    def domain(self):
        """Keep every question's original ID and readable content in one durable group."""
        return QuestionSet(tuple(q.domain() for q in self.questions))

    @model_validator(mode="after")
    def bounded_questions(self):
        """Apply byte bounds and identity checks after wire-shape validation."""
        self.domain()
        return self


class AnswerQuestions(BaseModel):
    """Bind free text or explicit option selections to an observed question context."""
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    expected_version: int = Field(ge=1)
    answers: dict[str, str | SelectedOption] = Field(min_length=1, max_length=3)

"""Shared HTTP/MCP question shapes; authority stays outside these inputs."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.runtime.questions import Question, QuestionSet


class HumanQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    question: str = Field(min_length=1, max_length=2000)
    why_needed: str = Field(default="", max_length=2000)
    options: list[str] = Field(default_factory=list, max_length=4)
    example: str = Field(default="", max_length=2000)

    def domain(self):
        return Question(**{**self.model_dump(), "options": tuple(self.options)})


class AskUser(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    questions: list[HumanQuestion] = Field(min_length=1, max_length=3)

    def domain(self):
        return QuestionSet(tuple(q.domain() for q in self.questions))

    @model_validator(mode="after")
    def bounded_questions(self):
        self.domain()
        return self


class AnswerQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    expected_version: int = Field(ge=1)
    answers: dict[str, str] = Field(min_length=1, max_length=3)

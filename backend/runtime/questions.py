"""Human information requests are context records, never effect permissions."""

import json
import re
from dataclasses import asdict, dataclass

from backend.runtime.contracts import text


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    why_needed: str = ""
    options: tuple[str, ...] = ()
    example: str = ""

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", self.id):
            raise ValueError("Question id must be a short ASCII identifier")
        text(self.question, "question", 2000)
        for name, value in (("why_needed", self.why_needed), ("example", self.example)):
            if value:
                text(value, name, 2000)
        if not isinstance(self.options, tuple) or len(self.options) not in (0, 2, 3, 4):
            raise ValueError(
                "Use no options or two to four choices; free text is always allowed"
            )
        for option in self.options:
            text(option, "choice", 400)
        if len(set(self.options)) != len(self.options):
            raise ValueError("Question choices must be distinct")


@dataclass(frozen=True)
class QuestionSet:
    questions: tuple[Question, ...]

    def __post_init__(self):
        if not isinstance(self.questions, tuple) or not 1 <= len(self.questions) <= 3:
            raise ValueError("Ask one to three questions together")
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Question ids must be distinct")
        text(json.dumps(self.payload(), ensure_ascii=False), "question set", 12000)

    def payload(self):
        return [{**asdict(q), "options": list(q.options)} for q in self.questions]

    def validate_answers(self, answers):
        if not isinstance(answers, dict) or set(answers) != {
            q.id for q in self.questions
        }:
            raise ValueError("Answer every question with its exact id")
        for value in answers.values():
            text(value, "answer", 12000)
        text(json.dumps(answers, ensure_ascii=False), "answers", 12000)

    def message(self):
        blocks = []
        for q in self.questions:
            parts = [q.question]
            if q.why_needed:
                parts.append(q.why_needed)
            if q.example:
                parts.append("Ejemplo: " + q.example)
            if q.options:
                parts.append("\n".join("- " + option for option in q.options))
            blocks.append("\n\n".join(parts))
        return "\n\n".join(blocks)

    def answered_statement(self, answers):
        self.validate_answers(answers)
        return "\n\n".join(
            q.question + "\nRespuesta del usuario: " + answers[q.id]
            for q in self.questions
        )


def question_set(payload):
    return QuestionSet(
        tuple(
            Question(**{**q, "options": tuple(q.get("options", ()))}) for q in payload
        )
    )

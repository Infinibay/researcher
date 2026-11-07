"""Human information requests are context records, never effect permissions."""

import json
import re
from dataclasses import asdict, dataclass

from backend.runtime.contracts import text


@dataclass(frozen=True)
class QuestionOption:
    """Keep a stable selection identity separate from its user-facing label."""

    id: str
    label: str

    def __post_init__(self):
        """Reject ambiguous or unbounded identities before they enter a durable question."""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", self.id):
            raise ValueError("Option id must be a short ASCII identifier")
        text(self.label, "choice label", 400)


@dataclass(frozen=True)
class Question:
    """One correctable information request, retaining historical text-only choices."""

    id: str
    question: str
    why_needed: str = ""
    options: tuple[str | QuestionOption, ...] = ()
    example: str = ""

    def __post_init__(self):
        """Validate bounded question content and distinct identities without rewriting old choices."""
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
            if not isinstance(option, QuestionOption):
                text(option, "choice", 400)
        identities = [option.id if isinstance(option, QuestionOption) else option for option in self.options]
        if len(set(identities)) != len(identities):
            raise ValueError("Question choices must be distinct")


@dataclass(frozen=True)
class QuestionSet:
    """A bounded group whose complete answers are correlated by exact question and option identities."""

    questions: tuple[Question, ...]

    def __post_init__(self):
        """Require a small complete question group before pausing work for human input."""
        if not isinstance(self.questions, tuple) or not 1 <= len(self.questions) <= 3:
            raise ValueError("Ask one to three questions together")
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Question ids must be distinct")
        text(json.dumps(self.payload(), ensure_ascii=False), "question set", 12000)

    def payload(self):
        """Preserve old string choices and encode new choices as explicit ID/label objects."""
        return [{**asdict(q), "options": [asdict(o) if isinstance(o, QuestionOption) else o for o in q.options]} for q in self.questions]

    def validate_answers(self, answers):
        """Treat free text literally and accept structured selections only from the original options."""
        if not isinstance(answers, dict) or set(answers) != {
            q.id for q in self.questions
        }:
            raise ValueError("Answer every question with its exact id")
        for q in self.questions:
            value = answers[q.id]
            if isinstance(value, dict):
                ids = {o.id for o in q.options if isinstance(o, QuestionOption)}
                if set(value) != {"option_id"} or not isinstance(value['option_id'], str) or value['option_id'] not in ids:
                    raise ValueError("Select an exact option id from this question")
            else:
                text(value, "answer", 12000)
        text(json.dumps(answers, ensure_ascii=False), "answers", 12000)

    def message(self):
        """Describe every question with readable labels while retaining IDs in the saved payload."""
        blocks = []
        for q in self.questions:
            parts = [q.question]
            if q.why_needed:
                parts.append(q.why_needed)
            if q.example:
                parts.append("Ejemplo: " + q.example)
            if q.options:
                parts.append("\n".join("- " + (option.label if isinstance(option, QuestionOption) else option) for option in q.options))
            blocks.append("\n\n".join(parts))
        return "\n\n".join(blocks)

    def answered_statement(self, answers):
        """Explain selected labels and original IDs without converting typed strings into inferred choices."""
        self.validate_answers(answers)
        statements = []
        for q in self.questions:
            value = answers[q.id]
            if isinstance(value, dict):
                option = next(o for o in q.options if isinstance(o, QuestionOption) and o.id == value['option_id'])
                value = f"{option.label} (opción {option.id})"
            statements.append(q.question + "\nRespuesta del usuario: " + value)
        return "\n\n".join(statements)


def question_set(payload):
    """Load current or historical question JSON without inventing identities for old text choices."""
    return QuestionSet(
        tuple(
            Question(**{**q, "options": tuple(QuestionOption(**o) if isinstance(o, dict) else o for o in q.get("options", ()))}) for q in payload
        )
    )

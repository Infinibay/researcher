"""Atomic question/pause and owner-answer/context transitions on the run journal."""

import json
from uuid import uuid4

from backend.research.models import ResearchForbidden
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    RunSpec,
    StaleAttempt,
    command_key,
    identity,
)
from backend.runtime.questions import question_set
from backend.runtime.sqlite_runs import _json


class SQLiteQuestionStore:
    def __init__(self, runs, research):
        self.runs = runs
        self.research = research

    def ask(self, scope, operation_key, questions):
        """A business-tool request, requiring a live, bound native attempt."""

        def apply(conn):
            grant = conn.execute(
                "SELECT runtime_bound,runtime_attempt_id FROM tool_grants WHERE id=?",
                (scope.grant_id,),
            ).fetchone()
            if not grant["runtime_bound"] or not grant["runtime_attempt_id"]:
                raise ResearchForbidden(
                    "Human questions require a runtime-bound attempt"
                )
            run_id = conn.execute(
                "SELECT run_id FROM runtime_attempts WHERE id=?",
                (grant["runtime_attempt_id"],),
            ).fetchone()[0]
            row = self.runs._row(conn, scope.project_id, run_id)
            if not row["thread_id"] or not row["turn_id"]:
                raise ResearchForbidden(
                    "Bind the actual native turn before asking the user"
                )
            if conn.execute(
                "SELECT 1 FROM runtime_question_links WHERE run_id=?", (run_id,)
            ).fetchone():
                raise RunConflict("This attempt already requested user input")
            link = conn.execute(
                "SELECT thread_id FROM runtime_chat_links WHERE run_id=?", (run_id,)
            ).fetchone()
            if link is None:
                thread_id = str(uuid4())
                spec = RunSpec(
                    row["project_id"],
                    row["task_id"],
                    row["actor_id"],
                    row["context_version"],
                    row["operation_key"],
                    row["prompt"],
                    row["runtime"],
                )
                self.runs._attach_conversation(conn, spec, run_id, thread_id)
            else:
                thread_id = link[0]
            body = questions.message()
            request_id = conn.execute(
                """INSERT INTO user_requests(project_id,agent_id,agent_run_id,request_type,title,body)
                VALUES(?,?,?,'question',?,?)""",
                (
                    scope.project_id,
                    scope.agent_id,
                    run_id,
                    questions.questions[0].question[:120],
                    body,
                ),
            ).lastrowid
            message_id = conn.execute(
                """INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,conversation_type,message,metadata_json)
                VALUES(?,?,?,'user','agent_to_user',?,?)""",
                (
                    scope.project_id,
                    thread_id,
                    scope.agent_id,
                    body,
                    _json(
                        {
                            "schema_version": 1,
                            "runtime_run_id": run_id,
                            "context_version": scope.context_version,
                            "kind": "question",
                        }
                    ),
                ),
            ).lastrowid
            conn.execute(
                """INSERT INTO runtime_question_links(request_id,project_id,run_id,attempt_id,context_version,
                operation_key,question_set_json,thread_id,question_message_id) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    request_id,
                    scope.project_id,
                    run_id,
                    grant["runtime_attempt_id"],
                    scope.context_version,
                    operation_key,
                    _json(questions.payload()),
                    thread_id,
                    message_id,
                ),
            )
            self.runs._withdraw(conn, row, "cancelling")
            self.runs._event(
                conn,
                scope.project_id,
                scope.task_id,
                "question.requested",
                {
                    "request_id": request_id,
                    "run_id": run_id,
                    "attempt_id": grant["runtime_attempt_id"],
                    "context_version": scope.context_version,
                },
            )
            return {
                "request_id": request_id,
                "run_id": run_id,
                "attempt_id": grant["runtime_attempt_id"],
                "context_version": scope.context_version,
                "state": "confirming_pause",
            }

        return self.research._write(
            scope,
            operation_key,
            "question.ask",
            {"questions": questions.payload()},
            apply,
        )

    def park(self, lease):
        """Host-only: both native AND business peers have confirmed closure.

        Derive precedence from durable controls, not callback delivery order.
        """
        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            row = self.runs._row(conn, lease.project_id, lease.run_id)
            linked = conn.execute(
                "SELECT q.*,u.status FROM runtime_question_links q JOIN user_requests u ON u.id=q.request_id WHERE q.run_id=? AND q.attempt_id=?",
                (lease.run_id, lease.attempt_id),
            ).fetchone()
            if linked is None:
                return None
            if row["current_attempt_id"] != lease.attempt_id:
                raise StaleAttempt("Another attempt owns this question")
            if row["status"] in (
                "waiting_input",
                "cancelled",
                "superseded",
                "failed",
                "accepted",
            ):
                return self.runs._view(row)
            if conn.execute(
                "SELECT 1 FROM runtime_jobs WHERE attempt_id=? AND status<>'exited'",
                (lease.attempt_id,),
            ).fetchone():
                raise RunConflict(
                    "Owned jobs require terminal reconciliation before waiting"
                )
            if row["cancel_requested"]:
                status = "cancelled"
            elif self.runs._context(conn, lease.task_id) != lease.context_version:
                status = "superseded"
            elif linked["status"] == "pending":
                status = "waiting_input"
            else:
                raise RunConflict("Question is no longer pending under this context")
            return self.runs._retire_closed(conn, row, status)

    @staticmethod
    def _question(conn, project_id, task_id, request_id):
        row = conn.execute(
            """SELECT q.*,u.status,u.response,r.status AS run_status FROM runtime_question_links q
            JOIN user_requests u ON u.id=q.request_id AND u.project_id=q.project_id
            JOIN runtime_runs r ON r.id=q.run_id WHERE q.project_id=? AND r.task_id=? AND q.request_id=?""",
            (project_id, task_id, request_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Question not found in this project and task")
        return row

    def answer(
        self,
        *,
        project_id,
        task_id,
        request_id,
        expected_version,
        operation_key,
        answers,
    ):
        for value in (project_id, task_id, request_id, expected_version):
            identity(value)
        command_key(operation_key)
        intent = {
            "kind": "answer_question",
            "request_id": request_id,
            "expected_version": expected_version,
            "answers": answers,
        }
        with self.runs._transaction(write=True) as conn:
            receipt = self.runs._receipt(
                conn, project_id, task_id, operation_key, intent
            )
            if receipt is not None:
                return receipt["version"]
            row = self._question(conn, project_id, task_id, request_id)
            draft = question_set(json.loads(row["question_set_json"]))
            draft.validate_answers(answers)
            if (
                row["status"] != "pending"
                or row["run_status"] != "waiting_input"
                or row["context_version"] != expected_version
            ):
                raise RunConflict(
                    "Question is stale or its pause has not been confirmed"
                )
            conn.execute(
                "UPDATE user_requests SET status='responded',response=?,responded_at=CURRENT_TIMESTAMP WHERE id=?",
                (_json(answers), request_id),
            )
            version = self.runs._advance_context(
                conn,
                project_id=project_id,
                task_id=task_id,
                expected_version=expected_version,
                statement=draft.answered_statement(answers),
                source_kind="user_message",
                source_reference="question:" + str(request_id),
            )
            message_id = conn.execute(
                """INSERT INTO chat_messages(project_id,thread_id,parent_message_id,from_agent,to_agent,
                conversation_type,message,metadata_json) VALUES(?,?,?,'user','researcher','user_to_agent',?,?)""",
                (
                    project_id,
                    row["thread_id"],
                    row["question_message_id"],
                    draft.answered_statement(answers),
                    _json(
                        {
                            "schema_version": 1,
                            "runtime_run_id": row["run_id"],
                            "context_version": version,
                            "kind": "answer",
                        }
                    ),
                ),
            ).lastrowid
            conn.execute(
                "UPDATE runtime_question_links SET answer_message_id=?,answer_context_version=? WHERE request_id=?",
                (message_id, version, request_id),
            )
            self.runs._save_receipt(
                conn, project_id, task_id, operation_key, intent, {"version": version}
            )
            self.runs._event(
                conn,
                project_id,
                task_id,
                "question.answered",
                {
                    "request_id": request_id,
                    "run_id": row["run_id"],
                    "context_version": version,
                    "application": "recorded_for_next_run",
                },
            )
            return version

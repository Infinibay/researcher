"""The owner sees every pending question, with its actual task and context."""

from dataclasses import replace

import httpx


def pending_question(c, *, project=101, task=1001, park=True):
    from backend.runtime.questions import Question, QuestionSet
    from backend.runtime.sqlite_questions import SQLiteQuestionStore

    spec = replace(
        c.spec, project_id=project, task_id=task, operation_key="inbox-" + str(task)
    )
    run = c.store.admit(spec, conversation_thread="inbox-thread-" + str(task))
    lease = c.store.claim(project, run.run_id, "owner")
    c.store.bind_thread(lease, thread_id="native-" + str(task))
    c.store.bind_native(
        lease, thread_id="native-" + str(task), turn_id="turn-" + str(task)
    )
    token = c.research.issue_grant(
        project_id=project,
        task_id=task,
        agent_id=spec.actor_id,
        permissions={"questions.ask"},
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    questions = SQLiteQuestionStore(c.store, c.research)
    receipt = questions.ask(
        scope,
        "question",
        QuestionSet(
            (
                Question(
                    "folder",
                    "Which folder?",
                    "To scope the inspection",
                    ("client", "server"),
                    "Inspect only the selected folder.",
                ),
            )
        ),
    )
    if park:
        questions.park(lease)
    return questions, run, receipt


def test_inbox_contains_all_native_questions_with_scope_and_readiness(coordination):
    from backend.runtime.views import OwnerRuntimeView

    c = coordination
    _, first, q1 = pending_question(c)
    _, second, q2 = pending_question(c, task=1002, park=False)
    pending_question(c, project=202, task=2002)
    page = OwnerRuntimeView(c.database).question_inbox(101)
    assert page["total_pending"] == 2 and page["next_after_id"] is None
    assert [x["request_id"] for x in page["items"]] == [
        q1["request_id"],
        q2["request_id"],
    ]
    one, two = page["items"]
    assert (
        one["task_id"],
        one["run_id"],
        one["context_version"],
        one["current_context_version"],
    ) == (1001, first.run_id, 1, 1)
    assert one["ready_for_answer"] is True and two["ready_for_answer"] is False
    assert two["run_id"] == second.run_id and two["task_title"] == "Second"
    assert one["questions"][0]["id"] == "folder"
    assert one["questions"][0]["options"] == ["client", "server"]
    assert one["kind"] == "native" and one["thread_id"] == "inbox-thread-1001"


def test_inbox_pagination_keeps_legacy_questions_visible_without_invented_task_authority(
    coordination,
):
    from backend.runtime.views import OwnerRuntimeView

    c = coordination
    _, _, q1 = pending_question(c)
    _, _, q2 = pending_question(c, task=1002)
    legacy = c.conn.execute(
        "INSERT INTO user_requests(project_id,agent_id,request_type,title,body,options_json) VALUES(101,'legacy-agent','question','Earlier question','Original premise','[{\"text\":\"Inspect\",\"value\":\"read-only\"}]')"
    ).lastrowid
    c.conn.commit()
    view = OwnerRuntimeView(c.database)
    first = view.question_inbox(101, limit=2)
    assert first["total_pending"] == 3 and first["next_after_id"] == q2["request_id"]
    assert [x["request_id"] for x in first["items"]] == [
        q1["request_id"],
        q2["request_id"],
    ]
    last = view.question_inbox(101, after_id=first["next_after_id"], limit=2)
    assert len(last["items"]) == 1 and last["next_after_id"] is None
    item = last["items"][0]
    assert item["request_id"] == legacy and item["kind"] == "legacy"
    assert item["task_id"] is None and item["context_version"] is None
    assert item["questions"] is None and item["ready_for_answer"] is False
    assert item["body"] == "Original premise"
    assert (
        c.conn.execute(
            "SELECT options_json FROM user_requests WHERE id=?", (legacy,)
        ).fetchone()[0]
        == '[{"text":"Inspect","value":"read-only"}]'
    )


def test_answered_or_invalidated_questions_leave_the_inbox(coordination):
    from backend.runtime.views import OwnerRuntimeView

    c = coordination
    questions, _, q1 = pending_question(c)
    _, _, q2 = pending_question(c, task=1002)
    questions.answer(
        project_id=101,
        task_id=1001,
        request_id=q1["request_id"],
        expected_version=1,
        operation_key="answer",
        answers={"folder": "server"},
    )
    c.conn.execute("UPDATE tasks SET description='Changed premise' WHERE id=1002")
    c.conn.commit()
    page = OwnerRuntimeView(c.database).question_inbox(101)
    assert page["items"] == [] and page["total_pending"] == 0
    assert (
        c.conn.execute(
            "SELECT status FROM user_requests WHERE id=?", (q2["request_id"],)
        ).fetchone()[0]
        == "expired"
    )


async def test_owner_question_inbox_is_read_only_authenticated_and_available_without_runtime(
    coordination,
):
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = coordination
    _, _, q = pending_question(c)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )
    before = c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0]
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as anonymous:
            assert (
                await anonymous.get("/api/projects/101/questions")
            ).status_code == 401
            token = c.research.issue_grant(
                project_id=101,
                task_id=1002,
                agent_id="agent",
                permissions={"sources.read"},
            )
            assert (
                await anonymous.get(
                    "/api/projects/101/questions",
                    headers={"Authorization": "Bearer " + token},
                )
            ).status_code == 401
        async with owner_client(app) as owner:
            response = await owner.get("/api/projects/101/questions?limit=1")
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["items"][0]["request_id"] == q["request_id"]
            assert (await owner.get("/api/projects/202/questions")).json()[
                "items"
            ] == []
            assert (await owner.get("/api/projects/999/questions")).status_code == 404
            assert (
                await owner.get("/api/projects/101/questions?limit=101")
            ).status_code == 422
            assert (
                await owner.get("/api/projects/101/questions?after_id=-1")
            ).status_code == 422
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == before
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )

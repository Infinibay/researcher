"""Seed historical SQL records without requiring a future runtime API or claiming actor execution."""

import json


def historical_run(conn, run_id, *, kind="research", status="failed", task_id=1001):
    """Retain a schema-only run and original attempt using columns present since version34."""
    attempt_id = run_id + "-attempt"
    conn.execute(
        """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,
        operation_key,prompt,runtime,status,fence,current_attempt_id,created_at,updated_at,execution_kind)
        VALUES(?,101,?,'historical-fixture',1,?,'Historical schema fixture','codex',?,1,?,1000,1000,?)""",
        (run_id, task_id, run_id, status, attempt_id, kind),
    )
    conn.execute(
        """INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at)
        VALUES(?,?,'historical-owner',1,'finished',1000,1000)""",
        (attempt_id, run_id),
    )
    return attempt_id


def historical_plan_execution(conn):
    """Seed a version49 execution with two task references and retained original JSON bytes."""
    attempt = historical_run(conn, "historical-plan")
    conn.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1003,101,'research','Historical child')")
    conn.execute(
        """INSERT INTO runtime_project_plan_requests VALUES
        ('historical-plan',101,1001,1,'{}',?,1000)""", ("a" * 64,),
    )
    conn.execute(
        """INSERT INTO runtime_project_plan_proposals VALUES
        ('historical-proposal','historical-plan',?,'proposal',?,'{}',1000)""", (attempt, "b" * 64),
    )
    conn.execute(
        """INSERT INTO runtime_project_plan_acceptances VALUES
        ('historical-acceptance',101,1001,'historical-plan','historical-proposal',1,'accept','{}',1000)""",
    )
    manifest = json.dumps({"tasks": [{"task_id": task, "context_version": 1} for task in (1002, 1003)]})
    conn.execute(
        """INSERT INTO runtime_plan_executions VALUES
        ('historical-execution',101,'historical-plan','historical-acceptance','authorize',?,?,'paused',1000,1000)""",
        ("c" * 64, manifest),
    )
    for task in (1002, 1003):
        conn.execute("INSERT INTO runtime_project_plan_tasks VALUES(?,'historical-acceptance',?)", (task, str(task)))
        conn.execute(
            """INSERT INTO runtime_plan_deliveries(id,execution_id,task_id,operation_key)
            VALUES(?,'historical-execution',?,?)""", (f"delivery-{task}", task, f"deliver-{task}"),
        )
    conn.commit()
    return "historical-execution", "delivery-1002"


def historical_code_review(conn):
    """Seed closed version41 author/reviewer references for inverse preservation tests only."""
    author = historical_run(conn, "historical-author", kind="development")
    reviewer = historical_run(conn, "historical-review", kind="code_review")
    conn.execute(
        """INSERT INTO runtime_development_workspaces(attempt_id,run_id,project_id,task_id,
        context_version,fence,owner_id,source_json,allocation,state,created_at,updated_at)
        VALUES(?,'historical-author',101,1001,1,1,'historical-owner','{}','old-workspace','reconciling',1000,1000)""",
        (author,),
    )
    conn.execute(
        """INSERT INTO runtime_code_candidates(attempt_id,run_id,project_id,task_id,repository_id,
        context_version,fence,owner_id,source_json,prepared_json,base_sha,base_tree_sha,allocation,state,created_at,updated_at)
        VALUES(?,'historical-author',101,1001,11,1,1,'historical-owner','{}','{}',?,?,'old-candidate','reconciling',1000,1000)""",
        (author, "a" * 40, "b" * 40),
    )
    conn.execute(
        """INSERT INTO runtime_code_review_requests VALUES
        ('historical-review',101,1001,1,?,'{}','historical-author',?,'historical-fixture',
         'historical-thread','/historical/fixture',1,1,1000)""", ("c" * 64, author),
    )
    conn.execute(
        """INSERT INTO runtime_code_review_records(attempt_id,run_id,project_id,task_id,
        context_version,fence,owner_id,subject_sha256,state,proposal_key,proposal_json,
        reference_proof_json,created_at,updated_at)
        VALUES(?,'historical-review',101,1001,1,1,'historical-owner',?,'reconciling',
        'historical-proposal','{"verdict":"unsupported"}','{}',1000,1000)""", (reviewer, "c" * 64),
    )
    conn.commit()
    return author

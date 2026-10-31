"""Compatibility guard: native-marked conversations have one delivery owner.

The marker prevents legacy dispatch, never grants authority. Human projections
still verify their canonical runtime_chat_links rather than trusting metadata.
This uses existing chat columns so legacy readers do not require a new table.
"""

NATIVE_MARKER = "CASE WHEN json_valid(ownership.metadata_json) THEN json_extract(ownership.metadata_json,'$.runtime_run_id') END IS NOT NULL"
LEGACY_THREAD_CLAUSE = f"""NOT EXISTS(SELECT 1 FROM chat_messages ownership
    WHERE ownership.project_id=cm.project_id AND ownership.thread_id=cm.thread_id AND {NATIVE_MARKER})"""


def native_thread(conn, project_id, thread_id):
    return bool(
        conn.execute(
            f"SELECT EXISTS(SELECT 1 FROM chat_messages ownership WHERE project_id=? AND thread_id=? AND {NATIVE_MARKER})",
            (project_id, thread_id),
        ).fetchone()[0]
    )

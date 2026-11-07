"""Shared admission accounting for durable project work, distinct from provider billing."""


def project_work_usage(conn, project_id):
    """Aggregate recorded high waters and conservative holds in the caller's transaction.

    A settled measured dispatch counts its retained observation. Other dispatches
    hold at least their ceiling, including observed overruns. An absent measurement
    remains None; counted capacity is not a claim about actual tokens or quota.
    Preparations without a dispatch retain their ceiling; a matching dispatch
    replaces that hold rather than counting a second request.
    """
    row = conn.execute(
        """SELECT COUNT(*) AS used_turns, SUM(observed_tokens) AS observed_tokens,
        COALESCE(SUM(kind='dispatch' AND observed_tokens IS NULL),0) AS unmeasured_dispatches,
        COALESCE(SUM(kind='preparation'),0) AS preparation_only,
        COALESCE(SUM(kind='dispatch' AND status<>'settled'),0) AS unsettled_dispatches,
        COALESCE(SUM(CASE WHEN status='settled' AND observed_tokens IS NOT NULL
            THEN observed_tokens ELSE MAX(token_ceiling,COALESCE(observed_tokens,0)) END),0) AS accounted_tokens,
        COALESCE(SUM(CASE WHEN status='settled' AND observed_tokens IS NOT NULL
            THEN 0 ELSE MAX(token_ceiling,COALESCE(observed_tokens,0)) END),0) AS held_tokens
        FROM (
            SELECT 'dispatch' AS kind,status,observed_tokens,token_ceiling
            FROM runtime_inference_dispatches WHERE project_id=?
            UNION ALL
            SELECT 'preparation','reserved',NULL,p.token_ceiling
            FROM runtime_preparation_reservations p WHERE p.project_id=?
            AND NOT EXISTS (SELECT 1 FROM runtime_inference_dispatches d WHERE d.attempt_id=p.attempt_id)
        )""",
        (project_id, project_id),
    ).fetchone()
    return dict(row)

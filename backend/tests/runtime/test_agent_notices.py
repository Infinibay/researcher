"""Scoped native notice reads preserve global provenance, expiry and unread text without granting work authority."""

import pytest

from backend.tests.runtime.test_agent_messages import peers


def seed_notices(c):
    """Seed project, global, foreign, disabled and expired historical notices without an old tool."""
    records = (
        (91,101,"Project scope","á" * 1800 + ". Do not infer permission to publish.",1,None),
        (92,None,"Shared context","This is a global historical statement.",1,None),
        (93,202,"Foreign","Other project context.",1,None),
        (94,101,"Withdrawn","Do not rely on this old statement.",0,None),
        (95,101,"Expired","Earlier constraint.",1,"1970-01-01 00:10:00"),
        (96,101,"Current deadline","Check the exact scope.",1,"9999-01-01 00:00:00"),
    )
    c.conn.executemany("INSERT INTO notices(id,project_id,title,content,active,expires_at,created_by) VALUES(?,?,?,?,?,?,'historical-author-label')", records)
    c.conn.commit()


def test_notices_keep_project_global_and_expiry_boundaries_without_authority(coordination):
    """Recover complete text, distinguish old labels from verified authorship, and reject cross-project reads."""
    from backend.research.models import ResearchForbidden, ResearchNotFound

    c = coordination
    messages, sender, _recipient = peers(c)
    seed_notices(c)
    first = messages.notices(sender[2], limit=1)
    assert first["items"][0]["id"] == 91 and first["next_after_id"] == 91
    assert first["items"][0]["scope"] == "project"
    assert first["items"][0]["content_chars"] > len(first["items"][0]["preview"])
    rest = messages.notices(sender[2], after_id=first["next_after_id"])
    assert [r["id"] for r in rest["items"]] == [92,96]
    assert rest["items"][0]["scope"] == "global"
    one = messages.notice(sender[2], 91, max_chars=1000)
    two = messages.notice(sender[2], 91, offset=one["next_offset"])
    assert one["content"] + two["content"] == "á" * 1800 + ". Do not infer permission to publish."
    assert one["notice"]["recorded_creator"] == "historical-author-label"
    assert one["authorizes_work"] is False and one["authorship_verified"] is False
    assert one["immutable"] is False
    assert [r["id"] for r in messages.notices(sender[2], active_only=False)["items"]] == [91,92,94,95,96]
    assert messages.notice(sender[2], 95)["notice"]["active_at_observation"] is False
    with pytest.raises(ResearchNotFound):
        messages.notice(sender[2], 93)
    assert c.conn.execute("SELECT count(*) FROM message_reads").fetchone()[0] == 0
    c.research.revoke_grant(sender[2].grant_id)
    with pytest.raises(ResearchForbidden):
        messages.notices(sender[2])

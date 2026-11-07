-- Migration59: preserve a project deletion watermark atomically with event removal.
CREATE TABLE event_retention (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    pruned_through INTEGER NOT NULL CHECK(pruned_through>=0)
);
CREATE TRIGGER track_event_retention AFTER DELETE ON events_log
WHEN OLD.project_id IS NOT NULL AND EXISTS(SELECT 1 FROM projects WHERE id=OLD.project_id)
BEGIN
    INSERT INTO event_retention(project_id,pruned_through) VALUES(OLD.project_id,OLD.id)
    ON CONFLICT(project_id) DO UPDATE SET pruned_through=MAX(pruned_through,excluded.pruned_through);
END;
INSERT INTO schema_migrations(version,name) VALUES(59,'durable_event_retention');

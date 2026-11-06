-- Migration 55: owner model policy and immutable attempt selection.
CREATE TABLE runtime_model_settings(
    scope_key TEXT PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    actor_id TEXT,
    revision INTEGER NOT NULL CHECK(revision>0),
    profile_json TEXT CHECK(profile_json IS NULL OR json_valid(profile_json)),
    updated_at REAL NOT NULL,
    CHECK((project_id IS NULL AND actor_id IS NULL AND scope_key='global')
       OR (project_id IS NOT NULL AND actor_id IS NULL AND scope_key='project:'||project_id)
       OR (project_id IS NOT NULL AND actor_id IS NOT NULL AND scope_key='actor:'||project_id||':'||actor_id))
);
CREATE TABLE runtime_attempt_models(
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id),
    selection_json TEXT NOT NULL CHECK(json_valid(selection_json))
);
INSERT INTO schema_migrations(version,name) VALUES(55,'owner_model_settings_and_attempt_selection');

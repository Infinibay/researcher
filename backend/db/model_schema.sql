-- Migration 23: model provenance. Historical dispatches stay unknown.
ALTER TABLE runtime_inference_dispatches ADD COLUMN model TEXT
    CHECK(model IS NULL OR length(model) BETWEEN 1 AND 256);
INSERT INTO schema_migrations(version,name) VALUES(23,'runtime_model_provenance');

-- Migration58: preserve imported fragment identity through subsequent source capture.
CREATE TABLE reference_import_provenance (
    reference_file_id INTEGER PRIMARY KEY REFERENCES reference_files(id) ON DELETE CASCADE,
    content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
    provenance_json TEXT NOT NULL CHECK(json_valid(provenance_json))
);
CREATE TRIGGER reference_import_provenance_immutable BEFORE UPDATE ON reference_import_provenance
BEGIN SELECT RAISE(ABORT,'Imported reference provenance is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(58,'imported_reference_provenance');

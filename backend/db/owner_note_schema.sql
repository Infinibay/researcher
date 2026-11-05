-- Migration49: explanatory owner messages with original durable receipts, never implicit agent activation.
CREATE TABLE runtime_owner_endpoint(singleton INTEGER PRIMARY KEY CHECK(singleton=1),installation_id TEXT NOT NULL CHECK(length(installation_id)=64));
INSERT INTO runtime_owner_endpoint VALUES(1,lower(hex(randomblob(32))));
CREATE TRIGGER owner_endpoint_immutable BEFORE UPDATE ON runtime_owner_endpoint
BEGIN SELECT RAISE(ABORT,'Owner endpoint installation identity is immutable'); END;
CREATE TABLE runtime_owner_notes (
 project_id INTEGER NOT NULL REFERENCES projects(id), operation_key TEXT NOT NULL,
 request_sha256 TEXT NOT NULL CHECK(length(request_sha256)=64),
 message_id INTEGER NOT NULL UNIQUE REFERENCES chat_messages(id),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)), created_at REAL NOT NULL,
 PRIMARY KEY(project_id,operation_key)
);
CREATE TRIGGER owner_note_receipt_immutable BEFORE UPDATE ON runtime_owner_notes
BEGIN SELECT RAISE(ABORT,'Original explanatory note receipts are immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(49,'explanatory_owner_note_receipts');

-- Migration46: original host HTTP lifetimes and separate fresh readonly remote observers.
CREATE TABLE runtime_remote_clients (
 attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
 run_id TEXT NOT NULL REFERENCES runtime_remote_publications(run_id) ON DELETE CASCADE,
 database_identity TEXT NOT NULL, fence INTEGER NOT NULL,
 owner_pid INTEGER NOT NULL,owner_start_ticks INTEGER NOT NULL,
 boot_id TEXT NOT NULL,observer_namespace INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('open','closed')),
 created_at REAL NOT NULL,closed_at REAL
);
CREATE TRIGGER remote_client_identity_immutable BEFORE UPDATE OF attempt_id,run_id,database_identity,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at
 ON runtime_remote_clients BEGIN SELECT RAISE(ABORT,'Original remote HTTP identity is immutable');END;
CREATE TRIGGER remote_client_closed_immutable BEFORE UPDATE ON runtime_remote_clients
 WHEN old.state='closed' BEGIN SELECT RAISE(ABORT,'Original HTTP closure is immutable');END;
CREATE TABLE runtime_remote_recoveries (
 attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
 run_id TEXT NOT NULL REFERENCES runtime_remote_publications(run_id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL,task_id INTEGER NOT NULL,operation_key TEXT NOT NULL,
 source_attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id),expected_fence INTEGER NOT NULL,
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 closure_json TEXT NOT NULL CHECK(json_valid(closure_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),created_at REAL NOT NULL,
 UNIQUE(project_id,task_id,operation_key)
);
CREATE TRIGGER remote_recovery_intent_immutable BEFORE UPDATE OF attempt_id,run_id,project_id,task_id,operation_key,source_attempt_id,expected_fence,request_json,closure_json,created_at
 ON runtime_remote_recoveries BEGIN SELECT RAISE(ABORT,'Remote readonly authority is immutable');END;
CREATE TRIGGER remote_recovery_result_immutable BEFORE UPDATE OF result_json ON runtime_remote_recoveries
 WHEN old.result_json IS NOT NULL AND old.result_json IS NOT new.result_json
 BEGIN SELECT RAISE(ABORT,'Remote recovery receipts are immutable');END;
INSERT INTO schema_migrations(version,name)VALUES(46,'readonly_remote_recovery');

"""One ordered forward schema chain after the retained legacy version17 baseline.

Explicit targets support staged upgrades and historical recovery rehearsals.
They never authorize downgrades or repair fabricated/incomplete history.
"""

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

BASE_VERSION = 17


@dataclass(frozen=True)
class Migration:
    """Identify one packaged SQL step or the specialized atomic rebuild it requires."""

    version: int
    resource: str | None = None
    handler: str | None = None

    def apply(self, connection):
        """Apply this trusted catalog step through its original transactional implementation."""
        if self.handler:
            module, name = self.handler.split(':')
            getattr(import_module(module), name)(connection)
        else:
            from backend.db.migrations import apply_sql_resource

            apply_sql_resource(connection, Path(__file__).with_name(self.resource))
        if connection.execute('SELECT 1 FROM schema_migrations WHERE version=?', (self.version,)).fetchone() is None:
            raise RuntimeError(f'Migration {self.version} returned without its committed version record')


MIGRATIONS = (
    Migration(18, handler='backend.db.research_migration:apply_research_schema'),
    Migration(19, resource='runtime_schema.sql'),
    Migration(20, resource='job_schema.sql'),
    Migration(21, resource='inference_schema.sql'),
    Migration(22, resource='conversation_schema.sql'),
    Migration(23, resource='model_schema.sql'),
    Migration(24, handler='backend.db.question_migration:apply_question_schema'),
    Migration(25, resource='peer_schema.sql'),
    Migration(26, resource='peer_origin_schema.sql'),
    Migration(27, resource='command_peer_schema.sql'),
    Migration(28, resource='admission_schema.sql'),
    Migration(29, resource='task_inputs_schema.sql'),
    Migration(30, resource='run_input_schema.sql'),
    Migration(31, handler='backend.db.peer_kind_migration:migrate_ken_peers'),
    Migration(32, resource='native_state_schema.sql'),
    Migration(33, handler='backend.db.wiki_migration:apply_wiki_schema'),
    Migration(34, resource='review_schema.sql'),
    Migration(35, resource='result_schema.sql'),
    Migration(36, resource='development_schema.sql'),
    Migration(37, resource='development_workspace_schema.sql'),
    Migration(38, resource='code_candidate_schema.sql'),
    Migration(39, resource='code_check_schema.sql'),
    Migration(40, resource='code_review_schema.sql'),
    Migration(41, resource='code_review_record_schema.sql'),
    Migration(42, resource='code_acceptance_schema.sql'),
    Migration(43, resource='code_publication_schema.sql'),
    Migration(44, resource='publication_recovery_schema.sql'),
    Migration(45, resource='remote_publication_schema.sql'),
    Migration(46, resource='remote_recovery_schema.sql'),
    Migration(47, resource='project_planning_schema.sql'),
    Migration(48, resource='plan_execution_schema.sql'),
    Migration(49, resource='owner_note_schema.sql'),
    Migration(50, resource='plan_continuation_schema.sql'),
    Migration(51, resource='plan_reauthorization_schema.sql'),
    Migration(52, resource='investigation_schema.sql'),
    Migration(53, resource='scientific_schema.sql'),
    Migration(54, resource='native_task_cutover_schema.sql'),
    Migration(55, resource='model_settings_schema.sql'),
    Migration(56, resource='agent_messages_schema.sql'),
    Migration(57, resource='peer_archive_schema.sql'),
    Migration(58, resource='reference_provenance_schema.sql'),
    Migration(59, resource='event_retention_schema.sql'),
)
LATEST_VERSION = MIGRATIONS[-1].version


def forward_target(target):
    """Validate the requested supported forward boundary before opening or creating storage."""
    if target is None:
        return LATEST_VERSION
    if type(target) is not int or not BASE_VERSION <= target <= LATEST_VERSION:
        raise ValueError(f'Expected an integer schema target from {BASE_VERSION} through {LATEST_VERSION}')
    return target


def validate_history(applied, target):
    """Refuse future schemas, incomplete modern prefixes and implicit reversal without changing data."""
    current = max(applied, default=0)
    if current > LATEST_VERSION:
        raise RuntimeError('Database schema is newer than this installation; use a compatible application')
    modern = {version for version in applied if version > BASE_VERSION}
    if modern != set(range(BASE_VERSION + 1, current + 1)):
        raise RuntimeError('Modern migration history is incomplete; inspect or restore the original database')
    if current > target:
        raise RuntimeError('Forward migration cannot downgrade existing data; use an explicit validated inverse or restore')

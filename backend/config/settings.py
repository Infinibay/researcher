"""Load process-level settings still consumed by storage, source retrieval and owner Git views.

Native execution has its own explicit owned-runtime configuration and versioned
model settings. Historical provider/loop options and .researcher/settings.json
are neither loaded nor migrated here; reading settings never creates storage.
"""

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings

from backend.config.paths import resolve_database_path


class Settings(BaseSettings):
    """Resolve retained host defaults from INFINIBAY_ environment variables at startup."""

    DB_PATH: str = Field(
        default_factory=resolve_database_path,
        validation_alias=AliasChoices("INFINIBAY_DB", "INFINIBAY_DB_PATH", "DB_PATH"),
    )
    MAX_RETRIES: int = 5
    RETRY_BASE_DELAY: float = 0.1

    # Owner-facing Forgejo views still use these explicit host defaults.
    # They do not grant native publication authority or select model credentials.
    FORGEJO_API_URL: str = ""
    FORGEJO_TOKEN: str = ""
    FORGEJO_OWNER: str = ""
    WEB_TIMEOUT: int = 30

    # Source retrieval uses pinned local assets and its existing rate/robots policy.
    RETRIEVAL_ASSET_DIR: str | None = None
    WEB_RPM_LIMIT: int = 20
    WEB_ROBOTS_CACHE_TTL: int = 3600

    model_config = {"env_prefix": "INFINIBAY_"}

    @field_validator("DB_PATH", mode="before")
    @classmethod
    def normalize_database_path(cls, value: str) -> str:
        """Resolve the configured database without initializing, moving or migrating it."""
        return resolve_database_path(explicit_path=value)


settings = Settings()

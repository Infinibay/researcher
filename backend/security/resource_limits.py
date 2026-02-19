"""Per-role resource limits for sandbox containers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    memory: str
    cpus: float
    pids_limit: int
    timeout: int  # seconds


ROLE_LIMITS: dict[str, ResourceLimits] = {
    "developer": ResourceLimits(memory="2g", cpus=2.0, pids_limit=256, timeout=300),
    "researcher": ResourceLimits(memory="4g", cpus=4.0, pids_limit=512, timeout=600),
    "code_reviewer": ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=120),
    "research_reviewer": ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=120),
    "team_lead": ResourceLimits(memory="512m", cpus=0.5, pids_limit=64, timeout=60),
    "project_lead": ResourceLimits(memory="512m", cpus=0.5, pids_limit=64, timeout=60),
    "default": ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=120),
}


def get_limits_for_role(role: str) -> ResourceLimits:
    """Return resource limits for the given role, falling back to 'default'."""
    return ROLE_LIMITS.get(role, ROLE_LIMITS["default"])

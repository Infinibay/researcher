"""Native task profiles select repository or documentary outcomes; a type label grants no execution, acceptance or publication authority."""

DOCUMENTARY_TASK_TYPES = ("research", "investigation", "review")
DEVELOPMENT_TASK_TYPES = (
    "code", "bug_fix", "test", "design", "integrate", "documentation",
    "experimentation", "optimization",
)
NATIVE_TASK_TYPES = (
    "research", "code", "bug_fix", "plan", "investigation", "review", "test",
    "design", "integrate", "documentation", "experimentation", "optimization",
)
# Every persisted task category has a native entry; old labels remain historical.
OWNER_ONLY_LEGACY_TASK_TYPES = NATIVE_TASK_TYPES

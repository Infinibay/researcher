"""Task-type capability boundaries distinguish native documentary work from completed legacy cutovers; they never infer permission from a role or event."""

DOCUMENTARY_TASK_TYPES = ("research", "investigation")
NATIVE_TASK_TYPES = ("research", "code", "bug_fix", "plan", "investigation")
# Supporting native execution does not prove all old domain outcomes migrated.
OWNER_ONLY_LEGACY_TASK_TYPES = ("research", "investigation")

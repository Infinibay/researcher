"""Pure bounded plan policy: exact basis, explicit unknowns and a closed acyclic graph; no framework, persistence or runtime authority."""

import json
import re

from backend.runtime.task_profiles import DOCUMENTARY_TASK_TYPES


def _text(value, name, maximum):
    """Require meaningful bounded UTF-8 content without silently truncating a planning premise."""
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(f"{name} must be nonempty and at most {maximum} UTF-8 bytes")


def _keys(value, required):
    """Reject extra fields that could smuggle task IDs, actors or execution permission into a model proposal."""
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError("Plan fields differ from the declared proposal contract")


def _key(value):
    """Accept only local graph names, never database identities or external references."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_-]{0,47}", value
    ):
        raise ValueError("Plan graph key is invalid")


def validate_plan(packet, sources):
    """Return a detached validated append-only plan; quotes must exist in attributed material, and every dependency must stay inside its DAG."""
    _keys(packet, ("title", "rationale", "assumptions", "basis", "epics", "tasks"))
    _text(packet["title"], "Plan title", 256)
    _text(packet["rationale"], "Plan rationale", 12000)
    if not isinstance(packet["assumptions"], list) or len(packet["assumptions"]) > 16:
        raise ValueError("Plan assumptions must be a bounded explicit list")
    for item in packet["assumptions"]:
        _text(item, "Plan assumption", 4000)
    if not isinstance(packet["basis"], list) or not 1 <= len(packet["basis"]) <= 16:
        raise ValueError("Plan requires attributed observed basis")
    for basis in packet["basis"]:
        _keys(basis, ("source", "quote"))
        _text(basis["source"], "Basis source", 80)
        _text(basis["quote"], "Basis quote", 4000)
        if (
            basis["source"] not in sources
            or basis["quote"] not in sources[basis["source"]]
        ):
            raise ValueError(
                "Plan basis is not an exact quote from its attributed material"
            )
    epics, tasks = packet["epics"], packet["tasks"]
    if (
        not isinstance(epics, list)
        or not 1 <= len(epics) <= 12
        or not isinstance(tasks, list)
        or not 1 <= len(tasks) <= 32
    ):
        raise ValueError("Plan must contain 1–12 epics and 1–32 tasks")
    epic_keys = set()
    task_keys = set()
    graph = {}
    for epic in epics:
        _keys(epic, ("key", "title", "description"))
        _key(epic["key"])
        if epic["key"] in epic_keys:
            raise ValueError("Duplicate epic key")
        epic_keys.add(epic["key"])
        _text(epic["title"], "Epic title", 256)
        _text(epic["description"], "Epic description", 8000)
    for task in tasks:
        _keys(
            task,
            (
                "key",
                "epic_key",
                "type",
                "title",
                "description",
                "acceptance_criteria",
                "priority",
                "depends_on",
            ),
        )
        _key(task["key"])
        _key(task["epic_key"])
        if task["key"] in task_keys or task["epic_key"] not in epic_keys:
            raise ValueError("Duplicate task key or missing epic")
        task_keys.add(task["key"])
        if task["type"] not in (*DOCUMENTARY_TASK_TYPES, "code", "bug_fix"):
            raise ValueError("Plan task type is not supported by the owned runtime")
        if type(task["priority"]) is not int or not 1 <= task["priority"] <= 5:
            raise ValueError("Invalid task priority")
        for name, limit in [
            ("title", 256),
            ("description", 8000),
            ("acceptance_criteria", 8000),
        ]:
            _text(task[name], name, limit)
        deps = task["depends_on"]
        if not isinstance(deps, list) or len(deps) > 32:
            raise ValueError("Invalid dependency list")
        for dep in deps:
            _key(dep)
        if len(set(deps)) != len(deps):
            raise ValueError("Duplicate dependency")
        graph[task["key"]] = set(deps)
    if any(not deps <= task_keys for deps in graph.values()):
        raise ValueError("Plan dependency points outside its proposed graph")
    pending = dict(graph)
    done = set()
    while pending:
        ready = {key for key, deps in pending.items() if deps <= done}
        if not ready:
            raise ValueError("Plan dependencies contain a cycle")
        done.update(ready)
        pending = {key: deps for key, deps in pending.items() if key not in ready}
    encoded = json.dumps(packet, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > 180000:
        raise ValueError("Complete plan exceeds its retained proposal budget")
    return json.loads(encoded)

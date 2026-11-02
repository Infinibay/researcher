"""Bound native search policy and retain discovery facts without claiming evidence.

Search result payloads are optional and vendor-defined. Only observed public URL
fields are retained; arbitrary provider fields, credentials and snippets never become
captured sources. Capture selected URLs through the existing research boundary.
"""

import hashlib
import json
from urllib.parse import urlsplit


class NativeSearchUnavailable(RuntimeError):
    """Configured search cannot be admitted; do not silently switch providers."""


def validate_search_mode(mode):
    """Validate trusted configuration before launching any native process."""
    if not isinstance(mode, str) or mode not in (
        "disabled",
        "cached",
        "indexed",
        "live",
    ):
        raise ValueError(
            "Native web search mode must be disabled, cached, indexed or live"
        )
    return mode


def _text(value, budget):
    """Bound a string's serialized UTF-8 JSON, including escaping overhead."""
    if not isinstance(value, str):
        return ""
    candidate = value.encode("utf-8")[:budget].decode("utf-8", errors="ignore")
    low, high = 0, len(candidate)
    while low < high:
        middle = (low + high + 1) // 2
        if _wire_size(candidate[:middle]) <= budget:
            low = middle
        else:
            high = middle - 1
    return candidate[:low]


def _wire_size(value):
    """Count actual JSON bytes so escaping cannot defeat observation budgets."""
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _url(value):
    """Return a bounded HTTP candidate, never a credential-bearing URL."""
    if not isinstance(value, str) or _wire_size(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme in ("http", "https")
            and parsed.hostname
            and not (parsed.username or parsed.password)
        ):
            return value
    except ValueError:
        pass
    return None


def search_observation(item, *, mode, thread_id, turn_id):
    """Describe one bounded native item; missing results remain explicitly unknown.

    At most 256 nodes / eight levels of opaque results are inspected, and at most
    10 distinct URL fields are retained. A digest binds the received JSON, not its
    truth or completeness. Late observations retain original scope in SQLiteRunStore
    and never grant a new attempt permission to use a source.
    """
    validate_search_mode(mode)
    raw = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    urls, visited, truncated = [], 0, False

    def visit(value, depth=0):
        """Inspect bounded URL-bearing fields without copying opaque content."""
        nonlocal visited, truncated
        visited += 1
        if visited > 256 or depth > 8:
            truncated = True
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in ("url", "link", "href"):
                    if isinstance(nested, str) and _wire_size(nested) > 2048:
                        truncated = True
                    candidate = _url(nested)
                    if candidate and candidate not in urls:
                        if len(urls) < 10:
                            urls.append(candidate)
                        else:
                            truncated = True
                if visited >= 256:
                    truncated = True
                    break
                if isinstance(nested, (dict, list)):
                    visit(nested, depth + 1)
        elif isinstance(value, list):
            for nested in value:
                if visited >= 256:
                    truncated = True
                    break
                visit(nested, depth + 1)

    visit(item.get("results"))
    action = item.get("action")
    normalized_action = None
    if isinstance(action, dict):
        visit(action)
        normalized_action = {"type": _text(action.get("type"), 64)}
        for name in ("query", "pattern"):
            if isinstance(action.get(name), str):
                normalized_action[name] = _text(action[name], 1024)
                truncated |= normalized_action[name] != action[name]
        if isinstance(action.get("queries"), list):
            queries = action["queries"]
            normalized_action["queries"] = [
                _text(q, 512) for q in queries[:8] if isinstance(q, str)
            ]
            truncated |= normalized_action["queries"] != queries
    query = _text(item.get("query"), 2048)
    return {
        "thread_id": thread_id,
        "turn_id": turn_id,
        "item_id": item["id"],
        "type": "webSearch",
        "provider": "openai",
        "mode": mode,
        "query": query,
        "action": normalized_action,
        "candidate_urls": urls,
        "results_state": "not_supplied" if item.get("results") is None else "supplied",
        "native_item_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "truncated": truncated or query != item.get("query", ""),
        "evidence_status": "uncaptured_search_observation",
    }

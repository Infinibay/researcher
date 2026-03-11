"""Warm up SGLang RadixAttention prefix cache with system prompt templates.

Sends each agent role's system prompt (with placeholder values) to the server
so the KV states are pre-computed. Subsequent real requests that share the same
prefix will skip the prefill computation entirely.

Usage:
    python -m backend.scripts.warmup_prefix_cache [--base-url http://localhost:8081]
"""

import argparse
import concurrent.futures
import sys
import time

import requests

# Each role's build_system_prompt with dummy values to generate the static prefix.
# The dynamic parts (agent_name, agent_id) are short and at known positions —
# RadixAttention matches the longest common prefix, so the vast majority of
# tokens (the static template) will be cached.
ROLE_PROMPTS: dict[str, str] = {}


def _load_prompts() -> dict[str, str]:
    """Import and render each role's system prompt with placeholder values."""
    prompts = {}

    dummy = {
        "agent_name": "__warmup_agent__",
        "agent_id": "__warmup_id__",
        "teammates": [],
        "engine": "crewai",
    }

    try:
        from backend.prompts.project_lead.system import build_system_prompt
        prompts["project_lead"] = build_system_prompt(**dummy)
    except Exception as e:
        print(f"  skip project_lead: {e}")

    try:
        from backend.prompts.team_lead.system import build_system_prompt
        prompts["team_lead"] = build_system_prompt(**dummy)
    except Exception as e:
        print(f"  skip team_lead: {e}")

    try:
        from backend.prompts.researcher.system import build_system_prompt
        prompts["researcher"] = build_system_prompt(**dummy)
    except Exception as e:
        print(f"  skip researcher: {e}")

    try:
        from backend.prompts.research_reviewer.system import build_system_prompt
        prompts["research_reviewer"] = build_system_prompt(**dummy)
    except Exception as e:
        print(f"  skip research_reviewer: {e}")

    try:
        from backend.prompts.developer.system import build_system_prompt
        prompts["developer"] = build_system_prompt(**{**dummy, "tech_hints": []})
    except Exception as e:
        print(f"  skip developer: {e}")

    try:
        from backend.prompts.code_reviewer.system import build_system_prompt
        prompts["code_reviewer"] = build_system_prompt(**dummy)
    except Exception as e:
        print(f"  skip code_reviewer: {e}")

    return prompts


def _warmup_one(
    role: str, prompt: str, base_url: str, model: str
) -> tuple[str, float, int]:
    """Send a minimal completion request to seed the prefix cache."""
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "warmup"},
        ],
        "max_tokens": 1,
        "temperature": 0,
    }
    t0 = time.monotonic()
    resp = requests.post(url, json=payload, timeout=120)
    elapsed = time.monotonic() - t0
    resp.raise_for_status()
    data = resp.json()
    prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
    return role, elapsed, prompt_tokens


def main():
    parser = argparse.ArgumentParser(description="Warm up SGLang prefix cache")
    parser.add_argument(
        "--base-url", default="http://localhost:8081",
        help="SGLang server base URL (default: http://localhost:8081)",
    )
    parser.add_argument(
        "--model", default="mistral-small-3.2-24b",
        help="Model name as registered in SGLang (default: mistral-small-3.2-24b)",
    )
    args = parser.parse_args()

    # Check server is up
    try:
        resp = requests.get(f"{args.base_url}/v1/models", timeout=5)
        resp.raise_for_status()
    except Exception:
        print(f"ERROR: Server not reachable at {args.base_url}")
        sys.exit(1)

    print(f"Loading system prompts...")
    prompts = _load_prompts()
    if not prompts:
        print("No prompts loaded — nothing to warm up")
        sys.exit(1)

    print(f"Warming up {len(prompts)} role prefixes on {args.base_url}...")
    print()

    t_start = time.monotonic()

    # Send all warmup requests concurrently (they'll hit different DP workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(prompts)) as pool:
        futures = {
            pool.submit(_warmup_one, role, prompt, args.base_url, args.model): role
            for role, prompt in prompts.items()
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                role, elapsed, tokens = future.result()
                print(f"  {role:20s}  {tokens:5d} tokens  {elapsed:.1f}s")
            except Exception as e:
                role = futures[future]
                print(f"  {role:20s}  FAILED: {e}")

    total = time.monotonic() - t_start
    print(f"\nDone in {total:.1f}s — prefix cache is warm")


if __name__ == "__main__":
    main()

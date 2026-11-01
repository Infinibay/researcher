"""Evaluation adapter: guarded unchanged candidate, private grant delivered by FD."""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

import litellm
from infinidev.config.providers import get_provider
from infinidev.config.settings import settings

payload = json.loads(os.read(int(sys.argv[2]), 8192))
os.close(int(sys.argv[2]))
assert settings.LLM_PROVIDER == "openai_subscription"
expected = get_provider("openai_subscription").default_base_url
real_completion = litellm.completion
records = []
lock = threading.Lock()


def bounded_completion(*args, **kwargs):
    with lock:
        if (
            len(records) >= 32
            or sum(r.get("observed_tokens") or 0 for r in records) >= 350000
        ):
            raise RuntimeError("Evaluation inference budget exhausted")
        if kwargs.get("api_base") != expected or not kwargs.get("model", "").startswith(
            "openai/responses/"
        ):
            raise RuntimeError("Evaluation refused a non-subscription inference route")
        record = {
            "model": kwargs["model"],
            "subscription_route": True,
            "started_monotonic": time.monotonic(),
        }
        records.append(record)
        Path(".infinidev/evaluation-requests.json").write_text(
            json.dumps(records, indent=2)
        )
    response = real_completion(*args, **kwargs)

    def usage(value):
        count = getattr(getattr(value, "usage", None), "total_tokens", None)
        if count is not None:
            with lock:
                record["observed_tokens"] = int(count)
                Path(".infinidev/evaluation-requests.json").write_text(
                    json.dumps(records, indent=2)
                )

    if not kwargs.get("stream"):
        usage(response)
        return response

    def stream():
        try:
            for chunk in response:
                usage(chunk)
                yield chunk
        finally:
            close = getattr(response, "close", None)
            if close:
                close()

    return stream()


litellm.completion = bounded_completion
logging.basicConfig(level=logging.WARNING)
from infinidev.engine.mcp_client import get_default_mcp_manager
from infinidev.tools.mcp_bridge import discover_mcp_tool_classes

manager = get_default_mcp_manager()
client = manager.get("researcher")
assert client is not None
client.env.update(
    {
        "RESEARCHER_API_URL": payload["api_url"],
        "RESEARCHER_TOOL_TOKEN": payload["grant_token"],
    }
)
classes = discover_mcp_tool_classes(force=True, block=True)
names = {c.model_fields["name"].default for c in classes}
assert (
    "ken_find" in names and len([n for n in names if n.startswith("researcher_")]) == 11
)
import uvicorn
from infinidev.server.app import create_app

uvicorn.run(
    create_app(token=payload["control_token"]),
    fd=int(sys.argv[1]),
    log_level="warning",
    access_log=False,
)

"""Exercise a separately identified ONNX candidate without changing the product's Ken pin.

Build the candidate with docs/patches/ken-onnx-1.23.2.patch first. This diagnostic
temporarily selects its exact version in this process only; normal host admission
still requires the published Ken release. No subscription file or generative
model is used; retrieval models run locally.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
CANDIDATE_VERSION = "0.18.0+researcher.1"


async def main(args):
    """Verify candidate metadata, then reuse the real cold-start and two-owner MCP evaluation."""
    from backend.runtime import ken_worker
    from evals.security.run_ken_isolation import main as evaluate_isolation

    command = args.ken_command.resolve(strict=True)
    probe = subprocess.run(
        [str(command.parent / "python"), "-I", "-c",
         "import importlib.metadata as m,json,ken,onnx; "
         "print(json.dumps({'distribution':m.version('ken-rank'),"
         "'module':ken.__version__,'onnx':onnx.__version__}))"],
        cwd="/", env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        capture_output=True, text=True, timeout=15, check=True,
    )
    versions = json.loads(probe.stdout)
    if versions != {"distribution": CANDIDATE_VERSION,
                    "module": CANDIDATE_VERSION, "onnx": "1.23.2"}:
        raise ValueError("Expected the explicitly identified Ken/ONNX candidate")
    published_version = ken_worker.KEN_VERSION
    print(json.dumps({"diagnostic_candidate": versions,
                      "product_pin_unchanged": published_version}), flush=True)
    with patch.object(ken_worker, "KEN_VERSION", CANDIDATE_VERSION):
        await evaluate_isolation(args)
    if ken_worker.KEN_VERSION != published_version:
        raise RuntimeError("Diagnostic version selection was not restored")


if __name__ == "__main__":
    from evals.runtime.kernel_trial import arguments

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--ken-command", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--memory-mib", type=int, required=True)
    asyncio.run(main(arguments(parser)))

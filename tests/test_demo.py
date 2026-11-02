"""The README demo must keep working (G6)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_runs_and_reveals_truth_only_at_the_end():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo.py"), "--level", "L2",
                          "--index", "1"], capture_output=True, text=True, check=True,
                         timeout=120).stdout
    head, _, tail = out.partition("== Hidden truth")
    assert "--> observe" in head and "--> submit" in head and "true cause:" in tail
    # the truth label never appears before the reveal (agent-visible part)
    assert "dispatch_error_surge" not in head.split("Fault taxonomy")[0]

"""One investigation, end to end, in the terminal (no GPU, no API key).

Generates a hidden-fault incident, lets the knowledge-based playbook investigate it through
the public tools only (observe, query, hypothesize, experiment, submit), then reveals the
hidden truth and the evaluator's score.

Usage: uv run python scripts/demo.py [--level L2] [--index 0] [--agent playbook|rules]
Uses the development seed (2026) so the final evaluation seed stays untouched.
"""

from __future__ import annotations

import argparse
import textwrap

from deliverytwin.agent.baselines import run_playbook_agent, run_rules_agent
from deliverytwin.agent.session import InvestigationSession
from deliverytwin.benchmark.evaluator import evaluate
from deliverytwin.benchmark.generator import LEVELS, generate_instance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="L2", choices=sorted(LEVELS))
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--agent", default="playbook", choices=["playbook", "rules"])
    ap.add_argument("--width", type=int, default=100)
    a = ap.parse_args()

    inst = generate_instance(a.level, a.index, master_seed=2026)
    s = InvestigationSession(inst)
    (run_playbook_agent if a.agent == "playbook" else run_rules_agent)(s)

    print(f"== Incident {inst.public.dataset_id} (level {a.level}, agent {a.agent})\n")
    for step in s.transcript:
        args = "" if not step["args"] else f" {step['args']}"
        print(f"--> {step['op']}{args}"[: a.width * 2])
        body = step["response"].strip().splitlines()
        shown = body[:12] + ([f"... ({len(body) - 12} more lines)"] if len(body) > 12 else [])
        for line in shown:
            print(textwrap.indent(line[: a.width], "    "))
        print()

    ev = evaluate(s.bundle({"name": a.agent}), inst)
    print("== Hidden truth (only the evaluator sees this)")
    print(f"    true cause:      {inst.private.family}")
    print(f"    submitted cause: {ev.get('cause')}")
    print(f"    exact: {ev['exact']}  abstained: {ev['abstained']}  path_f1: {ev['path_f1']:.2f}")
    if ev.get("recommendation"):
        print(f"    recommendation {ev['recommendation']}: change in bad-order rate in the "
              f"true world = {ev['recommendation_diff_bad']:+.3f}")


if __name__ == "__main__":
    main()

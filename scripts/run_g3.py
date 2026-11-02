"""Run investigator agents on benchmark instances and evaluate them (G3).

Usage:
  uv run python scripts/run_g3.py --agent playbook --levels L0,L1,L2 --n 20 --seed eval
  uv run --group llm python scripts/run_g3.py --agent llm --model gpt-5-nano --levels L2 --n 1

Seeds: dev = public development seed (rules were tuned on it); eval = 909090 (held-out,
but LLM transcripts were inspected there); final = 515151 (untouched; final G3 numbers).
Bundles and results go to runs/ (git-ignored). LLM spend is capped by .env.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from deliverytwin.agent.baselines import run_playbook_agent, run_rules_agent
from deliverytwin.agent.session import Budgets, InvestigationSession, bundle_json
from deliverytwin.benchmark.evaluator import bundle_leaks, evaluate
from deliverytwin.benchmark.generator import LEVELS, generate_instance

ROOT = Path(__file__).resolve().parents[1]
SEEDS = {"dev": 2026, "eval": 909_090, "final": 515_151}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["rules", "playbook", "llm", "local"], required=True)
    ap.add_argument("--adapter", default="", help="local: path to a LoRA adapter")
    ap.add_argument("--model", default="gpt-5-nano")
    ap.add_argument("--reasoning", default="low")
    ap.add_argument("--levels", default="L0,L1,L2")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--seed", choices=list(SEEDS), default="eval")
    ap.add_argument("--max-turns", type=int, default=16)
    ap.add_argument("--tag", default="")
    ap.add_argument("--budgets-of", default=None, choices=sorted(LEVELS),
                    help="G5 matched ladder: run these instances with another level's "
                         "budgets (e.g. L2 instances with L4 budgets)")
    ap.add_argument("--twin-delta", type=float, default=None,
                    help="G5: run the lab on an imperfect twin (mode B) with this mismatch")
    ap.add_argument("--no-experiments", action="store_true",
                    help="G5 ablation H1/H9: experiment tool removed from the schema and "
                         "the dispatcher, experiment budget zero; query budget unchanged")
    a = ap.parse_args()

    client = None
    disabled = frozenset({"experiment"}) if a.no_experiments else frozenset()
    if a.agent == "llm":
        from deliverytwin.agent.llm import LLMClient, spent_usd
        client = LLMClient(a.model, reasoning_effort=a.reasoning or None, tag=a.tag)
        start_spend = spent_usd()

    if a.agent == "local":
        from deliverytwin.agent.local_llm import LocalQwenClient
        client = LocalQwenClient(adapter=a.adapter or None)
    name = {"llm": f"llm-{a.model}",
            "local": "local-qwen3-1.7b" + ("-sft" if a.adapter else "")}.get(a.agent, a.agent)
    out_dir = ROOT / "runs" / "g3" / f"{name}_{a.seed}{('_' + a.tag) if a.tag else ''}"
    (out_dir / "bundles").mkdir(parents=True, exist_ok=True)
    rows = []
    for level in a.levels.split(","):
        for i in range(a.start, a.start + a.n):
            inst = generate_instance(level, i, master_seed=SEEDS[a.seed])
            budgets = (Budgets(**LEVELS[a.budgets_of].get("budgets", {}))
                       if a.budgets_of else None)
            s = InvestigationSession(inst, budgets=budgets, twin_delta=a.twin_delta)
            if a.no_experiments:
                s.budgets.max_experiments = 0
            t = time.time()
            if a.agent == "rules":
                meta = run_rules_agent(s)
            elif a.agent == "playbook":
                meta = run_playbook_agent(s)
            elif a.agent == "local":
                from deliverytwin.agent.llm_agent import run_llm_agent
                meta = run_llm_agent(s, client, max_turns=a.max_turns,
                                     disabled_tools=disabled)
            else:
                from deliverytwin.agent.llm import BudgetExceeded
                from deliverytwin.agent.llm_agent import run_llm_agent
                try:
                    meta = run_llm_agent(s, client, max_turns=a.max_turns,
                                     disabled_tools=disabled)
                except BudgetExceeded as e:
                    print("STOP:", e)
                    break
            meta["seconds"] = round(time.time() - t, 1)
            bundle = s.bundle(meta)
            text = bundle_json(bundle)
            leaks = bundle_leaks(text, inst)
            if leaks:
                raise RuntimeError(f"private data in bundle {bundle['dataset_id']}")
            (out_dir / "bundles" / f"{bundle['dataset_id']}.json").write_text(text)
            ev = evaluate(bundle, inst)
            ev.update(agent=name, meta=meta)
            rows.append(ev)
            print(f"{level} #{i} {inst.private.family:22s} -> cause={ev.get('cause')!s:22s} "
                  f"exact={ev['exact']} exps={ev['used']['experiments']} "
                  f"q={ev['used']['queries']} turns={meta.get('turns', '-')}")
        else:
            continue
        break
    (out_dir / "results.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in rows))
    for level in sorted({r["level"] for r in rows}):
        rs = [r for r in rows if r["level"] == level]
        print(f"[{name}] {level}: n={len(rs)} exact={statistics.fmean(r['exact'] for r in rs):.2f} "
              f"family={statistics.fmean(r['family_correct'] for r in rs):.2f} "
              f"abstain_truth={statistics.fmean(r['abstained_with_truth'] for r in rs):.2f} "
              f"path_f1={statistics.fmean(r['path_f1'] for r in rs):.2f} "
              f"exps={statistics.fmean(r['used']['experiments'] for r in rs):.1f}")
    if a.agent == "llm":
        print(f"LLM spend this run: ${spent_usd() - start_spend:.4f}; total ${spent_usd():.4f}")
    if a.agent == "local":
        print(f"local tokens: prompt {client.prompt_tokens}, completion {client.completion_tokens}")


if __name__ == "__main__":
    main()

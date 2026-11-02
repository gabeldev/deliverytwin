"""Summarise the final G3 evaluation (seed 515151) into docs/reports/G3_REPORT_DATA.json.

Usage: uv run python scripts/g3_report.py
Reads runs/g3/*_final*/results.jsonl and the LLM cost ledger.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wilson(k, n):
    if n == 0:
        return [math.nan, math.nan]
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load():
    runs = {}
    for d in sorted((ROOT / "runs" / "g3").glob("*_final*")):
        f = d / "results.jsonl"
        if f.exists() and f.read_text().strip():
            runs[d.name] = [json.loads(line) for line in f.read_text().splitlines() if line]
    return runs


def main():
    runs = load()
    ledger = ROOT / "runs" / "llm_ledger.jsonl"
    cost_by_tag = defaultdict(float)
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            e = json.loads(line)
            if "usd" in e:  # settled entries (reservations are accounted in llm.spent_usd)
                cost_by_tag[(e["model"], e.get("tag", ""))] += e["usd"]
    summary = {}
    for name, rows in runs.items():
        per = {}
        for level in ("L0", "L1", "L2"):
            rs = [r for r in rows if r["level"] == level]
            if not rs:
                continue
            n = len(rs)
            k = sum(r["exact"] for r in rs)
            per[level] = {
                "n": n, "exact": round(k / n, 3), "exact_wilson95": wilson(k, n),
                "abstained_with_truth": round(sum(r["abstained_with_truth"] for r in rs) / n, 3),
                "wrong_commit": round(sum((not r["exact"]) and r.get("cause") is not None
                                          for r in rs) / n, 3),
                "path_f1": round(sum(r["path_f1"] for r in rs) / n, 3),
                "experiments": round(sum(r["used"]["experiments"] for r in rs) / n, 2),
                "brier_committed": (round(sum(r["brier"] for r in rs if r.get("brier") is not None)
                                       / max(1, sum(r.get("brier") is not None for r in rs)), 3)),
                "coverage": round(sum(r.get("cause") is not None for r in rs) / n, 3),
            }
        summary[name] = per
    # cost per episode for LLM runs
    for name, rows in runs.items():
        if name.startswith("llm-"):
            model = name.split("_")[0][4:]
            tag = name.split("_")[-1]
            summary[name]["usd_total"] = round(cost_by_tag.get((model, tag), 0.0), 4)
            summary[name]["usd_per_episode"] = round(cost_by_tag.get((model, tag), 0.0) / len(rows), 5)

    def key(r):
        return (r["level"], r["dataset_id"])

    # paired comparisons vs the playbook baseline (same instances)
    paired = {}
    # Post-review runs carry the tag "fix"; pre-fix runs (r1/r2) are kept only to measure
    # run-to-run variability of the same model.
    base = {key(r): r["exact"] for r in runs.get("playbook_final_fix", [])}
    for name, rows in runs.items():
        if name == "playbook_final_fix" or not base or not name.endswith("_fix"):
            continue
        for level in ("L0", "L1", "L2"):
            pairs = [(base[key(r)], r["exact"]) for r in rows
                     if r["level"] == level and key(r) in base]
            b = sum(1 for x, y in pairs if x and not y)
            c = sum(1 for x, y in pairs if y and not x)
            paired[f"{name} vs playbook {level}"] = {
                "n": len(pairs), "playbook_only": b, "agent_only": c,
                "mcnemar_p": round(mcnemar_exact(b, c), 4)}
    # run-to-run noise floor (same model, same instances, r1 vs r2)
    floor = {}
    for model in ("gpt-5.6-luna", "gpt-5-mini"):
        r1 = {key(r): r for r in runs.get(f"llm-{model}_final_r1", [])}
        r2 = {key(r): r for r in runs.get(f"llm-{model}_final_r2", [])}
        common = sorted(set(r1) & set(r2))
        if not common:
            continue
        def diagnosis(r):
            # Full diagnosis: cause + scope, or the canonical unresolved set (Codex review G3).
            return (r.get("cause"), r.get("scope"), tuple(sorted(r.get("unresolved_between") or ())))

        agree = sum(diagnosis(r1[k]) == diagnosis(r2[k]) for k in common)
        disc = sum(r1[k]["exact"] != r2[k]["exact"] for k in common)
        floor[model] = {"n": len(common), "same_answer": round(agree / len(common), 3),
                        "exact_discordant": disc,
                        "exact_r1": round(sum(r1[k]["exact"] for k in common) / len(common), 3),
                        "exact_r2": round(sum(r2[k]["exact"] for k in common) / len(common), 3)}
    out = {"summary": summary, "paired_vs_playbook": paired,
           "run_to_run_prefix": floor,
           "note": "runs tagged _fix are the post-review final results; r1/r2 are pre-fix "
                   "(older lab: accepted-only cohort, z intervals) kept for repeat variability"}
    (ROOT / "docs" / "reports" / "G3_REPORT_DATA.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

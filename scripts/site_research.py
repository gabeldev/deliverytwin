"""Export the research results shown on the public site (site/public/data/research.json).

Every figure is recomputed from run files (runs/g3/*/results.jsonl) or copied from the
committed report data (docs/reports/*.json), and carries its source. Nothing is typed in.

Usage: uv run python scripts/site_research.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from g3_report import mcnemar_exact, wilson

RUNS = ROOT / "runs" / "g3"
REP = ROOT / "docs" / "reports"
OUT = ROOT / "site" / "public" / "data" / "research.json"

AGENTS = {  # agent key -> (final-seed run for L0-L2, display name, kind)
    "rules": ("rules_final_fix", "Observational rules", "baseline"),
    "playbook": ("playbook_final_fix", "Playbook + experiment", "baseline"),
    "gpt-5-nano": ("llm-gpt-5-nano_final_fix", "gpt-5-nano", "api-llm"),
    "gpt-5-mini": ("llm-gpt-5-mini_final_fix", "gpt-5-mini", "api-llm"),
    "gpt-5.6-luna": ("llm-gpt-5.6-luna_final_fix", "gpt-5.6-luna", "api-llm"),
    "qwen-base": ("local-qwen3-1.7b_final_g4", "Qwen3-1.7B base", "local"),
    "qwen-sft": ("local-qwen3-1.7b-sft_final_g4", "Qwen3-1.7B + LoRA (ours)", "local"),
}


def rows(run: str) -> list[dict]:
    f = RUNS / run / "results.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def acc(rs: list[dict]) -> dict:
    n, k = len(rs), sum(r["exact"] for r in rs)
    return {"n": n, "k": k, "acc": round(k / n, 3) if n else None,
            "ci": wilson(k, n) if n else None,
            "abstain": round(sum(r["abstained"] for r in rs) / n, 3) if n else None,
            "experiments": round(sum(r["used"]["experiments"] for r in rs) / n, 2) if n else None}


def by_level(rs, lv):
    return [r for r in rs if r["level"] == lv]


def paired(a, b):
    ka = {r["dataset_id"]: r["exact"] for r in a}
    kb = {r["dataset_id"]: r["exact"] for r in b}
    c = sorted(set(ka) & set(kb))
    x = sum(ka[d] and not kb[d] for d in c)
    y = sum(kb[d] and not ka[d] for d in c)
    return {"n": len(c), "only_first": x, "only_second": y, "p": round(mcnemar_exact(x, y), 4)}


def main():
    data = json.loads((REP / "G5_REPORT_DATA.json").read_text())
    out: dict = {"seed": "final 515151", "n_per_level": 20,
                 "sources": {"runs": "runs/g3/*/results.jsonl (recomputed)",
                             "g5": "docs/reports/G5_REPORT_DATA.json",
                             "interventions": "docs/reports/G5_INTERVENTIONS.json",
                             "gsm8k": "docs/reports/G4_GENERAL_CHECK.json"}}
    # 1. L0-L2 by agent
    lv_tab = {}
    for key, (run, name, kind) in AGENTS.items():
        rs = rows(run)
        lv_tab[key] = {"name": name, "kind": kind, "run": run,
                       **{lv: acc(by_level(rs, lv)) for lv in ("L0", "L1", "L2")}}
    out["levels"] = lv_tab
    sft_l2 = by_level(rows(AGENTS["qwen-sft"][0]), "L2")
    out["l2_pairs"] = {k: paired(sft_l2, by_level(rows(AGENTS[k][0]), "L2"))
                       for k in AGENTS if k != "qwen-sft"}
    # 2. With vs without the experiment tool (pre-registered H1/H9)
    h = data["h1_h9_sft_l2"]
    out["experiment_ablation"] = {
        "with": {k: h["with_experiments"][k] for k in ("n", "exact", "ci")},
        "without": {k: h["without_experiments"][k] for k in ("n", "exact", "ci")},
        "paired": h["paired"], "label": "pre-registered (H1/H9)",
        "source": "G5_REPORT_DATA.json:h1_h9_sft_l2"}
    # 3. Matched ladder on the same L2 incidents
    m = data["matched_ladder_on_l2_instances"]
    out["matched_ladder"] = {
        cond: {a: {k: v[a].get(k) for k in ("exact", "ci", "abstained", "experiments_mean")}
               for a in ("rules", "playbook", "qwen-base", "qwen-sft")}
        for cond, v in m.items()}
    out["matched_ladder"]["source"] = "G5_REPORT_DATA.json:matched_ladder_on_l2_instances"
    # 4. L4-L6 own samples incl. API LLMs (addendum A1, exploratory)
    lad = data["ladder_l3_l6"]
    api = data["addendum_a1_api"]["ladder"]
    out["ladder"] = {a: {lv: {k: s.get(k) for k in ("exact", "ci", "experiments_mean")}
                         for lv, s in t.items() if lv in ("L4", "L5", "L6")}
                     for a, t in {**lad, **api}.items()}
    out["ladder"]["source"] = "G5_REPORT_DATA.json:ladder_l3_l6, addendum_a1_api"
    # 5. Twin sweep (playbook, L2)
    out["twin_sweep"] = {k: {"exact": v["exact"], "ci": v["ci"],
                             "rec_diff_bad": v["recommendation_true_world_diff_bad_mean"],
                             "vs_A_p": v["vs_mode_A"].get("mcnemar_p")}
                         for k, v in data["twin_sweep_playbook_l2"].items()}
    # 6. Interventions study
    iv = json.loads((REP / "G5_INTERVENTIONS.json").read_text())
    out["interventions"] = {
        "n_incidents": iv["n_incidents"], "replicas": iv["replicas"],
        "placebo_all_exactly_zero": iv["placebo_all_exactly_zero"],
        "variance_ratio": iv["variance_ratio_paired_over_unpaired"],
        "regret_common_oracle": iv["regret_vs_common_oracle"],
        "infeasible": {a: c["infeasible_recommendations"] for a, c in iv["agent_coverage"].items()},
        "best_action_counts_by_family": iv["best_action_counts_by_family"],
        "mean_pareto_size": iv["mean_pareto_size"]}
    # 7. General ability check
    g = json.loads((REP / "G4_GENERAL_CHECK.json").read_text())
    out["gsm8k"] = {"n": g["n"], "base_strict": g["base_acc"], "sft_strict": g["sft_acc"],
                    "base_last_number": round(g["diagnostic_last_number"]["base_correct"] / g["n"], 3),
                    "sft_last_number": round(g["diagnostic_last_number"]["sft_correct"] / g["n"], 3)}
    # 8. Names-only leakage control
    nm = json.loads((REP / "G5_NAMES_ONLY.json").read_text())["per_level"]
    out["names_only"] = {lv: {"acc": v["names_only_acc"], "majority": v["majority_acc"]}
                         for lv, v in nm.items()}
    # 9. Receipt: every recorded, evaluated investigation behind the reports
    counts: Counter = Counter()
    for d in sorted(RUNS.iterdir()):
        if not d.is_dir() or "_site" in d.name:
            continue
        n = len(rows(d.name))
        if not n:
            continue
        agent = d.name.split("_")[0]
        group = ("API LLMs" if agent.startswith("llm-") else
                 "Qwen3-1.7B (local)" if agent.startswith("local-") else "Baselines")
        counts[(group, agent)] += n
    receipt = {}
    for (group, agent), n in sorted(counts.items()):
        receipt.setdefault(group, []).append({"agent": agent, "n": n})
    out["receipt"] = {"groups": receipt, "total": sum(counts.values()),
                      "note": "Every evaluated investigation recorded under runs/g3: all seeds, "
                              "including development, ablation and superseded pre-fix runs "
                              "(reported numbers use the post-fix runs only); invalid pre-fix "
                              "L3 rows excluded"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print("total investigations", out["receipt"]["total"])
    print({k: (v["L2"]["acc"]) for k, v in lv_tab.items()})


if __name__ == "__main__":
    main()

"""Summarise G4/G5 runs (final seed 515151) into docs/reports/G5_REPORT_DATA.json.

Usage: uv run python scripts/g5_report.py
Reads runs/g3/*/results.jsonl, G5_INTERVENTIONS.json, G5_NAMES_ONLY.json,
G4_GENERAL_CHECK.json (if present).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from g3_report import mcnemar_exact, wilson

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "g3"


def rows(run: str) -> list[dict]:
    f = RUNS / run / "results.jsonl"
    if not f.exists() or not f.read_text().strip():
        return []
    return [json.loads(line) for line in f.read_text().splitlines() if line]


def by_level(rs: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rs:
        out.setdefault(r["level"], []).append(r)
    return out


def summary(rs: list[dict]) -> dict:
    if not rs:
        return {"status": "not_run", "n": 0}
    n, k = len(rs), sum(r["exact"] for r in rs)
    rec = [r.get("recommendation_diff_bad") or 0.0 for r in rs]  # no recommendation = no-op
    return {"n": n, "exact": round(k / n, 3), "ci": wilson(k, n),
            "abstained": round(sum(r["abstained"] for r in rs) / n, 3),
            "wrong_commit": round(sum(not r["exact"] and not r["abstained"] for r in rs) / n, 3),
            "experiments_mean": round(statistics.fmean(r["used"]["experiments"] for r in rs), 2),
            "recommendation_true_world_diff_bad_mean": round(statistics.fmean(rec), 4)}


def paired(a: list[dict], b: list[dict], label: str = "exploratory") -> dict:
    """Exact McNemar on the shared instances. `label`: principal = a G5 registered
    prediction; g4_main_not_preregistered = the main G4 comparison (G4 had no registration);
    component_of_H2 = an input to a registered claim, not a test of it; exploratory."""
    ka = {r["dataset_id"]: r["exact"] for r in a}
    kb = {r["dataset_id"]: r["exact"] for r in b}
    common = sorted(set(ka) & set(kb))
    only_a = sum(ka[d] and not kb[d] for d in common)
    only_b = sum(kb[d] and not ka[d] for d in common)
    if not common:  # not run: never report p = 1 for a comparison that did not happen
        return {"status": "not_run", "label": label, "n": 0, "n_first": len(ka),
                "n_second": len(kb), "mcnemar_p": None}
    return {"status": "ok" if len(common) == max(len(ka), len(kb)) else "incomplete",
            "label": label, "n": len(common), "only_first": only_a, "only_second": only_b,
            "mcnemar_p": round(mcnemar_exact(only_a, only_b), 4)}


def table(spec: dict[str, list[str]]) -> dict:
    out = {}
    for agent, runs in spec.items():
        rs = [r for run in runs for r in rows(run)]
        out[agent] = {lv: summary(v) for lv, v in sorted(by_level(rs).items())}
    return out


def main():
    rep: dict = {}
    g4 = {"qwen-base": ["local-qwen3-1.7b_final_g4"], "qwen-sft": ["local-qwen3-1.7b-sft_final_g4"],
          "playbook": ["playbook_final_fix"], "rules": ["rules_final_fix"]}
    rep["g4_l0_l2"] = table(g4)
    rep["g4_paired"] = {}
    for lv in ("L0", "L1", "L2"):
        sft = by_level(rows("local-qwen3-1.7b-sft_final_g4")).get(lv, [])
        base = by_level(rows("local-qwen3-1.7b_final_g4")).get(lv, [])
        pb = by_level(rows("playbook_final_fix")).get(lv, [])
        mini = by_level(rows("llm-gpt-5-mini_final_fix")).get(lv, [])
        rep["g4_paired"][lv] = {"sft_vs_base": paired(sft, base, "g4_main_not_preregistered"),
                                "sft_vs_playbook": paired(sft, pb),
                                "sft_vs_gpt5mini": paired(sft, mini)}
    ladder = {"rules": ["rules_final_g5", "rules_final_g5l3"],
              "playbook": ["playbook_final_g5", "playbook_final_g5l3"],
              "qwen-base": ["local-qwen3-1.7b_final_g5"],
              "qwen-sft": ["local-qwen3-1.7b-sft_final_g5"]}
    rep["ladder_l3_l6"] = table(ladder)
    rep["ladder_paired"] = {}
    for lv in ("L3", "L4", "L5", "L6"):
        get = {a: by_level([x for run in r for x in rows(run)]).get(lv, []) for a, r in ladder.items()}
        rep["ladder_paired"][lv] = {
            # PREREG study 3: (a) playbook > rules on L5; (b) SFT not better than base on L4.
            "playbook_vs_rules": paired(get["playbook"], get["rules"],
                                        "principal" if lv == "L5" else "exploratory"),
            # (b) registers "SFT not better than base on L4" (principal). On L5 the contrast
            # is only a COMPONENT of H2 (the registered claim is that the gain SHRINKS).
            "sft_vs_base": paired(get["qwen-sft"], get["qwen-base"],
                                  {"L4": "principal", "L5": "component_of_H2"}.get(
                                      lv, "exploratory")),
            "sft_vs_playbook": paired(get["qwen-sft"], get["playbook"])}
    # Matched ladder (Codex report review #1): the SAME L2 instances run with L4 budgets
    # (--budgets-of L4) or with the L6 twin (--twin-delta 0.25), so the change is isolated.
    l2_runs = {"rules": "rules_final_fix", "playbook": "playbook_final_fix",
               "qwen-base": "local-qwen3-1.7b_final_g4",
               "qwen-sft": "local-qwen3-1.7b-sft_final_g4"}
    rep["matched_ladder_on_l2_instances"] = {}
    for cond, tag in (("L2_mode_A", None), ("L4_budgets", "l4matched"), ("L6_twin_0.25", "twin0.25")):
        rep["matched_ladder_on_l2_instances"][cond] = {}
        for agent, base_run in l2_runs.items():
            run = base_run if tag is None else f"{base_run.rsplit('_', 1)[0]}_{tag}"
            rs = by_level(rows(run)).get("L2", [])
            entry = summary(rs)
            if tag is not None:
                entry["vs_L2_mode_A"] = paired(rs, by_level(rows(base_run)).get("L2", []))
            rep["matched_ladder_on_l2_instances"][cond][agent] = entry
    mp = rep["matched_ladder_on_l2_instances"]
    for cond in ("L4_budgets", "L6_twin_0.25"):
        tag = "l4matched" if cond == "L4_budgets" else "twin0.25"
        g = {a: by_level(rows(f"{r.rsplit('_', 1)[0]}_{tag}")).get("L2", [])
             for a, r in l2_runs.items()}
        mp[cond]["paired"] = {"sft_vs_base": paired(g["qwen-sft"], g["qwen-base"]),
                              "sft_vs_playbook": paired(g["qwen-sft"], g["playbook"]),
                              "playbook_vs_rules": paired(g["playbook"], g["rules"])}
    # Addendum A1 (exploratory, paid API).
    api = {"gpt-5-mini": "llm-gpt-5-mini_final_g5", "gpt-5.6-luna": "llm-gpt-5.6-luna_final_g5"}
    rep["addendum_a1_api"] = {"ladder": table({a: [r] for a, r in api.items()})}
    rep["addendum_a1_api"]["paired"] = {
        lv: {f"{a}_vs_{o}": paired(by_level(rows(r)).get(lv, []),
                                   by_level(rows(orun)).get(lv, []))
             for a, r in api.items()
             for o, orun in (("qwen-sft", "local-qwen3-1.7b-sft_final_g5"),
                             ("playbook", "playbook_final_g5"))}
        for lv in ("L4", "L5", "L6")}
    luna_l2 = by_level(rows("llm-gpt-5.6-luna_final_fix")).get("L2", [])
    luna_noexp = by_level(rows("llm-gpt-5.6-luna_final_noexp")).get("L2", [])
    rep["addendum_a1_api"]["luna_l2_with_vs_without_experiments"] = {
        "with": summary(luna_l2), "without": summary(luna_noexp),
        "paired": paired(luna_l2, luna_noexp)}
    sweep = {"mode_A": "playbook_final_fix"} | {f"delta_{d}": f"playbook_final_twin{d}"
                                                for d in ("0", "0.1", "0.25", "0.5")}
    a_l2 = by_level(rows("playbook_final_fix")).get("L2", [])
    rep["twin_sweep_playbook_l2"] = {}
    for k, run in sweep.items():
        rs = by_level(rows(run)).get("L2", [])
        if rs:
            rep["twin_sweep_playbook_l2"][k] = summary(rs) | {
                "vs_mode_A": paired(rs, a_l2, "principal" if k == "delta_0" else "exploratory")}
    noexp = by_level(rows("local-qwen3-1.7b-sft_final_noexp")).get("L2", [])
    withexp = by_level(rows("local-qwen3-1.7b-sft_final_g4")).get("L2", [])
    if noexp:
        rep["h1_h9_sft_l2"] = {"with_experiments": summary(withexp),
                               "without_experiments": summary(noexp),
                               "paired": paired(withexp, noexp, "principal"),
                               "condition": "experiment tool removed from schema and "
                                            "dispatcher; query budget unchanged (25)"}
    for name in ("G5_INTERVENTIONS", "G5_NAMES_ONLY", "G4_GENERAL_CHECK"):
        f = ROOT / "docs" / "reports" / f"{name}.json"
        if f.exists():
            rep[name.lower()] = json.loads(f.read_text())
    (ROOT / "docs" / "reports" / "G5_REPORT_DATA.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: rep[k] for k in rep if not k.startswith(("g5_inter", "g5_names"))},
                     indent=1))


if __name__ == "__main__":
    main()

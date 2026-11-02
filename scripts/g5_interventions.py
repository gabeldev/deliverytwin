"""G5 study 1: intervention research on the final-seed incidents (PREREG_G5.md).

For every incident (L0-L2, final seed, indices 0-19) and every action of the feasible menu,
20 paired replicas (ids 2001-2020, disjoint from everything agents saw) measure:
  delta bad rate on the demand cohort (primary), delta penalised time, delta rejected
  share, and the action's cost units.
Outputs: per family x action effects (t-CI over incidents), Pareto sets, best feasible
action, regret of the per-family default remedy and of the agents' G3/G4 recommendations,
paired/unpaired variance ratios (H4/H7) and the placebo execution floor (H8).

Usage: uv run python scripts/g5_interventions.py [--workers 8]
Output: docs/reports/G5_INTERVENTIONS.json (+ per-incident rows in runs/g5/)
"""

from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from deliverytwin.agent.baselines import REMEDY
from deliverytwin.agent.protocol import intervention_cost
from deliverytwin.agent.session import LAB_COHORT, LAB_FOLLOW_UP, _world_for_lab, t_ci
from deliverytwin.benchmark.generator import generate_instance
from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    NoOp,
    Placebo,
    SetAdmissionRate,
    SetDispatcherWorkers,
    SetDispatchPolicy,
    SetRetryBackoff,
)
from deliverytwin.simulation.kpis import demand_cohort_metrics

ROOT = Path(__file__).resolve().parents[1]
FINAL = 515_151
REPLICAS = list(range(2001, 2021))
MENU = {
    "add_couriers_5": AddCouriers(count=5),
    "add_couriers_10": AddCouriers(count=10),
    "workers_4": SetDispatcherWorkers(workers=4),
    "workers_6": SetDispatcherWorkers(workers=6),
    "retry_backoff_0.2": SetRetryBackoff(minutes=0.2),
    "policy_eta_aware": SetDispatchPolicy(policy="eta_aware"),
    "admission_0.9": SetAdmissionRate(rate=0.9),
    "admission_0.8": SetAdmissionRate(rate=0.8),
}
AGENT_RUNS = {
    "playbook": "playbook_final_fix",
    "gpt-5-mini": "llm-gpt-5-mini_final_fix",
    "gpt-5.6-luna": "llm-gpt-5.6-luna_final_fix",
    "qwen-sft": "local-qwen3-1.7b-sft_final_g4",
    "qwen-base": "local-qwen3-1.7b_final_g4",
}


def _arm(world, t0, ivs, P):
    out = []
    for r in REPLICAS:
        w = world.fork_at(Branch(t0=t0, interventions=tuple(ivs), replica=r)).run()
        out.append(demand_cohort_metrics(w.log, P, t0, t0 + LAB_COHORT, t0 + LAB_FOLLOW_UP))
    return out


def _summary(ctrl, trt, cost):
    d_bad = [b["bad_rate"] - a["bad_rate"] for a, b in zip(ctrl, trt, strict=True)]
    # Registered unpaired contrast: control replica r vs treatment replica r+1 (the last
    # control is matched with the first treatment). Codex review G4/G5 #9.
    shifted = trt[1:] + trt[:1]
    d_unp = [b["bad_rate"] - a["bad_rate"] for a, b in zip(ctrl, shifted, strict=True)]
    m, ci = t_ci(d_bad)
    return {"diff_bad": m, "ci_bad": ci,
            "diff_time": statistics.fmean(b["penalized_time"] - a["penalized_time"]
                                          for a, b in zip(ctrl, trt, strict=True)),
            "diff_rejected": statistics.fmean(b["rejected"] / b["n"] - a["rejected"] / a["n"]
                                              for a, b in zip(ctrl, trt, strict=True)),
            "cost": cost,
            "var_paired": statistics.variance(d_bad), "var_unpaired": statistics.variance(d_unp),
            "all_zero": all(x == 0 for x in d_bad)}


MISSING = "missing"  # no bundle: not evaluated (different from a submitted no-op)


def _recommendations(dataset_id: str) -> dict[str, dict | str | None]:
    out: dict[str, dict | str | None] = {}
    for agent, run in AGENT_RUNS.items():
        f = ROOT / "runs" / "g3" / run / "bundles" / f"{dataset_id}.json"
        if not f.exists():
            out[agent] = MISSING
            continue
        rep = json.loads(f.read_text()).get("report") or {}
        out[agent] = rep.get("recommendation")
    return out


def feasible(iv) -> bool:
    """Registered constraints: cost <= 10 units; admission may reject at most 20%."""
    if isinstance(iv, SetAdmissionRate) and iv.rate < 0.8:
        return False
    return intervention_cost(iv) <= 10.0


def study_incident(job):
    level, i = job
    from pydantic import TypeAdapter

    from deliverytwin.simulation.interventions import Intervention
    try:
        inst = generate_instance(level, i, master_seed=FINAL)
    except RuntimeError as e:  # reported, never replaced (PREREG analysis rules)
        return {"level": level, "index": i, "failed": str(e)}
    t0 = inst.private.alert["t"]
    world = _world_for_lab(inst, t0)
    P = inst.world_config.promised_delivery_minutes
    ctrl = _arm(world, t0, (NoOp(),), P)
    arms = {name: _summary(ctrl, _arm(world, t0, (iv,), P), intervention_cost(iv))
            for name, iv in MENU.items()}
    arms["placebo"] = _summary(ctrl, _arm(world, t0, (Placebo(),), P), 0.0)
    recs = {}
    for agent, rec in _recommendations(inst.public.dataset_id).items():
        if rec == MISSING:
            recs[agent] = {"status": MISSING}
            continue
        if rec is None:
            recs[agent] = {"status": "ok", "kind": None, "diff_bad": 0.0, "feasible": True,
                           "in_menu": True}
            continue
        iv = TypeAdapter(Intervention).validate_python(rec)
        s = _summary(ctrl, _arm(world, t0, (iv,), P), intervention_cost(iv))
        recs[agent] = {"status": "ok", "kind": iv.kind, "args": rec, "diff_bad": s["diff_bad"],
                       "cost": s["cost"], "feasible": feasible(iv),
                       "in_menu": any(iv == m for m in MENU.values())}
    remedy = REMEDY.get(inst.private.family)
    return {"level": level, "index": i, "dataset_id": inst.public.dataset_id,
            "family": inst.private.family, "control_bad": statistics.fmean(
                m["bad_rate"] for m in ctrl),
            "arms": arms, "agent_recommendations": recs,
            "remedy": next((n for n, iv in MENU.items() if iv == remedy), None)}


def pareto(arms: dict) -> list[str]:
    pts = {n: (a["diff_bad"], a["cost"]) for n, a in arms.items() if n != "placebo"}
    pts["noop"] = (0.0, 0.0)
    return sorted(n for n, (b, c) in pts.items()
                  if not any((b2 <= b and c2 <= c) and (b2 < b or c2 < c)
                             for n2, (b2, c2) in pts.items() if n2 != n))


def aggregate(all_rows: list[dict]) -> dict:
    rows = [r for r in all_rows if "failed" not in r]
    out: dict = {"n_incidents": len(rows), "replicas": len(REPLICAS), "menu": list(MENU),
                 "generation_failures": [r for r in all_rows if "failed" in r],
                 "complete": len(rows) == len(all_rows)}
    if not rows:
        return out
    fams = sorted({r["family"] for r in rows})
    eff = {}
    for fam in fams:
        rs = [r for r in rows if r["family"] == fam]
        eff[fam] = {"n": len(rs)}
        for name in [*MENU, "placebo"]:
            m, ci = t_ci([r["arms"][name]["diff_bad"] for r in rs]) if len(rs) > 1 else (
                rs[0]["arms"][name]["diff_bad"], (float("nan"),) * 2)
            eff[fam][name] = {"diff_bad": round(m, 4), "ci": [round(x, 4) for x in ci],
                              "diff_rejected": round(statistics.fmean(
                                  r["arms"][name]["diff_rejected"] for r in rs), 4)}
    out["effects_by_family"] = eff
    # best feasible action and regrets (lower diff_bad is better; NoOp = 0 is feasible)
    # Regret = recommendation effect minus the best effect among the menu AND the
    # recommendation itself (if feasible), so an out-of-menu action is never compared with
    # an oracle that could not choose it (Codex review G4/G5 #7). Infeasible
    # recommendations are counted separately, not scored as regret.
    # Two definitions (Codex report review #2):
    # - shortfall_vs_menu: clipped shortfall against menu + the agent's own recommendation
    #   (a different reference per agent; kept for continuity with the first draft);
    # - regret_vs_common_oracle: one reference per incident, the best of the menu, no-op and
    #   EVERY feasible recommendation any agent made there (same control and replicas).
    regrets: dict[str, list[float]] = {"remedy": []}
    common: dict[str, list[float]] = {"remedy": []}
    infeasible: dict[str, int] = {}
    levels_covered: dict[str, dict[str, int]] = {}
    best_by_family: dict[str, dict[str, int]] = {}
    for r in rows:
        cand = {n: a["diff_bad"] for n, a in r["arms"].items() if n != "placebo"}
        cand["noop"] = 0.0
        best = min(cand, key=lambda n: (cand[n], r["arms"].get(n, {"cost": 0})["cost"]))
        r["best"], r["pareto"] = best, pareto(r["arms"])
        best_by_family.setdefault(r["family"], {}).setdefault(best, 0)
        best_by_family[r["family"]][best] += 1
        rem = cand[r["remedy"]] if r["remedy"] else 0.0
        regrets["remedy"].append(rem - cand[best])
        oracle = min([cand[best], *(a["diff_bad"] for a in r["agent_recommendations"].values()
                                    if a.get("status") == "ok" and a.get("feasible"))])
        common["remedy"].append(rem - oracle)
        for agent, rec in r["agent_recommendations"].items():
            if rec["status"] == MISSING:
                continue
            cov = levels_covered.setdefault(agent, {})
            cov[r["level"]] = cov.get(r["level"], 0) + 1
            if not rec["feasible"]:
                infeasible[agent] = infeasible.get(agent, 0) + 1
                continue
            regrets.setdefault(agent, []).append(
                rec["diff_bad"] - min(cand[best], rec["diff_bad"]))
            common.setdefault(agent, []).append(rec["diff_bad"] - oracle)
    out["best_action_counts_by_family"] = best_by_family
    def stats(d):
        return {k: {"n": len(v), "mean": round(statistics.fmean(v), 4),
                    "median": round(statistics.median(v), 4),
                    "share_within_0.02": round(sum(x <= 0.02 for x in v) / len(v), 3)}
                for k, v in d.items() if v}
    out["regret_vs_best"] = stats(regrets)  # = shortfall vs menu + own recommendation
    out["regret_vs_common_oracle"] = stats(common)
    expected = {lv: sum(r["level"] == lv for r in rows) for lv in ("L0", "L1", "L2")}
    out["agent_coverage"] = {a: {"by_level": c, "complete": c == expected,
                                 "infeasible_recommendations": infeasible.get(a, 0)}
                             for a, c in levels_covered.items()}
    # H4/H7: paired vs unpaired variance of the bad-rate difference, per action
    vr = {}
    for name in MENU:
        ratios = sorted(r["arms"][name]["var_paired"] / r["arms"][name]["var_unpaired"]
                        for r in rows if r["arms"][name]["var_unpaired"] > 0)
        vr[name] = {"n": len(ratios), "median": round(statistics.median(ratios), 4),
                    "q25": round(ratios[len(ratios) // 4], 4),
                    "q75": round(ratios[(3 * len(ratios)) // 4], 4),
                    "share_below_1": round(sum(x < 1 for x in ratios) / len(ratios), 3)}
    out["variance_ratio_paired_over_unpaired"] = vr
    out["placebo_all_exactly_zero"] = all(r["arms"]["placebo"]["all_zero"] for r in rows)
    out["mean_pareto_size"] = round(statistics.fmean(len(r["pareto"]) for r in rows), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--aggregate-only", action="store_true",
                    help="recompute the aggregate from runs/g5/interventions_rows.json")
    a = ap.parse_args()
    if a.aggregate_only:
        rows = json.loads((ROOT / "runs" / "g5" / "interventions_rows.json").read_text())
        rep = aggregate(rows)
        (ROOT / "docs" / "reports" / "G5_INTERVENTIONS.json").write_text(json.dumps(rep, indent=2))
        print(json.dumps(rep["regret_vs_common_oracle"], indent=1))
        return
    jobs = [(lv, i) for lv in ("L0", "L1", "L2") for i in range(a.n)]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(study_incident, jobs))
    out_dir = ROOT / "runs" / "g5"
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = aggregate(rows)
    (out_dir / "interventions_rows.json").write_text(json.dumps(rows, indent=1, default=str))
    (ROOT / "docs" / "reports" / "G5_INTERVENTIONS.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: rep[k] for k in ("regret_vs_best", "variance_ratio_paired_over_unpaired",
                                          "placebo_all_exactly_zero", "mean_pareto_size")},
                     indent=1))


if __name__ == "__main__":
    main()

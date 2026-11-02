"""G1 measurements: replay cost and variance reduction from event-keyed pairing.

Usage: uv run python scripts/g1_report.py [--seeds N] [--out docs/reports/G1_REPORT_DATA.json]

For each intervention B vs control A (NoOp) at t0, KPI differences over the post-t0
window are computed three ways:
  paired-event-keyed : same seed and replica, event-keyed RNG (ADR-0002)
  paired-stateful    : same seed and replica, but draws depend on draw order
                       (emulates a stateful PRNG with a shared seed)
  independent        : different seeds for A and B
and the variance of the differences is compared.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
from contextlib import contextmanager

import deliverytwin.core.rng as rng_mod
from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    NoOp,
    SetAdmissionRate,
    SetDispatcherWorkers,
    SetDispatchPolicy,
)
from deliverytwin.simulation.kpis import cohort_bad_rate, cohort_penalized_time
from deliverytwin.simulation.world import World
from deliverytwin.world.config import WorldConfig

# Closed cohort with complete follow-up (Codex review G1, finding 8): orders accepted in
# [T0, T0 + 60), evaluated at the horizon (>= cohort end + promise).
KPIS = ("bad_rate", "penalized_time")
T0 = 90.0
CFG = WorldConfig(horizon_minutes=240)
INTERVENTIONS = {
    "add_couriers_5": AddCouriers(count=5),
    "admission_0.8": SetAdmissionRate(rate=0.8),
    "policy_eta_aware": SetDispatchPolicy(policy="eta_aware"),
    "dispatcher_workers_4": SetDispatcherWorkers(workers=4),
}


@contextmanager
def stateful_rng():
    original = rng_mod.EventRng.uniform

    def uniform(self, *key):
        # One draw counter per generator; the seed is part of the key because the pre- and
        # post-fork generators share the world's key registry.
        self._n = getattr(self, "_n", 0) + 1
        return original(self, "__counter__", self.seed % (1 << 62), self._n)

    rng_mod.EventRng.uniform = uniform
    try:
        yield
    finally:
        rng_mod.EventRng.uniform = original


def kpis(seed: int, iv, replica: int) -> dict[str, float]:
    w = World(CFG, seed=seed, branch=Branch(t0=T0, interventions=(iv,), replica=replica)).run()
    P, end = CFG.promised_delivery_minutes, CFG.horizon_minutes
    bad, _ = cohort_bad_rate(w.log, P, T0, T0 + 60, end)
    pen, _ = cohort_penalized_time(w.log, P, T0, T0 + 60, end)
    return {"bad_rate": bad, "penalized_time": pen}


def diffs(pairs) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {k: [] for k in KPIS}
    for ka, kb in pairs:
        for k in KPIS:
            if not (math.isnan(ka[k]) or math.isnan(kb[k])):
                out[k].append(kb[k] - ka[k])
    return out


def summarize(xs: list[float]) -> dict[str, float]:
    n = len(xs)
    m = statistics.fmean(xs)
    sd = statistics.stdev(xs) if n > 1 else math.nan
    half = 1.96 * sd / math.sqrt(n) if n > 1 else math.nan
    return {"n": n, "mean": m, "sd": sd, "ci95_low": m - half, "ci95_high": m + half}


def variance_study(n_seeds: int) -> dict:
    results = {}
    seeds = list(range(1, n_seeds + 1))
    for name, iv in INTERVENTIONS.items():
        paired = [(kpis(s, NoOp(), 1), kpis(s, iv, 1)) for s in seeds]
        independent = [(kpis(s, NoOp(), 1), kpis(s + 10_000, iv, 1)) for s in seeds]
        with stateful_rng():
            paired_stateful = [(kpis(s, NoOp(), 1), kpis(s, iv, 1)) for s in seeds]
        d_p, d_i, d_s = diffs(paired), diffs(independent), diffs(paired_stateful)
        per_kpi = {}
        for k in KPIS:
            sp, si, ss = summarize(d_p[k]), summarize(d_i[k]), summarize(d_s[k])
            per_kpi[k] = {
                "paired_event_keyed": sp,
                "paired_stateful": ss,
                "independent": si,
                "var_ratio_event_keyed_vs_independent": (sp["sd"] / si["sd"]) ** 2,
                "var_ratio_stateful_vs_independent": (ss["sd"] / si["sd"]) ** 2,
            }
        results[name] = per_kpi
    return results


def replay_cost() -> dict:
    out = {}
    for horizon in (240, 480, 960):
        cfg = WorldConfig(horizon_minutes=horizon)
        times, events = [], 0
        for s in range(1, 6):
            t = time.perf_counter()
            w = World(cfg, seed=s).run()
            times.append(time.perf_counter() - t)
            events = len(w.log)
        out[str(horizon)] = {"median_seconds": statistics.median(times), "events_last_run": events}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--out", default="docs/reports/G1_REPORT_DATA.json")
    args = ap.parse_args()
    data = {
        "manifest": {
            "rng": rng_mod.RNG_IMPLEMENTATION,
            "python": platform.python_version(),
            "t0": T0,
            "horizon": CFG.horizon_minutes,
            "seeds": args.seeds,
            "replica": 1,
        },
        "replay_cost": replay_cost(),
        "variance": variance_study(args.seeds),
    }
    with open(args.out, "w") as f:
        json.dump(data, f, indent=2)
    print(json.dumps(data["replay_cost"], indent=2))
    for name, per in data["variance"].items():
        for k, v in per.items():
            p = v["paired_event_keyed"]
            print(f"{name:22s} {k:18s} effect={p['mean']:+.3f} [{p['ci95_low']:+.3f},{p['ci95_high']:+.3f}] "
                  f"var_ratio keyed={v['var_ratio_event_keyed_vs_independent']:.3f} "
                  f"stateful={v['var_ratio_stateful_vs_independent']:.3f}")


if __name__ == "__main__":
    main()

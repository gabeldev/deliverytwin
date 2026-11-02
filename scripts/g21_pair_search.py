"""G2.1: search for an observationally equivalent, interventionally separable fault pair.

For each candidate pair (with severity ranges matched by effect size):
  1. generate L2-style instances (customer profile, ambient noise, all generator gates);
  2. distinguishability probe: cross-validated logistic regression and gradient boosting
     on customer-visible features; report accuracy with a Wilson 95% CI;
  3. interventional separability: in the lab (paired fork after detection), does the
     candidate discriminating intervention help one family and not the other?
Acceptance (ADR-0005 amendment): probe CI upper bound <= 0.60 AND a discriminating
intervention exists.

Usage: uv run python scripts/g21_pair_search.py [--n 80] [--out docs/reports/G2_1_PAIR_SEARCH.json]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from deliverytwin.benchmark.generator import generate_instance
from deliverytwin.diagnostics.features import customer_features
from deliverytwin.faults.spec import (
    CourierScarcity,
    DispatchErrorSurge,
    DispatcherSaturation,
    DispatchLatency,
    NoiseSpec,
)
from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    NoOp,
    SetDispatcherWorkers,
    SetRetryBackoff,
)
from deliverytwin.simulation.kpis import cohort_bad_rate
from deliverytwin.simulation.world import World

NOISE = NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)
FAULT_CLS = {"courier_scarcity": CourierScarcity, "dispatcher_saturation": DispatcherSaturation,
             "dispatch_error_surge": DispatchErrorSurge, "dispatch_latency": DispatchLatency}

CANDIDATES = {
    "C_errors_vs_latency_constructed": {
        "families": ("dispatch_error_surge", "dispatch_latency"),
        "severity": {"dispatch_error_surge": (0.95, 0.98), "dispatch_latency": (0.95, 0.98)},
        "discriminating": SetRetryBackoff(minutes=0.2),
    },
    "A_saturation_vs_errors": {
        "families": ("dispatcher_saturation", "dispatch_error_surge"),
        "severity": {"dispatcher_saturation": (7.5, 9.0), "dispatch_error_surge": (0.88, 0.97)},
        "discriminating": SetDispatcherWorkers(workers=6),
    },
    "B_scarcity_vs_saturation_matched": {
        "families": ("courier_scarcity", "dispatcher_saturation"),
        "severity": {"courier_scarcity": (0.45, 0.70), "dispatcher_saturation": (7.5, 9.0)},
        "discriminating": SetDispatcherWorkers(workers=6),
    },
}


MIN_N = 300
MAX_UPPER_CI = 0.60


def acceptance_status(n: int, upper_ci: float) -> str:
    """ADR-0005 amendment 2: accept only with n >= 300 AND upper CI <= 0.60.
    Codex review G2.1, finding 6."""
    if upper_ci > MAX_UPPER_CI:
        return "rejected"
    if n < MIN_N:
        return "insufficient_n"
    return "accepted"


def wilson(k, n):
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def probe(rows):
    names = None
    X, y = [], []
    for r in rows:
        f = customer_features(r.public, r.private.alert["t"])
        names = sorted(f)
        X.append([f[k] for k in names])
        y.append(int(r.private.family == rows[0].private.family))
    X, y = np.array(X), np.array(y)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    out = {"n": len(y), "chance": round(float(max(y.mean(), 1 - y.mean())), 3)}
    best = 0.0
    for name, model in (("logreg", make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000))),
                        ("gboost", GradientBoostingClassifier(random_state=0))):
        pred = cross_val_predict(model, X, y, cv=cv)
        k = int((pred == y).sum())
        out[name] = {"acc": round(k / len(y), 3), "wilson95": wilson(k, len(y))}
        best = max(best, k / len(y))
        if name == "gboost":
            imp = model.fit(X, y).feature_importances_
            out["top_features"] = [(names[i], round(float(imp[i]), 3)) for i in np.argsort(-imp)[:4]]
    out["best_upper_ci"] = max(out["logreg"]["wilson95"][1], out["gboost"]["wilson95"][1])
    return out


def lab_effect(rows, iv, per_family=20):
    """Paired lab effect of an intervention applied at the alert, per family (mode A)."""
    res: dict[str, list[float]] = {}
    taken: dict[str, int] = {}
    chosen = []
    for r in rows:
        if taken.get(r.private.family, 0) < per_family:
            taken[r.private.family] = taken.get(r.private.family, 0) + 1
            chosen.append(r)
    for r in chosen:
        p = r.private
        fault = FAULT_CLS[p.family](**{k: v for k, v in p.fault.items() if k != "family"})
        t0 = p.alert["t"]
        # The lab needs its own horizon beyond the alert; extending the horizon only adds
        # future (event-keyed draws are unchanged before the original horizon).
        cfg = r.world_config.model_copy(update={"horizon_minutes": int(t0) + 150})
        base = World(cfg, p.world_seed, faults=(fault,), noise=NOISE)
        ctrl = base.fork_at(Branch(t0=t0, interventions=(NoOp(),), replica=1)).run()
        trt = base.fork_at(Branch(t0=t0, interventions=(iv,), replica=1)).run()
        P = r.world_config.promised_delivery_minutes
        # Closed cohort: orders accepted in [t0, t0 + 90), all determinable at t0 + 150.
        a, _ = cohort_bad_rate(ctrl.log, P, t0, t0 + 90, t0 + 150)
        b, _ = cohort_bad_rate(trt.log, P, t0, t0 + 90, t0 + 150)
        res.setdefault(p.family, []).append(b - a)
    out = {}
    for fam, v in res.items():
        ok = [x for x in v if not math.isnan(x)]
        out[fam] = {"bad_rate_delta_mean": round(statistics.fmean(ok), 4) if ok else None,
                    "sd": round(statistics.stdev(ok), 4) if len(ok) > 1 else None,
                    "n": len(ok), "nan_dropped": len(v) - len(ok)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--out", default="docs/reports/G2_1_PAIR_SEARCH.json")
    ap.add_argument("--only", default="", help="comma-separated candidate names")
    a = ap.parse_args()
    results = {}
    for name, c in CANDIDATES.items():
        if a.only and name not in a.only.split(","):
            continue
        spec = {"name": "L2c", "families": c["families"], "profile": "customer", "noise": NOISE,
                "severity": c["severity"]}
        rows = [generate_instance(spec, 50_000 + i) for i in range(a.n)]
        res = {"severity": c["severity"], "probe": probe(rows),
               "impact_global_time": {
                   fam: round(statistics.fmean(r.private.impact["global_time"] for r in rows
                                               if r.private.family == fam), 2)
                   for fam in c["families"]},
               "detect_delay_median": statistics.median(r.private.alert["t"] - r.private.fault["onset"]
                                                        for r in rows),
               "lab": {"discriminating": c["discriminating"].kind,
                       "effects": lab_effect(rows, c["discriminating"])},
               "lab_add_workers": lab_effect(rows, SetDispatcherWorkers(workers=6)),
               "lab_add_couriers": lab_effect(rows, AddCouriers(count=10))}
        res["observational_status"] = acceptance_status(res["probe"]["n"],
                                                        res["probe"]["best_upper_ci"])
        res["accepted_observational"] = res["observational_status"] == "accepted"
        results[name] = res
        print(name, json.dumps(res, indent=1))
    with open(a.out, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

"""G2 measurements: fault effects, detection, benchmark levels, baselines,
distinguishability probe, leakage checks and slot-vs-dyad key sensitivity.

Usage: uv run python scripts/g2_report.py [--n 60] [--out docs/reports/G2_REPORT_DATA.json]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from deliverytwin.benchmark.generator import (
    FORBIDDEN_TERMS,
    LEVELS,
    generate_instance,
)
from deliverytwin.core.rng import EventRng, derive_seed
from deliverytwin.diagnostics.detector import CALIBRATED, detect
from deliverytwin.diagnostics.features import customer_features, full_features
from deliverytwin.diagnostics.rules import diagnose_rules
from deliverytwin.faults.spec import (
    CourierScarcity,
    DispatchErrorSurge,
    DispatcherSaturation,
    DispatchLatency,
    RestaurantBottleneck,
)
from deliverytwin.simulation.interventions import AddCouriers, Branch, NoOp, SetDispatchPolicy
from deliverytwin.simulation.kpis import cohort_bad_rate, cohort_penalized_time
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator, build_telemetry, scan_for_leaks
from deliverytwin.world.config import WorldConfig

CFG = WorldConfig(horizon_minutes=360)
FAULT_CLS = {"courier_scarcity": CourierScarcity, "dispatcher_saturation": DispatcherSaturation,
             "restaurant_bottleneck": RestaurantBottleneck,
             "dispatch_error_surge": DispatchErrorSurge, "dispatch_latency": DispatchLatency}


def ci(xs):
    xs = [x for x in xs if not math.isnan(x)]
    m = statistics.fmean(xs)
    h = 1.96 * statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else math.nan
    return {"mean": round(m, 4), "ci95": [round(m - h, 4), round(m + h, 4)], "n": len(xs)}


def wilson(k, n):
    if n == 0:
        return [math.nan, math.nan]
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def fault_effects(n):
    faults = {
        "courier_scarcity": CourierScarcity(onset=195, offline_fraction=0.57),
        "dispatcher_saturation": DispatcherSaturation(onset=195, service_multiplier=8.25),
        "restaurant_bottleneck": RestaurantBottleneck(onset=195, restaurant_index=0,
                                                      prep_multiplier=4.5),
        "dispatch_error_surge": DispatchErrorSurge(onset=195, error_prob=0.965),
        "dispatch_latency": DispatchLatency(onset=195, hang_prob=0.965),
    }
    out = {}
    for name, f in faults.items():
        # Closed cohort with complete follow-up (same rule as the impact gate and the lab).
        d = {"bad_rate": [], "penalized_time": []}
        P = CFG.promised_delivery_minutes
        for s in range(1, n + 1):
            a_log = World(CFG, s).run().log
            b_log = World(CFG, s, faults=(f,)).run().log
            for metric, fn in (("bad_rate", cohort_bad_rate), ("penalized_time", cohort_penalized_time)):
                va, _ = fn(a_log, P, 195, 255, 360)
                vb, _ = fn(b_log, P, 195, 255, 360)
                d[metric].append(vb - va)
        out[name] = {metric: ci(values) for metric, values in d.items()}
    return out


def detection_power(n):
    from deliverytwin.benchmark.generator import _sample_fault
    from deliverytwin.world.city import build_city
    out = {}
    for fam in FAULT_CLS:
        delays, outcome = [], Counter()
        for i in range(n):
            meta = EventRng(derive_seed(7, "power", fam, i), strict=False)
            seed = derive_seed(7, "w", fam, i) >> 64
            city = build_city(CFG, EventRng(seed, strict=False))
            f = _sample_fault(meta, fam, CFG, "f", popularity=[r.popularity for r in city.restaurants])
            w = World(CFG, seed, faults=(f,)).run()
            a = detect(build_telemetry(w, dataset_id="x", profile="customer", observed_until=360,
                                       obfuscator=Obfuscator(1)))
            if a is None:
                outcome["not_detected"] += 1
            elif a.t < f.onset:
                outcome["before_onset"] += 1
            else:
                outcome["detected"] += 1
                delays.append(a.t - f.onset)
        k = outcome["detected"]
        out[fam] = {"outcomes": dict(outcome), "detection_rate": round(k / n, 3),
                    "wilson95": wilson(k, n),
                    "delay_median": statistics.median(delays) if delays else None,
                    "delay_iqr": [float(np.percentile(delays, 25)), float(np.percentile(delays, 75))]
                    if delays else None}
    return out


# Baselines are scored on an evaluation set generated with a master seed never used
# while developing the rules (which were tuned on development-seed instances); the
# majority floor is learned on the train split of the development set
# (Codex review G2, finding 5).
EVAL_MASTER_SEED = 909_090


def evaluate_levels(n):
    out, insts = {}, {}
    for level in ("L0", "L1", "L2"):
        dev = [generate_instance(level, i) for i in range(n)]
        rows = [generate_instance(level, i, master_seed=EVAL_MASTER_SEED) for i in range(n)]
        insts[level] = dev
        fams = LEVELS[level]["families"]
        train = [r for r in dev if r.private.split == "train"]
        majority = Counter(r.private.family for r in train).most_common(1)[0][0] if train else fams[0]
        rng = random.Random(0)
        res = Counter()
        unresolved_pair = 0
        for r in rows:
            p = r.private
            d = diagnose_rules(r.public, p.alert["t"])
            ok = d.cause == p.family and (p.family != "restaurant_bottleneck"
                                          or d.scope == p.restaurant_token)
            res["rules"] += ok
            res["rules_family"] += d.cause == p.family
            res["majority_family"] += majority == p.family
            res["random_family"] += rng.choice(fams) == p.family
            unresolved_pair += d.cause is None and p.family in d.unresolved_between
        leaks = sum(bool(scan_for_leaks(r.public.model_dump_json(),
                                        [*FORBIDDEN_TERMS, r.private.canary])) for r in rows)
        out[level] = {
            "n": n,
            "families": Counter(r.private.family for r in rows),
            "attempts_mean": round(statistics.fmean(r.private.attempts for r in rows), 2),
            "detect_delay_median": statistics.median(r.private.alert["t"] - r.private.fault["onset"]
                                                     for r in rows),
            "accuracy": {k: {"rate": round(v / n, 3), "wilson95": wilson(v, n)} for k, v in res.items()},
            "rules_unresolved_on_pair": {"rate": round(unresolved_pair / n, 3)},
            "leaks_found": leaks,
            "majority_family_train": majority,
            "evaluation_master_seed": EVAL_MASTER_SEED,
            "scored_on": "held-out evaluation set (fresh master seed)",
        }
    return out, insts


def probe(insts, n_extra):
    """Probe each pair: the L2 pair and the original (scarcity, saturation) pair from L1."""
    pairs = {"L2_pair": list(LEVELS["L2"]["families"]),
             "L1_scarcity_vs_saturation": ["courier_scarcity", "dispatcher_saturation"]}
    l2 = [r for r in insts["L2"]] + [generate_instance("L2", 10_000 + i) for i in range(n_extra)]
    l1 = [r for r in insts["L1"] if r.private.family in pairs["L1_scarcity_vs_saturation"]]
    l1 += [r for r in (generate_instance("L1", 10_000 + i) for i in range(n_extra))
           if r.private.family in pairs["L1_scarcity_vs_saturation"]]
    out = {}
    for pair_name, rows in (("L2_pair", l2), ("L1_scarcity_vs_saturation", l1)):
        out[pair_name] = _probe_rows(rows, pairs[pair_name])
    return out


def _probe_rows(rows, fams):
    out = {}
    for view in ("customer", "full"):
        X, y = [], []
        for r in rows:
            p = r.private
            fault = FAULT_CLS[p.family](**{k: v for k, v in p.fault.items() if k != "family"})
            noise = LEVELS[p.level]["noise"]
            w = World(r.world_config, p.world_seed, faults=(fault,), noise=noise).run()
            tel = build_telemetry(w, dataset_id="probe", profile=view, observed_until=p.alert["t"],
                                  obfuscator=Obfuscator(p.obfuscation_salt),
                                  gauge_noise_sigma=noise.gauge_noise_sigma, noise_seed=p.noise_seed)
            feats = (full_features if view == "full" else customer_features)(tel, p.alert["t"])
            X.append([feats[k] for k in sorted(feats)])
            y.append(int(p.family == fams[0]))
        X, y = np.array(X), np.array(y)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
        lr = cross_val_score(make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)), X, y, cv=cv)
        gb = cross_val_score(GradientBoostingClassifier(random_state=0), X, y, cv=cv)
        out[view] = {"n": len(y), "positives": int(y.sum()),
                     "logreg_acc": [round(float(lr.mean()), 3), round(float(lr.std()), 3)],
                     "gboost_acc": [round(float(gb.mean()), 3), round(float(gb.std()), 3)],
                     "chance": round(max(y.mean(), 1 - y.mean()), 3)}
    return out


def key_sensitivity(n):
    out = {}
    ivs = {"add_couriers_5": AddCouriers(count=5), "policy_eta_aware": SetDispatchPolicy(policy="eta_aware")}
    for mode in ("slot", "dyad"):
        cfg = WorldConfig(horizon_minutes=240, accept_key_mode=mode)
        res = {}
        for name, iv in ivs.items():
            paired, indep = [], []
            for s in range(1, n + 1):
                def k(seed, x, cfg=cfg):
                    w = World(cfg, seed, Branch(t0=90, interventions=(x,), replica=1)).run()
                    # Closed cohort, promise from the config (was a stale hard-coded 40).
                    pen, _ = cohort_penalized_time(w.log, cfg.promised_delivery_minutes,
                                                   90, 150, cfg.horizon_minutes)
                    return pen
                a, b = k(s, NoOp()), k(s, iv)
                paired.append(b - a)
                indep.append(k(s + 10_000, iv) - a)
            res[name] = {"effect": ci(paired), "var_ratio": round(statistics.variance(paired) /
                                                               statistics.variance(indep), 4)}
        out[mode] = res
    return out


def leak_mutation():
    """The scanner must catch a planted leak."""
    w = World(CFG, 1).run()
    tel = build_telemetry(w, dataset_id="x", profile="full", observed_until=200,
                          obfuscator=Obfuscator(9))
    clean = scan_for_leaks(tel.model_dump_json(), FORBIDDEN_TERMS)
    planted = scan_for_leaks(tel.model_dump_json().replace("telemetry/v1", "telemetry/v1 r003 courier_scarcity"),
                             FORBIDDEN_TERMS)
    return {"clean_payload_hits": clean, "planted_payload_hits": planted}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--out", default="docs/reports/G2_REPORT_DATA.json")
    a = ap.parse_args()
    data = {"world_config": json.loads(CFG.model_dump_json()),
            "detector": {"thr_global": CALIBRATED.thr_global, "thr_local": CALIBRATED.thr_local}}
    data["fault_effects"] = fault_effects(40)
    print("fault effects done")
    data["detection_power"] = detection_power(a.n)
    print("detection power done")
    data["levels"], insts = evaluate_levels(a.n)
    print("levels done")
    data["probe"] = probe(insts, n_extra=a.n)
    print("probe done")
    data["key_sensitivity"] = key_sensitivity(40)
    data["leak_mutation"] = leak_mutation()
    with open(a.out, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(json.dumps({k: data[k] for k in ("detection_power", "levels", "probe", "key_sensitivity",
                                           "leak_mutation")}, indent=1, default=str))


if __name__ == "__main__":
    main()

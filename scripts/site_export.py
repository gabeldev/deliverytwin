"""Export the public showcase data (site/public/data/) from the real simulator.

Everything the site shows about a scenario comes from here: the simulated world (map and
order trajectories), the agent-visible telemetry, recorded agent sessions, a grid of paired
counterfactual experiments and, separately, the hidden truth for the post-submission reveal.

Only the PUBLIC development seed (2026) is used, never the evaluation or final seeds, so the
showcase cannot leak a reserved benchmark (PRODUCT.md, ADR-0006).

Usage: uv run python scripts/site_export.py [--replicas 20] [--workers 6]
Recorded sessions are read from runs/g3/<agent>_dev_<tag>/bundles (see SESSION_RUNS).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from deliverytwin.agent.baselines import run_playbook_agent
from deliverytwin.agent.protocol import intervention_cost
from deliverytwin.agent.session import (
    LAB_COHORT,
    LAB_FOLLOW_UP,
    T95,
    InvestigationSession,
    _world_for_lab,
    instance_faults,
)
from deliverytwin.benchmark.evaluator import evaluate
from deliverytwin.benchmark.generator import LEVELS, generate_instance
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
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "public" / "data"
DEV_SEED = 2026
REPLICA_BASE = 3000  # showcase futures, disjoint from investigation (1-5), evaluator (1001+), G5 (2001+)
TWIN_DELTA = 0.25

# Featured scenarios: (level, index). Chosen because recorded API-LLM sessions exist for
# them on the public dev seed (runs/g3/llm-*_dev_dev2) and they cover every fault family.
SCENARIOS = [("L2", 2), ("L2", 0), ("L0", 2), ("L0", 3), ("L0", 1)]

# Lab menu offered to visitors: every value is valid for the simulator's own schema.
ARMS = [
    ("placebo", "placebo", Placebo()),
    ("add_couriers_5", "add_couriers", AddCouriers(count=5)),
    ("add_couriers_10", "add_couriers", AddCouriers(count=10)),
    ("add_couriers_20", "add_couriers", AddCouriers(count=20)),
    ("workers_3", "set_dispatcher_workers", SetDispatcherWorkers(workers=3)),
    ("workers_4", "set_dispatcher_workers", SetDispatcherWorkers(workers=4)),
    ("workers_6", "set_dispatcher_workers", SetDispatcherWorkers(workers=6)),
    ("workers_8", "set_dispatcher_workers", SetDispatcherWorkers(workers=8)),
    ("retry_backoff_0.5", "set_retry_backoff", SetRetryBackoff(minutes=0.5)),
    ("retry_backoff_0.2", "set_retry_backoff", SetRetryBackoff(minutes=0.2)),
    ("retry_backoff_0.05", "set_retry_backoff", SetRetryBackoff(minutes=0.05)),
    ("policy_eta_aware", "set_dispatch_policy", SetDispatchPolicy(policy="eta_aware")),
    ("admission_0.9", "set_admission_rate", SetAdmissionRate(rate=0.9)),
    ("admission_0.8", "set_admission_rate", SetAdmissionRate(rate=0.8)),
]

SESSION_RUNS = {
    "qwen-sft": ("local-qwen3-1.7b-sft_dev_site", "recorded", "Qwen3-1.7B + DeliveryTwin LoRA (G4)"),
    "qwen-base": ("local-qwen3-1.7b_dev_site", "recorded", "Qwen3-1.7B base, no fine-tuning"),
    "gpt-5-mini": ("llm-gpt-5-mini_dev_dev2", "recorded", "gpt-5-mini (OpenAI API, G3)"),
    "gpt-5.6-luna": ("llm-gpt-5.6-luna_dev_dev2", "recorded", "gpt-5.6-luna (OpenAI API, G3)"),
}

BIN = 5.0          # minutes per telemetry bin
LAB_BIN = 10.0     # minutes per counterfactual cohort bin


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _r(x, nd=4):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(x, nd)


# --- world view ------------------------------------------------------------------------
def world_view(inst, world: World) -> dict:
    """The simulator's view (NOT available to the agent): city and order trajectories."""
    ob = Obfuscator(inst.private.obfuscation_salt)
    cfg = world.cfg
    rest = {r.restaurant_id: r for r in world.city.restaurants}
    pos = dict(world.city.courier_homes)  # courier -> current position (replayed)
    orders: dict[str, dict] = {}
    courier_from: dict[str, tuple] = {}
    t_end = inst.public.observed_until
    # Trajectories run a little past the alert so trips in flight at the alert are drawn
    # correctly; the map itself only plays up to t_end.
    for e in world.log.events:
        if e["t"] > t_end + 60:
            break
        oid, ev = e.get("oid"), e["ev"]
        if ev == "order_created":
            if e["t"] > t_end:
                continue
            o = world.orders[oid] if hasattr(world, "orders") and oid in world.orders else None
            dest = list(o.destination) if o is not None else None
            r = rest[e["rid"]]
            orders[oid] = {"id": ob.token("o", oid), "r": ob.token("r", e["rid"]),
                           "z": e["zone"], "rx": r.position[0], "ry": r.position[1],
                           "dest": dest, "created": _r(e["t"], 2)}
        elif oid in orders:
            o = orders[oid]
            if ev == "order_rejected":
                o["rejected"] = _r(e["t"], 2)
            elif ev == "order_assigned":
                o["assigned"] = _r(e["t"], 2)
                o["c"] = e["cid"]
                courier_from[oid] = pos.get(e["cid"])
                o["from"] = list(courier_from[oid]) if courier_from[oid] else None
            elif ev == "courier_at_restaurant":
                o["at_rest"] = _r(e["t"], 2)
                pos[e["cid"]] = (o["rx"], o["ry"])
            elif ev == "order_ready":
                o["ready"] = _r(e["t"], 2)
            elif ev == "order_picked_up":
                o["picked"] = _r(e["t"], 2)
            elif ev == "order_delivered":
                o["delivered"] = _r(e["t"], 2)
                if o.get("dest"):
                    pos[e["cid"]] = tuple(o["dest"])
            elif ev == "order_cancelled":
                o["cancelled"] = _r(e["t"], 2)
    return {"label": "Simulator view: the agent never sees this",
            "grid": cfg.grid_size, "zones": cfg.n_zones, "t_end": t_end,
            "zone_tokens": [ob.token("z", f"zone{z}") for z in range(cfg.n_zones)],
            "restaurants": [{"token": ob.token("r", r.restaurant_id), "x": r.position[0],
                             "y": r.position[1], "zone": r.zone} for r in world.city.restaurants],
            "couriers": len(world.city.courier_homes),
            "orders": list(orders.values())}


# --- agent-visible telemetry -------------------------------------------------------------
def telemetry_view(inst) -> dict:
    tel = inst.public
    P = tel.promised_delivery_minutes
    T = tel.observed_until
    nb = math.ceil(T / BIN)
    created = [0] * nb
    bad = [0] * nb
    resolved = [0] * nb
    by_zone: dict[str, list[list[int]]] = {}
    for o in tel.orders:
        b = min(int(o.created // BIN), nb - 1)
        created[b] += 1
        z = by_zone.setdefault(o.zone, [[0] * nb, [0] * nb])
        z[0][b] += 1
        # Outcome as known at observation time: late, cancelled or rejected = bad; still
        # open orders past their promise also count as late (observable to the customer).
        if o.delivered is not None:
            is_bad, known = (o.delivered - o.created) > P, True
        elif o.cancelled is not None or not o.accepted:
            is_bad, known = True, True
        else:
            is_bad, known = (T - o.created) > P, (T - o.created) > P
        if known:
            resolved[b] += 1
            bad[b] += is_bad
            z[1][b] += is_bad
    gauges: dict[str, list] = {}
    for g in tel.gauges:
        key = g.metric if g.entity is None else f"{g.metric}:{g.entity}"
        gauges.setdefault(key, []).append([_r(g.t, 1), _r(g.value, 3)])
    # aggregate kitchen_load per entity into a mean series for compactness
    kl = [k for k in gauges if k.startswith("kitchen_load:")]
    if kl:
        ts: dict[float, list[float]] = {}
        for k in kl:
            for t, v in gauges[k]:
                ts.setdefault(t, []).append(v)
        gauges["kitchen_load_mean"] = [[t, _r(statistics.fmean(v), 3)] for t, v in sorted(ts.items())]
        gauges["kitchen_load_max"] = [[t, _r(max(v), 3)] for t, v in sorted(ts.items())]
        for k in kl:
            del gauges[k]
    return {"label": "Agent-visible telemetry (observed)", "profile": tel.profile,
            "bin_minutes": BIN, "promise": P, "observed_until": T,
            "t": [_r(i * BIN, 1) for i in range(nb)], "created": created,
            "resolved": resolved, "bad": bad,
            "zones": {z: {"created": v[0], "bad": v[1]} for z, v in sorted(by_zone.items())},
            "gauges": gauges}


# --- recorded sessions ---------------------------------------------------------------------
def _steps(transcript: list[dict]) -> list[dict]:
    return [{"op": s["op"], "args": s.get("args"), "response": s.get("response"),
             "ok": s.get("ok", True)} for s in transcript]


def _result(ev: dict) -> dict:
    keys = ("cause", "scope", "exact", "family_correct", "abstained", "path_f1", "confidence",
            "recommendation", "recommendation_diff_bad", "unresolved_between")
    out = {k: ev.get(k) for k in keys}
    out["used"] = ev.get("used")
    return out


def sessions(inst) -> dict:
    out = {}
    s = InvestigationSession(inst)
    run_playbook_agent(s)
    b = s.bundle({"name": "playbook"})
    out["playbook"] = {"kind": "deterministic",
                       "label": "Knowledge-based playbook (deterministic, re-run at export)",
                       "steps": _steps(b["transcript"]), "report": b.get("report"),
                       "result": _result(evaluate(b, inst))}
    for name, (run, kind, label) in SESSION_RUNS.items():
        f = ROOT / "runs" / "g3" / run / "bundles" / f"{inst.public.dataset_id}.json"
        if not f.exists():
            # Recorded LLM sessions are not part of the public repository; say so instead of dropping them silently.
            print(f"warning: no recorded session '{name}' for {inst.public.dataset_id} ({f.parent} missing); skipped",
                  file=sys.stderr)
            continue
        b = json.loads(f.read_text())
        out[name] = {"kind": kind, "label": label, "run": run, "steps": _steps(b["transcript"]),
                     "report": b.get("report"), "meta": {k: b.get("agent", {}).get(k) for k in
                                                         ("model", "turns", "tool_errors",
                                                          "forced_submit")},
                     "result": _result(evaluate(b, inst))}
    return out


# --- counterfactual lab --------------------------------------------------------------------
def _binned(log, P, t0, now):
    nb = int(LAB_COHORT // LAB_BIN)
    n, bad = [0] * nb, [0] * nb
    created, done = {}, {}
    for e in log.events:
        if e["t"] > now:
            break
        oid = e.get("oid")
        if e["ev"] == "order_created" and t0 <= e["t"] < t0 + LAB_COHORT:
            created[oid] = e["t"]
        elif oid in created and e["ev"] == "order_delivered":
            done[oid] = e["t"]
    for oid, t in created.items():
        b = min(int((t - t0) // LAB_BIN), nb - 1)
        n[b] += 1
        bad[b] += (oid not in done) or (done[oid] - t > P)
    return n, bad


def lab(inst, replicas: int, twin_delta: float | None) -> dict:
    t0 = inst.private.alert["t"]
    base = _world_for_lab(inst, t0, twin_delta)
    P = inst.world_config.promised_delivery_minutes
    hi, now = t0 + LAB_COHORT, t0 + LAB_FOLLOW_UP
    ids = list(range(REPLICA_BASE + 1, REPLICA_BASE + replicas + 1))
    ctrl, ctrl_bins = [], []
    trt = {k: [] for k, _, _ in ARMS}
    trt_bins = {k: [] for k, _, _ in ARMS}
    for r in ids:
        c = base.fork_at(Branch(t0=t0, interventions=(NoOp(),), replica=r)).run()
        ctrl.append(demand_cohort_metrics(c.log, P, t0, hi, now))
        ctrl_bins.append(_binned(c.log, P, t0, now))
        for key, _, iv in ARMS:
            w = base.fork_at(Branch(t0=t0, interventions=(iv,), replica=r)).run()
            trt[key].append(demand_cohort_metrics(w.log, P, t0, hi, now))
            trt_bins[key].append(_binned(w.log, P, t0, now))

    def series(bins):
        nb = len(bins[0][0])
        return [_r(statistics.fmean(b[1][i] / b[0][i] for b in bins if b[0][i]), 4)
                if any(b[0][i] for b in bins) else None for i in range(nb)]

    def ci(d):
        m = statistics.fmean(d)
        h = T95.get(len(d) - 1, 1.96) * statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else math.nan
        return m, m - h, m + h

    arms = []
    for key, kind, iv in ARMS:
        d_bad = [b["bad_rate"] - a["bad_rate"] for a, b in zip(ctrl, trt[key], strict=True)]
        d_time = [b["penalized_time"] - a["penalized_time"] for a, b in zip(ctrl, trt[key], strict=True)]
        m, lo, hi_ = ci(d_bad)
        mt, lot, hit = ci(d_time)
        rej = statistics.fmean(b["rejected"] / b["n"] for b in trt[key])
        arms.append({"key": key, "kind": kind, "params": iv.model_dump(),
                     "cost": _r(intervention_cost(iv), 2) if kind != "placebo" else 0.0,
                     "diff_bad": _r(m), "ci_bad": [_r(lo), _r(hi_)],
                     "diff_time": _r(mt, 2), "ci_time": [_r(lot, 2), _r(hit, 2)],
                     "treatment_bad": _r(statistics.fmean(b["bad_rate"] for b in trt[key])),
                     "treatment_rejected": _r(rej),
                     "replica_diffs": [_r(x) for x in d_bad],
                     "all_zero": all(x == 0 for x in d_bad),
                     "series_bad": series(trt_bins[key])})
    return {"mode": "A" if twin_delta is None else "B", "twin_delta": twin_delta,
            "t0": t0, "cohort_minutes": LAB_COHORT, "follow_up_minutes": LAB_FOLLOW_UP,
            "replicas": replicas, "replica_ids": [ids[0], ids[-1]],
            "control_bad": _r(statistics.fmean(a["bad_rate"] for a in ctrl)),
            "control_time": _r(statistics.fmean(a["penalized_time"] for a in ctrl), 2),
            "control_n": _r(statistics.fmean(a["n"] for a in ctrl), 1),
            "control_series_bad": series(ctrl_bins), "bin_minutes": LAB_BIN, "arms": arms}


# --- reveal --------------------------------------------------------------------------------
def reveal(inst) -> dict:
    p = inst.private
    return {"label": "Hidden truth: evaluator only, shown after the investigation is submitted",
            "family": p.family, "fault": p.fault, "extra_faults": list(p.extra_faults),
            "restaurant_token": p.restaurant_token, "causal_dag": [list(e) for e in p.causal_dag],
            "impact": {k: _r(v) for k, v in p.impact.items()},
            "identifiability": p.identifiability_assumed}


def export(job) -> dict:
    (level, index), replicas = job
    inst = generate_instance(level, index, master_seed=DEV_SEED)
    world = World(inst.world_config, inst.private.world_seed, faults=instance_faults(inst),
                  noise=inst.noise).run()
    s = InvestigationSession(inst)
    data = {"id": f"{level.lower()}-{index}", "level": level, "index": index, "seed": DEV_SEED,
            "dataset_id": inst.public.dataset_id,
            "level_spec": {"families": list(LEVELS[level]["families"]),
                           "profile": LEVELS[level]["profile"]},
            "observe": s.observe(), "alert": {k: inst.private.alert[k] for k in
                                              ("t", "series", "metric", "score")},
            "world": world_view(inst, world), "telemetry": telemetry_view(inst),
            "sessions": sessions(inst),
            "lab": {"A": lab(inst, replicas, None), "B": lab(inst, replicas, TWIN_DELTA)},
            "reveal": reveal(inst)}
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicas", type=int, default=20)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--commit", help="commit label to record (use the PUBLIC snapshot commit that regenerates the data; "
                    "see docs/PROVENANCE.md). Defaults to the current git HEAD.")
    a = ap.parse_args()
    if a.replicas < 2 or a.replicas > 20:
        ap.error("--replicas must be 2-20 (Student-t table in session.T95 covers df <= 19)")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scenarios").mkdir(exist_ok=True)
    commit = a.commit or _git_commit()
    with ProcessPoolExecutor(a.workers) as ex:
        results = list(ex.map(export, [(s, a.replicas) for s in SCENARIOS]))
    index = []
    for d in results:
        d["provenance"] = {"commit": commit, "seed": DEV_SEED,
                           "replica_ids": f"{REPLICA_BASE + 1}-{REPLICA_BASE + a.replicas}",
                           "command": "uv run python scripts/site_export.py",
                           "generator": "deliverytwin.benchmark.generator.generate_instance"}
        # The hidden truth and every evaluator verdict live in a separate file that the site
        # fetches only after the visitor asks for the reveal (DESIGN_SYSTEM §1.6).
        truth = {"id": d["id"], "reveal": d.pop("reveal"),
                 "evaluations": {k: v.pop("result") for k, v in d["sessions"].items()}}
        (OUT / "scenarios" / f"{d['id']}.json").write_text(json.dumps(d, separators=(",", ":")))
        (OUT / "scenarios" / f"{d['id']}.truth.json").write_text(json.dumps(truth, separators=(",", ":")))
        index.append({"id": d["id"], "level": d["level"], "index": d["index"],
                      "dataset_id": d["dataset_id"], "profile": d["telemetry"]["profile"],
                      "alert": d["alert"], "agents": sorted(d["sessions"])})
        print(d["id"], truth["reveal"]["family"], len(d["world"]["orders"]), "orders",
              {k: v["exact"] for k, v in truth["evaluations"].items()})
    (OUT / "scenarios" / "index.json").write_text(json.dumps(
        {"commit": commit, "seed": DEV_SEED, "scenarios": index}, indent=1))


if __name__ == "__main__":
    main()

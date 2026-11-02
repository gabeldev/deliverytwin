"""Regression tests for the independent Codex review of the G2 code (58daf00, at HEAD 5b65735)."""

import importlib.util
from pathlib import Path

from deliverytwin.benchmark.generator import impact, passes_impact
from deliverytwin.diagnostics.detector import DetectorConfig, calibrate_thresholds, max_scores
from deliverytwin.diagnostics.features import customer_features
from deliverytwin.faults.spec import CourierScarcity, DispatcherSaturation, NoiseSpec, causal_dag
from deliverytwin.simulation.interventions import Branch
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator, build_telemetry
from deliverytwin.world.config import WorldConfig


# Finding 1: demand jitter for blocks after a fork was shared by all replicas.
def test_post_fork_demand_shocks_vary_across_replicas():
    cfg = WorldConfig(horizon_minutes=240)
    noise = NoiseSpec(demand_jitter_sigma=0.25)  # 30-min blocks; fork at 60 = block 2
    base = World(cfg, 5, noise=noise)
    r1 = base.fork_at(Branch(t0=60, replica=1)).run()
    r2 = base.fork_at(Branch(t0=60, replica=2)).run()
    for zone in range(cfg.n_zones):
        for block in (0, 1):  # observed before the fork: shared
            assert r1.demand_jitter[(zone, block)] == r2.demand_jitter[(zone, block)]
        for block in (2, 3, 4):  # first reached after the fork: replica-specific
            assert r1.demand_jitter[(zone, block)] != r2.demand_jitter[(zone, block)]


# Finding 2: the saturation DAG lacked the direct service-time edge.
def test_saturation_dag_has_direct_service_time_edge():
    dag = causal_dag(DispatcherSaturation(onset=1, service_multiplier=5))
    assert ("dispatch_service_time", "assignment_delay") in dag
    assert ("dispatch_service_time", "dispatch_queue") in dag


# Finding 3: thresholds were rounded down before a strict `>` comparison.
def test_calibrated_thresholds_are_observed_order_statistics():
    cfg = WorldConfig(horizon_minutes=360)
    tels = [build_telemetry(World(cfg, 700 + i).run(), dataset_id="c", profile="customer",
                            observed_until=360, obfuscator=Obfuscator(1)) for i in range(12)]
    det = calibrate_thresholds(tels, 0.2, DetectorConfig())
    globals_ = [max_scores(t, DetectorConfig())["global"] for t in tels]
    assert det.thr_global in globals_  # exact value, not a rounded one


# Finding 4: the impact gate rejected a complete outage.
def test_impact_gate_accepts_a_complete_outage():
    cfg = WorldConfig(horizon_minutes=360, customer_patience_floor_minutes=500)
    f = CourierScarcity(onset=180, offline_fraction=0.999999)
    imp = impact(World(cfg, 1, faults=(f,)).run(), World(cfg, 1).run(), 180)
    assert imp["global_time"] > 10 and imp["global_bad"] > 0.5
    assert passes_impact(imp)


# Finding 5: baselines were scored on a set that included their own training data.
def test_baselines_are_scored_on_a_fresh_evaluation_seed():
    path = Path(__file__).resolve().parents[2] / "scripts" / "g2_report.py"
    spec = importlib.util.spec_from_file_location("g2r", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from deliverytwin.benchmark.generator import PUBLIC_DEV_MASTER_SEED
    assert mod.EVAL_MASTER_SEED != PUBLIC_DEV_MASTER_SEED


# Finding 6: open_share looked at outcomes after the alert time.
def test_open_share_ignores_outcomes_after_alert():
    cfg = WorldConfig(horizon_minutes=360)
    w = World(cfg, 3).run()
    short = build_telemetry(w, dataset_id="x", profile="customer", observed_until=240,
                            obfuscator=Obfuscator(1))
    long = build_telemetry(w, dataset_id="x", profile="customer", observed_until=360,
                           obfuscator=Obfuscator(1))
    assert customer_features(short, 240)["open_share"] == customer_features(long, 240)["open_share"]

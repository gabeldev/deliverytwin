"""G2 checks: faults, telemetry contract, leakage, generator gates, detector, rules."""

import json

import pytest

from deliverytwin.benchmark.generator import FORBIDDEN_TERMS, generate_instance
from deliverytwin.diagnostics.detector import detect
from deliverytwin.diagnostics.rules import diagnose_rules
from deliverytwin.faults.spec import (
    CourierScarcity,
    DispatcherSaturation,
    NoiseSpec,
    RestaurantBottleneck,
    causal_dag,
)
from deliverytwin.simulation.interventions import AddCouriers, Branch, NoOp, Placebo
from deliverytwin.simulation.kpis import compute_kpis
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator, build_telemetry, scan_for_leaks
from deliverytwin.world.config import WorldConfig

CFG = WorldConfig(horizon_minutes=300)
NOISE = NoiseSpec(demand_jitter_sigma=0.25, gauge_noise_sigma=0.15)


# --- faults --------------------------------------------------------------------------

@pytest.mark.parametrize("fault", [CourierScarcity(onset=140, offline_fraction=0.6),
                                   DispatcherSaturation(onset=140, service_multiplier=11)])
def test_global_faults_degrade_delivery_in_paired_comparison(fault):
    worse = 0
    for s in range(1, 9):
        a = compute_kpis(World(CFG, s).run().log, 40, 140)
        b = compute_kpis(World(CFG, s, faults=(fault,)).run().log, 40, 140)
        worse += b.delivery_p50 > a.delivery_p50
    assert worse >= 7


def test_restaurant_bottleneck_inflates_only_that_restaurants_prep():
    f = RestaurantBottleneck(onset=140, restaurant_index=1, prep_multiplier=4)
    w = World(CFG, 3, faults=(f,)).run()
    target = w.city.restaurants[1].restaurant_id
    start, durations = {}, {}
    for e in w.log.events:
        if e["ev"] == "prep_started":
            start[e["oid"]] = (e["t"], e["rid"])
        elif e["ev"] == "order_ready":
            t0, rid = start[e["oid"]]
            durations.setdefault((rid == target, t0 >= 140), []).append(e["t"] - t0)
    mean = {k: sum(v) / len(v) for k, v in durations.items()}
    assert mean[(True, True)] > 2.5 * mean[(True, False)]
    assert mean[(False, True)] < 1.5 * mean[(False, False)]


def test_causal_dags_have_expected_roots():
    assert causal_dag(CourierScarcity(onset=1, offline_fraction=0.5))[0][0] == "courier_supply"
    assert causal_dag(DispatcherSaturation(onset=1, service_multiplier=5))[0][0] == \
        "dispatch_service_time"
    assert causal_dag(RestaurantBottleneck(onset=1, restaurant_index=0, prep_multiplier=2),
                      "r_x")[0][0] == "prep_time[r_x]"


# --- G1 guarantees still hold with faults and noise ----------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_zero_difference_and_placebo_hold_in_faulty_noisy_worlds(seed):
    faults = (CourierScarcity(onset=140, offline_fraction=0.5),)
    base = World(CFG, seed, faults=faults, noise=NOISE)
    a = base.fork_at(Branch(t0=200, interventions=(AddCouriers(count=4),), replica=2)).run()
    b = base.fork_at(Branch(t0=200, interventions=(AddCouriers(count=4),), replica=2)).run()
    assert a.log.digest() == b.log.digest()
    n = base.fork_at(Branch(t0=200, interventions=(NoOp(),), replica=2)).run()
    p = base.fork_at(Branch(t0=200, interventions=(Placebo(extra_draws=300),), replica=2)).run()
    assert n.log.digest() == p.log.digest()


def test_fork_inherits_faults_and_noise():
    faults = (DispatcherSaturation(onset=140, service_multiplier=10),)
    continuous = World(CFG, 5, faults=faults, noise=NOISE).run()
    forked = World(CFG, 5, faults=faults, noise=NOISE).fork_at(Branch(t0=180)).run()
    assert forked.log.digest() == continuous.log.digest()


# --- telemetry contract ----------------------------------------------------------------

def _tel(profile, salt=7, until=200.0):
    w = World(CFG, 11, faults=(CourierScarcity(onset=140, offline_fraction=0.5),)).run()
    return build_telemetry(w, dataset_id="t", profile=profile, observed_until=until,
                           obfuscator=Obfuscator(salt))


def test_telemetry_contract_and_censoring():
    tel = _tel("full")
    assert tel.schema_version == "telemetry/v1" and tel.source == "simulated"
    times = [v for o in tel.orders for v in (o.created, o.assigned, o.ready, o.picked_up,
                                               o.delivered, o.cancelled) if v is not None]
    assert max(times) <= 200.0
    assert all(g.t <= 200.0 for g in tel.gauges)
    assert {g.metric for g in tel.gauges} >= {"couriers_online", "dispatch_queue"}


def test_customer_profile_hides_operational_signals():
    tel = _tel("customer")
    assert tel.gauges == ()
    assert all(o.assigned is None and o.ready is None and o.picked_up is None for o in tel.orders)
    assert any(o.delivered is not None for o in tel.orders)


def test_obfuscation_is_stable_per_salt_and_differs_across_salts():
    a, b, c = _tel("customer", salt=7), _tel("customer", salt=7), _tel("customer", salt=8)
    assert a.model_dump_json() == b.model_dump_json()
    assert {e.token for e in a.entities}.isdisjoint({e.token for e in c.entities})


def test_leak_scanner_catches_planted_leaks():
    payload = _tel("full").model_dump_json()
    assert scan_for_leaks(payload, FORBIDDEN_TERMS) == []
    assert scan_for_leaks(payload + " r003", FORBIDDEN_TERMS)
    assert scan_for_leaks(payload + " courier_scarcity", FORBIDDEN_TERMS)
    assert scan_for_leaks(payload + " CANARY-x", ["CANARY-x"])


# --- generator gates ---------------------------------------------------------------------

@pytest.mark.parametrize("level", ["L0", "L1", "L2"])
def test_generator_is_deterministic_and_gated(level):
    a = generate_instance(level, 3)
    b = generate_instance(level, 3)
    assert a.private == b.private
    assert a.public.model_dump_json() == b.public.model_dump_json()
    p = a.private
    assert p.alert["t"] >= p.fault["onset"]
    assert a.public.observed_until == p.alert["t"]
    assert a.public.profile == ("customer" if level == "L2" else "full")
    payload = a.public.model_dump_json()
    assert scan_for_leaks(payload, [*FORBIDDEN_TERMS, p.canary, str(p.world_seed)]) == []
    assert p.split in {"train", "dev", "test"}
    assert json.loads(payload)["source"] == "simulated"


# --- detector and rules -------------------------------------------------------------------

def test_detector_rarely_alarms_on_healthy_worlds():
    alarms = 0
    for s in range(300_000, 300_010):
        w = World(CFG, s, noise=NOISE).run()
        tel = build_telemetry(w, dataset_id="h", profile="customer", observed_until=300,
                              obfuscator=Obfuscator(1))
        alarms += detect(tel) is not None
    assert alarms <= 2


def test_rule_baseline_beats_trivial_floors_on_l0():
    hits = 0
    for i in range(20):
        inst = generate_instance("L0", i)
        d = diagnose_rules(inst.public, inst.private.alert["t"])
        hits += d.cause == inst.private.family
    assert hits >= 10  # majority/random family floors are ~0.33-0.4


def test_rules_abstain_on_customer_profile_pair():
    inst = generate_instance("L2", 0)
    d = diagnose_rules(inst.public, inst.private.alert["t"])
    assert d.cause in (None, "restaurant_bottleneck")


# --- G2.1: constructed L2 pair -------------------------------------------------------------

def _assign_delays(world):
    acc, out = {}, {}
    for e in world.log.events:
        if e["ev"] == "order_accepted":
            acc[e["oid"]] = e["t"]
        elif e["ev"] == "order_assigned" and e["oid"] in acc:
            out[e["oid"]] = e["t"] - acc[e["oid"]]
    return out


@pytest.mark.parametrize("seed", [4, 5])
def test_error_surge_and_latency_delay_each_order_identically(seed):
    from deliverytwin.faults.spec import DispatchErrorSurge, DispatchLatency
    cfg = WorldConfig(horizon_minutes=360)
    a = _assign_delays(World(cfg, seed, faults=(DispatchErrorSurge(onset=200, error_prob=0.96),)).run())
    b = _assign_delays(World(cfg, seed, faults=(DispatchLatency(onset=200, hang_prob=0.96),)).run())
    common = [o for o in a if o in b and a[o] > 0.5]
    assert len(common) > 50
    same = sum(abs(a[o] - b[o]) < 0.5 for o in common) / len(common)
    assert same >= 0.95


def test_retry_backoff_separates_error_surge_from_latency():
    from deliverytwin.faults.spec import DispatchErrorSurge, DispatchLatency
    from deliverytwin.simulation.interventions import SetRetryBackoff
    cfg = WorldConfig(horizon_minutes=400)

    def effect(fault):
        deltas = []
        for s in range(1, 5):
            base = World(cfg, s, faults=(fault,))
            ctrl = base.fork_at(Branch(t0=230, interventions=(NoOp(),), replica=1)).run()
            trt = base.fork_at(Branch(t0=230, interventions=(SetRetryBackoff(minutes=0.2),),
                                      replica=1)).run()
            a = compute_kpis(ctrl.log, cfg.promised_delivery_minutes, 230)
            b = compute_kpis(trt.log, cfg.promised_delivery_minutes, 230)
            deltas.append(b.delivery_p50 - a.delivery_p50)
        return sum(deltas) / len(deltas)

    assert effect(DispatchErrorSurge(onset=200, error_prob=0.96)) < -3.0
    assert abs(effect(DispatchLatency(onset=200, hang_prob=0.96))) < 0.5

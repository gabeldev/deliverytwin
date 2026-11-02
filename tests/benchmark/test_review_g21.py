"""Regression tests for the independent Codex review of commit 3a7e506 (G2.1).

Each test reproduces one confirmed finding and fails on the pre-fix code.
"""

import importlib.util
from pathlib import Path

import pytest

from deliverytwin.benchmark.generator import generate_instance, resolve_master_seed
from deliverytwin.faults.spec import DispatchErrorSurge, DispatchLatency
from deliverytwin.simulation.interventions import Branch, NoOp
from deliverytwin.simulation.kpis import cohort_bad_rate
from deliverytwin.simulation.world import World
from deliverytwin.telemetry.build import Obfuscator
from deliverytwin.world.config import WorldConfig, ZoneDemand


# Finding 1 (high): public dataset id revealed level/index, hence the hidden family.
def test_public_dataset_id_is_opaque():
    a, b = generate_instance("L2", 0), generate_instance("L2", 1)
    for inst in (a, b):
        pid = inst.public.dataset_id
        assert inst.private.instance_id not in pid
        assert "L2" not in pid and "-000" not in pid
    assert a.public.dataset_id != b.public.dataset_id


def test_public_seed_instances_are_marked_unsealed(monkeypatch):
    monkeypatch.delenv("DELIVERYTWIN_MASTER_SEED", raising=False)
    assert resolve_master_seed(None) == (2026, False)
    monkeypatch.setenv("DELIVERYTWIN_MASTER_SEED", "987654321")
    assert resolve_master_seed(None) == (987654321, True)
    inst = generate_instance("L2", 0)
    assert inst.private.sealed
    # A secret seed yields a different world than the public seed for the same index, so
    # recomputing from public code no longer reproduces the instance.
    assert inst.private.world_seed != generate_instance("L2", 0, master_seed=2026).private.world_seed


# Finding 2 (medium): kitchen gauges were serialised in raw restaurant-id order.
def test_kitchen_gauges_are_not_in_raw_id_order():
    inst = generate_instance("L0", 0)
    t = inst.public.gauges[0].t
    order = [g.entity for g in inst.public.gauges if g.metric == "kitchen_load" and g.t == t]
    ob = Obfuscator(inst.private.obfuscation_salt)
    raw_order = [ob.token("r", f"r{i:03d}") for i in range(len(order))]
    assert order == sorted(order)
    assert order != raw_order


def _assigned(world):
    return {e["oid"]: e["t"] for e in world.log.events if e["ev"] == "order_assigned"}


# Finding 3 (high): latency pre-drew future steps with the base seed across a fork.
def test_error_surge_and_latency_stay_coupled_across_a_fork():
    cfg = WorldConfig(horizon_minutes=360)
    branch = Branch(t0=230, interventions=(NoOp(),), replica=1)
    e = _assigned(World(cfg, 4, faults=(DispatchErrorSurge(onset=200, error_prob=0.96),))
                  .fork_at(branch).run())
    lat = _assigned(World(cfg, 4, faults=(DispatchLatency(onset=200, hang_prob=0.96),))
                    .fork_at(branch).run())
    assert abs(e["o-1-229-1"] - lat["o-1-229-1"]) < 0.5
    common = [o for o in e if o in lat]
    assert sum(abs(e[o] - lat[o]) < 0.5 for o in common) / len(common) >= 0.95


# Finding 4 (medium): a 500-step cap turned an unresolved dependency into a success.
def test_latency_never_forces_success():
    cfg = WorldConfig(horizon_minutes=20, dispatch_retry_minutes=0.01,
                      customer_patience_floor_minutes=500, n_zones=1,
                      demand=(ZoneDemand(zone=0, orders_per_minute=0.4),))
    e = _assigned(World(cfg, 4, faults=(DispatchErrorSurge(onset=0, error_prob=0.9999),)).run())
    lat = _assigned(World(cfg, 4, faults=(DispatchLatency(onset=0, hang_prob=0.9999),)).run())
    assert len(e) == len(lat)


# Finding 5 (medium): lab effects used an open, outcome-censored cohort.
def test_cohort_bad_rate_uses_whole_closed_cohort():
    cfg = WorldConfig(horizon_minutes=360)
    w = World(cfg, 3).run()
    rate, n = cohort_bad_rate(w.log, cfg.promised_delivery_minutes, 200, 260, 330)
    accepted = sum(1 for e in w.log.events if e["ev"] == "order_accepted" and 200 <= e["t"] < 260)
    assert n == accepted and 0 <= rate <= 1
    with pytest.raises(ValueError):
        cohort_bad_rate(w.log, cfg.promised_delivery_minutes, 200, 260, 300)


# Finding 6 (medium): acceptance ignored the n >= 300 requirement.
def test_acceptance_requires_minimum_sample_size():
    path = Path(__file__).resolve().parents[2] / "scripts" / "g21_pair_search.py"
    spec = importlib.util.spec_from_file_location("g21", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.acceptance_status(150, 0.586) == "insufficient_n"
    assert mod.acceptance_status(300, 0.56) == "accepted"
    assert mod.acceptance_status(300, 0.61) == "rejected"

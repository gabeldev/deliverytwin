"""Regression tests for the independent Codex review of the G1 code (c2db1ae, at HEAD 5b65735).

Findings 9 and 10 (weak tests) are fixed in test_dispatch_baselines.py and
test_invariants.py; both strengthened tests were checked to fail under the mutations the
reviewer described.
"""

import math

import pytest

import deliverytwin.core.rng as rng_mod
from deliverytwin.core.rng import EventRng, KeyReuseError
from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    Placebo,
    SetAdmissionRate,
    SetDispatcherWorkers,
)
from deliverytwin.simulation.kpis import cohort_bad_rate, cohort_penalized_time
from deliverytwin.simulation.world import World
from deliverytwin.world.config import WorldConfig


# Finding 1: uniform() could return exactly 1.0 for an all-ones digest.
def test_uniform_never_returns_one(monkeypatch):
    class AllOnes:
        def __init__(self, *a, **k):
            pass

        def digest(self):
            return b"\xff" * 8

    monkeypatch.setattr(rng_mod.hashlib, "blake2b", AllOnes)
    r = EventRng(1, strict=False)
    u = r.uniform("x")
    assert 0.0 < u < 1.0
    assert math.isfinite(r.exponential(1.0, "e")) and math.isfinite(r.lognormal_factor(0.5, "l"))
    assert r.bernoulli(1.0, "b") is True


# Finding 2: large Poisson rates silently returned a cap of 10_000.
def test_poisson_rejects_unsupported_rates_and_is_correct_at_the_limit():
    with pytest.raises(ValueError):
        EventRng(1).poisson(1000, "p")
    r = EventRng(2)
    mean = sum(r.poisson(80.0, "p", i) for i in range(4000)) / 4000
    assert abs(mean - 80.0) < 1.0


# Finding 3: weighted sampling could pick a zero-weight outcome.
def test_weighted_index_never_picks_zero_weight():
    r = EventRng(1)
    assert r.weighted_index([1e308, 1e308, 0.0], "w") in (0, 1)
    with pytest.raises(ValueError):
        r.weighted_index([1.0, -1.0], "neg")
    with pytest.raises(ValueError):
        r.weighted_index([1.0, math.inf], "inf")


# Finding 4: the strict key guard was not shared across the t0 RNG switch.
def test_key_reuse_detected_across_fork_switch():
    w = World(WorldConfig(horizon_minutes=30), 1, branch=Branch(t0=10, replica=3))
    w.rng().uniform("reused")
    w.env.run(until=10)
    with pytest.raises(KeyReuseError):
        w.rng().uniform("reused")


# Finding 5: forking a branched world silently dropped the parent's branch.
def test_nested_fork_is_rejected():
    parent = World(WorldConfig(horizon_minutes=60), 7,
                   branch=Branch(t0=10, interventions=(SetAdmissionRate(rate=0.2),), replica=3))
    with pytest.raises(NotImplementedError):
        parent.fork_at(Branch(t0=25))


# Finding 6: inserting a placebo changed added couriers' identities and homes.
def test_placebo_insertion_does_not_change_other_interventions():
    cfg = WorldConfig(horizon_minutes=180, n_couriers=10)
    a = World(cfg, 42, branch=Branch(t0=60, interventions=(AddCouriers(count=3),), replica=1)).run()
    b = World(cfg, 42, branch=Branch(t0=60, interventions=(Placebo(extra_draws=1),
                                                            AddCouriers(count=3)), replica=1)).run()
    assert a.log.digest() == b.log.digest()


# Finding 7: decreasing dispatcher workers was silently ignored.
def test_dispatcher_worker_decrease_takes_effect():
    cfg = WorldConfig(horizon_minutes=120, dispatcher_workers=3)
    w = World(cfg, 7, branch=Branch(t0=10, interventions=(SetDispatcherWorkers(workers=1),))).run()
    assert w.params.dispatcher_workers == 1
    late = [e["worker"] for e in w.log.events if e["ev"] == "order_assigned" and e["t"] > 20]
    assert late and set(late) == {0}


# Finding 8: G1 KPIs used an open cohort whose membership depended on the outcome.
def test_closed_cohort_metrics_do_not_reward_pushing_orders_out():
    cfg = WorldConfig(horizon_minutes=240)
    w = World(cfg, 3).run()
    P = cfg.promised_delivery_minutes
    bad, n = cohort_bad_rate(w.log, P, 90, 150, 240)
    pen, m = cohort_penalized_time(w.log, P, 90, 150, 240)
    accepted = sum(1 for e in w.log.events if e["ev"] == "order_accepted" and 90 <= e["t"] < 150)
    assert n == m == accepted
    assert 0 <= bad <= 1 and pen > 0
    with pytest.raises(ValueError):
        cohort_penalized_time(w.log, P, 90, 150, 180)

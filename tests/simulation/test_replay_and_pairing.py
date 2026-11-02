"""G1 checks for ADR-0001 (replay fork) and ADR-0002 (event-keyed pairing)."""

import pytest

from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    NoOp,
    Placebo,
    SetAdmissionRate,
    SetDispatcherWorkers,
    SetDispatchPolicy,
)
from deliverytwin.simulation.kpis import compute_kpis
from deliverytwin.simulation.world import World
from deliverytwin.world.config import WorldConfig

CFG = WorldConfig(horizon_minutes=180)
SEEDS = [1, 2, 3, 17, 42]
T0 = 90.0


def run(seed, branch=None, cfg=CFG):
    return World(cfg, seed=seed, branch=branch).run()


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_is_deterministic(seed):
    assert run(seed).log.digest() == run(seed).log.digest()


def test_different_seeds_differ():
    assert len({run(s).log.digest() for s in SEEDS}) == len(SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_replay_fork_without_intervention_equals_continuous_run(seed):
    continuous = run(seed)
    forked = World(CFG, seed=seed).fork_at(Branch(t0=T0)).run()
    assert forked.log.digest() == continuous.log.digest()


@pytest.mark.parametrize("seed", SEEDS)
def test_branches_share_identical_past(seed):
    a = run(seed, Branch(t0=T0, interventions=(SetDispatcherWorkers(workers=4),), replica=3))
    b = run(seed, Branch(t0=T0, interventions=(SetAdmissionRate(rate=0.7),), replica=5))
    past_a = [e for e in a.log.events if e["t"] < T0]
    past_b = [e for e in b.log.events if e["t"] < T0]
    assert past_a == past_b


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("replica", [0, 1, 7])
def test_zero_difference_between_identical_alternatives(seed, replica):
    ivs = (SetDispatchPolicy(policy="eta_aware"), AddCouriers(count=3))
    a = run(seed, Branch(t0=T0, interventions=ivs, replica=replica))
    b = run(seed, Branch(t0=T0, interventions=ivs, replica=replica))
    ka = compute_kpis(a.log, CFG.promised_delivery_minutes, window_start=T0)
    kb = compute_kpis(b.log, CFG.promised_delivery_minutes, window_start=T0)
    assert a.log.digest() == b.log.digest()
    assert ka == kb


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("replica", [0, 4])
def test_placebo_changes_nothing(seed, replica):
    base = run(seed, Branch(t0=T0, interventions=(NoOp(),), replica=replica))
    placebo = run(seed, Branch(t0=T0, interventions=(Placebo(extra_draws=500),), replica=replica))
    assert placebo.log.digest() == base.log.digest()


def _prep_durations(world):
    started, ready = {}, {}
    for e in world.log.events:
        if e["ev"] == "prep_started":
            started[e["oid"]] = e["t"]
        elif e["ev"] == "order_ready":
            ready[e["oid"]] = e["t"]
    return {o: ready[o] - started[o] for o in ready if o in started}


def _order_attrs(world):
    return {
        oid: (o.restaurant.restaurant_id, o.destination, o.patience)
        for oid, o in world.orders.items()
        if o.patience > 0
    }


@pytest.mark.parametrize("seed", SEEDS)
def test_execution_invariance_under_path_changing_intervention(seed):
    """Lowering admission changes the execution path; shared events keep their noise."""
    a = run(seed, Branch(t0=T0, interventions=(NoOp(),), replica=2))
    b = run(seed, Branch(t0=T0, interventions=(SetAdmissionRate(rate=0.6),), replica=2))
    assert set(a.orders) == set(b.orders), "exogenous demand must not depend on the intervention"
    attrs_a, attrs_b = _order_attrs(a), _order_attrs(b)
    common = set(attrs_a) & set(attrs_b)
    assert len(common) > 50
    assert all(attrs_a[o] == attrs_b[o] for o in common)
    prep_a, prep_b = _prep_durations(a), _prep_durations(b)
    common_prep = set(prep_a) & set(prep_b)
    assert len(common_prep) > 50
    assert all(abs(prep_a[o] - prep_b[o]) < 1e-9 for o in common_prep)
    assert a.log.digest() != b.log.digest(), "the intervention must have an effect"


def test_replicas_differ_after_t0_only():
    a = run(42, Branch(t0=T0, replica=1))
    b = run(42, Branch(t0=T0, replica=2))
    assert [e for e in a.log.events if e["t"] < T0] == [e for e in b.log.events if e["t"] < T0]
    assert a.log.digest(since=T0) != b.log.digest(since=T0)


def test_world_runs_once():
    w = run(1)
    with pytest.raises(RuntimeError):
        w.run()

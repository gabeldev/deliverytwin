"""Dispatch baselines must be non-trivial (RFC §11, G1): informed policies beat random."""

from statistics import mean

from deliverytwin.simulation.interventions import Branch, SetDispatchPolicy
from deliverytwin.simulation.world import World
from deliverytwin.world.city import manhattan
from deliverytwin.world.config import WorldConfig

CFG = WorldConfig(horizon_minutes=180)


def pickup_distance(world):
    """Mean travel time from assignment to courier arrival at the restaurant."""
    assigned, arrived = {}, {}
    for e in world.log.events:
        if e["ev"] == "order_assigned":
            assigned[e["oid"]] = e["t"]
        elif e["ev"] == "courier_at_restaurant":
            arrived[e["oid"]] = e["t"]
    return mean(arrived[o] - assigned[o] for o in arrived if o in assigned)


def test_nearest_beats_random_on_pickup_travel_paired_over_seeds():
    diffs = []
    for seed in range(8):
        near = World(CFG, seed, Branch(t0=0.0, interventions=(SetDispatchPolicy(policy="nearest"),))).run()
        rand = World(CFG, seed, Branch(t0=0.0, interventions=(SetDispatchPolicy(policy="random"),))).run()
        diffs.append(pickup_distance(rand) - pickup_distance(near))
    assert mean(diffs) > 0
    assert sum(d > 0 for d in diffs) >= 7


def _assignments(world):
    """order -> courier mapping, excluding intervention metadata (Codex review G1, #9)."""
    return {e["oid"]: e["cid"] for e in world.log.events if e["ev"] == "order_assigned"}


def test_policies_are_not_degenerate():
    """Every pair of dispatch policies must assign orders differently on most seeds."""
    policies = ("nearest", "eta_aware", "random")
    for i, p in enumerate(policies):
        for q in policies[i + 1:]:
            differing = 0
            for seed in range(6):
                a = World(CFG, seed, Branch(t0=0.0, interventions=(SetDispatchPolicy(policy=p),))).run()
                b = World(CFG, seed, Branch(t0=0.0, interventions=(SetDispatchPolicy(policy=q),))).run()
                differing += _assignments(a) != _assignments(b)
            assert differing >= 5, (p, q, differing)


def test_manhattan_helper():
    assert manhattan((0, 0), (3, 4)) == 7

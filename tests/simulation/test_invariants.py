"""Property-based lifecycle invariants (RFC §11, G1)."""

from collections import defaultdict

from hypothesis import given, settings
from hypothesis import strategies as st

from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    SetAdmissionRate,
    SetDispatcherWorkers,
    SetDispatchPolicy,
)
from deliverytwin.simulation.world import World
from deliverytwin.world.config import WorldConfig

TERMINAL = {"order_rejected", "order_delivered", "order_cancelled"}

interventions = st.sampled_from([
    (),
    (SetDispatcherWorkers(workers=4),),
    (SetAdmissionRate(rate=0.5),),
    (SetDispatchPolicy(policy="random"),),
    (SetDispatchPolicy(policy="eta_aware"),),
    (AddCouriers(count=5),),
])


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=2**64),
    n_couriers=st.integers(min_value=3, max_value=40),
    workers=st.integers(min_value=1, max_value=3),
    ivs=interventions,
    replica=st.integers(min_value=0, max_value=5),
)
def test_order_and_courier_invariants(seed, n_couriers, workers, ivs, replica):
    cfg = WorldConfig(horizon_minutes=120, n_couriers=n_couriers, dispatcher_workers=workers)
    w = World(cfg, seed=seed, branch=Branch(t0=60.0, interventions=ivs, replica=replica)).run()

    per_order = defaultdict(list)
    times = []
    for e in w.log.events:
        times.append(e["t"])
        if "oid" in e:
            per_order[e["oid"]].append(e)
    assert times == sorted(times), "event log must be time-ordered"

    for oid, evs in per_order.items():
        kinds = [e["ev"] for e in evs]
        assert kinds[0] == "order_created", oid
        terminals = [k for k in kinds if k in TERMINAL]
        assert len(terminals) <= 1, (oid, kinds)
        if "order_rejected" in kinds:
            assert "order_accepted" not in kinds
        if "order_picked_up" in kinds:
            i = kinds.index("order_picked_up")
            assert "order_ready" in kinds[:i] and "order_assigned" in kinds[:i], (oid, kinds)
            assert "order_cancelled" not in kinds, (oid, kinds)
        if "order_delivered" in kinds:
            assert kinds.index("order_picked_up") < kinds.index("order_delivered")
        assert kinds.count("order_assigned") <= 1

    # A courier never carries two orders at once.
    holding: dict[str, str | None] = defaultdict(lambda: None)
    for e in w.log.events:
        if e["ev"] == "order_assigned":
            assert holding[e["cid"]] is None, (e, holding[e["cid"]])
            holding[e["cid"]] = e["oid"]
        elif e["ev"] in ("order_delivered", "courier_released"):
            assert holding[e["cid"]] == e["oid"]
            holding[e["cid"]] = None

    # Conservation (Codex review G1, #10): every created order has exactly one admission
    # decision, admission precedes every later lifecycle event, and the logged outcome
    # agrees with the live state.
    created = {o for o, evs in per_order.items() if evs[0]["ev"] == "order_created"}
    assert created == set(w.orders)
    for oid, evs in per_order.items():
        kinds = [e["ev"] for e in evs]
        decisions = [k for k in kinds if k in ("order_accepted", "order_rejected")]
        assert len(decisions) == 1, (oid, kinds)
        assert kinds.index(decisions[0]) == 1, (oid, kinds)
        order = w.orders[oid]
        if "order_delivered" in kinds:
            assert order.picked_up and not order.cancelled, oid
        if "order_cancelled" in kinds:
            assert order.cancelled and not order.picked_up, oid
        assert order.cancelled == ("order_cancelled" in kinds), oid
        if "order_cancelled" in kinds:
            # After a cancellation the kitchen may finish and an en-route courier is
            # released, but nothing can be assigned, picked up or delivered.
            after = kinds[kinds.index("order_cancelled") + 1:]
            assert set(after) <= {"prep_started", "order_ready", "courier_at_restaurant",
                                  "courier_released"}, (oid, kinds)
    accepted = sum(1 for evs in per_order.values() if evs[1]["ev"] == "order_accepted")
    delivered = sum(1 for evs in per_order.values() if evs[-1]["ev"] == "order_delivered")
    cancelled = sum(1 for o in w.orders.values() if o.cancelled)
    open_orders = sum(1 for o in w.orders.values()
                      if o.patience > 0 and not o.cancelled
                      and not any(e["ev"] == "order_delivered" for e in per_order[o.order_id]))
    assert accepted == delivered + cancelled + open_orders

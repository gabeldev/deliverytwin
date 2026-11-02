"""G5: twin lab (mode B), partial profile, and the L3-L6 ladder."""

import pytest

from deliverytwin.agent.session import (
    InvestigationSession,
    _world_for_lab,
    instance_faults,
    replica_metrics,
)
from deliverytwin.benchmark.evaluator import bundle_leaks
from deliverytwin.benchmark.generator import generate_instance
from deliverytwin.counterfactual.twin import twin_seed
from deliverytwin.simulation.interventions import Placebo

DEV = 2026


@pytest.fixture(scope="module")
def l2():
    return generate_instance("L2", 0, master_seed=DEV)


def test_twin_uses_other_seed_and_perturbed_parameters(l2):
    t0 = l2.private.alert["t"]
    true_w = _world_for_lab(l2, t0)
    twin0 = _world_for_lab(l2, t0, twin_delta=0.0)
    twin5 = _world_for_lab(l2, t0, twin_delta=0.5)
    assert twin0.seed == twin_seed(l2.private.world_seed) != true_w.seed
    assert twin0.cfg == true_w.cfg  # delta 0: only the realisation changes
    assert twin5.cfg != true_w.cfg
    assert twin5.faults[0] != true_w.faults[0]
    assert type(twin5.faults[0]) is type(true_w.faults[0])  # structure is kept
    # deterministic
    assert _world_for_lab(l2, t0, twin_delta=0.5).cfg == twin5.cfg


def test_placebo_is_exactly_null_in_both_lab_modes(l2):
    for delta in (None, 0.25):
        c, t, _ = replica_metrics(l2, (Placebo(),), [1, 2], twin_delta=delta)
        assert c == t


def test_mode_a_observe_text_is_unchanged_for_l0_l2(l2):
    text = InvestigationSession(l2).observe()
    assert "Lab:" not in text and "TWIN" not in text  # G4 SFT traces used this exact text


def test_l6_session_runs_on_twin_and_says_so():
    inst = generate_instance("L6", 0, master_seed=DEV)
    s = InvestigationSession(inst)
    assert s.lab_mode == "B" and s.twin_delta == 0.25
    assert "TWIN" in s.observe()
    out = s.experiment({"interventions": [{"kind": "set_retry_backoff", "minutes": 0.2}],
                        "replicas": 2})
    assert out.startswith("[evidence") and "twin lab experiment" in out
    assert not bundle_leaks(str(s.bundle({})), inst)


def test_l4_has_zero_slack_budget():
    s = InvestigationSession(generate_instance("L4", 0, master_seed=DEV))
    assert (s.budgets.max_experiments, s.budgets.experiment_units) == (1, 1.0)
    s.experiment({"interventions": [{"kind": "set_retry_backoff", "minutes": 0.2}],
                  "replicas": 2})
    assert "budget exhausted" in s.experiment(
        {"interventions": [{"kind": "set_retry_backoff", "minutes": 0.2}], "replicas": 2})


def test_l5_partial_profile_hides_fleet_and_dispatch_gauges():
    inst = generate_instance("L5", 0, master_seed=DEV)
    assert inst.public.profile == "partial"
    assert {g.metric for g in inst.public.gauges} == {"orders_active", "kitchen_load"}
    s = InvestigationSession(inst)
    out = s.query({"kind": "gauges", "metric": "couriers_online", "window_minutes": 30})
    assert out.startswith("ERROR") and s.queries_used == 0
    out = s.query({"kind": "gauges", "metric": "kitchen_load", "window_minutes": 30})
    assert out.startswith("[evidence") and s.queries_used == 1


def test_l3_compound_primary_has_larger_isolated_impact():
    inst = generate_instance("L3", 0, master_seed=DEV)
    p = inst.private
    assert len(p.extra_faults) == 1
    families = {p.family, p.extra_faults[0]["family"]}
    assert "restaurant_bottleneck" in families and len(families) == 2
    assert len(instance_faults(inst)) == 2
    assert p.causal_dag  # DAG of the primary

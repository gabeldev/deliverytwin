"""G3a: investigation protocol, budgets, sealed bundle, evaluator, non-LLM agents."""

import pytest

from deliverytwin.agent.baselines import run_playbook_agent, run_rules_agent
from deliverytwin.agent.session import Budgets, InvestigationSession, SessionError, bundle_json
from deliverytwin.benchmark.evaluator import bundle_leaks, evaluate, path_f1
from deliverytwin.benchmark.generator import FORBIDDEN_TERMS, generate_instance


@pytest.fixture(scope="module")
def l2():
    return generate_instance("L2", 0)


def test_invalid_actions_are_rejected_and_not_charged(l2):
    s = InvestigationSession(l2)
    assert s.query({"kind": "orders", "window_minutes": 1}).startswith("ERROR")
    assert s.query({"kind": "sql", "text": "select *"}).startswith("ERROR")
    assert s.experiment({"interventions": [{"kind": "placebo"}]}).startswith("ERROR")
    assert s.experiment({"interventions": [{"kind": "set_dispatcher_workers", "workers": 99}]}).startswith("ERROR")
    assert s.queries_used == 0 and s.experiments_used == 0 and s.units_used == 0


def test_budgets_are_enforced(l2):
    s = InvestigationSession(l2, budgets=Budgets(max_queries=1, max_experiments=1,
                                                 experiment_units=1.0))
    assert not s.query({"kind": "orders"}).startswith("ERROR")
    assert s.query({"kind": "orders"}).startswith("ERROR")
    # cost 0.5 * 4 = 2 > 1 unit
    assert "exceeds remaining" in s.experiment(
        {"interventions": [{"kind": "set_dispatcher_workers", "workers": 4}]})
    assert s.experiment({"interventions": [{"kind": "set_retry_backoff", "minutes": 0.2}],
                         "replicas": 1}).startswith("ERROR")  # one replica has no CI
    assert not s.experiment({"interventions": [{"kind": "set_retry_backoff", "minutes": 0.2}],
                             "replicas": 2}).startswith("ERROR")
    assert s.experiment({"interventions": [{"kind": "set_retry_backoff", "minutes": 0.5}],
                         "replicas": 2}).startswith("ERROR")


def test_gauges_unavailable_in_customer_profile(l2):
    s = InvestigationSession(l2)
    out = s.query({"kind": "gauges", "metric": "dispatch_queue"})
    assert out.startswith("ERROR") and "not available" in out and s.queries_used == 0


def test_submit_seals_the_session(l2):
    s = InvestigationSession(l2)
    s.submit({"cause": "dispatch_latency", "confidence": 0.6})
    with pytest.raises(SessionError):
        s.query({"kind": "orders"})


def test_agent_facing_text_and_bundle_never_contain_private_data(l2):
    s = InvestigationSession(l2)
    run_playbook_agent(s)
    text = bundle_json(s.bundle({"name": "playbook"}))
    assert bundle_leaks(text, l2) == []
    agent_text = "\n".join(t["response"] for t in s.transcript)
    # Fault family names appear only in the public taxonomy line of `observe`, never as
    # an indication of the injected one; parameter names never appear.
    for term in ("offline_fraction", "service_multiplier", "prep_multiplier", "error_prob",
                 "hang_prob", "restaurant_index", "fault"):
        assert term not in agent_text.replace("Fault taxonomy", "")
    assert l2.private.instance_id not in agent_text
    assert set(FORBIDDEN_TERMS) >= {"error_prob", "hang_prob"}


def test_path_f1():
    true = [("a", "b"), ("b", "c")]
    assert path_f1([("a", "b"), ("b", "c")], true) == 1.0
    assert path_f1([("a", "b")], true) == pytest.approx(2 / 3)
    assert path_f1([("x", "y")], true) == 0.0
    assert path_f1([("prep_time", "ready_delay")], [("prep_time[r_1]", "ready_delay[r_1]")]) == 1.0


def test_evaluator_scores_a_correct_report(l2):
    s = InvestigationSession(l2)
    s.observe()
    s.submit({"cause": l2.private.family, "confidence": 0.9,
              "causal_path": [list(e) for e in l2.private.causal_dag]})
    ev = evaluate(s.bundle({"name": "oracle"}), l2, measure_recommendation=False)
    assert ev["exact"] and ev["path_f1"] == 1.0 and ev["brier"] == pytest.approx(0.01)


def test_rules_abstain_and_playbook_experiments_on_l2(l2):
    r = InvestigationSession(l2)
    run_rules_agent(r)
    assert r.report.cause is None and r.experiments_used == 0
    p = InvestigationSession(l2)
    run_playbook_agent(p)
    assert p.experiments_used >= 1

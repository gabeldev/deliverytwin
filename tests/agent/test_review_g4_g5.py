"""Regressions for the Codex review of G4/G5 (docs/reviews/CODEX_REVIEW_G4_G5.md)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from deliverytwin.agent.llm_agent import run_llm_agent
from deliverytwin.agent.local_llm import parse_tool_calls
from deliverytwin.agent.session import InvestigationSession, _world_for_lab, instance_faults
from deliverytwin.benchmark.generator import generate_instance
from deliverytwin.simulation.world import World

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
FINAL = 515_151


def _script(name):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 1 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    '<tool_call>{"name":"query_orders","arguments":[]}</tool_call>',
    '<tool_call>{"arguments": {}}</tool_call>',
    '<tool_call>{"name": 3, "arguments": {}}</tool_call>',
])
def test_wrong_shaped_tool_calls_become_malformed(text):
    _, calls = parse_tool_calls(text)
    assert calls[0].function.name == "__malformed__"


def test_agent_loop_survives_non_object_arguments():
    from types import SimpleNamespace as NS
    inst = generate_instance("L0", 0, master_seed=2026)
    s = InvestigationSession(inst)
    bad = NS(id="c1", function=NS(name="query_orders", arguments="[]"),
             model_dump=lambda: {"id": "c1", "type": "function",
                                 "function": {"name": "query_orders", "arguments": "[]"}})

    class Client:
        model = "fake"

        def chat(self, messages, tools):
            return NS(choices=[NS(message=NS(content="", tool_calls=[bad]))])

    meta = run_llm_agent(s, Client(), max_turns=2)
    assert meta["tool_errors"] == 2 and meta["forced_submit"]


# 2 -------------------------------------------------------------------------------------
def test_gsm8k_parser_is_strict():
    predicted = _script("g4_general_check").predicted
    assert predicted("Answer: -$12") == "-12"
    assert predicted("Answer: 1e3") is None
    assert predicted("Need to divide by 42") is None
    assert predicted("work\nAnswer: $1,234.") == "1234"


# 4, 5 ----------------------------------------------------------------------------------
def test_l3_never_has_two_restaurant_faults():
    p = generate_instance("L3", 7, master_seed=FINAL).private
    fams = [p.family, *(f["family"] for f in p.extra_faults)]
    assert sorted(fams) != ["restaurant_bottleneck", "restaurant_bottleneck"]
    assert "restaurant_bottleneck" in fams and len(set(fams)) == 2


def test_lab_replays_l3_faults_in_injection_order():
    inst = generate_instance("L3", 8, master_seed=FINAL)
    fs = instance_faults(inst)
    assert [f.family for f in fs] == [f["family"] for f in inst.private.injected_faults]
    t_end = inst.private.alert["t"]
    lab = _world_for_lab(inst, t_end)
    observed = World(lab.cfg, inst.private.world_seed, faults=fs, noise=inst.noise).run()
    replay = lab.run()

    def offline(w):
        return {e["cid"] for e in w.log.events if e["ev"] == "courier_offline"}
    assert offline(observed) == offline(replay)
    # the primary is stored separately from the execution order
    assert inst.private.family in {f.family for f in fs}


# 6 -------------------------------------------------------------------------------------
def test_l3_observe_states_the_primary_fault_task_and_l0_does_not():
    l3 = InvestigationSession(generate_instance("L3", 0, master_seed=2026)).observe()
    l0 = InvestigationSession(generate_instance("L0", 0, master_seed=2026)).observe()
    assert "PRIMARY" in l3 and "PRIMARY" not in l0


# 7, 9 ----------------------------------------------------------------------------------
def test_unpaired_contrast_is_control_r_vs_treatment_r_plus_1():
    mod = _script("g5_interventions")
    ctrl = [{"bad_rate": x, "penalized_time": 0, "rejected": 0, "n": 1} for x in (0, .2, .8)]
    trt = [{"bad_rate": x, "penalized_time": 0, "rejected": 0, "n": 1} for x in (.1, .7, .3)]
    assert mod._summary(ctrl, trt, 0.0)["var_unpaired"] == pytest.approx(0.49333, abs=1e-4)


def test_infeasible_recommendations_are_not_scored_as_regret():
    from deliverytwin.simulation.interventions import AddCouriers, SetAdmissionRate
    mod = _script("g5_interventions")
    assert not mod.feasible(SetAdmissionRate(rate=0.5))
    assert mod.feasible(SetAdmissionRate(rate=0.8)) and mod.feasible(AddCouriers(count=20))
    arms = {n: {"diff_bad": 0.0, "cost": 1.0, "diff_rejected": 0, "var_paired": 0,
                "var_unpaired": 1, "all_zero": True} for n in [*mod.MENU, "placebo"]}
    arms["add_couriers_10"]["diff_bad"] = -0.1
    row = {"level": "L0", "family": "courier_scarcity", "remedy": "add_couriers_10",
           "arms": arms, "agent_recommendations": {
               "a": {"status": "ok", "diff_bad": -0.3, "feasible": True},    # beats menu
               "b": {"status": "ok", "diff_bad": -0.5, "feasible": False},   # infeasible
               "c": {"status": "missing"}}}
    out = mod.aggregate([row])
    assert out["regret_vs_best"]["a"]["mean"] == 0.0  # never negative
    assert "b" not in out["regret_vs_best"]
    assert out["agent_coverage"]["b"]["infeasible_recommendations"] == 1
    assert "c" not in out["agent_coverage"]


# 11 ------------------------------------------------------------------------------------
def test_missing_comparisons_are_not_reported_as_p_equal_1():
    paired = _script("g5_report").paired
    out = paired([], [])
    assert out["status"] == "not_run" and out["mcnemar_p"] is None
    a = [{"dataset_id": "x", "exact": True}]
    assert paired(a, a, "principal")["label"] == "principal"


# 13 ------------------------------------------------------------------------------------
def test_generation_failures_are_recorded_not_raised(monkeypatch):
    mod = _script("g5_interventions")

    def boom(*a, **k):
        raise RuntimeError("no valid instance")
    monkeypatch.setattr(mod, "generate_instance", boom)
    row = mod.study_incident(("L0", 3))
    assert row == {"level": "L0", "index": 3, "failed": "no valid instance"}
    out = mod.aggregate([row])
    assert out["complete"] is False and out["generation_failures"] == [row]
    json.dumps(out)

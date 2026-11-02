"""LLM agent loop and budget guard, tested without network (fake client)."""

import json
from types import SimpleNamespace

import pytest

from deliverytwin.agent import llm as llm_mod
from deliverytwin.agent.llm_agent import TOOLS, _clean, run_llm_agent
from deliverytwin.agent.session import InvestigationSession
from deliverytwin.benchmark.generator import generate_instance


def _call(i, name, args):
    return SimpleNamespace(
        id=f"c{i}", function=SimpleNamespace(name=name, arguments=json.dumps(args)),
        model_dump=lambda: {"id": f"c{i}", "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}})


class FakeClient:
    """Replays a fixed script of tool calls, one per turn."""

    model = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def chat(self, messages, tools):
        self.seen.append(messages[-1])
        name, args = self.script.pop(0)
        calls = [_call(len(self.seen), name, args)] if name else []
        msg = SimpleNamespace(content="", tool_calls=calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_agent_loop_runs_tools_and_submits():
    inst = generate_instance("L2", 0)
    s = InvestigationSession(inst)
    client = FakeClient([
        ("query_orders", {"window_minutes": 30, "group_by": None}),
        ("hypothesize", {"hypotheses": [
            {"family": "dispatch_error_surge", "rationale": "slow assignment"},
            {"family": "dispatch_latency", "rationale": "slow assignment"}]}),
        ("experiment", {"interventions": [{"kind": "set_retry_backoff", "minutes": 0.2,
                                           "workers": None}], "replicas": 2}),
        ("bogus_tool", {}),
        ("submit", {"cause": "dispatch_latency", "confidence": 0.7, "evidence_ids": ["q1", "x2"],
                    "scope": None}),
    ])
    meta = run_llm_agent(s, client)
    assert s.sealed and s.report.cause == "dispatch_latency"
    assert s.queries_used == 1 and s.experiments_used == 1
    assert meta["tool_errors"] == 1 and not meta["forced_submit"]
    assert any("evidence x" in str(m.get("content", "")) for m in client.seen)


def test_agent_is_forced_to_submit_at_turn_limit():
    s = InvestigationSession(generate_instance("L2", 0))
    meta = run_llm_agent(s, FakeClient([(None, {})] * 3), max_turns=3)
    assert meta["forced_submit"] and s.report.cause is None


def test_clean_drops_nulls():
    assert _clean({"a": None, "b": {"c": "", "d": 1}, "e": [None, {"f": None}]}) == \
        {"b": {"d": 1}, "e": [None, {}]}


def test_tool_schemas_cover_session_operations():
    assert {t["function"]["name"] for t in TOOLS} == {"query_orders", "query_gauges",
                                                      "hypothesize", "experiment", "submit"}


def test_call_cost_uses_cached_and_output_prices():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
             "prompt_tokens_details": {"cached_tokens": 500_000}}
    # gpt-5-nano: 0.5M * 0.05 + 0.5M * 0.005 + 1M * 0.40 = 0.4275
    assert llm_mod.call_cost("gpt-5-nano", usage) == pytest.approx(0.4275)


def test_budget_guard_refuses_before_calling(monkeypatch):
    client = object.__new__(llm_mod.LLMClient)
    client.model, client.max_completion_tokens, client.reasoning_effort = "gpt-5-nano", 2500, "low"
    client._client = None  # any real call would crash: the guard must refuse first
    monkeypatch.setattr(llm_mod, "spent_usd", lambda: 1.4999)
    monkeypatch.setattr(llm_mod, "budget_usd", lambda: 1.50)
    with pytest.raises(llm_mod.BudgetExceeded):
        client.chat([{"role": "user", "content": "x" * 3000}], TOOLS)

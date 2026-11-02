"""Regression tests for the independent Codex review of G3 (commits 8469e5a, 2745ede)."""

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from deliverytwin.agent import llm as llm_mod
from deliverytwin.agent import session as session_mod
from deliverytwin.agent.session import InvestigationSession, run_lab_experiment
from deliverytwin.benchmark import evaluator as eval_mod
from deliverytwin.benchmark.generator import generate_instance
from deliverytwin.simulation.interventions import AddCouriers, SetAdmissionRate

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def l0():
    return generate_instance("L0", 2)


# Lab: rejecting demand must not look like an improvement.
def test_admission_cut_does_not_improve_bad_rate(l0):
    r = run_lab_experiment(l0, (SetAdmissionRate(rate=0.1),), 3)
    assert r["ok"] and r["treatment_rejected"] > 0.8
    assert r["diff_bad"] > 0


# Lab: an extreme but valid experiment returns a controlled result, never crashes.
def test_extreme_admission_does_not_crash():
    s = InvestigationSession(generate_instance("L2", 0))
    out = s.experiment({"interventions": [{"kind": "set_admission_rate", "rate": 1e-20}],
                        "replicas": 2})
    assert isinstance(out, str)


# Lab: small-sample intervals use Student-t, not 1.96.
def test_lab_interval_uses_student_t(l0, monkeypatch):
    r = run_lab_experiment(l0, (AddCouriers(count=10),), 3)
    half = (r["ci_time"][1] - r["ci_time"][0]) / 2
    assert session_mod.T95[2] == pytest.approx(4.303)
    assert half > 0
    # The z-based half-width would be 1.96 / 4.303 of this one.
    assert half * 1.96 / 4.303 < half


# Evaluator: recommendation measured on futures disjoint from the investigation's.
def test_recommendation_uses_disjoint_replicas(l0, monkeypatch):
    seen = {}

    def fake(instance, ivs, replicas, replica_offset=0):
        seen["offset"] = replica_offset
        return {"ok": True, "diff_bad": 0.0}

    monkeypatch.setattr(eval_mod, "run_lab_experiment", fake)
    s = InvestigationSession(l0)
    s.submit({"cause": "courier_scarcity", "confidence": 0.5,
              "recommendation": {"kind": "add_couriers", "count": 5}})
    eval_mod.evaluate(s.bundle({"name": "t"}), l0)
    assert seen["offset"] == eval_mod.EVAL_REPLICA_OFFSET >= 100


# Evaluator: abstentions are not scored by Brier.
def test_abstention_has_no_brier(l0):
    s = InvestigationSession(l0)
    s.submit({"cause": None, "confidence": 0.0})
    ev = eval_mod.evaluate(s.bundle({"name": "t"}), l0, measure_recommendation=False)
    assert ev["brier"] is None


# Budget: the worst-case bound covers token-dense input.
def test_worst_case_bound_covers_token_dense_input():
    client = object.__new__(llm_mod.LLMClient)
    client.model, client.max_completion_tokens = "gpt-5-nano", 2500
    msgs = [{"role": "user", "content": "a1" * 1500}]  # up to ~3000 tokens
    pin, _, pout = llm_mod.PRICES["gpt-5-nano"]
    assert client._worst_case(msgs, []) >= (3000 * pin + 2500 * pout) / 1e6


def _fake_client(tmp_path, monkeypatch, cap, usage, delay=0.0):
    monkeypatch.setattr(llm_mod, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(llm_mod, "LOCK", tmp_path / "ledger.lock")
    monkeypatch.setattr(llm_mod, "budget_usd", lambda: cap)

    def create(**kwargs):
        time.sleep(delay)
        u = None if usage is None else SimpleNamespace(model_dump=lambda: usage)
        return SimpleNamespace(usage=u, choices=[])

    c = object.__new__(llm_mod.LLMClient)
    c.model, c.max_completion_tokens, c.reasoning_effort, c.tag = "gpt-5-nano", 2500, None, ""
    c._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return c


# Budget: concurrent clients cannot both spend the same remaining budget.
def test_concurrent_calls_cannot_exceed_cap(tmp_path, monkeypatch):
    msgs = [{"role": "user", "content": "x"}]
    c = _fake_client(tmp_path, monkeypatch, cap=1.0,
                     usage={"prompt_tokens": 10, "completion_tokens": 10}, delay=0.2)
    one = c._worst_case(msgs, [])
    monkeypatch.setattr(llm_mod, "budget_usd", lambda: 1.5 * one)  # room for exactly one
    results = []

    def go():
        try:
            c.chat(msgs, [])
            results.append("ok")
        except llm_mod.BudgetExceeded:
            results.append("refused")

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "refused"]


# Budget: a response without usage keeps the worst-case reservation charged.
def test_missing_usage_keeps_reservation(tmp_path, monkeypatch):
    c = _fake_client(tmp_path, monkeypatch, cap=1.0, usage=None)
    msgs = [{"role": "user", "content": "hello"}]
    est = c._worst_case(msgs, [])
    c.chat(msgs, [])
    assert llm_mod.spent_usd() == pytest.approx(est)


# Secret scan: non-ASCII staged filenames are scanned.
@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_secret_scan_handles_non_ascii_filenames(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    f = tmp_path / "arquivo_á.txt"
    f.write_text('k = "sk-proj-' + "FAKE" * 8 + '"\n')
    subprocess.run(["git", "-C", str(tmp_path), "add", f.name], check=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_secrets.py"), "--staged"],
                       cwd=tmp_path, capture_output=True, text=True, check=False)
    assert r.returncode == 1 and "arquivo_" in r.stderr

"""Budgeted LLM client (reservation ledger, fail-closed).

- The API key is read from the environment or the git-ignored `.env`; it is never logged.
- Ledger `runs/llm_ledger.jsonl` (git-ignored), append-only, two entry kinds:
    {"id", "reserve": usd}   written durably BEFORE the request (under a file lock)
    {"id", "usd": actual}    written after a response with reported usage
  Spend = sum over ids of the settled cost if present, otherwise the reservation. A call
  whose outcome or usage is unknown therefore stays charged at its worst case.
- Reservation = upper bound: prompt tokens <= UTF-8 bytes of the request (byte-level BPE
  emits >= 1 byte per token) + framing allowance; output <= max_completion_tokens.
- Check-and-reserve happens under an exclusive lock, so concurrent clients cannot spend
  the same remaining budget (Codex review G3).
"""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "runs" / "llm_ledger.jsonl"
LOCK = ROOT / "runs" / "llm_ledger.lock"
FRAMING_TOKENS = 1000  # per-request allowance for chat/tool framing

# USD per 1M tokens (input, cached input, output); OpenAI pricing page, 2026-11-02.
PRICES = {
    "gpt-5-nano": (0.05, 0.005, 0.40),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
    "gpt-5-mini": (0.25, 0.025, 2.00),
}


class BudgetExceeded(RuntimeError):
    pass


def _env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return None


def spent_usd() -> float:
    """Settled cost per id, or the reservation when no settlement exists (fail closed)."""
    if not LEDGER.exists():
        return 0.0
    reserved: dict[str, float] = {}
    settled: dict[str, float] = {}
    for line in LEDGER.read_text().splitlines():
        if not line:
            continue
        e = json.loads(line)
        cid = e.get("id") or f"legacy-{len(settled) + len(reserved)}"
        if "reserve" in e:
            reserved[cid] = e["reserve"]
        if "usd" in e:
            settled[cid] = e["usd"]
    return sum(settled.get(k, v) for k, v in reserved.items()) + sum(
        v for k, v in settled.items() if k not in reserved)


@contextmanager
def _locked():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _append(entry: dict) -> None:
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())


def budget_usd() -> float:
    return float(_env("DELIVERYTWIN_LLM_BUDGET_USD") or 0.0)


def call_cost(model: str, usage: dict) -> float:
    pin, pcached, pout = PRICES[model]
    prompt = usage.get("prompt_tokens", 0)
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
    completion = usage.get("completion_tokens", 0)
    return ((prompt - cached) * pin + cached * pcached + completion * pout) / 1e6


@dataclass
class LLMClient:
    model: str
    max_completion_tokens: int = 2500
    reasoning_effort: str | None = "low"
    tag: str = ""

    def __post_init__(self):
        if self.model not in PRICES:
            raise ValueError(f"no price for model {self.model}; add it to PRICES first")
        key = _env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set (environment or .env)")
        from openai import OpenAI  # lazy: only the llm dependency group installs it

        self._client = OpenAI(api_key=key)

    def _worst_case(self, messages: list[dict], tools: list[dict]) -> float:
        prompt_bytes = len(json.dumps(messages).encode()) + len(json.dumps(tools).encode())
        prompt_tokens = prompt_bytes + FRAMING_TOKENS
        pin, _, pout = PRICES[self.model]
        return (prompt_tokens * pin + self.max_completion_tokens * pout) / 1e6

    def chat(self, messages: list[dict], tools: list[dict]) -> Any:
        est = self._worst_case(messages, tools)
        cid = uuid.uuid4().hex
        with _locked():
            spent, cap = spent_usd(), budget_usd()
            if spent + est > cap:
                raise BudgetExceeded(f"spent ${spent:.4f} + worst case ${est:.4f} > cap ${cap:.2f}")
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            _append({"id": cid, "t": time.time(), "model": self.model, "tag": self.tag,
                     "reserve": est})
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "tools": tools,
                                  "max_completion_tokens": self.max_completion_tokens}
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        resp = self._client.chat.completions.create(**kwargs)  # failure: reservation stays
        usage = resp.usage.model_dump() if resp.usage else None
        if not usage or "prompt_tokens" not in usage:
            return resp  # unknown usage: keep the worst-case reservation as the charge
        with _locked():
            _append({"id": cid, "t": time.time(), "model": self.model, "tag": self.tag,
                     "usage": usage, "usd": call_cost(self.model, usage)})
        return resp

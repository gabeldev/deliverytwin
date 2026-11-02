"""LLM investigator: acts only through the session's typed tools (ADR-0004, ADR-0008)."""

from __future__ import annotations

import json
from typing import Any

from deliverytwin.agent.protocol import CAUSAL_NODES, FAULT_TAXONOMY
from deliverytwin.agent.session import InvestigationSession

SYSTEM_PROMPT = f"""You are an incident investigator for a SIMULATED food-delivery operation \
(synthetic, not a real company). An alert fired. Find the root cause using only the tools.

Possible causes (exactly one is active, or say it cannot be determined):
- courier_scarcity: many couriers went offline.
- dispatcher_saturation: the dispatch service became slow (queueing).
- restaurant_bottleneck: one restaurant's kitchen slowed down (give its token as scope).
- dispatch_error_surge: dispatch calls fail fast and are retried after a backoff.
- dispatch_latency: dispatch calls hang (no failure, no retry).

Tools: query_orders (customer-visible order statistics by time window, optionally per \
zone or restaurant), query_gauges (operational gauges; only in the full profile), \
hypothesize (record competing hypotheses), experiment (paired lab experiment from the \
alert time: intervention vs control; costs budget), submit (final report).
What each intervention does (operator runbook):
- set_dispatcher_workers: number of parallel dispatch workers (dispatch capacity).
- add_couriers: brings extra couriers online now.
- set_retry_backoff: wait before a FAILED dispatch call is retried.
- set_admission_rate: fraction of new orders accepted (rejects the rest).
- set_dispatch_policy: rule used to choose a courier.
Method: look at the data, record at least two competing hypotheses, and when the data \
cannot separate them, run experiments that change ONE intervention at a time, chosen so \
that its expected effect differs between your hypotheses. An intervention acting on the \
true cause lowers the bad-order rate (CI below zero); a null result is evidence against \
the causes that intervention would act on. Base the conclusion on the evidence, cite \
evidence ids (q1, x2, ...) and report a confidence that reflects it. If the remaining \
causes cannot be separated, submit cause=null with unresolved_between.
causal_path: list of [from, to] edges using only these nodes: {", ".join(CAUSAL_NODES)}.
Be economical: few, targeted queries. Always finish with submit."""

_INTERVENTION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "kind": {"type": "string", "enum": ["set_dispatcher_workers", "set_admission_rate",
                                            "set_dispatch_policy", "add_couriers",
                                            "set_retry_backoff"]},
        "workers": {"type": "integer", "minimum": 1, "maximum": 16},
        "rate": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        "policy": {"type": "string", "enum": ["nearest", "eta_aware", "random"]},
        "count": {"type": "integer", "minimum": 1, "maximum": 50},
        "minutes": {"type": "number", "minimum": 0.05, "maximum": 10},
    },
    "required": ["kind"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "query_orders",
        "description": "Customer-visible order statistics per time window.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "window_minutes": {"type": "integer", "minimum": 5, "maximum": 120},
            "group_by": {"type": "string", "enum": ["none", "zone", "restaurant"]},
            "since": {"type": "number", "minimum": 0}}, "required": []}}},
    {"type": "function", "function": {
        "name": "query_gauges",
        "description": "Operational gauge means per time window (full profile only).",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "metric": {"type": "string", "enum": ["dispatch_queue", "couriers_online",
                                                  "couriers_idle", "orders_active",
                                                  "kitchen_load"]},
            "window_minutes": {"type": "integer", "minimum": 5, "maximum": 120},
            "since": {"type": "number", "minimum": 0}}, "required": ["metric"]}}},
    {"type": "function", "function": {
        "name": "hypothesize", "description": "Record 1-5 competing hypotheses.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "hypotheses": {"type": "array", "minItems": 1, "maxItems": 5, "items": {
                "type": "object", "additionalProperties": False, "properties": {
                    "family": {"type": "string", "enum": list(FAULT_TAXONOMY)},
                    "scope": {"type": "string", "description": "restaurant token, if any"},
                    "rationale": {"type": "string", "maxLength": 600},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["family", "rationale"]}}}, "required": ["hypotheses"]}}},
    {"type": "function", "function": {
        "name": "experiment", "description": "Paired lab experiment from the alert time.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "interventions": {"type": "array", "minItems": 1, "maxItems": 3,
                              "items": _INTERVENTION},
            "replicas": {"type": "integer", "minimum": 2, "maximum": 5},
            "rationale": {"type": "string", "maxLength": 600}},
            "required": ["interventions"]}}},
    {"type": "function", "function": {
        "name": "submit", "description": "Final report; ends the investigation.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {
            "cause": {"type": ["string", "null"], "enum": [*FAULT_TAXONOMY, None]},
            "scope": {"type": "string", "description": "restaurant token, if any"},
            "unresolved_between": {"type": "array", "items": {
                "type": "string", "enum": list(FAULT_TAXONOMY)}},
            "causal_path": {"type": "array", "items": {
                "type": "array", "minItems": 2, "maxItems": 2,
                "items": {"type": "string", "enum": list(CAUSAL_NODES)}}},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "recommendation": _INTERVENTION,
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string", "maxLength": 1200}},
            "required": ["cause", "confidence"]}}},
]


def _clean(x: Any) -> Any:
    """Drop null/empty fields the model adds for irrelevant parameters."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if v is not None and v != ""}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def run_llm_agent(s: InvestigationSession, client, max_turns: int = 16,
                  disabled_tools: frozenset[str] = frozenset()) -> dict:
    """`disabled_tools` removes tools from the schema sent to the model and from the
    dispatcher (G5 ablation H1/H9: no experiment tool)."""
    tools = [t for t in TOOLS if t["function"]["name"] not in disabled_tools]
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": s.observe()}]
    turns, tool_calls, errors = 0, 0, 0
    ops = {"query_orders": lambda a: s.query({"kind": "orders", **a}),
           "query_gauges": lambda a: s.query({"kind": "gauges", **a}),
           "hypothesize": s.hypothesize, "experiment": s.experiment, "submit": s.submit}
    ops = {k: v for k, v in ops.items() if k not in disabled_tools}
    while not s.sealed and turns < max_turns:
        turns += 1
        resp = client.chat(messages, tools)
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        messages.append({"role": "assistant", "content": msg.content or "",
                         **({"tool_calls": [c.model_dump() for c in calls]} if calls else {})})
        if not calls:
            messages.append({"role": "user", "content":
                             "Use the tools. Finish with submit when ready."})
            continue
        for c in calls:
            tool_calls += 1
            try:
                args = _clean(json.loads(c.function.arguments or "{}"))
            except json.JSONDecodeError:
                args = None
            fn = ops.get(c.function.name)
            if fn is None or not isinstance(args, dict):
                out = "ERROR unknown tool or malformed JSON arguments"
            elif s.sealed:
                out = "ERROR session already submitted"
            else:
                out = fn(args)
            errors += out.startswith("ERROR")
            messages.append({"role": "tool", "tool_call_id": c.id, "content": out})
    forced = False
    if not s.sealed:
        forced = True
        s.submit({"cause": None, "confidence": 0.0, "summary": "no submission within turn limit"})
    return {"name": "llm", "model": getattr(client, "model", "fake"), "turns": turns,
            "disabled_tools": sorted(disabled_tools),
            "tool_calls": tool_calls, "tool_errors": errors, "forced_submit": forced}


def compact_tools(tools: list[dict] = TOOLS) -> list[dict]:
    """Same functions, fields and enums, without free-text descriptions and length limits:
    used by the local model (training and inference) to fit the 4096-token budget."""
    drop = {"description", "maxLength", "minLength"}

    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in drop}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x

    return [{"type": "function", "function": {
        "name": t["function"]["name"], "parameters": strip(t["function"]["parameters"])}}
        for t in tools]

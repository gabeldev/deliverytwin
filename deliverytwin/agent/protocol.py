"""Typed investigation protocol (ADR-0004). Every agent action is validated here by the
orchestrator before anything runs; the model never touches the simulator directly
(ADR-0008)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from deliverytwin.simulation.interventions import (
    AddCouriers,
    SetAdmissionRate,
    SetDispatcherWorkers,
    SetDispatchPolicy,
    SetRetryBackoff,
)

# Public fault taxonomy the agent may hypothesise about (names are public; which one is
# injected in an instance is private).
FAULT_TAXONOMY = ("courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck",
                  "dispatch_error_surge", "dispatch_latency")
CAUSAL_NODES = ("courier_supply", "idle_couriers", "dispatch_service_time", "dispatch_queue",
                "dispatch_errors", "dispatch_retries", "dependency_latency", "dispatch_hang",
                "prep_time", "ready_delay", "assignment_delay", "pickup_delay",
                "delivery_time", "late_rate", "cancellations")


class _M(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- queries -------------------------------------------------------------------------

class OrdersQuery(_M):
    """Customer-visible order statistics, aggregated by time window and optional group."""

    kind: Literal["orders"] = "orders"
    window_minutes: int = Field(default=30, ge=5, le=120)
    group_by: Literal["none", "zone", "restaurant"] = "none"
    since: float | None = Field(default=None, ge=0)


class GaugesQuery(_M):
    """Operational gauges (only available in the full observability profile)."""

    kind: Literal["gauges"] = "gauges"
    metric: Literal["dispatch_queue", "couriers_online", "couriers_idle", "orders_active",
                    "kitchen_load"]
    window_minutes: int = Field(default=15, ge=5, le=120)
    since: float | None = Field(default=None, ge=0)


Query = Annotated[OrdersQuery | GaugesQuery, Field(discriminator="kind")]


# --- hypotheses ----------------------------------------------------------------------

class Hypothesis(_M):
    family: Literal["courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck",
                    "dispatch_error_surge", "dispatch_latency"]
    scope: str | None = Field(default=None, description="restaurant token if localised")
    rationale: str = Field(max_length=600)
    evidence_ids: tuple[str, ...] = ()


class HypothesisSet(_M):
    hypotheses: tuple[Hypothesis, ...] = Field(min_length=1, max_length=5)


# --- experiments ---------------------------------------------------------------------

AllowedIntervention = Annotated[
    SetDispatcherWorkers | SetAdmissionRate | SetDispatchPolicy | AddCouriers | SetRetryBackoff,
    Field(discriminator="kind"),
]


class ExperimentSpec(_M):
    """Run treatment vs control from the alert, paired replicas, in the lab."""

    interventions: tuple[AllowedIntervention, ...] = Field(min_length=1, max_length=3)
    replicas: int = Field(default=3, ge=2, le=5)  # >= 2 so a CI exists
    rationale: str = Field(default="", max_length=600)


# --- report --------------------------------------------------------------------------

class Report(_M):
    cause: Literal["courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck",
                   "dispatch_error_surge", "dispatch_latency"] | None = None
    scope: str | None = None
    unresolved_between: tuple[str, ...] = ()
    causal_path: tuple[tuple[str, str], ...] = ()
    evidence_ids: tuple[str, ...] = ()
    recommendation: AllowedIntervention | None = None
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(default="", max_length=1200)


# Operational cost of each intervention in an experiment (budget units, ADR-0004).
def intervention_cost(iv) -> float:
    if isinstance(iv, SetDispatcherWorkers):
        return 0.5 * iv.workers
    if isinstance(iv, AddCouriers):
        return 0.2 * iv.count
    if isinstance(iv, SetAdmissionRate):
        return 10.0 * (1.0 - iv.rate)
    if isinstance(iv, SetDispatchPolicy | SetRetryBackoff):
        return 1.0
    raise TypeError(iv)

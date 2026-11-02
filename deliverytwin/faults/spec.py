"""Injectable faults and ambient noise (ADR-0005).

A fault is a *mechanism change* starting at `onset`. Its causal propagation graph is
private ground truth: it is stored in the instance manifest and never exposed to the
agent. Ambient noise injectors are separate from faults and are never a valid cause.

Node vocabulary for causal DAGs (shared with the evaluator):
  courier_supply, idle_couriers, dispatch_service_time, dispatch_queue,
  dispatch_errors, dispatch_retries, dependency_latency, dispatch_hang,
  assignment_delay, pickup_delay, prep_time[r], ready_delay[r],
  delivery_time, late_rate, cancellations
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Fault(BaseModel):
    model_config = ConfigDict(frozen=True)
    onset: float = Field(ge=0)


class CourierScarcity(_Fault):
    """A fraction of online couriers go offline at onset (they finish current deliveries)."""

    family: Literal["courier_scarcity"] = "courier_scarcity"
    offline_fraction: float = Field(gt=0, lt=1)


class DispatcherSaturation(_Fault):
    """The dispatch service slows down (e.g. throttling, degraded dependency)."""

    family: Literal["dispatcher_saturation"] = "dispatcher_saturation"
    service_multiplier: float = Field(gt=1, le=50)


class RestaurantBottleneck(_Fault):
    """One restaurant's preparation time inflates (kitchen problem)."""

    family: Literal["restaurant_bottleneck"] = "restaurant_bottleneck"
    restaurant_index: int = Field(ge=0)
    prep_multiplier: float = Field(gt=1, le=10)


class DispatchErrorSurge(_Fault):
    """Assignment attempts start failing (e.g. a flaky dependency); failed attempts retry."""

    family: Literal["dispatch_error_surge"] = "dispatch_error_surge"
    error_prob: float = Field(gt=0, lt=1)


class DispatchLatency(_Fault):
    """A dispatch dependency hangs instead of failing. By construction it reuses the same
    per-attempt draws as `DispatchErrorSurge`, so each order is delayed by the same number
    of steps; the difference is that the worker is held (no retry backoff involved).
    Observationally equivalent to an error surge for customers; separable by changing the
    retry backoff (helps errors only) or adding workers (helps latency when workers bind)."""

    family: Literal["dispatch_latency"] = "dispatch_latency"
    hang_prob: float = Field(gt=0, lt=1)


Fault = Annotated[
    CourierScarcity | DispatcherSaturation | RestaurantBottleneck | DispatchErrorSurge
    | DispatchLatency,
    Field(discriminator="family"),
]

FAULT_FAMILIES = ("courier_scarcity", "dispatcher_saturation", "restaurant_bottleneck",
                  "dispatch_error_surge", "dispatch_latency")


class NoiseSpec(BaseModel):
    """Ambient (non-causal) variation."""

    model_config = ConfigDict(frozen=True)
    demand_jitter_sigma: float = Field(default=0.0, ge=0, le=1)
    demand_jitter_block_minutes: int = Field(default=30, ge=1)
    gauge_noise_sigma: float = Field(default=0.0, ge=0, le=1)


_DOWNSTREAM = [
    ("assignment_delay", "pickup_delay"),
    ("pickup_delay", "delivery_time"),
    ("delivery_time", "late_rate"),
    ("assignment_delay", "cancellations"),
]


def causal_dag(fault,
               restaurant_id: str | None = None) -> list[tuple[str, str]]:
    """True propagation edges for a fault (private ground truth)."""
    if isinstance(fault, CourierScarcity):
        return [("courier_supply", "idle_couriers"), ("idle_couriers", "assignment_delay"),
                *_DOWNSTREAM]
    if isinstance(fault, DispatcherSaturation):
        # Slower service delays assignment directly and through queueing (Codex review G2, #2).
        return [("dispatch_service_time", "dispatch_queue"),
                ("dispatch_service_time", "assignment_delay"),
                ("dispatch_queue", "assignment_delay"), *_DOWNSTREAM]
    if isinstance(fault, DispatchErrorSurge):
        return [("dispatch_errors", "dispatch_retries"), ("dispatch_retries", "assignment_delay"),
                *_DOWNSTREAM]
    if isinstance(fault, DispatchLatency):
        return [("dependency_latency", "dispatch_hang"), ("dispatch_hang", "assignment_delay"),
                *_DOWNSTREAM]
    if isinstance(fault, RestaurantBottleneck):
        r = restaurant_id or f"restaurant[{fault.restaurant_index}]"
        return [(f"prep_time[{r}]", f"ready_delay[{r}]"), (f"ready_delay[{r}]", "delivery_time"),
                ("delivery_time", "late_rate"), (f"ready_delay[{r}]", "cancellations")]
    raise TypeError(f"unknown fault {fault!r}")


def root_node(fault, restaurant_id: str | None = None) -> str:
    return causal_dag(fault, restaurant_id)[0][0]

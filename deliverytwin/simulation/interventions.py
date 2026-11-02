"""Typed operational interventions applied at the branch time t0 (ADR-0004 allowlist).

Interventions change mechanisms or their inputs; they never touch exogenous noise.
`Placebo` is a mechanically null intervention used to test execution invariance.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from deliverytwin.world.config import DispatchPolicyName


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class NoOp(_Base):
    kind: Literal["noop"] = "noop"


class SetDispatcherWorkers(_Base):
    kind: Literal["set_dispatcher_workers"] = "set_dispatcher_workers"
    workers: int = Field(ge=1, le=16)


class SetAdmissionRate(_Base):
    kind: Literal["set_admission_rate"] = "set_admission_rate"
    rate: float = Field(gt=0, le=1)


class SetDispatchPolicy(_Base):
    kind: Literal["set_dispatch_policy"] = "set_dispatch_policy"
    policy: DispatchPolicyName


class AddCouriers(_Base):
    """Incentive that brings extra couriers online at t0."""

    kind: Literal["add_couriers"] = "add_couriers"
    count: int = Field(ge=1, le=50)


class SetRetryBackoff(_Base):
    """Change the wait before a failed dispatch attempt is retried."""

    kind: Literal["set_retry_backoff"] = "set_retry_backoff"
    minutes: float = Field(ge=0.05, le=10)


class Placebo(_Base):
    """Consumes extra random draws and changes nothing else (invariance test only)."""

    kind: Literal["placebo"] = "placebo"
    extra_draws: int = Field(default=100, ge=1, le=100_000)


Intervention = Annotated[
    NoOp | SetDispatcherWorkers | SetAdmissionRate | SetDispatchPolicy | AddCouriers
    | SetRetryBackoff | Placebo,
    Field(discriminator="kind"),
]


class Branch(_Base):
    """A counterfactual branch: interventions applied at t0, future replica r.

    Replica 0 reuses the base seed after t0, so a branch with no interventions and
    replica 0 reproduces the continuous run exactly (ADR-0001 replay check).
    """

    t0: float = Field(ge=0)
    interventions: tuple[Intervention, ...] = ()
    replica: int = Field(default=0, ge=0)

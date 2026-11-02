"""Discrete-event delivery world (ADR-0001, ADR-0002).

Domain state lives in explicit dataclasses; SimPy processes only schedule events
over that state. All randomness goes through `EventRng` with stable event keys.

Branching (counterfactuals) is implemented by deterministic replay: a branched
world is rebuilt from the same config and seed, runs identically until `t0`, then
applies the branch interventions. Draws at simulated time >= t0 use a seed derived
from the replica index (replica 0 = base seed), so replicas are independent futures
while the shared past is fixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import simpy

from deliverytwin.core.rng import EventRng, KeyPart, derive_seed
from deliverytwin.faults.spec import (
    CourierScarcity,
    DispatchErrorSurge,
    DispatcherSaturation,
    DispatchLatency,
    NoiseSpec,
    RestaurantBottleneck,
)
from deliverytwin.simulation.eventlog import EventLog
from deliverytwin.simulation.interventions import (
    AddCouriers,
    Branch,
    NoOp,
    Placebo,
    SetAdmissionRate,
    SetDispatcherWorkers,
    SetDispatchPolicy,
    SetRetryBackoff,
)
from deliverytwin.world.city import (
    City,
    Point,
    Restaurant,
    build_city,
    manhattan,
    random_point_in_zone,
)
from deliverytwin.world.config import WorldConfig


@dataclass
class Courier:
    courier_id: str
    position: Point
    available: bool
    busy: bool = False


@dataclass
class Order:
    order_id: str
    zone: int
    created_at: float
    restaurant: Restaurant
    destination: Point
    patience: float = 0.0
    prep_started_at: float | None = None
    ready: bool = False
    picked_up: bool = False
    cancelled: bool = False
    courier_id: str | None = None
    offers_made: int = 0
    dispatch_attempts: int = 0
    ready_event: simpy.Event | None = None
    cancel_event: simpy.Event | None = None
    pickup_event: simpy.Event | None = None


@dataclass
class _DispatchRequest:
    order: Order
    latency_resolved: bool = False  # the dependency hang for this attempt already happened


@dataclass
class _Mutable:
    """Mechanism parameters that interventions are allowed to change."""

    admission_rate: float
    dispatch_policy: str
    dispatcher_workers: int
    dispatch_error_prob: float = 0.0
    dispatch_latency_prob: float = 0.0
    dispatch_retry_minutes: float = 1.0
    dispatch_service_multiplier: float = 1.0
    prep_multiplier: dict[str, float] = field(default_factory=dict)


@dataclass
class Gauge:
    """Per-minute operational gauges (sampled at the end of each simulated minute)."""

    t: float
    dispatch_queue: int
    couriers_online: int
    couriers_idle: int
    orders_active: int
    kitchen_load: dict[str, int]


@dataclass
class World:
    cfg: WorldConfig
    seed: int
    branch: Branch | None = None
    faults: tuple = ()
    noise: NoiseSpec | None = None
    log: EventLog = field(default_factory=EventLog)

    def __post_init__(self) -> None:
        self.env = simpy.Environment()
        self._rng_pre = EventRng(self.seed)
        if self.branch is None or self.branch.replica == 0:
            self._rng_post = self._rng_pre
        else:
            # Shared key registry: a key drawn before t0 cannot be drawn again after it
            # (Codex review G1, finding 4).
            self._rng_post = EventRng(derive_seed(self.seed, "replica", self.branch.replica),
                                      seen=self._rng_pre._seen)
        self.city: City = build_city(self.cfg, self._rng_pre)
        # Kitchens are sized for their expected load (Little's law) so that a healthy world
        # has no structurally overloaded kitchen: servers = ceil(lambda_r * prep / target_util).
        zone_rate = {d.zone: d.orders_per_minute for d in self.cfg.demand}
        zone_pop: dict[int, float] = {}
        for r in self.city.restaurants:
            zone_pop[r.zone] = zone_pop.get(r.zone, 0.0) + r.popularity
        self.kitchens = {}
        for r in self.city.restaurants:
            lam = zone_rate.get(r.zone, 0.0) * r.popularity / zone_pop[r.zone]
            mean_prep = self.cfg.prep_mean_minutes * math.exp(self.cfg.prep_sigma**2 / 2)
            servers = math.ceil(lam * mean_prep / self.cfg.kitchen_target_utilization)
            self.kitchens[r.restaurant_id] = simpy.Resource(
                self.env, capacity=max(self.cfg.kitchen_capacity, servers)
            )
        self.couriers: dict[str, Courier] = {}
        for cid, home in self.city.courier_homes:
            available = self._rng_pre.bernoulli(
                self.cfg.courier_shift_availability, "shift", cid, self.cfg.day
            )
            self.couriers[cid] = Courier(courier_id=cid, position=home, available=available)
        self.orders: dict[str, Order] = {}
        self.params = _Mutable(
            admission_rate=self.cfg.admission_rate,
            dispatch_policy=self.cfg.dispatch_policy,
            dispatcher_workers=self.cfg.dispatcher_workers,
            dispatch_error_prob=self.cfg.dispatch_error_prob,
            dispatch_retry_minutes=self.cfg.dispatch_retry_minutes,
        )
        self.dispatch_queue: simpy.Store = simpy.Store(self.env)
        self.gauges: list[Gauge] = []
        self._active_workers: set[int] = set()
        self.demand_jitter: dict[tuple[int, int], float] = {}  # (zone, block) -> factor
        self._dyad_offers: dict[tuple[str, str], int] = {}
        self._ran = False

    # --- randomness -------------------------------------------------------------

    def rng(self) -> EventRng:
        if self.branch is not None and self.env.now >= self.branch.t0:
            return self._rng_post
        return self._rng_pre

    # --- forking (ADR-0001) -------------------------------------------------------

    def fork_at(self, branch: Branch) -> World:
        """Counterfactual branch by deterministic replay from the same config and seed.

        Only unbranched worlds can be forked: replaying a branched parent would drop its
        interventions and replica seed (Codex review G1, finding 5)."""
        if self.branch is not None:
            raise NotImplementedError("nested forks are not supported; fork the root world")
        return World(cfg=self.cfg, seed=self.seed, branch=branch, faults=self.faults,
                     noise=self.noise)

    # --- run ------------------------------------------------------------------------

    def run(self) -> World:
        if self._ran:
            raise RuntimeError("a World can only be run once; fork a new one instead")
        self._ran = True
        for cid in sorted(self.couriers):
            c = self.couriers[cid]
            self.log.emit(0.0, "courier_shift", cid=cid, available=c.available)
        for i in range(self.params.dispatcher_workers):
            self.env.process(self._dispatcher_worker(i))
        self.env.process(self._demand())
        for idx, fault in enumerate(self.faults):
            self.env.process(self._inject(fault, idx))
        if self.branch is not None:
            self.env.process(self._apply_branch(self.branch))
        self.env.process(self._sample_gauges())
        self.env.run(until=self.cfg.horizon_minutes)
        return self

    # --- faults (private mechanism changes, ADR-0005) --------------------------------

    def _inject(self, fault, idx: int):
        # Fault realisations use the base seed: they are part of the world, shared by all
        # branches and replicas, never re-drawn per counterfactual.
        yield self.env.timeout(fault.onset)
        if isinstance(fault, CourierScarcity):
            for cid in sorted(self.couriers):
                c = self.couriers[cid]
                if c.available and self._rng_pre.bernoulli(
                    fault.offline_fraction, "fault_offline", idx, cid
                ):
                    c.available = False
                    self.log.emit(self.env.now, "courier_offline", cid=cid)
        elif isinstance(fault, DispatchErrorSurge):
            self.params.dispatch_error_prob = fault.error_prob
        elif isinstance(fault, DispatchLatency):
            self.params.dispatch_latency_prob = fault.hang_prob
        elif isinstance(fault, DispatcherSaturation):
            self.params.dispatch_service_multiplier = fault.service_multiplier
        elif isinstance(fault, RestaurantBottleneck):
            r = self.city.restaurants[fault.restaurant_index % len(self.city.restaurants)]
            self.params.prep_multiplier[r.restaurant_id] = fault.prep_multiplier
        else:  # pragma: no cover
            raise TypeError(f"unknown fault {fault!r}")

    def _sample_gauges(self):
        while True:
            yield self.env.timeout(1)
            online = [c for c in self.couriers.values() if c.available]
            active = sum(1 for o in self.orders.values()
                         if o.patience > 0 and not o.cancelled and not o.picked_up)
            self.gauges.append(Gauge(
                t=self.env.now,
                dispatch_queue=len(self.dispatch_queue.items),
                couriers_online=len(online),
                couriers_idle=sum(1 for c in online if not c.busy),
                orders_active=active,
                kitchen_load={rid: k.count + len(k.queue) for rid, k in sorted(self.kitchens.items())},
            ))

    # --- processes ----------------------------------------------------------------

    def _apply_branch(self, branch: Branch):
        yield self.env.timeout(branch.t0)
        # Interventions are identified by their ordinal among interventions of the same
        # kind, so inserting an unrelated one (e.g. a placebo) does not change the keys of
        # the others (Codex review G1, finding 6).
        ordinal: dict[str, int] = {}
        for iv in branch.interventions:
            k = ordinal.get(iv.kind, 0)
            ordinal[iv.kind] = k + 1
            self._apply(iv, k)

    def _apply(self, iv, idx: int) -> None:
        now = self.env.now
        if isinstance(iv, NoOp):
            return
        if isinstance(iv, Placebo):
            rng = self.rng()
            for j in range(iv.extra_draws):
                rng.uniform("placebo", idx, j)
            return
        self.log.emit(now, "intervention", kind=iv.kind, **iv.model_dump(exclude={"kind"}))
        if isinstance(iv, SetAdmissionRate):
            self.params.admission_rate = iv.rate
        elif isinstance(iv, SetDispatchPolicy):
            self.params.dispatch_policy = iv.policy
        elif isinstance(iv, SetDispatcherWorkers):
            # Increase: start the missing workers. Decrease: workers with index >= target
            # retire before taking their next request (Codex review G1, finding 7).
            self.params.dispatcher_workers = iv.workers
            for i in range(iv.workers):
                if i not in self._active_workers:
                    self.env.process(self._dispatcher_worker(i))
        elif isinstance(iv, SetRetryBackoff):
            self.params.dispatch_retry_minutes = iv.minutes
        elif isinstance(iv, AddCouriers):
            for j in range(iv.count):
                cid = f"inc{idx}-{j:02d}"
                zone = j % self.cfg.n_zones
                home = random_point_in_zone(self.rng(), self.cfg, zone, "incentive_home", idx, j)
                self.couriers[cid] = Courier(courier_id=cid, position=home, available=True)
                self.log.emit(now, "courier_shift", cid=cid, available=True)
        else:  # pragma: no cover - guarded by the pydantic union
            raise TypeError(f"unknown intervention {iv!r}")

    def _demand(self):
        """Exogenous order arrivals: per (zone, minute) Poisson counts with stable keys."""
        rates = {d.zone: d.orders_per_minute for d in self.cfg.demand}
        jitter = self.demand_jitter
        for minute in range(self.cfg.horizon_minutes):
            rng = self.rng()
            for zone in sorted(rates):
                lam = rates[zone]
                if self.noise is not None and self.noise.demand_jitter_sigma > 0:
                    block = minute // self.noise.demand_jitter_block_minutes
                    if (zone, block) not in jitter:
                        # Drawn with the active generator when the block is first reached:
                        # blocks after a fork vary across replicas (Codex review G2, #1).
                        jitter[(zone, block)] = rng.lognormal_factor(
                            self.noise.demand_jitter_sigma, "demand_jitter", zone, block
                        )
                    lam *= jitter[(zone, block)]
                n = rng.poisson(lam, "arrivals", zone, minute)
                for k in range(n):
                    oid = f"o-{zone}-{minute}-{k}"
                    offset = rng.uniform("arrival_offset", oid)
                    self.env.process(self._order(oid, zone, minute + offset))
            yield self.env.timeout(1)

    def _order(self, oid: str, zone: int, created_at: float):
        yield self.env.timeout(created_at - self.env.now)
        rng = self.rng()
        candidates = self.city.restaurants_in_zone(zone) or list(self.city.restaurants)
        restaurant = candidates[
            rng.weighted_index([r.popularity for r in candidates], "restaurant", oid)
        ]
        destination = random_point_in_zone(rng, self.cfg, zone, "destination", oid)
        order = Order(oid, zone, self.env.now, restaurant, destination)
        self.orders[oid] = order
        self.log.emit(self.env.now, "order_created", oid=oid, zone=zone,
                      rid=restaurant.restaurant_id)
        if not rng.bernoulli(self.params.admission_rate, "admit", oid):
            self.log.emit(self.env.now, "order_rejected", oid=oid)
            return
        self.log.emit(self.env.now, "order_accepted", oid=oid)
        order.patience = self.cfg.customer_patience_floor_minutes + rng.exponential(
            self.cfg.customer_patience_mean_minutes, "patience", oid
        )
        order.ready_event = self.env.event()
        order.cancel_event = self.env.event()
        order.pickup_event = self.env.event()
        self.env.process(self._kitchen(order))
        self.dispatch_queue.put(_DispatchRequest(order))
        result = yield order.pickup_event | self.env.timeout(order.patience)
        if order.pickup_event not in result and not order.picked_up:
            order.cancelled = True
            order.cancel_event.succeed()
            self.log.emit(self.env.now, "order_cancelled", oid=oid, cid=order.courier_id)

    def _kitchen(self, order: Order):
        kitchen = self.kitchens[order.restaurant.restaurant_id]
        with kitchen.request() as req:
            yield req
            order.prep_started_at = self.env.now
            self.log.emit(self.env.now, "prep_started", oid=order.order_id,
                          rid=order.restaurant.restaurant_id)
            prep = self.cfg.prep_mean_minutes * self.rng().lognormal_factor(
                self.cfg.prep_sigma, "prep", order.order_id
            ) * self.params.prep_multiplier.get(order.restaurant.restaurant_id, 1.0)
            yield self.env.timeout(prep)
        order.ready = True
        order.ready_event.succeed()
        self.log.emit(self.env.now, "order_ready", oid=order.order_id)

    def _dispatcher_worker(self, worker_index: int):
        """Dispatch loop. Error surges and dependency latency share the per-attempt draws
        ("dispatch_err", order, attempt) so that, by construction, an order suffers the same
        number of failed/hung steps in both worlds:
          - error: the call fails fast (no service time), the request waits the retry
            backoff and re-enters the queue;
          - latency: the call hangs asynchronously, one step (the *default* backoff
            length) per failed draw, each drawn when it happens, then re-enters the queue
            as resolved.
        The successful attempt then gets the normal service time and an offer."""
        self._active_workers.add(worker_index)
        while True:
            if worker_index >= self.params.dispatcher_workers:
                self._active_workers.discard(worker_index)
                return
            req: _DispatchRequest = yield self.dispatch_queue.get()
            order = req.order
            if order.cancelled:
                continue
            rng = self.rng()
            if self.params.dispatch_latency_prob > 0 and not req.latency_resolved:
                if rng.bernoulli(self.params.dispatch_latency_prob, "dispatch_err",
                                 order.order_id, order.dispatch_attempts):
                    order.dispatch_attempts += 1
                    self.env.process(self._hang_then_requeue(order))
                    continue
            elif self.params.dispatch_latency_prob == 0 and rng.bernoulli(
                self.params.dispatch_error_prob, "dispatch_err", order.order_id,
                order.dispatch_attempts,
            ):
                self.log.emit(self.env.now, "dispatch_error", oid=order.order_id,
                              attempt=order.dispatch_attempts)
                order.dispatch_attempts += 1
                self.env.process(self._requeue(order))
                continue
            yield self.env.timeout(
                self.cfg.dispatch_service_minutes * self.params.dispatch_service_multiplier
            )
            if order.cancelled:
                continue
            attempt = order.dispatch_attempts
            order.dispatch_attempts += 1
            self._try_assign(order, attempt, worker_index)

    def _hang_then_requeue(self, order: Order):
        """Asynchronous dependency hang. Each step is drawn when it actually happens (so a
        fork's replica seed applies to post-fork steps exactly as it does for error
        retries), and the loop only ends on an observed success or a cancellation.
        Codex review G2.1, findings 3 and 4."""
        while True:
            yield self.env.timeout(self.cfg.dispatch_retry_minutes)
            if order.cancelled:
                return
            if not self.rng().bernoulli(self.params.dispatch_latency_prob, "dispatch_err",
                                        order.order_id, order.dispatch_attempts):
                break  # success draw at this attempt index; the worker reuses it
            order.dispatch_attempts += 1
        self.dispatch_queue.put(_DispatchRequest(order, latency_resolved=True))

    def _try_assign(self, order: Order, attempt: int, worker_index: int) -> None:
        courier = self._offer(order, attempt)
        if courier is None:
            self.log.emit(self.env.now, "no_courier", oid=order.order_id, attempt=attempt)
            self.env.process(self._requeue(order))
            return
        courier.busy = True
        order.courier_id = courier.courier_id
        self.log.emit(self.env.now, "order_assigned", oid=order.order_id,
                      cid=courier.courier_id, attempt=attempt, worker=worker_index)
        self.env.process(self._delivery(order, courier))

    def _requeue(self, order: Order):
        yield self.env.timeout(self.params.dispatch_retry_minutes)
        if not order.cancelled:
            self.dispatch_queue.put(_DispatchRequest(order))

    def _offer(self, order: Order, attempt: int) -> Courier | None:
        idle = [c for cid, c in sorted(self.couriers.items()) if c.available and not c.busy]
        if not idle:
            return None
        ranked = self._rank(order, idle, attempt)
        rng = self.rng()
        for courier in ranked:
            offer = order.offers_made
            order.offers_made += 1
            if self.cfg.accept_key_mode == "slot":
                key: tuple[KeyPart, ...] = ("accept", order.order_id, offer)
            else:  # dyad: the latent chance belongs to the (order, courier) pair
                pair = (order.order_id, courier.courier_id)
                k = self._dyad_offers.get(pair, 0)
                self._dyad_offers[pair] = k + 1
                key = ("accept_dyad", order.order_id, courier.courier_id, k)
            accepted = rng.bernoulli(self.cfg.courier_accept_prob, *key)
            self.log.emit(self.env.now, "offer", oid=order.order_id, cid=courier.courier_id,
                          offer=offer, accepted=accepted)
            if accepted:
                return courier
        return None

    def _rank(self, order: Order, idle: list[Courier], attempt: int) -> list[Courier]:
        policy = self.params.dispatch_policy
        rpos = order.restaurant.position
        if policy == "random":
            pool = list(idle)
            out = []
            i = 0
            while pool:
                j = self.rng().choice_index(len(pool), "random_rank", order.order_id, attempt, i)
                out.append(pool.pop(j))
                i += 1
            return out
        if policy == "nearest":
            return sorted(idle, key=lambda c: (manhattan(c.position, rpos), c.courier_id))
        if policy == "eta_aware":
            # Just-in-time matching: prefer the courier whose estimated arrival is closest
            # to the estimated ready time, keeping nearer couriers free for urgent orders.
            ready_in = 0.0
            if not order.ready:
                started = order.prep_started_at
                elapsed = 0.0 if started is None else self.env.now - started
                ready_in = max(0.0, self.cfg.prep_mean_minutes - elapsed)

            def score(c: Courier) -> tuple[float, int, str]:
                dist = manhattan(c.position, rpos)
                arrive = dist * self.cfg.minutes_per_block
                return (abs(arrive - ready_in), dist, c.courier_id)

            return sorted(idle, key=score)
        raise ValueError(f"unknown dispatch policy {policy}")

    def _travel_time(self, a: Point, b: Point, *key: KeyPart) -> float:
        base = max(manhattan(a, b), 0.5) * self.cfg.minutes_per_block
        return base * self.rng().lognormal_factor(self.cfg.travel_noise_sigma, "travel", *key)

    def _delivery(self, order: Order, courier: Courier):
        oid = order.order_id
        yield self.env.timeout(
            self._travel_time(courier.position, order.restaurant.position, oid, "to_restaurant")
        )
        courier.position = order.restaurant.position
        self.log.emit(self.env.now, "courier_at_restaurant", oid=oid, cid=courier.courier_id)
        if not order.ready and not order.cancelled:
            yield order.ready_event | order.cancel_event
        if order.cancelled:
            courier.busy = False
            self.log.emit(self.env.now, "courier_released", oid=oid, cid=courier.courier_id)
            return
        # Handover starts: from here the customer can no longer cancel (the food is with the
        # courier); the pickup is logged when the service time ends.
        order.picked_up = True
        order.pickup_event.succeed()
        yield self.env.timeout(self.cfg.pickup_service_minutes)
        self.log.emit(self.env.now, "order_picked_up", oid=oid, cid=courier.courier_id)
        yield self.env.timeout(
            self._travel_time(order.restaurant.position, order.destination, oid, "to_customer")
        )
        yield self.env.timeout(self.cfg.dropoff_service_minutes)
        courier.position = order.destination
        courier.busy = False
        self.log.emit(self.env.now, "order_delivered", oid=oid, cid=courier.courier_id)

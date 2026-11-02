# Revisão independente (Codex CLI) — commit c2db1ae (G1), avaliado no HEAD 5b65735

**Data:** 2026-11-01 · **Revisor:** Codex CLI 0.166 (`codex exec -s read-only`) · **Instruções:** `docs/reviews/codex_review_prompt_g1.txt`

Saída original do revisor (caminhos convertidos para relativos). Verificação e correções: `docs/reports/REVIEW_FIXES_G1_G2.md`.

---

Confirmed against HEAD `5b65735` after inspecting `c2db1ae`. The 59 RNG, replay, and dispatch tests passed; targeted in-memory probes reproduced the findings below.

1. **Medium — `uniform()` can return exactly 1.0.** [rng.py:73](deliverytwin/core/rng.py:73)  
   When `bits == 2**53 - 1`, floating-point rounding makes `(bits + 0.5) / 2**53` equal `1.0`. Forcing an all-ones digest reproduces this: `bernoulli(1)` returns false, while `exponential()` and `lognormal_factor()` raise `ValueError`.  
   **Fix:** use an exactly representable open-interval construction, such as 52 random bits with `(bits + 0.5) / 2**52`, and add endpoint tests.

2. **Medium — Poisson sampling silently produces incorrect counts for valid large rates.** [rng.py:90](deliverytwin/core/rng.py:90)  
   For `lam=1000`, `exp(-lam)` underflows to zero. The recurrence never recovers, so every draw returns the arbitrary cap of `10_000`. `EventRng(1).poisson(1000, "p")` reproduces this. Demand rates have no upper validation bound, so a valid configuration can generate ten times the intended demand.  
   **Fix:** implement a numerically stable algorithm for large rates, or reject unsupported rates explicitly; never return the loop cap as a sampled count.

3. **Medium — Weighted sampling can select a zero-weight outcome.** [rng.py:105](deliverytwin/core/rng.py:105)  
   Finite weights `[1e308, 1e308, 0.0]` overflow their total to infinity. Every comparison fails, and the fallback returns index `2`, whose probability should be zero. Negative and nonfinite weights also pass the current validation.  
   **Fix:** validate finite, nonnegative weights and normalize by their maximum before accumulating.

4. **Low — Strict key reuse detection stops at the RNG switch.** [world.py:126](deliverytwin/simulation/world.py:126)  
   Nonzero replicas create separate `_seen` sets before and after `t0`. Drawing `"reused"` through `world.rng()`, advancing to `t0`, and drawing it again succeeds with a different value. This contradicts the documented once-per-world guard and can conceal accidental resampling across the fork.  
   **Fix:** share a world-level registry of consumed event keys between both RNG instances.

5. **High — Forking an already branched world discards its history.** [world.py:170](deliverytwin/simulation/world.py:170)  
   `fork_at()` retains configuration, seed, faults, and noise, but replaces the existing branch entirely. Reproduce with a parent using `Branch(t0=10, interventions=(SetAdmissionRate(rate=.2),), replica=3)`, then call `parent.fork_at(Branch(t0=25)).run()`. The child omits the intervention at minute 10 and uses the base RNG during minutes 10–25, changing its supposedly shared past.  
   **Fix:** replay the complete intervention and replica-seed history through the new fork time, then append the new branch. Alternatively, explicitly reject nested forks until supported.

6. **Medium — Inserting a placebo changes added couriers’ exogenous attributes.** [world.py:265](deliverytwin/simulation/world.py:265)  
   Added courier IDs and home-position keys depend on the intervention’s tuple index. Consequently, `(AddCouriers(count=3),)` and `(Placebo(extra_draws=1), AddCouriers(count=3))` create different couriers and locations. With seed 42, 10 initial couriers, horizon 180, `t0=60`, replica 1, inserting the placebo changes cancellations from 35 to 36. The existing placebo test exercises only standalone interventions.  
   **Fix:** identify courier additions independently of unrelated intervention positions, and test placebo insertion into intervention bundles.

7. **Medium — `SetDispatcherWorkers` silently ignores decreases.** [world.py:258](deliverytwin/simulation/world.py:258)  
   The implementation only starts workers and takes `max(current, requested)`. From the default two workers, `SetDispatcherWorkers(workers=1)` logs a successful intervention but leaves two workers running. This produces an incorrect counterfactual for an accepted intervention value.  
   **Fix:** implement worker retirement at safe boundaries, or explicitly expose and validate an increase-only intervention.

8. **Medium — G1 KPI comparisons remain biased by incomplete outcomes.** [kpis.py:63](deliverytwin/simulation/kpis.py:63), [g1_report.py:65](scripts/g1_report.py:65)  
   Delivery percentiles and lateness exclude unresolved and cancelled orders; assignment delay excludes unassigned orders. The creation window extends through the simulation cutoff, so treatment affects which outcomes enter these calculations. For example, one delivery taking 10 minutes and another taking 59 minutes yield lateness `0.5` against a 40-minute promise. Delaying the second beyond the cutoff improves reported lateness to `0` and median delivery time to `10`, despite worsening service.  
   HEAD added `cohort_bad_rate()`, but the G1 report still uses the original calculations.  
   **Fix:** use an explicit closed creation cohort and complete follow-up, or censoring-aware estimates; include unresolved overdue orders and cancellations in the service-failure comparison.

9. **Medium — The policy nondegeneracy test passes when every policy is identical.** [test_dispatch_baselines.py:43](tests/simulation/test_dispatch_baselines.py:43)  
   It compares complete log hashes. Each log already records a different intervention `policy` value, guaranteeing different hashes independently of assignments. I replaced `_rank()` in memory with identical courier-ID ordering for all policies; this test still passed. Thus it cannot support the report’s nondegenerate-policy verification claim.  
   **Fix:** compare actual assignment sequences or mappings, excluding intervention metadata.

10. **Low — The claimed lifecycle/conservation check does not verify conservation.** [test_invariants.py:75](tests/simulation/test_invariants.py:75)  
    The final assertion only compares creation events with entries in `world.orders`. It never reconciles acceptance, rejection, terminal outcomes, and live state. Suppressing every `order_accepted` event still passes the test’s assertions for seed 42, 20 couriers, two workers, and replica 1—even though delivered orders then lack acceptance and KPI `in_flight` can become negative.  
    **Fix:** require exactly one acceptance or rejection per created order, acceptance before subsequent lifecycle events, and agreement between terminal events and remaining live state.

No additional findings in ordinary key encoding, inverse-normal computation, replica-seed derivation, small-index choice bias, courier double assignment, cancellation versus pickup, or iteration/same-time ordering in the inspected paths. The published G1 point estimates and variance ratios match the stored JSON; the KPI selection problem above still limits their interpretation.
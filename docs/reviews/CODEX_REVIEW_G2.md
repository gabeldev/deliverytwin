# Revisão independente (Codex CLI) — commit 58daf00 (G2), avaliado no HEAD 5b65735

**Data:** 2026-11-01 · **Revisor:** Codex CLI 0.166 (`codex exec -s read-only`) · **Instruções:** `docs/reviews/codex_review_prompt_g2.txt`

Saída original do revisor (caminhos convertidos para relativos). Verificação e correções: `docs/reports/REVIEW_FIXES_G1_G2.md`.

---

Reviewed `58daf00` against committed HEAD `5b65735`. All locations below refer to HEAD.

**1. Public telemetry leakage: no additional findings.** I found no remaining leak in censoring, serialization ordering, or the customer profile’s operational-field filtering. Pre-onset payloads matched their fault-free counterparts for all five current fault families.

**2. Fault injection semantics**

- **Medium — Future demand shocks are shared across replicas.** [deliverytwin/simulation/world.py:284](deliverytwin/simulation/world.py:284)  
  Demand jitter always uses `_rng_pre`, including blocks beginning after a fork. This contradicts the documented independent-future semantics: replicas vary arrivals conditional on exactly the same future demand shocks, omitting that component of uncertainty.  
  **Reproduction:** seed `5`, fork at `60`, horizon `120`, jitter sigma `0.25`: replicas `1` and `2` both draw every jitter value for blocks `2` and `3` from seed `5`.  
  **Fix:** use the active replica RNG when first drawing a new block; retain cached values for blocks already observed before the fork.

- **Medium — The saturation DAG omits the direct service-time effect.** [deliverytwin/faults/spec.py:100](deliverytwin/faults/spec.py:100)  
  Ground truth represents assignment delay solely through `dispatch_service_time → dispatch_queue → assignment_delay`. The implementation also increases assignment delay directly through service duration, without any queueing. A correct explanation of that mechanism therefore lacks a corresponding ground-truth edge.  
  **Reproduction:** seed `3`, horizon `30`, one zone and restaurant, demand `0.02/min`, dispatch errors disabled, saturation at `0` with multiplier `10`: the sole assignment moves from `11.0331` to `13.7331`, while the queue remains empty.  
  **Fix:** add `dispatch_service_time → assignment_delay`; distinguish service duration from queue waiting in the graph.

**3. Detector and calibration**

- **Low — Rounding thresholds downward changes the calibrated rejection tail.** [deliverytwin/diagnostics/detector.py:137](deliverytwin/diagnostics/detector.py:137)  
  Thresholds are rounded before the detector applies strict `score > threshold`. Downward rounding makes the selected quantile itself trigger an alert, which is particularly problematic for discrete scores with ties.  
  **Reproduction:** the documented 300 calibration worlds select global score `0.16891891891891891`; rounding produces `0.1689`, increasing calibration exceedances from seven to eight runs and exceeding the allocated 2.5% global budget.  
  **Fix:** retain full precision, or round upward. If finite-sample false-alarm control is intended, use the `ceil((n + 1) × q)` order statistic, with an infinite threshold when that rank exceeds `n`.

  No additional finding for multiplicity or default seed separation: maxima cover series and checks, and calibration/evaluation seeds are disjoint. The documented held-out results reproduced: `1/150` without noise and `4/150` with noise.

**4. Generator gates, features, and baselines**

- **Medium — The impact gate can reject a complete outage because overdue open orders disappear.** [deliverytwin/benchmark/generator.py:158](deliverytwin/benchmark/generator.py:158), [generator.py:178](deliverytwin/benchmark/generator.py:178)  
  `_late()` includes only delivered or cancelled orders. Overdue open orders contribute nothing; missing rates and medians subsequently become zero. Consequently, selection can favor faults that produce completed outcomes over more severe faults that leave orders stranded.  
  **Reproduction:** seed `1`, horizon `360`, patience floor `500`, scarcity at `180` with offline fraction `0.999999`: no post-onset order is delivered, yet impact reports `global_p50=-30.487`, `global_late=-0.0429`, and the gate rejects the outage. These parameters pass validation.  
  **Fix:** compare a common, mature acceptance cohort and count overdue open orders as bad. Keep unavailable medians missing instead of substituting zero. This is the generator’s separate impact calculation, not the previously fixed laboratory metric.

- **Medium — Baseline evaluation includes its own training population.** [scripts/g2_report.py:125](scripts/g2_report.py:125), [g2_report.py:130](scripts/g2_report.py:130)  
  The majority label is learned from the training split, then every row—including training rows—is scored. The resulting accuracy and Wilson intervals do not establish held-out baseline performance.  
  **Reproduction:** with the published 60 L1 instances, reported rule-family accuracy is `39/60`; the actual test split yields `9/16`. The majority floor likewise mixes training and evaluation observations.  
  **Fix:** learn the majority label on training data and score all baselines on the same held-out instances, or explicitly label these numbers as training-inclusive development measurements.

- **Low — `open_share` can inspect outcomes after the requested alert time.** [deliverytwin/diagnostics/features.py:39](deliverytwin/diagnostics/features.py:39)  
  This feature checks whether outcome timestamps exist, without checking whether they precede `alert_t`. Supplying a longer telemetry history therefore reveals future completion status.  
  **Reproduction:** healthy seed `3`, alert time `240`: telemetry censored at `240` gives `open_share=0.3023256`; telemetry through `360`, evaluated at the same alert time, gives `0.0`.  
  **Fix:** consider an order open unless delivery or cancellation occurred by `alert_t`. Existing report callers truncate first, so this does not invalidate their current probe results.
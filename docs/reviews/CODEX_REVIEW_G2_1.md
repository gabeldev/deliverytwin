# Revisão independente (Codex CLI) — commit 3a7e506 (G2.1)

**Data:** 2026-11-01 · **Revisor:** Codex CLI 0.166 (`codex exec -s read-only`), conta do responsável · **Instruções:** foco em vazamento, pareamento, invariantes e estatística.

Saída original do revisor (caminhos convertidos para relativos). Verificação e correções: `docs/reports/G2_1_REPORT.md` §7.

---

Found six correctness issues. The two telemetry leakage paths predate this commit but remain exploitable.

1. **High — Leakage: public instance IDs reveal the hidden fault.** [generator.py:180](deliverytwin/benchmark/generator.py:180), [generator.py:206](deliverytwin/benchmark/generator.py:206)  
   Public IDs expose the level and generation index, while generation defaults to the public master seed `2026`. Consequently, `dataset_id="L2-0000"` alone deterministically reveals `dispatch_latency`: recompute the manifest seed and `"family"` draw. Regenerating that instance also recovers its world seed and fault parameters. The leak scanner cannot detect this indirect disclosure.  
   **Fix:** use private generation entropy for sealed benchmarks and independently generated opaque public IDs. Include an ID-only prediction check in leakage validation.

2. **Medium — Leakage: gauge ordering reveals raw restaurant IDs.** [build.py:99](deliverytwin/telemetry/build.py:99)  
   Kitchen gauges preserve the dictionary order established by sorting raw restaurant IDs. Thus, the first kitchen gauge identifies `r000`, the second `r001`, and so forth, despite opaque entity tokens. I reproduced recovery of every restaurant ID from public gauge positions.  
   **Fix:** serialize kitchen gauges in opaque-token order, and check serialization order as well as payload strings for leakage.

3. **High — Pairing: latency precomputes future attempts with the wrong replica seed.** [world.py:354](deliverytwin/simulation/world.py:354)  
   The latency loop draws its entire failure sequence immediately using one captured RNG. Error retries draw each attempt when it actually occurs. If the sequence crosses `t0`, identical `"dispatch_err"` keys therefore use different seeds between the two mechanisms.  
   **Reproduction:** seed `4`, onset `200`, probability `0.96`, fork at `230`, replica `1`: order `o-1-229-1` is assigned at `232.641` under errors versus `295.641` under latency. Error attempts 1–3 use the replica seed; latency attempts 0–66 were already drawn from the base seed. This breaks the intended coupling across the fork.  
   **Fix:** implement latency as asynchronous steps sampled at their actual step times, retaining the fixed dependency interval and caching each resolved attempt.

4. **Medium — Pairing: the 500-step cap forces an unresolved dependency to succeed.** [world.py:357](deliverytwin/simulation/world.py:357)  
   After 500 consecutive failures, the loop exits without observing success and queues the request as `latency_resolved=True`. Assignment proceeds while skipping the draw for attempt 500.  
   **Reproduction:** with probability `0.9999`, retry interval `0.01`, sufficient patience, seed `4`, and a 20-minute single-zone world, latency assigns six of seven orders; errors assign none. The first forced assignment’s attempt-500 draw still indicates failure. These parameter values pass validation.  
   **Fix:** preserve the unresolved state when a processing cap is reached; continue in chunks rather than treating the cap as success.

5. **Medium — Statistics: lab effects use a different, censored cohort from the one claimed.** [g21_pair_search.py:124](scripts/g21_pair_search.py:124)  
   `compute_kpis(..., t0)` includes every order created through `t0 + 150`; it does not implement the stated 90-minute creation window. Its late rate also includes only delivered orders, so treatment changes which orders enter the denominator.  
   **Reproduction:** candidate instance `50003` includes 15 control deliveries and 23 treatment deliveries from orders created after the supposed cohort endpoint. Applying the stated endpoint changes its measured effect from approximately `−0.1749` to `−0.1906`. The published aggregate therefore does not measure the documented cohort.  
   **Fix:** enforce an explicit creation-window endpoint, handle unresolved outcomes consistently across alternatives, and regenerate the lab results and report.

6. **Medium — Statistics: acceptance omits the required minimum sample size.** [g21_pair_search.py:162](scripts/g21_pair_search.py:162)  
   ADR-0005 amendment 2 requires both `n ≥ 300` and an upper confidence bound ≤ `0.60`; this gate checks only the confidence bound. Running candidate C on the first 150 configured instances produces an upper bound of `0.586` and is accepted by the code.  
   **Fix:** enforce both conditions and record insufficient sample size separately from rejection.

**Simulator invariants:** no correctness finding for cancellation versus pickup, courier double-assignment, or conservation.

**Additional checks:** exact replica-0 replay and identical pre-fork histories held for both new faults. I found no duplicate-key draw in the inspected dispatcher paths, calibration/evaluation seed overlap, or preprocessing leakage across CV folds. The default baseline finishes evaluation at minute 175, before the earliest default fault onset.

All **81 existing tests pass**; they do not cover the failures above.
# Revisão independente (Codex CLI) — G3 (commits 8469e5a e 2745ede)

**Data:** 2026-11-02 · **Revisor:** Codex CLI 0.166 (`codex exec -s read-only`), instruído a não ler `.env` nem chamar APIs · **Instruções:** `docs/reviews/codex_review_prompt_g3.txt`

Saída original (caminhos convertidos para relativos). Verificação e correções: `docs/reports/G3_REPORT.md` §7.

---

Reviewed both commits against HEAD. All 14 existing agent tests passed; additional offline probes exposed the findings below. No files were modified, `.env` was not read, and no external APIs were called.

**1. Leakage**

No confirmed findings in normal session responses or generated bundles. Alert details derive from public telemetry; query outputs respect the observability profile; lab responses expose aggregate intervention outcomes. I found no direct disclosure of hidden family, severity, onset, seeds, or raw restaurant identity.

**2. Lab and evaluator correctness**

- **Medium — Admission recommendations can improve the score by discarding demand.** [session.py:222](deliverytwin/agent/session.py:222), [evaluator.py:66](deliverytwin/benchmark/evaluator.py:66). Each arm measures its own accepted orders, excluding treatment rejections. Reproduction: `generate_instance("L0", 2)` with admission rate `0.1`, three replicas, reports bad rate **0.727 → 0.104**. In replica 1, control has 66 bad among 87 arrivals; treatment rejects 77 and has one bad among ten accepted. Counting rejected demand gives **78/87 unsuccessful orders**, yet the evaluator records a strong improvement. **Fix:** measure a shared demand cohort and report rejection/throughput alongside service outcomes, or explicitly penalize rejected demand.

- **Medium — A valid experiment can crash the investigation.** [session.py:231](deliverytwin/agent/session.py:231). Empty treatment cohorts produce NaNs that reach `statistics.stdev`. On `generate_instance("L2", 0)`, calling `experiment` with admission rate `1e-20` and two replicas raises uncaught `AttributeError: 'float' object has no attribute 'numerator'`. The action passes validation and already consumes the experiment budget. **Fix:** detect empty cohorts and return a controlled no-data/infeasible result before computing intervals.

- **Medium — The advertised 95% intervals are too narrow for 2–5 replicas.** [session.py:231](deliverytwin/agent/session.py:231). The calculation uses `1.96` with an estimated standard deviation despite the tiny sample. For L0 development instance 0, admission `0.1`, three replicas, the penalized-time difference is approximately **−6.84**, with reported interval **[−10.30, −3.37]**. A Student-t interval with two degrees of freedom is approximately **[−14.45, +0.77]**, changing whether zero is excluded. **Fix:** use a justified small-sample interval and preferably increase replica counts.

- **Medium — Recommendation evaluation reuses the investigation’s futures.** [evaluator.py:66](deliverytwin/benchmark/evaluator.py:66), [session.py:219](deliverytwin/agent/session.py:219). Both always use replica IDs `1..replicas`. An agent can test several actions and select whichever benefited most from those particular futures; its recommendation is then measured on the selection samples. Reproduction: L0 development instance 2, `AddCouriers(10)`, three replicas, gives **−0.238** both during investigation and during recommendation evaluation. **Fix:** use disjoint evaluator replica IDs, shared across compared agents.

- **Medium — Failed investigations receive a perfect Brier score.** [evaluator.py:63](deliverytwin/benchmark/evaluator.py:63), [llm_agent.py:155](deliverytwin/agent/llm_agent.py:155). Turn-limit exhaustion forces `cause=None, confidence=0`; the evaluator treats this as an incorrect diagnosis with predicted correctness zero and awards **Brier 0**. Consequently, an agent that never answers can outperform informative agents on the reported confidence metric. **Fix:** exclude abstentions/nonanswers from diagnosis-confidence calibration and report their coverage separately, or define a proper probability distribution including explicit abstention semantics.

- **Medium — Baselines bypass the purported common protocol.** [baselines.py:66](deliverytwin/agent/baselines.py:66), [baselines.py:78](deliverytwin/agent/baselines.py:78). Both baselines call `diagnose_rules` directly on complete raw public telemetry, spending zero queries. LLMs receive capped aggregate queries; some baseline features, such as censored-age shifts, are unavailable through those aggregations. The information access and query costs therefore differ despite the “same protocol” claim. **Fix:** expose equivalent evidence through the protocol and make baselines consume it, or explicitly report their different access privileges.

No additional findings in the exact family/scope comparison or edge-set F1 arithmetic. Evidence validity checks citation existence, not evidential support.

**3. Budget and secret safety**

- **Medium — The preflight estimate is not a worst-case token bound.** [llm.py:81](deliverytwin/agent/llm.py:81). `chars / 3` can underestimate token-dense input and does not explicitly account for model framing. A local fake-response reproduction with `"a1" * 1500` estimates **$0.00105095**, passes a **$0.0011** cap, then records **$0.00115** for 3,000 prompt and 2,500 completion tokens. That reproduction demonstrates the guard behavior; the token count was supplied locally rather than measured through an API. **Fix:** use a conservative model-specific token bound including tools/framing before admitting the request.

- **High — Concurrent clients can spend the same remaining budget.** [llm.py:88](deliverytwin/agent/llm.py:88). Reading spend, making the request, and appending cost are unsynchronized. Two clients can both pass before either writes its charge. Synchronized fake clients passed a **$0.0015** cap and recorded **$0.00201** combined. **Fix:** use interprocess locking and durable, atomic reservations before issuing requests; reconcile reservations afterward.

- **High — Unknown usage and accounting failures leave billable spend unreserved.** [llm.py:97](deliverytwin/agent/llm.py:97). Missing usage becomes `{}` and costs zero. A successful response followed by a ledger-write failure leaves no accounting entry; similarly, uncertain request failures have no retained reservation. Local fake probes repeatedly admitted responses after missing usage or failed ledger writes. **Fix:** reserve funds durably before the request, retain reservations for uncertain outcomes, and fail closed when usage cannot be reconciled.

- **Medium — Git-quoted filenames bypass the staged secret scan.** [check_secrets.py:30](scripts/check_secrets.py:30), [check_secrets.py:39](scripts/check_secrets.py:39). Without NUL-delimited output, Git quotes filenames containing non-ASCII characters, tabs, or newlines. The scanner passes that quoted representation literally to `git show`, ignores its failure, and scans empty stdout. A staged key in a filename such as `arquivo_á.txt` can therefore pass the pre-commit check. **Fix:** use `-z` filename output and reject unsuccessful blob reads.

No additional confirmed API-key disclosure finding in logs, bundles, ledger contents, or exception handling. Cached-input accounting is correct; reasoning tokens should remain included through total completion-token accounting.

**4. Statistics and claims**

- **Low — “Same answer” ignores restaurant scope and unresolved candidates.** [g3_report.py:107](scripts/g3_report.py:107). Agreement compares only `cause`. The final bundles contain a mini pair with the same restaurant-bottleneck family but different restaurant scopes, plus four luna abstention pairs with different unresolved sets. Comparing complete diagnoses gives **66.7% mini agreement and 65.0% luna agreement**, versus reported **68.3% and 71.7%**. **Fix:** compare cause plus relevant scope, or canonicalized unresolved sets for abstentions.

- **Medium — The universal 0.12 noise-floor claim is unsupported.** [G3_REPORT.md:45](docs/reports/G3_REPORT.md:45), [g3_report.py:99](scripts/g3_report.py:99). The threshold reflects a pooled observed accuracy difference from two runs, not an uncertainty bound or an estimated minimum detectable effect. Mini’s pooled difference is about **0.117**, while its L2 difference is **0.25**. Applying one threshold across models and levels hides that variation. **Fix:** estimate paired uncertainty per model × level with sufficient repetitions, or describe these numbers solely as observed repeat variability.

No findings in the Wilson or exact McNemar formulas. Regeneration in memory matched the committed report data, and all seven final runs contained 20 instances per level. No additional seed-hygiene finding was established; the claimed historical untouched status cannot be independently proved from the snapshot.
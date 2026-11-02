# DeliveryTwin AI

Simulation-grounded causal investigation and counterfactual intervention for last-mile logistics.

> **Simulated environment.** Nothing here represents a real delivery company, real couriers or real operational data.

**Interactive research preview:** https://deliverytwin-puce.vercel.app (follow an investigation, run counterfactual decisions, read the results). Source in [`site/`](site/).

A simulated delivery world hides an injected operational fault with a known causal structure. An investigator agent sees only telemetry and can run **paired counterfactual experiments** in a sandbox. An isolated evaluator scores the diagnosis, the reasoning path and the recommendation against the hidden ground truth.

```bash
uv sync
uv run python scripts/demo.py --level L2   # one investigation end to end, ~2 s, no GPU or API key
uv run pytest                              # determinism, replay, zero-difference, placebo, invariants
```

## Main findings (final seed 515151, n = 20 per level; details in the reports)

1. **Experiments matter when observation is not enough.** On L2, where the two candidate causes produce indistinguishable telemetry, removing the experiment tool from the fine-tuned model drops accuracy from 0.90 to 0.45. That is the coin-flip ceiling, and the drop is significant (p = 0.02). In G3, API LLMs reached 0.00–0.30 on L2, while a knowledge-based playbook that experiments reached 0.65.
2. **Paired replay is cheap variance reduction.** Event-keyed randomness makes a placebo intervention produce exactly zero difference. Pairing cuts the variance of a contrast by roughly 3–30× (median ratio 0.03–0.30 across 8 intervention types).
3. **A wrong twin hurts diagnosis.** Moving the lab from forks of the true world to a twin with perturbed parameters (δ = 0.1–0.5) lowered playbook accuracy on L2 from 0.65 to 0.40–0.45 in this sample (paired p = 0.06–0.13, not significant). The true-world benefit of its recommendations fell by about 45–63%. Changing only the twin's seed (δ = 0) cost nothing.
4. **A 1.7B model learns the protocol, plus a shortcut.**
   - QLoRA SFT of Qwen3-1.7B on 362 expert traces lifts L2 accuracy from 0.00 to 0.90. On the same L2 incidents it keeps 0.80 with a one-experiment budget and 0.95 with the imperfect twin, while the playbook drops to 0.35 and 0.45.
   - On L5 (L0 fault families, partial gauges) it never experiments and scores 0.40. The playbook reaches 0.65, and API LLMs reach 0.80–0.90 by experimenting on their own (exploratory, p ≤ 0.022 against the SFT). The same API LLMs score 0.00–0.30 on the constructed equivalent pair (L2/L4/L6). The working hypothesis, consistent with the data but not isolated by an ablation, is that the small model learned *when* to probe for each benchmark fault set, and the large ones know *why* to probe but not *which* intervention separates the pair.
   - It loses general ability (strict GSM8K accuracy 0.61 → 0.14).
5. **Diagnosis is the main bottleneck within this action space.** Given the true family, a fixed per-family remedy has a mean regret of 0.043 against a common oracle (menu plus every feasible agent recommendation), well ahead of every agent except gpt-5-mini. 19 of 60 gpt-5-mini recommendations cut admission to 0.5–0.7. That fails a feasibility screen the agents were never told about, and it also worsens the true-world bad-order rate.

Every comparison is labelled principal (pre-registered) or exploratory. Refuted predictions are reported as refuted (G5 §3.2).

## Status by gate (RFC §11)

| Gate | Status | Report |
|---|---|---|
| G0 Specification | done | [`ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md), ADR-0001…0006 |
| G1 Simulator verification | done | [`G1_REPORT.md`](docs/reports/G1_REPORT.md) |
| G2 / G2.1 Benchmark, real-data calibration (Grubhub MDRP) | done | [`G2_REPORT.md`](docs/reports/G2_REPORT.md), [`G2_1_REPORT.md`](docs/reports/G2_1_REPORT.md) |
| G3 Investigator, lab, evaluator, LLM agents | done | [`G3_REPORT.md`](docs/reports/G3_REPORT.md) |
| G4 Adapted model (Qwen3-1.7B QLoRA) | done; adapter public on [Hugging Face](https://huggingface.co/gabeldev/deliverytwin-investigator-qwen3-1.7b-lora) | [`G4_REPORT.md`](docs/reports/G4_REPORT.md), [`MODEL_CARD.md`](docs/model/MODEL_CARD.md) |
| G5 Intervention research, twin lab, L3–L6 ladder | done (pre-registered) | [`G5_REPORT.md`](docs/reports/G5_REPORT.md), [`PREREG_G5.md`](docs/methods/PREREG_G5.md) |
| G6 Public release | released 2026-11-02: clean public snapshot at [gabeldev/deliverytwin](https://github.com/gabeldev/deliverytwin) (Apache-2.0, without internal commercial documents) and the adapter on Hugging Face. **This repository stays private** (full history and commercial material) | [`LIMITATIONS.md`](docs/LIMITATIONS.md), [`DATASET_CARD.md`](docs/DATASET_CARD.md) |

Every milestone was checked by an independent reviewer (Codex CLI). The findings were reproduced before fixing and each fix has a regression test: [`docs/reviews/`](docs/reviews/).

## Difficulty levels

| Level | What changes | What it tests |
|---|---|---|
| L0 | Full gauges; courier scarcity, dispatcher saturation or restaurant bottleneck | Reading observational evidence |
| L1 | L0 with telemetry noise | Robustness to noise |
| L2 | Two causes with identical telemetry (dispatch error surge vs dependency latency) | Needs an experiment (retry backoff separates them) |
| L3 | A global fault plus a restaurant bottleneck; the answer is the primary fault | Compound faults |
| L4 | L2 with 8 queries, 1 experiment, 1.0 cost unit | Experiment selection under budget |
| L5 | L0 families, partial gauges (no courier or dispatch-queue gauges) | Observability gap (defeats observational rules; equivalence not probe-verified as on L2) |
| L6 | L2 with an imperfect twin lab (δ = 0.25) | Model-mismatch in the sandbox |

## Reproduce

```bash
# G3 baselines and agents (rules / playbook are CPU-only and free)
uv run python scripts/run_g3.py --agent playbook --levels L0,L1,L2 --n 20 --seed final --tag fix
uv run python scripts/g3_report.py
# G4 (needs a CUDA GPU with >= 4 GB; see the model card)
uv run --group train python scripts/g4_build_dataset.py
uv run --group train python scripts/g4_train.py
# G5
uv run python scripts/g5_interventions.py
uv run python scripts/run_g3.py --agent playbook --levels L2 --n 20 --seed final --twin-delta 0.25 --tag twin0.25
uv run python scripts/g5_names_only.py
uv run python scripts/g5_report.py
```

API agents (`--agent llm`) need an OpenAI key in `.env`, which is git-ignored. The client enforces a hard spending cap (`DELIVERYTWIN_LLM_BUDGET_USD`) through an append-only ledger. Seeds: development 2026 (all tuning and training data), eval 909090, final 515151 (all reported numbers).

## Documents

| Document | Contents |
|---|---|
| [`DeliveryTwin_RFC_001.md`](DeliveryTwin_RFC_001.md) | Research specification (rev. 2) |
| [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) | Architecture and scope |
| [`docs/decisions/`](docs/decisions/README.md) | Architecture decision records ADR-0001…0012 |
| [`docs/methods/`](docs/methods/) | Literature review, G5 pre-registration |
| [`docs/reports/`](docs/reports/) | Gate reports G1–G5 with their JSON data |
| [`docs/model/MODEL_CARD.md`](docs/model/MODEL_CARD.md) | Fine-tuned adapter card (not published) |
| [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md) | Benchmark card (generated, not published) |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | Consolidated limitations and threats to validity |
| [`docs/reviews/`](docs/reviews/) | Independent review findings and fixes |
| [`docs/architecture/DESIGN_SYSTEM.md`](docs/architecture/DESIGN_SYSTEM.md) | Dashboard design system |

## License

Decided in [ADR-0013](docs/decisions/ADR-0013-licensing-split.md): the benchmark and the fine-tuned adapter will be released under **Apache-2.0**, and the simulator and lab follow an **open-core** model: this repository (synthetic world, faults, lab, benchmark, evaluator, agents) is the open part under Apache-2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)), and real-data ingestion, customer-twin calibration, dashboard and managed service will live in a separate proprietary repository. The repository is still private; making it public is the owner's call. Third-party material keeps its own terms: Grubhub MDRP instances (calibration only, not redistributed), Dolly-15k (CC BY-SA 3.0, training replay), GSM8K (MIT, evaluation) and Qwen3 (Apache-2.0).

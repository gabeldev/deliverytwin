# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated by the owner ("não quero impor uma stack"); decided in `site/DECISIONS.md` and hosted on Vercel (owner's CLI, deploy authorized 2026-11-02). The research core stays Python (`deliverytwin` package); the public site is a separate web app under `site/`.

## Users

- **Operations leaders and engineers at delivery/logistics companies** evaluating whether evidence-backed incident investigation and counterfactual "what if" testing could help their operation. They arrive without background in simulation, causal inference or LLMs.
- **Researchers and ML engineers** (agents, causal inference, simulation, evaluation) who want the method, numbers, uncertainty and reproducibility.
- **Potential partners** (software vendors, research groups) looking for a professional way to start a conversation.

Language: English by default with a Portuguese version (owner decision, 2026-11-02).

## Product Purpose

DeliveryTwin AI investigates the question: **what is causing an operational problem, and what would happen if we made a different decision?** A simulated delivery world hides an injected fault. An investigator agent sees only telemetry, forms hypotheses, runs paired counterfactual experiments in a sandbox lab and submits a diagnosis with a recommendation. An isolated evaluator scores it against the hidden truth. The public site lets anyone follow such an investigation, run interventions and inspect the evidence and research results.

Success for a visitor: they understand the problem, see the technology working on real simulator output, and can imagine its use in a real operation, while knowing exactly what has and has not been validated.

## Positioning

The difference is not "an AI that answers logistics questions". It is a system that **investigates, tests hypotheses with paired counterfactual experiments, compares decisions and makes its conclusions examinable**, with every claim traceable to a run and every limitation stated. Its results include refuted predictions and failure modes, and it publishes them.

## Operating Context

- Synthetic grid city: 3 zones, 10 restaurants, 56 couriers, a dispatcher with workers, a 240-minute horizon. Fault families: courier scarcity, dispatcher saturation, restaurant bottleneck, dispatch error surge, dispatch latency.
- Agent tools: `query_orders`, `query_gauges`, `hypothesize`, `experiment`, `submit`, all with budgets.
- Interventions supported by the simulator: add couriers, dispatcher workers, retry backoff, dispatch policy (nearest / eta_aware), admission rate, placebo.
- Lab mode A (forks of the true world) and mode B (imperfect twin, δ).
- Difficulty levels L0–L6 (see README).

## Capabilities and Constraints

- Everything is **simulated**; nothing is validated in a real operation. No customers, pilots, savings or market validation exist and none may be implied.
- Public demo scenarios use only the public development seed (2026). Evaluation seeds and hidden labels are never shown before an investigation is submitted; the "hidden truth" view is a separate, labelled reveal.
- Recorded agent sessions (deterministic playbook, Qwen3-1.7B base/SFT, gpt-5-mini, gpt-5.6-luna) are shown as **recordings**, never as live LLM execution.
- Counterfactual results shown on the site come from the real simulator (precomputed and labelled, or computed on demand), never from illustrative numbers.
- Confidential commercial strategy documents must never appear on the site (guard: `scripts/check_secrets.py --dir <dir> --public`).

## Brand Commitments

- Name: **DeliveryTwin AI**. Independent project of its owner (gabeldev); no institutional affiliation may be stated.
- The epistemic status system in `docs/architecture/DESIGN_SYSTEM.md` (observation, hypothesis, assumption, experiment, recommendation, hidden truth: colour + icon + label, never colour alone) is a binding product requirement.
- License: Apache-2.0 (code, benchmark, adapter). Code: https://github.com/gabeldev/deliverytwin. Adapter: https://huggingface.co/gabeldev/deliverytwin-investigator-qwen3-1.7b-lora.

## Evidence on Hand

- Gate reports G1–G5 with JSON data (`docs/reports/`), pre-registration (`docs/methods/PREREG_G5.md`), independent review records (`docs/reviews/`), limitations (`docs/LIMITATIONS.md`), model and dataset cards.
- The simulator itself, which can regenerate every demo scenario and experiment.
- **Absent and never to be fabricated:** testimonials, customer logos, case studies, press, publications, pricing, operational savings, real-world accuracy.

## Product Principles

1. Show the process, not just the answer: observations, hypotheses, experiments and conclusions stay distinguishable.
2. Every number is traceable to a run, a seed and a command.
3. Uncertainty and limitations are part of the product, not footnotes.
4. Simulation is labelled as simulation everywhere.
5. Ambitious but verifiable: say what was demonstrated, what is in development, and what still needs real-world validation.

## Accessibility & Inclusion

WCAG 2.x AA contrast, visible focus, full keyboard operation, status never conveyed by colour or motion alone, `prefers-reduced-motion` respected (DESIGN_SYSTEM §6).

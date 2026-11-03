# Provenance of the site data

The interactive site (`site/`) shows precomputed results. Each result is labelled with a commit and a command.

| Item | Value |
|---|---|
| Data files | `site/public/data/scenarios/*.json`, `site/public/data/research.json` |
| Public snapshot that regenerates them | `gabeldev/deliverytwin@670384d` |
| Command | `uv run python scripts/site_export.py` (5 scenarios, dev seed 2026, replicas 3001–3020) |
| Check performed (2026-11-03) | Re-exported from a clean copy of the public snapshot: all 11 scenario files are byte-identical to the published ones, apart from the provenance label. |

## History

The files were first exported from a development commit (`ab46db9`) that is not part of the public history; the
simulator code there is identical to the public snapshot. The label on the site now points to the public commit,
which anyone can check out.

## What is and is not reproducible from the public repository

- **Reproducible:** the world, telemetry, every lab result (modes A and B, all arms and the placebo), the
  deterministic playbook session and every evaluator verdict.
- **Not regenerated, replayed:** the recorded language-model sessions (Qwen3-1.7B base and fine-tuned, gpt-5-mini,
  gpt-5.6-luna). They are recordings of single runs from different project stages (API models: G3 runs; Qwen:
  G4 runs). The exporter reads them from run bundles that are not published. They illustrate behaviour and are
  not a controlled comparison; the controlled comparisons are in `docs/reports/`.

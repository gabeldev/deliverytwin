# Revisão independente (Codex) dos relatórios G4/G5 e da documentação G6

**Data:** 2026-11-02 · **Revisor:** Codex CLI (`codex exec -s read-only`), com o prompt em `codex_review_prompt_reports.txt` · **Escopo:** afirmações de G4_REPORT, G5_REPORT, MODEL_CARD, README, LIMITATIONS, DATASET_CARD e PREREG_G5, conferidas contra os dados e o código.

Cada achado foi reproduzido antes da correção: recalculado a partir dos dados ou lido no código.

| # | Sev. | Achado | Verificação | Correção |
|---|---|---|---|---|
| 1 | Alta | L4 e L6 usam incidentes diferentes dos do L2, porque o nome do nível entra nas sementes. A comparação L2 → L6 mistura a troca de laboratório com a troca de amostra | Confirmado: 0 ids em comum; composição 11/9 no L2, 8/12 no L4, 12/8 no L6 | Nova opção `--budgets-of` em `run_g3.py`. Todos os agentes locais foram rodados nos incidentes do L2 com o orçamento do L4 e com o gêmeo δ = 0,25. Os L4/L6 originais ficam como amostras independentes (G5 §3) |
| 2 | Média | O arrependimento usava como referência o cardápio mais a recomendação do próprio agente | Confirmado no código; números reproduzidos (remédio 0,013 → 0,043) | `regret_vs_common_oracle` com referência comum. A métrica antiga continua no JSON com o nome correto (G5 §1.3) |
| 3 | Média | A restrição de 20% de rejeição nunca foi passada aos agentes | Confirmado (prompt e `observe`) | Texto sobre restrição "ignorada" retirado. Agora é um filtro aplicado depois |
| 4 | Média | A viabilidade foi checada no parâmetro de admissão, não na rejeição observada | Confirmado: 25 de 60 incidentes acima de 20%, máximo 21,6% | Documentado (G5 §1.1). Sem efeito nas contagens |
| 5 | Média | O veredito de H7 reinterpretava o critério registrado | Confirmado: 31 razões ≥ 1 em 6 tipos | Veredito "parcial" |
| 6 | Média | Números e interpretação errados na seção de nomes (H10) | Confirmado | Tabela com a base "maioria do treino"; sem alegação de ausência de vazamento |
| 7 | Média | Gêmeo descrito como "monotônico" e "metade ou mais" | Confirmado: p = 0,125, 0,125 e 0,063; queda de 45–63% | Texto corrigido |
| 8 | Média | Sem sonda, não está demonstrado que o L5 exija experimento | Confirmado | Declarado no relatório, no README, nas limitações e no cartão do dataset |
| 9 | Média | "Nunca experimenta sem medidores" é falso fora do L5; o atalho é hipótese, não fato | Confirmado: 1,7 experimento por episódio no L2 e 1,9 no L6 | Restrito ao L5; atalho descrito como hipótese apoiada |
| 10 | Média | O comando documentado não reproduz o conjunto de treino (padrão 4096 contra 4608 registrado) | Confirmado | Padrão do script mudado para 4608 |
| 11 | Média | Rótulos "principal" fora do pré-registro do G5 | Confirmado | Rótulos `g4_main_not_preregistered` e `component_of_H2` |
| 12 | Média | A métrica do último número no GSM8K ainda mistura formato com cálculo | Confirmado com um exemplo | Perda de raciocínio descrita como "provável" |

Afirmações conferidas e mantidas pelo revisor: tabelas e ICs do G4/G5, McNemar de H1/H9 e do Estudo 3(a), refutação de 3(b), agregado de intervenções reproduzido exatamente, contagens do GSM8K, ausência de vazamento na demo.

Erro adicional achado na própria verificação: "25 incidentes" com ações melhores fora do cardápio eram, na verdade, 16 incidentes (25 recomendações).

## Revisão original

Reviewed read-only, excluding `.env`, `runs/llm_ledger*`, and the pending G5 §6.

1. **High — L6 changes the incidents as well as the laboratory.** [G5_REPORT.md:126](docs/reports/G5_REPORT.md:126), [generator.py:220](deliverytwin/benchmark/generator.py:220).  
   **Claim:** L6 measures performance on L2 instances with an imperfect twin, as registered in PREREG §2.  
   **Evidence:** The generator includes the level in every seed derivation. L2 has 11 error-surge / 9 latency incidents; L6 has 12 / 8, with different dataset IDs and worlds. Consequently, SFT 0.90→0.95 and playbook 0.65→0.50 do not isolate the lab change. The actual matched L2 sweep gives playbook **0.45** at δ=0.25.  
   **Fix:** Reuse L2 instances and change only the session’s lab. Until then, describe L6 as a separate sample and disclose the deviation from registration.

2. **Medium — “Best feasible action” uses a different oracle for each agent.** [G5_REPORT.md:57](docs/reports/G5_REPORT.md:57), [g5_interventions.py:199](scripts/g5_interventions.py:199).  
   **Claim:** Regret compares recommendations against the best feasible action.  
   **Evidence:** The comparator is the menu **plus that agent’s own recommendation**. Fourteen mini recommendations and eleven luna recommendations outperform the menu and receive zero regret. Using one common oracle containing all observed feasible recommendations changes playbook’s mean from **0.1377→0.1685**, SFT’s **0.1591→0.1899**, and the true-family remedy’s **0.0126→0.0434**.  
   **Fix:** Document the current metric as clipped shortfall against the menu, or use a common action set. Qualify “diagnosis is the bottleneck” as dependent on this restricted menu.

3. **Medium — The agents were never given the business constraint they allegedly ignored.** [G5_REPORT.md:68](docs/reports/G5_REPORT.md:68), [session.py:144](deliverytwin/agent/session.py:144).  
   **Claim:** Mini achieves its objective while ignoring business constraints, demonstrating unsafe behavior.  
   **Evidence:** Neither the system prompt nor `observe()` supplies the 20% rejection limit. G5 applies this screen to existing G3 recommendations. **The count itself checks out:** 19/60 recommendations fail the screen, and all nineteen worsen Δbad.  
   **Fix:** Say “19 recommendations failed the subsequently applied feasibility screen.” Supply the constraint explicitly before making claims about instruction compliance.

4. **Medium — Feasibility checks configured admission probability, not actual rejection.** [G5_REPORT.md:57](docs/reports/G5_REPORT.md:57), [g5_interventions.py:101](scripts/g5_interventions.py:101).  
   **Claim:** Feasible actions reject at most 20% of demand.  
   **Evidence:** `feasible()` checks only `rate >= 0.8` and cost. Admission is Bernoulli: admission=0.8 produces a mean rejected fraction above 0.20 in **25/60 incidents**, reaching **0.2164**.  
   **Fix:** Specify that the registered constraint concerns **expected rejection probability**, or evaluate the observed rejection constraint explicitly. Admission=0.8 never wins here, so this ambiguity does not change the reported best-action counts.

5. **Medium — H7/H4 is not unambiguously confirmed under the registered wording.** [G5_REPORT.md:53](docs/reports/G5_REPORT.md:53), [PREREG_G5.md:18](docs/methods/PREREG_G5.md:18).  
   **Claim:** The prediction is confirmed by interpreting its first condition through medians.  
   **Evidence:** Registration separately requires “ratio <1 for all types” and “median <0.5 in at least half,” without defining median aggregation for the first condition. There are **31 ratios ≥1 across six types**, including **12/60** for workers=6. All eight reported medians do check out and satisfy the median condition.  
   **Fix:** Report the median condition as supported; identify the first condition’s aggregation as underspecified and its incident-level reading as unmet. Do not call the median interpretation itself registered.

6. **Medium — The names-only section contains numerical and interpretive errors.** [G5_REPORT.md:141](docs/reports/G5_REPORT.md:141), [DATASET_CARD.md:45](docs/DATASET_CARD.md:45).  
   **Claim:** Accuracy is always within 0.05 of the majority class, never exceeds it, and establishes that identifiers reveal no cause information.  
   **Evidence:** L1 is **0.40 versus 0.50**, a difference of **0.10**. L0 is **0.20 versus 0.15**, exceeding the reported baseline. Moreover, “majority” means the **training-majority classifier**: actual final-sample majority shares are **0.45/0.50/0.55**, not 0.15/0.50/0.45.  
   **Fix:** Name the baseline accurately and say this classifier showed no advantage greater than 0.05 over it. The registered sample threshold passes; that does not certify absence of leakage.

7. **Medium — The twin headline overstates both magnitude and generality.** [README.md:19](README.md:19), [G5_REPORT.md:83](docs/reports/G5_REPORT.md:83).  
   **Claim:** A wrong twin degrades diagnosis monotonically and cuts recommendation benefit by half or more.  
   **Evidence:** Benefit falls from **0.0991** to **0.0537/0.0541/0.0371**: reductions of approximately **46%/45%/63%**. Accuracy is non-increasing in this particular sweep, but paired comparisons give **p=0.125, 0.125, 0.0625**, before multiplicity correction.  
   **Fix:** Report the observed sample trend and “about 45–63% less benefit”; avoid presenting monotonic degradation as an established general law.

8. **Medium — L5 has not been shown to require experiments.** [README.md:51](README.md:51), [PREREG_G5.md:34](docs/methods/PREREG_G5.md:34).  
   **Claim:** Removing fleet and dispatch gauges makes the causes observationally inseparable.  
   **Evidence:** L5 has no equivalence probe comparable to L2. Its public order records retain assignment, preparation, and pickup timestamps. The rules explicitly abstain when the profile is not `full`; playbook outperforming those rules demonstrates improvement over that policy, not an information limit.  
   **Fix:** Say the missing gauges defeat the implemented observational rules. Establish observational inseparability separately before claiming experiments are necessary.

9. **Medium — The missing-gauges claim is false outside L5, and the shortcut explanation is stronger than the experiment establishes.** [README.md:22](README.md:22), [G4_REPORT.md:45](docs/reports/G4_REPORT.md:45).  
   **Claim:** SFT “never experiments when gauges are missing” and learned when to probe, not why.  
   **Evidence:** It runs **1.7 experiments/episode on L2** and **1.9 on L6**, both without gauges. Zero experiments is specific to L5. The behavior is consistent with a profile shortcut, but no training-selection or profile-randomization ablation isolates its cause.  
   **Fix:** Restrict the observation to L5 and describe the shortcut explanation as a supported hypothesis.

10. **Medium — The documented training command does not reproduce the recorded dataset.** [MODEL_CARD.md:65](docs/model/MODEL_CARD.md:65), [g4_build_dataset.py:37](scripts/g4_build_dataset.py:37).  
    **Claim:** Running the supplied commands reproduces the 362/132 trace dataset.  
    **Evidence:** The script defaults to **4096 tokens**; the recorded dataset used **4608**. The supplied artifacts contain **58 training and 19 validation traces above 4096**, all L2. The documented default would discard those recorded examples.  
    **Fix:** Add `--max-len 4608` to both the model card and README reproduction commands.

11. **Medium — “Principal” labels do not consistently identify the registered predictions.** [g5_report.py:81](scripts/g5_report.py:81), [g5_report.py:96](scripts/g5_report.py:96).  
    **Claim:** Principal comparisons correspond to G5 pre-registered predictions.  
    **Evidence:** G4 SFT-versus-base tests are labeled principal although PREREG_G5 does not register those tests. The principal L5 SFT-versus-base test, **p=0.0078**, tests whether improvement exists—not H2’s prediction that improvement **shrinks** relative to L0–L2.  
    **Fix:** Distinguish previously planned G4 evaluations from G5 registration. Label the standalone L5 contrast as a component comparison, not a test of contraction.

12. **Medium — The exploratory GSM8K extractor does not fully separate arithmetic loss from formatting effects.** [G4_REPORT.md:69](docs/reports/G4_REPORT.md:69), [gsm8k_responses.json:1077](runs/g4/gsm8k_responses.json:1077).  
    **Claim:** The last-number metric forgives formatting and establishes a 22-point arithmetic-reasoning loss.  
    **Evidence:** Both reported score drops reproduce. But one SFT answer correctly computes **8 centimeters**, then mentions “5:00 PM”; the heuristic extracts **0** and marks it wrong. Thus the exploratory metric still confounds answer presentation with mathematical correctness.  
    **Fix:** Keep the measured score drops; qualify the attribution to arithmetic reasoning, or independently adjudicate semantic answers.

The following claims **check out**:

- G4 and G5 accuracy tables, Wilson intervals, and reported exact McNemar calculations reproduce from the result rows. H1/H9 is **18/20 versus 9/20**, discordances **11:2**, **p=0.02246**.
- Study 3(a) is supported: **13/20 versus 6/20**, **7:0**, **p=0.015625**. Study 3(b) is correctly reported as refuted. H2’s pooled gain decreases **0.5667→0.40**, while L0 and L1 gains remain 0.40; registration did not specify aggregation, so an inconclusive verdict is defensible.
- The intervention aggregate exactly reproduces from `interventions_rows.json`, including best-action counts, variance summaries, placebo zero flags, and mean Pareto size **2.8167**. Study 2 satisfies its registered descriptive tolerance.
- GSM8K counts reproduce: strict **91/150→21/150**; last-number **101/150→67/150**; unparsable **19→116**.
- The demo explicitly uses seed **2026** and reveals truth after submission. The dataset card and limitations correctly acknowledge that the disclosed evaluation seeds are no longer sealed.
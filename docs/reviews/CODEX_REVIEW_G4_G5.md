# Revisão independente (Codex CLI) — G4 e G5 (commits a6d2514, b02d900, cd54bc0)

**Data:** 2026-11-02 · **Revisor:** Codex CLI 0.166 (`codex exec -s read-only`), instruído a não ler `.env`, não chamar APIs e não carregar o modelo na GPU · **Instruções:** `docs/reviews/codex_review_prompt_g4_g5.txt`

## Correções (todas reproduzidas antes de corrigir; regressões em `tests/agent/test_review_g4_g5.py`, que falham no código anterior)

| # | Gravidade | Achado | Correção | Efeito nos resultados |
|---|---|---|---|---|
| 1 | Média | Argumentos de ferramenta com formato errado (lista) derrubavam a avaliação local | Chamada só é aceita como `{"name": str, "arguments": objeto}`; o laço do agente também recusa argumentos que não são objeto | Nenhuma execução tinha caído; proteção para as próximas |
| 2 | Média | Extração de resposta do GSM8K perdia sinal, aceitava `1e3` e pontuava números soltos do raciocínio | Só a última linha `Answer:` conta; formato numérico estrito; sem resposta = erro; respostas salvas para auditoria | Corrigido **antes** da execução do GSM8K |
| 3 | Baixa | Último lote parcial de acumulação de gradiente descartado | Lote final aplicado com normalização correta | O treino registrado (904 microlotes, múltiplo de 8) não foi afetado |
| 4 | **Alta** | L3: a família primária sobrescrevia a família sorteada, e uma nova tentativa podia gerar dois gargalos de restaurante (ex.: L3 #7 final) | Família sorteada imutável; primária guardada à parte | Instâncias L3 mudaram; L3 refeito (`*_final_g5l3`) |
| 5 | **Alta** | L3: reordenar as falhas mudava a aleatoriedade da falha no replay do laboratório | Ordem de injeção preservada (`injected_faults`); primária separada da ordem de execução | Idem |
| 6 | Média | Agentes no L3 não sabiam que a resposta pontuada é a falha primária | Nota de tarefa no `observe` só do L3; texto do L0–L2 inalterado | Idem |
| 7 | Média | Arrependimento comparava recomendações fora do cardápio com um oráculo restrito ao cardápio, e recomendações inviáveis (admissão < 0,8) passavam | Oráculo = cardápio ∪ recomendação viável (arrependimento ≥ 0); inviáveis contadas à parte | Estudo 1 refeito |
| 8 | Média | Pacote ausente sumia do denominador | Ausente ≠ no-op; cobertura por nível e marca de completude | Estudo 1 refeito após todas as execuções locais |
| 9 | Média | Contraste não pareado invertido em relação ao pré-registro | Controle r × tratamento r+1, como registrado | Razões de variância recalculadas |
| 10 | Média | Ablação H1/H9 só zerava o orçamento; a ferramenta continuava anunciada | Ferramenta removida do esquema e do despachante; condição registrada no resultado | Execução sem experimento feita já com a correção |
| 11 | Média | Comparação não executada aparecia como p = 1 | `status = not_run` e p nulo; `incomplete` quando a cobertura difere | Relatório |
| 12 | Baixa | H10 sem IC e sem contagens; comparações sem rótulo principal/exploratória | Contagens e Wilson; rótulo em toda comparação | Relatório |
| 13 | Média | Falha do gerador abortava o estudo sem registro | Falhas registradas, nunca substituídas; marca `complete` | Estudo 1 |

Sem achados de vazamento para o modelo: os traços usam só telemetria pública e resultados de laboratório; nenhuma instância da semente final chega ao treino; o gêmeo não expõe s\*. Observação aceita: o JSONL de treino guarda a família como metadado (não consumido pelo treinador); o arquivo fica fora do git.

## Revisão original

Two high-severity regressions affect L3: retries can generate two restaurant faults, and selecting the primary fault can change the world replayed by the lab.

Reviewed all three requested commits and current files, including the untracked `g5_report.py`. Verification used CPU probes, the cached tokenizer, and 13 relevant tests, which passed. No files were modified, `.env` was not read, no external APIs were called, and no Qwen model was loaded.

**1. Leakage and contamination**

No model-input leakage findings.

- Expert decisions use public telemetry and experiment results; the private alert time used by the expert is also disclosed by `observe`.
- Dataset construction fixes the development seed at `2026`; I found no path that inserts final-seed `515151` instances into training.
- The JSONL does contain private `family` metadata at [g4_build_dataset.py:62](scripts/g4_build_dataset.py:62), but the trainer consumes only `input_ids` and `mask`. Thus, the artifact contains a private label, while the current model inputs and loss targets do not consume that metadata.
- I found no direct disclosure of private family, severity, onset, world seed, or raw restaurant identity through the new session surfaces. Twin seed derivation and perturbation do not expose `s*`.

**2. Training correctness**

1. **Medium — Malformed local tool arguments can abort evaluation.**  
   [local_llm.py:28](deliverytwin/agent/local_llm.py:28)

   Parsing validates JSON syntax but accepts any argument type. For example:

   ```python
   parse_tool_calls(
       '<tool_call>{"name":"query_orders","arguments":[]}</tool_call>'
   )
   ```

   This produces a tool call that subsequently crashes `run_llm_agent` with `TypeError: 'list' object is not a mapping`, instead of returning a tool error. A malformed generation can therefore terminate an evaluation run.

   **Fix:** Validate the tool name and require an argument object before constructing the call. Convert invalid shapes into the existing malformed-tool error path.

2. **Medium — GSM8K extraction can change an answer’s meaning.**  
   [g4_general_check.py:46](scripts/g4_general_check.py:46)

   Reproduced:

   ```python
   predicted("Answer: -$12")  # "12": sign lost
   predicted("Answer: 1e3")   # "1": numeric prefix accepted
   predicted("Need to divide by 42")  # "42": no final answer required
   ```

   The fallback also scores an incidental reasoning number when generation ends without an answer. These errors can change correctness flags and therefore the paired McNemar result.

   **Fix:** Parse a complete final-answer field, reject unsupported trailing numeric syntax, preserve currency/sign ordering, and distinguish missing or truncated answers from valid predictions. Retain generated responses for auditing.

3. **Low — The final incomplete accumulation batch is discarded.**  
   [g4_train.py:136](scripts/g4_train.py:136)

   Optimization happens only when `micro % accum == 0`; remaining gradients are never applied before saving. With the existing 452 examples, `--epochs 1` performs 56 updates and discards four examples’ gradients, despite scheduling 57 updates. A sufficiently small `--max-train` run can save an adapter without any optimizer update.

   **Fix:** Flush and correctly normalize the final partial accumulation batch. The recorded two-epoch run has 904 microbatches, divisible by eight, so this does not invalidate that particular run.

No additional findings in assistant-only masking, THINK normalization, compact-tool consistency, or `target_loss` indexing. Cached-tokenizer probes confirmed train/inference prefix consistency; a tiny CPU model confirmed equivalence to shifted, masked cross-entropy. Dolly train/evaluation slicing is disjoint, but its NLL measures retention on the replay distribution, not general absence of forgetting. The exact McNemar implementation itself is correct.

**3. Lab and study correctness**

4. **High — L3 primary selection mutates the family used by later generation attempts.**  
   [generator.py:243](deliverytwin/benchmark/generator.py:243)

   `family` is sampled before the retry loop, then overwritten with the selected primary family. If a restaurant-primary attempt subsequently fails a detection/attribution gate, the next attempt samples a restaurant as the supposed global fault and adds another restaurant fault.

   This occurs in the registered final set:

   ```python
   from deliverytwin.benchmark.generator import generate_instance

   p = generate_instance("L3", 7, master_seed=515151).private
   print(p.attempts, p.family, p.extra_faults[0]["family"])
   # 2 restaurant_bottleneck restaurant_bottleneck
   ```

   **Fix:** Keep the originally sampled global family immutable across attempts. Store the selected primary family separately.

5. **High — Reordering L3 faults changes stochastic fault realization during lab replay.**  
   [generator.py:242](deliverytwin/benchmark/generator.py:242), [session.py:249](deliverytwin/agent/session.py:249)

   The observed world runs faults in their original order. The private record stores them reordered as primary first, and the lab reconstructs that order. Courier-offline randomness includes the fault’s tuple index, so moving courier scarcity from index zero to index one changes which couriers went offline.

   Reproduced on final L3 index 8:

   ```python
   from deliverytwin.agent.session import instance_faults, _world_for_lab
   from deliverytwin.simulation.world import World

   i = generate_instance("L3", 8, master_seed=515151)
   fs = instance_faults(i)
   original = World(i.world_config, i.private.world_seed,
                    faults=fs[::-1], noise=i.noise).run()
   lab = _world_for_lab(i, i.private.alert["t"]).run()
   offline = lambda w: {e["cid"] for e in w.log.events
                        if e["ev"] == "courier_offline"}
   assert offline(original) == offline(lab)  # fails
   ```

   Thus, mode A and recommendation evaluation can replay a different pre-alert incident.

   **Fix:** Preserve injection order or persist stable fault identities used by RNG keys. Represent primary attribution separately from execution order.

6. **Medium — L3 agents are not told the task they are scored on.**  
   [llm_agent.py:14](deliverytwin/agent/llm_agent.py:14), [session.py:129](deliverytwin/agent/session.py:129)

   The system prompt says “exactly one is active,” while L3 contains two faults. Neither it nor `observe` explains that the required answer is the fault with the larger isolated global bad-rate impact. An agent correctly identifying both mechanisms is given instructions inconsistent with the scoring contract.

   **Fix:** Add L3-specific public task instructions describing coexistence, primary selection, scope, and secondary reporting. Preserve the existing L0–L2 text.

7. **Medium — Reported regret compares recommendations against a different action set.**  
   [g5_interventions.py:112](scripts/g5_interventions.py:112), [g5_interventions.py:150](scripts/g5_interventions.py:150)

   The oracle minimizes over the eight menu actions, but agent recommendations may use arbitrary protocol-valid parameters. Consequently, “regret” can be substantially negative because the recommendation buys more resources than the oracle is allowed to consider.

   Existing rows contain 25 negative agent–incident regrets. For final L0 index 0, GPT-5-mini recommends 20 couriers: its effect is approximately `-0.3584`, versus menu best `-0.1265`, producing regret `-0.2319`. Recommendations with admission rates `0.5–0.7` also pass through despite the registered 20% rejection restriction.

   **Fix:** Enforce and report feasibility, and compare recommendations with an oracle over the same action set. Preserve the registered menu analysis; label additional out-of-menu contrasts as exploratory signed differences.

8. **Medium — Missing bundles silently change the cohort used for agent regret.**  
   [g5_interventions.py:88](scripts/g5_interventions.py:88), [g5_interventions.py:158](scripts/g5_interventions.py:158)

   An existing bundle without a recommendation correctly becomes no-op. A missing bundle instead removes that incident from the agent’s regret denominator.

   The current Qwen-SFT result uses 29 incidents: 20 L0, nine L1, and **zero L2**, whereas other agents use all 60. Its aggregate regret therefore describes a different difficulty mix.

   **Fix:** Distinguish missing evaluation from submitted no-op. Require complete coverage for full-cohort comparisons, or report coverage by level and compare agents on an explicitly shared cohort.

No additional findings in perturbation determinism, valid parameter ranges for the registered sweep, delta-zero behavior, replica-ID separation, L4 budget enforcement, L5 gauge filtering, or default level budgets/twin delta. Pareto dominance is correct for the declared two objectives. Representative L0–L2 observe, query, and experiment responses were byte-identical to G4.

**4. Statistics and claims**

9. **Medium — H4/H7 uses the opposite unpaired mapping from the registration.**  
   [g5_interventions.py:71](scripts/g5_interventions.py:71)

   Registration specifies control `r` against treatment `r+1`. Implementation pairs treatment `r` with control `r+1`. These have different finite-sample cross-covariances.

   For control `[0, .2, .8]` and treatment `[.1, .7, .3]`, the implemented unpaired variance is approximately `0.05333`; the registered mapping gives `0.49333`.

   **Fix:** Implement the registered mapping, explicitly resolve the endpoint convention, and recompute the variance ratios. Existing ratios are not the registered statistic.

10. **Medium — H1/H9 implements denied experiments rather than the registered tool-removal ablation.**  
    [run_g3.py:65](scripts/run_g3.py:65), [local_llm.py:64](deliverytwin/agent/local_llm.py:64)

    `--no-experiments` only sets the experiment count to zero. The experiment tool remains advertised, and query allowance is unchanged. The local client always renders its fixed complete tool list.

    An SFT model can therefore spend turns attempting an advertised tool and receiving budget errors. This mixes unavailable information with tool-denial behavior, unlike the registered “without the tool, with additional queries” condition.

    **Fix:** Propagate an active tool set through inference, implement the registered query allocation, and record the condition in results. Otherwise label this variant as a registration deviation.

11. **Medium — Missing paired evaluations are emitted as completed tests with `p=1`.**  
    [g5_report.py:44](scripts/g5_report.py:44)

    Reproduced:

    ```python
    paired([], [])
    # {"n": 0, ..., "mcnemar_p": 1.0}
    ```

    Current report data contains such entries for absent Qwen evaluations. An unperformed comparison becomes indistinguishable from an observed comparison with no discordance.

    **Fix:** Emit `status="not_run"` or `"incomplete"` and a null p-value when no valid pairs exist. Report missing IDs and expected versus observed coverage.

12. **Low — The report omits registered uncertainty and comparison classifications.**  
    [g5_names_only.py:60](scripts/g5_names_only.py:60), [g5_report.py:73](scripts/g5_report.py:73)

    H10 exports accuracies without Wilson intervals or per-level denominators, and `g5_report.py` incorporates them unchanged. Comparisons also lack the required principal/exploratory labels, despite adding exploratory comparisons such as SFT versus GPT-5-mini.

    **Fix:** Export counts and Wilson intervals for H10, and attach the registered analysis classification to every comparison. These are explicit analysis rules in PREREG line 45.

13. **Medium — Generator failures are not reported as registered.**  
    [g5_interventions.py:187](scripts/g5_interventions.py:187)

    A `generate_instance` failure propagates through `ex.map` and aborts before either output is written. There is no failed-instance record; an earlier report may remain on disk. This contradicts the rule that unproducible instances must be reported without replacement.

    **Fix:** Capture expected generation failures as records containing level, index, seed, and reason; persist successes and failures; mark the study incomplete and expose the effective denominator.
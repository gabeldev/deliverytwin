# G1 — Relatório de verificação do simulador

> **Atualização (revisão independente do G1):** 10 achados corrigidos; os KPIs passaram a usar coorte fechada. Números atuais em `REVIEW_FIXES_G1_G2.md` e `G1_REPORT_DATA_v4.json`.


> **Nota (G2):** os números abaixo valem para o mundo do G1 (30 entregadores, popularidade uniforme). O G2 recalibrou o mundo padrão; as medições refeitas estão em `G1_REPORT_DATA_v2.json` e resumidas em `G2_REPORT.md` §8. As conclusões se mantêm e ficaram mais fortes.

**Data:** 2026-11-01 · **Gate:** G1 (RFC §11) · **Dados brutos:** `docs/reports/G1_REPORT_DATA.json` (gerado por `scripts/g1_report.py --seeds 40`)

## 1. O que foi implementado

| Módulo | Conteúdo |
|---|---|
| `deliverytwin/core/rng.py` | `EventRng`: sorteios como função pura de (semente, chave do evento), BLAKE2b com chave; modo estrito que proíbe reutilizar chave; distribuições derivadas |
| `deliverytwin/world/` | `WorldConfig` (pydantic, imutável); cidade em grade com 3 zonas, restaurantes e casas de entregadores sorteados por chave |
| `deliverytwin/simulation/world.py` | Mundo SimPy com estado explícito: demanda exógena por (zona, minuto), cozinhas com capacidade, despachante com fila e trabalhadores, ofertas com aceite, deslocamentos, cancelamento por paciência; políticas `nearest`, `eta_aware` (chegada na hora certa) e `random`; `fork_at` por replay |
| `deliverytwin/simulation/interventions.py` | Intervenções tipadas da lista permitida + `Placebo`; `Branch(t0, interventions, replica)` |
| `deliverytwin/simulation/kpis.py` | KPIs a partir do log: atraso, p50/p95, atraso de atribuição, cancelamento |
| `tests/` | 60 testes (unitários, replay/pareamento, propriedades com hypothesis, baselines de despacho) |

## 2. Critérios do G1 (RFC §11 rev. 2)

| Critério | Teste | Resultado |
|---|---|---|
| Determinismo | `test_same_seed_is_deterministic` (5 sementes) | Passa |
| Replay = execução contínua (ADR-0001) | `test_replay_fork_without_intervention_equals_continuous_run` | Passa (hash idêntico do log) |
| Passado compartilhado entre ramos | `test_branches_share_identical_past` | Passa |
| **Diferença zero** entre alternativas idênticas | `test_zero_difference_between_identical_alternatives` (5 sementes × 3 réplicas) | Passa |
| **Placebo** não muda nada (ADR-0002) | `test_placebo_changes_nothing` | Passa |
| **Invariância de execução** sob intervenção que muda o caminho | `test_execution_invariance_under_path_changing_intervention` | Passa: pedidos, restaurantes, destinos, paciência e tempos de preparo idênticos para eventos comuns |
| Invariantes de ciclo de vida e de entregador | `test_order_and_courier_invariants` (hypothesis, 40 exemplos) | Passa |
| Baselines de despacho não triviais | `test_nearest_beats_random…`, `test_policies_are_not_degenerate` | Passa |

### Os testes detectam o que deveriam?

Teste de mutação: substituí o RNG por um que depende da ordem dos sorteios (emula gerador com estado). **Falharam exatamente os 15 testes de placebo e de invariância de execução**; determinismo e replay continuaram passando, como esperado, porque um gerador com estado também é determinístico.

## 3. Custo do replay (ADR-0001)

| Horizonte simulado | Mediana por execução | Eventos |
|---|---|---|
| 240 min | 0,027 s | ~2.600 |
| 480 min | 0,056 s | ~5.400 |
| 960 min | 0,108 s | ~10.600 |

Custo linear no horizonte. Com uma bifurcação = uma execução completa, 1.000 experimentos de 240 min custam ~30 s. **O critério de migração para snapshot da ADR-0001 não é atingido**; manter replay.

## 4. Redução de variância pelo pareamento (ADR-0002, hipótese H7)

Intervenção B contra controle A (NoOp) em t0 = 90 min, horizonte 240 min, KPIs dos pedidos criados após t0, 40 sementes, réplica 1. Razão = variância das diferenças pareadas ÷ variância com sementes independentes.

| Intervenção | KPI | Efeito pareado [IC 95%] | Razão, RNG por evento | Razão, RNG com estado (emulado) |
|---|---|---|---|---|
| +5 entregadores | mediana de entrega (min) | −2,07 [−2,51, −1,64] | 0,26 | 0,49 |
| +5 entregadores | atraso de atribuição (min) | −2,53 [−3,11, −1,94] | 0,58 | 0,95 |
| +5 entregadores | taxa de atraso | −0,028 [−0,038, −0,019] | 0,43 | 1,25 |
| Admissão 0,8 | mediana de entrega | −2,59 [−3,14, −2,03] | 0,37 | 0,63 |
| Admissão 0,8 | atraso de atribuição | −2,50 [−3,12, −1,88] | 0,63 | 1,01 |
| Admissão 0,8 | taxa de atraso | −0,031 [−0,040, −0,022] | 0,40 | 1,16 |
| Política `eta_aware` | mediana de entrega | +0,48 [+0,21, +0,74] | 0,065 | 0,26 |
| Política `eta_aware` | atraso de atribuição | +0,18 [+0,05, +0,31] | 0,018 | 0,31 |
| Política `eta_aware` | taxa de atraso | +0,003 [−0,003, +0,009] | 0,085 | 0,29 |
| 4 trabalhadores no despachante | mediana de entrega | −0,16 [−0,39, +0,08] | 0,055 | 0,50 |
| 4 trabalhadores no despachante | atraso de atribuição | −0,09 [−0,25, +0,07] | 0,027 | 0,60 |
| 4 trabalhadores no despachante | taxa de atraso | +0,001 [−0,005, +0,008] | 0,12 | 0,57 |

Leitura:

- O RNG por evento reduz a variância das diferenças para **2–63%** do caso independente. O gerador com estado emulado fica entre 26% e **125%**: em 3 casos **pior que não parear**, exatamente o problema descrito em 2603.11084.
- O ganho é maior em intervenções que mudam pouco o mundo (política, trabalhadores) e menor nas que mudam muito o caminho (admissão, frota). Isso é coerente com a teoria: a correlação por semente cai quando a intervenção altera mais eventos.
- O mundo base não está sob estresse, então mais trabalhadores no despachante não têm efeito detectável. Isso é esperado: a saturação do despachante é uma falha a ser injetada no G2.

## 5. Problemas encontrados e corrigidos durante o G1

1. **Paciência exponencial pura** gerava 28% de cancelamento num mundo saudável. Corrigido com piso de 25 min + exponencial de média 30 min; cancelamento base agora 0–2,5%.
2. **`eta_aware` era um clone de `nearest`** (efeito exatamente zero em 40 sementes): a pontuação empatava quando o preparo ainda não tinha começado. Reescrita como pareamento na hora certa; adicionado teste que proíbe políticas degeneradas.

## 6. Limitações

- IC normal com 40 sementes; a taxa de atraso é discreta e assimétrica, então IC por bootstrap seria mais adequado no G5.
- Emulação de RNG com estado é aproximada (contador global por mundo), não um Mersenne Twister real.
- Parâmetros do mundo são sintéticos e não calibrados (ADR-0009).
- Ainda não há falhas injetadas, telemetria ofuscada nem detector de incidentes (G2).
- `courier_accept_prob` usa chave por slot; a análise de sensibilidade slot × díade (ADR-0002) fica para o G2.

## 7. Decisão

**G1 cumprido.** Abre o G2: injeção de falhas com DAG causal, telemetria com IDs ofuscados, detector de incidentes e baseline de regras.

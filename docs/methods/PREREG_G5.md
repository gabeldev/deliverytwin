# Pré-registro G5 — pesquisa de intervenções, escada L3–L6 e ablações

**Data:** 2026-11-02 · **Registrado antes** de qualquer execução dos estudos abaixo (commit deste arquivo precede os resultados; ver `git log`).
**Restrição:** sem chamadas pagas de API no G5 (teto de US$ 1,50 praticamente esgotado no G3). Agentes: regras, manual + experimento (playbook), Qwen3-1.7B base e SFT (local).

## Sementes e conjuntos

- Desenvolvimento (2026): construção e ajuste. Nenhum número final vem daqui.
- Final (515151): todos os números do relatório G5, índices 0–19 por nível, como no G3.
- Réplicas de laboratório: investigação usa ids 1–5; avaliador de recomendações, 1001–1003; **Estudo 1 usa 2001–2020** (futuros disjuntos de tudo o que os agentes viram).

## Estudo 1 — Intervenções (RFC G5: experimentos pareados, incerteza, viabilidade, multiobjetivo)

- **Incidentes:** L0, L1, L2 da semente final (60).
- **Cardápio viável** (restrições declaradas antes): `add_couriers` 5 e 10; `set_dispatcher_workers` 4 e 6; `set_retry_backoff` 0,2; `set_dispatch_policy eta_aware`; `set_admission_rate` 0,9 e 0,8 (restrição de negócio: rejeitar no máximo 20% da demanda); custo ≤ 10 unidades; `placebo` como controle de execução.
- **Objetivos:** Δ taxa de pedidos ruins na coorte de demanda (primário; rejeitado conta como ruim), Δ tempo penalizado, Δ fração rejeitada, custo em unidades. 20 réplicas pareadas por braço.
- **Saídas:** efeito médio por família × intervenção com IC t sobre incidentes; fronteira de Pareto (Δruim, custo) por incidente; ação ótima viável por incidente; **arrependimento** do remédio-padrão por família (`REMEDY`) e das recomendações do playbook no G3 em relação à ótima.
- **H7/H4 (variância pareada):** razão Var(diferenças pareadas) / Var(diferenças não pareadas, controle da réplica r contra tratamento da réplica r+1) por tipo de intervenção. **Previsão:** razão < 1 para todos os tipos; mediana < 0,5 em ao menos metade dos tipos. Refutação: razão ≥ 1 em algum tipo.
- **H8 (piso de execução):** o placebo deve dar diferença **exatamente zero** em todas as réplicas (RNG por evento). Qualquer diferença não nula refuta.

## Estudo 2 — Laboratório modo B (gêmeo) e L6

- **Gêmeo:** mesmo código, **semente diferente** do mundo (derivada do registro privado, nunca s*), parâmetros multiplicados por exp(δ·z) com z ~ N(0,1) por parâmetro (entregadores, demanda por zona, preparo, serviço do despachante, espera de nova tentativa, paciência), severidade da falha perturbada da mesma forma e início deslocado em δ·20 min. O gêmeo **conhece a estrutura** da falha (mecanismo certo, parâmetros errados): é uma cota otimista do modo B real; descompasso estrutural fica fora deste estudo e é declarado como limitação.
- **Descompasso:** δ ∈ {0, 0,1, 0,25, 0,5}. δ = 0 isola o efeito de trocar só a semente.
- **Agentes:** playbook (todos os δ); Qwen SFT em δ = 0,25 se houver tempo de GPU.
- **Métricas:** acurácia exata no L2 em função de δ; Δruim da recomendação **medido no mundo verdadeiro** (modo A, réplicas do avaliador).
- **Previsão:** acurácia não aumenta com δ (tolerância de 0,10 por ruído de n = 20); δ = 0 fica a ±0,10 do modo A.
- **L6 =** instâncias L2 com laboratório modo B em δ = 0,25.

## Estudo 3 — Escada L3–L5

- **L3 (falhas compostas):** duas falhas de famílias diferentes no mesmo incidente (uma global e um gargalo de restaurante). Resposta correta = a falha **primária** (a de maior impacto isolado no mundo verdadeiro, medido pelo gerador); a secundária pode ser declarada em `unresolved_between`, sem pontuação. Acerto exato exige a primária com escopo correto.
- **L4 (orçamento apertado):** gerador do L2, orçamento de 8 consultas, 1 experimento e 1,0 unidade (folga zero: cabe exatamente uma sonda discriminante).
- **L5 (observabilidade parcial):** famílias do L0, perfil `partial`: pedidos + `orders_active` + `kitchen_load`; **sem** `couriers_online`, `couriers_idle` e `dispatch_queue`. Escassez de entregadores vs. saturação do despachante deixa de ser separável por observação e passa a exigir experimento (adicionar entregadores vs. trabalhadores).
- **Agentes:** regras, playbook; Qwen base e SFT em L4/L5 (fora da distribuição de treino: teste de generalização **H2**).
- **Previsões:** (a) no L5, playbook > regras (as regras abstêm no par); (b) no L4, o playbook mantém a acurácia do L2 (usa uma sonda) e o SFT não ganha do base; (c) H2: o ganho do SFT sobre o base no L0–L2, se existir, encolhe no L5.

## Estudo 4 — Ablações sem API paga

- **H1/H9 (valor do experimento com o mesmo orçamento):** Qwen SFT no L2 com e sem a ferramenta `experiment` (sem ela, consultas extras no mesmo orçamento). Teto sem informação no L2 = 1/2 de acerto ao comprometer. **Previsão:** sem experimento, acerto ≤ 0,5 + ruído; com experimento, maior.
- **H10 (vazamento por nomes):** classificador que só vê os identificadores ofuscados e o `dataset_id`, treinado em instâncias da semente de desenvolvimento e testado na final. **Previsão:** acurácia ≤ classe majoritária + 0,10.

## Regras de análise (fixas)

- Acurácia com IC de Wilson 95%; comparações pareadas por McNemar exato; nenhuma correção de multiplicidade é aplicada, e por isso cada comparação é rotulada como **principal** (as previsões acima) ou **exploratória** (todo o resto).
- Instâncias que o gerador não consegue produzir são relatadas, não substituídas.
- Resultados negativos ou que refutem uma previsão entram no relatório sem reformulação da hipótese.

## Adenda A1 — rodadas com API paga (registrada antes de executar, 2026-11-02)

O responsável liberou mais US$ 0,55 de API depois do pré-registro. O teto no `.env` sobe de 1,50 para 1,98; o cliente continua recusando chamadas acima do teto. Todas as comparações abaixo são **exploratórias**: não estavam no pré-registro original e não mudam o rótulo de nenhuma comparação principal.

Mesma semente final (515151), n = 20 por nível, raciocínio "low" e o mesmo laço de agente do G3. Ordem de execução, da mais barata para a mais cara; se o teto for atingido, as execuções seguintes ficam marcadas como incompletas e não são substituídas:

1. gpt-5.6-luna no L4, L5 e L6 (custo estimado de ~US$ 0,12 pelo custo de 60 episódios no G3).
2. gpt-5.6-luna no L2 sem a ferramenta de experimento (H1/H9 num segundo modelo, ~US$ 0,04).
3. gpt-5-mini no L4, L5 e L6 (~US$ 0,30).

Previsões, só exploratórias:
- (e1) Os LLMs de API ficam abaixo do próprio desempenho no L2 tanto no L4 (um experimento só) quanto no L6 (gêmeo imperfeito).
- (e2) Sem o experimento, o luna no L2 não supera o luna com experimento.

**Emenda A1.1 (antes de qualquer resultado do luna).** As duas execuções do luna falharam já na primeira chamada: a rota `/v1/chat/completions` não aceita ferramentas com `reasoning_effort` para esse modelo (erro 400). Foi a mesma limitação do G3, onde o luna rodou sem raciocínio (G3 §6). As execuções 1 e 2 vão rodar com `--reasoning none`, igual ao G3, **depois** da 3 (gpt-5-mini, que não muda). As chamadas que falharam ficaram cobradas pelo valor reservado no ledger, um total abaixo de US$ 0,02.

# G2.1 — Calibração contra dados reais e par equivalente do L2

> **Atualização (revisões do G1 e do G2):** efeitos das falhas, baselines (agora num conjunto de avaliação com semente nova) e métricas foram corrigidos; números atuais em `REVIEW_FIXES_G1_G2.md`. As tabelas abaixo das seções 2 e 4 são históricas.


**Data:** 2026-11-01 · **Dados:** `G2_1_REPORT_DATA.json` (`scripts/g2_report.py`), `G2_1_PAIR_SEARCH.json` e `G2_1_PAIR_C_N300.json` (`scripts/g21_pair_search.py`), `G2_1_MDRP_COMPARISON.json` (`scripts/compare_mdrp.py`), `G1_REPORT_DATA_v3.json`

**Veredito:** pendência do G2 **resolvida**. Revisão independente (Codex) encontrou 6 problemas, todos confirmados e corrigidos (§7). O L2 agora usa um par observacionalmente equivalente **verificado pela sonda** e separável por intervenção. O mundo foi recalibrado contra dados reais do Grubhub.

## 1. Calibração contra o Grubhub MDRP

Fonte: [grubhub/mdrplib](https://github.com/grubhub/mdrplib), 10 instâncias-semente sem modificação (`o100t100s1p100`), dados anonimizados de operação real de entrega de refeições. O repositório não tem arquivo LICENSE; uso local para pesquisa, sem redistribuir dados nem parâmetros derivados (ADR-0009). Os números abaixo são estatísticas agregadas.

| Grandeza | Grubhub | Mundo antes | Mundo depois |
|---|---|---|---|
| Preparo p50 / p90 / média (min) | 15 / 30 / 17,7 | 12 / 18,8 / 12,7 | **14,8 / 31,5 / 17,6** |
| Serviço na coleta + na entrega (min) | 4 + 4 | 0 | **4 + 4** |
| Deslocamento restaurante → cliente p50 / p90 (min) | 8,2 / 17,7 | 7,5 / 15 | 7,5 / 15 |
| Dispersão de pedidos por restaurante (σ log) | 0,99 | 0,81 | **0,89** |
| Pedidos por hora de entregador | 1,88 | 1,82 | 1,33 |

Mudanças no mundo padrão:

- preparo log-normal com mediana 15 e σ = 0,6; serviço de 4 + 4 min; popularidade σ = 1,0;
- frota de **56 entregadores** (utilização ~0,77–0,80);
- prazo prometido de **55 min** (≈ p90 do mundo saudável) e paciência mínima de 50 min. O alvo de 40 min do Grubhub pressupõe roteirização otimizada **com agrupamento** de pedidos, que este mundo não modela.

Mundo saudável resultante: atraso 7%, cancelamento 0,7%, mediana de entrega 33 min.

**Divergências conhecidas (não corrigidas):**

1. **Sem agrupamento de pedidos.** Por isso os pedidos por hora de entregador ficam em 1,33 contra 1,88.
2. **Sem turnos escalonados** (Grubhub: mediana de 3 h). Todos os entregadores ficam disponíveis o dia todo. Afeta diretamente a falha de escassez e merece decisão própria.
3. σ log do preparo: 0,6 contra 0,80 medidos. Os quantis batem; o σ medido provavelmente infla pelo arredondamento em minutos inteiros nos dados.

Um defeito apareceu ao introduzir os 4 min de coleta: o cliente podia cancelar durante a entrega da comida ao entregador, gerando pedidos ao mesmo tempo cancelados e entregues. **O teste de invariantes com hypothesis detectou o problema**; a correção define que, iniciada a coleta, não há mais cancelamento.

## 2. Detector depois da recalibração

Duas correções de desenho foram necessárias por causa do prazo de 55 min:

1. A **coorte** do detector é amarrada ao prazo: pedidos com idade entre 10 min e prazo + 30 min. Com a janela antiga, de 60 min, quase nenhum pedido tinha destino determinado e a saturação **nunca** era detectada (0 de 30).
2. A **referência** são os pedidos criados entre 80 e 120 min, avaliados em 120 + prazo. As falhas passam a começar entre 180 e 215 min, e o horizonte vai a 360 min.

Calibração: limiares de +0,169 (global) e +0,70 (local). Falso alarme em sementes separadas: **0,7% sem ruído e 2,7% com ruído** (150 cada).

| Família | Detecção | IC 95% | Atraso mediano após o início [IQR] |
|---|---|---|---|
| Escassez | 92% | [82%, 96%] | 96 min [82, 108] |
| Saturação | 100% | [94%, 100%] | 105 min [97, 116] |
| Gargalo de restaurante | 43% | [32%, 56%] | 108 min [88, 126] |
| Surto de erros | 87% | [76%, 93%] | 87 min [80, 102] |
| Latência de dependência | 82% | [70%, 89%] | 90 min [79, 105] |

O limite físico escala com o prazo: um atraso só é observável depois de 55 min. Portão de atraso máximo: prazo + 65 = 120 min.

## 3. Busca do par equivalente

Critério (ADR-0005, emenda 1): melhor sonda com limite superior do IC de Wilson ≤ 0,60 **e** existência de intervenção discriminante.

**Correção do critério:** com n = 80, o IC tem meia-largura de ~0,11, então até um classificador no acaso teria limite superior ~0,65. **O critério era inatingível com aquela amostra**; a aceitação exige n ≥ ~300.

| Candidato | n | Sonda (melhor) | Limite sup. IC | Efeito na mediana | Aceito |
|---|---|---|---|---|---|
| A. Saturação × surto de erros | 80 | 0,99 | 1,00 | +20,1 vs. +8,0 | Não |
| B. Escassez × saturação (severidades pareadas) | 80 | 0,95 | 0,98 | +12,6 vs. +19,7 | Não |
| **C. Surto de erros × latência de dependência (construído)** | **300** | **0,50** (acaso 0,52) | **0,56** | +9,7 vs. +9,9 | **Sim** |

Por que A e B falham mesmo com severidades pareadas: a saturação acima da capacidade é uma **rampa**, porque a fila cresce sem parar, enquanto erros e escassez são **degraus**. No momento do alerta as magnitudes diferem. A escassez ainda tem padrão espacial próprio (sonda a 74% sem features de magnitude).

### Construção do par C

- **Surto de erros:** a chamada ao serviço de despacho falha rápido; o pedido espera o intervalo entre tentativas e volta à fila.
- **Latência de dependência:** a chamada trava de forma **assíncrona**, sem prender um trabalhador, pelo mesmo número de passos, e depois volta à fila.
- Os dois usam **as mesmas chaves de sorteio** por tentativa. Com o mesmo mundo, 98–100% dos pedidos têm o mesmo atraso de atribuição (diferença < 0,5 min).
- Duas versões intermediárias falharam e mostram por que os detalhes importam:
  - latência que **prendia o trabalhador** derrubou a capacidade e virou saturação disfarçada (atraso 51 vs. 10 min);
  - erros que **consumiam tempo de serviço** geraram uma tempestade de retentativas (atraso 28 vs. 6 min).

### Separação por intervenção (laboratório modo A, 20 instâncias por família)

Métrica (corrigida após a revisão, §7): taxa de pedidos ruins (cancelados, entregues após o prazo ou ainda abertos após o prazo) na **coorte fechada** de pedidos aceitos em [t0, t0 + 90), avaliada em t0 + 150, quando todos têm destino determinado. Mesmo denominador nos dois braços.

| Intervenção no alerta | Δ pedidos ruins: surto de erros | Δ pedidos ruins: latência |
|---|---|---|
| **Reduzir o intervalo entre tentativas para 0,2 min** (nova, `SetRetryBackoff`) | **−0,274 ± 0,082** | **0,000** |
| Mais trabalhadores no despachante (6) | −0,002 | −0,001 |
| +10 entregadores | −0,005 | −0,004 |

Só a primeira discrimina; as outras duas servem de controle (experimentos que não informam). A versão anterior desta tabela (−0,161 vs. 0,000) usava uma métrica com viés de seleção; a conclusão se mantém e o efeito ficou maior.

### Ressalva importante

A equivalência vale **para o perfil do cliente**. Com os medidores operacionais (perfil completo), a sonda chega a 0,61–0,71, porque a fila do despachante se comporta de outro jeito: os erros fazem entrar e sair, a latência não. Isso é coerente com a teoria (identificabilidade depende do que se observa) e é exatamente o desenho do L2.

Também corrigido: o laboratório usava o horizonte do mundo e o alerta ficava perto do fim, deixando KPIs indefinidos. Agora o laboratório estende o horizonte além do alerta. Com sorteios por evento, isso só acrescenta futuro.

## 4. Benchmark e baselines (60 instâncias por nível)

| Nível | Famílias | Regras (causa + escopo) | Regras (família) | Majoritária | Aleatório | Vazamentos |
|---|---|---|---|---|---|---|
| L0 | escassez, saturação, gargalo | 0,68 [0,56, 0,79] | 0,70 | 0,38 | 0,38 | 0 |
| L1 (+ruído) | idem | 0,65 [0,52, 0,76] | 0,65 | 0,40 | 0,30 | 0 |
| L2 (cliente) | surto de erros, latência | 0,00 (abstém em 70%) | 0,00 | 0,57 | 0,62 | 0 |

No L2, o teto sem informação é 1/2. Classe majoritária e aleatório ficam em torno disso, como esperado. O valor do experimento passa a ser mensurável: um agente que use `SetRetryBackoff` no laboratório deveria se aproximar de 1,0.

## 5. G1 refeito no mundo final (`G1_REPORT_DATA_v3.json`)

Todos os testes do G1 passam. Razão de variância pareada/independente com RNG por evento: **0,000–0,71**. Com RNG dependente da ordem (emulado): **0,51–4,8**. A conclusão da ADR-0002 se mantém.

## 6. Limitações

- A revisão independente (§7) cobriu este commit; marcos anteriores (G1, G2) ainda não foram revisados por ela.
- Laboratório com 20 instâncias por família; sonda do L2 com n = 300 no candidato e n = 120 no relatório geral.
- Equivalência do par C é **construída**: valida o protocolo (o agente precisa experimentar), não diz que esses dois mecanismos sejam indistinguíveis em operações reais com observabilidade completa.
- Gargalo de restaurante continua com detecção baixa (43%) pelo volume pequeno por restaurante.
- Sem agrupamento de pedidos e sem turnos (seção 1).

## 7. Revisão independente (Codex CLI) e correções

Revisor: Codex CLI 0.166, sandbox somente leitura, sobre o commit 3a7e506. Saída integral em `docs/reviews/CODEX_REVIEW_G2_1.md`. **Cada achado foi reproduzido por mim antes de qualquer correção**; cada correção tem teste de regressão em `tests/benchmark/test_review_g21.py`. Os quatro testes compatíveis com a API antiga **falham no commit 3a7e506** e passam depois da correção.

| # | Gravidade | Achado | Reproduzido? | Impacto nos resultados publicados | Correção |
|---|---|---|---|---|---|
| 1 | Alta | O ID público ("L2-0000") somado à semente-mestra padrão permitia recalcular a família oculta | Sim, família recuperada só pelo ID | Invalidava instâncias para qualquer avaliado capaz de rodar o código (ex.: baseline "agente de código") | ID público opaco (token com sal privado); semente secreta via `DELIVERYTWIN_MASTER_SEED`; registro `sealed` no canal privado; instâncias da semente pública são só de desenvolvimento |
| 2 | Média | A ordem dos medidores de cozinha seguia a ordem dos IDs crus dos restaurantes | Sim | Mapeamento token → restaurante recuperável no perfil completo | Serialização na ordem dos tokens |
| 3 | Alta | A latência pré-sorteava passos futuros com a semente base; após uma bifurcação, erros e latência divergiam | Sim, o-1-229-1: 232,64 vs. 295,64 | Telemetria e sonda **não** afetadas (0 de 369 pedidos diferem sem bifurcação); ramos do laboratório sim | Travamento passo a passo, cada passo sorteado quando acontece |
| 4 | Média | O limite de 500 passos virava sucesso | Sim, 0 vs. 7 pedidos atribuídos com p = 0,9999 | Nenhum nos parâmetros usados (p ≤ 0,98) | Laço só termina em sucesso observado ou cancelamento |
| 5 | Média | Métrica do laboratório com coorte aberta e denominador dependente do resultado; um comentário no código descrevia uma janela de 90 min inexistente | Sim, por inspeção | Números do laboratório mudaram (tabela acima); conclusão mantida | `cohort_bad_rate`: coorte fechada, todos determináveis |
| 6 | Média | A aceitação ignorava n ≥ 300 | Sim, por inspeção | Nenhum (o par aceito tinha n = 300) | `acceptance_status`: `accepted` / `rejected` / `insufficient_n` |

Áreas sem achados segundo o revisor: invariantes de cancelamento × coleta, dupla atribuição de entregador, conservação de pedidos, reutilização de chaves de sorteio, sobreposição de sementes de calibração e avaliação, vazamento entre partes da validação cruzada.

**Lição para o processo:** os 81 testes existentes passavam com os 6 problemas presentes. A revisão independente passa a fazer parte de cada marco (ver memória do projeto e `docs/reviews/`).

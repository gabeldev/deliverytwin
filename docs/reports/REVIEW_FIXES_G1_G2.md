# Correções da revisão independente do G1 e do G2

**Data:** 2026-11-01 · **Revisor:** Codex CLI 0.166, sandbox somente leitura · **Revisões:** `docs/reviews/CODEX_REVIEW_G1.md` (commit c2db1ae) e `docs/reviews/CODEX_REVIEW_G2.md` (commit 58daf00), ambas avaliadas no HEAD 5b65735 · **Testes de regressão:** `tests/simulation/test_review_g1.py`, `tests/benchmark/test_review_g2.py`

**Procedimento:** cada achado foi reproduzido por mim antes de qualquer correção. Cada correção tem teste de regressão. Para os testes que usam APIs já existentes, confirmei que **falham no código anterior** (worktree em 5b65735 com importação forçada da árvore antiga) e passam depois. Os dois testes acusados de fracos foram verificados com **mutações**: eles passavam com a propriedade quebrada e agora falham.

**Resultado:** 16 de 16 achados confirmados e corrigidos (G1: 10, G2: 6). Nenhum achado na área de vazamento da verdade oculta na revisão do G2.

## G1 (10 achados)

| # | Gravidade | Achado | Reprodução | Correção |
|---|---|---|---|---|
| 1 | Média | `uniform()` podia retornar exatamente 1,0 (digest todo 1) | Sim | Valor limitado ao maior float < 1; só esse caso extremo muda, todos os outros sorteios ficam idênticos |
| 2 | Média | Poisson com taxa alta devolvia em silêncio o teto de 10.000 | Sim, `poisson(1000)` = 10000 | Taxas > 100 rejeitadas; o laço levanta erro em vez de devolver o teto; demanda por zona limitada a 30 pedidos/min |
| 3 | Média | Sorteio ponderado podia escolher peso zero (soma estourando para infinito) | Sim, retornou o índice 2 | Pesos validados (finitos, não negativos); reescala quando a soma estoura; o retorno de segurança nunca é um peso zero |
| 4 | Baixa | A proteção contra reuso de chave não atravessava a troca de gerador na bifurcação | Sim | Registro de chaves compartilhado entre os geradores de antes e depois |
| 5 | **Alta** | Bifurcar um mundo já bifurcado descartava as intervenções e a semente da réplica do pai | Sim, passado diferente | Bifurcação aninhada rejeitada explicitamente; o laboratório só bifurca o mundo raiz |
| 6 | Média | Inserir um placebo mudava IDs e casas dos entregadores adicionados | Sim, `inc0-*` vs `inc1-*` | Intervenções identificadas pelo ordinal dentro do próprio tipo |
| 7 | Média | Reduzir trabalhadores do despachante era ignorado | Sim, continuava com 2 | Trabalhadores com índice ≥ alvo se aposentam antes do próximo pedido |
| 8 | Média | KPIs do relatório do G1 com coorte aberta: o tratamento mudava quem entrava na métrica | Por inspeção | Coorte fechada com acompanhamento completo (`cohort_bad_rate`, `cohort_penalized_time`) |
| 9 | Média | O teste de políticas não degeneradas comparava hashes que já diferiam pela intervenção registrada | Sim, passou com políticas idênticas | Compara o mapeamento pedido → entregador; agora falha sob a mutação |
| 10 | Baixa | O teste de conservação não verificava conservação | Sim, passou sem eventos de aceite | Uma decisão de admissão por pedido, admissão antes do resto, cancelado ⇔ evento de cancelamento, nada atribuído ou entregue após cancelamento, contagem fecha; agora falha sob a mutação |

Ao reforçar o teste do achado 10, **uma suposição minha estava errada**: eu esperava que nada acontecesse depois de um cancelamento, mas a cozinha termina o preparo, por desenho. O teste foi corrigido, não o simulador.

## G2 (6 achados)

| # | Gravidade | Achado | Reprodução | Correção |
|---|---|---|---|---|
| 1 | Média | A oscilação de demanda de blocos após a bifurcação era igual em todas as réplicas | Por inspeção; teste direto sobre os valores sorteados | Bloco sorteado com o gerador ativo quando é alcançado pela primeira vez |
| 2 | Média | O DAG da saturação não tinha a aresta direta tempo de serviço → atraso de atribuição | Por raciocínio sobre o mecanismo | Aresta adicionada |
| 3 | Baixa | O limiar calibrado era arredondado para baixo antes de uma comparação estrita | Por inspeção | Precisão total; o limiar é exatamente a estatística de ordem calibrada |
| 4 | Média | **O portão de impacto rejeitava uma pane total**: pedidos abertos e atrasados sumiam, e medianas ausentes viravam zero | Sim, escassez de 99,9999%: −30,5 min, rejeitada | Coorte fechada e madura: atrasados abertos contam como ruins, grupos sem dados são omitidos; a mesma pane agora dá +46,7 min e passa |
| 5 | Média | Baselines avaliados num conjunto que incluía o próprio treino | Por inspeção | Avaliação num conjunto gerado com outra semente-mestra (909090), nunca usada para ajustar as regras; classe majoritária aprendida no treino do conjunto de desenvolvimento |
| 6 | Baixa | A feature `open_share` olhava resultados após o instante do alerta | Por inspeção | Aberto = sem entrega ou cancelamento até o alerta |

## Problemas adicionais encontrados ao aplicar as correções

- A emulação de "gerador com estado" no relatório do G1 reutilizava chaves entre os geradores de antes e depois da bifurcação. A proteção do achado G1-4 detectou isso, e a emulação passou a incluir a semente na chave.
- A tabela de efeitos das falhas e a análise slot × díade ainda usavam coorte aberta. A análise slot × díade ainda tinha o prazo de 40 min fixo no código, de antes da recalibração. Ambas passaram para coorte fechada.
- Um dos meus testes de regressão (oscilação de demanda) passaria mesmo com o bug, porque as chegadas já diferem entre réplicas. Foi reescrito para comparar os valores sorteados, e confirmei que falha com o comportamento antigo.

## Números depois das correções

### G1 (`G1_REPORT_DATA_v4.json`): coorte fechada [90, 150) avaliada em 240 min, 40 sementes, réplica 1

| Intervenção | Δ pedidos ruins [IC] | Δ tempo penalizado (min) [IC] | Razão de variância, RNG por evento | Razão, RNG com estado (emulado) |
|---|---|---|---|---|
| +5 entregadores | 0,000 | −0,24 [−0,32, −0,17] | 0,000 / 0,007 | 0,76 / 1,13 |
| Admissão 0,8 | −0,006 [−0,012, +0,001] | −0,69 [−1,00, −0,37] | 0,14 / 0,12 | 0,51 / 0,63 |
| Política `eta_aware` | +0,001 | +2,11 [+1,87, +2,35] | 0,009 / 0,072 | 0,56 / 0,61 |
| 4 trabalhadores no despachante | 0,000 | +0,02 [−0,00, +0,04] | 0,000 / 0,001 | 0,42 / 0,33 |

Razão 0,000 significa diferenças pareadas exatamente zero: a intervenção não mudou o desfecho de nenhum pedido da coorte. A conclusão da ADR-0002 se mantém.

### G2.1 (`G2_1_REPORT_DATA.json`)

**Efeito das falhas** (coorte fechada [195, 255) avaliada em 360 min, 40 sementes):

| Falha | Δ pedidos ruins [IC] | Δ tempo penalizado (min) [IC] |
|---|---|---|
| Escassez (57%) | +0,310 [0,270, 0,350] | +25,1 [21,5, 28,6] |
| Saturação (×8,25) | +0,036 [0,019, 0,052] | +4,5 [3,7, 5,4] |
| Gargalo de restaurante (×4,5) | +0,043 [0,028, 0,058] | +4,0 [2,6, 5,5] |
| Surto de erros (0,965) | +0,267 [0,252, 0,283] | +19,8 [18,8, 20,9] |
| Latência (0,965) | +0,268 [0,252, 0,283] | +19,8 [18,7, 20,8] |

A saturação parece menor que na tabela anterior (janela aberta): ela cresce em rampa e a coorte fechada logo após o início pega a fase inicial.

**Baselines** num conjunto de avaliação com semente-mestra nova (909090), 60 instâncias por nível:

| Nível | Regras | Classe majoritária (aprendida no treino de desenvolvimento) | Aleatório |
|---|---|---|---|
| L0 | **0,75** [0,63, 0,84] | 0,27 | 0,33 |
| L1 | **0,55** [0,42, 0,67] | 0,25 | 0,42 |
| L2 | 0,00 (abstém em 75%) | 0,55 | 0,53 |

Antes (avaliado no conjunto de desenvolvimento): L0 0,68 e L1 0,65. A queda no L1 é o efeito esperado de avaliar fora dos dados usados para ajustar as regras.

**Inalterados:** sonda do par L2 com n = 300 (0,47 e 0,50, acaso 0,52, aceito); laboratório (`SetRetryBackoff`: −0,272 vs. 0,000); detector (falso alarme medido 0,7% / 2,7%); 0 vazamentos em 360 payloads públicos.

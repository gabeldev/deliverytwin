# ADR-0002 — Aleatoriedade por evento (números aleatórios comuns válidos)

**Status:** Aceita (2026-11-01) · **Gate:** G0 → verificado no G1 · **Data:** 2026-11-01

## Contexto

Comparações pareadas (RFC §5) exigem que o mesmo evento modelado receba o mesmo ruído exógeno nos dois cenários. Com gerador com estado (Mersenne Twister, PCG), qualquer intervenção que mude o caminho de execução desloca o índice dos sorteios seguintes e quebra o pareamento. 2603.11084 chama a propriedade necessária de **invariância de execução**: `U_e = g(s, event_id_e)`, com `event_id_e` estável entre cenários e independente do histórico.

## Decisão

1. **Proibido** usar `random`, `numpy.random.default_rng()` ou qualquer gerador com estado dentro do simulador.
2. Todo sorteio passa por uma função pura:

   ```python
   def draw(seed: WorldSeed, key: EventKey) -> float  # U(0,1)
   ```

   implementada com gerador **por contador** (Philox ou Threefry do NumPy, a confirmar na versão fixada). `EventKey` é uma tupla tipada transformada em contador de 128 bits.
3. **Catálogo de chaves v0** (decisão de modelagem, revisável por ADR):

   | Fonte | Chave | Tipo | Hipótese de permutabilidade |
   |---|---|---|---|
   | Chegada de pedidos | `("arrival", zone, minute, k)` | slot | Demanda é exógena a toda intervenção |
   | ID do pedido | `hash(zone, minute, k)` | genealógico | Mesmo pedido em todos os cenários |
   | Tempo de preparo | `("prep", order_id)` | slot | Restaurante e carga entram pelo estado, não pela chave |
   | Aceite do entregador | `("accept", order_id, offer_index)` | slot | Entregadores permutáveis dado o estado; **análise de sensibilidade** com díade `("accept", order_id, courier_id)` |
   | Tempo de deslocamento | `("travel", order_id, leg)` | slot | Distância e congestionamento entram pelo estado |
   | Disponibilidade do entregador | `("shift", courier_id, day)` | díade | Entregadores fundadores com ID fixo |
   | Erro do serviço de despacho | `("dispatch_err", order_id, attempt)` | slot | — |
   | Ruído de telemetria | `("noise", metric, t)` | slot | — |
   | Futuro após bifurcação | chaves acima com `replica r` incorporada à semente: `seed = h(s, r)` para eventos depois de `t0` | — | Réplicas = futuros exógenos independentes; antes de `t0` tudo é fixo |

4. Regras (de 2603.11084 §4.3): chave suficientemente granular; **nenhuma quantidade endógena na chave** (ex.: fila atual); cada evento sorteado uma vez e guardado; IDs de 128 bits com verificação de colisão em modo debug; entidades criadas durante a simulação recebem ID genealógico.
5. **Fixar** implementação e versão do gerador no manifesto do experimento (2609.26461 levanta que o estado completo pode não garantir portabilidade entre bibliotecas).

## Consequências

- Pareamento válido mesmo quando a intervenção muda a ordem de execução.
- O catálogo de chaves vira parte da especificação científica e é revisado como tal.
- Sorteio por chave é um pouco mais caro; aceitável.

## Verificação (G1, em CI)

- **Teste de diferença zero:** duas alternativas idênticas ⇒ diferença exatamente 0 em todos os KPIs.
- **Teste placebo:** uma intervenção mecanicamente nula que só faz sorteios extras ⇒ nenhum KPI muda.
- **Teste de sensibilidade de chave:** slot vs. díade para o aceite; reportar a razão de variâncias pareada/independente para cada tipo de intervenção (hipótese H7).

## Emenda 1 (2026-11-01, durante o G1)

1. **Gerador:** BLAKE2b com chave (hash de 64 bits), em vez de Philox/Threefry. É um gerador por hash, da mesma classe "counter-based (or hash-based)" de 2603.11084, e mediu 0,71 µs por sorteio contra 7,2 µs do Philox instanciado por evento. Momentos de U(0,1) conferidos em teste. Identificador gravado no manifesto: `blake2b-keyed-64/v1`.
2. **Futuro após t0:** sorteios com tempo simulado ≥ t0 usam a semente `derive_seed(s, "replica", r)`; a réplica 0 reutiliza a semente base, o que faz o ramo sem intervenção reproduzir a execução contínua.
3. **Ofertas:** chave `("accept", order_id, offer_index)` com `offer_index` acumulado por pedido entre tentativas.
4. **Resultado do G1:** diferença zero, placebo e invariância passam; o teste de mutação com RNG dependente da ordem quebra exatamente os testes de placebo e invariância. Razão de variâncias pareada/independente entre 0,02 e 0,63 (ver `docs/reports/G1_REPORT.md`). A análise slot × díade fica para o G2.

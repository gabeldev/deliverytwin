# ADR-0005 — Geração do benchmark: falhas, identificabilidade e escada de dificuldade

**Status:** Aceita (2026-11-01) · **Gate:** G0 → implementado no G2 · **Data:** 2026-11-01

## Contexto

Benchmarks de RCA tendem a ser fáceis demais: regras simples igualam métodos sofisticados (10.1145/3797100, 2610.30004). Nomes vazam respostas (Heuresis 2610.22846). ACDB usa portões de rejeição, orçamento ótimo pré-calculado, rótulos permutados, escada com um eixo por nível e piso aleatório. O ISS formaliza o piso observacional.

## Decisão

**Instância** = (configuração do mundo, especificação de falha F* com DAG causal, semente s*, orçamento B, modo de laboratório, nível).

**Pipeline de geração** com portões que rejeitam e reamostram:

1. Amostrar mundo e F* (uma ou mais falhas, ruído ambiente por injetores **separados** dos de falha).
2. **Portão de impacto:** rejeitar se a falha não degrada nenhum SLI acima de limiar declarado.
3. **Classificação de identificabilidade** (com o ISS-oráculo sobre a taxonomia):
   - *observacionalmente identificável*: só uma hipótese é compatível com a telemetria;
   - *identificável por intervenção*: várias compatíveis, mas existe experimento que as separa com custo ≤ B;
   - *não identificável dentro de B*.
4. Pré-calcular o **conjunto ótimo de experimentos** I* e o orçamento `B = c(I*) + folga`.
5. Ofuscar identificadores de entidades por instância (zonas, restaurantes, entregadores, serviços).
6. Registrar F*, DAG e classe de identificabilidade **só** no canal privado.

**Pares de equivalência observacional v0:** escassez de entregadores vs. saturação/throttling do despachante (ambos elevam o atraso de atribuição). O **teto sem informação** de uma classe com k causas indistinguíveis é 1/k.

**Escada de dificuldade** (cada nível isola um eixo, como no ACDB):

| Nível | Eixo variado |
|---|---|
| L0 | Tutorial: falha única, identificável por observação |
| L1 | Ruído ambiente |
| L2 | Pares observacionalmente equivalentes (exige experimento) |
| L3 | Falhas compostas/em cascata |
| L4 | Orçamento apertado (folga 0) |
| L5 | Observabilidade parcial (métricas ausentes) |
| L6 | Descompasso do gêmeo (só modo B) |

**Controles contra vazamento e facilidade:**

- Pisos reportados sempre: aleatório cego, classe majoritária (taxa-base das famílias), só nomes, leitura sem rótulo.
- Distribuição de famílias de falha balanceada por nível, ou taxa-base publicada.
- Splits por mecanismo, geografia sintética, regime de demanda e semente (RFC §6).
- Manifesto pareado: todas as abordagens rodam as mesmas instâncias.

## Consequências

- O valor do experimento contrafactual é medido diretamente em L2 contra o teto 1/k.
- Se as regras resolverem L0–L3 quase por completo, o gerador está fácil e deve ser recalibrado antes do G3.

## Emenda 1 (2026-11-01, resultado do G2)

1. **Identificabilidade é empírica.** A suposição de que escassez de entregadores × saturação do despachante formam par observacionalmente equivalente foi **refutada**: uma sonda de classificação separa o par com 90–93% de acurácia só com dados de cliente (acaso 54%), por magnitude e por padrão espacial. A partir de agora, todo rótulo de identificabilidade de um nível vem de uma **sonda de distinguibilidade** (classificadores fortes com validação cruzada sobre features observáveis do perfil), nunca de suposição. Critério para um par entrar como "equivalente": limite superior do IC da melhor sonda ≤ 0,60.
2. **Par candidato do L2 (G2.1):** saturação do despachante × surto de erros de despacho com novas tentativas, com severidades pareadas pelo efeito.
3. **Portões efetivos:** impacto (contrafactual pareado sem falha), detecção (alerta após o início e em até 90 min) e **atribuição** (o mundo sem falha pareado não alerta até o mesmo instante).
4. **Janela de referência após o aquecimento** (80–125 min); falhas começam entre 130 e 165 min.
5. Detalhes e números: `docs/reports/G2_REPORT.md`.

## Emenda 2 (2026-11-01, G2.1)

1. **Par do L2:** surto de erros de despacho × latência de dependência, **construído** para ser equivalente na visão do cliente (mesmas chaves de sorteio por tentativa; latência assíncrona; erros falham rápido). Verificado: sonda no acaso com n = 300 (limite superior 0,56). Intervenção discriminante: `SetRetryBackoff`.
2. **Critério de aceitação com amostra explícita:** limite superior do IC de Wilson ≤ 0,60 **com n ≥ 300**. Com n = 80 o critério é inatingível mesmo no acaso.
3. **Equivalência é relativa ao perfil:** o par é separável com os medidores operacionais. O nível declara o perfil em que a equivalência foi verificada.
4. **Horários:** referência = pedidos criados em 80–120 min, avaliados em 120 + prazo; falhas entre 180 e 215 min; horizonte 360 min; atraso máximo de detecção = prazo + 65 min.
5. Detalhes: `docs/reports/G2_1_REPORT.md`.

## Emenda 3 (2026-11-01, revisão independente do G2.1)

1. **Conjuntos lacrados exigem semente-mestra secreta** (`DELIVERYTWIN_MASTER_SEED` ou argumento). Instâncias geradas com a semente pública padrão são reprodutíveis por qualquer um com o código e servem só para desenvolvimento; o canal privado registra `sealed`.
2. **ID público opaco:** o `dataset_id` é um token derivado do sal privado; nível e índice não aparecem.
3. **Vazamento estrutural** (ordem de serialização, IDs reconstituíveis) passa a ser verificado por testes, não só a varredura textual.

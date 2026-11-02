# ADR-0003 — Separação entre Mundo, Laboratório e Gêmeo

**Status:** Aceita (2026-11-01) · **Gate:** G0 · **Data:** 2026-11-01

## Contexto

Se o agente pudesse rodar o mesmo simulador, com a mesma semente e o mesmo estado do mundo verdadeiro, ele poderia injetar cada falha candidata e comparar a telemetria byte a byte. O diagnóstico viraria busca exaustiva, sem raciocínio. Ao mesmo tempo, o ISS (2609.32247) mostra que a capacidade de **consultar o sistema verdadeiro sob intervenção** é exatamente o que supera o piso observacional.

Precisamos dar ao agente acesso intervencional ao mundo **sem** dar acesso ao seu estado interno ou à sua semente.

## Decisão

Três componentes com fronteiras rígidas:

| Componente | O que contém | Quem acessa | O que o agente recebe |
|---|---|---|---|
| **Mundo** | Especificação completa, falha injetada F*, DAG causal, semente s* | Só o processo do Mundo e o Avaliador | Telemetria (métricas, logs, traces) com identificadores ofuscados |
| **Laboratório** | Bifurcações do Mundo a partir do instante do incidente, com intervenções tipadas e réplicas pareadas | O orquestrador, a pedido do agente | KPIs agregados, diferenças pareadas e IC; nunca estado interno |
| **Gêmeo** | Modelo próprio do agente: mesmo código de simulador, **outra semente**, parâmetros estimados a partir da telemetria, falhas candidatas injetáveis | O agente, livremente, dentro do orçamento de computação | Previsões condicionais a hipóteses |

Dois modos de laboratório, reportados separadamente:

- **Modo A, "laboratório oráculo":** experimentos rodam em bifurcações do **Mundo** (mesmo s*, réplicas futuras independentes). Mede raciocínio investigativo com acesso contrafactual perfeito. **Não tem análogo direto na operação real** e deve ser descrito assim (RFC §5, nota de validade).
- **Modo B, "laboratório gêmeo":** experimentos rodam no **Gêmeo**, com descompasso de modelo configurável (parâmetros perturbados, observabilidade parcial). Mede robustez a gêmeo imperfeito.

Regras:

1. O agente **nunca** recebe s*, F*, o DAG ou o estado interno do Mundo.
2. O Laboratório aceita apenas **intervenções operacionais** da lista permitida (ADR-0004), nunca injeção de falhas no Mundo.
3. Injeção de falhas candidatas só é permitida no Gêmeo.
4. Baselines com privilégio (ex.: ISS usando o Mundo e falhas candidatas) são marcados como **oráculo** e só servem de cota superior.

## Consequências

- Fecha a via de busca exaustiva por correspondência de telemetria.
- Permite o resultado científico central: ganho do modo A sobre o piso observacional, e a perda do modo B em função do descompasso do gêmeo.
- O Avaliador roda em processo separado e é o único que lê o canal privado (RFC §4).

## Verificação

- Teste de fronteira: nenhuma resposta do Laboratório ou da telemetria contém s*, nome da falha, parâmetros de injeção ou identificadores não ofuscados (canário textual + varredura em CI).

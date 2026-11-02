# ADR-0004 — Protocolo de investigação e contrato de ferramentas

**Status:** Aceita (2026-11-01) · **Gate:** G0 → implementado no G3 · **Data:** 2026-11-01

## Contexto

ACDB (2609.31675) mostra o valor de um protocolo fixo *observe → intervene → submit* com orçamento e pontuação separada. HERO e EviDiag usam estado de crença explícito sobre hipóteses concorrentes. ISS (2609.32247) dá um critério de parada com certificado. *Free to Look* (2610.35767) mostra que procedimentos rígidos podem atrapalhar.

## Decisão

Uma sessão de investigação é uma máquina de estados com cinco operações tipadas (esquemas pydantic, validação **no orquestrador**, nunca confiando no modelo):

| Operação | Entrada | Saída | Custo |
|---|---|---|---|
| `observe()` | — | Alerta do incidente, janela temporal, inventário de métricas disponíveis | Grátis, uma vez |
| `query(QuerySpec)` | Métrica/log/trace, filtro por entidade ofuscada, agregação, janela | Tabela ou série | 1 unidade de consulta |
| `hypothesize(HypothesisSet)` | Hipóteses da **taxonomia pública** de falhas, com escopo e previsões declaradas | Registro no livro-razão | Grátis (registrado) |
| `experiment(ExperimentSpec)` | Intervenções da lista permitida com parâmetros dentro dos limites, controle, horizonte, nº de réplicas (limitado) | Diferenças pareadas de KPIs com IC, viabilidade, custo operacional | Custo operacional c(I) do orçamento B |
| `submit(Report)` | Conjunto de causas **ou** `unresolved{H…}` **ou** `refuted`; caminho causal citando IDs de evidência; ação recomendada; confiança | Sessão selada | — |

Lista permitida v0 de intervenções: aumentar trabalhadores do despachante; reduzir taxa de admissão; trocar política de despacho; incentivo a entregadores (aumenta oferta); não fazer nada. Cada uma com faixa de parâmetros e custo declarado.

Regras:

1. **Respostas não resolvidas e refutadas são válidas** e pontuadas separadamente de respostas erradas (ACDB, ISS).
2. Orçamento por instância: `B = custo do conjunto ótimo pré-calculado + folga` (ADR-0005).
3. O livro-razão de hipóteses é **registro**, não obrigação de procedimento: o agente pode investigar livremente (lição de *Free to Look*).
4. Tudo é registrado num **pacote selado** (ADR-0006).

## Baselines que usam o mesmo contrato

Regras especialistas; leitura sem rótulo da entrada; só nomes; classe majoritária; três *harnesses* simples (uma chamada sobre pacote de evidência, agente SQL, agente de código); RCA clássico adaptado; **ISS** com previsões do Gêmeo (modo B) e ISS-oráculo (modo A, cota superior); LLM base; LLM com SFT.

## Consequências

- Agentes e baselines são comparáveis no mesmo manifesto.
- A política ISS fornece um critério de parada verificável que também pode ser oferecido ao agente como ferramenta, em ablação.

## Emenda 1 (2026-11-01, G2.1)

1. **Nova intervenção na lista permitida:** `SetRetryBackoff(minutes ∈ [0,05, 10])`, intervalo de espera antes de repetir uma tentativa de despacho que falhou. É a intervenção que separa surto de erros de latência de dependência no L2.
2. **Horizonte do laboratório:** experimentos estendem o horizonte além do instante da intervenção (padrão: +150 min). Com sorteios por evento, isso só acrescenta futuro e não altera o passado.

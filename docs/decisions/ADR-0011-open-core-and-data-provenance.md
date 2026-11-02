# ADR-0011 — Núcleo aberto, fronteira comercial e proveniência dos dados

**Status:** Aceita parcialmente (2026-11-01) — itens 1–4 aceitos; item 5 (licença) resolvido pela ADR-0013 (2026-11-02) · **Gate:** G2 em diante

## Contexto

O responsável quer que o projeto possa virar produto rentável sem comprometer a pesquisa. O risco arquitetural é misturar dados sintéticos, inferências do gêmeo e dados reais, ou acoplar o núcleo a conceitos comerciais (clientes, contas) que depois impeçam abri-lo.

## Decisão

1. **Contrato de telemetria agnóstico à origem.** O esquema de telemetria (métricas, eventos de pedido, entidades) é versionado (`telemetry/v1`) e não depende do simulador. Toda série e todo evento carregam `source ∈ {simulated, real}` e o identificador da instância ou do conjunto de dados. O simulador é **uma** fonte; a ingestão de dados reais será outra, implementando a mesma interface.
2. **Nunca misturar origens.** Um conjunto de telemetria tem uma única `source`. O agente, o laboratório e os relatórios exibem a origem (o design system já exige a faixa "AMBIENTE SIMULADO"). Previsões do gêmeo são rotuladas como previsões, nunca como observações.
3. **Núcleo sem conceitos comerciais.** O pacote `deliverytwin` não contém clientes, contas, cobrança, autenticação ou multiusuário. Isso fica num futuro pacote/serviço separado (ex.: `deliverytwin-cloud`), em repositório próprio.
4. **Modo B é o caminho do produto.** O laboratório modo B e o nível L6 são tratados como requisitos de primeira classe, não como extensão (ADR-0003, ADR-0005).
5. **Licença (pendente).** Recomendação: núcleo de pesquisa sob licença permissiva (ex.: Apache-2.0) quando o repositório for aberto, e componentes comerciais proprietários em repositório separado. **Não adicionar LICENSE** até o responsável decidir. Enquanto isso o repositório permanece privado.

## Consequências

- O G2 implementa a telemetria já com o contrato `telemetry/v1` e o campo `source`.
- Dependências do núcleo continuam limitadas a licenças compatíveis com uso comercial; LaDe e similares só em scripts de calibração locais (ADR-0009).

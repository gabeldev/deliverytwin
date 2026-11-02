# DeliveryTwin AI — Design System do painel

**Data:** 2026-11-01 · **Decisão:** ADR-0010 · **Escopo:** painel para humanos (RFC §9). As ferramentas do agente são textuais e não usam este sistema.

## 1. Princípios

1. **Status epistêmico é a primeira dimensão visual.** Todo número, texto ou gráfico declara se é observação, hipótese, suposição do simulador, resultado de experimento ou recomendação (RFC §8).
2. **Nunca só cor.** Status = cor + ícone + rótulo textual. Funciona em escala de cinza e para daltônicos.
3. **Incerteza sempre visível.** Nenhum efeito sem intervalo de confiança; nenhuma confiança sem calibração declarada.
4. **Proveniência clicável.** Todo elemento carrega o ID da evidência, consulta ou experimento que o produziu.
5. **O ambiente é simulado, sempre.** Faixa fixa no topo de toda tela; não pode ser ocultada.
6. **Verdade oculta é outra rota.** A visão do Avaliador (que mostra F* e o DAG) usa um tema próprio e nunca aparece junto da investigação ao vivo.

## 2. Tokens

### 2.1 Cores semânticas de status (texto e borda; fundo com 8–12% de opacidade)

| Token | Status | Claro | Escuro | Ícone | Rótulo |
|---|---|---|---|---|---|
| `status.observation` | Observação da telemetria | `#1D4ED8` | `#93C5FD` | olho | OBSERVADO |
| `status.hypothesis` | Hipótese do agente | `#6D28D9` | `#C4B5FD` | ponto de interrogação | HIPÓTESE |
| `status.assumption` | Suposição do simulador/modelo | `#B45309` | `#FCD34D` | engrenagem | SUPOSIÇÃO |
| `status.experiment` | Resultado de experimento pareado | `#047857` | `#6EE7B7` | frasco | EXPERIMENTO |
| `status.recommendation` | Recomendação (exige aprovação) | `#BE185D` | `#F9A8D4` | seta | RECOMENDAÇÃO |
| `status.truth` | Verdade oculta (só Avaliador) | `#B91C1C` | `#FCA5A5` | cadeado | VERDADE OCULTA |

Contraste calculado (fórmula WCAG 2.x) em 2026-11-01. Todas as cores de status passam AA (≥ 4,5:1) sobre `surface.base` e `surface.raised` nos dois temas. Pior caso: `status.assumption` claro, 4,80:1 sobre `#F8FAFC`. Faixa de simulação: 8,15:1 (claro) e 11,7:1 (escuro). **Ainda não verificado:** texto sobre os fundos coloridos translúcidos de 8–12%; conferir antes do G6.

### 2.2 Neutros e superfície

| Token | Claro | Escuro |
|---|---|---|
| `surface.base` | `#FFFFFF` | `#0B1120` |
| `surface.raised` | `#F8FAFC` | `#111827` |
| `border.default` | `#E2E8F0` | `#1F2937` |
| `text.primary` | `#0F172A` | `#F1F5F9` |
| `text.muted` | `#475569` | `#94A3B8` |
| `banner.sim` | `#FEF3C7` fundo, `#78350F` texto | `#422006` fundo, `#FDE68A` texto |

### 2.3 Tipografia

- Interface: sans-serif do sistema (Inter, se disponível). Escala: 12 / 14 / 16 / 20 / 24 / 32.
- **IDs, chaves de evento, valores numéricos em tabelas:** monoespaçada (JetBrains Mono ou similar), números tabulares.
- Rótulos de status: 11–12 px, caixa alta, espaçamento de letras +0,04em.

### 2.4 Espaço, raio, elevação

Escala de espaçamento em múltiplos de 4 px (4, 8, 12, 16, 24, 32, 48). Raio 6 px (cartões), 4 px (chips). Uma única elevação para cartões; nada de sombras decorativas.

## 3. Componentes

| Componente | Função | Regras |
|---|---|---|
| `SimBanner` | Faixa "AMBIENTE SIMULADO — não representa operação real" | Sempre visível; inclui ID da instância e nível |
| `StatusChip` | Rótulo de status epistêmico | Cor + ícone + texto; obrigatório em todo cartão |
| `EvidenceCard` | Uma observação com consulta de origem | ID clicável, janela temporal, entidade ofuscada |
| `HypothesisLedger` | Tabela de hipóteses com estado (ativa, eliminada, sobrevivente) | Mostra qual evidência ou experimento eliminou cada uma; nunca exibe "correta" na visão ao vivo |
| `ExperimentResult` | Diferença pareada controle vs. tratamento | Ponto + IC; nº de réplicas; modo de laboratório (A ou B) sempre visível |
| `BudgetMeter` | Orçamento de consultas e de experimentos | Mostra gasto vs. B; destaca quando ISS certificaria parada |
| `IncidentTimeline` | Eventos e consultas no tempo | Marcadores coloridos por status; início do incidente marcado como estimado |
| `CausalPathView` | Caminho causal proposto pelo agente | Arestas citam IDs de evidência; arestas sem evidência ficam tracejadas |
| `RecommendationPanel` | Ação proposta | Botão "aprovar" só simula; texto lembra que nada é aplicado fora do sandbox |
| `EvaluatorDiff` | Comparação com a verdade (só rota do Avaliador) | Tema `status.truth`; DAG verdadeiro vs. proposto |

## 4. Gráficos

- Diferenças pareadas: **gráfico de pontos com IC**, linha de zero destacada; nunca barras sem IC.
- Distribuições de KPIs por réplica: faixas ou violinos discretos, com n visível.
- Séries de telemetria: linha simples; faixa do incidente sombreada com `status.observation`.
- Cores de séries categóricas seguem a skill `dataviz` quando os gráficos forem implementados; as cores de status epistêmico **não** são reutilizadas como cores de série.

## 5. Telas (RFC §9)

| Tela | Componentes principais |
|---|---|
| Mapa de operações | SimBanner, mapa, KPIs com StatusChip OBSERVADO |
| Linha do tempo do incidente | IncidentTimeline, EvidenceCard |
| Agente investigador | HypothesisLedger, chamadas ao vivo, BudgetMeter |
| Laboratório contrafactual | ExperimentResult, seleção de modo A/B |
| Bancada de pesquisa | Tabelas de avaliação em camadas, pisos e MDE |
| Avaliador (rota separada) | EvaluatorDiff, CausalPathView vs. DAG verdadeiro |

## 6. Acessibilidade

Contraste AA para texto; foco visível; navegação por teclado; status anunciado por leitores de tela via rótulo; nenhuma informação transmitida só por cor ou animação.

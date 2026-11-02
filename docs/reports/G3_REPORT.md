# G3 — Relatório: investigador, laboratório, avaliador e primeiros agentes LLM

**Data:** 2026-11-02 · **Gate:** G3 (RFC §11) · **Dados:** `docs/reports/G3_REPORT_DATA.json` (`scripts/g3_report.py`), execuções em `runs/g3/` (ignorado pelo git) · **Executor:** `scripts/run_g3.py`

## 1. O que foi implementado

| Componente | Conteúdo |
|---|---|
| `agent/protocol.py` | Tipos das 5 operações (ADR-0004); taxonomia pública de falhas; vocabulário de nós causais; custo das intervenções |
| `agent/queries.py` | Consultas somente leitura sobre `telemetry/v1`: pedidos por janela/zona/restaurante e medidores (perfil completo) |
| `agent/session.py` | Orquestrador: validação, orçamento (25 consultas, 4 experimentos, 10 unidades), evidências numeradas, pacote selado sem dados privados; laboratório modo A (bifurcações pareadas do mundo verdadeiro a partir do alerta, coorte fechada) |
| `benchmark/evaluator.py` | Avaliador isolado: causa e escopo, abstenção, F1 do caminho causal, validade das evidências citadas, Brier, efeito medido da recomendação |
| `agent/baselines.py` | Agentes sem LLM no mesmo protocolo: **regras** e **manual + experimento** (separação intervencional baseada em conhecimento) |
| `agent/llm.py`, `agent/llm_agent.py` | Agente LLM com ferramentas (OpenAI) e **teto rígido de custo** com registro por chamada; chave lida do `.env`, nunca registrada |
| `scripts/check_secrets.py` | Varredura de segredos no hook antes do commit e no CI |

## 2. Protocolo de avaliação

- **Sementes:** desenvolvimento 2026 (regras e prompts ajustados nela); 909090 (fora da amostra, mas **inspecionei transcrições de LLM nela**, então deixou de ser intocada); **final 515151, intocada**: todos os números abaixo.
- 20 instâncias por nível (L0, L1, L2), as mesmas para todos os agentes, o que permite comparação pareada (McNemar exato).
- Modelos: gpt-5-nano (raciocínio baixo), gpt-5.6-luna (sem raciocínio: a API não aceita ferramentas com raciocínio nesse modelo pela rota usada), gpt-5-mini (raciocínio baixo). Luna e mini rodaram **duas vezes** para medir o ruído entre execuções.

## 3. Resultados (semente final 515151, laboratório corrigido após a revisão)

Execuções marcadas `_fix`, feitas depois das correções da revisão independente (§7). Acurácia exata (causa + escopo) com IC de Wilson 95%:

| Agente | L0 | L1 | L2 | Comprometimento errado no L2 | Brier (só diagnósticos comprometidos) L2 | US$/caso |
|---|---|---|---|---|---|---|
| Regras | 0,50 [0,30, 0,70] | 0,70 [0,48, 0,86] | 0,00 (abstém 65%) | 0,35 | 0,49 | 0 |
| Manual + experimento | 0,50 [0,30, 0,70] | 0,70 [0,48, 0,86] | **0,65 [0,43, 0,82]** | 0,35 | 0,20 | 0 |
| gpt-5-nano | 0,25 | 0,40 | 0,10 | 0,85 | 0,33 | 0,0011 |
| gpt-5.6-luna | 0,80 [0,58, 0,92] | 0,75 | 0,00 (abstém 60%) | 0,40 | 0,42 | 0,0018 |
| gpt-5-mini | **0,90** [0,70, 0,97] | 0,75 | 0,30 [0,15, 0,52] | 0,70 | 0,44 | 0,0051 |

Comparação pareada contra o baseline manual + experimento (McNemar exato, 20 pares):

| Nível | Resultado |
|---|---|
| L2 | O baseline vence luna (p = 0,0002) e nano (p = 0,001). **Contra o mini a diferença não é significativa** (0,65 vs. 0,30; p = 0,09) |
| L0 | Mini melhor que o baseline (p = 0,02); luna 0,80 vs. 0,50 (p = 0,07) |
| L1 | Nenhuma diferença significativa |

**Variabilidade entre execuções** (medida nas execuções anteriores às correções, as únicas repetidas): o mesmo modelo, nas mesmas 60 instâncias, dá a mesma resposta em ~68–72% dos casos, e a acurácia do mini oscila de 0,65 para 0,53. Esses números descrevem a variabilidade observada em duas repetições. **Não são** um limiar de efeito mínimo: estimar isso exige mais repetições por modelo e nível (correção da revisão).

## 4. Leitura

1. **Leitura observacional:** com os medidores operacionais (L0), mini e luna superam as regras escritas à mão (0,80–0,90 contra 0,50); para o mini a diferença é significativa.
2. **Uso de experimentos:** no L2, onde a observação não separa as causas por construção, o procedimento sistemático acerta 0,65. Os LLMs ficam entre 0,00 e 0,30: diferença significativa para luna e nano, **não significativa para o mini com n = 20**. A afirmação anterior de que o baseline vencia todos os LLMs foi retirada após o reprocessamento.
3. **Confiança:** os erros no L2 são em grande parte comprometimentos errados (mini 70%, nano 85%). O luna prefere se abster (60%), o que é mais honesto, mas também não resolve.

## 5. Defeitos encontrados durante o G3 (e corrigidos antes da avaliação final)

- **Esquema de ferramenta ambíguo:** uma única `query` anunciava campos de pedidos e de medidores; o modelo misturava e a validação rejeitava. Isso gerou 181 erros numa execução. Dividida em `query_orders` e `query_gauges`, com os limites da validação no esquema; os erros de ferramenta caíram de 5,3 para 0,27 por investigação.
- **Medidores no perfil do cliente** custavam uma consulta e recebiam ID de evidência; agora é erro sem custo.
- **Experimento com 1 réplica** mostrava um "IC" de largura zero; agora o mínimo é 2 réplicas.
- O prompt passou a descrever **o que cada intervenção faz** (como num manual de operação) e o princípio de mudar um fator por vez. **Não** diz qual intervenção corrige qual causa.

## 6. Limitações e pendências

- 20 instâncias por nível: ICs de ±0,20. As conclusões do L2 resistem a isso (p ≤ 0,02 em todas as comparações); as do L0 e L1, não.
- **Laboratório modo B (gêmeo) não implementado**; o L6 depende dele. **ISS-oráculo** substituído pelo baseline manual + experimento, baseado em conhecimento.
- O F1 do caminho causal pode ser parcialmente "comprado" listando muitos nós (o nano fez isso); a precisão limita o ganho, mas a métrica deve ser lida junto com a acurácia.
- O luna rodou sem raciocínio por limitação da rota de API usada; usar a API de Responses pode mudar o resultado.
- O orçamento de experimento (10 unidades) é uma escolha de desenho; agentes que gastam muito numa intervenção cara ficam sem testar a discriminante. Isso é parte do que o benchmark mede, mas o valor exato não foi calibrado.
- Gasto total com LLM até aqui: US$ 1,02 (teto US$ 1,50).

## 7. Revisão independente (Codex) e reprocessamento

Revisão completa em `docs/reviews/CODEX_REVIEW_G3.md`. 12 achados, todos reproduzidos e corrigidos; regressões em `tests/agent/test_review_g3.py`. **Nenhum vazamento** da verdade oculta foi encontrado.

| # | Gravidade | Achado | Correção |
|---|---|---|---|
| 1 | Média | Reduzir a admissão "melhorava" a taxa de pedidos ruins só por rejeitar clientes (admissão 0,1: 0,727 → 0,104) | Coorte de **toda a demanda** criada na janela; rejeitado conta como ruim; o laboratório reporta a fração rejeitada (agora 0,727 → 0,910) |
| 2 | Média | Experimento válido com admissão quase zero travava a sessão | Resposta controlada; coorte de demanda nunca fica vazia |
| 3 | Média | IC com 1,96 para 2–5 réplicas (estreito demais) | t de Student |
| 4 | Média | Recomendação avaliada nos mesmos futuros usados para escolhê-la | Avaliador usa réplicas disjuntas (offset 1000) |
| 5 | Média | Não responder dava Brier perfeito | Brier só para diagnósticos comprometidos; cobertura reportada à parte |
| 6 | Média | Baselines liam um sinal (idade dos pedidos abertos) que o LLM não tinha | Coluna `mean_open_age` na consulta de pedidos; diferença de acesso documentada abaixo |
| 7 | Média | Estimativa de pior caso de tokens podia subestimar | Limite pelos bytes UTF-8 + 1000 tokens de enquadramento |
| 8 | **Alta** | Clientes concorrentes podiam gastar o mesmo saldo | Reserva sob trava de arquivo antes da chamada; teste falha sem a trava |
| 9 | **Alta** | Uso ausente ou falha de registro deixava gasto sem contabilizar | Reserva durável antes; sem uso conhecido, a reserva fica como gasto |
| 10 | Média | Varredura de segredos ignorava arquivos com nome não ASCII | Caminhos com `-z`; leitura falha = arquivo bloqueado |
| 11 | Baixa | "Mesma resposta" ignorava escopo e conjuntos não resolvidos | Compara o diagnóstico completo |
| 12 | Média | Afirmação de um "piso de ruído de 0,12" universal sem base | Reescrita como variabilidade observada (§3) |

**Diferença de acesso que permanece:** os baselines aplicam regras sobre a telemetria pública inteira, sem gastar consultas; os LLMs veem a mesma telemetria por consultas agregadas com orçamento. A coluna `mean_open_age` reduz, mas não elimina, a diferença. Isso favorece os baselines nos níveis observacionais (L0/L1), onde mesmo assim os LLMs vencem.

**Reprocessamento:** como o laboratório mudou o que os agentes veem, a avaliação final foi refeita (execuções `_fix`). O gasto total com API chegou a **US$ 1,49** do teto de US$ 1,50; por isso não houve segunda repetição pós-correção dos LLMs.

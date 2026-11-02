# Revisão sistemática de literatura — LR-001

**Data da busca:** 2026-11-01 · **Escopo:** apoiar `docs/architecture/ARCH_RESEARCH_001.md` e o RFC 001
**Tipo:** revisão sistemática *leve* (inspirada em PRISMA, mas **um único revisor** e **uma única base de preprints**). Não é uma revisão sistemática completa e não deve ser descrita como tal em publicação.

## 1. Perguntas de revisão

- **LQ1.** Existem agentes LLM que validam hipóteses de causa-raiz por **intervenção em simulação/gêmeo digital** (e não só por leitura de telemetria)?
- **LQ2.** Como a literatura controla variância em comparações pareadas de simulação (CRN, seeds) e como isso se aplica a agentes?
- **LQ3.** Que benchmarks, geradores e métricas de RCA com agentes já existem, e o que eles medem?
- **LQ4.** Que evidência há sobre treinar modelos locais/pequenos (SFT, GRPO) para diagnóstico?
- **LQ5.** Que simuladores/benchmarks de despacho e entrega existem?
- **LQ6.** Há tratamento de abstenção/identificabilidade quando a causa não é distinguível por observação?

## 2. Fontes e estratégia

| Fonte | Uso | Observação |
|---|---|---|
| arXiv API (`export.arxiv.org`) | 16 consultas por resumo, ordenadas por relevância; 1 consulta por lista de IDs em 3 lotes (20 resumos) | Busca principal |
| Semantic Scholar API | Encadeamento de citações *forward* para 3 sementes | Cobertura baixa e 1 resposta HTTP 429 (limite de taxa) |
| OpenAlex API | 1 consulta de teste | **Descartada**: ranking por relevância ruidoso (resultados fora do tema) |
| Busca web | Rodada anterior (ARCH-001) | Usada só como pista inicial |
| `paper-search-cli` (skill labrat) | — | **Não executado**: a instalação foi bloqueada pelo ambiente |

**Não coberto:** ACM DL, IEEE Xplore, Scopus, Web of Science, Google Scholar, anais de WSC/INFORMS/ICSE/KDD fora do arXiv, e literatura de pesquisa operacional publicada em periódicos fechados.

## 3. Consultas executadas (arXiv, campo de resumo)

| # | Consulta (resumida) | Total no feed | Recuperados |
|---|---|---:|---:|
| Q1 | root cause ∧ (LLM ∨ language model) ∧ agent | 226 | 30 |
| Q2 | benchmark ∧ (incident ∨ fault injection) ∧ agent ∧ LLM | 80 | 30 |
| Q3 | counterfactual ∧ simulation ∧ LLM agent(s) | n/d | 18 |
| Q4 | (food/instant/on-demand delivery) ∧ (simulator ∨ simulation ∨ benchmark) | 39 | 30 |
| Q5 | digital twin ∧ LLM ∧ (diagnosis ∨ root cause ∨ what-if) | n/d | 26 |
| Q6 | (common random numbers ∨ paired seeds ∨ paired evaluation) ∧ (simulation ∨ agent) | 82 | 30 |
| Q7 | (root cause ∨ fault localization) ∧ (causal graph ∨ propagation path ∨ process supervision ∨ step-level) ∧ (LLM ∨ agent) | n/d | 20 |
| Q8 | (fine-tune ∨ RL ∨ GRPO) ∧ (root cause ∨ incident ∨ AIOps ∨ SRE) ∧ (SLM ∨ LoRA ∨ 7B) | n/d | 4 |
| Q9 | (active intervention ∨ experiment design) ∧ causal discovery ∧ LLM | n/d | **0** (restritiva demais) |
| Q10 | (abstention ∨ selective prediction ∨ conformal) ∧ (root cause ∨ diagnosis) ∧ (agent ∨ LLM) | n/d | 28 |
| Q11 | (DES ∨ SimPy) ∧ (LLM ∨ language model) | n/d | 22 |
| Q12 | LLM ∧ hypothesis ∧ intervention ∧ (diagnosis ∨ root cause ∨ troubleshooting) | n/d | 3 |
| Q13 | (dynamic pickup-delivery ∨ order dispatching/assignment) ∧ (benchmark ∨ simulator) | 26 | 25 |
| Q14 | (verifiable reward ∨ GRPO) ∧ (cloud ∨ SRE ∨ AIOps ∨ incident) ∧ diagnosis | n/d | **0** |
| Q15 | (contamination ∨ leakage) ∧ (synthetic/simulated benchmark) ∧ (agent ∨ LLM) | n/d | 5 |
| Q16 | (observationally equivalent ∨ identifiability) ∧ (root cause ∨ fault diagnosis) ∧ (intervention ∨ experiment) | 286 | 20 |
| | **Total de registros recuperados** | | **≈ 291** |

Limitação visível: para as consultas Q1, Q2, Q4, Q6 e Q16 o feed informa muito mais resultados do que os 20–30 recuperados. **Só vi o topo do ranking de relevância**; não há garantia de exaustividade.

Duas consultas com 0 resultados (Q9, Q14) foram restritivas demais; Q8 e Q12 também voltaram pouco. Isso é falha de formulação minha, não evidência de ausência de literatura.

## 4. Triagem

- **Critérios de inclusão:** (i) agente/LLM/simulador aplicado a diagnóstico, RCA, intervenção, despacho/entrega, ou método de simulação (CRN/seeds) diretamente transferível; (ii) 2023–2026 salvo trabalhos metodológicos clássicos; (iii) resumo disponível.
- **Exclusão:** domínio sem transferência (ex.: imagem médica, drones, segurança ofensiva) mesmo quando bem avaliado.
- **Processo:** triagem por título e resumo por mim (revisor único, sem dupla checagem, sem medida de concordância). Cerca de 45 registros ficaram como candidatos; **29 resumos foram lidos na íntegra** (9 na rodada anterior, 20 nesta). Os demais ficaram só no nível de título e resumo curto da listagem.
- **Ferramenta:** `WebFetch` resume a página com um modelo menor. Isso pode omitir entradas ou distorcer números. Valores citados abaixo vêm dos resumos devolvidos e **devem ser conferidos nos papers originais** antes de uso em publicação.
- Vários IDs de arXiv são de jun–out/2026 e não têm revisão por pares verificada.

## 5. Estudos incluídos (resumos lidos)

### 5.1 RCA com agentes: benchmarks, falhas e baselines

| ID | Contribuição | Resultado-chave (do resumo) | LQ |
|---|---|---|---|
| 2606.27154 OpenRCA 2.0 | Rótulos causais passo a passo via injeção | exato 20,7%; relaxado 76,0%; fundamentado 61,5% | 3 |
| 2607.28545 ORCA-bench | 1.079 tarefas, relatos ambíguos | melhor 25,3% (médio) / 10,0% (difícil); alucinação até 40% | 3 |
| 2608.21310 Trajetórias | 5.000 trajetórias, 10 configurações | falhas: evidência omitida / mal interpretada / sem suporte | 3 |
| 2602.09937 Pitfalls em OpenRCA | 1.675 runs, 5 LLMs, 12 tipos de falha | alucinação na interpretação e exploração incompleta persistem em todos os modelos; mais estrutura de comunicação entre agentes reduz falhas de comunicação em até 15 p.p. | 3 |
| 2601.22208 Stalled, Biased, Confused | 48.000 cenários simulados; 16 falhas de raciocínio | taxonomia de erros por LLM-juiz | 3 |
| **2610.35767 Free to Look** | 3 *harnesses* simples vs. 5 agentes publicados, RCAtlas (90 casos, 8 datasets) | simples: PR@1 65–77% (modelos médios); agentes publicados 16–53%; não-LLM 6–39% | 3 |
| 2510.04711 Benchmarks realistas | gerador; 1.430 casos de 9.152 injeções | regras ≈ SOTA nos benchmarks antigos; top-1 médio 0,21 no novo | 3 |
| **2610.30004 Gerador de alarmes telecom** | gerador **Apache-2.0** com causa exata e caminho de propagação; 9 baselines | regra "primeiro alarme crítico" top-1 0,650 vs. 0,575 do método temporal; em perda de energia de um site, métodos que ranqueiam dispositivos alarmados pontuam 0,000 enquanto os que andam pela topologia pontuam 1,000 e 0,833 | 3, 6 |
| 2605.14866 / 2508.20370 / 2509.15635 / 2504.20462 / 2404.12135 / 2502.08224 | Agentes de RCA (recursion-of-thought, MicroRCA-Agent, TAMO, mABC, Flow-of-Action) | variam; não comparáveis entre si | 3 |
| **2607.04623 R2Act** | 302 incidentes Kubernetes, ações válidas anotadas | RAG-LLMs acertam a causa em 91,4–99,7% mas só 36,8–60,3% das recuperações são válidas; 39,5–62,0% de ações inválidas mesmo com diagnóstico certo | 1, 3 |
| 2609.33023 SRE-Marathon | falhas sobrepostas em agenda semeada; *sealed bundle*; pontuação offline determinística | melhor de 10 métodos: 41,3/100; agentes localizam mas quase nunca reparam | 3 |
| 2608.27182 TraceBench | tarefas geradas por simulação de sistemas físicos | agentes usam saída numérica melhor que gráficos; contexto de domínio ajuda; resultados e *leaderboard* publicados | 3 |
| 2610.19291 CoffeeBench | agente diagnostica eletrodoméstico simulado | melhores estreitam o espaço de falhas iterativamente; incerteza inicial e coerência prevêem sucesso | 3, 6 |
| 2607.28802 Model or Harness? | taxonomia de 41 modos de falha por interface | juiz mais forte κ=0,76 | 3 |

### 5.2 Intervenção/contrafactual com LLM

| ID | Contribuição | Limite para nós | LQ |
|---|---|---|---|
| 2509.10401 A2P | Abdução → ação corretiva mínima → predição da trajetória, **em uma passada do LLM**; 47,46% vs. 16,67% (Who&When, gerado por algoritmo) | O "contrafactual" é previsto pelo próprio LLM, não executado em simulador; domínio = falhas de sistemas multiagente | 1 |
| **2609.11264 GuardedAct** | Sandbox de gêmeo digital estima *blast radius* de ações propostas por LLM; recuperação 87,4%; dano colateral cai de 25,6% para 5,2% | Valida **ações de remediação**, não hipóteses de diagnóstico; 5 cenários em DeathStarBench | 1 |
| 2608.23622 Experimentos controlados | Agentes LLM desenham e rodam experimentos em modelos de simulação (farmacêutico) | Avaliação qualitativa, sem código | 1 |
| 2607.22385 AgentRCA | Gêmeo de dinâmica normal + LLM com ferramentas; pesa hipóteses concorrentes; competitivo com supervisionado | Gêmeo é modelo de dados, não intervenção; sem código | 1 |
| 2609.01360 EDGE | Grafos de dependência de erro verificados por *rollouts* contrafactuais | Sistemas multiagente | 1 |
| 2406.08106, 2505.00930, 2606.05636, 2606.20912 | RCA contrafactual / por intervenção / sem grafo / com confundidores latentes | Métodos estatísticos clássicos, sem agente | 1, 6 |

### 5.3 Simulação, pareamento e variância

| ID | Contribuição | LQ |
|---|---|---|
| **2603.11084 Event-Keyed Hashing** | PRNG com estado quebra CRN quando intervenções mudam o caminho de execução (o índice de sorteio desloca). Propõe geradores **baseados em contador (Philox/Threefry)** com ID do evento, de modo que cada sorteio é função do evento que o pediu | 2 |
| 2605.04732 CRN em planejamento por rollouts | CRN reduz variância ao comparar ações | 2 |
| 2512.24145 Pairing seeds | Variância estritamente menor quando as saídas são positivamente correlacionadas por seed | 2 |
| **2606.20695 Noise-floor** | Medir primeiro a discordância pareada entre configurações **equivalentes**; 7 de 10 arquiteturas relatadas têm efeito abaixo desse piso | 2 |
| 2609.29522 Stale ≠ unsafe | Simulador determinístico, propostas de agentes **congeladas e reproduzidas** sem LLM-juiz; guardas por frescor bloqueiam 92–95% das corridas benignas | 2, 3 |
| 2609.24144 Luck Is Not Skill | Rollouts pareados em RL relativo-a-grupo de agentes (citante de 2603.11084) — **só título; não li** | 2, 4 |

### 5.4 Treino

| ID | Contribuição | LQ |
|---|---|---|
| **2603.03378 AOI** | GRPO para destilar conhecimento em modelos locais; modelo 14B chega a 42,9% avg@1 em 63 tarefas com falhas inéditas, acima de Claude Sonnet 4.5; trajetórias com falha viram supervisão corretiva (37 falhas → +4,8 p.p., variância −35%). Sem código declarado | 4 |
| 2605.02906 OpsLLM | LLM de operações com treino em estágios | 4 |
| 2607.18725 Find Before You Fine-Tune | Em QA de cibersegurança, fine-tuning de LLMs pequenos frequentemente **piora**; instruction tuning causa perda de conhecimento por abstenção | 4 |
| 2608.27847 CaRDI | Planejamento de perguntas por **risco calibrado** em vez de entropia: −21,5% de perda clínica, menos perguntas | 6 |

### 5.5 Logística/despacho

| ID | Contribuição | LQ |
|---|---|---|
| 2603.12559 LLM-DR | Simulação de entrega sob demanda com agentes-entregadores LLM (9.025 pedidos de Pequim); **código e dados anonimizados publicados** | 5 |
| 2607.10173 RideGym | Interface Gym para despacho em ride-sharing; ranking de métodos muda com o ruído de exploração | 5 |
| 2202.01256 ICAPS 2021 DPDP | Benchmark e simulador de logística real, usado por 152 equipes | 5 |
| 2608.10897, 2607.22356, 2601.21858, 2402.10725, 2610.02122 | Despacho multiplataforma, despacho+rota, regra de custo-balanceado, Cloud Kitchen, Argo-Bench | 5 |
| 2512.19234 DeliveryBench | Agente como operador | 5 |
| LaDe 2306.10675 | Dataset de last-mile (CC BY-NC-SA) | 5 |

### 5.6 Abstenção e identificabilidade

| ID | Contribuição | LQ |
|---|---|---|
| 2608.21412 Abstention Protocol (Clos) | RCA com álgebra de abstenção em vez de fusão ponderada | 6 |
| 2607.26481 | Changepoint e RCA conformais com observações corrompidas | 6 |
| 2410.12151, 2406.05014 | Condições de identificabilidade da causa-raiz em modelos lineares/politrees | 6 |
| Q15 (vazamento) | Resultados na maioria fora do domínio; não encontrei trabalho direto sobre vazamento de rótulo em benchmarks sintéticos de RCA | 6 |

## 6. Síntese por pergunta

- **LQ1 (intervenção em simulação).** Há peças adjacentes, mas não a combinação. A2P usa contrafactual **imaginado** pelo LLM; GuardedAct usa sandbox para **validar ações**; AgentRCA e 2608.23622 usam gêmeos/simuladores sem pareamento nem avaliação com causa oculta verificável; os métodos contrafactuais clássicos não têm agente. **Não encontrei** (nestas consultas) um agente LLM que teste **hipóteses de diagnóstico** por experimentos pareados num simulador com causa oculta. Resultado condicionado às limitações da seção 7.
- **LQ2 (pareamento).** Literatura recente confirma e **refina** o desenho: PRNG com estado quebra o CRN quando a intervenção muda o caminho de execução, e a solução proposta é RNG de contador indexado por evento (2603.11084). Medir também o *noise floor* entre configurações equivalentes (2606.20695).
- **LQ3 (benchmarks).** Consenso: acertar a causa esconde raciocínio ruim (OpenRCA 2.0, trajetórias, pitfalls). Regras simples e *harnesses* mínimos igualam ou superam agentes sofisticados (2510.04711, 2610.30004, 2610.35767). Diagnóstico certo não implica ação válida (R2Act).
- **LQ4 (treino).** GRPO local em modelo de 14B funciona em diagnóstico de nuvem segundo o resumo do AOI; aprendizado com trajetórias falhas ajuda. Para modelos pequenos, fine-tuning pode piorar (2607.18725). Não há evidência para 6 GB.
- **LQ5 (despacho).** Existem simuladores e benchmarks abertos de despacho/ride-sharing/pickup-delivery (RideGym, ICAPS-DPDP, LLM-DR) que podem fornecer baselines e conferência. Não encontrei simulador aberto de entrega de comida com injeção de falhas **operacionais** e causa oculta.
- **LQ6 (abstenção/identificabilidade).** Há RCA com abstenção e identificabilidade teórica, mas não encontrei benchmark com **classes de equivalência observacional** para agentes. O gerador de telecom mostra um exemplo concreto: algoritmos que só ranqueiam dispositivos alarmados pontuam 0,000 quando a causa é perda de energia do site, o que é um caso natural de causa não identificável pela mesma observação.

## 7. Limitações da revisão

1. Base única de preprints (arXiv) e só 16 consultas; ACM/IEEE/Scopus não consultadas.
2. Topo do ranking apenas; não vi a cauda de consultas com centenas de resultados.
3. Revisor único, sem dupla triagem; critérios de inclusão aplicados por julgamento.
4. Resumos lidos via `WebFetch` (sumarização intermediária); números não conferidos nos PDFs.
5. Encadeamento de citações incompleto: Semantic Scholar devolveu 1–9 citantes por semente (cobertura baixa) e teve uma resposta 429; encadeamento *backward* não feito.
6. Q9 e Q14 vazias por formulação; `paper-search-cli` bloqueado.
7. Lacunas ("não encontrei") **não** comprovam ausência; antes de afirmar novidade é necessária repetição em ACM/IEEE/Scholar e leitura dos textos completos dos candidatos mais próximos: 2509.10401, 2609.11264, 2608.23622, 2607.22385, 2609.01360, 2603.03378.

## 8. Próximos passos de busca (se quiser aprofundar)

- Executar `paper-search` (skill labrat) em ambiente permitido, com ACM/IEEE via credenciais, e encadeamento *forward/backward* sobre: 2603.03378, 2603.11084, 2609.11264, 2509.10401, 2607.04623, 2606.27154.
- Reformular Q9/Q14 com termos mais curtos (ex.: "interventional diagnosis" ∧ LLM; "GRPO" ∧ "root cause").
- Buscar: seleção de hipóteses por ganho de informação com custo; *replay* de agentes (cut-point replay / Chronicle); simulação de entrega com falhas operacionais em periódicos de pesquisa operacional.
- Ler integralmente: 2603.11084 (CRN por evento), 2606.20695 (noise floor), 2610.35767 (harness simples), 2603.03378 (AOI), 2607.04623 (R2Act).

---

# Rodada 2 — multi-base com `paper-search` (2026-11-01)

O `paper-search-cli` foi instalado com autorização explícita do usuário (dependências conferidas antes: `requests`, `feedparser`, `pypdf`, `beautifulsoup4`, `pydantic`). Scripts de execução em área temporária de sessão, não no repositório.

## 9. Protocolo da rodada 2

| Item | Detalhe |
|---|---|
| Bases consultadas | DBLP, OpenAlex, Crossref, ACM, OpenReview (lote 1); as mesmas mais arXiv (lote 2) |
| Bases indisponíveis | Semantic Scholar (HTTP 429, sem chave de API); Google Scholar (página de captcha). Scopus e Web of Science exigem credenciais que não estão configuradas e **não foram tentados** |
| Lote 1 | 10 consultas × 5 bases × 15 resultados: 570 registros, 511 após remover títulos duplicados |
| Lote 2 | 6 consultas dirigidas a lacunas × 6 bases × 12 resultados: 272 registros |
| Encadeamento de citações | 7 sementes × 2 direções = 14 chamadas. **Só 3 devolveram registros**: referências do HERO (40 de 47 disponíveis, truncado), 1 citante do Cloud-OpsBench e 1 do A2P. O OpenAlex ainda não tem os vínculos de citação desses preprints recentes. O encadeamento deve ser considerado **não efetivo** |
| Triagem | Título e resumo por mim, revisor único, sem dupla checagem. Os resumos foram lidos a partir do campo `abstract` devolvido pelas bases (não do PDF); alguns vieram truncados ou ausentes |
| Total acumulado de registros | ≈ 291 (rodada 1) + 842 (rodada 2) = ≈ 1.130, com sobreposição entre rodadas |

Consultas do lote 1: agente LLM de RCA com intervenção em simulação; gêmeo digital LLM com experimento contrafactual; CRN em simulação baseada em agentes; despacho de comida com falhas; despacho sob demanda com benchmark/simulador; benchmark de RCA com injeção de falhas; fine-tuning de modelo pequeno para RCA; teste de hipótese intervencional para causa-raiz; avaliação de agentes com verdade oculta; redução de variância em DES.
Consultas do lote 2: geradores de números aleatórios por contador (Philox/Threefry); vazamento de resposta por nomes de variáveis; estado oculto observacionalmente equivalente; estado de crença com hipóteses concorrentes e orçamento; agente que simula mitigação em sandbox/gêmeo; QLoRA para tool-calling em GPU de consumo.

## 10. Novos estudos incluídos (resumos lidos)

| ID / DOI | Contribuição | Resultado-chave (do resumo) | Impacto |
|---|---|---|---|
| **2609.31675 ACDB** | Ambiente baseado em SCM onde agentes LLM recuperam o grafo causal a partir de observações e **intervenções duras com orçamento**; API *observe–intervene–submit*; pontuação em 3 camadas (esqueleto, DAG, eficiência de intervenção) | PC com heurística ativa gulosa é o melhor não-oráculo (F1 dirigido 42,7%) à frente de Claude Sonnet 4.6 (31,7%) e GPT-5.4 (22,9%); LLMs **comprometem demais** (menos precisão); acesso a ferramentas estatísticas aumenta abstenção | Precedente direto de "agente com intervenções orçadas". Reduz novidade de G1 em causalidade genérica; fornece contrato de API e pontuação |
| **2609.32247 ISS** | *Interventional Separation Selection*: consultar uma intervenção admissível em que os modelos candidatos sobreviventes **discordam**, descartar os contraditos, parar quando nenhuma intervenção dentro do custo separa os sobreviventes; certifica concordância em todas as intervenções admissíveis até o limite | Garantia que nenhum aprendiz puramente observacional dá | **Política não-LLM de seleção de experimentos** para usar como baseline/oráculo; formaliza "experimento discriminativo" |
| openreview "Observationally Equivalent, Interventionally Different" | Alvo de intervenção é identificável sse constante na **fibra observacional** | Cota minimax e certificado de não-identificabilidade | Base formal da ideia de classes de equivalência observacional |
| 10.21203/rs.3.rs-10730245 *Did It Happen?* | Benchmark contrafactual: cada unidade **pareia dois estados ocultos atrás de um timeout idêntico**; teto exato de 0,5 sem informação | 756 pares: 0,4979 com conselho no prompt, 0,8066 com reconciliação de estado, 1,0000 com contrato idempotente (só um modelo/serviço) | **Precedente do desenho de pares equivalentes com teto exato**. Mostra também que informação disponível não garante uso correto |
| openreview *Recovery Credit Under Hidden Physical State* | Configurações pareadas expõem a mesma informação ao agente; ações de diagnóstico resolvem a ambiguidade; métricas de conclusão pareada e uso de intervenção | Microbenchmarks com checagens determinísticas | Mesmo padrão em robótica |
| **10.1145/3832783.3837509 HERO** | RCA centrada em hipóteses: instanciação limitada do espaço de hipóteses, **estado de crença explícito** e aquisição de evidência guiada por ambiguidade | OpenRCA: SR 79,77, +23,20 sobre a melhor base estilo ReAct, com 1,04 ações a menos; dataset industrial: 85,00. Referências incluem teoria de evidências (Dempster-Shafer) e LM-PACE (confiança em causa-raiz) | O "livro-razão de hipóteses" **não é novo**; é observacional. Passa a ser baseline forte |
| openreview EviDiag; EviDx (EMNLP Findings 2026) | Busca de evidência guiada por posterior e valor de informação de horizonte finito; atualização bayesiana | Domínios de séries temporais e clínico | EIG/valor da informação = prática estabelecida; baseline |
| **10.21203/rs.3.rs-11401166** *Where Does the Accuracy Come From?* | Estudo **pré-registrado** em RCAEval (RE2 270, RE3 90): isola detectores, texto e modelo | Agente AC@1 0,44 < contagem do detector 0,60 < N-Sigma 0,80; pipeline genérico 0,87, +0,30 por causa da evidência mostrada e +0,05 pelo prompt; erro de início de 2 min derruba para 0,27; texto falso ("decoy") nomeado primeiro em 21–42% vs. ~4% | Baseline "leitura sem rótulo da entrada"; testes com decoy, ablação de texto e deslocamento de início |
| **2610.22846 Heuresis** | Benchmark de datasets simulados **anônimos** para descoberta causal agêntica | Só pelos **nomes** das variáveis, um LLM acerta 99% das direções do Tübingen | **Evidência direta de vazamento por nomes**. Obriga a ofuscar nomes e a incluir baseline "só nomes" |
| 2603.00468 Cloud-OpsBench | 754 casos, 57 tipos de falha; falhas capturadas como **snapshot de estado** e reexecutadas por interfaces padrão | Acurácia conjunta 0,76 / 0,68 mas **taxa de fechamento de evidência** só 0,38 / 0,15 | Apoia fork/replay por snapshot; adotar métrica de fechamento de evidência |
| 10.1145/3797100 (versão publicada de 2510.04711) | Benchmark com propagação de falha | Regras simples ≈ SOTA nos 4 benchmarks antigos | Confirma baseline de regras |
| openreview *Telecom-Specific SLMs for RCA* | Destila professor de 8,3B em Qwen2.5-1,5B com LoRA; classificação em 8 classes | 84,72% de acurácia; 97 trocas entre duas classes parecidas; sistema hierárquico com especialista de evidência chega a 94,44%; **forte sensibilidade à serialização da telemetria**; memória de pico 4,53× menor | Precedente de SLM de 1,5B em RCA; teste de robustez à serialização; confusão entre classes quase equivalentes |
| 10.2139/ssrn.7201500 *Agent-trace FT of SLMs under constrained compute* | Fine-tuning em GPUs de 16 GB | Receita ingênua: perda cai 47–87% mas **esquecimento catastrófico** (−18,9 em HumanEval) escondido na curva de perda; correções: perda só sobre a completude, replay de domínios mistos, decontaminação aproximada; "vazamento de sessão" | Protocolo do G4. **Não é 6 GB** |
| openreview *Internalizing Tool Knowledge in SLMs via QLoRA* | QLoRA 8 bits em Gemma 4 E4B e Qwen3-4B, ~1.700 exemplos, inferência sem descrição de ferramentas | Entrada 82,6% menor; AT-F1 0,65 vs. 0,47 do baseline informado | Precedente de SFT de tool-calling em Qwen3-4B (hardware não declarado no resumo) |
| openreview *ToolGuard* | Red-teaming de SLMs de 1B a 4B em tool-calling | Taxa de sucesso de ataque 47–52% | Avaliar segurança das ferramentas tipadas (RFC §8) |
| openreview *Same Noise, Better Gradients* | CRN em gradiente de política: desacopla RNG de ação e de transição, variável de controle dependente do ruído de transição | Não-viesado, variância menor em certas condições; modificações do PPO | Transferível ao GRPO em simulador; **ler o texto completo** |
| 2609.26461 *Reproducible AI Requires Reproducible Randomness* | Examina se o estado completo do PRNG garante saídas idênticas entre bibliotecas (Mersenne Twister, Philox) | Resumo truncado: **conclusão não lida** | Fixar implementação e versão do RNG; não assumir portabilidade |
| 2609.27490 WhatWorkedBench | Agentes compram medições com orçamento para prever efeitos de mudanças | Ridge de efeitos de pares escolhe o ótimo exato em 15 de 22 fontes | Avaliação de aquisição vs. reconstrução em experimentos orçados |
| 10.2139/ssrn.7095162 | Benchmark aberto de despacho de manutenção com gerador calibrado e validador independente | Em capacidade calibrada, ótimos certificados e regras por prazo quase coincidem | Lembrete: baseline de regras de despacho forte; modelo de gerador+validador |
| ACM *Safe LLM-Agent Execution via Typed Tool Mediation and World-Effect Evaluation*; 2604.18233 *Aether* | Mediação tipada de ferramentas; agentes + gêmeo digital para validar mudanças de rede | Sem resumo (ACM) / resumo qualitativo | Ler antes de fechar o desenho do RFC §8 |
| Despacho: *Learning to Optimize the Dispatch Time Interval for On-Demand Food Delivery* (ITSC 2024); *MDP framework for order dispatching in on-demand delivery* (2026); 2501.05808; DECO (CIKM 2024) | Literatura de despacho de entrega de comida | — | Fonte de baselines de despacho e de parâmetros do mundo |

## 11. Síntese revisada das perguntas

- **LQ1.** A lacuna se estreitou. Já existem: agente LLM com **intervenções orçadas** em ambiente de SCM (ACDB), política de **seleção de experimento discriminativo** com garantia (ISS), RCA **centrada em hipóteses** com crença explícita (HERO) e **sandbox de gêmeo digital** para ações (GuardedAct). Não achei o conjunto: agente que testa hipóteses de **diagnóstico operacional** por **experimentos pareados** num simulador com **DAG causal oculto** e avaliação por **processo**. A contribuição defensável é esse protocolo e o benchmark, e não a ideia de agente que intervém.
- **LQ2.** Confirmado e reforçado (CRN por evento; CRN em gradiente de política). Fixar versão e implementação do RNG.
- **LQ3.** Novo consenso: a acurácia final se sobrepõe a heurísticas sem rótulo; **o que o pipeline mostra ao modelo importa mais que o prompt** (+0,30 vs. +0,05); texto falso e erro de início derrubam resultados. Métrica de fechamento de evidência (ECR) expõe a diferença entre acertar e fundamentar.
- **LQ4.** Há precedentes em 1,5B (RCA em telecom), 4B (tool-calling) e 14B (GRPO em AOI). Em 16 GB, esquecimento catastrófico pode passar despercebido na curva de perda. Nada em 6 GB.
- **LQ5.** Literatura de despacho de comida é abundante em otimização/RL; não há par com falhas operacionais e causa oculta.
- **LQ6.** Existe fundamentação formal (fibras observacionais, ISS) e dois benchmarks com **estados ocultos pareados** (*Did It Happen?*, *Recovery Credit*), que usam teto exato sem informação. É o melhor precedente para o nosso desenho de pares equivalentes.

## 12. Limitações adicionais da rodada 2

1. Semantic Scholar e Google Scholar indisponíveis; Scopus e Web of Science não tentados (sem credenciais).
2. Encadeamento de citações praticamente vazio por falta de vínculos no OpenAlex.
3. Vários resumos vieram truncados ou ausentes (ACM); itens marcados "não lido" não foram avaliados.
4. Muitas fontes são preprints de jun–out/2026 e entradas OpenReview/SSRN/Research Square **sem revisão por pares verificada**. Números de acurácia entre papers não são comparáveis.
5. Revisor único; títulos duplicados removidos por correspondência exata de texto normalizado, o que pode deixar variantes.
6. Os itens de modelos específicos citados (Claude Sonnet 4.6, GPT-5.4, Gemma 4 etc.) vêm dos resumos; não verifiquei.

---

## 13. Leitura integral orientada a decisões do G0 (2026-11-01)

Objetivo: ler as seções de **método** dos textos que mudam decisões do G0, e não para avaliar novidade (adiada para G5/G6). Textos obtidos com `paper-search read arxiv`.

| Texto | Status | O que muda no projeto |
|---|---|---|
| 2603.11084 *Realizing CRN: Event-Keyed Hashing* | **Lido** §§2.3, 3, 4, 5 | (1) Propriedade exigida: **invariância de execução**, `U_e = g(s, event_id_e)`. (2) RNG **por contador** (Philox/Threefry) com chave = (semente, ID do evento). (3) **Escolher a identidade do evento é decisão de modelagem, não automatizável**: chave por **slot** (oportunidade) vs. por **díade** (par de entidades) corresponde a hipóteses de permutabilidade diferentes. (4) Regras: granularidade suficiente, chave **sem quantidades endógenas**, cada evento sorteado uma vez e guardado, IDs de 128 bits, IDs **genealógicos** para entidades criadas durante a simulação. (5) **Teste placebo**: uma intervenção mecanicamente nula que só consome sorteios não pode mudar nada. (6) Philox ≈ 2× mais lento e Threefry ≈ 5% mais rápido que Mersenne Twister (tabela citada de Salmon et al. 2011) |
| 2606.20695 *Paired noise-floor protocol* | **Lido** §§6.2, 6.5, 6.6 | (1) Piso = discordância pareada entre configurações **equivalentes** (verificadas por inspeção e hash do payload). (2) Converter o limite superior do IC do piso em **efeito mínimo detectável (MDE)** e planejar o tamanho de amostra (tabela com teste de McNemar pareado vs. independente). (3) O piso é **específico do regime** (modelo × domínio) e precisa ser re-medido. (4) Subconjunto "ativo" **pré-especificável** em que o mecanismo pode atuar. (5) Replicar com segunda semente antes de afirmar; um efeito de +18 p.p. não se reproduziu |
| 2609.32247 *Interventional Separation Selection* | **Lido** §§3–4 | (1) **Piso observacional** (Teorema 1): todo aprendiz observacional tem risco intervencional ≥ ½ da separação máxima entre hipóteses observacionalmente equivalentes, para qualquer tamanho de amostra. (2) Algoritmo ISS: manter o espaço de versões V, escolher uma intervenção admissível que **separe** dois membros, eliminar os contraditos, parar quando nenhuma intervenção dentro do custo R separa os sobreviventes; o critério de parada é um **certificado verificável sem conhecer a verdade**. (3) V vazio ⇒ **classe refutada** (nenhuma hipótese serve). (4) Cota inferior de ⌈log₂ C⌉ intervenções. (5) Versão contínua: ε-separação com ruído das respostas η; termina se 2η < ε. (6) Achar a intervenção separadora mais barata é NP-completo em geral, tratável com família de consultas enumerável. (7) **Fase de validação** com consultas aleatórias, a única que pode falsificar a classe |
| 2609.31675 *ACDB* | **Lido** §§3–6 | (1) Sessão *observe → intervene → submit*, orçamento **específico por instância** = ótimo pré-calculado + folga. (2) Geração com **portões de rejeição** (fidelidade). (3) Rótulos **permutados** para não vazar estrutura. (4) Pontuação em camadas; precisão e recall sempre visíveis; "não resolvido" é uma falha distinta de "errado". (5) Eficiência η = \|I*\| / max(\|I_usado\|, \|I*\|); **eficiência alta sem ganho de acurácia indica abstenção**. (6) **Piso aleatório cego à estrutura** e "vazamento por densidade". (7) Escada de dificuldade em que cada nível isola um eixo; mesmo manifesto pareado para todos os agentes. (8) Intervenções às vezes **pioram** o LLM: a política não converte dados de intervenção em decisões |
| *Did It Happen?* (Research Square) | **Não lido**: o texto não está acessível pela API nem pela página | Mantido o resumo da seção 10 |
| *Observationally Equivalent, Interventionally Different* (OpenReview `NDJB2YFYXl`) | **Não lido**: OpenReview exige verificação no navegador | Mantido o resumo; o Teorema 1 do ISS já cobre a formalização necessária |

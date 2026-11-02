# Relatório G5 — intervenções, gêmeo imperfeito, escada L3–L6 e ablações

**Data:** 2026-11-02 · **Pré-registro:** `docs/methods/PREREG_G5.md`, commit `b02d900`, feito antes de qualquer execução, mais a adenda A1 (`746bfdc`) e a emenda A1.1 (`29296c0`) · **Semente:** final 515151, índices 0–19 por nível · **Dados:** `G5_REPORT_DATA.json`, `G5_INTERVENTIONS.json`, `G5_NAMES_ONLY.json`, `G4_GENERAL_CHECK.json` · **Revisões independentes:** `docs/reviews/CODEX_REVIEW_G4_G5.md` (código) e `docs/reviews/CODEX_REVIEW_REPORTS_G4_G6.md` (relatórios) · **Decisão de arquitetura:** ADR-0012 (proposta)

Convenções: acurácia exata com IC de Wilson 95%; comparações pareadas por McNemar exato, sem correção de multiplicidade. Por isso cada comparação traz um rótulo: **principal** (previsão registrada) ou **exploratória** (todo o resto). n = 20 por nível: os ICs são largos e as diferenças abaixo de ~0,3 raramente são significativas.

## Resumo das previsões registradas

| Previsão | Resultado | Situação |
|---|---|---|
| H8: o placebo dá diferença exatamente zero | Zero em todas as réplicas dos 60 incidentes | **Confirmada** |
| H7/H4: razão de variância pareada/não pareada < 1 em todos os tipos; mediana < 0,5 em ≥ metade | Medianas de 0,03 a 0,30 em todos os 8 tipos. Em 80–100% dos incidentes a razão fica < 1; há 31 razões ≥ 1 em 6 tipos | **Parcial.** A condição da mediana foi atendida. A primeira condição não definia a agregação; lida por incidente, não foi atendida (§1.2) |
| Estudo 2: a acurácia não sobe com δ; δ = 0 a ±0,10 do modo A | 0,65 → 0,65 → 0,45 → 0,45 → 0,40; δ = 0 idêntico ao modo A | **Confirmada** (descritiva; nenhuma queda é significativa sozinha) |
| Estudo 3 (a): no L5, playbook > regras | 0,65 contra 0,30, p = 0,016 | **Confirmada** |
| Estudo 3 (b): no L4, o playbook mantém a acurácia do L2 e o SFT não ganha do base | Nos mesmos incidentes do L2 com o orçamento do L4: playbook 0,65 → 0,35 (p = 0,031); SFT 0,80 contra base 0,00 (16 a 0, p < 0,001). Na amostra própria do L4: playbook 0,30; SFT 0,70 contra base 0,10 (p = 0,002) | **Refutada** nas duas partes, nas duas amostras |
| Estudo 3 (c), H2: o ganho do SFT sobre o base encolhe no L5 | Ganho de +0,40 no L5. No L0–L2 foi +0,57 agrupado e +0,40 no L0 | **Ambígua** (§3.3) |
| H1/H9: sem experimento, acerto ≤ 0,5 + ruído; com experimento, maior | 0,45 contra 0,90, p = 0,022 | **Confirmada** |
| H10: nomes sozinhos ≤ classe majoritária + 0,10 | L0 0,20 (maioria do treino: 0,15); L1 0,40 (0,50); L2 0,45 (0,45) | **Confirmada** no limiar registrado, sem certificar ausência de vazamento (§4.2) |

## 1. Estudo 1 — pesquisa de intervenções

Foram 60 incidentes (L0–L2), 8 ações do cardápio mais o placebo, e 20 réplicas pareadas por braço com ids 2001–2020, que nenhum agente viu. Nenhuma falha de geração.

### 1.1 Melhor ação viável por família

| Família | Melhor ação (nº de incidentes) | Efeito médio em Δruim [IC t 95%] |
|---|---|---|
| Escassez de entregadores | `add_couriers` 10 (12/12) | −0,243 [−0,278, −0,208] |
| Saturação do despachante | `set_dispatcher_workers` 6 (10/10) | ver JSON |
| Surto de erros de despacho | `set_retry_backoff` 0,2 (11/11) | ver JSON |
| Latência de despacho | `eta_aware` (7) ou `add_couriers` 10 (2) | ver JSON |
| Gargalo de restaurante | `add_couriers` 10 (18/18) | ver JSON |

A restrição registrada ("rejeitar no máximo 20% da demanda") foi aplicada sobre o parâmetro: taxa de admissão ≥ 0,8, ou seja, rejeição **esperada** ≤ 20%. Como a admissão é sorteada pedido a pedido, a admissão de 0,8 rejeita na prática mais de 20% em 25 dos 60 incidentes (máximo 21,6%). Essa ação nunca é a melhor, então a ambiguidade não muda as contagens acima. A fronteira de Pareto (Δruim × custo) tem em média 2,82 ações por incidente: quase sempre há uma troca real entre custo e efeito.

**Gargalo de restaurante:** nenhuma ação do cardápio atua no restaurante. A melhor resposta disponível é mitigar com mais entregadores, e isso é uma limitação do cardápio, não uma descoberta.

### 1.2 Variância pareada (H7/H4)

| Ação | Mediana da razão | IQR | Fração < 1 |
|---|---|---|---|
| add_couriers 5 | 0,058 | 0,015–0,181 | 0,96 |
| add_couriers 10 | 0,109 | 0,028–0,267 | 1,00 |
| workers 4 | 0,056 | 0,010–0,554 | 0,83 |
| workers 6 | 0,057 | 0,010–0,577 | 0,80 |
| retry_backoff 0,2 | 0,113 | 0,015–0,467 | 0,96 |
| eta_aware | 0,028 | 0,019–0,051 | 1,00 |
| admission 0,9 | 0,180 | 0,124–0,287 | 0,96 |
| admission 0,8 | 0,297 | 0,212–0,539 | 0,94 |

O pareamento por réplica, com RNG por evento, corta a variância do contraste em uma ordem de grandeza na mediana. O n por ação vai de 50 a 60 porque incidentes com variância não pareada nula ficam de fora da razão.

O pré-registro tem duas condições: "razão < 1 para todos os tipos" (refutação: "razão ≥ 1 em algum tipo") e "mediana < 0,5 em ao menos metade dos tipos".
- **A segunda foi atendida:** as 8 medianas ficam abaixo de 0,5.
- **A primeira não definia como agregar por tipo.** Lida por incidente, não foi atendida: há 31 razões ≥ 1, espalhadas por 6 tipos (12 de 60 no `workers_6`). São casos em que a ação quase não muda o mundo e as duas variâncias são ruído de tamanho parecido.
- Por mediana, ela seria atendida. Mas essa leitura foi escolhida depois de ver os dados e não estava registrada. **Veredito: parcial.**

### 1.3 Arrependimento das recomendações

**Referência comum.** Para cada incidente, a referência é a melhor entre as ações do cardápio, a não-ação e **todas** as recomendações viáveis que qualquer agente fez nesse incidente. Todas foram medidas com o mesmo controle e as mesmas 20 réplicas. O arrependimento é Δruim da recomendação menos Δruim da referência. Recomendações que não passam no filtro de viabilidade (admissão < 0,8 ou custo > 10) contam à parte.

| Agente | n pontuado | Média | Mediana | Dentro de 0,02 | Reprovadas no filtro |
|---|---|---|---|---|---|
| Remédio-padrão por família (`REMEDY`, com a família verdadeira) | 60 | 0,043 | 0,010 | 0,62 | 0 |
| gpt-5-mini | 41 | 0,056 | 0,000 | 0,66 | **19** |
| gpt-5.6-luna | 52 | 0,127 | 0,022 | 0,50 | 8 |
| Playbook | 60 | 0,169 | 0,030 | 0,43 | 0 |
| Qwen SFT | 60 | 0,190 | 0,012 | 0,57 | 0 |
| Qwen base | 60 | 0,281 | 0,203 | 0,25 | 0 |

A primeira versão deste relatório usava como referência o cardápio mais a recomendação do **próprio** agente, ou seja, uma referência diferente para cada um. Por ela, o remédio-padrão tinha 0,013, o playbook 0,138 e o SFT 0,159 (`regret_vs_best` no JSON; revisão Codex dos relatórios, #2).

**Leitura.**
- **O cardápio registrado era estreito.** Em 16 dos 60 incidentes, alguma recomendação viável fora dele foi melhor que todas as ações do cardápio (25 recomendações ao todo): 16 ou 12 trabalhadores no despachante, 20 entregadores ou espera de nova tentativa de 0,05. Todas cabem no custo ≤ 10.
- **O diagnóstico é o maior gargalo dentro deste espaço de ações.** Mesmo com a referência comum, o remédio-padrão (família verdadeira mais uma ação fixa) fica muito à frente de todo agente, exceto o gpt-5-mini. Isso depende do cardápio, não é uma conclusão geral.
- **Filtro de viabilidade.** As 19 recomendações do gpt-5-mini que reprovam no filtro cortam a admissão para 0,5–0,7. **Os agentes não receberam a restrição de 20%:** ela foi aplicada depois, sobre as recomendações do G3. Por isso não dá para falar em restrição "ignorada". Mesmo assim, como pedido rejeitado conta como ruim (o que constava no texto dos experimentos), as 19 também **pioram** o Δruim no mundo verdadeiro (por exemplo, +0,18 com admissão de 0,7). Ou seja, pioram a métrica que o agente via. Restrições de negócio precisam ser declaradas ao agente e checadas antes de agir (ADR-0008).

## 2. Estudo 2 — laboratório com gêmeo imperfeito (modo B)

Playbook no L2. Δruim da recomendação medido no mundo verdadeiro.

| Laboratório | Acurácia [IC] | Δruim da recomendação | McNemar contra o modo A |
|---|---|---|---|
| Modo A (forks do mundo verdadeiro) | 0,65 [0,43, 0,82] | −0,099 | — |
| Gêmeo δ = 0 | 0,65 [0,43, 0,82] | −0,099 | idêntico (principal) |
| δ = 0,1 | 0,45 [0,26, 0,66] | −0,054 | 0 a 4, p = 0,125 |
| δ = 0,25 (= L6) | 0,45 [0,26, 0,66] | −0,054 | 0 a 4, p = 0,125 |
| δ = 0,5 | 0,40 [0,22, 0,61] | −0,037 | 0 a 5, p = 0,063 |

- **Trocar só a semente não custa nada** (δ = 0). O experimento pareado dentro do gêmeo continua informativo, porque o efeito de interesse é estrutural.
- **Errar os parâmetros custa.** Nesta amostra a acurácia não sobe com δ, e com δ = 0,1 já se perdem 4 acertos. As comparações pareadas contra o modo A, porém, não são significativas (p = 0,125, 0,125 e 0,063). É uma tendência observada, não uma lei geral. O benefício da recomendação no mundo verdadeiro cai de 0,099 para 0,054, 0,054 e 0,037: cerca de 45%, 45% e 63% a menos.
- O gêmeo aqui **conhece a estrutura** da falha, então este é o caso otimista. Um gêmeo com mecanismo errado está fora do estudo.
- Uma verificação confirmou que o gêmeo de fato rodou: os resultados diferem do modo A a partir de δ = 0,1.

## 3. Estudo 3 — escada L3–L6

**Correção de desenho (revisão Codex dos relatórios, #1).** O nome do nível entra na derivação das sementes, então L4 e L6 geram **incidentes próprios**, diferentes dos do L2. O pré-registro dizia "L6 = instâncias L2 com laboratório modo B". As execuções originais do L4/L6 mudavam, portanto, a amostra e a condição ao mesmo tempo. Para isolar a condição, todos os agentes locais rodaram de novo **nos mesmos 20 incidentes do L2**, com o orçamento do L4 (`--budgets-of L4`) ou com o gêmeo δ = 0,25 (`--twin-delta 0.25`). As comparações com o L2 usam essas execuções pareadas. As execuções originais do L4/L6 ficam como **amostras independentes** do mesmo gerador, uma réplica.

### 3.0 Escada pareada (mesmos incidentes do L2)

| Agente | L2 (modo A, 25 consultas, 4 experimentos) | Orçamento do L4 (8 / 1 / 1,0) | Gêmeo do L6 (δ = 0,25) |
|---|---|---|---|
| Regras | 0,00 (abstém 65%) | 0,00 | 0,00 |
| Playbook | 0,65 [0,43, 0,82] | 0,35 [0,18, 0,57]; 0 a 6 contra L2, p = 0,031 | 0,45 [0,26, 0,66]; 0 a 4, p = 0,125 |
| Qwen base | 0,00 | 0,00 (abstém 100%) | 0,00 |
| **Qwen SFT** | 0,90 [0,70, 0,97] | **0,80** [0,58, 0,92]; 0 a 2, p = 0,50 | **0,95** [0,76, 0,99]; 2 a 1, p = 1,0 |

Pareados dentro de cada condição: SFT × base 16 a 0 (orçamento) e 19 a 0 (gêmeo), p < 0,001; SFT × playbook 9 a 0 (p = 0,004) e 10 a 0 (p = 0,002).

### 3.1 Amostras próprias de L3–L6

| Agente | L3 compostas | L4 orçamento: 1 experimento | L5 perfil parcial | L6 gêmeo δ = 0,25 |
|---|---|---|---|---|
| Regras | 0,35 | 0,00 (abstém 80%) | 0,30 (abstém 40%) | 0,00 (abstém 70%) |
| Playbook | 0,35 | 0,30 (abstém 50%) | 0,65 | 0,50 |
| Qwen base | — | 0,10 (não termina em 85%) | 0,00 | 0,00 |
| **Qwen SFT** | — | **0,70** | 0,40 | **0,95** |
| gpt-5-mini (adenda A1) | — | 0,00 | **0,80** | 0,30 |
| gpt-5.6-luna (adenda A1) | — | 0,05 | **0,90** | 0,15 |

O L3 não foi rodado com o Qwen nem com os LLMs de API. Isso não estava previsto no pré-registro, e o tempo de GPU foi para as comparações principais.

| Comparação pareada | L4 | L5 | L6 |
|---|---|---|---|
| Playbook × regras | 6 a 0, p = 0,031 | **7 a 0, p = 0,016 (principal)** | 10 a 0, p = 0,002 |
| SFT × base | **13 a 1, p = 0,002 (principal)** | 8 a 0, p = 0,008 (componente de H2) | 19 a 0, p < 0,001 |
| SFT × playbook | 8 a 0, p = 0,008 | 2 a 7, p = 0,18 | 9 a 0, p = 0,004 |

**L3 — falhas compostas.** Regras e playbook acertam a falha primária em 35% dos casos, com respostas idênticas caso a caso. Em 17 dos 20 casos os dois respondem "gargalo de restaurante", e isso só está certo em 4. A falha secundária de restaurante deixa um rastro observacional forte e a regra dela dispara primeiro. Nenhum dos dois experimenta no L3 (o playbook só experimenta no par equivalente). Separar duas causas simultâneas exige experimentos de intervenção que o protocolo atual não induz.

### 3.2 L4 — orçamento apertado (previsão (b) refutada)

- **Playbook (0,65 → 0,35 nos mesmos incidentes).** Ele parte das quatro famílias globais e só cabe uma sonda. Quando ela não decide, abstém-se (30%). A previsão supunha que ele usaria a sonda certa e não considerou essa ordem.
- **SFT (0,90 → 0,80 nos mesmos incidentes, sem diferença significativa).** A primeira sonda dele (`set_retry_backoff`) já separa as duas famílias possíveis. É coerente com a hipótese do G4 §3: o SFT teria aprendido qual sonda é discriminante neste perfil.
- **Base.** Não produz diagnóstico (abstenção de 100% nos mesmos incidentes).

### 3.3 L5 — observabilidade parcial e H2

O SFT cai para 0,40 e **nunca experimenta no L5** (0,0 experimentos por episódio). No L2 e no L6, também sem medidores, ele experimenta 1,7 e 1,9 vezes por episódio. Ou seja, o comportamento acompanha o conjunto de famílias, não a falta de medidores. No L5 ele repete o comportamento do L0, compromete-se observando e erra 60%. O playbook, que experimenta quando falta evidência, chega a 0,65.

**O L5 não foi verificado como observacionalmente inseparável.** Diferente do L2, não houve sonda de equivalência, e os registros de pedidos mantêm os horários de atribuição, preparo e coleta. O resultado (a) mostra que a falta de medidores derruba as regras observacionais implementadas, não que o experimento seja necessário no L5 (revisão Codex dos relatórios, #8).

H2 previa que o ganho do SFT sobre o base encolheria no L5:
- Contra o ganho agrupado do L0–L2 (+0,57), encolheu (+0,40).
- Contra o L0, que tem as mesmas famílias, o ganho é igual (+0,40).

O pré-registro não fixou qual base de comparação vale, então a previsão fica **ambígua**. O teste SFT × base no L5 (p = 0,008) mostra que há ganho; ele é um componente de H2, não um teste de que o ganho encolheu. O dado comportamental (zero experimentos só no L5) é **compatível** com a hipótese de que o SFT aprendeu **quando** experimentar por conjunto de famílias, não **por que** experimentar. Nenhuma ablação (perfis embaralhados, outra seleção de traços) isolou essa causa.

### 3.4 L6 — gêmeo imperfeito

Nos mesmos incidentes, o SFT fica em 0,95 contra 0,90 no modo A (2 a 1, sem diferença), e o playbook cai para 0,45 (0 a 4). A sonda do SFT dá um efeito grande e de sinal claro mesmo no gêmeo errado. Já os limiares de magnitude do playbook são sensíveis aos parâmetros. Essa robustez é estreita: vale para esse par de famílias e para essa sonda.

## 4. Estudo 4 — ablações

### 4.1 H1/H9 — valor do experimento com o mesmo orçamento (Qwen SFT, L2)

| Condição | Acurácia [IC] |
|---|---|
| Com a ferramenta `experiment` | 0,90 [0,70, 0,97] |
| Sem ela (removida do esquema e do despachante; mesmas 25 consultas) | 0,45 [0,26, 0,66] |

O resultado pareado foi 11 a 2, p = 0,022 (principal). Sem experimento, o acerto fica no teto de quem chuta entre duas causas observacionalmente equivalentes (≈ 0,5). Sem a ferramenta, o modelo responde "latência" nos 20 casos, e o acerto de 0,45 é só a fração de casos de latência na amostra.

### 4.2 H10 — vazamento pelos nomes

Um classificador de n-gramas de caracteres sobre `dataset_id` e os tokens ofuscados foi treinado em 300 instâncias da semente de desenvolvimento e testado na semente final. A base de comparação é o classificador que sempre prevê a família mais comum **do treino**. Ela não é a maioria da amostra final, que seria 0,45, 0,50 e 0,55.

| Nível | Só nomes | Maioria do treino | Diferença |
|---|---|---|---|
| L0 | 0,20 | 0,15 | +0,05 |
| L1 | 0,40 | 0,50 | −0,10 |
| L2 | 0,45 | 0,45 | 0 |

O classificador nunca supera essa base em mais de 0,05, dentro do limiar registrado (+0,10). Isso não certifica ausência de vazamento: só mostra que este classificador, com n = 20 por nível, não achou sinal.

## 5. Capacidade geral do SFT (vem do G4)

No GSM8K com 150 problemas, a métrica estrita cai de 0,61 para 0,14. Pelo último número da resposta, um diagnóstico exploratório, cai de 0,67 para 0,45, com p < 0,001 nos dois casos. Há esquecimento de formato e provável perda de raciocínio; a métrica do último número ainda mistura as duas coisas. Detalhes em G4_REPORT §4.1.

## 6. Adenda A1 — LLMs de API no L4–L6 (exploratório)

Rodados depois do pré-registro, com US$ 0,55 a mais liberados pelo responsável (adenda A1 e emenda A1.1, registradas antes de qualquer resultado). Mesma semente final, n = 20 por nível, mesmo laço de agente do G3. O luna rodou sem raciocínio, como no G3. Gasto total do projeto com API: US$ 1,92 (teto US$ 1,98). Todas as comparações são **exploratórias**. As amostras são as próprias do L4–L6 (§3.1); não houve verba para as versões pareadas.

| Agente | L4 | L5 | L6 | Experimentos por episódio (L4 / L5 / L6) |
|---|---|---|---|---|
| gpt-5-mini | 0,00 (abstém 35%) | **0,80** [0,58, 0,92] | 0,30 | 1,0 / 1,6 / 2,4 |
| gpt-5.6-luna | 0,05 (abstém 70%) | **0,90** [0,70, 0,97] | 0,15 (abstém 55%) | 1,0 / 2,3 / 2,0 |

| Comparação pareada (exploratória) | L4 | L5 | L6 |
|---|---|---|---|
| mini × Qwen SFT | 0 a 14, p < 0,001 | **9 a 1, p = 0,021** | 0 a 13, p < 0,001 |
| luna × Qwen SFT | 0 a 13, p < 0,001 | **10 a 0, p = 0,002** | 0 a 16, p < 0,001 |
| mini × playbook | 0 a 6, p = 0,031 | 5 a 2, p = 0,45 | 3 a 7, p = 0,34 |
| luna × playbook | 0 a 5, p = 0,063 | 6 a 1, p = 0,13 | 1 a 8, p = 0,039 |

**Previsões exploratórias.**
- **(e1) Os LLMs ficam abaixo do próprio L2 no L4 e no L6:** no L2 (G3), o mini fez 0,30 e o luna 0,00. O mini cai para 0,00 no L4 e fica igual (0,30) no L6. O luna, já em 0,00, não tem como cair. São amostras diferentes e sem pareamento. Previsão **não confirmada**: os LLMs já falhavam no L2, e o L4/L6 não muda isso de forma detectável.
- **(e2) Sem experimento, o luna no L2 não supera o luna com experimento:** confirmada, trivialmente. São 0,00 nos dois; sem a ferramenta, ele se abstém em 90%.

**Leitura.** A inversão no L5 é o achado mais informativo da adenda:
- No **L5**, sem os medidores de frota e de despacho, os LLMs **experimentam por conta própria** (1,6 a 2,3 por episódio) e acertam 80–90%. O Qwen SFT nunca experimenta ali e fica em 0,40.
- No **par equivalente** (L2, L4 e L6), os mesmos LLMs falham: gastam o único experimento numa intervenção que não separa as causas ou leem mal a diferença.

Uma leitura compatível com os dados, mas não testada: os LLMs grandes sabem **por que** experimentar quando há uma lacuna de observação reconhecível, mas não descobrem **qual** intervenção separa duas causas construídas para serem equivalentes. O SFT tem o padrão oposto. A combinação, isto é, um modelo pequeno treinado com traços de mais de um especialista, é o próximo passo natural (§8).

## 7. Revisão independente

A revisão do Codex sobre o código G4/G5 trouxe 13 achados, todos reproduzidos e corrigidos antes das execuções finais, com testes de regressão em `tests/agent/test_review_g4_g5.py` (`docs/reviews/CODEX_REVIEW_G4_G5.md`). Os dois de severidade alta afetavam o L3:

- a família mudava entre tentativas e produzia duas falhas de restaurante;
- reordenar as falhas mudava o RNG reexecutado.

As linhas do L3 rodadas antes da correção foram isoladas em `results_L3_prefix_INVALID.jsonl` e não entram em nenhum número.

Uma segunda revisão do Codex, sobre os **relatórios**, trouxe 12 achados, todos verificados e corrigidos (`docs/reviews/CODEX_REVIEW_REPORTS_G4_G6.md`). O de severidade alta, L4/L6 com incidentes diferentes dos do L2, originou a escada pareada da §3.0. Os demais tornaram vereditos e alegações mais estritos: arrependimento com referência comum, H7 parcial, nomes, gêmeo, L5, restrição de viabilidade e rótulos.

## 8. Limitações

- n = 20 por nível e uma execução gulosa por modelo. Várias diferenças exploratórias de 0,2 a 0,3 não são significativas.
- Um único especialista gerou os traços. O SFT herda a ordem de sondas dele e o atalho de distribuição por perfil (G4 §3), o que explica tanto o bom L4/L6 quanto o L5 fraco.
- O gêmeo conhece a estrutura da falha (cota otimista). Os parâmetros perturbados são seis.
- O cardápio de intervenções não tem ação no restaurante e é estreito: os agentes acharam ações viáveis melhores fora dele (§1.3).
- A restrição de rejeição não foi informada aos agentes e foi aplicada sobre o parâmetro de admissão, não sobre a rejeição observada (§1.1, §1.3).
- Dados 100% sintéticos. Nenhuma alegação sobre operação real.
- Os LLMs de API rodaram só nas amostras próprias do L4–L6, sem versão pareada, por falta de verba.
- **Próximo passo natural:** treinar o modelo pequeno com traços de mais de um especialista, incluindo traços em que a decisão de experimentar vem de uma lacuna de observação (como fazem os LLMs no L5), e misturar famílias entre perfis para quebrar o atalho de distribuição.

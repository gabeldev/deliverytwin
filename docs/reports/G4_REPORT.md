# Relatório G4 — modelo adaptado (Qwen3-1.7B + QLoRA)

**Data:** 2026-11-02 · **Semente de avaliação:** final 515151 (intocada até a avaliação) · **Dados de treino:** só semente de desenvolvimento 2026 · **Revisão independente:** `docs/reviews/CODEX_REVIEW_G4_G5.md`

## 1. O que foi feito

| Etapa | Resultado |
|---|---|
| Portão de memória (RTX 3050, 6 GB) | Qwen3-1.7B em 4 bits NF4 com LoRA r = 16 e sequências de até 4608 tokens: pico de 3,05 GB. Qwen3-4B estourou memória já em 2048 tokens (`G4_MEMORY_GATE.json`) |
| Traços de especialista | O especialista age só pelas ferramentas públicas da sessão, com a lógica do playbook. Por amostragem por rejeição ficam só os episódios que o avaliador pontua como corretos. A verdade oculta decide manter ou descartar; nunca entra no texto (`training/traces.py`) |
| Conjunto | 362 traços de treino e 132 de validação, divididos pela partição privada das instâncias da semente 2026. A partição de teste da semente 2026 não foi usada (`G4_DATASET_STATS.json`) |
| Formato | Renderização única para treino e inferência: modo sem raciocínio, bloco `<think>` vazio em todo turno do assistente e esquemas de ferramenta compactos. A perda é calculada só sobre os tokens do assistente |
| Treino | 2 épocas, 113 passos, 81 min, lr 2e-4, acumulação de gradiente 8. Replay de 90 exemplos do Dolly-15k para limitar o esquecimento. Perda de validação nos traços: 1,81 → 0,015 |

## 2. Avaliação no benchmark (semente final, 20 instâncias por nível)

Acurácia exata com IC de Wilson 95%. "Comprometido errado" é a fração de casos em que o agente dá uma causa e erra.

| Agente | L0 | L1 | L2 | Abstenção | Comprometido errado (L0/L1/L2) |
|---|---|---|---|---|---|
| Qwen3-1.7B base | 0,05 | 0,00 | 0,00 | 85–90% (não termina) | 0,05 / 0,10 / 0,15 |
| **Qwen3-1.7B + SFT** | 0,45 [0,26, 0,66] | 0,40 [0,22, 0,61] | **0,90** [0,70, 0,97] | 0% | 0,55 / 0,60 / 0,10 |
| Manual + experimento (playbook) | 0,50 | 0,70 | 0,65 | 0% | 0,50 / 0,30 / 0,35 |
| gpt-5-mini (G3) | 0,90 | 0,75 | 0,30 | — | — |

**Comparações pareadas (McNemar exato):**

| Comparação | Nível | Resultado | Rótulo |
|---|---|---|---|
| SFT × base | L0 | 9 a 1, p = 0,02 | principal do G4 (sem pré-registro) |
| SFT × base | L1 | 8 a 0, p = 0,008 | principal do G4 (sem pré-registro) |
| SFT × base | L2 | 18 a 0, p < 0,001 | principal do G4 (sem pré-registro) |
| SFT × playbook | L0 | p = 1,0 | exploratória |
| SFT × playbook | L1 | p = 0,07 | exploratória |
| SFT × playbook | L2 | p = 0,13 | exploratória |
| SFT × gpt-5-mini | L0 | o mini vence, p = 0,02 | exploratória |
| SFT × gpt-5-mini | L2 | o SFT vence, p = 0,002 | exploratória |

O modelo base não consegue seguir o protocolo: 88% dos episódios terminam pelo limite de turnos, com média de 12 erros de ferramenta por episódio. O SFT sempre termina.

## 3. De onde vem o 0,90 no L2 (leitura cuidadosa)

O SFT segue o procedimento do especialista: testa `set_retry_backoff`; se ajudar, conclui surto de erros; se não ajudar, testa entregadores e trabalhadores e conclui latência. O playbook segue o mesmo procedimento. Os 35% de erros dele no L2 vêm de a regra observacional de restaurante disparar em falso, levando a "gargalo de restaurante".

O SFT nunca comete esse erro. A amostragem por rejeição descartou todos os traços em que isso acontecia, e no L2 a causa nunca é restaurante. **A explicação mais provável para o ganho sobre o playbook é o modelo ter aprendido a distribuição de famílias de cada perfil do benchmark**, e não raciocínio novo. Seria um atalho de conjunto de dados (hipótese rival de H2 na ARCH_RESEARCH_001). É uma hipótese apoiada pelos dados, não isolada: nenhuma ablação de seleção de traços ou de perfis embaralhados foi feita.

O teste disso está no G5 (`G5_REPORT.md`). No L5, as famílias do L0 aparecem num perfil que o modelo não viu no treino. No L4 e no L6, a distribuição é a mesma do L2, mas o orçamento ou o laboratório mudam.

Os dois erros do SFT no L2 foram leituras erradas: ele concluiu surto de erros com diferença +0,000 no experimento.

## 4. Capacidade geral (esquecimento)

- **Perda no Dolly retido:** 4,86 → 1,78. **Não serve como medida de esquecimento.** O replay usa a mesma distribuição, então a queda reflete adaptação ao formato do Dolly (a perda inicial alta indica descompasso entre o formato sem raciocínio e as respostas do Dolly).
- **Verificação independente (GSM8K, 150 problemas fixos, decodificação gulosa, pareada base × SFT):** houve esquecimento significativo (seção 4.1).

### 4.1 GSM8K

Foram usados 150 problemas fixos do conjunto de teste (semente 0), com decodificação gulosa, modo sem raciocínio e no máximo 512 tokens. As respostas estão em `runs/g4/gsm8k_responses.json`, fora do git, e os números em `G4_GENERAL_CHECK.json`.

| Métrica | Base | SFT | Pareado (só base / só SFT) | McNemar |
|---|---|---|---|---|
| **Estrita** (valor na última linha `Answer:`, métrica definida antes da execução) | 0,61 (91) | **0,14** (21) | 79 / 9 | p < 0,001 |
| Sem resposta legível no formato pedido | 19 | 116 | — | — |
| Diagnóstico: último número do texto (definido depois da execução, só exploratório) | 0,67 (101) | 0,45 (67) | 52 / 18 | p < 0,001 |

**Leitura.** Houve esquecimento real:

1. **Seguir instruções de formato.** O SFT ignora "termine com Answer: <número>" em 77% dos casos. Responde em prosa curta, no estilo do Dolly usado no replay. Das 116 respostas que o extrator não leu, 46 tinham o número certo no fim.
2. **Provável perda de raciocínio aritmético.** Mesmo pela leitura do último número, a acurácia cai 22 pontos. Essa leitura ainda mistura apresentação com cálculo: há resposta do SFT que calcula certo e termina citando outro número, como um horário, e é marcada errada (revisão Codex dos relatórios, #12). A queda medida é robusta. Atribuí-la por inteiro ao raciocínio exigiria corrigir as respostas à mão, o que não foi feito.

O replay de 90 exemplos do Dolly não bastou para preservar a capacidade geral. O adaptador serve só para o protocolo do DeliveryTwin e não deve ser usado como assistente geral. Mitigações possíveis, não testadas: replay com dados de matemática ou instruções que tenham formato de saída, LoRA de posto menor e menos épocas.

## 5. Correções da revisão que afetam o G4

| Achado | Correção | Efeito |
|---|---|---|
| #1 | Chamadas de ferramenta com argumentos que não são objeto agora vão para o caminho de erro | Nenhuma execução tinha caído por isso |
| #2 | Extração do GSM8K estrita | Corrigida antes de rodar |
| #3 | O último lote parcial de acumulação passa a ser aplicado | O treino registrado (904 microlotes, múltiplo de 8) não foi afetado |

## 6. Limitações

- n = 20 por nível; os ICs são largos.
- Os traços vêm de um único especialista determinístico. O modelo imita esse procedimento e herda os pontos cegos dele. No L0/L1 fica abaixo do próprio especialista porque erra a leitura dos medidores.
- O ganho no L2 depende do atalho descrito na §3.
- Avaliação com decodificação gulosa: uma execução por modelo, sem variabilidade entre repetições.
- Adaptador e dados de treino ficam fora do git (`runs/g4/`). O cartão do modelo está em `docs/model/MODEL_CARD.md`. Não há publicação externa sem decisão do responsável (licença pendente, ADR-0009/0011).

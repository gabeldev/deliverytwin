---
# Portuguese source of the published English card (Hugging Face, ADR-0013)
license: apache-2.0
base_model: Qwen/Qwen3-1.7B
library_name: peft
pipeline_tag: text-generation
tags: [qlora, lora, tool-use, root-cause-analysis, simulation, logistics, synthetic-data]
datasets: [databricks/databricks-dolly-15k]
language: [en]
---

# DeliveryTwin investigator — Qwen3-1.7B QLoRA adapter (research artifact)

**Status:** pesquisa. Publicado em 2026-11-02 (Apache-2.0): https://huggingface.co/gabeldev/deliverytwin-investigator-qwen3-1.7b-lora (cartão em inglês). **Ambiente simulado**; nenhuma relação com operação real de qualquer empresa.

## O que é

Adaptador LoRA (r = 16, projeções de atenção e MLP) para `Qwen/Qwen3-1.7B` em 4 bits NF4. O modelo conduz uma investigação tipada de incidentes num simulador sintético de entregas: consulta a telemetria, formula hipóteses, roda experimentos pareados num laboratório contrafactual e entrega um diagnóstico com recomendação. Usa as ferramentas `query_orders`, `query_gauges`, `hypothesize`, `experiment` e `submit` (ADR-0004).

## Uso pretendido

- Pesquisa sobre agentes de diagnóstico que usam experimentos.
- Linha de base local e sem custo para o benchmark DeliveryTwin.

**Fora do escopo:** decisões operacionais reais; qualquer uso sem aprovação humana (ADR-0008); outros domínios.

## Treino

| Item | Valor |
|---|---|
| Dados | 362 traços de investigação de um especialista determinístico (playbook), só da semente de desenvolvimento 2026, mantidos por amostragem por rejeição sobre o avaliador. Mais 90 exemplos de replay do Dolly-15k (CC BY-SA 3.0) |
| Formato | Modo sem raciocínio (bloco `<think>` vazio em todo turno do assistente), esquemas de ferramenta compactos, perda só nos tokens do assistente |
| Hiperparâmetros | 2 épocas, lr 2e-4 com cosseno, acumulação 8, sequência ≤ 4608 tokens, semente 0 |
| Hardware | RTX 3050 Laptop 6 GB, 81 min, pico de 3,05 GB |

## Avaliação (semente final 515151, n = 20 por nível; `docs/reports/G4_REPORT.md`, `G5_REPORT.md`)

| Nível | Base | SFT | Playbook |
|---|---|---|---|
| L0 (medidores completos) | 0,05 | 0,45 | 0,50 |
| L1 (+ ruído) | 0,00 | 0,40 | 0,70 |
| L2 (par equivalente, exige experimento) | 0,00 | 0,90 | 0,65 |

Condições novas (relatório G5), mesma semente, n = 20. Primeiro nos **mesmos incidentes do L2**, isolando a condição:

| Condição nos incidentes do L2 | Base | SFT | Playbook |
|---|---|---|---|
| Orçamento do L4 (8 consultas, 1 experimento) | 0,00 | 0,80 | 0,35 |
| Gêmeo imperfeito do L6 (δ = 0,25) | 0,00 | 0,95 | 0,45 |
| Sem a ferramenta de experimento | — | 0,45 | — |

Nas amostras próprias de cada nível:

| Nível | Base | SFT | Playbook | gpt-5-mini | gpt-5.6-luna |
|---|---|---|---|---|---|
| L4 | 0,10 | 0,70 | 0,30 | 0,00 | 0,05 |
| L5 (perfil parcial, nunca visto no treino) | 0,00 | **0,40** | 0,65 | 0,80 | 0,90 |
| L6 | 0,00 | 0,95 | 0,50 | 0,30 | 0,15 |

No L5, o SFT nunca experimenta e perde para os LLMs de API, que experimentam por conta própria (p ≤ 0,022, exploratório).

**Capacidade geral (GSM8K, 150 problemas):** com a métrica estrita, a acurácia cai de 0,61 no base para 0,14 no SFT. Considerando só o último número da resposta, cai de 0,67 para 0,45. O modelo perde tanto a obediência ao formato pedido quanto raciocínio aritmético (G4_REPORT §4.1).

## Limitações e riscos conhecidos

- **Atalho de distribuição:** a amostragem por rejeição ensina ao modelo quais famílias de falha ocorrem em cada perfil do benchmark. Parte do ganho no L2 vem disso (G4_REPORT §3).
- **Esquecimento:** o modelo perde capacidade geral (GSM8K acima). Use o adaptador só no protocolo do DeliveryTwin.
- Imita um único especialista e herda os pontos cegos dele. Erra a leitura de medidores no L0/L1.
- Dados 100% sintéticos; nada indica que transfira para operações reais.
- n pequeno; avaliação com decodificação gulosa, uma execução.

## Reprodução

```bash
uv run --group train python scripts/g4_build_dataset.py
uv run --group train python scripts/g4_train.py
uv run --group train python scripts/run_g3.py --agent local --adapter runs/g4/adapter --levels L0,L1,L2 --n 20 --seed final --tag g4
```

## Licença

Apache-2.0 (ADR-0013). Modelo base: Qwen3-1.7B (Apache-2.0, © Alibaba Cloud / Qwen Team). O treino incluiu 90 exemplos de replay do Dolly-15k (CC BY-SA 3.0, © Databricks), que não são redistribuídos com o adaptador.

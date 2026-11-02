# ADR-0007 — Protocolo de treino do modelo pequeno

**Status:** Aceita (2026-11-01) · **Gate:** G4 · **Data:** 2026-11-01

## Contexto

Hardware local: RTX 3050 6 GB, 16 GB de RAM. Precedentes: Qwen2.5-1.5B com LoRA para RCA em telecom (sensível à serialização da telemetria); Qwen3-4B com QLoRA para tool-calling; GRPO em 14B (AOI). Em GPUs de 16 GB, fine-tuning ingênuo causou **esquecimento catastrófico escondido na curva de perda**. Fine-tuning de modelos pequenos pode piorar o desempenho (2607.18725). Nada demonstrado em 6 GB.

## Decisão

1. **Portão de memória antes de tudo:** medir `torch.cuda.max_memory_allocated` para Qwen3-1.7B (4 bits, QLoRA, checkpointing) em sequências de 1k, 2k e 4k. Só seguir com o tamanho que couber com folga. Qwen3-4B só se o portão passar.
2. **SFT (T1)** com trajetórias geradas pelo simulador e rótulos de processo verificados (DAG da falha), mais supervisão corretiva a partir de trajetórias com falha.
3. Receita obrigatória: perda **só sobre a completude**; replay de dados de domínio geral; decontaminação aproximada entre treino e teste (por instância, mecanismo e semente).
4. Medir **antes e depois** do SFT: capacidade geral (um benchmark fixo), seguimento de esquema e todas as métricas da ADR-0006.
5. Teste de robustez à **serialização** da telemetria (ordem de colunas, formato, nomes ofuscados).
6. RL (GRPO, T3) é **stretch**: só com fork rápido (ADR-0001 migrada) ou computação externa. Se ocorrer, reutilizar o ruído de transição entre amostras do grupo (*Same Noise, Better Gradients*).
7. Nada sobre RL entra no README antes de medido.

## Consequências

- G4 pode terminar só com T1, e isso é um resultado válido, incluindo resultado negativo.

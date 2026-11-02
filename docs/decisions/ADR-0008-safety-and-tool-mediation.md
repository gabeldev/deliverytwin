# ADR-0008 — Segurança e mediação de ferramentas

**Status:** Aceita (2026-11-01) · **Gate:** G0 → verificado no G3 · **Data:** 2026-11-01

## Contexto

RFC §8 exige leitura por padrão, parâmetros tipados e permitidos, sem execução arbitrária. ToolGuard mostra modelos de 1–4B com 47–52% de sucesso de ataque em tool-calling.

## Decisão

1. Toda chamada do agente passa pelo orquestrador, que valida esquema, faixa de parâmetros, orçamento e permissão **antes** de executar. O modelo nunca chama o simulador diretamente.
2. Nenhuma ferramenta executa código arbitrário, shell ou rede. Agentes de código usados como baseline rodam em sandbox sem acesso ao canal privado.
3. Limites de chamadas, de tempo e de tentativas por sessão; ao estourar, a sessão é selada como `timeout`.
4. Teste adversarial no G3: chamadas com parâmetros fora da faixa, ferramentas inexistentes, tentativas de ler o canal privado e injeção de instruções via texto de telemetria (logs contendo comandos).
5. Qualquer recomendação de ação é **proposta** para aprovação humana; nada é aplicado fora do sandbox (RFC §8).

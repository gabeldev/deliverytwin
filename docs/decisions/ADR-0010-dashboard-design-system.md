# ADR-0010 — Design system do painel: status epistêmico como primeira dimensão visual

**Status:** Aceita (2026-11-01) · **Gate:** G0 (spec) → G6 (painel completo) · **Data:** 2026-11-01

## Contexto

RFC §8 e §9 exigem que o painel separe observação, hipótese, suposição do simulador, experimento e recomendação, e sempre identifique o ambiente como simulado. A pesquisa mostrou que agentes usam melhor saída numérica que gráficos (TraceBench), então o painel é para humanos e as ferramentas do agente são textuais.

## Decisão

Adotar o design system descrito em `docs/architecture/DESIGN_SYSTEM.md`, cujo princípio central é: **todo elemento exibe o seu status epistêmico** por cor, ícone e rótulo textual juntos (nunca só cor). Visões do Avaliador, que mostram a verdade oculta, ficam em rota separada e nunca aparecem na visão do agente ou na demo de investigação ao vivo.

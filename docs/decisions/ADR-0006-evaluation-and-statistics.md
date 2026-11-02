# ADR-0006 — Avaliação, estatística e pacote selado

**Status:** Aceita (2026-11-01) · **Gate:** G0 → aplicado do G1 ao G5 · **Data:** 2026-11-01

## Contexto

Acertar a causa esconde raciocínio fraco (OpenRCA 2.0, Cloud-OpsBench, estudo de trajetórias). Diagnóstico certo não implica ação válida (R2Act). Ganhos relatados costumam ficar abaixo do piso de ruído (2606.20695). Texto falso e erro de início derrubam resultados (*Where Does the Accuracy Come From?*).

## Decisão

**Pontuação em camadas** (determinística dado o pacote selado e o canal privado; sem LLM-juiz na nota principal):

| Camada | Métricas |
|---|---|
| Causa | Precisão, recall e F1 do conjunto de causas (**precisão e recall sempre visíveis**); top-1; taxa de alucinação |
| Fundamentação | Diagnóstico fundamentado (causa certa + caminho causal verificado); **fechamento de evidência** = fração dos nós do DAG verdadeiro cobertos por evidência citada |
| Identificabilidade | Ganho sobre o teto 1/k em classes equivalentes; acerto de `unresolved` em instâncias não identificáveis dentro de B; acerto de `refuted` quando aplicável |
| Política | Eficiência η = c(I*) / max(c(I_usado), c(I*)), lida **junto** com a acurácia (alta eficiência sem acurácia = abstenção) |
| Ação | Validade da recomendação (viável e admissível) e arrependimento contra o oráculo do simulador |
| Confiança | Brier, calibração |
| Custo | Consultas, experimentos, tokens, tempo, VRAM |

**Pacote selado** por sessão: manifesto (versões, gerador de RNG, semente derivada, nível), trajetória completa, chamadas e respostas, relatório. O Avaliador reexecuta e pontua offline.

**Estatística:**

1. **Piso de ruído** antes de cada comparação de agentes: duas configurações equivalentes (verificadas por hash), mesmo manifesto; o limite superior do IC vira o **MDE**, e o tamanho de amostra é planejado com teste pareado (McNemar). Re-medir por regime (modelo × nível).
2. Comparações sempre **pareadas** no mesmo manifesto; diferenças com IC; segunda semente antes de afirmar.
3. Subconjuntos "ativos" **pré-especificados** (ex.: só L2 para o valor do experimento).
4. **Pré-registro** em manifesto de experimento (RFC §7): tarefas, métricas, contrastes primários, correções de multiplicidade.
5. Testes de robustez: decoy (afirmação falsa no texto), deslocamento do início do incidente, ablação do texto de evidência, serialização alternativa da telemetria.

## Consequências

- Relatórios mostram o perfil de falha, não um número único.
- O custo de avaliação sobe (pisos e réplicas); compensado por comparações pareadas.

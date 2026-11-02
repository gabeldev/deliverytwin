# ADR-0001 — Núcleo de simulação e bifurcação de estado

**Status:** Aceita (2026-11-01) · **Gate:** G0 → verificado no G1 · **Data:** 2026-11-01

## Contexto

O RFC §5 pede "clonar o estado pré-intervenção" para comparar políticas. Em SimPy o estado de cada processo vive em geradores Python, e geradores não podem ser copiados com `deepcopy` nem serializados com `pickle`. Não há snapshot nativo.

Cloud-OpsBench (2603.00468) usa snapshot de estado reexecutado para comparações pareadas; isso confirma a necessidade de bifurcar, não a técnica.

## Decisão

1. Kernel de eventos discretos **SimPy** na v0.
2. Toda bifurcação passa por uma interface única:

   ```python
   class Forkable(Protocol):
       def fork_at(self, t: SimTime, branch: BranchSpec) -> "World": ...
   ```

3. Implementação v0: **replay determinístico**. Para bifurcar em `t`, reexecutar o mundo do início até `t` com a mesma especificação e semente, e só então aplicar o `BranchSpec` (intervenção e réplica). Isso é correto por construção desde que a ADR-0002 valha (aleatoriedade por evento).
4. Estado do domínio (pedidos, entregadores, filas) mora em **estruturas de dados explícitas** (dataclasses), e os processos SimPy só agendam eventos sobre elas. Isso mantém aberta a migração para snapshot real.
5. Critério de migração para snapshot (kernel próprio com estado serializável): se o custo do replay em G1 tornar inviável a avaliação de G5 (por exemplo, mais de 10× o custo de um episódio por experimento), abrir ADR nova.

## Consequências

- Custo O(t) por bifurcação; aceitável para o ciclo mínimo do RFC §12.
- Replay é auditável: o mesmo manifesto reproduz o mesmo mundo.
- Treino por RL (fora do caminho crítico) provavelmente exigirá a migração.

## Verificação (G1)

- Replay até `t` e continuação sem intervenção produzem fluxo de eventos **idêntico** ao da execução contínua (comparação por hash do log de eventos).
- Medir tempo de replay por tamanho de cenário e registrar no relatório do G1.

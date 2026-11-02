# Cartão do benchmark DeliveryTwin (rascunho, não publicado)

**Status:** gerado sob demanda pelo código; nenhum arquivo de dados foi publicado. **Licença: Apache-2.0** (ADR-0013). O simulador sintético necessário para os níveis com experimento faz parte da parte aberta (ADR-0013, opção A).
**Ambiente simulado:** nenhuma relação com empresa, entregador ou incidente real.

## O que é

Um gerador determinístico de incidentes de entrega de última milha com causa oculta. Cada instância é produzida por `deliverytwin.benchmark.generator.generate_instance(level, index, master_seed)` e tem duas partes:

| Parte | Quem vê | Conteúdo |
|---|---|---|
| `public` (`Telemetry`, schema `telemetry/v1`) | O agente | `dataset_id`, perfil de observabilidade, horizonte observado, prazo prometido, entidades com identificadores ofuscados (zonas, restaurantes), pedidos visíveis ao cliente e, conforme o perfil, séries de medidores |
| `private` (`PrivateRecord`) | Só o avaliador | Família e escopo da falha, falhas extras (L3) na ordem de injeção, semente do mundo, sal de ofuscação, alerta, DAG causal, canário |

A telemetria pública passa por uma checagem de vazamento: nomes de família, parâmetros da falha, sementes, sal e canário não podem aparecer nela. Os pacotes de investigação também são checados antes de serem salvos (`bundle_leaks`).

## Níveis

| Nível | Famílias | Perfil | Ruído | Laboratório / orçamento |
|---|---|---|---|---|
| L0 | escassez de entregadores, saturação do despachante, gargalo de restaurante | `full` | não | modo A; 25 consultas, 4 experimentos, 10 unidades |
| L1 | as do L0 | `full` | demanda σ = 0,25; medidores σ = 0,15 | igual ao L0 |
| L2 | surto de erros de despacho, latência de dependência | `customer` (sem medidores) | sim | modo A; par verificado como equivalente por sonda (G2.1) |
| L3 | escassez ou saturação **mais** gargalo de restaurante | `full` | sim | modo A; resposta = falha primária |
| L4 | as do L2 | `customer` | sim | 8 consultas, 1 experimento, 1,0 unidade |
| L5 | as do L0 | `partial` (pedidos, `orders_active`, `kitchen_load`) | sim | modo A; sem sonda de equivalência |
| L6 | as do L2 | `customer` | sim | modo B, gêmeo com δ = 0,25 |

O nome do nível entra na derivação de todas as sementes. Por isso L4 e L6 têm **incidentes próprios**, diferentes dos do L2, mesmo com o mesmo gerador. Para isolar o efeito do orçamento ou do gêmeo, rode os incidentes do L2 com `run_g3.py --levels L2 --budgets-of L4` ou `--twin-delta 0.25` (G5 §3).

## Sementes e partições

- **Desenvolvimento (2026, padrão público):** qualquer pessoa regenera as instâncias. Usada no ajuste e em todos os dados de treino do G4.
- **Avaliação (909090) e final (515151):** usadas nos relatórios. **As duas estão nos documentos e, portanto, não são mais seladas** (ver LIMITATIONS §3). Um release público precisa de uma semente secreta nova via `DELIVERYTWIN_MASTER_SEED`.
- Cada instância tem uma partição privada (`train`/`dev`/`test`, 60/20/20 pela semente do mundo), usada para separar treino e validação no G4.
- Instâncias que o gerador não consegue produzir (25 tentativas sem impacto mínimo ou sem alerta atribuível à falha) são relatadas como falhas, nunca substituídas.

## Uso pretendido

- Avaliar agentes de diagnóstico que precisam decidir **quando experimentar**.
- Comparar estratégias de experimento sob orçamento, observabilidade parcial e gêmeo imperfeito.

**Fora do escopo:** treinar sistemas para operação real; tirar conclusões sobre empresas de entrega.

## Atalhos conhecidos e controles

- **Nomes:** um classificador de n-gramas que só vê os identificadores não supera em mais de 0,05 a classe majoritária do treino (H10, G5 §4.2). Isso não certifica ausência de vazamento.
- **Distribuição por perfil:** o perfil revela o conjunto de famílias possíveis (por exemplo, `customer` implica o par do L2). O modelo treinado no G4 parece ter aprendido isso (hipótese apoiada, não isolada; G4 §3). Releases futuros podem misturar famílias entre perfis.
- **Equivalência do L2:** verificada por sonda com n = 300. Vale para a telemetria do benchmark, não para observabilidade completa.

## Proveniência

O código do gerador e do mundo é deste projeto. A calibração de ordem de grandeza usou o Grubhub MDRP localmente, sem redistribuir os dados (ADR-0009). Não há dados pessoais.

## Como gerar

```python
from deliverytwin.benchmark.generator import generate_instance
inst = generate_instance("L2", 0, master_seed=2026)  # inst.public vai para o agente
```

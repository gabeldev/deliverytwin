# G2 — Relatório: injeção de falhas, telemetria, detector e benchmark

**Data:** 2026-11-01 · **Gate:** G2 (RFC §11) · **Dados:** `docs/reports/G2_REPORT_DATA.json` (`scripts/g2_report.py --n 60`), calibração em `scripts/calibrate_detector.py`

> **Atualização (G2.1):** a pendência da seção 6 foi resolvida e o mundo foi recalibrado contra dados reais; números atuais em `G2_1_REPORT.md`. Este relatório é mantido como registro histórico.

**Veredito:** G2 **cumprido com uma pendência bloqueante para o L2** (seção 6). L0 e L1 estão válidos. O L2 não está: a hipótese de que escassez e saturação são observacionalmente equivalentes foi **refutada** pela sonda de distinguibilidade.

## 1. O que foi implementado

| Módulo | Conteúdo |
|---|---|
| `faults/spec.py` | 3 famílias (escassez de entregadores, saturação do despachante, gargalo de restaurante) com início e severidade; DAG causal privado por falha; `NoiseSpec` (oscilação de demanda, ruído nos medidores) separado das falhas |
| `simulation/world.py` | Injeção como mudança de mecanismo no início da falha; medidores por minuto; modo de chave do aceite slot/díade; popularidade de restaurantes; cozinhas dimensionadas pela carga |
| `telemetry/` | Contrato `telemetry/v1` com `source`, perfis `full` e `customer`, IDs ofuscados por instância, corte temporal, varredura de vazamento |
| `diagnostics/detector.py` | Detector online pela taxa de pedidos ruins (global, zona, restaurante), limiares calibrados |
| `diagnostics/rules.py` | Baseline de regras especialistas (sem LLM) e pisos |
| `diagnostics/features.py` | Features observacionais para a sonda de distinguibilidade |
| `benchmark/generator.py` | Instâncias L0–L2 com portões de impacto, detecção e **atribuição contrafactual**; canal privado × público |
| `tests/benchmark/test_g2.py` | 18 testes novos (78 no total) |

## 2. Efeito das falhas (pareado contra o mesmo mundo sem falha, 40 sementes, pedidos após o início)

| Falha (severidade fixa) | Mediana de entrega | Taxa de atraso | Cancelamento | Atraso de atribuição |
|---|---|---|---|---|
| Escassez, 57% offline | +8,5 min [7,7, 9,3] | +0,20 | +0,21 | +13,5 min |
| Saturação, serviço ×11,5 | +22,0 min [20,8, 23,3] | +0,54 | +0,30 | +30,5 min |
| Gargalo no restaurante 0, preparo ×4,5 | +0,3 min [0,2, 0,5] | +0,01 | +0,03 | +0,2 min |

O gargalo tem efeito global pequeno por construção (um restaurante); o portão de impacto também considera SLIs de zona e de restaurante.

## 3. Problemas encontrados e corrigidos (em ordem)

1. **Aquecimento.** A duração de entrega sobe de 20 para ~25 min até t≈80 e só então estabiliza. A referência original (20–70 min) caía no transiente. Referência movida para 80–125 min; falhas começam entre 130 e 165 min; horizonte 300 min.
2. **Mundo à beira do colapso.** Com 30 entregadores a utilização era **93%** (nenhum entregador livre em 53% dos minutos), gerando colapsos espontâneos em mundos "saudáveis". Padrão alterado para **40 entregadores (74%)**.
3. **Cozinhas subdimensionadas** depois de introduzir a popularidade de restaurantes (pior cozinha a 4,3× a capacidade). Cozinhas agora dimensionadas pela lei de Little com utilização-alvo de 60%.
4. **Detector, três versões:**
   - z-score por pedido: **68–80% de falso alarme**; pedidos da mesma janela compartilham congestionamento e não são independentes;
   - z calibrado: limiar efetivo ~13 (vs. 4 nominal), detecção lenta demais;
   - idade média da coorte: limitada por cancelamentos, quase não se move mesmo sob falhas grandes;
   - **versão final:** taxa de pedidos ruins numa coorte recente, com limiar calibrado.
5. **Monitor local desligado sem perceber:** com mínimo de 4 pedidos, o limiar calibrado (0,95) era inatingível porque a pontuação é `taxa − referência ≥ 0,05`. Mínimo passou a 6.
6. **Regra de gargalo olhava só pedidos concluídos:** os pedidos presos no restaurante afetado não apareciam. Corrigido com idade censurada e, no perfil completo, com a carga da cozinha.

## 4. Detector

Calibração em 300 mundos sem falha **com ruído ambiente** (conservador), meta de 5% de falso alarme por execução, limiares: **+0,254** (global) e **+0,45** (local) na taxa de pedidos ruins.

| | Falso alarme medido (sementes separadas, 150 cada) |
|---|---|
| Sem ruído | 0,0% (0/150) |
| Ruído ambiente | 6,0% (9/150), IC Wilson ~[3%, 11%] |

Poder de detecção (60 instâncias por família, severidade sorteada):

| Família | Detectadas | IC 95% | Atraso mediano após o início [IQR] |
|---|---|---|---|
| Escassez | 93% | [84%, 97%] | 77 min [69, 87] |
| Saturação | 100% | [94%, 100%] | 76 min [69, 92] |
| Gargalo de restaurante | 32% | [21%, 44%] | 76 min [62, 111] |

**Limite físico documentado:** com prazo prometido de 40 min, um atraso só é observável pelo cliente depois de 40 min. A detecção só por sinais do cliente não pode ser muito mais rápida que isso. Detecção rápida exige métricas operacionais (filas, frota), o que também é argumento de produto.

## 5. Benchmark e baselines (60 instâncias por nível)

| Nível | Perfil | Famílias | Tentativas médias | Regras (causa + escopo) | Regras (família) | Classe majoritária | Aleatório |
|---|---|---|---|---|---|---|---|
| L0 | completo | 3 | 2,1 | 0,65 [0,52, 0,76] | 0,68 | 0,38 | 0,38 |
| L1 (+ruído) | completo | 3 | 2,3 | 0,63 [0,51, 0,74] | 0,65 | 0,40 | 0,30 |
| L2 (+ruído) | cliente | 2 (par) | 1,2 | 0,00 (abstém) | 0,00 | 0,57 | 0,62 [0,49, 0,73] |

- No L2 as regras dizem "não resolvido entre escassez e saturação" em **82%** das instâncias. Nos 18% restantes acusam erroneamente gargalo de restaurante.
- **Vazamento:** 0 ocorrências em 180 payloads públicos. O teste de mutação confirma que a varredura detecta IDs crus, nomes de falha e canário plantados.
- O baseline de regras resolve cerca de 2/3 do L0–L1. Pelo critério da ADR-0005, isso **não** indica benchmark fácil demais, mas também não deixa muito espaço: vale acompanhar quando houver agentes.

## 6. Pendência bloqueante: o par do L2 não é observacionalmente equivalente

A ADR-0005 assumia que escassez e saturação seriam indistinguíveis só com dados de cliente. A sonda de distinguibilidade (validação cruzada em 5 partes, sobre as features observáveis de cada perfil) mostrou o contrário:

| Visão | n | Regressão logística | Gradient boosting | Acaso |
|---|---|---|---|---|
| Cliente | 136 | **0,93** ± 0,04 | 0,90 ± 0,02 | 0,54 |
| Completa | 76 | 1,00 | 1,00 | 0,51 |

O que separa o par (importância no gradient boosting, n=120):

1. **Magnitude:** mediana de entrega 27 vs. 35 min. As faixas de severidade não estavam pareadas: a saturação produz efeito ~2,5× maior.
2. **Padrão espacial:** sem nenhuma feature de magnitude a sonda ainda acerta **74%**. A escassez retira entregadores aleatórios e degrada zonas de forma desigual; a saturação atinge todas igualmente.

Consequência: o valor do experimento contrafactual **não pode** ser medido no L2 atual, porque a observação já resolve a maior parte dos casos. A ADR-0005 foi emendada: o rótulo de identificabilidade passa a ser **empírico**, dado pela sonda, nunca presumido.

**G2.1 (antes de usar o L2 no G3/G5):** trocar o par por **saturação do despachante × surto de erros de despacho com novas tentativas**. Ambos atrasam a atribuição de forma espacialmente uniforme; as severidades devem ser pareadas pelo efeito; "mais trabalhadores" corrige só a saturação. Critério de aceitação: limite superior do IC da sonda mais forte ≤ 0,60 na visão de cliente.

## 7. Sensibilidade da chave do aceite (ADR-0002)

| Intervenção | Chave por slot: efeito [IC], razão de variância | Chave por díade: efeito [IC], razão de variância |
|---|---|---|
| +5 entregadores | −0,24 [−0,33, −0,14], 0,074 | −0,20 [−0,28, −0,12], 0,051 |
| Política `eta_aware` | +1,35 [+1,13, +1,57], 0,339 | +1,38 [+1,16, +1,60], 0,310 |

As duas escolhas de identidade do evento dão estimativas compatíveis e redução de variância semelhante. A chave por slot fica como padrão.

## 8. G1 refeito no mundo final

O mundo padrão mudou no G2 (40 entregadores, popularidade, cozinhas dimensionadas). As medições do G1 foram refeitas (`docs/reports/G1_REPORT_DATA_v2.json`). Os 60 testes do G1 continuam passando. A razão de variância pareada/independente com RNG por evento ficou entre **0,0006 e 0,71**. Com RNG dependente da ordem (emulado), ficou entre **0,65 e 10,3**, ou seja, até 10× **pior** que não parear. A conclusão da ADR-0002 se fortaleceu.

## 9. Limitações

- Revisor e implementador são o mesmo; limiares das regras foram escolhidos por mecanismo, mas avaliados nas mesmas sementes de desenvolvimento.
- 60 instâncias por nível: ICs largos (±12 p.p.).
- O detector é um só para todos os perfis e não usa medidores operacionais; por isso o gargalo tem detecção baixa (32%).
- O portão de atribuição contrafactual usa o mundo sem falha pareado; isso é possível no simulador, não em operação real.
- O pareamento por classe de identificabilidade com o ISS-oráculo (ADR-0005 passo 3) ainda não foi implementado; depende do laboratório no G3.

# ADR-0009 — Dados externos e licenças

**Status:** Aceita (2026-11-01) · **Gate:** G0 · **Data:** 2026-11-01

## Decisão

1. A v0 usa **apenas dados sintéticos** e grafo viário sintético.
2. OpenStreetMap (via OSMnx), quando entrar, segue ODbL com atribuição.
3. LaDe (CC BY-NC-SA 4.0) só para **calibração local de distribuições**; o repositório publica o **script** de calibração, não os parâmetros derivados nem os dados. Revisar antes de qualquer uso comercial.
4. Geradores de terceiros (ex.: gerador de alarmes de telecom, Apache-2.0) podem inspirar formatos; código copiado mantém licença e atribuição.
5. Todo artefato publicado (modelo, dataset) declara origem sintética e limitações (RFC §6).

## Emenda 1 (2026-11-01, G2.1)

- **Grubhub MDRP** ([grubhub/mdrplib](https://github.com/grubhub/mdrplib)): instâncias anonimizadas de operação real. O repositório **não tem arquivo LICENSE**; o README diz que foram fornecidas para avançar a pesquisa. Uso: clonado localmente em `datasets/external/` (ignorado pelo git), apenas para calibração e comparação; publicamos o script (`scripts/compare_mdrp.py`) e estatísticas agregadas no relatório, nunca os dados. Antes de qualquer uso comercial, obter autorização.
- Outras bases avaliadas e não usadas: Meituan/INFORMS TSL (só acadêmico, sem redistribuição), Amazon Last Mile (CC BY-NC 4.0), LaDe (CC BY-NC-SA). Nenhuma base pública com incidentes de entrega e causa rotulada foi encontrada.

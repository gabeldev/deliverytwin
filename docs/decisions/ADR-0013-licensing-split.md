# ADR-0013 — Licenças: benchmark e modelo abertos, simulador em núcleo aberto (open-core)

**Status:** Aceita pelo responsável (2026-11-02), incluindo a fronteira do item 3 (**opção A**). · **Resolve:** ADR-0011 item 5 · **Gate:** G6

## Decisão do responsável

1. **Apache-2.0** para o que gera reputação de pesquisa:
   - o **adaptador LoRA** do G4, com crédito ao Qwen3 (Apache-2.0) e menção ao replay do Dolly-15k (CC BY-SA 3.0) no cartão;
   - o **benchmark**: instâncias, avaliador, protocolo de investigação, cartões e relatórios.
2. **Open-core** para o que vira produto. Simulador e laboratório ficam com uma parte aberta e uma parte proprietária, em repositório separado (ADR-0011 item 3).
3. Os dados de treino do G4 (traços e replay do Dolly) **não** serão publicados por padrão. Se forem, a parte do Dolly sai como CC BY-SA 3.0.

## Problema técnico que define a fronteira (decidido: opção A)

O benchmark **não roda sem o simulador**. Nos níveis L2, L4 e L6, a ferramenta `experiment` reexecuta o mundo verdadeiro (ou o gêmeo) a partir do alerta. Publicar só as instâncias deixaria esses níveis inutilizáveis. Há três formas de fechar a fronteira:

| Opção | O que é aberto | O que é fechado | Prós | Contras |
|---|---|---|---|---|
| **A. Simulador sintético aberto** (recomendada) | Mundo sintético, falhas, laboratório modo A/B sobre o mundo sintético, benchmark | Ingestão de dados reais, calibração de gêmeo a partir de dados de clientes, painel, serviço gerenciado (Cloud) | Benchmark reproduzível por qualquer um, o que gera citações. O valor comercial está em gêmeos de operações reais, não no mundo sintético | Concorrentes podem usar o simulador sintético |
| B. Laboratório hospedado | Instâncias, avaliador, cliente da API | Simulador inteiro; experimentos via API (cota gratuita para pesquisa) | Protege o simulador; já é o embrião do produto Cloud | Pesquisa depende de um servidor seu, com custo e disponibilidade. Menos reproduzível, o que pesa na revisão por pares |
| C. Experimentos pré-computados | Instâncias mais resultados de um cardápio fixo de experimentos | Simulador | Nada roda no seu servidor | Limita o agente ao cardápio. Muda o benchmark (perde a escolha livre de intervenções) |

**Escolhida pelo responsável: opção A.** A ADR-0011 já separa o núcleo sem conceitos comerciais dos componentes comerciais. O diferencial de produto é o gêmeo calibrado com dados reais (modo B real), a ingestão e o painel, e nada disso existe no repositório atual.

## Consequências

- **Este repositório é a parte aberta** e recebeu `LICENSE` (Apache-2.0) e `NOTICE` na raiz. Contém o mundo sintético, as falhas, o laboratório modo A/B sobre o mundo sintético, o benchmark, o avaliador, os agentes de referência e os scripts.
- **A parte proprietária vai para um repositório separado e privado** (ex.: `deliverytwin-cloud`, ADR-0011 item 3): ingestão de dados reais, calibração de gêmeo a partir de dados de clientes, painel e serviço gerenciado. Nada disso pode entrar neste repositório.
- **Repositório público:** cópia limpa do estado final, sem documentos comerciais internos e sem o histórico de desenvolvimento.
- Cada artefato publicado leva a própria licença: `license: apache-2.0` nos metadados do cartão do modelo e do cartão do dataset, e arquivo `LICENSE` junto do artefato no Hugging Face.
- Antes de publicar o benchmark, é preciso uma semente final secreta nova, porque a 515151 está nos documentos (LIMITATIONS §3).
- Dependências do núcleo seguem restritas a licenças compatíveis com Apache-2.0 e com uso comercial (ADR-0009).
- Não é aconselhamento jurídico. Antes de licenciamento comercial, consultar advogado de propriedade intelectual.

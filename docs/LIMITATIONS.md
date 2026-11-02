# Limitações e ameaças à validade (consolidado G1–G5)

Este documento reúne o que cada relatório declara como limitação, organizado pelo tipo de ameaça. Ler junto com os relatórios de cada portão.

## 1. Validade externa — o que os resultados **não** dizem

- **Dados 100% sintéticos.** O mundo foi calibrado em ordem de grandeza contra instâncias anonimizadas do Grubhub MDRP (G2.1), mas não reproduz uma operação real. Nenhum resultado afirma algo sobre empresas, entregadores ou incidentes reais.
- **A equivalência do L2 é construída.** O par "surto de erros de despacho × latência de dependência" foi escolhido e ajustado para ser indistinguível na telemetria do benchmark (sonda verificada). Isso valida o protocolo, que obriga o agente a experimentar. Não mostra que esses mecanismos sejam indistinguíveis numa operação real com observabilidade completa.
- **Taxonomia fechada.** São cinco famílias de falha, conhecidas pelo agente. Falhas fora da taxonomia, mudanças de regime e erros humanos não são modelados.
- **Mundo simplificado.** Cidade em grade com 3 zonas, sem agrupamento de pedidos, sem turnos e sem tráfego realista (G2.1 §6).

## 2. Validade de construto — o que as métricas medem

- **Acurácia exata** exige família e escopo corretos. O F1 do caminho causal pode ser inflado listando muitos nós e deve ser lido junto com a acurácia (G3 §6).
- **Δruim da recomendação** é medido no mundo verdadeiro em 3 réplicas do avaliador. No Estudo 1 foram 20 réplicas.
- **O gêmeo do modo B conhece a estrutura da falha.** Só os parâmetros estão errados, então os resultados do L6 e da varredura de δ são uma cota otimista. Um gêmeo com o mecanismo errado não foi estudado (G5 §2).
- **O cardápio de intervenções não tem ação no restaurante e é estreito.** No gargalo de restaurante, a "melhor ação" só mitiga. Em 16 dos 60 incidentes, agentes acharam ações viáveis melhores fora do cardápio (G5 §1.3).
- **O L5 não teve sonda de equivalência.** Diferente do L2, não está demonstrado que o experimento seja necessário nele (G5 §3.3).
- **A primária do L3** é definida pelo impacto isolado medido pelo gerador. Outra definição, como a causa que surgiu primeiro, mudaria as respostas corretas.

## 3. Validade estatística

- **n = 20 por nível** nas avaliações finais, com ICs de Wilson de cerca de ±0,20. Diferenças abaixo de ~0,3 raramente são significativas.
- **Sem correção de multiplicidade.** Cada comparação é rotulada principal (pré-registrada no G5) ou exploratória. Os portões G3 e G4 não tinham pré-registro e suas comparações devem ser lidas como exploratórias, exceto as definidas antes de rodar.
- **Uma execução por modelo**, com decodificação gulosa nos modelos locais e amostragem padrão nos de API. Não há variabilidade entre repetições.
- **A semente final foi reutilizada** nos portões G3–G5 com os mesmos 20 índices por nível. O desenho do G5 não foi ajustado olhando para ela (pré-registro antes), mas é a mesma amostra do G3.
- **A semente final (515151) está escrita nos documentos.** Quem tiver o código pode regenerar as instâncias e as respostas. Antes de qualquer release público do benchmark, é preciso criar uma semente secreta nova (`DELIVERYTWIN_MASTER_SEED`) para o conjunto selado. A 515151 passa a servir só para reproduzir este relatório.

## 4. Modelo adaptado (G4)

- **Atalho de distribuição.** A amostragem por rejeição ensina quais famílias aparecem em cada perfil. Parte do 0,90 no L2 e do 0,95 no L6 vem de o modelo saber qual sonda é discriminante nessa distribuição (G4 §3, G5 §3).
- **Generalização fraca.** No L5, um perfil que o modelo não viu, ele nunca experimenta e cai para 0,40.
- **Esquecimento.** No GSM8K, a métrica estrita cai de 0,61 para 0,14 e o último número da resposta, de 0,67 para 0,45. O adaptador serve só para este protocolo.
- **Um único especialista** gerou os traços. O modelo herda a ordem de sondas e os pontos cegos dele.

## 5. Agentes de API (G3, G5 adenda A1)

- O orçamento total foi de US$ 1,98, então só modelos pequenos e n = 20.
- O luna rodou sem raciocínio, por causa da rota de API usada.
- Os resultados dependem da versão do modelo no dia da execução e podem não se reproduzir depois.

## 6. Segurança e uso

- O agente só age por ferramentas tipadas e só dentro do laboratório. Nenhuma ação toca um sistema real (ADR-0008).
- Até 32% das recomendações de agentes de API reprovaram num filtro de viabilidade aplicado depois, que os agentes não conheciam, e também pioraram a métrica principal (G5 §1.3). Qualquer uso fora da pesquisa exige declarar as restrições ao agente, verificá-las antes de agir e ter aprovação humana.

## 7. Reprodutibilidade

- O simulador é determinístico por semente e as execuções sem GPU e sem API se reproduzem byte a byte (testes de replay no CI).
- O treino do G4 depende de GPU, de versões de bibliotecas (`uv.lock`) e de não determinismo do CUDA. O adaptador e os traços ficam fora do git (`runs/g4/`).
- Os dados do MDRP não são redistribuídos. Para refazer a calibração do G2.1, é preciso cloná-los localmente (ADR-0009).

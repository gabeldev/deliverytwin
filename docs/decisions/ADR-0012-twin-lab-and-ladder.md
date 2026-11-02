# ADR-0012 — Laboratório modo B (gêmeo) e escada L3–L6

**Status:** Proposta (2026-11-02), implementada no G5 em execução autônoma; aguarda aceite do responsável · **Gate:** G5

## Contexto

A ADR-0003 previa dois modos de laboratório, e a ADR-0005 previa a escada L0–L6. Até o G4 existiam só o modo A (bifurcações do mundo verdadeiro) e os níveis L0–L2. A ADR-0011 trata o modo B e o L6 como o caminho do produto: numa operação real, o único laboratório possível é um gêmeo imperfeito.

## Decisão

1. **Gêmeo (modo B)**, em `deliverytwin/counterfactual/twin.py`:
   - roda o mesmo código de simulação com outra semente, derivada do registro privado e nunca igual a s\*;
   - multiplica os parâmetros por exp(δ·Z): frota, demanda por zona, preparo, serviço do despachante, espera de nova tentativa e paciência;
   - aplica a mesma perturbação à severidade da falha e desloca o início em δ·20 min.
2. O gêmeo **conhece o mecanismo da falha**. É, portanto, uma cota otimista de um gêmeo estimado de verdade. O descompasso estrutural (mecanismo errado) fica para uma ADR futura.
3. O avaliador mede a recomendação **sempre no mundo verdadeiro** (modo A, réplicas disjuntas). É isso que separa "parece funcionar no gêmeo" de "funciona na operação".
4. Para o agente:
   - no modo B, a resposta de `observe` traz uma linha "Lab: … TWIN …" e os resultados vêm marcados como `twin lab experiment`;
   - no modo A, o texto continua idêntico byte a byte ao do G3/G4, porque os traços de SFT foram renderizados com ele (há teste de regressão).
5. **Escada:**

   | Nível | Conteúdo |
   |---|---|
   | L3 | Falha global + gargalo de restaurante no mesmo incidente; a resposta é a falha **primária**, a de maior impacto isolado medido pelo gerador |
   | L4 | Par do L2 com folga de orçamento zero (8 consultas, 1 experimento, 1,0 unidade) |
   | L5 | Famílias do L0 no perfil `partial`, sem os medidores de frota e despacho |
   | L6 | Par do L2 com laboratório modo B (δ = 0,25) |

6. Os orçamentos e o modo de laboratório vêm da definição do nível (`LEVELS`). Uma sessão pode sobrescrevê-los explicitamente, por exemplo na varredura de δ.

## Consequências

- O ponto central da ADR-0003 fica mensurável: a perda de acurácia e de qualidade da recomendação em função de δ.
- A pontuação do L3 aceita uma resposta única (a primária). Um protocolo de múltiplas causas exigiria mudar o `Report` e o avaliador; isso fica adiado.
- Os níveis L0–L2 e seus números do G3/G4 não mudam: o gerador só sorteia a segunda falha no L3.

## Verificação

`tests/benchmark/test_g5_levels.py`:
- o gêmeo usa outra semente;
- com δ = 0, a configuração do gêmeo é igual à do mundo;
- o placebo dá diferença exatamente nula nos dois modos;
- o texto do modo A não mudou;
- o L4 bloqueia o segundo experimento;
- o L5 recusa medidores ausentes sem cobrar a consulta;
- o L3 tem a falha secundária registrada.

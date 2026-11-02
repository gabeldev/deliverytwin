# Revisão independente (Codex) do site público

**Data:** 2026-11-02 · **Prompt:** `codex_review_prompt_site.txt` · **Escopo:** `site/`, `scripts/site_export.py`, `scripts/site_research.py`, dados exportados. O Codex confirmou como corretos a separação da verdade oculta, os números de pesquisa e os 140 intervalos do laboratório.

| # | Achado | Situação |
|---|---|---|
| 1 | Limite de tamanho burlável (só lia Content-Length) | Corrigido: leitura em fluxo com teto de 4 KB |
| 2 | JSON válido não-objeto derrubava a rota | Corrigido: 400 estruturado |
| 3 | Limite de taxa só por instância | Mitigado (mapa limitado, honeypot, teto); limitador compartilhado pendente (DECISIONS §4) |
| 4 | Decisões reais com efeito nulo rotuladas como placebo | Corrigido: placebo só pela chave |
| 5 | Interpretador invertia pedidos ("remove", "nearest", compostos) | Corrigido + testes; a interpretação é sempre exibida |
| 6 | Janelas recentes pareciam recuperação | Corrigido: só janelas com ≥ 90% dos desfechos conhecidos |
| 7 | Futuros individuais fora do gráfico | Corrigido: domínio pelos extremos; lista textual por réplica |
| 8 | Respostas do FAQ fora da árvore de acessibilidade no desktop | Corrigido |
| 9 | Quadros ocultos com controles focáveis | Corrigido: `inert` |
| 10 | Contraste de marcas e foco | Corrigido: cores mais escuras, validadas (≥ 4:1, daltonismo ΔE ≥ 9,3) |
| 11 | Mapa e réplicas sem alternativa textual | Corrigido: anel nos atrasados, resumo para leitores de tela, lista de réplicas |
| 12 | Animação sem pausa; rolagem suave ignorava "reduzir movimento" | Corrigido |
| 13 | Quantidades diferentes chamadas de concordância | Corrigido: compara a decisão completa |
| 14 | "Testa cada decisão antes de recomendar" | Corrigido: "pode testar" |
| 15 | Restrição de admissão como garantia | Corrigido: "recusa esperada" |
| 16 | Gêmeo generalizado; "metade ou mais" | Corrigido: caso otimista declarado; 45–63% |
| 17 | Grupos de rádio sem navegação por setas | Pendente (baixa) |
| 18 | Proveniência de réplicas fixa no código | Corrigido: derivada; 2–20 réplicas |
| 19 | Canal de exclusão dependia de resposta | Corrigido: pedido pelo próprio formulário |
| 20 | Sem CSP | Pendente (baixa) |

## Revisão original

Read-only review completed; excluded paths were not read and no files were changed. The live deployment was inaccessible, so browser and accessibility findings below are based on source inspection, exported data and calculated contrast.

1. **Medium — Request-size limit is bypassable.** [route.ts:18](site/app/api/interest/route.ts:18) checks only the supplied `Content-Length`, then parses the entire body. An in-memory request containing a 100 KB message without that header returned 200 with mocked storage. **Fix:** enforce a byte limit while reading the request stream, before parsing JSON.

2. **Medium — Valid JSON can cause an uncaught server error.** [route.ts:22](site/app/api/interest/route.ts:22) assumes the parsed value is an object. Posting `null` throws when reading `body.website`; the JSON-parsing catch does not cover this. **Fix:** reject null, arrays and non-object values with a structured 400 response before accessing fields.

3. **Medium — Abuse protection is limited to one function instance.** [route.ts:9](site/app/api/interest/route.ts:9) stores limits in a process-local map. Limits reset on cold starts and are independent across instances; expired IP keys are never removed. This leaves the storage-writing endpoint exposed to distributed submission abuse. **Fix:** use an expiring shared limiter and a deployment-trusted client identity; bound or remove the local map.

4. **Medium — Real interventions are incorrectly labelled “Placebo.”** [CounterfactualLab.tsx:88](site/components/lab/CounterfactualLab.tsx:88) interprets `all_zero` as identical futures. However, [site_export.py:307](scripts/site_export.py:307) checks only bad-rate differences. In `l0-3`, mode A, `workers_3` has `all_zero: true` while penalised delivery time improves by **10.65 minutes**. **Fix:** identify placebo by intervention kind; describe other cases as zero observed bad-rate difference. Metric equality does not establish identical trajectories.

5. **Medium — The what-if parser can reverse the requested decision.** [whatif.ts:29](site/lib/whatif.ts:29) uses keyword matching and unsigned numbers. Reproduced examples: “remove 10 couriers” selects **add 10 couriers**; “nearest policy” selects **ETA-aware policy**; “add 10 couriers and 8 workers” selects only workers. Some incorrect interpretations receive no warning. **Fix:** explicitly recognise supported actions and direction, reject unsupported or compound requests, and display the interpreted decision.

6. **Medium — Recent telemetry windows can misleadingly show recovery.** [series.ts:9](site/lib/series.ts:9) divides bad outcomes by currently known outcomes, omitting pending orders. In `l2-0`, the window starting at minute 240 displays **0%**, although only **7 of 22** orders have known outcomes. A minimum of six resolved orders does not remove this completion bias. **Fix:** suppress immature creation cohorts or prominently show outcome coverage and identify the conditional denominator.

7. **Medium — “Each paired future” plots omit outlying replicas.** [CounterfactualLab.tsx:30](site/components/lab/CounterfactualLab.tsx:30) derives the strip-plot domain from confidence intervals for means, then plots individual replica differences on that domain. Individual observations extend farther. For `l0-1`, mode B, adding 20 couriers puts **6 of 20** replica centres outside the SVG viewport. **Fix:** calculate the strip’s domain from replica extrema, including marker padding.

8. **Medium — Desktop FAQ answers are absent from the accessibility tree.** [Faq.tsx:20](site/components/home/Faq.tsx:20) provides an inline answer that CSS hides on desktop, while the visible desktop answer pane has `aria-hidden="true"`. Screen-reader users can reach the questions but cannot read their answers at desktop widths. **Fix:** keep one accessible answer representation visible to assistive technology at every breakpoint.

9. **Medium — Hidden hero frames retain keyboard-focusable controls.** [HeroReel.tsx:107](site/components/home/HeroReel.tsx:107) applies `aria-hidden` to inactive frames without removing their chart `<summary>` controls from keyboard navigation. Transforms, opacity and `pointer-events: none` do not prevent tab focus. **Fix:** apply `inert` to inactive frames or mount only the active frame.

10. **Medium — Some chart marks and focus indicators have insufficient contrast.** [globals.css:29](site/app/globals.css:29) defines orange chart marks with approximately **2.88:1** contrast against panel background `#f3f3f3`; the green zone series is approximately **2.54:1**. The contact field’s green focus ring is approximately **2.37:1** against that background. **Fix:** darken these tokens to meet 3:1 for essential graphics and focus indicators, and verify each actual background.

11. **Medium — Map states and replica distributions lack equivalent alternatives.** [CityMap.tsx:137](site/components/CityMap.tsx:137) distinguishes late couriers through colour alone; its canvas label supplies no restaurant-level or courier-level equivalent. [CounterfactualLab.tsx:100](site/components/lab/CounterfactualLab.tsx:100) labels the replica strip generically without exposing its values. **Fix:** add non-colour map marks and an accessible snapshot/table; provide replica IDs and differences in a table or expandable list.

12. **Medium — Automatic motion has no pause control.** [HeroReel.tsx:55](site/components/home/HeroReel.tsx:55) starts an indefinitely looping city animation without a pause button. Initial reduced-motion preferences stop that autoplay, but [LabApp.tsx:54](site/components/lab/LabApp.tsx:54) explicitly requests smooth scrolling regardless of that preference. **Fix:** provide pause/resume and choose instant scrolling when reduced motion is requested.

13. **Medium — Different recommended quantities are described as agreement.** [Conclusion.tsx:75](site/components/lab/Conclusion.tsx:75) compares intervention `kind`, ignoring parameters. In `l0-1`, mode A selects **5 couriers** and mode B selects **20 couriers**, yet the page says both labs agree on the best decision. **Fix:** compare complete arm keys or normalised interventions; distinguish agreement on intervention family from agreement on quantity.

14. **Medium — The hero promises experimentation before every recommendation.** [i18n.ts:16](site/lib/i18n.ts:16), also Portuguese line 160, says the investigator tests each decision before recommending anything. The exported `l0-3` Qwen SFT session recommends adding 10 couriers after **zero experiments**. **Fix:** describe experimentation as a supported investigation capability, without promising it occurs before every recommendation.

15. **Medium — The admission constraint is presented as a guaranteed outcome.** [lab-i18n.ts:46](site/lib/lab-i18n.ts:46) says “turn away at most 20%.” The simulator constrains the admission **parameter**, so realised rejection can exceed 20%. Exported examples include **21.44%** for `l2-0` mode A. [G5_REPORT.md:34](docs/reports/G5_REPORT.md:34) explicitly documents this distinction. **Fix:** state “expected rejection at most 20%” and distinguish it from observed rejection.

16. **Medium — Twin copy overgeneralises an optimistic model.** [lab-i18n.ts:39](site/lib/lab-i18n.ts:39) says a real operation only ever has a twin “like this,” without explaining that this twin already knows the correct fault structure. [G5_REPORT.md:92](docs/reports/G5_REPORT.md:92) calls that an optimistic case and excludes incorrect mechanisms. The homepage also says recommendations lose “half or more” of their benefit, while the report gives approximately **45–63%**. **Fix:** disclose the known-mechanism assumption and use the reported range.

17. **Low — Custom radio groups lack expected keyboard behaviour.** [Investigation.tsx:17](site/components/lab/Investigation.tsx:17), incident selection and lab-mode selection use buttons with radio roles, but implement neither arrow-key selection nor a single tab stop. Tab and activation still work. **Fix:** use native radio inputs or implement the complete radio-group keyboard pattern.

18. **Low — Replica provenance becomes false with supported CLI options.** [site_export.py:359](scripts/site_export.py:359) hardcodes provenance to `3001-3020`, despite accepting arbitrary `--replicas`. Several UI explanations also hardcode 20 futures. **Fix:** derive provenance and copy from actual replica IDs/counts, and reject replica counts that cannot support the advertised confidence interval.

19. **Low — The documented deletion channel depends on receiving a reply.** [i18n.ts:134](site/lib/i18n.ts:134) tells visitors to request deletion by replying to an email. A visitor who has not received that email has no documented deletion contact. **Fix:** publish a deletion-request address or explicitly document a request workflow available immediately after submission.

20. **Low — Security headers lack a Content Security Policy.** [next.config.ts:3](site/next.config.ts:3) includes useful defensive headers but no CSP. This is a defence-in-depth gap; I found no corresponding script-injection sink in the reviewed components. **Fix:** introduce a tested Next.js-compatible CSP, preferably through report-only deployment first.

Checked and found clean, within the stated limits:

- **Hidden-truth separation:** all five ordinary scenario JSON files omit injected-fault parameters and evaluator verdicts. Agent hypotheses and submitted diagnoses remain appropriately separate from evaluator truth. The lab route loads ordinary data; its explicit truth fetch occurs in the Reveal handler.
- **Homepage exception:** `l2-2` truth is intentionally included in the homepage payload and narrated end to end. Simulation, recording, submitted diagnosis and evaluator truth are labelled honestly. Consequently, this incident is already spoiled for visitors arriving through the homepage. Public truth files provide presentation separation, not access control.
- **Research evidence:** displayed accuracies, intervals, ablation results, ladders, twin sweep, variance/regret figures, GSM8K and names-only results match the report data. The research page preserves important qualifications and failed predictions. I found no claim of demonstrated real-world savings or live LLM execution.
- **Export calculations:** all **140** shipped lab-arm confidence intervals match paired Student-t calculations within rounding. Current replica ranges are correct and disjoint as documented. Counterfactual bin boundaries, trajectory destinations/endpoints and consecutive courier-position reconstruction showed no discrepancy in the exported scenarios.
- **Storage and errors:** consent is checked server-side; writes explicitly request private Blob access; stored records omit IP addresses; storage failures return generic errors without exposing credentials.
- **Accessibility foundations:** form controls have labels, general focus styling and a skip link exist, status chips include icons and text, and the main line/effect/accuracy charts expose tables or numeric equivalents.
- **Verification:** all five existing parser tests passed, and TypeScript checking passed with emission and incremental writes disabled. No production build, real contact submission or deployed storage test was performed.
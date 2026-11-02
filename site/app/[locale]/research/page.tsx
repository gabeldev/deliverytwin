import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { isLocale, type Locale } from "@/lib/i18n";
import { REPO, HF, blob, loadResearch } from "@/lib/data";
import { AccuracyRows } from "@/components/charts";
import Status from "@/components/ui/Status";
import r from "./research.module.css";

const T = {
  en: {
    title: "Research and results",
    lead: "What was tested, how, and what came out, including what failed. Final seed 515151, 20 held-out incidents per condition, exact McNemar tests and 95% Wilson intervals. No multiplicity correction, so each comparison is labelled pre-registered or exploratory.",
    docs: [["Pre-registration", "docs/methods/PREREG_G5.md"], ["G5 report", "docs/reports/G5_REPORT.md"], ["G4 report", "docs/reports/G4_REPORT.md"], ["G3 report", "docs/reports/G3_REPORT.md"], ["Independent reviews", "docs/reviews"], ["Limitations", "docs/LIMITATIONS.md"]],
    q: "The question", qBody: "Can an agent find the hidden cause of an operational incident when observation alone cannot tell two causes apart, and does testing decisions in paired counterfactual experiments make the difference? The benchmark's levels make this progressively harder: L0 full gauges, L1 noise, L2 two causes with identical customer-facing telemetry, L4 a one-experiment budget, L5 missing gauges, L6 an imperfect twin.",
    levels: "Accuracy by agent and level", levelsNote: "Exact cause, 20 incidents each. Dot = accuracy, line = 95% Wilson interval.",
    exp: "Removing the experiment tool", expBody: "Same fine-tuned model, same 20 L2 incidents, same 25-query budget; only the experiment tool removed. Without it the model answers dispatch latency in all 20 cases.",
    matched: "Same incidents, harder conditions", matchedBody: "The L2 incidents re-run with the L4 budget (one experiment) and with the L6 imperfect twin. Matching the incidents isolates the condition.",
    cond: ["L2, true-world lab", "L4 budget", "L6 twin"],
    inv: "The L5 inversion", invBody: "With fleet and dispatcher gauges removed (L0 fault families), the API models run experiments on their own and score highest; our model never experiments there. On the constructed equivalent pair the order flips. L5 had no equivalence probe, so it shows the gauges' absence defeats observational rules, not that experiments are strictly required.",
    twin: "An imperfect twin", twinBody: "Playbook on L2 with the lab moved to a twin whose parameters are perturbed by δ. Changing only the seed (δ = 0) costs nothing; δ ≥ 0.1 loses four or more correct answers (paired p = 0.06–0.13, not significant alone) and the recommendation's true-world benefit falls by about 45–63%.",
    rec: "Benefit of the recommendation (Δ bad-order rate, true world)",
    pair: "Why paired futures", pairBody: "Event-keyed randomness means a control and a treatment share every random draw except those the decision touches. A placebo therefore gives exactly 0.000 in every future of all 60 incidents, and pairing cuts the variance of a contrast to 3–30% of the unpaired one (median by intervention).",
    action: "Intervention", median: "Median ratio", share: "Share of incidents below 1",
    regret: "Regret of recommendations", regretBody: "How far each recommendation falls short of the best feasible action seen for that incident (menu plus every feasible recommendation, same 20 replicas). Recommendations that fail the feasibility screen (admission below 80%) are counted apart; agents were never told that constraint.",
    agent: "Agent", mean: "Mean regret", n: "Scored", infeasible: "Failed screen",
    forget: "What fine-tuning cost", forgetBody: "150 fixed GSM8K problems, greedy decoding. The adapter mostly stops following output-format instructions, and even a lenient reading shows a real drop. It is a narrow specialist; use it only inside this protocol.",
    strict: "Strict format", lenient: "Last number (lenient, exploratory)",
    names: "Leakage control", namesBody: "A classifier that sees only the opaque identifiers and dataset id never beats the training-majority baseline by more than 0.05 (registered threshold 0.10). This does not certify the absence of leakage.",
    score: "Pre-registered predictions", scoreRows: [
      ["Placebo gives exactly zero (H8)", "Confirmed", "ok"],
      ["Paired variance below unpaired (H7)", "Partly met: median criterion met; 31 per-incident ratios ≥ 1", "part"],
      ["Accuracy does not rise with twin error", "Confirmed (descriptive)", "ok"],
      ["Playbook beats rules on L5", "Confirmed, p = 0.016", "ok"],
      ["Playbook keeps its L2 accuracy on L4; fine-tuned model not better than base", "Refuted on both counts", "no"],
      ["Fine-tuning gain shrinks on L5 (H2)", "Ambiguous: shrinks vs pooled L0–L2, equal vs L0", "part"],
      ["Experiments beat no experiments on L2 (H1/H9)", "Confirmed, p = 0.022", "ok"],
      ["Names alone ≤ majority + 0.10 (H10)", "Confirmed at the threshold", "ok"],
    ] as [string, string, string][],
    repro: "Reproduce", reproBody: "Every number on this page regenerates from the public code.",
    seeAlso: "Code and model",
  },
  pt: {
    title: "Pesquisa e resultados",
    lead: "O que foi testado, como, e o que saiu, inclusive o que falhou. Semente final 515151, 20 incidentes reservados por condição, testes exatos de McNemar e intervalos de Wilson de 95%. Sem correção de multiplicidade, por isso cada comparação é rotulada como pré-registrada ou exploratória.",
    docs: [["Pré-registro", "docs/methods/PREREG_G5.md"], ["Relatório G5", "docs/reports/G5_REPORT.md"], ["Relatório G4", "docs/reports/G4_REPORT.md"], ["Relatório G3", "docs/reports/G3_REPORT.md"], ["Revisões independentes", "docs/reviews"], ["Limitações", "docs/LIMITATIONS.md"]],
    q: "A pergunta", qBody: "Um agente consegue achar a causa oculta de um incidente operacional quando só observar não separa duas causas, e testar decisões em experimentos contrafactuais pareados faz a diferença? Os níveis do benchmark dificultam isso aos poucos: L0 com medidores completos, L1 com ruído, L2 com duas causas de telemetria idêntica para o cliente, L4 com orçamento de um experimento, L5 sem medidores, L6 com um gêmeo imperfeito.",
    levels: "Acurácia por agente e nível", levelsNote: "Causa exata, 20 incidentes cada. Ponto = acurácia, linha = intervalo de Wilson de 95%.",
    exp: "Sem a ferramenta de experimento", expBody: "Mesmo modelo ajustado, mesmos 20 incidentes do L2, mesmo orçamento de 25 consultas; só a ferramenta de experimento foi retirada. Sem ela, o modelo responde latência de despacho nos 20 casos.",
    matched: "Mesmos incidentes, condições mais difíceis", matchedBody: "Os incidentes do L2 rodados de novo com o orçamento do L4 (um experimento) e com o gêmeo imperfeito do L6. Parear os incidentes isola a condição.",
    cond: ["L2, laboratório no mundo verdadeiro", "Orçamento do L4", "Gêmeo do L6"],
    inv: "A inversão do L5", invBody: "Sem os medidores de frota e do despachante (famílias do L0), os modelos de API experimentam por conta própria e ficam no topo; nosso modelo nunca experimenta ali. No par equivalente construído, a ordem se inverte. O L5 não teve sonda de equivalência: mostra que a falta de medidores derruba as regras observacionais, não que o experimento seja estritamente necessário.",
    twin: "Um gêmeo imperfeito", twinBody: "Playbook no L2 com o laboratório num gêmeo de parâmetros perturbados por δ. Trocar só a semente (δ = 0) não custa nada; δ ≥ 0,1 perde quatro acertos ou mais (p pareado = 0,06–0,13, não significativo sozinho) e o benefício real da recomendação cai cerca de 45–63%.",
    rec: "Benefício da recomendação (Δ taxa de pedidos ruins, mundo verdadeiro)",
    pair: "Por que futuros pareados", pairBody: "Com aleatoriedade indexada por evento, controle e tratamento compartilham todos os sorteios, exceto os que a decisão toca. Por isso um placebo dá exatamente 0,000 em todos os futuros dos 60 incidentes, e o pareamento reduz a variância de um contraste a 3–30% da não pareada (mediana por intervenção).",
    action: "Intervenção", median: "Razão mediana", share: "Fração de incidentes abaixo de 1",
    regret: "Arrependimento das recomendações", regretBody: "Quanto cada recomendação fica atrás da melhor ação viável vista naquele incidente (cardápio mais toda recomendação viável, mesmas 20 réplicas). Recomendações reprovadas no filtro de viabilidade (admissão abaixo de 80%) contam à parte; os agentes nunca foram informados dessa restrição.",
    agent: "Agente", mean: "Arrependimento médio", n: "Pontuadas", infeasible: "Reprovadas no filtro",
    forget: "O que o ajuste custou", forgetBody: "150 problemas fixos do GSM8K, decodificação gulosa. O adaptador deixa de seguir instruções de formato, e mesmo uma leitura tolerante mostra queda real. É um especialista estreito; use só dentro deste protocolo.",
    strict: "Formato estrito", lenient: "Último número (tolerante, exploratório)",
    names: "Controle de vazamento", namesBody: "Um classificador que só vê os identificadores ofuscados e o id do conjunto nunca supera em mais de 0,05 a classe majoritária do treino (limiar registrado 0,10). Isso não certifica ausência de vazamento.",
    score: "Previsões pré-registradas", scoreRows: [
      ["Placebo dá exatamente zero (H8)", "Confirmada", "ok"],
      ["Variância pareada abaixo da não pareada (H7)", "Parcial: critério da mediana atendido; 31 razões por incidente ≥ 1", "part"],
      ["Acurácia não sobe com o erro do gêmeo", "Confirmada (descritiva)", "ok"],
      ["Playbook supera regras no L5", "Confirmada, p = 0,016", "ok"],
      ["Playbook mantém acurácia do L2 no L4; modelo ajustado não supera o base", "Refutada nas duas partes", "no"],
      ["Ganho do ajuste encolhe no L5 (H2)", "Ambígua: encolhe contra L0–L2 agrupado, igual contra L0", "part"],
      ["Experimento supera ausência de experimento no L2 (H1/H9)", "Confirmada, p = 0,022", "ok"],
      ["Nomes sozinhos ≤ maioria + 0,10 (H10)", "Confirmada no limiar", "ok"],
    ] as [string, string, string][],
    repro: "Reproduzir", reproBody: "Cada número desta página é regenerado a partir do código público.",
    seeAlso: "Código e modelo",
  },
};

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  return { title: T[locale].title, description: T[locale].lead };
}

const LEVELS: Record<Locale, [string, string][]> = {
  en: [["L0", "Full gauges; courier scarcity, dispatcher saturation or a restaurant bottleneck"], ["L1", "L0 plus telemetry noise"], ["L2", "Two causes with identical customer-facing telemetry"], ["L3", "Two simultaneous faults; name the primary one"], ["L4", "L2 with one experiment and 8 queries"], ["L5", "L0 faults with fleet and dispatcher gauges removed"], ["L6", "L2 with the lab on an imperfect twin"]],
  pt: [["L0", "Medidores completos; falta de entregadores, despachante saturado ou gargalo de restaurante"], ["L1", "L0 com ruído na telemetria"], ["L2", "Duas causas com telemetria idêntica para o cliente"], ["L3", "Duas falhas simultâneas; nomear a principal"], ["L4", "L2 com um experimento e 8 consultas"], ["L5", "Falhas do L0 sem os medidores de frota e despachante"], ["L6", "L2 com o laboratório num gêmeo imperfeito"]],
};

const AG: [string, string][] = [["rules", "Rules"], ["playbook", "Playbook"], ["gpt-5-nano", "gpt-5-nano"], ["gpt-5-mini", "gpt-5-mini"], ["gpt-5.6-luna", "gpt-5.6-luna"], ["qwen-base", "Qwen base"], ["qwen-sft", "Qwen + LoRA"]];

export default async function Research({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = T[locale as Locale];
  const d = await loadResearch();
  const lad = d.ladder as Record<string, Record<string, { exact: number; ci: [number, number]; experiments_mean: number }>>;
  const ml = d.matched_ladder as Record<string, Record<string, { exact: number; ci: [number, number] }>>;
  const conds = ["L2_mode_A", "L4_budgets", "L6_twin_0.25"];
  const pre = locale === "pt" ? "pré-registrado" : "pre-registered";
  const expl = locale === "pt" ? "exploratório" : "exploratory";
  const f2 = (v: number) => v.toFixed(2);

  return (
    <article className={r.page}>
      <header className={`${r.head} wrap`}>
        <h1 className={r.h1}>{t.title}</h1>
        <p className={r.lead}>{t.lead}</p>
        <ul className={r.docs}>{t.docs.map(([n, p]) => <li key={p}><a href={blob(p)}>{n}</a></li>)}</ul>
      </header>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="q">
        <div>
          <h2 id="q" className={r.h2}>{t.q}</h2>
          <p className={r.body}>{t.qBody}</p>
        </div>
        <ol className={`${r.levels} rise`}>
          {LEVELS[locale as Locale].map(([k, v]) => <li key={k}><b>{k}</b><span>{v}</span></li>)}
        </ol>
      </section>

      <section className={`${r.sec} wrap`} aria-labelledby="lv">
        <h2 id="lv" className={r.h2}>{t.levels}</h2>
        <p className={r.note}>{t.levelsNote}</p>
        <div className={r.three} data-ui>
          {(["L0", "L1", "L2"] as const).map((lv) => (
            <div key={lv} className={`${r.card} rise`}>
              <h3 className={r.h3}>{lv}</h3>
              <AccuracyRows ariaLabel={`${t.levels} ${lv}`} highlight="qwen-sft"
                rows={AG.map(([k, n]) => ({ key: k, label: n, acc: d.levels[k][lv].acc, ci: d.levels[k][lv].ci }))} />
            </div>
          ))}
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="ex">
        <div>
          <h2 id="ex" className={r.h2}>{t.exp}</h2>
          <p className={r.body}>{t.expBody}</p>
          <p className={r.tag}><Status kind="experiment" locale={locale} label={pre} /> <span className="tnum">{d.experiment_ablation.paired.only_first} : {d.experiment_ablation.paired.only_second}, p = {d.experiment_ablation.paired.mcnemar_p.toFixed(3)}</span></p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <AccuracyRows ariaLabel={t.exp} rows={[
            { key: "w", label: locale === "pt" ? "Com experimento" : "With experiment", acc: d.experiment_ablation.with.exact, ci: d.experiment_ablation.with.ci },
            { key: "wo", label: locale === "pt" ? "Sem experimento" : "Without experiment", acc: d.experiment_ablation.without.exact, ci: d.experiment_ablation.without.ci },
          ]} />
        </div>
      </section>

      <section className={`${r.sec} wrap`} aria-labelledby="ml">
        <h2 id="ml" className={r.h2}>{t.matched}</h2>
        <p className={r.body}>{t.matchedBody}</p>
        <div className={r.three} data-ui>
          {conds.map((c, i) => (
            <div key={c} className={`${r.card} rise`}>
              <h3 className={r.h3}>{t.cond[i]}</h3>
              <AccuracyRows ariaLabel={t.cond[i]} highlight="qwen-sft" rows={["rules", "playbook", "qwen-base", "qwen-sft"].map((a) => ({ key: a, label: AG.find(([k]) => k === a)![1], acc: ml[c][a].exact, ci: ml[c][a].ci }))} />
            </div>
          ))}
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="inv">
        <div>
          <h2 id="inv" className={r.h2}>{t.inv}</h2>
          <p className={r.body}>{t.invBody}</p>
          <p className={r.tag}><Status kind="hypothesis" locale={locale} label={expl} /></p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <table className={r.table}>
            <thead><tr><th scope="col">{t.agent}</th><th scope="col">L4</th><th scope="col">L5</th><th scope="col">L6</th><th scope="col">{locale === "pt" ? "Exp./ep. L5" : "Exp./ep. L5"}</th></tr></thead>
            <tbody>
              {["playbook", "qwen-base", "qwen-sft", "gpt-5-mini", "gpt-5.6-luna"].map((a) => (
                <tr key={a}><th scope="row">{AG.find(([k]) => k === a)![1]}</th>
                  {["L4", "L5", "L6"].map((lv) => <td key={lv} className="tnum">{f2(lad[a][lv].exact)}<small> {f2(lad[a][lv].ci[0])}–{f2(lad[a][lv].ci[1])}</small></td>)}
                  <td className="tnum">{lad[a].L5.experiments_mean?.toFixed(1)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="tw">
        <div>
          <h2 id="tw" className={r.h2}>{t.twin}</h2>
          <p className={r.body}>{t.twinBody}</p>
          <p className={r.tag}><Status kind="experiment" locale={locale} label={pre} /></p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <table className={r.table}>
            <thead><tr><th scope="col">Lab</th><th scope="col">{locale === "pt" ? "Acurácia" : "Accuracy"}</th><th scope="col">{t.rec}</th><th scope="col">p vs A</th></tr></thead>
            <tbody>
              {Object.entries(d.twin_sweep).map(([k, v]) => (
                <tr key={k}><th scope="row">{k === "mode_A" ? "A" : k.replace("delta_", "δ = ")}</th>
                  <td className="tnum">{f2(v.exact)}<small> {f2(v.ci[0])}–{f2(v.ci[1])}</small></td>
                  <td className="tnum">{(v.rec_diff_bad * 100).toFixed(1)} pts</td>
                  <td className="tnum">{k === "mode_A" ? "–" : v.vs_A_p == null ? "–" : v.vs_A_p.toFixed(3)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="pr">
        <div>
          <h2 id="pr" className={r.h2}>{t.pair}</h2>
          <p className={r.body}>{t.pairBody}</p>
          <p className={r.tag}><Status kind="experiment" locale={locale} label={pre} /> <span>placebo = 0.000: {String(d.interventions.placebo_all_exactly_zero)}</span></p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <table className={r.table}>
            <thead><tr><th scope="col">{t.action}</th><th scope="col">{t.median}</th><th scope="col">{t.share}</th></tr></thead>
            <tbody>{Object.entries(d.interventions.variance_ratio).map(([k, v]) => (
              <tr key={k}><th scope="row"><code>{k}</code></th><td className="tnum">{v.median.toFixed(3)}</td><td className="tnum">{v.share_below_1.toFixed(2)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="rg">
        <div>
          <h2 id="rg" className={r.h2}>{t.regret}</h2>
          <p className={r.body}>{t.regretBody}</p>
          <p className={r.tag}><Status kind="hypothesis" locale={locale} label={expl} /></p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <table className={r.table}>
            <thead><tr><th scope="col">{t.agent}</th><th scope="col">{t.mean}</th><th scope="col">{t.n}</th><th scope="col">{t.infeasible}</th></tr></thead>
            <tbody>{Object.entries(d.interventions.regret_common_oracle).map(([k, v]) => (
              <tr key={k}><th scope="row">{k === "remedy" ? (locale === "pt" ? "Remédio-padrão (família verdadeira)" : "Fixed remedy (true family)") : k}</th>
                <td className="tnum">{v.mean.toFixed(3)}</td><td className="tnum">{v.n}</td><td className="tnum">{d.interventions.infeasible[k] ?? 0}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="fg">
        <div>
          <h2 id="fg" className={r.h2}>{t.forget}</h2>
          <p className={r.body}>{t.forgetBody}</p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <table className={r.table}>
            <thead><tr><th scope="col">GSM8K, n = {d.gsm8k.n}</th><th scope="col">Qwen3-1.7B</th><th scope="col">+ LoRA</th></tr></thead>
            <tbody>
              <tr><th scope="row">{t.strict}</th><td className="tnum">{f2(d.gsm8k.base_strict)}</td><td className="tnum">{f2(d.gsm8k.sft_strict)}</td></tr>
              <tr><th scope="row">{t.lenient}</th><td className="tnum">{f2(d.gsm8k.base_last_number)}</td><td className="tnum">{f2(d.gsm8k.sft_last_number)}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="nm">
        <div>
          <h2 id="nm" className={r.h2}>{t.names}</h2>
          <p className={r.body}>{t.namesBody}</p>
        </div>
        <div className={`${r.card} rise`} data-ui>
          <table className={r.table}>
            <thead><tr><th scope="col"></th>{Object.keys(d.names_only).map((lv) => <th key={lv} scope="col">{lv}</th>)}</tr></thead>
            <tbody>
              <tr><th scope="row">{locale === "pt" ? "Só nomes" : "Names only"}</th>{Object.values(d.names_only).map((v, i) => <td key={i} className="tnum">{f2(v.acc)}</td>)}</tr>
              <tr><th scope="row">{locale === "pt" ? "Maioria do treino" : "Training majority"}</th>{Object.values(d.names_only).map((v, i) => <td key={i} className="tnum">{f2(v.majority)}</td>)}</tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className={`${r.sec} wrap`} aria-labelledby="sc">
        <h2 id="sc" className={r.h2}>{t.score}</h2>
        <ul className={r.score}>
          {t.scoreRows.map(([p, v, k]) => (
            <li key={p} data-k={k}><span>{p}</span><b>{v}</b></li>
          ))}
        </ul>
      </section>

      <section className={`${r.sec} ${r.split} wrap`} aria-labelledby="rp">
        <div>
          <h2 id="rp" className={r.h2}>{t.repro}</h2>
          <p className={r.body}>{t.reproBody}</p>
          <p className={r.links}><a href={REPO}>GitHub · Apache-2.0</a> <a href={HF}>Hugging Face</a></p>
        </div>
        <pre className={r.code}>{`git clone ${REPO}\ncd deliverytwin && uv sync\nuv run pytest\nuv run python scripts/run_g3.py --agent playbook \\\n  --levels L0,L1,L2 --n 20 --seed final --tag fix\nuv run python scripts/g5_interventions.py\nuv run python scripts/g5_report.py\nuv run python scripts/site_export.py   # this site's lab data`}</pre>
      </section>
    </article>
  );
}

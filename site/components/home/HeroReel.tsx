"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import type { Scenario, Truth } from "@/lib/types";
import CityMap, { busiestAt, statsAt } from "../CityMap";
import { EffectPlot, LineChart } from "../charts";
import Status from "../ui/Status";
import { familyName } from "@/lib/names";
import { badRate } from "@/lib/series";
import s from "./hero.module.css";

export default function HeroReel({ sc, truth: tr, t, locale }: { sc: Scenario; truth: Truth; t: Dict; locale: Locale }) {
  const stage = useRef<HTMLElement>(null);
  const [step, setStep] = useState(0);
  const [now, setNow] = useState(sc.alert.t - 90);
  const [paused, setPaused] = useState(false);
  const [stacked, setStacked] = useState(false); // small screens: frames are stacked cards, not a pinned reel
  const range = useMemo<[number, number]>(() => [sc.alert.t - 100, sc.alert.t], [sc.alert.t]);
  const focus = useRef<{ token: string; n: number } | null>(null);
  const onTime = useCallback((v: number) => setNow(v), []);
  const promise = sc.telemetry.promise;

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1000px)");
    const on = () => setStacked(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const onScroll = () => {
      const r = el.getBoundingClientRect();
      const total = r.height - window.innerHeight;
      const k = total > 0 ? Math.min(Math.max(-r.top / total, 0), 0.999) : 0;
      setStep(Math.floor(k * 4));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); };
  }, []);

  const agentKey = sc.sessions["qwen-sft"] ? "qwen-sft" : "playbook";
  const sess = sc.sessions[agentKey];
  const res = tr.evaluations[agentKey];
  const lab = sc.lab.A;
  const arm = (k: string) => lab.arms.find((a) => a.key === k)!;
  const pp = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(1)}`;
  const tel = sc.telemetry;
  const br = badRate(tel);
  const st = statsAt(sc.world, now, promise);
  // Follow the restaurant where orders pile up, with hysteresis so the ring does not flicker between ties.
  const top = busiestAt(sc.world, now, promise);
  if (!top || top.n < 3) focus.current = null;
  else if (!focus.current || top.token === focus.current.token || top.n >= focus.current.n + 2) focus.current = { token: top.token, n: top.n };
  const pt = locale === "pt";
  const toAlert = Math.max(0, Math.round(sc.alert.t - now));
  const phase = now >= sc.alert.t - 2 ? 3 : st.late > 0 ? 2 : focus.current ? 1 : 0;
  const story = pt
    ? ["Operação normal: entregadores buscam pedidos nos restaurantes e levam até os clientes.",
       "Os pedidos começam a se acumular num restaurante (anel vermelho).",
       `${st.late} ${st.late === 1 ? "pedido já passou" : "pedidos já passaram"} do prazo de ${promise} min.`,
       "O alerta dispara: a taxa de pedidos atrasados passou do limite."]
    : ["Normal operation: couriers pick up orders at restaurants and take them to customers.",
       "Orders start piling up at one restaurant (red ring).",
       `${st.late} ${st.late === 1 ? "order is" : "orders are"} already past the ${promise}-min promise.`,
       "The alert fires: the late-order rate crossed its threshold."];
  const progress = Math.min(1, Math.max(0, (now - range[0]) / (range[1] - range[0])));
  const truth = tr.reveal.family;
  const sub = res.cause;

  const frames = [
    <div key="map" className={s.frameInner} data-ui>
      <div className={s.frameTop}>
        <Status kind="assumption" locale={locale} label={locale === "pt" ? "Visão do simulador" : "Simulator view"} />
        <button type="button" className={s.pause} onClick={() => setPaused((p) => !p)} aria-pressed={paused}>{paused ? (locale === "pt" ? "Continuar" : "Play") : (locale === "pt" ? "Pausar" : "Pause")}</button>
        <span className="tnum">min {Math.round(now)} · {st.active} {locale === "pt" ? "pedidos ativos" : "active orders"} · <b className={s.lateTxt}>{st.late} {locale === "pt" ? (st.late === 1 ? "atrasado" : "atrasados") : "late"}</b></span>
      </div>
      <p key={phase} className={s.story} data-phase={phase} aria-live="polite">{story[phase]}</p>
      <div className={s.mapBox}>
        <CityMap world={sc.world} promise={promise} autoplay={!paused} t={paused ? now : undefined} range={range} speed={8} onTime={onTime}
          highlight={focus.current?.token} focusLabel={pt ? "pedidos acumulando" : "orders piling up"}
          label={pt ? "Animação da cidade simulada: entregadores e pedidos se movendo até o alerta" : "Animation of the simulated city: couriers and orders moving until the alert"} />
      </div>
      <div className={s.clock} aria-hidden="true">
        <span className={s.track}><span className={s.fill} style={{ transform: `scaleX(${progress})` }} /></span>
        <span className="tnum">{toAlert > 0 ? (pt ? `alerta em ${toAlert} min` : `alert in ${toAlert} min`) : (pt ? "alerta!" : "alert!")}</span>
      </div>
      <ul className={s.legend}>
        <li><i className={s.lgRest} aria-hidden="true" />{pt ? "restaurante" : "restaurant"}</li>
        <li><i className={s.lgHalo} aria-hidden="true" />{pt ? "pedidos esperando" : "orders waiting"}</li>
        <li><i className={s.lgDot} aria-hidden="true" />{pt ? "entregador com pedido" : "courier with an order"}</li>
        <li><i className={s.lgLate} aria-hidden="true" />{pt ? "pedido atrasado" : "late order"}</li>
      </ul>
    </div>,
    <div key="tel" className={s.frameInner} data-ui>
      <div className={s.frameTop}>
        <Status kind="observation" locale={locale} />
        <span>{locale === "pt" ? "Pedidos atrasados ou perdidos, por janela de 15 min" : "Late or failed orders, per 15-min window"}</span>
      </div>
      <LineChart x={br.x} series={[{ id: "bad", label: locale === "pt" ? "Taxa de pedidos ruins" : "Bad-order rate", color: "var(--series-control)", values: br.y }]}
        height={230} yMax={1} markers={[{ x: sc.alert.t, label: locale === "pt" ? "alerta" : "alert" }]} xLabel="min"
        ariaLabel={locale === "pt" ? "Taxa de pedidos ruins observada ao longo do tempo" : "Observed bad-order rate over time"}
        tableCaption={locale === "pt" ? "Ver dados" : "Show data"} />
    </div>,
    <div key="exp" className={s.frameInner} data-ui>
      <div className={s.frameTop}>
        <Status kind="experiment" locale={locale} />
        <span>{lab.replicas} {locale === "pt" ? "futuros pareados · modo A" : "paired futures · mode A"}</span>
      </div>
      <EffectPlot domain={[-0.25, 0.05]} format={pp} zeroLabel="0" betterLabel={locale === "pt" ? "menos atrasos" : "fewer late"}
        ariaLabel={locale === "pt" ? "Efeito pareado de duas intervenções" : "Paired effect of two interventions"}
        rows={[
          { key: "r", label: locale === "pt" ? "Esperar 0,2 min antes de repetir" : "Retry after 0.2 min", mean: arm("retry_backoff_0.2").diff_bad, lo: arm("retry_backoff_0.2").ci_bad[0], hi: arm("retry_backoff_0.2").ci_bad[1], note: locale === "pt" ? "pontos percentuais" : "percentage points" },
          { key: "c", label: locale === "pt" ? "+10 entregadores" : "+10 couriers", mean: arm("add_couriers_10").diff_bad, lo: arm("add_couriers_10").ci_bad[0], hi: arm("add_couriers_10").ci_bad[1] },
          { key: "p", label: "Placebo", mean: arm("placebo").diff_bad, lo: arm("placebo").ci_bad[0], hi: arm("placebo").ci_bad[1], note: locale === "pt" ? "exatamente zero" : "exactly zero" },
        ]} />
    </div>,
    <div key="ver" className={s.frameInner} data-ui>
      <div className={s.frameTop}>
        <Status kind="truth" locale={locale} />
        <span>{locale === "pt" ? "Revelado só depois do envio" : "Revealed only after submission"}</span>
      </div>
      <dl className={s.verdict}>
        <div><dt>{t.how.submitted}</dt><dd>{familyName(sub, locale)}</dd></div>
        <div><dt>{t.how.truth}</dt><dd>{familyName(truth, locale)}</dd></div>
        <div><dt>{t.how.verdict}</dt><dd className={res.exact ? s.ok : s.bad}>{res.exact ? t.how.correct : t.how.wrong}</dd></div>
      </dl>
      <p className={s.small}>{locale === "pt" ? `Agente: ${sess.label}. Incidente ${sc.id.toUpperCase()}, semente pública ${sc.seed}.` : `Agent: ${sess.label}. Incident ${sc.id.toUpperCase()}, public seed ${sc.seed}.`}</p>
    </div>,
  ];

  return (
    <section ref={stage} className={s.stage} aria-labelledby="hero-title">
      <div className={s.sticky}>
        <h1 id="hero-title" className={s.title}>
          <span className={s.a}><Words text={t.hero.a} start={0} /></span>
          <span className={s.gap} aria-hidden="true" />
          <span className={s.b}><Words text={t.hero.b} start={t.hero.a.split(" ").length} /></span>
        </h1>
        <p className="sr-only" aria-live="polite">{t.hero.frames[step]}</p>
        <div className={s.reel}>
          {frames.map((f, i) => (
            <div key={i} className={s.frame} data-pos={stacked ? 0 : i - step}
              aria-hidden={!stacked && i !== step} inert={!stacked && i !== step}>
              <p className={s.caption}>{t.hero.frames[i]}</p>
              {f}
            </div>
          ))}
        </div>
        <div className={s.lead}>
          <p>{t.hero.lead}</p>
          <Link href={`/${locale}/lab`} className="btn btn-primary">{t.hero.cta}</Link>
          <a href="#audit" className={s.business}>{t.hero.business} →</a>
        </div>
        <ol className={s.dots} aria-label={locale === "pt" ? "Etapas" : "Steps"}>
          {frames.map((_, i) => <li key={i} data-on={i === step ? "1" : undefined}><span className="sr-only">{t.hero.frames[i]}</span></li>)}
        </ol>
      </div>
    </section>
  );
}

/** First-load headline entrance: each word rises out of a mask, staggered (reduced motion: fade only). */
function Words({ text, start }: { text: string; start: number }) {
  return (
    <>
      {text.split(" ").map((w, i) => (
        <span key={i}>
          <span className={s.word}><span style={{ animationDelay: `${120 + (start + i) * 70}ms` }}>{w}</span></span>{" "}
        </span>
      ))}
    </>
  );
}

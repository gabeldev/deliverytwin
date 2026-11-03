# Public site: technical and design decisions

Product record: `PRODUCT.md`. Date: 2026-11-02.

## 1. Architecture

| Decision | Choice | Why |
|---|---|---|
| Framework | Next.js 16 (App Router, TypeScript), static generation plus one serverless route | Vercel-native, every page prerendered (fast, cacheable, SEO), one function for the contact form. No server is needed for the demo itself. |
| Where the simulator runs | **Precomputed**, never in the browser or on Vercel | The simulator is Python. Every lab result shown is produced by `scripts/site_export.py` from the real simulator and labelled with seed, replica ids, commit and the reproduce command. This is honest, free to host, instant for visitors, and impossible to abuse. A live mode (Pyodide in the browser or a separate Python service) is a possible extension, listed under pending work. |
| LLM agents | **Recorded sessions only**, labelled "Recorded session, replayed" | The brief forbids pretending a model runs live. Sessions come from real runs on the public development seed (`runs/g3/*_dev_*`). The playbook is deterministic code, re-run at export time. |
| Hidden truth | **Separate file** `<id>.truth.json`, fetched only when the visitor presses "Reveal" | DESIGN_SYSTEM §1.6 ("hidden truth is another route"). The investigation views never receive the injected fault or the evaluator's verdicts. |
| Seeds | Public development seed 2026 only | The evaluation and final seeds are never used for demo scenarios (PRODUCT.md, ADR-0006). |
| Research numbers | `scripts/site_research.py` → `public/data/research.json` | Recomputed from run files or copied from committed report data; nothing typed into the UI. |
| Contact | Next.js route `/api/interest` → **Vercel Blob, private access** | Owner's choice. No public email address, no third-party form service, consent required, honeypot, size limit, per-instance rate limit. |
| i18n | `/en` and `/pt` static routes, typed dictionaries | Owner's choice: English default with Portuguese. Tool transcripts stay verbatim in English. |
| Charts | Hand-built SVG (d3-scale, d3-shape) | Small, accessible (title, legend, table view), width-measured so text never scales; follows the dataviz skill. |
| Motion | CSS transitions, one scroll-linked reel and staggered section entrances; no animation library | Transform and opacity only, so it stays cheap; `prefers-reduced-motion` keeps the content and drops the travel. |

## 2. Design

- **Direction:** "The product performs" (taste-skill draw, seed 2103533034): white ground, near-black ink, mint accent only on primary actions and one tile, Hanken Grotesk. The page's imagery is the product's own interface, built in HTML with real data (`data-ui` fragments): city map, telemetry, paired-experiment plots, verdicts.
- **Idea:** the **fork**. One simulated city is replayed into two futures that are identical until the decision. The hero reel walks one incident from alert to verdict, and the home page's live element lets a visitor ask a what-if question in plain words and get the simulator's paired answer.
- **Epistemic status first:** the project's DESIGN_SYSTEM status chips (observed, hypothesis, assumption, experiment, recommendation, hidden truth: colour + icon + label) mark every fragment. The simulated-environment banner is fixed at the top of every page.
- **Palette for data:** validated with the dataviz skill's script (`validate_palette.js`): zones and control/treatment use the reference categorical slots (blue, orange, aqua; CVD ΔE ≥ 9.2). Lateness uses the reference "critical" red, always with a label. The first proposal failed the CVD check and was replaced.
- **Pictures:** no photographs. A delivery photo would suggest a real company or real couriers, which the brief and the project forbid. The taste inspector's "no real pictures" warning is accepted for this reason.
- **Known conflicts and how they were settled:** the taste skill bans small uppercase labels and violet; the project's design system requires uppercase status chips and a violet hypothesis colour. The brief makes the design system binding, so the chips keep their colours and are set at 13px instead of 11–12px.

## 3. Data flow

```
deliverytwin (Python) ── scripts/site_export.py ──> site/public/data/scenarios/<id>.json        (world, telemetry, sessions, lab A/B)
                                                └─> site/public/data/scenarios/<id>.truth.json  (hidden fault + evaluator verdicts)
docs/reports + runs ─── scripts/site_research.py ─> site/public/data/research.json
```

Rebuild the data after any change to the simulator, agents or reports, then rebuild the site.

## 4. Pending and possible extensions

- **Shared rate limit for the contact form.** The current limit is per serverless instance; a shared limiter needs a KV store (Upstash/Vercel KV). Mitigations today: 4 KB streamed body cap, honeypot, consent required, private storage (Codex site review #3).
- Done 2026-11-03: arrow-key navigation in the radio groups (`components/ui/radio.ts`, review #17) and a first-party Content-Security-Policy in `next.config.ts` (review #20; `'unsafe-inline'` remains for Next.js inline scripts and styles, a nonce-based policy would remove it).
- Done 2026-11-03: small-screen menu with an always-visible language switch that keeps the current page; the hero becomes stacked cards on small screens (no pinned scrolling) and narrates the map (legend, focus ring on the busiest restaurant, synchronised captions, time-to-alert bar).
- English version of the sample Decision Audit report (the report generator is Portuguese-only today).

- Live counterfactual runs (Pyodide or a small Python service) for arbitrary intervention values; today values snap to the precomputed grid and the snap is shown.
- More scenarios (L4–L6 and L3) in the lab; today five L0/L2 incidents with recorded sessions for every agent.
- A dark theme (the design system defines dark tokens; the site ships light only).

# PRD — Tyre Debt

*Causal Attribution & Counterfactual Coaching for Tyre Life*
TrackShift 2026 · Team Rocket

> **USP:** Tyre Debt doesn't predict when your tyres will die. It tells you who's killing them, lap by lap, and what to change right now to stop.

> **v3 note:** supersedes the earlier prior-art claim. A prior draft stated no public work does explainable/counterfactual tyre modeling — checked against real literature and found overstated. Section 2/3 below hold the corrected, narrower, defensible claim. Do not repeat the old novelty line.

## 1. Overview

Tyre Debt is a causal attribution and coaching system for tyre degradation. It does **not** forecast when a tyre falls off a cliff. It explains, lap by lap, why a specific driver's tyre is degrading faster or slower than a physics-informed baseline, attributes that deviation to specific driving decisions (braking aggression, throttle transients, lateral dynamics, kerb usage), and outputs a quantified, reversible action: what to change, and how many laps of tyre life that change recovers.

Built for TrackShift 2026's "AI Motorsport Intelligence" theme, under the problem statement "Tyre Degradation Intelligence."

## 2. Competitive Landscape (researched, not assumed)

Literature/product search covering 2022–2026. Every claim below is checkable.

### 2.1 Academic work

| Work | What it does | What it doesn't do |
|---|---|---|
| Todd, Jiang, Russo, Winkler, Sale, McMillan, Rago — "Explainable Time Series Prediction of Tyre Energy in F1 Race Strategy," Imperial College London × Mercedes-AMG PETRONAS, ACM SAC 2025 (arXiv:2501.04067) | Forecasts instantaneous tyre energy via deep learning/XGBoost on proprietary Mercedes telemetry (2020–2023). Uses feature importance (TIME) + counterfactual explanations (CausalImpact). | CausalImpact evaluates discrete external events only (e.g. "did the VSC matter") — structurally cannot attribute to a continuous, driver-controlled variable like braking aggression. Proprietary data, not reproducible. Authors state their method is "currently limited to post-race analysis." No output converts to an actionable quantity a driver would act on. |
| Cappello & Hoegh — "A State-Space Approach to Modeling Tire Degradation in F1 Racing," Montana State University (arXiv:2512.00640, Nov 2025) | Kalman-filter/state-space degradation model on public FastF1 data, benchmarked vs ARIMA(2,1,2). | Pure forecasting improvement. No explainability, no attribution, no counterfactual layer. |
| "Pitwall: Faithful Natural-Language Race-Strategy Briefings from a Calibrated Real-Time Monte Carlo Engine" (arXiv:2607.06495, Jul 2026) | Deconfounds tyre wear from fuel burn-off and track evolution in the same lap-time decomposition this project uses; generates NL strategy briefings via Monte Carlo simulation. | Briefings are about pit/strategy decisions, not individual driving behavior. No behavioral attribution, no per-driver coaching output. |

### 2.2 Existing tools and products

- **tracinginsights / F1-analysis** (public HuggingFace Space, open Streamlit source): already ships fuel-corrected, LOWESS-smoothed degradation curves from public FastF1 data, free, live, today. This directly commoditizes what this project calls its "baseline model" (Section 7.1). It never ingests braking/throttle/position telemetry — describes that a curve is worse, never why.
- **AWS F1 Insights / Battle Forecast:** live overtake and strategy probability graphics, broadcast since 2019. Prediction-only, no attribution, no counterfactual, not tyre-degradation-specific.
- **Sim-racing coaching tools** (Trophi.ai, VRS, Track Titan, MoTeC i2): real-time, per-corner feedback vs a reference lap. Optimize lap-time delta only — none account for what a driving change costs in tyre life. Can hand advice that's faster this lap and costs two laps of tyre life later, with no way to know it.
- **Industry-standard linear degradation models:** manually calculated, don't incorporate covariate data — confirmed as the stated industry baseline in the Todd et al. paper itself.

## 3. The Corrected Novelty Claim

> Nobody public converts a driver-controllable behavior into a causally-attributed, cumulative tyre-life cost, expressed as a quantified number of recoverable laps, built entirely on public data, intended for in-race use.

Every clause is load-bearing:

- **"Causally attributed to controllable driving behavior"** — Todd et al.'s CausalImpact method is structurally limited to discrete external events, not continuous driver-controlled variables. A mathematical ceiling of their method, not a scoping choice.
- **"Cumulative debt/credit ledger, in laps"** — not found in any reviewed academic work or public tool. Todd et al. output a causal-effect probability; Cappello & Hoegh output a curve with confidence bands; Pitwall outputs a strategy sentence; none output a laps-of-life number.
- **"Public data only"** — Todd et al. is proprietary Mercedes telemetry, not reproducible by anyone else. This project is not.
- **"In-race intent"** — Todd et al. states their method is post-race only. This project's architecture is built specifically to support a live path.

This is deliberately narrower than earlier drafts — it's the claim that survives a technical judge who has read the same papers.

## 4. Goals

- **Primary:** compute a running "tyre debt/credit" ledger per stint — cumulative deviation between actual and physics-baseline degradation, lap by lap.
- **Attribution:** decompose accumulated debt into named driving-behavior categories, explainable by construction (see Architecture — Model Family Decision), not a black-box score.
- **Counterfactual:** for any attributed cause, quantify recoverable tyre life in laps, computed live — not merely precomputed for a fixed set of scenarios.
- **Credibility:** report one real, measured holdout accuracy number before submission (not only a target), and validate attribution against publicly known driver reputations — directly answering the trust/faithfulness gap Todd et al. name as unsolved.
- **Latency (stated precisely):** the interactive counterfactual query — the one a judge will click live — targets sub-200ms measured latency, not a vague "real-time" claim.

## 5. Non-Goals

- No full tyre thermal/compound physics simulation — Stage 1 is a data-driven baseline, not a physics engine, and is explicitly not claimed as novel.
- No race-long fuel/energy strategy modeling.
- No vehicle control or actuation — strictly a recommendation/analysis tool.
- No proprietary team telemetry — built entirely on public FastF1/OpenF1/Ergast data.
- No driver "tyre management signature" transfer prediction in MVP — stretch goal only.
- No per-100ms live coaching during a corner — the latency target is for interactive-query cadence, not a continuous 10Hz control loop.

## 6. Target Users

| User | Need |
|---|---|
| Race engineer, junior series (primary) | F2/F3/FE engineers without AWS-grade infrastructure — actionable, in-race tyre coaching. |
| Broadcast / fan engagement (secondary) | Proven, already-monetized market for degradation-aware storytelling, extended with causal explainability. |
| Hackathon judges | Evidence of a precisely-scoped, honestly-compared gap, verified feasibility on public data, and a live demo that survives an unscripted question, incl. "isn't this what Mercedes already published." |

## 7. Core Features (MVP)

### 7.1 Baseline degradation model — explicitly not the novel part
- Physics-informed regression: expected lap-time-loss vs. compound, tyre age, estimated fuel load, track, track evolution.
- Trained on 3–4 seasons of FastF1 data, green-flag laps only. Credit existing open work (tracinginsights) rather than presenting this as a contribution.

### 7.2 Residual ledger
- Actual minus baseline, lap by lap. Positive = debt. Negative = credit. Locked colors: debt `#E10600`, credit `#00B450`.

### 7.3 Attribution model — the actual differentiator
- Per-lap behavioral features: braking aggression (derived), throttle transient smoothness, lateral dynamics proxy (estimated), kerb usage, lock-up flags.
- Explainable-by-construction model (linear/GAM) — not a post-hoc explainer bolted onto a black box.

### 7.4 Counterfactual layer — computed live
- Perturb an attributed feature, recompute projected debt using the model's own coefficients (not a perturb-and-rerun SHAP loop), convert the change into laps of tyre life recovered.
- Example must be reproducible live from the actual endpoint, not printed as static copy: *"Reduce Turn 4 braking aggression by 15% → recover 1.8 laps of tyre life."*

### 7.5 Single-stint visualization
- Running debt/credit chart, one-sentence attribution summary, one-sentence counterfactual. Deliberately minimal.

## 8. Validation Methodology

- **Quantitative:** held-out R²/correlation on unseen stints, reported as a real measured number before submission. Status as of writing: target ~0.85, not yet measured — stated honestly.
- **Attribution sanity check** (answers a named open problem): across multiple races, model should consistently flag known aggressive drivers as higher-debt and known tyre-management specialists as higher-credit. Directly addresses trust/faithfulness gap Todd et al. name as unaddressed future work — state this connection explicitly when presenting validation.
- **Live latency validation:** p95 measured latency for the counterfactual endpoint, reported with hardware and sample size (e.g. "p95 34ms, N=500, [hardware]"), not a target.
- **Narrative anchors:** 2–3 press-documented stints, illustrative only, never a substitute for the quantitative holdout.

## 9. Constraints, Stated Honestly

- Zero dependency on ERS/energy deployment fields (unresolved for 2026 regs) — avoided by design.
- Fuel load estimated from lap number and burn-rate approximation — stated as a modeling assumption.
- All visual assets are native vector graphics or in-house generated charts — no scraped/hotlinked photography (learned the expensive way across two broken pitch-deck builds).
- Attribution/counterfactual model is deliberately linear/GAM, not a more "impressive-sounding" deep model — a considered tradeoff (explainability + latency both improve), not a limitation to hide.

## 10. Real-World Application

Degradation-informed strategy tooling already has a proven commercial market (sim-racing coaching, broadcast graphics), de-risking the adoption argument. Tyre Debt's wedge: the underserved segment — junior series without AWS-grade infrastructure — and a currency (tyre-life laps, not lap-time deltas) no existing coaching tool accounts for. The architecture generalizes to any domain with a controllable input causing measurable wear against a physics-informed expectation — stated as a one-line bonus claim, not a demonstrated capability unless a working cross-domain example actually exists.

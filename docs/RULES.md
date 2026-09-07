# Rules — Tyre Debt

Non-negotiable constraints distilled from PRD v3 / TRD v3. Any code, copy, or artifact that violates one of these is wrong by construction, not a style nitpick.

## Modeling rules

1. **Stage 3/4 (live path) must be linear/GAM (e.g. EBM), never a black-box model with a post-hoc explainer.** SHAP-on-GBDT is banned for anything on the live/interactive path.
2. **Stage 1 (offline baseline) may use GBDT + SHAP.** It has no live latency requirement. Do not let this offline choice bleed into Stage 3/4.
3. Attribution must be computed as `coefficient × feature value` — no perturbation loop, no re-inference per request.
4. Counterfactuals must be computed live from the model's own trained coefficients — never a "perturb-and-rerun" loop, never precomputed for only a fixed set of scenarios.
5. Model artifacts (coefficients/shape functions) load into memory once at process start. No per-request deserialization or disk reads on the request path.

## Latency rules

6. "Real-time" must never be used unqualified. Always attach one of the three defined meanings:
   - Per-lap update: <1s
   - Interactive demo query (counterfactual endpoint): **<200ms measured, p95** — this is the target for the project
   - Continuous in-corner coaching (10Hz): explicitly out of MVP scope
7. Latency numbers reported in any artifact (pitch, PRD, report, demo) must be **measured**, with hardware and sample size stated (e.g. "p95 34ms, N=500, [hardware]") — never a stated target passed off as a result.
8. If client-side computation is used for the slider interaction, this must be stated explicitly in the architecture — not obscured as if it were a server round-trip.

## Data & claims rules

9. Public data only — FastF1/OpenF1/Ergast. No proprietary team telemetry claimed, ever.
10. No ERS/energy deployment fields (unresolved for 2026 regs).
11. Fuel load is an estimate from lap number + burn-rate approximation — always stated as a modeling assumption, never presented as measured. Any copy describing behavioral features like braking aggression or lateral dynamics proxy must say "derived" or "estimated," never implying a raw sensor reading.
12. The novelty claim used anywhere (pitch, README, demo narration) must be the **Section 3 corrected claim** from the PRD, verbatim in spirit:
    > Nobody public converts a driver-controllable behavior into a causally-attributed, cumulative tyre-life cost, expressed as a quantified number of recoverable laps, built entirely on public data, intended for in-race use.
    Do not revert to the earlier, broader "no public work does explainable/counterfactual tyre modeling" claim — it was checked and found overstated.
13. Stage 1 (baseline degradation model) must never be presented as the novel contribution. Credit tracinginsights/F1-analysis as comparable prior art.
14. Any held-out accuracy (R²/correlation) reported before submission must be a real measured number, not the ~0.85 target.

## Visual asset rules

15. **No hotlinked or scraped photography anywhere** — product UI or any submission artifact. This has broken two prior pitch decks (load failures / unlicensed rival-team press photos).
16. All charts must be generated from real data by the project's own pipeline. No hand-drawn placeholders, no stock imagery.
17. Locked color tokens — do not deviate:
    - Debt / alert red: `#E10600`
    - Credit / positive green: `#00B450`
    - Background: `#15151E`
18. Demo fallback responses (if the live call fails) must be genuine cached pipeline output — never a hand-written placeholder value.

## Scope rules

19. No full tyre thermal/compound physics simulation.
20. No race-long fuel/energy strategy modeling.
21. No vehicle control or actuation — recommendation/analysis tool only.
22. No driver "tyre management signature" transfer in MVP — stretch goal only, and only if time remains after the core roadmap.
23. Cross-domain generalization (beyond tyres) is a one-line bonus claim only — never presented as a demonstrated capability unless an actual working example exists.

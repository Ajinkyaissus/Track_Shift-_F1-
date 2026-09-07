# Build Roadmap / Phases — Tyre Debt

Ordered so that each phase produces a real, checkable artifact before the next begins. Don't skip ahead — Stage 3 depends on Stage 2's residuals being correct, and Stage 4's latency number is meaningless without Stage 3's coefficients being sane first.

## Phase 0 — Data Foundation
- Pull 3–4 seasons of data via FastF1's local cache.
- **Gate:** confirm braking, throttle, X/Y position, and tyre compound/age fields are populated before anything downstream is built.

## Phase 1 — Feature Engineering
- Per-lap: braking aggression (derived), throttle transient smoothness, lateral dynamics proxy (estimated), kerb usage, lock-up flags.
- Fuel load estimated from lap number and burn-rate.
- Filter to green-flag laps only.

## Phase 2 — Stage 1: Baseline Degradation Model
- Physics-informed regression: expected lap-time-loss vs. compound, tyre age, estimated fuel load, track, track evolution.
- GBDT acceptable here (offline only, no live latency requirement).
- **Gate:** real held-out R²/correlation number, reported honestly. Not presented as the novel contribution — credit tracinginsights as comparable prior art.

## Phase 3 — Stage 2: Residual Ledger
- Actual minus baseline, lap by lap.
- Precomputed table, never recomputed per request.
- Locked colors applied: debt `#E10600`, credit `#00B450`.

## Phase 4 — Stage 3: Attribution Model (core IP)
- Train linear/GAM (EBM) attribution model offline against the behavioral features.
- **Gate:** confirm coefficients are sane (sign/magnitude match domain intuition, e.g. more braking aggression → more debt) before building the live endpoint around them.
- This is the actual differentiator — do not rush this gate to get to a demo faster.

## Phase 5 — Stage 4: Counterfactual Endpoint (live path)
- Build the live endpoint: `{feature, delta_pct}` → projected recovered laps, via coefficient lookup + arithmetic.
- Load model into memory once at process start.
- **Gate:** measure p95 latency immediately — don't wait until the end to discover it's slow. Target <200ms measured.

## Phase 6 — Single-Stint Visualization
- Debt/credit line chart (Recharts), one-sentence attribution summary, one-sentence live counterfactual.
- Native charts only — no fetched imagery.

## Phase 7 — Validation Pass
- Held-out R²/correlation finalized and reported with method.
- Attribution sanity check across multiple races: known aggressive drivers → higher debt; known tyre-management specialists → higher credit. Frame explicitly as answering Todd et al.'s named trust/faithfulness gap.
- p95 latency reported with hardware + sample size (e.g. "p95 34ms, N=500, [hardware]").
- 2–3 narrative/press-documented stints assembled as illustrative anchors only.

## Phase 8 — Demo Hardening
- Cache real precomputed responses as fallback for the live call.
- WebSocket push wired up for any live ledger update (perceived responsiveness).
- Rehearse the "isn't this what Mercedes already published" question using the Section 3 corrected novelty claim.

## Stretch (only if time remains)
- Driver tyre-management signature transfer.

## Status flags to track per phase
- 🔴 Not started / blocked
- 🟠 In progress, gate not yet met
- 🟡 Gate met, needs validation/writeup
- 🟢 Done, measured, documented

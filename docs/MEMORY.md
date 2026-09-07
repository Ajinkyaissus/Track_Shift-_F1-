# Project Memory — Tyre Debt

Running log of decisions, corrections, and why they were made. Purpose: prevent regressing to earlier (wrong) versions of a claim or design choice.

## v3 changes and why

- **Model family for Stage 3/4 changed from SHAP-attributed GBDT → linear/GAM (EBM).**
  Reason: KernelSHAP is exponential; even TreeSHAP re-runs a tree-traversal explanation per call. Every counterfactual query would recompute an explanation from scratch — a self-inflicted latency problem. Fix is not optimizing that computation, it's not needing it. This single decision resolves both the explainability requirement and the <200ms latency target at once, rather than trading one against the other.
  GBDT + SHAP is still fine for Stage 1 (offline baseline) — no live latency requirement there. Do not let that choice bleed into Stage 3/4 again.

- **Novelty claim narrowed.**
  Earlier draft claimed "no public work does explainable/counterfactual tyre modeling." Checked against real literature (Todd et al. ACM SAC 2025, Cappello & Hoegh, Pitwall, tracinginsights) and found overstated. Corrected claim (PRD Section 3) is narrower and specifically defensible: causal attribution to *continuous, driver-controllable* behavior, output as a *cumulative laps-of-life number*, on *public data*, for *in-race* use. Each clause defends against one specific piece of prior art. Do not revert to the broad claim.

- **"Real-time" was ambiguous across earlier drafts, including a sub-millisecond claim.**
  Corrected by defining three distinct cadences (per-lap update <1s, interactive query <200ms measured — the actual target, and 10Hz in-corner coaching — explicitly out of scope). Every artifact must state which of the three it means; never use "real-time" bare again.

- **Visual asset policy locked after two broken pitch decks.**
  Both failures were externally fetched images: one failed to load, one turned out to be unlicensed press photography of a rival F1 team. Policy since: no hotlinked/scraped photography anywhere, ever — native SVG / in-app generated charts only.

## Standing decisions (carry forward, don't re-litigate)

- Public data only: FastF1/OpenF1/Ergast. No proprietary telemetry claimed.
- Locked color tokens: debt `#E10600`, credit `#00B450`, background `#15151E`.
- Stage 1 baseline explicitly not claimed as novel; credit tracinginsights.
- Any accuracy/latency figure presented must be a real measurement (with hardware/sample size for latency), never a target passed off as a result.
- Fuel load is an estimated modeling assumption (lap number + burn-rate), always stated as such.
- Cross-domain generalization is a one-line bonus claim only, not a demonstrated capability, unless an actual working example exists.
- Stretch goal (driver tyre-management signature transfer) only attempted if time remains after the full core roadmap.

## Known open items (not yet resolved as of v3)

- Held-out R²/correlation: target ~0.85, not yet measured.
- p95 latency for counterfactual endpoint: Real latency test implemented in `tests/test_latency.py` via HTTP client and subprocess (N=500). Actual p95 value pending successful multi-season pipeline execution (currently blocked by FastF1 API rate limits).
- Attribution sanity check against known driver reputations: not yet run across multiple races.
- Whether client-side computation will be used for the slider interaction (vs. live server call) — undecided; if chosen, must be stated explicitly in the architecture, not hidden.

## Reviewer question to always be ready for

"Isn't this what Mercedes already published?" — Answer via the Section 3 corrected novelty claim: Todd et al.'s CausalImpact is structurally limited to discrete external events, is on proprietary data, and is explicitly post-race only. This project attributes to continuous driver-controlled behavior, on public data, live, output as a laps-of-life number — none of which Todd et al. do.

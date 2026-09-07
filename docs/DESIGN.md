# Design — Tyre Debt

## Visual identity

Locked tokens (non-negotiable, see Rules #17):

| Token | Hex | Use |
|---|---|---|
| Debt / alert | `#E10600` | Positive ledger deviation (tyre degrading faster than baseline), warnings |
| Credit / positive | `#00B450` | Negative ledger deviation (tyre degrading slower than baseline) |
| Background | `#15151E` | App shell background — dark, motorsport-broadcast feel |

All charts and visual assets are native SVG / in-app generated only. No hotlinked, scraped, or stock photography anywhere in the product or submission artifacts (two prior pitch decks broke this way — see Rules #15).

## Screens / surfaces (MVP)

1. **Stint selector** — choose race/session → stint (driver + compound shown).
2. **Debt/credit ledger** — cumulative running line chart over the stint, colored by sign using the locked tokens (Recharts).
3. **Attribution panel** — per-behavior % contribution to accumulated debt (braking aggression (derived), throttle transient smoothness, lateral dynamics proxy (estimated), kerb usage, lock-up flags), shown with model coefficients — not a black-box importance score.
4. **Counterfactual interaction** — slider/input per behavior; on change, live call (or client-side computation, if coefficients are shipped to frontend) returns recovered laps. Example target phrasing: *"Reduce Turn 4 braking aggression by 15% → recover 1.8 laps of tyre life."*

## Interaction principles

- **Deliberately minimal.** Single-stint view: chart + one-sentence attribution summary + one-sentence counterfactual. Resist adding more panels for the MVP demo.
- **Every counterfactual must be live and reproducible from the actual endpoint** — never printed as static/canned copy in the UI or the pitch deck.
- **Perceived responsiveness matters as much as raw compute time** to a judge — use WebSocket push for any genuinely live ledger update rather than polling; consider client-side slider computation if the coefficients are simple enough (state this choice explicitly, don't hide it).
- **State the latency meaning being shown.** If a number appears on screen (e.g. "34ms"), it must be labeled with which of the three latency cadences it refers to (see Architecture Section 3) — never a bare "real-time" badge.

## Copy / narrative principles

- Lead with the USP: *"Tyre Debt doesn't predict when your tyres will die. It tells you who's killing them, lap by lap, and what to change right now to stop."*
- Novelty claim on any slide must match the PRD Section 3 corrected claim — narrow and defensible, not the earlier broad "nobody does this" line.
- Any accuracy or latency number shown must be a real measurement with method noted (sample size, hardware), not a target dressed up as a result.
- When positioning against prior art (Todd et al., Cappello & Hoegh, Pitwall, tracinginsights, AWS F1 Insights, sim-racing coaching tools), name the specific structural limitation each one has — not a vague "existing tools are worse."

## Accessibility / trust cues

- Debt/credit color choice is also a semantic signal (red = cost, green = benefit) — keep it consistent everywhere (chart, attribution panel, counterfactual result) so a judge can read the ledger without reading labels.
- Show the model coefficient alongside every attribution line so the interface itself demonstrates the "explainable by construction" claim (e.g. "each 1% more braking aggression costs 0.12s of debt").

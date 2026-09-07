# UI/UX Brief — Tyre Debt

Expands DESIGN.md into build-ready detail. DESIGN.md tokens/principles are inherited,
not restated in full — read that first. This adds: typography/spacing scale, component
inventory, screen-by-screen layout, copy for every state, accessibility specifics.

## 1. Visual system

### Color (locked, RULES.md #17 — do not deviate)
| Token | Hex | Use |
|---|---|---|
| `--debt` | `#E10600` | Positive residual, warnings, "cost" framing |
| `--credit` | `#00B450` | Negative residual, "benefit" framing |
| `--bg` | `#15151E` | App shell background |
| `--bg-elevated` | `#1E1E2A` | Cards/panels above base background (new — needed for panel separation, not in DESIGN.md, does not conflict with locked tokens) |
| `--text-primary` | `#F5F5F7` | Primary text on dark bg |
| `--text-secondary` | `#9A9AA5` | Labels, metadata, timestamps |
| `--border` | `#2A2A38` | Panel dividers |

No other colors. No gradients standing in for the debt/credit signal — the red/green
distinction is the product's core trust cue (DESIGN.md §Accessibility) and must not be
diluted by decorative color elsewhere.

### Typography
- One typeface family, system stack (`-apple-system, Segoe UI, Roboto, sans-serif`) —
  no webfont fetch, consistent with the no-external-asset rule's spirit (RULES.md #15
  is photography-specific, but a failed font CDN is the same failure class that broke
  two prior decks — don't risk it).
- Scale: 32/24/18/15/13px for display/h1/h2/body/caption. Numbers in the ledger and
  counterfactual result use tabular figures (`font-variant-numeric: tabular-nums`) so
  digits don't jitter as values update live.

### Spacing
8px base unit. Panel padding 24px. Component gap 16px. Don't introduce a second scale.

## 2. Component inventory

| Component | Used in | Key states |
|---|---|---|
| `RaceList` | S1 | loading (skeleton rows), empty, loaded |
| `StintList` | S1 | loading, empty (with reason copy), loaded |
| `DebtCreditChart` | S2 | loading (skeleton line), loaded, error-inline |
| `AttributionPanel` | S2 | loading (skeleton rows), loaded, error-inline |
| `CounterfactualSlider` | S2 | idle, dragging, pending (debounced/in-flight), resolved, error |
| `LatencyBadge` | S2 (attached to CounterfactualSlider result) | always shows cadence label + ms, per RULES.md #6 |
| `DataSourceTag` | S2 | `live`, `cached`, `offline-demo` — see APP_FLOW.md §4 |
| `OfflineBanner` | global overlay | hidden, visible |

Nothing here is optional polish — every state above must exist before Phase 6 is
considered done per PHASE.md.

## 3. Screen-by-screen

### S1 — Stint Selector
```
┌─────────────────────────────────────────┐
│  TYRE DEBT                     [status] │  ← app header, DataSourceTag lives here
├─────────────────────────────────────────┤
│  Race                                    │
│  ┌───────────────────────────────────┐  │
│  │ 2024 Monza                    ›    │  │  ← RaceList, one row per race
│  │ 2024 Suzuka                   ›    │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Stint (shown after race selected)       │
│  ┌───────────────────────────────────┐  │
│  │ VER · MEDIUM · Laps 1–22      ›    │  │  ← StintList
│  │ HAM · SOFT   · Laps 1–14      ›    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```
Single column, list-driven, no map/grid — matches the "minimal" mandate and keeps this
screen legible if demoed on a laptop with a projector at low resolution.

### S2 — Stint Detail
```
┌─────────────────────────────────────────┐
│  ‹ VER · MEDIUM · Monza R      [status]  │
├─────────────────────────────────────────┤
│  Debt / Credit Ledger                    │
│  ┌───────────────────────────────────┐  │
│  │        [line chart, red/green]     │  │  ← DebtCreditChart
│  └───────────────────────────────────┘  │
│  "Verstappen is running 1.8s of debt     │  ← one-sentence attribution summary
│   by lap 18, mostly from Turn 4 braking."│    (auto-generated from top attribution row)
├─────────────────────────────────────────┤
│  Attribution                             │
│  Braking aggression      42%  (0.12/1%)  │  ← AttributionPanel, coefficient shown
│  Kerb usage               21%  (0.08/1%) │    inline per feature (DESIGN.md requirement)
│  ...                                     │
├─────────────────────────────────────────┤
│  Counterfactual                          │
│  Braking aggression   ──●────  -15%      │  ← CounterfactualSlider
│  "Reduce Turn 4 braking aggression by    │
│   15% → recover 1.8 laps of tyre life."  │
│  [live · 34ms]                           │  ← LatencyBadge, cadence-labeled
└─────────────────────────────────────────┘
```
Everything above the fold on a standard laptop screen at demo distance — this is the
screen a judge actually watches, so nothing critical scrolls below the fold.

## 4. Copy — every state gets real copy, never a placeholder

| State | Copy |
|---|---|
| S1 empty stints | "No usable stints in this session (red-flagged or fully wet-affected)." |
| S2 partial failure (attribution failed, ledger ok) | "Attribution unavailable right now — showing the debt/credit ledger only." + inline retry |
| Counterfactual pending | dim previous value, no spinner text — the dimming *is* the loading state |
| Counterfactual error, cache fallback | "cached · last computed 14:02" next to the number |
| Offline banner | "Running offline demo dataset — live endpoint unreachable." |
| Novelty/claim copy anywhere in-app (about page, tooltip) | must match PRD.md §3 verbatim in spirit — narrow claim only, never the earlier broad one (RULES.md #12) |
| Any causal-sounding copy | use "attributed to" / "associated with," not "caused by," unless MASTER_PROMPT gap-fix #3's lag structure is implemented — see MASTER_PROMPT.md |

## 5. Accessibility

- Debt/credit is color **and** sign (+/−) **and** label — never color alone. A
  colorblind judge must be able to read the ledger from the numbers.
- All latency/data-source badges are text, not icon-only — DESIGN.md's "state the
  meaning being shown" applies to screen readers too, not just sighted users.
- Slider is keyboard-operable (arrow keys ±1%), not drag-only — a judge may be
  handed a laptop with a trackpad they're unfamiliar with; don't make the demo's
  key interaction fragile to input device.
- Minimum contrast: `--text-primary` on `--bg` and `--bg-elevated` both meet WCAG AA
  at body size — verify once, don't assume dark-theme defaults pass.

## 6. Responsive / device assumption

Primary target: **one laptop screen, ~1440×900, demo/projector context.** Not a
public multi-device product (PRD.md Non-Goals scope). Do not spend build time on
mobile breakpoints — spend it on Phase 4/5 (the actual differentiator) instead. If
time remains after the full roadmap, a basic tablet breakpoint is acceptable, laptop
is not optional and mobile is not in scope at all.

## 7. Motion

Minimal. Chart line draws in on load (400ms ease-out), counterfactual number
transitions via a brief count-up (200ms) so a changed value is noticeably different
from a stale one — this is functional (communicates "this just updated"), not
decorative. No motion elsewhere; a hackathon demo bought down by janky animation on
a borrowed laptop is a worse outcome than a static screen.

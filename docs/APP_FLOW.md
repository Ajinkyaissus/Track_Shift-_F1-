# App Flow — Tyre Debt

Ties to: DESIGN.md (screens/tokens), ARCHITECTURE.md (API layer), RULES.md (latency
labeling, offline fallback), MASTER_PROMPT.md gap-fixes #4, #5, #7.

## 0. Screen inventory

| # | Screen | Purpose |
|---|---|---|
| S1 | Stint Selector | Pick race/session → stint (driver + compound) |
| S2 | Stint Detail | Ledger chart + attribution panel + counterfactual interaction (single view, not tabs — DESIGN.md "deliberately minimal") |
| — | Offline Banner | Persistent overlay state, not a separate screen — see §4 |

There is no third screen. DESIGN.md explicitly resists adding panels; the flow below
stays two-deep on purpose. If a future screen is proposed, it needs a RULES.md
amendment first, not a silent addition.

## 1. Primary flow (happy path)

```
App launch
  └─ GET /races
       → render race list (S1, step A)
User selects race
  └─ GET /sessions/{race_id}/stints        [reuses /sessions/{id}/stints; race→session
                                             resolved client-side or via race→session
                                             lookup — see BACKEND_SCHEMA.md §races/sessions]
       → render stint list (S1, step B): driver, compound, lap range
User selects stint
  └─ GET /stints/{id}/ledger
  └─ GET /stints/{id}/attribution           [fired in parallel, not sequential — both
                                             needed for first paint of S2]
       → render S2: debt/credit line chart + attribution panel with coefficients
User drags a counterfactual slider (e.g. "Turn 4 braking aggression –15%")
  └─ debounce 150ms
  └─ POST /stints/{id}/counterfactual  {feature, delta_pct}
       → render one-sentence result: "Reduce Turn 4 braking aggression by 15% →
         recover 1.8 laps of tyre life."
       → latency badge shows measured round-trip, labeled per RULES.md #6
         ("interactive query, <200ms target")
```

Parallelizing ledger + attribution on stint select is a deliberate latency choice —
serializing them would double perceived load time for no reason, since neither
depends on the other's response.

## 2. State machine per screen

### S1 — Stint Selector
- `loading` → skeleton list, no spinner-only screens (skeleton communicates shape,
  reduces perceived wait — ties to DESIGN.md "perceived responsiveness" principle)
- `empty` → no stints for this session (e.g. red-flagged race) → explicit copy, not
  a blank list: "No usable stints in this session (red-flagged or all wet-affected)."
- `error` → `/races` or `/stints` call fails → fall back per §4, do not show a raw
  error screen to a judge
- `loaded` → normal list

### S2 — Stint Detail
- `loading` → chart area shows skeleton line, attribution panel shows skeleton rows
  (both resolve independently — don't block one on the other)
- `partial` → one of ledger/attribution returned, the other failed → render what
  succeeded, show inline retry on the failed panel only, never blank the whole screen
  for one failed call
- `error` (both failed, or stint data missing) → fall back per §4
- `loaded` → chart + attribution rendered; counterfactual controls active
- `counterfactual-pending` → slider moved, debounce running or request in flight →
  disable the result sentence's old value visually (dim, not blank) until new value
  resolves, so the UI never shows a stale number as if it were current
- `counterfactual-error` → live call failed → show cached/last-known value labeled
  "last computed" (never silently show nothing), per RULES.md #18 (fallback must be
  genuine pipeline output, never hand-written)

## 3. Counterfactual interaction detail

1. User drags slider for one behavioral feature.
2. Debounce 150ms after last drag event (avoid firing a request per pixel).
3. If client-side compute is enabled (MASTER_PROMPT gap-fix #4: only if Phase 5 p95
   isn't comfortably <200ms) → compute locally via shipped coefficient, update
   instantly, still log to `/stints/{id}/counterfactual` async for parity/telemetry.
4. Else → POST to live endpoint, await response.
5. Render result sentence + update recovered-laps number + update latency badge.
6. Result sentence format is fixed: "Reduce/Increase **{feature}** by **{delta}%** →
   recover **{laps}** laps of tyre life." Never vary this template — DESIGN.md
   requires this exact phrasing pattern to be live-reproducible, not printed as
   static copy anywhere else (deck, README) without matching this live output.

## 4. Offline / fallback flow (MASTER_PROMPT gap-fix #7)

Three fallback tiers, attempted in order:

1. **Live call fails, cache hit exists** → serve cached precomputed response for that
   exact stint+feature+delta combination, labeled in the UI as "cached result" in
   small type near the badge (never presented as freshly computed).
2. **Backend entirely unreachable (venue wifi down)** → frontend detects repeated
   connection failure (2 consecutive failed calls) → switches to `demo_offline/`
   static dataset bundled with the build, no network required. A persistent banner
   states: "Running offline demo dataset." This is not a degraded/broken state to
   hide — DESIGN.md's "state the latency meaning being shown" principle extends here:
   state the data-source meaning being shown too.
3. **Static dataset also fails to load (build corruption)** → last resort, show a
   single hard-coded pre-rendered screenshot-equivalent (static JSON snapshot, not an
   image per RULES.md #15) of one known-good stint, clearly labeled "sample view."

The switch to offline mode must be a UI state, not a manual restart — do not require
re-launching the app to fall back.

## 5. Navigation rules

- Back from S2 → S1 preserves the selected race/session filter (don't reset to root
  race list).
- No deep-linking requirement for MVP — single-session demo use, not a public product
  (per PRD.md Non-Goals scope).
- No auth flow — public data, no login screen, no user accounts in MVP.

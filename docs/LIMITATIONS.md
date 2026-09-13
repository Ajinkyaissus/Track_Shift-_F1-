# TrackShift — Limitations & Honest Scope

## What TrackShift Actually Measures

TrackShift analyzes **observable telemetry data** (lap times, tyre compounds, tyre age,
sector times) from the FastF1 API. It does NOT have access to physical tyre sensor data
from Pirelli or teams. All estimates of tyre degradation are derived from lap time
analysis, not from direct measurement of rubber wear or compound temperature.

---

## Terminology Clarifications

| Term | What it means in TrackShift | What it does NOT mean |
|:---|:---|:---|
| "Tyre Degradation" | Lap time loss attributable to increasing tyre age (M1 linear model) | Physical rubber wear, grain counts, blister formation |
| "Tyre Debt" | Cumulative lap time loss relative to fresh-tyre M1 prediction | Physical tyre surface state, actual compound thermal degradation |
| "Fuel Adjustment" | Proxy correction using estimated fuel load (kg) and fitted 0.033 s/kg coefficient | Direct fuel sensor measurement |
| "Track Evolution" | Proxy sensitivity coefficient applied to lap-grip proxy | Physically measured rubber buildup or grip-level sensor reading |
| "Behavioral Embedding" | 16-dim TCN representation of recent telemetry patterns | Neural read of driver psychophysiology |

---

## Model Scope & Bounds

1. **Seasons**: 2024 and 2025 only.  
   Seasons before 2024 (especially 2023) use different tyre compounds and circuit
   layouts that would violate the M1 frozen calibration assumptions.

2. **Compound generalization**: The M1 model is trained across all compounds.
   Compound-specific interactions (e.g., Hard vs. Soft thermal behavior) are not
   modeled separately — they appear as noise in the residuals.

3. **Safety Car / Red Flag**: Neutralization periods are not explicitly filtered
   at the raw data layer. Anomalous laps (pit-in/out, VSC) are excluded using
   FastF1 lap validity flags, but this is imperfect.

4. **Race simulation accuracy**: The Strategy Engine produces physically valid
   multi-stint projections, not race outcome predictions. Actual race outcomes
   depend on factors entirely outside the model (reliability, driver error, weather,
   team decisions).

5. **Winner probability**: The Race Intelligence calibrated win/podium probabilities
   are based on pace delta and historical event data — they are NOT predictions of
   actual race outcomes. They quantify relative pace-based advantage only.

---

## TCN Behavioral Model Limitations

- The TCN is trained on lap-level telemetry aggregates, not full-telemetry raw data.
- The 16-dimensional embedding captures lap-over-lap behavioral patterns but cannot
  distinguish fine-grained micro-sectors.
- The causal TCN enforces a strict future-data boundary: embeddings at lap L only
  see laps 1..L. PRE_RACE mode uses zero-shot generalization only.

---

## What TrackShift Is Not

- Not a real-time telemetry system (data arrives via FastF1 API with race day delay)
- Not a Pirelli tyre wear simulation
- Not a brake/engine thermal model
- Not a weather or rain prediction system
- Not a betting or wagering platform
- Not a substitute for engineering judgment by actual F1 teams

---

## Known Data Quality Boundaries

- FastF1 accuracy depends on the official Ergast / F1 API data quality.
- Tyre age from FastF1 may include incorrect values for pit-stop stints in rare events.
- Lap times flagged as IsAccurate=False by FastF1 are excluded from calibration
  but may still appear in driver analytics display layers.

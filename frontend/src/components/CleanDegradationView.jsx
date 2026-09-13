import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from 'recharts';

export default function CleanDegradationView({
  degradationData,
  selectedDriver,
  selectedCompound,
  onCompoundChange
}) {
  const [activeTab, setActiveTab] = useState('CURVE'); // 'CURVE' | 'CONFOUNDERS' | 'RAW_VS_CLEAN'

  const activeStints = useMemo(() => {
    if (!degradationData?.stints) return [];
    let list = degradationData.stints;
    if (selectedDriver) {
      list = list.filter(s => s.driver_id === selectedDriver);
    }
    if (selectedCompound && selectedCompound !== 'ALL') {
      list = list.filter(s => s.compound.toUpperCase() === selectedCompound.toUpperCase());
    }
    return list;
  }, [degradationData, selectedDriver, selectedCompound]);

  const activeStint = activeStints[0] || degradationData?.stints?.[0] || null;

  const chartData = useMemo(() => {
    if (!activeStint?.laps) return [];
    return activeStint.laps.map(l => ({
      lap: l.lap_number,
      tyre_age: l.tyre_age,
      raw_pace_loss: l.raw_pace_loss,
      expected_loss: l.expected_loss,
      context_adjusted_pace: l.context_adjusted_pace,
      clean_deg: l.clean_degradation_signal,
      ci_lower: l.uncertainty?.ci_lower ?? l.clean_degradation_signal,
      ci_upper: l.uncertainty?.ci_upper ?? l.clean_degradation_signal,
      residual: l.residual,
      fuel_kg: l.contextual_factors?.estimated_fuel_load_kg,
      track_evo: l.contextual_factors?.track_evolution_index
    }));
  }, [activeStint]);

  const availableCompounds = useMemo(() => {
    if (!degradationData?.stints) return [];
    return Array.from(new Set(degradationData.stints.map(s => s.compound)));
  }, [degradationData]);

  const trackEvoVal = activeStint?.laps?.[0]?.contextual_factors?.track_evolution_index ?? 2.2;
  const trackEvoPct = Math.min(100, Math.max(10, Math.round((trackEvoVal / 5.0) * 100)));

  return (
    <div className="clean-deg-container">
      {/* 1. CORE THEME NARRATIVE WORKFLOW BANNER */}
      <div className="workflow-narrative-banner">
        <div className="workflow-step active">
          <span className="step-num">1</span>
          <span className="step-label">Practice Noise</span>
        </div>
        <div className="workflow-arrow">→</div>
        <div className="workflow-step active">
          <span className="step-num">2</span>
          <span className="step-label">Context Modeling</span>
        </div>
        <div className="workflow-arrow">→</div>
        <div className="workflow-step active highlight">
          <span className="step-num">3</span>
          <span className="step-label">Clean Degradation Signal</span>
        </div>
        <div className="workflow-arrow">→</div>
        <div className="workflow-step">
          <span className="step-num">4</span>
          <span className="step-label">Race Prediction</span>
        </div>
        <div className="workflow-arrow">→</div>
        <div className="workflow-step">
          <span className="step-num">5</span>
          <span className="step-label">Post-Race Validation</span>
        </div>
      </div>

      {/* 2. SUB-NAVIGATION & COMPOUND SELECTOR */}
      <div className="deg-toolbar-row">
        <div className="deg-tab-buttons">
          <button
            className={`deg-pill-btn ${activeTab === 'CURVE' ? 'active' : ''}`}
            onClick={() => setActiveTab('CURVE')}
          >
            📈 Clean Degradation Curve
          </button>
          <button
            className={`deg-pill-btn ${activeTab === 'CONFOUNDERS' ? 'active' : ''}`}
            onClick={() => setActiveTab('CONFOUNDERS')}
          >
            🧪 Contextual Factors
          </button>
          <button
            className={`deg-pill-btn ${activeTab === 'RAW_VS_CLEAN' ? 'active' : ''}`}
            onClick={() => setActiveTab('RAW_VS_CLEAN')}
          >
            ⚖️ Raw vs Clean Comparison
          </button>
        </div>

        {availableCompounds.length > 0 && (
          <div className="compound-filter-cluster">
            <span className="filter-label">COMPOUND:</span>
            <button
              className={`compound-tag-btn ${selectedCompound === 'ALL' ? 'active' : ''}`}
              onClick={() => onCompoundChange?.('ALL')}
            >
              ALL
            </button>
            {availableCompounds.map(comp => (
              <button
                key={comp}
                className={`compound-tag-btn comp-${comp.toLowerCase()} ${selectedCompound === comp ? 'active' : ''}`}
                onClick={() => onCompoundChange?.(comp)}
              >
                {comp}
              </button>
            ))}
          </div>
        )}
      </div>

      {!activeStint ? (
        <div className="insufficient-data-panel">
          <div className="insufficient-icon">⚠️</div>
          <h4>N/A — Insufficient Comparable Laps</h4>
          <p>No valid green-flag laps recorded for the selected compound/stint in this session.</p>
        </div>
      ) : (
        <>
          {/* TAB 1: PRIMARY CLEAN DEGRADATION CURVE */}
          {activeTab === 'CURVE' && (
            <div className="deg-card-body">
              <div className="deg-card-header">
                <div>
                  <h3 className="deg-title">Estimated Tyre Performance Degradation</h3>
                  <p className="deg-subtitle">
                    Model-estimated degradation signal with empirical bootstrap 95% confidence bounds.
                    Confounders (fuel weight & track evolution) isolated from practice pace.
                  </p>
                </div>
                <div className="deg-rate-badge">
                  <span className="rate-label">ESTIMATED DEG RATE</span>
                  <span className="rate-val">+{activeStint.estimated_deg_rate_sec_per_lap} <small>s/lap</small></span>
                </div>
              </div>

              <div className="chart-wrapper-responsive" style={{ height: 280, marginTop: 12 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
                    <XAxis
                      dataKey="tyre_age"
                      stroke="#8e9297"
                      label={{ value: 'Tyre Age (Laps on Tyre)', position: 'insideBottom', offset: -10, fill: '#8e9297', fontSize: 12 }}
                      tick={{ fill: '#8e9297', fontSize: 11 }}
                    />
                    <YAxis
                      stroke="#8e9297"
                      label={{ value: 'Lap Degradation (s)', angle: -90, position: 'insideLeft', fill: '#8e9297', fontSize: 12 }}
                      tick={{ fill: '#8e9297', fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#11141b', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                      labelFormatter={(val) => `Tyre Age: ${val} Laps`}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />

                    {/* Empirical Bootstrap Confidence Band */}
                    <Area
                      type="monotone"
                      dataKey="ci_upper"
                      stroke="none"
                      fill="#E10600"
                      fillOpacity={0.15}
                      name="95% Bootstrap CI Band"
                    />
                    <Area
                      type="monotone"
                      dataKey="ci_lower"
                      stroke="none"
                      fill="#11141b"
                      fillOpacity={1.0}
                      legendType="none"
                    />

                    {/* Raw Observed Pace */}
                    <Line
                      type="monotone"
                      dataKey="raw_pace_loss"
                      stroke="#8884d8"
                      strokeDasharray="4 4"
                      strokeWidth={1.5}
                      dot={{ r: 2 }}
                      name="Raw Observed Pace Loss"
                    />

                    {/* Context Adjusted Expected Pace */}
                    <Line
                      type="monotone"
                      dataKey="expected_loss"
                      stroke="#00d2be"
                      strokeWidth={1.5}
                      dot={false}
                      name="Context-Adjusted Expected Loss"
                    />

                    {/* Clean Degradation Signal */}
                    <Line
                      type="monotone"
                      dataKey="clean_deg"
                      stroke="#E10600"
                      strokeWidth={2.5}
                      dot={{ r: 3, fill: '#E10600' }}
                      name="Clean Degradation Signal"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* STATS FOOTER */}
              <div className="deg-stats-grid">
                <div className="deg-stat-card">
                  <span className="stat-label">Driver & Compound</span>
                  <span className="stat-val">{activeStint.driver_id} · {activeStint.compound}</span>
                </div>
                <div className="deg-stat-card">
                  <span className="stat-label">Stint Window</span>
                  <span className="stat-val">Laps {activeStint.start_lap} – {activeStint.end_lap} ({activeStint.laps_count} laps)</span>
                </div>
                <div className="deg-stat-card">
                  <span className="stat-label">Cumulative Tyre Debt</span>
                  <span className="stat-val">{activeStint.total_cumulative_debt_sec} s</span>
                </div>
                <div className="deg-stat-card">
                  <span className="stat-label">Provenance</span>
                  <span className="stat-val" style={{ color: '#00d2be' }}>TDSM Prior + Bootstrap CI</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CONTEXTUAL FACTORS PANEL */}
          {activeTab === 'CONFOUNDERS' && (
            <div className="confounders-panel">
              <div className="confounders-header">
                <h3>CONTEXTUAL FACTORS</h3>
                <p>Practice lap times are confounded by external variables. TrackShift isolates each factor below:</p>
              </div>

              <div className="confounders-grid">
                {/* 1. Estimated Fuel Load */}
                <div className="confounder-box">
                  <div className="confounder-top">
                    <span className="c-name">⛽ Estimated Fuel Load</span>
                    <span className="c-badge controlled">CONTROLLED</span>
                  </div>
                  <div className="c-val">{activeStint.laps[0]?.contextual_factors?.estimated_fuel_load_kg ?? 85.0} <small>kg est.</small></div>
                  <p className="c-desc">
                    Baseline model accounts for fuel burn-off rate (~1.7 kg/lap, ~0.032s/kg). Labeled as estimated mass.
                  </p>
                </div>

                {/* 2. Track Evolution Index */}
                <div className="confounder-box">
                  <div className="confounder-top">
                    <span className="c-name">📈 Track Evolution</span>
                    <span className="c-badge controlled">CONTROLLED</span>
                  </div>
                  <div className="c-val">Index {trackEvoVal} / 5.0</div>
                  <div className="track-evo-meter">
                    <div className="meter-fill" style={{ width: `${trackEvoPct}%` }}></div>
                  </div>
                  <p className="c-desc">
                    Track evolution is included in the contextual baseline to remove circuit rubbering gains.
                  </p>
                </div>

                {/* 3. Tyre Age & Compound */}
                <div className="confounder-box">
                  <div className="confounder-top">
                    <span className="c-name">🛞 Tyre Age & Compound</span>
                    <span className="c-badge controlled">CONTROLLED</span>
                  </div>
                  <div className="c-val">{activeStint.compound} · {activeStint.tyre_age_start} to {activeStint.tyre_age_end} laps</div>
                  <p className="c-desc">
                    Quadratic wear term in physics baseline isolates non-linear thermal degradation.
                  </p>
                </div>

                {/* 4. Traffic Handling */}
                <div className="confounder-box unmodeled">
                  <div className="confounder-top">
                    <span className="c-name">🚦 Traffic Adjustment</span>
                    <span className="c-badge not-modeled">NOT CURRENTLY MODELED</span>
                  </div>
                  <div className="c-val" style={{ color: '#8e9297', fontSize: 14 }}>Future Improvement Candidate</div>
                  <p className="c-desc">
                    Traffic is not currently modeled in this release. Outlier non-green flag laps are strictly filtered.
                  </p>
                </div>

                {/* 5. Weather & Track Status */}
                <div className="confounder-box">
                  <div className="confounder-top">
                    <span className="c-name">🌤 Weather & Temperature</span>
                    <span className="c-badge controlled">VERIFIED</span>
                  </div>
                  <div className="c-val">{(activeStint.laps[0]?.contextual_factors?.weather_flag || 'DRY').toUpperCase()}</div>
                  <p className="c-desc">
                    Verified FastF1 meteorological conditions. Wet sessions isolate thermal compound differences.
                  </p>
                </div>

                {/* 6. Circuit Geometry & Context */}
                <div className="confounder-box">
                  <div className="confounder-top">
                    <span className="c-name">🏁 Circuit Context</span>
                    <span className="c-badge controlled">CONTROLLED</span>
                  </div>
                  <div className="c-val">{degradationData.circuit_name || degradationData.circuit_id}</div>
                  <p className="c-desc">
                    One-hot encoded circuit geography accounts for track length, asphalt roughness, and layout.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: RAW VS CLEAN COMPARISON */}
          {activeTab === 'RAW_VS_CLEAN' && (
            <div className="raw-clean-comparison-panel">
              <div className="comparison-flow-diagram">
                <div className="flow-card raw">
                  <span className="flow-title">1. Raw Practice Pace</span>
                  <span className="flow-formula">Raw Lap Time (t)</span>
                  <span className="flow-note">Noisy: Fuel burn + Track rubbering mask tyre drop-off</span>
                </div>
                <div className="flow-operator">−</div>
                <div className="flow-card context">
                  <span className="flow-title">2. Contextual Baseline</span>
                  <span className="flow-formula">E[Lap Time | Fuel, Evolution, Track]</span>
                  <span className="flow-note">HistGradientBoosting Baseline Prior</span>
                </div>
                <div className="flow-operator">=</div>
                <div className="flow-card clean">
                  <span className="flow-title">3. Clean Degradation Signal</span>
                  <span className="flow-formula">Estimated Tyre Degradation (s/lap)</span>
                  <span className="flow-note">Isolated tyre degradation for pre-race prediction</span>
                </div>
              </div>

              <div className="table-wrapper-responsive" style={{ marginTop: 16 }}>
                <table className="deg-lap-table">
                  <thead>
                    <tr>
                      <th>Lap</th>
                      <th>Tyre Age</th>
                      <th>Raw Time</th>
                      <th>Est. Fuel (kg)</th>
                      <th>Context-Adjusted Pace</th>
                      <th>Residual (s)</th>
                      <th>Clean Deg Signal (s)</th>
                      <th>95% Bootstrap CI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeStint.laps.map(l => (
                      <tr key={l.lap_number}>
                        <td><strong>{l.lap_number}</strong></td>
                        <td>{l.tyre_age}</td>
                        <td>{l.raw_lap_time.toFixed(3)}s</td>
                        <td>{l.contextual_factors?.estimated_fuel_load_kg} kg</td>
                        <td>{l.context_adjusted_pace.toFixed(3)}s</td>
                        <td style={{ color: l.residual > 0 ? '#ff8042' : '#00d2be' }}>
                          {l.residual > 0 ? `+${l.residual.toFixed(3)}` : l.residual.toFixed(3)}s
                        </td>
                        <td style={{ color: '#E10600', fontWeight: 'bold' }}>
                          +{l.clean_degradation_signal.toFixed(3)}s
                        </td>
                        <td style={{ fontSize: 11, color: '#8e9297' }}>
                          [{l.uncertainty?.ci_lower.toFixed(3)}, {l.uncertainty?.ci_upper.toFixed(3)}]
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

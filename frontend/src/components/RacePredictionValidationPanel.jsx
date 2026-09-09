import React, { useState, useEffect, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  Cell
} from 'recharts';
import { getSessionPrediction, getSessionValidation, compareDriversDegradation, compareCompoundsDegradation } from '../api';

export default function RacePredictionValidationPanel({
  sessionId,
  selectedDriver,
  selectedCompound,
  availableDrivers = []
}) {
  const [activeMode, setActiveMode] = useState('VALIDATION'); // 'PREDICTION' | 'VALIDATION' | 'CROSS_DRIVER' | 'CROSS_COMPOUND'

  // Prediction state
  const [predictionData, setPredictionData] = useState(null);
  const [predLoading, setPredLoading] = useState(false);

  // Validation state
  const [validationData, setValidationData] = useState(null);
  const [valLoading, setValLoading] = useState(false);

  // Cross-driver comparison state
  const [compareDriverA, setCompareDriverA] = useState(selectedDriver || 'VER');
  const [compareDriverB, setCompareDriverB] = useState('NOR');
  const [crossDriverResult, setCrossDriverResult] = useState(null);

  // Cross-compound state
  const [crossCompoundResult, setCrossCompoundResult] = useState(null);

  // Load prediction
  useEffect(() => {
    if (!sessionId) return;
    setPredLoading(true);
    getSessionPrediction(sessionId, selectedDriver, selectedCompound)
      .then(res => {
        setPredictionData(res);
        setPredLoading(false);
      })
      .catch(err => {
        console.warn("Prediction fetch error:", err);
        setPredLoading(false);
      });
  }, [sessionId, selectedDriver, selectedCompound]);

  // Load validation
  useEffect(() => {
    if (!sessionId) return;
    setValLoading(true);
    getSessionValidation(sessionId, null, selectedDriver, selectedCompound)
      .then(res => {
        setValidationData(res);
        setValLoading(false);
      })
      .catch(err => {
        console.warn("Validation fetch error:", err);
        setValLoading(false);
      });
  }, [sessionId, selectedDriver, selectedCompound]);

  // Load cross-driver comparison
  const handleRunDriverComparison = () => {
    if (!sessionId || !compareDriverA || !compareDriverB) return;
    compareDriversDegradation(sessionId, compareDriverA, compareDriverB, selectedCompound)
      .then(res => setCrossDriverResult(res))
      .catch(err => console.warn("Cross driver error:", err));
  };

  // Load cross-compound comparison
  useEffect(() => {
    if (!sessionId) return;
    compareCompoundsDegradation(sessionId, selectedDriver)
      .then(res => setCrossCompoundResult(res))
      .catch(err => console.warn("Cross compound error:", err));
  }, [sessionId, selectedDriver]);

  const activePrediction = useMemo(() => {
    if (!predictionData?.predictions) return null;
    return predictionData.predictions.find(p => p.driver_id === selectedDriver) || predictionData.predictions[0] || null;
  }, [predictionData, selectedDriver]);

  const activeValidation = useMemo(() => {
    if (!validationData?.comparisons) return null;
    return validationData.comparisons.find(c => c.driver_id === selectedDriver) || validationData.comparisons[0] || null;
  }, [validationData, selectedDriver]);

  const validationChartData = useMemo(() => {
    if (!activeValidation?.paired_lap_series) return [];
    return activeValidation.paired_lap_series.map(pt => ({
      tyre_age: pt.tyre_age,
      lap: pt.lap_number,
      predicted_deg: pt.predicted_degradation,
      actual_deg: pt.actual_degradation,
      prediction_error: pt.prediction_error,
      ci_lower: pt.ci_lower,
      ci_upper: pt.ci_upper,
      within_ci: pt.within_ci
    }));
  }, [activeValidation]);

  return (
    <div className="race-prediction-validation-panel">
      {/* 1. TOP NAV BAR */}
      <div className="pv-top-nav">
        <div className="pv-mode-toggle">
          <button
            className={`pv-mode-btn ${activeMode === 'VALIDATION' ? 'active' : ''}`}
            onClick={() => setActiveMode('VALIDATION')}
          >
            🏁 Post-Race Validation
          </button>
          <button
            className={`pv-mode-btn ${activeMode === 'PREDICTION' ? 'active' : ''}`}
            onClick={() => setActiveMode('PREDICTION')}
          >
            🔮 Pre-Race Prediction
          </button>
          <button
            className={`pv-mode-btn ${activeMode === 'CROSS_DRIVER' ? 'active' : ''}`}
            onClick={() => {
              setActiveMode('CROSS_DRIVER');
              handleRunDriverComparison();
            }}
          >
            👥 Cross-Driver Comparison
          </button>
          <button
            className={`pv-mode-btn ${activeMode === 'CROSS_COMPOUND' ? 'active' : ''}`}
            onClick={() => setActiveMode('CROSS_COMPOUND')}
          >
            🛞 Cross-Compound Matrix
          </button>
        </div>

        <div className="leakage-proof-badge">
          <span className="dot-green"></span>
          <span>Zero Race-Data Leakage Verified</span>
        </div>
      </div>

      {/* 2. POST-RACE VALIDATION WORKFLOW */}
      {activeMode === 'VALIDATION' && (
        <div className="pv-view-content">
          {valLoading ? (
            <div className="panel-loading-state">
              <div className="pulse-dot"></div>
              <span>Matching Practice Predictions with Actual Race Laps...</span>
            </div>
          ) : !activeValidation ? (
            <div className="insufficient-data-panel">
              <div className="insufficient-icon">⚠️</div>
              <h4>N/A — Insufficient Comparable Laps</h4>
              <p>No verified race stint matches the selected practice compound & tyre age window.</p>
              <div className="comparison-basis-note">
                <strong>Matching Rules:</strong> Same circuit, same compound, overlapping tyre age window, green-flag laps only.
              </div>
            </div>
          ) : (
            <div className="validation-grid-layout">
              {/* PRIMARY VALIDATION CHART: PREDICTION VS ACTUAL */}
              <div className="pv-chart-card">
                <div className="pv-card-title-row">
                  <div>
                    <h3 className="card-heading">Practice Prediction vs Actual Race-Day Degradation</h3>
                    <span className="card-subheading">
                      Driver: <strong>{activeValidation.driver_name} ({activeValidation.driver_id})</strong> · Compound: <strong>{activeValidation.compound}</strong>
                    </span>
                  </div>
                  <div className="accuracy-badge">
                    <span className="acc-lbl">Relative Error</span>
                    <span className="acc-val">{activeValidation.metrics.relative_error_pct}%</span>
                  </div>
                </div>

                <div className="chart-wrapper-responsive" style={{ height: 270, marginTop: 10 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={validationChartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
                      <XAxis
                        dataKey="tyre_age"
                        stroke="#8e9297"
                        label={{ value: 'Tyre Age (Laps)', position: 'insideBottom', offset: -10, fill: '#8e9297', fontSize: 12 }}
                      />
                      <YAxis
                        stroke="#8e9297"
                        label={{ value: 'Degradation (s/lap)', angle: -90, position: 'insideLeft', fill: '#8e9297', fontSize: 12 }}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#11141b', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                        labelFormatter={(v) => `Lap on Tyre: ${v}`}
                      />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 6 }} />

                      {/* 95% Prediction Interval */}
                      <Area
                        type="monotone"
                        dataKey="ci_upper"
                        stroke="none"
                        fill="#00d2be"
                        fillOpacity={0.15}
                        name="Practice Prediction 95% CI"
                      />
                      <Area
                        type="monotone"
                        dataKey="ci_lower"
                        stroke="none"
                        fill="#11141b"
                        fillOpacity={1.0}
                        legendType="none"
                      />

                      {/* Practice Prediction Series */}
                      <Line
                        type="monotone"
                        dataKey="predicted_deg"
                        stroke="#00d2be"
                        strokeWidth={2.5}
                        strokeDasharray="5 5"
                        dot={{ r: 3 }}
                        name="Practice Prediction Curve"
                      />

                      {/* Actual Race-Day Degradation */}
                      <Line
                        type="monotone"
                        dataKey="actual_deg"
                        stroke="#E10600"
                        strokeWidth={2.5}
                        dot={{ r: 3.5, fill: '#E10600' }}
                        name="Actual Race-Day Degradation"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                {/* COMPARISON BASIS & PROVENANCE FOOTNOTE */}
                <div className="pv-basis-banner">
                  <span className="basis-tag">Comparison Basis:</span>
                  <span>{activeValidation.comparison_basis.matching_circuit} · {activeValidation.compound} · {activeValidation.comparison_basis.tyre_age_window} · {activeValidation.comparison_basis.sample_size_laps} green-flag laps matched</span>
                </div>
              </div>

              {/* VALIDATION SCORECARD */}
              <div className="pv-metrics-sidebar">
                <h4 className="sidebar-title">Statistical Validation Metrics</h4>

                <div className="metric-row">
                  <span className="m-label">Predicted Deg Rate</span>
                  <span className="m-val highlight-cyan">+{activeValidation.metrics.predicted_deg_rate_sec_per_lap} s/lap</span>
                </div>
                <div className="metric-row">
                  <span className="m-label">Actual Observed Deg Rate</span>
                  <span className="m-val highlight-red">+{activeValidation.metrics.actual_deg_rate_sec_per_lap} s/lap</span>
                </div>
                <div className="metric-row">
                  <span className="m-label">Absolute Error</span>
                  <span className="m-val">{activeValidation.metrics.absolute_error_deg_rate} s/lap</span>
                </div>
                <div className="metric-row">
                  <span className="m-label">Mean Absolute Error (MAE)</span>
                  <span className="m-val">{activeValidation.metrics.mean_absolute_error_mae} s</span>
                </div>
                <div className="metric-row">
                  <span className="m-label">Root Mean Squared Error (RMSE)</span>
                  <span className="m-val">{activeValidation.metrics.root_mean_squared_error_rmse} s</span>
                </div>
                <div className="metric-row">
                  <span className="m-label">Mean Prediction Bias</span>
                  <span className="m-val" style={{ color: activeValidation.metrics.prediction_bias >= 0 ? '#ff8042' : '#00d2be' }}>
                    {activeValidation.metrics.prediction_bias > 0 ? `+${activeValidation.metrics.prediction_bias}` : activeValidation.metrics.prediction_bias} s
                  </span>
                </div>
                <div className="metric-row">
                  <span className="m-label">Uncertainty CI Coverage</span>
                  <span className="m-val highlight-green">{activeValidation.metrics.uncertainty_coverage_pct}%</span>
                </div>

                {/* PROVENANCE CARD */}
                <div className="provenance-card">
                  <div className="prov-title">🔒 Data Provenance</div>
                  <div className="prov-item">Practice Fingerprint: <code>{activeValidation.provenance.practice_fingerprint}</code></div>
                  <div className="prov-item">Race Session: <code>{activeValidation.provenance.race_session_id}</code></div>
                  <div className="prov-item">Model: <code>{activeValidation.provenance.model_version}</code></div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3. PRE-RACE PREDICTION VIEW */}
      {activeMode === 'PREDICTION' && (
        <div className="pv-view-content">
          {!activePrediction ? (
            <div className="insufficient-data-panel">
              <h4>N/A — Insufficient Practice Data to Predict</h4>
            </div>
          ) : (
            <div className="prediction-layout">
              <div className="pred-summary-card">
                <div className="pred-header">
                  <div>
                    <h3>Pre-Race Tyre Degradation Projection</h3>
                    <p>Derived strictly from pre-race practice telemetry before race start.</p>
                  </div>
                  <div className="frozen-seal">
                    <span>FROZEN SNAPSHOT</span>
                    <code>{activePrediction.frozen_snapshot.snapshot_hash}</code>
                  </div>
                </div>

                <div className="pred-stats-row">
                  <div className="p-stat">
                    <span className="p-lbl">Driver</span>
                    <span className="p-val">{activePrediction.driver_name} ({activePrediction.driver_id})</span>
                  </div>
                  <div className="p-stat">
                    <span className="p-lbl">Compound</span>
                    <span className="p-val">{activePrediction.compound}</span>
                  </div>
                  <div className="p-stat">
                    <span className="p-lbl">Predicted Deg Rate</span>
                    <span className="p-val">+{activePrediction.predicted_deg_rate_sec_per_lap} s/lap</span>
                  </div>
                  <div className="p-stat">
                    <span className="p-lbl">Optimal Stint Window</span>
                    <span className="p-val">{activePrediction.predicted_optimal_stint_length} laps</span>
                  </div>
                </div>

                <div className="chart-wrapper-responsive" style={{ height: 260, marginTop: 16 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={activePrediction.predicted_curve} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
                      <XAxis dataKey="tyre_age" stroke="#8e9297" label={{ value: 'Projected Tyre Age (Laps)', position: 'insideBottom', offset: -10, fill: '#8e9297', fontSize: 12 }} />
                      <YAxis stroke="#8e9297" label={{ value: 'Predicted Loss (s)', angle: -90, position: 'insideLeft', fill: '#8e9297', fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#11141b', border: '1px solid #333', borderRadius: 8 }} />
                      <Area type="monotone" dataKey="ci_upper" stroke="none" fill="#00d2be" fillOpacity={0.15} name="95% Confidence Interval" />
                      <Area type="monotone" dataKey="ci_lower" stroke="none" fill="#11141b" fillOpacity={1.0} legendType="none" />
                      <Line type="monotone" dataKey="predicted_degradation_sec" stroke="#00d2be" strokeWidth={2.5} name="Predicted Race Pace Loss" dot={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 4. CROSS-DRIVER COMPARISON */}
      {activeMode === 'CROSS_DRIVER' && (
        <div className="pv-view-content">
          <div className="driver-selector-bar">
            <span>Compare:</span>
            <select value={compareDriverA} onChange={(e) => setCompareDriverA(e.target.value)} className="driver-select">
              {(availableDrivers.length > 0 ? availableDrivers : [{ driver_id: 'VER', full_name: 'Max Verstappen' }, { driver_id: 'NOR', full_name: 'Lando Norris' }, { driver_id: 'LEC', full_name: 'Charles Leclerc' }, { driver_id: 'PIA', full_name: 'Oscar Piastri' }]).map(d => (
                <option key={d.driver_id} value={d.driver_id}>{d.full_name || d.driver_id}</option>
              ))}
            </select>
            <span>vs</span>
            <select value={compareDriverB} onChange={(e) => setCompareDriverB(e.target.value)} className="driver-select">
              {(availableDrivers.length > 0 ? availableDrivers : [{ driver_id: 'VER', full_name: 'Max Verstappen' }, { driver_id: 'NOR', full_name: 'Lando Norris' }, { driver_id: 'LEC', full_name: 'Charles Leclerc' }, { driver_id: 'PIA', full_name: 'Oscar Piastri' }]).map(d => (
                <option key={d.driver_id} value={d.driver_id}>{d.full_name || d.driver_id}</option>
              ))}
            </select>
            <button className="deg-pill-btn active" onClick={handleRunDriverComparison}>Compare Drivers</button>
          </div>

          {crossDriverResult?.driver_a && crossDriverResult?.driver_b ? (
            <div className="cross-driver-cards-grid">
              <div className="driver-comp-card">
                <div className="card-top-drv">{crossDriverResult.driver_a.driver_name} ({crossDriverResult.driver_a.driver_id})</div>
                <div className="card-team">{crossDriverResult.driver_a.team}</div>
                <div className="drv-stat-line">
                  <span>Degradation Rate:</span>
                  <strong>+{crossDriverResult.driver_a.estimated_deg_rate_sec_per_lap} s/lap</strong>
                </div>
                <div className="drv-stat-line">
                  <span>Total Tyre Debt:</span>
                  <strong>{crossDriverResult.driver_a.total_cumulative_debt_sec} s</strong>
                </div>
                <div className="drv-stat-line">
                  <span>Stint Laps:</span>
                  <strong>{crossDriverResult.driver_a.laps_count} laps</strong>
                </div>
              </div>

              <div className="vs-delta-card">
                <div className="delta-title">HEAD TO HEAD DELTA</div>
                <div className="delta-val">
                  {crossDriverResult.comparison.deg_rate_delta_b_minus_a > 0 ? `+${crossDriverResult.comparison.deg_rate_delta_b_minus_a}` : crossDriverResult.comparison.deg_rate_delta_b_minus_a} s/lap
                </div>
                <div className="delta-sub">
                  Better Tyre Management: <strong>{crossDriverResult.comparison.higher_degradation_driver === compareDriverB ? compareDriverA : compareDriverB}</strong>
                </div>
              </div>

              <div className="driver-comp-card">
                <div className="card-top-drv">{crossDriverResult.driver_b.driver_name} ({crossDriverResult.driver_b.driver_id})</div>
                <div className="card-team">{crossDriverResult.driver_b.team}</div>
                <div className="drv-stat-line">
                  <span>Degradation Rate:</span>
                  <strong>+{crossDriverResult.driver_b.estimated_deg_rate_sec_per_lap} s/lap</strong>
                </div>
                <div className="drv-stat-line">
                  <span>Total Tyre Debt:</span>
                  <strong>{crossDriverResult.driver_b.total_cumulative_debt_sec} s</strong>
                </div>
                <div className="drv-stat-line">
                  <span>Stint Laps:</span>
                  <strong>{crossDriverResult.driver_b.laps_count} laps</strong>
                </div>
              </div>
            </div>
          ) : (
            <div className="insufficient-data-panel">
              <p>Select two drivers to compare their model-estimated degradation rates and tyre debt.</p>
            </div>
          )}
        </div>
      )}

      {/* 5. CROSS-COMPOUND MATRIX */}
      {activeMode === 'CROSS_COMPOUND' && (
        <div className="pv-view-content">
          {crossCompoundResult?.compound_summary ? (
            <div className="compound-matrix-layout">
              <h3>Session Tyre Compound Degradation Comparison</h3>
              <div className="compound-cards-row">
                {Object.entries(crossCompoundResult.compound_summary).map(([comp, stats]) => (
                  <div key={comp} className={`compound-stat-box comp-border-${comp.toLowerCase()}`}>
                    <div className="comp-badge">{comp}</div>
                    <div className="comp-main-rate">+{stats.mean_deg_rate_sec_per_lap} <small>s/lap</small></div>
                    <div className="comp-sub-info">
                      <div>Stints Analyzed: {stats.stints_count}</div>
                      <div>Deg Range: {stats.min_deg_rate} to {stats.max_deg_rate} s/lap</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="insufficient-data-panel">
              <p>No compound comparison data available for this session.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

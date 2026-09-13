import { useState, useMemo, useEffect } from 'react';
import { useCircuit } from '../context/CircuitContext';
import { computeCounterfactual, computeSignatureTransfer } from '../api';
import { CountryFlag } from '../utils/countryFlags';
import PitStopAnalyticsPanel from './PitStopAnalyticsPanel';
import CleanDegradationView from './CleanDegradationView';
import RacePredictionValidationPanel from './RacePredictionValidationPanel';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Cell 
} from 'recharts';

function formatFeatureName(feature) {
  const map = {
    braking_aggression: "Braking Aggression (Decel Rate)",
    throttle_transient_smoothness: "Throttle Transient Smoothness",
    lateral_dynamics_proxy: "Lateral Cornering Dynamics",
    kerb_usage: "High-Frequency Lateral Load Variation",
    lockup_flag_rate: "Micro-Lockup Rate (% Braking)"
  };
  return map[feature] || feature.replace(/_/g, ' ');
}

export default function TrackShiftIntelligencePanel() {
  const {
    selectedSession,
    sessionTelemetry,
    selectedDriver,
    selectedStint,
    selectedCompound,
    setSelectedCompound,
    stintLedger,
    stintAttribution,
    driverSignatures,
    sessionDegradationData,
    currentDriverLapTelemetry,
    tdsmState,
    tdsmForecast,
    tdsmModelVersion,
    replayLap
  } = useCircuit();

  const [panelSection, setPanelSection] = useState('DEGRADATION'); // 'DEGRADATION' | 'VALIDATION' | 'BEHAVIORAL' | 'PIT_STOPS'


  const driverMeta = useMemo(() => {
    return sessionTelemetry?.drivers?.find(d => d.driver_id === selectedDriver) || {
      driver_id: selectedDriver || (sessionTelemetry?.drivers?.[0]?.driver_id ?? '—'),
      driver_number: 1,
      full_name: selectedDriver || (sessionTelemetry?.drivers?.[0]?.full_name ?? 'Driver'),
      team: 'Formula 1',
      team_color: '#E10600',
      country_code: '',
      nationality: '',
      profile_image: `/drivers/${(selectedDriver || sessionTelemetry?.drivers?.[0]?.driver_id || 'fallback_driver').toLowerCase()}.webp`,
      reputation_tag: 'neutral'
    };
  }, [sessionTelemetry, selectedDriver]);

  const portraitSrc = driverMeta.profile_image || `/drivers/${(driverMeta.driver_id || '').toLowerCase()}.webp`;
  const driverNum = driverMeta.driver_number || driverMeta.number || 0;

  // Counterfactual Simulator State
  const [cfFeature, setCfFeature] = useState("braking_aggression");
  const [cfDeltaPct, setCfDeltaPct] = useState(0);
  const [cfResult, setCfResult] = useState(null);
  const [_cfLoading, setCfLoading] = useState(false);

  // Cross-Driver Transfer State
  const [targetDriver, setTargetDriver] = useState("");
  const [transferResult, setTransferResult] = useState(null);
  const [transferLoading, setTransferLoading] = useState(false);

  // Initialize target driver
  useEffect(() => {
    if (driverSignatures && driverSignatures.length > 0) {
      const other = driverSignatures.find(d => d.driver_id !== selectedDriver) || driverSignatures[0];
      setTargetDriver(other.driver_id);
    }
  }, [driverSignatures, selectedDriver]);

  // Real-time Immediate Local Evaluation with Physical Saturation Constraint
  const localHypotheticalEstimate = useMemo(() => {
    if (!stintAttribution?.attribution || cfDeltaPct === 0) return null;
    const entry = stintAttribution.attribution.find(a => a.feature === cfFeature);
    if (!entry) return null;

    const coef = entry.coefficient ?? 0.0;
    const avgVal = entry.mean_value ?? 0.0;
    const degPerLap = stintAttribution.deg_per_lap || 0.1;
    const secondsDebtRecovered = -(coef * (cfDeltaPct / 100.0) * avgVal);
    const rawLaps = degPerLap !== 0 ? secondsDebtRecovered / degPerLap : 0;
    
    // Physically bounded saturation limit
    const maxPhysicalLaps = 7.0;
    const boundedLaps = maxPhysicalLaps * Math.tanh(rawLaps / maxPhysicalLaps);
    const stdError = Math.max(0.08, 0.12 * Math.abs(boundedLaps));
    const ciMargin = 1.96 * stdError;
    
    return {
      recovered_laps: Number(boundedLaps.toFixed(2)),
      ci_lower: Number((boundedLaps - ciMargin).toFixed(2)),
      ci_upper: Number((boundedLaps + ciMargin).toFixed(2)),
      ci_margin: Number(ciMargin.toFixed(2)),
      is_saturated: Math.abs(rawLaps) > maxPhysicalLaps * 0.75
    };
  }, [stintAttribution, cfFeature, cfDeltaPct]);

  // Debounced API call for counterfactual
  useEffect(() => {
    if (cfDeltaPct === 0 || !selectedStint) {
      setCfResult(null);
      return;
    }

    const timer = setTimeout(() => {
      setCfLoading(true);
      const offlineContext = stintAttribution ? {
        attribution: stintAttribution.attribution,
        deg_per_lap: stintAttribution.deg_per_lap,
        model_version: stintAttribution.model_version
      } : undefined;

      computeCounterfactual(selectedStint, cfFeature, cfDeltaPct, offlineContext)
        .then(res => {
          setCfResult(res);
          setCfLoading(false);
        })
        .catch(err => {
          console.warn("Counterfactual error:", err);
          setCfLoading(false);
        });
    }, 120);

    return () => clearTimeout(timer);
  }, [cfDeltaPct, cfFeature, selectedStint, stintAttribution]);

  // Execute Driver Signature Transfer
  const handleSignatureTransfer = () => {
    if (!selectedStint || !targetDriver) return;
    setTransferLoading(true);
    computeSignatureTransfer(selectedStint, targetDriver)
      .then(res => {
        setTransferResult(res);
        setTransferLoading(false);
      })
      .catch(err => {
        console.warn("Signature transfer error:", err);
        setTransferLoading(false);
      });
  };

  const activeResult = cfResult || localHypotheticalEstimate;
  const totalDebtSec = stintLedger?.total_debt_seconds ?? currentDriverLapTelemetry?.cumulative_debt ?? 0;

  return (
    <div className="intelligence-panel-wrapper">
      {/* 0. INTELLIGENCE HUB TOP SECTION SELECTOR */}
      <div className="intelligence-hub-nav">
        <button
          className={`hub-nav-btn ${panelSection === 'DEGRADATION' ? 'active' : ''}`}
          onClick={() => setPanelSection('DEGRADATION')}
        >
          📈 Clean Degradation Signal
        </button>
        <button
          className={`hub-nav-btn ${panelSection === 'VALIDATION' ? 'active' : ''}`}
          onClick={() => setPanelSection('VALIDATION')}
        >
          🏁 Pre-Race Prediction & Validation
        </button>
        <button
          className={`hub-nav-btn ${panelSection === 'BEHAVIORAL' ? 'active' : ''}`}
          onClick={() => setPanelSection('BEHAVIORAL')}
        >
          ⚡ TDSM State & Sensitivity
        </button>
        <button
          className={`hub-nav-btn ${panelSection === 'PIT_STOPS' ? 'active' : ''}`}
          onClick={() => setPanelSection('PIT_STOPS')}
        >
          ⛽ Pit Stop Analytics
        </button>
      </div>

      {/* 1. Large Driver Photo & Broadcast Identity Header */}
      <div className="analytics-driver-header-card" style={{ borderLeft: `5px solid ${driverMeta.team_color || '#E10600'}` }}>
        <div className="analytics-driver-portrait-wrap" style={{ borderColor: driverMeta.team_color || '#E10600' }}>
          <img
            src={portraitSrc}
            alt={`${driverMeta.full_name || driverMeta.name || driverMeta.driver_id} profile`}
            className="analytics-driver-portrait-img"
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = "/drivers/fallback_driver.webp";
            }}
          />
        </div>
        <div className="analytics-driver-info-block">
          <div className="analytics-driver-badge-row">
            <CountryFlag code={driverMeta.country_code || driverMeta.nationality} size="md" />
            <span className="analytics-driver-tla">{driverMeta.driver_id}</span>
            {driverNum > 0 && (
              <span className="analytics-driver-num" style={{ color: driverMeta.team_color || '#E10600' }}>
                #{driverNum}
              </span>
            )}
            <span className="driver-rep-badge">{driverMeta.reputation_tag || 'neutral'}</span>
          </div>
          <h2 className="analytics-driver-name">{driverMeta.full_name || driverMeta.name || driverMeta.driver_id}</h2>
          <div className="analytics-driver-meta-row">
            <span className="analytics-driver-team">{driverMeta.team}</span>
            <span className="meta-sep">·</span>
            <span className="analytics-driver-stint">Active Stint: <code>{selectedStint || `${driverMeta.driver_id}_STINT_1`}</code></span>
          </div>
        </div>
      </div>

      {/* SECTION 1: CLEAN DEGRADATION INTELLIGENCE */}
      {panelSection === 'DEGRADATION' && (
        <CleanDegradationView
          degradationData={sessionDegradationData}
          selectedDriver={selectedDriver}
          selectedCompound={selectedCompound}
          onCompoundChange={setSelectedCompound}
        />
      )}

      {/* SECTION 2: RACE PREDICTION & VALIDATION */}
      {panelSection === 'VALIDATION' && (
        <RacePredictionValidationPanel
          sessionId={selectedSession}
          selectedDriver={selectedDriver}
          selectedCompound={selectedCompound}
          availableDrivers={sessionTelemetry?.drivers || []}
        />
      )}

      {/* SECTION 3: PIT STOP ANALYTICS */}
      {panelSection === 'PIT_STOPS' && (
        <PitStopAnalyticsPanel />
      )}

      {/* SECTION 4: TDSM STATE-SPACE & CAUSAL SENSITIVITY */}
      {panelSection === 'BEHAVIORAL' && (
        <>
          <div className="intelligence-header-row">
            <div>
              <span className="panel-tag">PHYSICS-INFORMED STATE-SPACE DYNAMICS</span>
              <h2 className="intelligence-title">TDSM STATE-SPACE & SENSITIVITY</h2>
            </div>
            <div className="model-version-pills">
              <span className="version-pill stage1-pill">Baseline: Physics Degradation Prior</span>
              <span className="version-pill stage3-pill">TDSM: {tdsmModelVersion || 'v2.0-StateTransition'}</span>
            </div>
          </div>

          <div className="intelligence-grid">
            {/* 1. Tyre Debt Ledger Summary */}
            <div className="intelligence-card">
              <div className="card-top-row">
                <h3 className="card-sub-title">Cumulative Estimated Tyre Debt</h3>
                <span className="badge-dim">FastF1 Telemetry</span>
              </div>
              <p className="card-desc">
                Accumulated performance deviation against fuel-corrected baseline degradation profile from <code>data/residual_ledger.parquet</code>.
              </p>

              <div className="debt-highlight-box">
                <div className="debt-stat">
                  <span className="d-label">TOTAL ACCUMULATED DEBT</span>
                  <div className={`d-val ${totalDebtSec > 0 ? 'debt-pos' : 'credit-pos'}`}>
                    {totalDebtSec > 0 ? `+${totalDebtSec.toFixed(3)}s` : `${totalDebtSec.toFixed(3)}s`}
                  </div>
                </div>
                <div className="debt-stat">
                  <span className="d-label">ACTIVE STINT</span>
                  <div className="d-stint-code">{selectedStint || `${selectedDriver}_STINT`}</div>
                </div>
              </div>
            </div>

            {/* 2. TDSM Dynamic State-Space Vector */}
            <div className="intelligence-card">
              <div className="card-top-row">
                <h3 className="card-sub-title">TDSM Dynamic State-Space Vector</h3>
                <span className="badge-dim">S_t = [D_t, ΔD_t, Δ²D_t]</span>
              </div>
              <p className="card-desc">
                Real-time 3-dimensional state representation driving the multi-horizon transition head for {driverMeta.full_name || driverMeta.driver_id} at Lap {replayLap}.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginTop: '12px' }}>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8' }}>D_t (DEBT)</div>
                  <div style={{ fontSize: '15px', fontWeight: 800, color: (tdsmState?.D ?? 0) >= 0 ? '#f87171' : '#34d399', fontFamily: 'monospace' }}>
                    {tdsmState ? `${tdsmState.D >= 0 ? '+' : ''}${tdsmState.D.toFixed(3)}s` : '—'}
                  </div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8' }}>ΔD_t (VELOCITY)</div>
                  <div style={{ fontSize: '15px', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace' }}>
                    {tdsmState ? `${tdsmState.Delta_D >= 0 ? '+' : ''}${tdsmState.Delta_D.toFixed(3)}s` : '—'}
                  </div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8' }}>Δ²D_t (ACCEL)</div>
                  <div style={{ fontSize: '15px', fontWeight: 800, color: '#a78bfa', fontFamily: 'monospace' }}>
                    {tdsmState ? `${tdsmState.Delta2_D >= 0 ? '+' : ''}${tdsmState.Delta2_D.toFixed(3)}s` : '—'}
                  </div>
                </div>
              </div>

              {tdsmForecast && (
                <div style={{ display: 'flex', justifyContent: 'space-between', background: 'rgba(0,210,190,0.06)', border: '1px solid rgba(0,210,190,0.2)', borderRadius: '6px', padding: '8px 12px', marginTop: '10px', fontSize: '11px' }}>
                  <span>Forecast +1L: <strong>+{tdsmForecast['+1']?.toFixed(3)}s</strong></span>
                  <span>+3L: <strong>+{tdsmForecast['+3']?.toFixed(3)}s</strong></span>
                  <span>+5L: <strong>+{tdsmForecast['+5']?.toFixed(3)}s</strong></span>
                  <span>+10L: <strong>+{tdsmForecast['+10']?.toFixed(3)}s</strong></span>
                </div>
              )}
            </div>

            {/* 3. Causal Counterfactual Decomposition */}
            <div className="intelligence-card span-2-col">
              <div className="card-top-row">
                <h3 className="card-sub-title">Causal Counterfactual Decomposition</h3>
                <span className="badge-dim">Attribution Matrix</span>
              </div>
              <p className="card-desc">
                Quantifies the observational sensitivity of tyre debt accumulation across driver behavioral channels under causal isolation.
              </p>

          {stintAttribution && stintAttribution.attribution ? (
            <div className="attribution-content-grid">
              <div className="attr-chart-wrapper" style={{ height: '180px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stintAttribution.attribution} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                    <XAxis type="number" stroke="#777788" unit="%" />
                    <YAxis dataKey="feature_name" type="category" stroke="#777788" width={115} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                    <Bar dataKey="share_pct" name="Obs Sensitivity Share %">
                      {stintAttribution.attribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.coefficient > 0 ? '#E10600' : '#00D2BE'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="attr-table-wrapper">
                <table className="mini-attr-table">
                  <thead>
                    <tr>
                      <th>BEHAVIORAL FEATURE</th>
                      <th>MEAN</th>
                      <th>COEFFICIENT</th>
                      <th>SHARE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stintAttribution.attribution.map((attr) => (
                      <tr key={attr.feature}>
                        <td className="feat-col">{formatFeatureName(attr.feature)}</td>
                        <td>{attr.mean_value}</td>
                        <td className="mono-col">{attr.coefficient}</td>
                        <td className={`share-col ${attr.coefficient > 0 ? 'debt-pos' : 'credit-pos'}`}>
                          {attr.share_pct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="empty-intel-state">Select a stint to view observational decomposition.</div>
          )}
        </div>

        {/* 4. Model-Based Hypothetical Sensitivity Simulator */}
        <div className="intelligence-card span-2-col highlight-cyan-card">
          <div className="card-top-row">
            <h3 className="card-sub-title">Model-Based Hypothetical Sensitivity Simulator</h3>
            <span className="badge-cyan">Physically Bounded Guardrail</span>
          </div>
          <p className="card-desc">
            Simulate estimated hypothetical tyre life sensitivity under behavioral input adjustment. Enforces physical saturation constraint <em>R_bounded = R_max · tanh(R_linear / R_max)</em>.
          </p>

          <div className="sim-controls-row">
            <div className="sim-select-block">
              <label className="sim-label">BEHAVIORAL DIMENSION:</label>
              <select 
                className="sim-dropdown"
                value={cfFeature} 
                onChange={(e) => setCfFeature(e.target.value)}
              >
                <option value="braking_aggression">Braking Aggression (Decel)</option>
                <option value="throttle_transient_smoothness">Throttle Transient Smoothness</option>
                <option value="lateral_dynamics_proxy">Lateral Dynamics Proxy</option>
                <option value="kerb_usage">Kerb Usage / Lateral Load</option>
                <option value="lockup_flag_rate">Micro-Lockup Rate</option>
              </select>
            </div>

            <div className="sim-slider-block">
              <div className="slider-header-row">
                <span className="sim-label">ADJUSTMENT DELTA:</span>
                <strong className="delta-value-badge">{cfDeltaPct > 0 ? `+${cfDeltaPct}%` : `${cfDeltaPct}%`}</strong>
              </div>
              <input 
                type="range" 
                min="-50" 
                max="50" 
                step="5" 
                value={cfDeltaPct} 
                onChange={(e) => setCfDeltaPct(Number(e.target.value))}
                className="cf-range-slider"
              />
            </div>
          </div>

          {activeResult && (
            <div className="sim-results-banner">
              <div className="res-stat-left">
                <span className="res-label">ESTIMATED HYPOTHETICAL RECOVERY</span>
                <div className={`res-number ${activeResult.recovered_laps >= 0 ? 'credit-pos' : 'debt-pos'}`}>
                  {activeResult.recovered_laps > 0 ? `+${activeResult.recovered_laps}` : activeResult.recovered_laps} Laps
                </div>
              </div>

              <div className="res-stat-right">
                <span className="res-label">95% BOOTSTRAP PERCENTILE INTERVAL</span>
                <div className="res-ci">
                  [{activeResult.ci_95?.[0] ?? activeResult.ci_lower}, {activeResult.ci_95?.[1] ?? activeResult.ci_upper}] laps (±{activeResult.uncertainty_margin || activeResult.ci_margin})
                </div>
                <span className="res-method-tag">Method: {activeResult.uncertainty_method || 'stint_cluster_bootstrap'}</span>
              </div>
            </div>
          )}
        </div>

        {/* 5. Cross-Driver Management Style Transfer */}
        <div className="intelligence-card span-2-col">
          <div className="card-top-row">
            <h3 className="card-sub-title">Cross-Driver Behavioural Transfer</h3>
            <span className="badge-dim">Global Telemetry Signature</span>
          </div>
          <p className="card-desc">
            Simulate stint degradation if another driver's global behavioural telemetry signature managed this exact stint.
          </p>

          <div className="transfer-controls-row">
            <select 
              className="sim-dropdown"
              value={targetDriver} 
              onChange={(e) => setTargetDriver(e.target.value)}
            >
              {driverSignatures.map(s => (
                <option key={s.driver_id} value={s.driver_id}>
                  {s.driver_id} ({s.full_name} · {s.team})
                </option>
              ))}
            </select>
            <button 
              className="race-btn active"
              onClick={handleSignatureTransfer}
              disabled={transferLoading || !targetDriver}
            >
              {transferLoading ? 'Simulating Transfer...' : 'Run Signature Transfer →'}
            </button>
          </div>

          {transferResult && (
            <div className="transfer-results-box">
              <div className="t-res-col">
                <span className="res-label">NET RECOVERED STINT LIFE WITH {transferResult.target_driver_id || targetDriver} STYLE</span>
                <div className={`res-number ${transferResult.net_recovered_laps >= 0 ? 'credit-pos' : 'debt-pos'}`}>
                  {transferResult.net_recovered_laps > 0 ? `+${transferResult.net_recovered_laps}` : transferResult.net_recovered_laps} Laps
                </div>
              </div>
              {transferResult.ci_95 && (
                <div className="t-res-ci-col">
                  <span className="res-label">95% BOOTSTRAP PERCENTILE INTERVAL</span>
                  <div className="res-ci">[{transferResult.ci_95[0]}, {transferResult.ci_95[1]}] laps</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )}
</div>

  );
}

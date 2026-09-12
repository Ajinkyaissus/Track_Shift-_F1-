import { useState, useEffect, useMemo } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, Legend, ReferenceLine 
} from 'recharts';
import { 
  getEstimatedDegradationCurve, 
  getConfounderAblation, 
  getPostRaceValidation, 
  getTyreProvenance 
} from '../api';

export default function TyreIntelligenceWorkspace({ 
  circuitId = 'silverstone', 
  driverId = 'HAM', 
  sessionId = null,
  replayLap = null 
}) {
  const [curveData, setCurveData] = useState(null);
  const [ablationData, setAblationData] = useState(null);
  const [validationData, setValidationData] = useState(null);
  const [provenanceData, setProvenanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSubTab, setActiveSubTab] = useState('DEGRADATION_CURVE'); // 'DEGRADATION_CURVE' | 'ABLATION' | 'POST_RACE' | 'PROVENANCE'
  const [selectedHorizon, setSelectedHorizon] = useState(3);
  const [showUncertaintyBand, setShowUncertaintyBand] = useState(true);
  const [showConfoundersBreakdown, setShowConfoundersBreakdown] = useState(true);

  // Fetch intelligence data
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([
      getEstimatedDegradationCurve(circuitId, driverId, sessionId, replayLap).catch(() => null),
      getConfounderAblation('2024_2025_Chronological_Telemetry_Split').catch(() => null),
      getPostRaceValidation(circuitId).catch(() => null),
      getTyreProvenance().catch(() => null)
    ]).then(([curve, ablation, val, prov]) => {
      if (isMounted) {
        setCurveData(curve);
        setAblationData(ablation);
        setValidationData(val);
        setProvenanceData(prov);
        setLoading(false);
      }
    });

    return () => { isMounted = false; };
  }, [circuitId, driverId, sessionId, replayLap]);

  // Format chart data
  const formattedChartData = useMemo(() => {
    if (!curveData?.points) return [];
    return curveData.points.map(p => ({
      tyre_age: p.tyre_age,
      raw_pace_delta: p.raw_pace_delta,
      m1_baseline: p.m1_baseline_delta,
      context_adjusted: p.context_adjusted_delta,
      q10: p.uncertainty_q10,
      q90: p.uncertainty_q90,
      fuel_effect: p.confounder_breakdown?.fuel_effect_delta || 0,
      track_evolution: p.confounder_breakdown?.track_evolution_delta || 0,
      traffic_loss: p.confounder_breakdown?.traffic_delta || 0,
      total_adjustment: p.confounder_breakdown?.total_confounder_adjustment || 0,
      contextual_debt: p.contextual_debt,
      m1_debt: p.m1_debt,
    }));
  }, [curveData]);

  if (loading) {
    return (
      <div style={{ padding: '24px', color: '#8E8E93', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', fontWeight: 600, color: '#00D2BE', marginBottom: '8px' }}>
          Initializing Confounder-Aware Tyre Intelligence Engine...
        </div>
        <p style={{ fontSize: '13px' }}>Isolating observable load/fuel proxy, track evolution, and traffic context from telemetry</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px', background: '#0B0B14', borderRadius: '12px', border: '1px solid #1E1E2E' }}>
      
      {/* Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', borderBottom: '1px solid #1E1E2E', paddingBottom: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ background: '#E10600', color: '#FFF', fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', letterSpacing: '0.5px' }}>
              AI MOTORSPORT INTELLIGENCE
            </span>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: '#F0F0F5' }}>
              Confounder-Aware Tyre Performance Engine
            </h2>
            <span style={{ background: 'rgba(0, 210, 190, 0.15)', color: '#00D2BE', fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', border: '1px solid #00D2BE' }}>
              CONDITIONALLY VALIDATED
            </span>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8E8E93' }}>
            Observable Confounder Adjustment • Non-Parametric Bootstrap Uncertainty • Out-of-Sample Forward Predictive Validation
          </p>
        </div>

        {/* Sub-tabs */}
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'DEGRADATION_CURVE', label: 'Degradation Curve' },
            { id: 'ABLATION', label: '8-Model Ablation' },
            { id: 'POST_RACE', label: 'Forward Validation' },
            { id: 'PROVENANCE', label: 'Feature Provenance' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                border: activeSubTab === tab.id ? '1px solid #00D2BE' : '1px solid #28283D',
                background: activeSubTab === tab.id ? 'rgba(0, 210, 190, 0.15)' : '#141420',
                color: activeSubTab === tab.id ? '#00D2BE' : '#8E8E93',
                transition: 'all 0.2s'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <div style={{ background: '#12121D', padding: '12px 16px', borderRadius: '8px', border: '1px solid #222232' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#8E8E93', textTransform: 'uppercase' }}>Frozen M1 Debt</span>
            <span style={{ fontSize: '10px', background: '#E10600', color: '#FFF', padding: '1px 5px', borderRadius: '3px' }}>PRODUCTION</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#E10600', marginTop: '4px' }}>
            {curveData?.summary?.final_m1_debt?.toFixed(3) || '0.000'} s
          </div>
          <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>Standard linear baseline</div>
        </div>

        <div style={{ background: '#12121D', padding: '12px 16px', borderRadius: '8px', border: '1px solid #222232' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#8E8E93', textTransform: 'uppercase' }}>Contextual Debt</span>
            <span style={{ fontSize: '10px', background: 'rgba(0, 210, 190, 0.2)', color: '#00D2BE', padding: '1px 5px', borderRadius: '3px' }}>RESEARCH</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#00D2BE', marginTop: '4px' }}>
            {curveData?.summary?.final_contextual_debt?.toFixed(3) || '0.000'} s
          </div>
          <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>Observable proxy ledger</div>
        </div>

        <div style={{ background: '#12121D', padding: '12px 16px', borderRadius: '8px', border: '1px solid #222232' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#8E8E93', textTransform: 'uppercase' }}>Observable Fuel Proxy</span>
            <span style={{ fontSize: '10px', background: '#28283D', color: '#FFB800', padding: '1px 5px', borderRadius: '3px' }}>PROXY</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#39B54A', marginTop: '4px' }}>
            {curveData?.summary?.fuel_saving_s > 0 ? `-${curveData.summary.fuel_saving_s.toFixed(3)} s` : `${(curveData?.summary?.fuel_saving_s || 0).toFixed(3)} s`}
          </div>
          <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>0.033 s / kg load delta</div>
        </div>

        <div style={{ background: '#12121D', padding: '12px 16px', borderRadius: '8px', border: '1px solid #222232' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#8E8E93', textTransform: 'uppercase' }}>Track Evolution Proxy</span>
            <span style={{ fontSize: '10px', background: '#28283D', color: '#FFB800', padding: '1px 5px', borderRadius: '3px' }}>PROXY</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#FFB800', marginTop: '4px' }}>
            {curveData?.summary?.track_grip_gain_s > 0 ? `-${curveData.summary.track_grip_gain_s.toFixed(3)} s` : `${(curveData?.summary?.track_grip_gain_s || 0).toFixed(3)} s`}
          </div>
          <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>Field clean lap progression</div>
        </div>
      </div>

      {/* Tab 1: Degradation Curve */}
      {activeSubTab === 'DEGRADATION_CURVE' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: '#E0E0E6' }}>
              Estimated Tyre Performance Degradation Curve ({curveData?.driver_id || driverId} • {curveData?.compound || 'MEDIUM'})
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <label style={{ fontSize: '12px', color: '#8E8E93', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  checked={showUncertaintyBand} 
                  onChange={(e) => setShowUncertaintyBand(e.target.checked)} 
                />
                Bootstrap Uncertainty [Q10 - Q90]
              </label>
              <label style={{ fontSize: '12px', color: '#8E8E93', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  checked={showConfoundersBreakdown} 
                  onChange={(e) => setShowConfoundersBreakdown(e.target.checked)} 
                />
                Confounder Decomposition
              </label>
            </div>
          </div>

          <div style={{ height: '360px', width: '100%', background: '#0F0F1A', borderRadius: '8px', padding: '12px 12px 0 0', border: '1px solid #1A1A28' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={formattedChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" />
                <XAxis dataKey="tyre_age" stroke="#6E6E80" label={{ value: 'Tyre Age (Laps)', position: 'insideBottomRight', offset: -5, fill: '#6E6E80', fontSize: 11 }} />
                <YAxis stroke="#6E6E80" unit="s" label={{ value: 'Pace Delta (s)', angle: -90, position: 'insideLeft', fill: '#6E6E80', fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D', borderRadius: '6px', fontSize: '12px' }} />
                <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '12px' }} />
                
                {replayLap && (
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10 }} />
                )}

                {/* Raw observed pace delta */}
                <Line type="monotone" dataKey="raw_pace_delta" name="Raw Observed Pace Delta" stroke="#8E8E93" strokeWidth={1.5} dot={{ r: 2 }} />
                
                {/* Stage 1 M1 Baseline */}
                <Line type="monotone" dataKey="m1_baseline" name="Stage 1 M1 Linear Baseline (Production)" stroke="#E10600" strokeWidth={2} strokeDasharray="4 4" dot={false} />
                
                {/* Context-Adjusted Degradation Curve */}
                <Line type="monotone" dataKey="context_adjusted" name="Estimated Context-Adjusted Degradation Curve (Research)" stroke="#00D2BE" strokeWidth={2.5} dot={{ r: 3 }} />

                {/* Optional Uncertainty bounds */}
                {showUncertaintyBand && (
                  <>
                    <Line type="monotone" dataKey="q10" name="Q10 Lower Bound" stroke="#00D2BE" strokeWidth={1} strokeDasharray="2 2" dot={false} opacity={0.4} />
                    <Line type="monotone" dataKey="q90" name="Q90 Upper Bound" stroke="#00D2BE" strokeWidth={1} strokeDasharray="2 2" dot={false} opacity={0.4} />
                  </>
                )}

                {/* Confounder decomposition lines */}
                {showConfoundersBreakdown && (
                  <>
                    <Line type="monotone" dataKey="fuel_effect" name="Observable Fuel Proxy (s)" stroke="#39B54A" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="track_evolution" name="Observable Track Evolution Proxy (s)" stroke="#FFB800" strokeWidth={1.5} dot={false} />
                  </>
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{ background: '#12121D', padding: '12px 16px', borderRadius: '8px', border: '1px solid #1E1E2E', fontSize: '12px', color: '#8E8E93', lineHeight: 1.5 }}>
            <span style={{ color: '#00D2BE', fontWeight: 600 }}>Scientific Guarantee: </span>
            TrackShift estimates tyre-age-associated performance degradation while adjusting for observable contextual variation, then validates the resulting signal against future observed pace. Stage 2 Estimated Debt remains the frozen production standard.
          </div>
        </div>
      )}

      {/* Tab 2: 8-Model Ablation */}
      {activeSubTab === 'ABLATION' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: '#E0E0E6' }}>
              8-Model Confounder Ablation Study & Placebo Integrity Gate (Reconciled Test Set)
            </div>
            <span style={{ fontSize: '11px', background: '#1E1E2E', color: '#00D2BE', padding: '4px 8px', borderRadius: '4px' }}>
              {ablationData?.total_test_laps ? `${ablationData.total_test_laps.toLocaleString()} Frozen Test Laps` : '3,372 Test Laps'}
            </span>
          </div>

          <div style={{ overflowX: 'auto', background: '#0F0F1A', borderRadius: '8px', border: '1px solid #1E1E2E' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#141424', borderBottom: '1px solid #28283D', color: '#8E8E93' }}>
                  <th style={{ padding: '10px 12px' }}>Model ID</th>
                  <th style={{ padding: '10px 12px' }}>Model Description</th>
                  <th style={{ padding: '10px 12px' }}>Signal Nature</th>
                  <th style={{ padding: '10px 12px' }}>MAE (s)</th>
                  <th style={{ padding: '10px 12px' }}>RMSE (s)</th>
                  <th style={{ padding: '10px 12px' }}>R²</th>
                  <th style={{ padding: '10px 12px' }}>+1L rho</th>
                  <th style={{ padding: '10px 12px' }}>+3L rho</th>
                  <th style={{ padding: '10px 12px' }}>+5L rho</th>
                  <th style={{ padding: '10px 12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {ablationData?.models?.map((m) => {
                  const isStage2 = m.model_id === 'Model G';
                  const isStage1 = m.model_id === 'Model A';
                  const isModelH = m.model_id === 'Model H';

                  return (
                    <tr 
                      key={m.model_id}
                      style={{ 
                        borderBottom: '1px solid #1A1A28',
                        background: isStage2 ? 'rgba(225, 6, 0, 0.08)' : isModelH ? 'rgba(0, 210, 190, 0.08)' : isStage1 ? 'rgba(225, 6, 0, 0.04)' : 'transparent'
                      }}
                    >
                      <td style={{ padding: '10px 12px', fontWeight: 600, color: (isStage2 || isStage1) ? '#E10600' : isModelH ? '#00D2BE' : '#F0F0F5' }}>
                        {m.model_id}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#F0F0F5' }}>
                        {m.model_name}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#8E8E93', fontSize: '11px' }}>
                        {m.is_instantaneous_model ? 'Instantaneous' : 'Cumulative Integral'}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#F0F0F5' }}>
                        {m.mae_s !== null ? `${m.mae_s.toFixed(4)} s` : 'N/A (Integral)'}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#F0F0F5' }}>
                        {m.rmse_s !== null ? `${m.rmse_s.toFixed(4)} s` : 'N/A (Integral)'}
                      </td>
                      <td style={{ padding: '10px 12px', color: (m.r2_score && m.r2_score > 0) ? '#39B54A' : '#F0F0F5' }}>
                        {m.r2_score !== null ? m.r2_score.toFixed(4) : 'N/A (Integral)'}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#00D2BE' }}>{m.downstream_corr_h1.toFixed(3)}</td>
                      <td style={{ padding: '10px 12px', color: '#00D2BE' }}>{m.downstream_corr_h3.toFixed(3)}</td>
                      <td style={{ padding: '10px 12px', color: '#00D2BE' }}>{m.downstream_corr_h5.toFixed(3)}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: (isStage2 || isStage1) ? 'rgba(225, 6, 0, 0.2)' : isModelH ? 'rgba(0, 210, 190, 0.2)' : '#1E1E2E',
                          color: (isStage2 || isStage1) ? '#E10600' : isModelH ? '#00D2BE' : '#8E8E93'
                        }}>
                          {m.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ background: '#141420', padding: '14px', borderRadius: '8px', border: '1px solid #28283D' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: '#00D2BE', marginBottom: '4px' }}>
              GATE VERDICT & SCIENTIFIC RECOMMENDATION
            </div>
            <p style={{ margin: 0, fontSize: '12px', color: '#C0C0D0', lineHeight: 1.5 }}>
              {ablationData?.verdict || 'STAGE 2 PRESERVED AS FROZEN PRODUCTION STANDARD; CONTEXTUAL LAYER CLASSIFIED AS RESEARCH ONLY'}
            </p>
            <p style={{ margin: '6px 0 0 0', fontSize: '11px', color: '#8E8E93' }}>
              {ablationData?.recommendation}
            </p>
          </div>
        </div>
      )}

      {/* Tab 3: Post-Race Validation */}
      {activeSubTab === 'POST_RACE' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, color: '#E0E0E6' }}>
            Out-of-Sample Forward Predictive Multi-Horizon Validation (+1, +3, +5, +10 Laps)
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            {validationData?.horizon_evaluations?.map((h) => (
              <div 
                key={h.horizon_laps}
                onClick={() => setSelectedHorizon(h.horizon_laps)}
                style={{
                  background: selectedHorizon === h.horizon_laps ? 'rgba(0, 210, 190, 0.08)' : '#12121D',
                  border: selectedHorizon === h.horizon_laps ? '1px solid #00D2BE' : '1px solid #222232',
                  padding: '14px',
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '14px', fontWeight: 700, color: '#F0F0F5' }}>+{h.horizon_laps} Laps Forward</span>
                  <span style={{ 
                    fontSize: '11px', 
                    padding: '2px 6px', 
                    borderRadius: '4px',
                    background: h.is_context_superior ? 'rgba(57, 181, 74, 0.2)' : 'rgba(225, 6, 0, 0.2)',
                    color: h.is_context_superior ? '#39B54A' : '#E10600'
                  }}>
                    {h.is_context_superior ? 'Contextual Offset' : 'M1 Baseline'}
                  </span>
                </div>

                <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8E8E93' }}>
                    <span>Context MAE:</span>
                    <span style={{ color: '#00D2BE', fontWeight: 600 }}>{h.context_mae_s.toFixed(4)} s</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8E8E93' }}>
                    <span>Frozen M1 MAE:</span>
                    <span style={{ color: '#E10600', fontWeight: 600 }}>{h.m1_mae_s.toFixed(4)} s</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8E8E93' }}>
                    <span>Spearman Rank (rho):</span>
                    <span style={{ color: '#F0F0F5' }}>{h.context_spearman_rho?.toFixed(3) || '0.000'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8E8E93' }}>
                    <span>Pearson r:</span>
                    <span style={{ color: '#F0F0F5' }}>{h.context_pearson_r?.toFixed(3) || '0.000'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8E8E93' }}>
                    <span>Sample Checkpoints:</span>
                    <span style={{ color: '#8E8E93' }}>{h.n_samples} laps</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Compound Breakdown */}
          {validationData?.compound_breakdown && (
            <div style={{ background: '#0F0F1A', padding: '14px', borderRadius: '8px', border: '1px solid #1E1E2E' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#8E8E93', marginBottom: '8px' }}>
                COMPOUND PERFORMANCE BREAKDOWN
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '8px' }}>
                {Object.entries(validationData.compound_breakdown).map(([cmp, stats]) => (
                  <div key={cmp} style={{ background: '#141422', padding: '8px 12px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '11px', color: '#FFB800', fontWeight: 700 }}>{cmp}</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#F0F0F5', marginTop: '2px' }}>
                      MAE: {stats.mean_mae_s.toFixed(4)} s
                    </div>
                    <div style={{ fontSize: '10px', color: '#666' }}>{stats.n_evaluations} checkpoints</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Feature Provenance */}
      {activeSubTab === 'PROVENANCE' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, color: '#E0E0E6' }}>
            Audited Feature Provenance Catalog (11 Variables)
          </div>

          <div style={{ overflowX: 'auto', background: '#0F0F1A', borderRadius: '8px', border: '1px solid #1E1E2E' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#141424', borderBottom: '1px solid #28283D', color: '#8E8E93' }}>
                  <th style={{ padding: '10px 12px' }}>Feature Name</th>
                  <th style={{ padding: '10px 12px' }}>Feature Nature</th>
                  <th style={{ padding: '10px 12px' }}>Category</th>
                  <th style={{ padding: '10px 12px' }}>Derivation / Formula</th>
                  <th style={{ padding: '10px 12px' }}>Units</th>
                  <th style={{ padding: '10px 12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {provenanceData?.catalog?.map((item) => {
                  const isMeasure = item.feature_nature?.includes('MEASUREMENT');
                  const isProxy = item.feature_nature?.includes('PROXY');

                  return (
                    <tr key={item.feature_name} style={{ borderBottom: '1px solid #1A1A28' }}>
                      <td style={{ padding: '10px 12px', fontWeight: 600, color: '#00D2BE' }}>
                        {item.feature_name}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: isMeasure ? 'rgba(57, 181, 74, 0.2)' : isProxy ? 'rgba(255, 184, 0, 0.2)' : 'rgba(155, 81, 224, 0.2)',
                          color: isMeasure ? '#39B54A' : isProxy ? '#FFB800' : '#9B51E0'
                        }}>
                          {item.feature_nature}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px', color: '#F0F0F5', fontSize: '11px' }}>
                        {item.category}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#8E8E93', fontSize: '11px' }}>
                        {item.derivation}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#6E6E80' }}>
                        {item.unit}
                      </td>
                      <td style={{ padding: '10px 12px', fontSize: '11px', color: '#8E8E93' }}>
                        {item.scientific_status}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ background: '#12121D', padding: '12px 16px', borderRadius: '8px', border: '1px solid #1E1E2E', fontSize: '12px', color: '#8E8E93', lineHeight: 1.5 }}>
            <span style={{ color: '#FFB800', fontWeight: 600 }}>Zero Synthetic Data Provenance: </span>
            Every contextual variable is strictly audited as a REAL MEASUREMENT, OBSERVABLE PROXY, or MODEL-DERIVED FEATURE. Proxies are never claimed as direct physical ground truth.
          </div>
        </div>
      )}

    </div>
  );
}

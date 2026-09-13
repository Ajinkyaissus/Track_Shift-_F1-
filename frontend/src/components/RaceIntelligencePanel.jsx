import React, { useState, useEffect, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine
} from 'recharts';
import { useCircuit } from '../context/CircuitContext';
import { CountryFlag } from '../utils/countryFlags';
import { getRaceIntelligence, getRaceIntelligenceStrategy } from '../api';

function getCompoundBadgeColor(comp) {
  const c = (comp || '').toUpperCase();
  if (c === 'SOFT') return '#E10600';
  if (c === 'MEDIUM') return '#FFB800';
  if (c === 'HARD') return '#FFFFFF';
  if (c === 'INTERMEDIATE') return '#39B54A';
  if (c === 'WET') return '#00AEEF';
  return '#888888';
}

export default function RaceIntelligencePanel() {
  const {
    selectedCircuit,
    selectedSession,
    selectedDriver,
    comparisonDriver,
    selectDriver,
    selectComparisonDriver,
    replayLap,
    raceIntelligenceData
  } = useCircuit();

  // Primary sub-view tabs inside Race Intelligence
  const [activeSubTab, setActiveSubTab] = useState('TYRE_OUTLOOK'); // 'TYRE_OUTLOOK' | 'PROJECTION' | 'STRATEGY' | 'BRAKING_THROTTLE' | 'TDSM_STATE' | 'EXPLANATION' | 'VALIDATION'
  
  const [liveData, setLiveData] = useState(raceIntelligenceData);
  const [loading, setLoading] = useState(false);
  const [strategyCompare, setStrategyCompare] = useState(null);

  // Sync / fetch live race intelligence when session, selectedDriver, or replayLap changes
  useEffect(() => {
    if (!selectedSession) return;
    setLoading(true);
    getRaceIntelligence(selectedSession, selectedDriver, replayLap)
      .then(res => {
        setLiveData(res);
        setLoading(false);
      })
      .catch(err => {
        console.warn("Race intelligence fetch error:", err);
        setLoading(false);
      });
  }, [selectedSession, selectedDriver, replayLap]);

  // Load strategy comparison between Driver A & Driver B
  useEffect(() => {
    if (!selectedSession || !selectedDriver || !comparisonDriver) {
      setStrategyCompare(null);
      return;
    }
    getRaceIntelligenceStrategy(selectedSession, selectedDriver, comparisonDriver)
      .then(setStrategyCompare)
      .catch(() => setStrategyCompare(null));
  }, [selectedSession, selectedDriver, comparisonDriver]);

  const driversList = useMemo(() => {
    if (!liveData?.drivers_ranking) return [];
    const list = [...liveData.drivers_ranking];

    return list.sort((a, b) => {
      const debtA = a.tyre_intelligence?.cumulative_tyre_debt_sec || 0;
      const debtB = b.tyre_intelligence?.cumulative_tyre_debt_sec || 0;
      return debtB - debtA;
    });
  }, [liveData]);

  const activeDriverData = useMemo(() => {
    if (!driversList.length) return null;
    return driversList.find(d => d.driver_id === selectedDriver) || driversList[0];
  }, [driversList, selectedDriver]);

  const comparisonDriverData = useMemo(() => {
    if (!driversList.length || !comparisonDriver) return null;
    return driversList.find(d => d.driver_id === comparisonDriver) || null;
  }, [driversList, comparisonDriver]);

  // Chart data for full-race lap-by-lap projection
  const raceProjectionChartData = useMemo(() => {
    if (!activeDriverData?.strategy_projection?.lap_projections) return [];
    const projA = activeDriverData.strategy_projection.lap_projections;
    const projB = comparisonDriverData?.strategy_projection?.lap_projections || [];

    return projA.map((p, idx) => {
      const pB = projB[idx];
      return {
        lap: p.lap,
        lap_time_a: p.projected_lap_time,
        lap_time_b: pB ? pB.projected_lap_time : null,
        lapTimeA: p.projected_lap_time,
        lapTimeB: pB ? pB.projected_lap_time : null,
        gap_delta: pB ? Number((pB.cumulative_time_sec - p.cumulative_time_sec).toFixed(2)) : null,
        compoundA: p.compound,
        isPitA: p.is_pit_lap
      };
    });
  }, [activeDriverData, comparisonDriverData]);

  if (loading && !liveData) {
    return (
      <div className="race-intelligence-loading">
        <div className="loading-spinner"></div>
        <p>Computing Universal Race Intelligence across full field...</p>
      </div>
    );
  }

  return (
    <div className="race-intelligence-panel">
      {/* 1. Header with Metadata & Security Status */}
      <div className="ri-header-bar">
        <div className="ri-header-title">
          <h2>Race Intelligence Engine</h2>
          <span className="ri-version-badge">TDSM PROJECTION v2.0</span>
          {loading && <span className="ri-loading-pill">CALCULATING...</span>}
        </div>
        <div className="ri-meta-badges">
          <span className="meta-tag">TRACK: <strong>{selectedCircuit?.toUpperCase() || 'UNKNOWN'}</strong></span>
          <span className="meta-tag">LAP: <strong>{replayLap || 1}</strong></span>
          🔒 FINGERPRINT: <code>{liveData?.frozen_snapshot?.fingerprint_hash || 'VERIFIED'}</code>
        </div>
      </div>

      {/* 2. Sub-Navigation Bar */}
      <div className="ri-subnav-bar">
        <button
          className={`ri-subtab-btn ${activeSubTab === 'TYRE_OUTLOOK' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('TYRE_OUTLOOK')}
        >
          🛞 TYRE OUTLOOK & DEBT ({driversList.filter(d => d.status === 'AVAILABLE').length}/{driversList.length})
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'PROJECTION' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('PROJECTION')}
        >
          🏁 FULL-RACE PROJECTION
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'STRATEGY' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('STRATEGY')}
        >
          🔧 STRATEGY ENGINE
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'BRAKING_THROTTLE' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('BRAKING_THROTTLE')}
        >
          🛑 BRAKING & THROTTLE
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'TDSM_STATE' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('TDSM_STATE')}
        >
          🧠 TDSM STATE & FORECAST
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'EXPLANATION' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('EXPLANATION')}
        >
          🎯 EXPLANATION
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'VALIDATION' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('VALIDATION')}
        >
          ✅ POST-RACE VALIDATION
        </button>
      </div>

      {/* 3. Main Content Body by Sub-Tab */}
      <div className="ri-body-content">

        {/* SUBTAB 2: TYRE OUTLOOK & COMPOUND INTELLIGENCE */}
        {activeSubTab === 'TYRE_OUTLOOK' && (
          <div className="ri-tyre-view">
            <div className="ri-cards-grid">
              {driversList.filter(d => d.status === 'AVAILABLE').map(drv => {
                const t = drv.tyre_intelligence;
                const isSelected = drv.driver_id === selectedDriver;
                const isComp = drv.driver_id === comparisonDriver;

                return (
                  <div 
                    key={drv.driver_id} 
                    className={`ri-card ${isSelected ? 'selected' : ''}`}
                    style={{ 
                      cursor: 'pointer',
                      border: isSelected ? '1px solid var(--accent-red)' : (isComp ? '1px solid #38bdf8' : undefined),
                      boxShadow: isSelected ? '0 0 12px rgba(225, 6, 0, 0.35)' : undefined
                    }}
                    onClick={() => selectDriver(drv.driver_id)}
                  >
                    <div className="ri-card-header">
                      <div className="card-driver-title">
                        <CountryFlag code={drv.country_code} size="sm" />
                        <h3>{drv.driver_id} • {drv.name}</h3>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          className="vs-compare-btn"
                          title="Set as comparison driver"
                          onClick={(e) => {
                            e.stopPropagation();
                            selectComparisonDriver(drv.driver_id);
                          }}
                          style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: isComp ? '#0284c7' : '#1e293b',
                            color: '#fff',
                            border: '1px solid #38bdf8'
                          }}
                        >
                          {isComp ? 'COMPARING' : 'VS'}
                        </button>
                        <span 
                          className="compound-pill"
                          style={{ backgroundColor: getCompoundBadgeColor(t?.current_compound) }}
                        >
                          {t?.current_compound}
                        </span>
                      </div>
                    </div>

                    <div className="ri-card-body">
                      <div className="metric-row">
                        <span>Current Tyre Age:</span>
                        <strong>{t?.current_tyre_age} Laps</strong>
                      </div>
                      <div className="metric-row">
                        <span>Estimated Degradation:</span>
                        <strong>{t?.estimated_deg_rate_sec_per_lap} s/lap</strong>
                      </div>
                      <div className="metric-row">
                        <span>Cumulative Tyre Debt:</span>
                        <strong className="debt-highlight">{t?.cumulative_tyre_debt_sec}s</strong>
                      </div>
                      <div className="metric-row">
                        <span>Competitive Life Remaining:</span>
                        <strong>{t?.competitive_life_remaining_laps} Laps</strong>
                      </div>
                      <div className="metric-row">
                        <span>Model Confidence (95% CI):</span>
                        <span>[{t?.ci_95?.[0]}s, {t?.ci_95?.[1]}s]</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* SUBTAB 3: FULL-RACE PROJECTION CHART */}
        {activeSubTab === 'PROJECTION' && (
          <div className="ri-projection-view">
            <div className="chart-header-row">
              <h3>Full-Race Projected Lap Time & Cumulative Gap Progression</h3>
              <div className="chart-legend-box">
                <span className="dot dot-a"></span> {activeDriverData?.driver_id || 'Driver A'}
                {comparisonDriverData && (
                  <>
                    <span className="dot dot-b"></span> {comparisonDriverData.driver_id}
                  </>
                )}
              </div>
            </div>

            <div className="chart-container-box" style={{ height: '360px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={raceProjectionChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#22272e" />
                  <XAxis dataKey="lap" stroke="#8b949e" label={{ value: 'Race Lap Number', position: 'insideBottom', offset: -5 }} />
                  <YAxis stroke="#8b949e" domain={['auto', 'auto']} label={{ value: 'Projected Lap Time (s)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip contentStyle={{ backgroundColor: '#0d1117', borderColor: '#30363d', color: '#c9d1d9' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#E10600" strokeDasharray="4 4" label="Replay Lap" />
                  <Line type="monotone" dataKey="lap_time_a" stroke="#00D2BE" strokeWidth={2.5} dot={false} name={`${activeDriverData?.driver_id} Projected Pace`} />
                  {comparisonDriverData && (
                    <Line type="monotone" dataKey="lap_time_b" stroke="#FF8700" strokeWidth={2} strokeDasharray="5 5" dot={false} name={`${comparisonDriverData.driver_id} Projected Pace`} />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* SUBTAB 4: STRATEGY ENGINE */}
        {activeSubTab === 'STRATEGY' && (
          <div className="ri-strategy-view">
            {strategyCompare ? (
              <div className="strategy-compare-box">
                <h3>Multi-Driver Strategy Evaluation: {strategyCompare.driver_a.driver_id} VS {strategyCompare.driver_b.driver_id}</h3>
                <div className="strategy-grid">
                  <div className="strategy-card">
                    <h4>{strategyCompare.driver_a.name} ({strategyCompare.driver_a.driver_id})</h4>
                    <p>Optimal: <strong>{strategyCompare.driver_a.strategy?.optimal_strategy}</strong></p>
                    <p>Pit Delta Loss: <strong>{strategyCompare.driver_a.strategy?.pit_loss_sec}s</strong></p>
                    <div className="stints-list">
                      {strategyCompare.driver_a.strategy?.strategy_options?.map((opt, i) => (
                        <div key={i} className="stint-opt-item">
                          <span>{opt.strategy_name}</span>
                          <strong>{opt.estimated_race_time_sec}s ({opt.stops_count} stop)</strong>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="strategy-card">
                    <h4>{strategyCompare.driver_b.name} ({strategyCompare.driver_b.driver_id})</h4>
                    <p>Optimal: <strong>{strategyCompare.driver_b.strategy?.optimal_strategy}</strong></p>
                    <p>Pit Delta Loss: <strong>{strategyCompare.driver_b.strategy?.pit_loss_sec}s</strong></p>
                    <div className="stints-list">
                      {strategyCompare.driver_b.strategy?.strategy_options?.map((opt, i) => (
                        <div key={i} className="stint-opt-item">
                          <span>{opt.strategy_name}</span>
                          <strong>{opt.estimated_race_time_sec}s ({opt.stops_count} stop)</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="strategy-fallback-box">
                <p>Select a second driver in the Leaderboard or Tyre Outlook to compare tactical strategies.</p>
              </div>
            )}
          </div>
        )}

        {/* SUBTAB 5: BRAKING & THROTTLE METRICS */}
        {activeSubTab === 'BRAKING_THROTTLE' && (
          <div className="ri-braking-view">
            <h3>Braking & Throttle Cornering Fingerprints</h3>
            <div className="corner-metrics-grid">
              {activeDriverData?.braking_throttle_profile?.corners?.map((c, i) => (
                <div key={i} className="corner-card">
                  <h4>Corner #{c.corner_number}</h4>
                  <p>Min Speed: <strong>{c.min_speed_kph} km/h</strong></p>
                  <p>Brake Onset: <strong>{c.brake_point_m}m</strong></p>
                  <p>Throttle Aggression: <strong>{c.throttle_application_pct}%</strong></p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SUBTAB 6: TDSM STATE & FORECAST */}
        {activeSubTab === 'TDSM_STATE' && (
          <div className="ri-tcn-view">
            <div className="tcn-status-box">
              <h3>TDSM State-Space Transitions & Forecasts</h3>
              <p>State-space representations S_t = [D_t, ΔD_t, Δ²D_t] and multi-horizon predictions evaluated across active session drivers.</p>
            </div>

            <div className="tcn-embeddings-grid">
              {driversList.filter(d => d.status === 'AVAILABLE').map(drv => {
                const isSelected = drv.driver_id === selectedDriver;
                const debt = drv.tyre_intelligence?.cumulative_tyre_debt_sec ?? 0;
                const predFinish = drv.expected_finish ?? '—';
                const degRate = drv.tyre_intelligence?.estimated_deg_rate_sec_per_lap;

                return (
                  <div key={drv.driver_id} className="tcn-driver-card" style={{ borderColor: isSelected ? 'var(--accent-red)' : '#1e2230' }}>
                    <div className="tcn-card-head">
                      <CountryFlag code={drv.country_code} size="sm" />
                      <h4>{drv.driver_id} • {drv.name}</h4>
                      <span className={`status-pill ${isSelected ? 'available' : 'default'}`}>{isSelected ? 'SELECTED' : 'IN ROSTER'}</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px', marginTop: '8px' }}>
                      <div style={{ background: '#12141F', padding: '6px', borderRadius: '4px' }}>
                        <span style={{ color: '#64748B' }}>Observed Debt: </span>
                        <strong style={{ color: debt >= 0 ? '#F87171' : '#34D399', fontFamily: 'monospace' }}>+{debt.toFixed(3)}s</strong>
                      </div>
                      <div style={{ background: '#12141F', padding: '6px', borderRadius: '4px' }}>
                        <span style={{ color: '#64748B' }}>Exp Finish: </span>
                        <strong style={{ color: '#FBBF24' }}>P{predFinish}</strong>
                      </div>
                      <div style={{ background: '#12141F', padding: '6px', borderRadius: '4px' }}>
                        <span style={{ color: '#64748B' }}>Deg Rate: </span>
                        <strong style={{ color: '#00D2BE' }}>{degRate != null ? `${degRate.toFixed(3)}s/l` : '—'}</strong>
                      </div>
                      <div style={{ background: '#12141F', padding: '6px', borderRadius: '4px' }}>
                        <span style={{ color: '#64748B' }}>Model Head: </span>
                        <strong style={{ color: '#A78BFA' }}>TDSM v2.0</strong>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* SUBTAB 7: TRANSPARENT PREDICTION EXPLANATION */}
        {activeSubTab === 'EXPLANATION' && (
          <div className="ri-explanation-view">
            <h3>Prediction Explanation for {activeDriverData?.name} ({activeDriverData?.driver_id})</h3>
            <p className="expl-summary">{activeDriverData?.explanation?.summary}</p>

            <div className="waterfall-box">
              {activeDriverData?.explanation?.contributions?.map((item, idx) => (
                <div key={idx} className="waterfall-row">
                  <div className="factor-name">{item.factor}</div>
                  <div className="factor-bar-box">
                    <div className="factor-bar-fill" style={{ width: `${Math.min(100, item.weight * 60)}%` }}></div>
                  </div>
                  <div className="factor-impact">{item.impact}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SUBTAB 8: POST-RACE VALIDATION SCORECARD */}
        {activeSubTab === 'VALIDATION' && (
          <div className="ri-validation-view">
            <div className="validation-scorecard-header">
              <h3>Post-Race Immutable Validation Scorecard</h3>
              <p>Compares frozen pre-race predictions against actual observed finishing classifications.</p>
            </div>

            {liveData?.post_race_validation?.status === 'VALIDATION_AVAILABLE' ? (
              <div className="val-metrics-grid">
                <div className="val-stat-card">
                  <span className="stat-label">FINISHING POSITION MAE:</span>
                  <strong className="stat-val">{liveData.post_race_validation.finishing_position_mae} POSITIONS</strong>
                </div>
                <div className="val-stat-card">
                  <span className="stat-label">DEGRADATION TRACKING:</span>
                  <strong className="stat-val hit">VERIFIED CAUSAL</strong>
                </div>
              </div>
            ) : (
              <div className="val-pending-notice">
                <p>Validation metrics are automatically calculated when actual race results are recorded in the database.</p>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

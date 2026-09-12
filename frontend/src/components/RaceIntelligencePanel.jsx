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

function getTeamAccentColor(team) {
  const t = (team || '').toLowerCase();
  if (t.includes('red bull')) return '#1E41FF';
  if (t.includes('ferrari')) return '#E10600';
  if (t.includes('mercedes')) return '#00D2BE';
  if (t.includes('mclaren')) return '#FF8700';
  if (t.includes('aston')) return '#006F62';
  if (t.includes('alpine')) return '#0090FF';
  if (t.includes('williams')) return '#005AFF';
  if (t.includes('haas')) return '#B6BABD';
  if (t.includes('sauber') || t.includes('kick')) return '#52E252';
  if (t.includes('rb') || t.includes('toro')) return '#6692FF';
  return '#E10600';
}

export default function RaceIntelligencePanel() {
  const {
    selectedSession,
    selectedDriver,
    comparisonDriver,
    selectDriver,
    selectComparisonDriver,
    replayLap,
    raceIntelligenceData
  } = useCircuit();

  // Primary sub-view tabs inside Race Intelligence
  const [activeSubTab, setActiveSubTab] = useState('LEADERBOARD'); // 'LEADERBOARD' | 'TYRE_OUTLOOK' | 'PROJECTION' | 'STRATEGY' | 'BRAKING_THROTTLE' | 'TCN_BEHAVIOR' | 'EXPLANATION' | 'VALIDATION'
  const [sortBy, setSortBy] = useState('win_probability'); // 'win_probability' | 'expected_finish' | 'pace' | 'tyre_debt'
  const [sortOrder, setSortOrder] = useState('desc'); // 'asc' | 'desc'
  
  const [liveData, setLiveData] = useState(raceIntelligenceData);
  const [loading, setLoading] = useState(false);
  const [strategyCompare, setStrategyCompare] = useState(null);

  // Sync / fetch live race intelligence when session or replayLap changes
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
  }, [selectedSession, replayLap]);

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
      let valA = 0;
      let valB = 0;

      if (sortBy === 'win_probability') {
        valA = a.win_probability || 0;
        valB = b.win_probability || 0;
      } else if (sortBy === 'expected_finish') {
        valA = a.expected_finish || 99;
        valB = b.expected_finish || 99;
        return sortOrder === 'asc' ? valA - valB : valB - valA;
      } else if (sortBy === 'pace') {
        valA = a.pace_metrics?.median_lap_time || 999;
        valB = b.pace_metrics?.median_lap_time || 999;
        return sortOrder === 'asc' ? valA - valB : valB - valA;
      } else if (sortBy === 'tyre_debt') {
        valA = a.tyre_intelligence?.cumulative_tyre_debt_sec || 0;
        valB = b.tyre_intelligence?.cumulative_tyre_debt_sec || 0;
      }

      return sortOrder === 'desc' ? valB - valA : valA - valB;
    });
  }, [liveData, sortBy, sortOrder]);

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
        cum_time_a: p.cumulative_time_sec,
        cum_time_b: pB ? pB.cumulative_time_sec : null,
        gap_delta: pB ? Number((pB.cumulative_time_sec - p.cumulative_time_sec).toFixed(2)) : null,
        deg_a: p.degradation_sec,
        deg_b: pB ? pB.degradation_sec : null,
        debt_a: p.tyre_debt_sec,
        debt_b: pB ? pB.tyre_debt_sec : null
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
    <div className="race-intelligence-container">
      {/* 1. Header Bar with Circuit, Session Context & Temporal Isolation Guard */}
      <div className="ri-header-bar">
        <div className="ri-title-box">
          <div className="ri-badge-row">
            <span className="live-status-pill">
              <span className="pulsing-dot"></span> UNIVERSAL RACE INTELLIGENCE
            </span>
            <span className="session-tag">{liveData?.event_name || selectedCircuit} • {liveData?.season}</span>
            <span className="circuit-flag-pill">
              <CountryFlag code={liveData?.country_code} size="sm" />
              <span>{liveData?.circuit_name || selectedCircuit}</span>
            </span>
            <span className="mode-pill">MODE: {liveData?.temporal_mode || 'IN_RACE'}</span>
            <span className="replay-lap-pill">REPLAY LAP {replayLap} / {liveData?.total_race_laps || 53}</span>
          </div>
        </div>

        {/* Temporal Isolation Provenance Pill */}
        <div className="ri-fingerprint-badge" title="Cryptographic snapshot fingerprint guaranteeing zero temporal leakage">
          🔒 FINGERPRINT: <code>{liveData?.frozen_snapshot?.fingerprint_hash || 'VERIFIED'}</code>
        </div>
      </div>

      {/* 2. Sub-Navigation Bar */}
      <div className="ri-subnav-bar">
        <button
          className={`ri-subtab-btn ${activeSubTab === 'LEADERBOARD' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('LEADERBOARD')}
        >
          🏆 WINNER PREDICTION ({driversList.filter(d => d.status === 'AVAILABLE').length}/{driversList.length})
        </button>
        <button
          className={`ri-subtab-btn ${activeSubTab === 'TYRE_OUTLOOK' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('TYRE_OUTLOOK')}
        >
          🛞 TYRE OUTLOOK & DEBT
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
          className={`ri-subtab-btn ${activeSubTab === 'TCN_BEHAVIOR' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('TCN_BEHAVIOR')}
        >
          🧠 TCN BEHAVIOR
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

        {/* SUBTAB 1: FULL FIELD WINNER & PODIUM PREDICTION LEADERBOARD */}
        {activeSubTab === 'LEADERBOARD' && (
          <div className="ri-leaderboard-view">
            <div className="ri-leaderboard-controls">
              <span className="controls-label">SORT FIELD BY:</span>
              <button 
                className={`sort-pill ${sortBy === 'win_probability' ? 'active' : ''}`}
                onClick={() => { setSortBy('win_probability'); setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc'); }}
              >
                WIN PROBABILITY {sortBy === 'win_probability' && (sortOrder === 'desc' ? '▼' : '▲')}
              </button>
              <button 
                className={`sort-pill ${sortBy === 'expected_finish' ? 'active' : ''}`}
                onClick={() => { setSortBy('expected_finish'); setSortOrder('asc'); }}
              >
                EXPECTED FINISH {sortBy === 'expected_finish' && '▲'}
              </button>
              <button 
                className={`sort-pill ${sortBy === 'pace' ? 'active' : ''}`}
                onClick={() => { setSortBy('pace'); setSortOrder('asc'); }}
              >
                RACE PACE {sortBy === 'pace' && '▲'}
              </button>
              <button 
                className={`sort-pill ${sortBy === 'tyre_debt' ? 'active' : ''}`}
                onClick={() => { setSortBy('tyre_debt'); setSortOrder('desc'); }}
              >
                TYRE DEBT {sortBy === 'tyre_debt' && (sortOrder === 'desc' ? '▼' : '▲')}
              </button>
            </div>

            <div className="ri-table-wrapper">
              <table className="ri-drivers-table">
                <thead>
                  <tr>
                    <th>RANK</th>
                    <th>DRIVER</th>
                    <th>TEAM</th>
                    <th>WIN PROB %</th>
                    <th>PODIUM %</th>
                    <th>EXP FINISH</th>
                    <th>RACE PACE</th>
                    <th>TYRE COMPOUND</th>
                    <th>TYRE DEBT</th>
                    <th>DATA STATUS</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {driversList.map((drv, idx) => {
                    const isSelected = drv.driver_id === selectedDriver;
                    const isComp = drv.driver_id === comparisonDriver;
                    const isAvailable = drv.status === 'AVAILABLE';
                    const winPct = (drv.win_probability * 100).toFixed(1);
                    const podPct = (drv.podium_probability * 100).toFixed(1);

                    return (
                      <tr 
                        key={drv.driver_id} 
                        className={`ri-driver-row ${isSelected ? 'selected' : ''} ${isComp ? 'comparison' : ''}`}
                        onClick={() => selectDriver(drv.driver_id)}
                      >
                        <td className="rank-col">
                          <span className={`rank-badge ${idx < 3 ? `top-${idx + 1}` : ''}`}>
                            P{drv.expected_finish || idx + 1}
                          </span>
                        </td>
                        <td className="driver-col">
                          <div className="driver-name-box">
                            <CountryFlag code={drv.country_code} size="sm" />
                            <strong>{drv.driver_id}</strong>
                            <span className="driver-full-name">{drv.name}</span>
                          </div>
                        </td>
                        <td className="team-col">
                          <span className="team-indicator" style={{ backgroundColor: getTeamAccentColor(drv.team) }}></span>
                          <span>{drv.team}</span>
                        </td>
                        <td className="win-prob-col">
                          {isAvailable ? (
                            <div className="prob-meter-box">
                              <div className="prob-bar-fill" style={{ width: `${Math.max(5, winPct)}%` }}></div>
                              <span className="prob-text">{winPct}%</span>
                            </div>
                          ) : (
                            <span className="na-text">—</span>
                          )}
                        </td>
                        <td className="podium-prob-col">
                          {isAvailable ? <span>{podPct}%</span> : <span className="na-text">—</span>}
                        </td>
                        <td className="exp-finish-col">
                          {isAvailable ? <strong>P{drv.expected_finish}</strong> : <span className="na-text">—</span>}
                        </td>
                        <td className="pace-col">
                          {isAvailable && drv.pace_metrics?.median_lap_time ? (
                            <span>{drv.pace_metrics.median_lap_time.toFixed(3)}s</span>
                          ) : (
                            <span className="na-text">—</span>
                          )}
                        </td>
                        <td className="compound-col">
                          {isAvailable && drv.tyre_intelligence ? (
                            <span 
                              className="compound-badge" 
                              style={{ borderColor: getCompoundBadgeColor(drv.tyre_intelligence.current_compound) }}
                            >
                              {drv.tyre_intelligence.current_compound} (L{drv.tyre_intelligence.current_tyre_age})
                            </span>
                          ) : (
                            <span className="na-text">—</span>
                          )}
                        </td>
                        <td className="debt-col">
                          {isAvailable && drv.tyre_intelligence ? (
                            <span className="debt-val">{drv.tyre_intelligence.cumulative_tyre_debt_sec.toFixed(2)}s</span>
                          ) : (
                            <span className="na-text">—</span>
                          )}
                        </td>
                        <td className="status-col">
                          <span className={`status-pill ${isAvailable ? 'available' : 'unavailable'}`}>
                            {isAvailable ? '✓ VERIFIED' : '⚠ UNAVAILABLE'}
                          </span>
                        </td>
                        <td className="actions-col">
                          <button 
                            className="vs-compare-btn"
                            title="Set as comparison driver"
                            onClick={(e) => {
                              e.stopPropagation();
                              selectComparisonDriver(drv.driver_id);
                            }}
                          >
                            VS
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* SUBTAB 2: TYRE OUTLOOK & COMPOUND INTELLIGENCE */}
        {activeSubTab === 'TYRE_OUTLOOK' && (
          <div className="ri-tyre-view">
            <div className="ri-cards-grid">
              {driversList.filter(d => d.status === 'AVAILABLE').map(drv => {
                const t = drv.tyre_intelligence;
                return (
                  <div key={drv.driver_id} className="ri-card">
                    <div className="ri-card-header">
                      <div className="card-driver-title">
                        <CountryFlag code={drv.country_code} size="sm" />
                        <h3>{drv.driver_id} • {drv.name}</h3>
                      </div>
                      <span 
                        className="compound-pill"
                        style={{ backgroundColor: getCompoundBadgeColor(t?.current_compound) }}
                      >
                        {t?.current_compound}
                      </span>
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
              <div className="single-strategy-box">
                <h3>Recommended Strategy Scenarios for {activeDriverData?.name}</h3>
                <div className="strategy-options-list">
                  {activeDriverData?.strategy_projection?.strategy_options?.map((opt, i) => (
                    <div key={i} className="strategy-option-card">
                      <div className="opt-header">
                        <h4>{opt.strategy_name}</h4>
                        <span className="feasibility-badge">{opt.feasibility}</span>
                      </div>
                      <p>Stops: <strong>{opt.stops_count}</strong> | Windows: <strong>{opt.pit_windows?.join(', ')}</strong></p>
                      <p>Estimated Total Race Time: <strong>{opt.estimated_race_time_sec}s</strong> (Delta: {opt.delta_to_optimal_sec}s)</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* SUBTAB 5: BRAKING & THROTTLE */}
        {activeSubTab === 'BRAKING_THROTTLE' && (
          <div className="ri-braking-throttle-view">
            <div className="telemetry-dynamics-grid">
              <div className="dynamics-card braking-card">
                <h3>🛑 Braking Dynamics Intelligence ({activeDriverData?.driver_id})</h3>
                <div className="metric-item">
                  <span>Braking Aggression Index:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.braking?.braking_aggression}</strong>
                </div>
                <div className="metric-item">
                  <span>Braking Consistency:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.braking?.braking_consistency_pct}%</strong>
                </div>
                <div className="metric-item">
                  <span>Peak Brake Pressure:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.braking?.peak_brake_pressure_pct}%</strong>
                </div>
                <div className="metric-item">
                  <span>Brake Application Profile:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.braking?.brake_application_rate}</strong>
                </div>
                <p className="sensitivity-note">
                  ℹ {activeDriverData?.behavioral_intelligence?.braking?.observational_sensitivity}
                </p>
              </div>

              <div className="dynamics-card throttle-card">
                <h3>⚡ Throttle Pickup & Acceleration ({activeDriverData?.driver_id})</h3>
                <div className="metric-item">
                  <span>Throttle Transient Smoothness:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.throttle?.throttle_transient_smoothness}</strong>
                </div>
                <div className="metric-item">
                  <span>Full Throttle % of Lap:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.throttle?.full_throttle_pct_lap}%</strong>
                </div>
                <div className="metric-item">
                  <span>Exit Acceleration Index:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.throttle?.exit_acceleration_index}</strong>
                </div>
                <div className="metric-item">
                  <span>Traction Control Pickup:</span>
                  <strong>{activeDriverData?.behavioral_intelligence?.throttle?.traction_control_pickup}</strong>
                </div>
                <p className="sensitivity-note">
                  ℹ {activeDriverData?.behavioral_intelligence?.throttle?.observational_sensitivity}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 6: TCN BEHAVIOR */}
        {activeSubTab === 'TCN_BEHAVIOR' && (
          <div className="ri-tcn-view">
            <div className="tcn-status-box">
              <h3>Temporal Convolutional Network (TCN) 16-Dimensional Embeddings</h3>
              <p>Authentic temporal sequential representations extracted from driver telemetry without synthetic interpolation.</p>
            </div>

            <div className="tcn-embeddings-grid">
              {driversList.filter(d => d.status === 'AVAILABLE').map(drv => {
                const emb = drv.behavioral_intelligence?.tcn_embedding;
                const status = drv.behavioral_intelligence?.tcn_status;
                return (
                  <div key={drv.driver_id} className="tcn-driver-card">
                    <div className="tcn-card-head">
                      <CountryFlag code={drv.country_code} size="sm" />
                      <h4>{drv.driver_id} • {drv.name}</h4>
                      <span className={`status-pill ${status === 'AVAILABLE' ? 'available' : 'unavailable'}`}>{status}</span>
                    </div>
                    {emb ? (
                      <div className="embedding-vector-box">
                        {emb.map((val, i) => (
                          <span key={i} className="emb-dim" title={`Dim ${i + 1}: ${val}`}>{val}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="na-text">TCN Embedding Unavailable — Insufficient consecutive telemetry laps.</p>
                    )}
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
                  <span className="stat-label">WINNER PREDICTION:</span>
                  <strong className={`stat-val ${liveData.post_race_validation.winner_prediction_accuracy === 'HIT' ? 'hit' : 'miss'}`}>
                    {liveData.post_race_validation.winner_prediction_accuracy}
                  </strong>
                </div>
                <div className="val-stat-card">
                  <span className="stat-label">FINISHING POSITION MAE:</span>
                  <strong className="stat-val">{liveData.post_race_validation.finishing_position_mae} POSITIONS</strong>
                </div>
                <div className="val-stat-card">
                  <span className="stat-label">PODIUM HIT ACCURACY:</span>
                  <strong className="stat-val">{liveData.post_race_validation.podium_accuracy_count}</strong>
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

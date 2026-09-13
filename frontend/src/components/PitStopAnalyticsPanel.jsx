import { useMemo, useState } from 'react';
import { useCircuit } from '../context/CircuitContext';

function getCompoundColor(comp) {
  const c = (comp || '').toUpperCase();
  if (c.startsWith('S') || c === 'SOFT') return '#E10600';
  if (c.startsWith('M') || c === 'MEDIUM') return '#FFB800';
  if (c.startsWith('H') || c === 'HARD') return '#FFFFFF';
  if (c.startsWith('I') || c === 'INTERMEDIATE') return '#39B54A';
  if (c.startsWith('W') || c === 'WET') return '#00AEEF';
  return '#888888';
}

function getCompoundShort(comp) {
  const c = (comp || '').toUpperCase();
  if (c.startsWith('S') || c === 'SOFT') return 'S';
  if (c.startsWith('M') || c === 'MEDIUM') return 'M';
  if (c.startsWith('H') || c === 'HARD') return 'H';
  if (c.startsWith('I') || c === 'INTERMEDIATE') return 'I';
  if (c.startsWith('W') || c === 'WET') return 'W';
  return c ? c[0] : '?';
}

export default function PitStopAnalyticsPanel() {
  const {
    sessionPitStops,
    selectedDriver,
    comparisonDriver,
    selectDriver
  } = useCircuit();

  const [activeTab, setActiveTab] = useState('strategy'); // 'strategy' | 'summary' | 'ranking' | 'h2h' | 'diagnostics'
  const [h2hDriverA, setH2hDriverA] = useState(() => selectedDriver || null);
  const [h2hDriverB, setH2hDriverB] = useState(() => comparisonDriver || null);

  const driversList = useMemo(() => {
    return sessionPitStops?.drivers || [];
  }, [sessionPitStops]);

  // Keep h2h drivers in sync when selectedDriver / comparisonDriver change
  useEffect(() => {
    if (selectedDriver && driversList.some(d => d.driver_id === selectedDriver)) {
      setH2hDriverA(selectedDriver);
    } else if (!h2hDriverA && driversList.length > 0) {
      setH2hDriverA(driversList[0].driver_id);
    }
  }, [selectedDriver, driversList, h2hDriverA]);

  useEffect(() => {
    if (comparisonDriver && driversList.some(d => d.driver_id === comparisonDriver)) {
      setH2hDriverB(comparisonDriver);
    } else if (driversList.length > 1 && (!h2hDriverB || h2hDriverB === h2hDriverA)) {
      const other = driversList.find(d => d.driver_id !== h2hDriverA);
      if (other) setH2hDriverB(other.driver_id);
    }
  }, [comparisonDriver, h2hDriverA, driversList, h2hDriverB]);

  // Summary Table Data (All Drivers)
  const summaryTableRows = useMemo(() => {
    return driversList.map(d => {
      const stops = d.pit_stops || [];
      const stopLaps = stops.map(s => s.lap).join(', ') || '—';
      const totalTime = stops.reduce((acc, s) => acc + (s.duration || 0), 0);
      const avgTime = stops.length > 0 ? totalTime / stops.length : 0;
      
      // Compute strategy string e.g. M → H → S
      let strat = '—';
      if (stops.length > 0) {
        const comps = [getCompoundShort(stops[0].compound_before)];
        stops.forEach(s => comps.push(getCompoundShort(s.compound_after)));
        strat = comps.join(' → ');
      }

      return {
        driver_id: d.driver_id,
        full_name: d.full_name || d.driver_id,
        team: d.team,
        team_color: d.team_color || '#E10600',
        stops_count: d.pit_stop_count || 0,
        laps: stopLaps,
        total_time: totalTime > 0 ? `${totalTime.toFixed(2)}s` : '—',
        avg_time: avgTime > 0 ? `${avgTime.toFixed(2)}s` : '—',
        strategy: strat,
        data_status: d.data_status || 'AVAILABLE'
      };
    });
  }, [driversList]);

  // Observed Pit Stop Ranking (Ranked by stationary duration)
  const observedRankings = useMemo(() => {
    const allStops = [];
    driversList.forEach(d => {
      (d.pit_stops || []).forEach(s => {
        if (s.duration && s.duration > 0) {
          allStops.push({
            driver_id: d.driver_id,
            full_name: d.full_name || d.driver_id,
            team: d.team,
            team_color: d.team_color || '#E10600',
            stop_number: s.stop_number,
            lap: s.lap,
            duration: s.duration,
            lane_duration: s.lane_duration,
            compound_before: s.compound_before,
            compound_after: s.compound_after,
            position_before: s.position_before,
            position_after: s.position_after,
            position_delta: s.position_delta
          });
        }
      });
    });

    allStops.sort((a, b) => a.duration - b.duration);
    return allStops;
  }, [driversList]);

  // Head-to-Head Comparison Data
  const h2hDataA = useMemo(() => driversList.find(d => d.driver_id === h2hDriverA) || null, [driversList, h2hDriverA]);
  const h2hDataB = useMemo(() => driversList.find(d => d.driver_id === h2hDriverB) || null, [driversList, h2hDriverB]);

  const h2hComparison = useMemo(() => {
    if (!h2hDataA || !h2hDataB) return null;

    const stopsA = h2hDataA.pit_stops || [];
    const stopsB = h2hDataB.pit_stops || [];

    const totalA = stopsA.reduce((acc, s) => acc + (s.duration || 0), 0);
    const totalB = stopsB.reduce((acc, s) => acc + (s.duration || 0), 0);

    const avgA = stopsA.length > 0 ? totalA / stopsA.length : 0;
    const avgB = stopsB.length > 0 ? totalB / stopsB.length : 0;

    const firstStopA = stopsA[0]?.lap ? `Lap ${stopsA[0].lap}` : 'None';
    const firstStopB = stopsB[0]?.lap ? `Lap ${stopsB[0].lap}` : 'None';

    const stratA = stopsA.length > 0 ? [getCompoundShort(stopsA[0].compound_before), ...stopsA.map(s => getCompoundShort(s.compound_after))].join(' → ') : '—';
    const stratB = stopsB.length > 0 ? [getCompoundShort(stopsB[0].compound_before), ...stopsB.map(s => getCompoundShort(s.compound_after))].join(' → ') : '—';

    return {
      driverA: h2hDataA,
      driverB: h2hDataB,
      stopsCountA: stopsA.length,
      stopsCountB: stopsB.length,
      firstStopA,
      firstStopB,
      totalTimeA: totalA > 0 ? `${totalA.toFixed(2)}s` : '—',
      totalTimeB: totalB > 0 ? `${totalB.toFixed(2)}s` : '—',
      avgTimeA: avgA > 0 ? `${avgA.toFixed(2)}s` : '—',
      avgTimeB: avgB > 0 ? `${avgB.toFixed(2)}s` : '—',
      stratA,
      stratB
    };
  }, [h2hDataA, h2hDataB]);

  if (!sessionPitStops) {
    return (
      <div className="pit-analytics-panel-loading">
        <div className="pulse-dot"></div>
        <span>Loading Real Pit Stop Analytics...</span>
      </div>
    );
  }

  return (
    <div className="pit-analytics-panel">
      {/* 1. Header & Navigation Tabs */}
      <div className="pit-panel-header">
        <div className="pit-header-left">
          <span className="pit-badge-tag">ALL-DRIVER PIT ANALYTICS</span>
          <h2 className="pit-panel-title">
            Pit Strategy & Timing Engine · {sessionPitStops.total_pit_stops} Total Stops ({sessionPitStops.driver_count} Drivers)
          </h2>
        </div>

        <div className="pit-tab-buttons">
          <button 
            className={`pit-tab-btn ${activeTab === 'strategy' ? 'active' : ''}`}
            onClick={() => setActiveTab('strategy')}
          >
            Strategy Timeline
          </button>
          <button 
            className={`pit-tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
            onClick={() => setActiveTab('summary')}
          >
            Summary Table
          </button>
          <button 
            className={`pit-tab-btn ${activeTab === 'ranking' ? 'active' : ''}`}
            onClick={() => setActiveTab('ranking')}
          >
            Fastest Stops
          </button>
          <button 
            className={`pit-tab-btn ${activeTab === 'h2h' ? 'active' : ''}`}
            onClick={() => setActiveTab('h2h')}
          >
            Head-to-Head
          </button>
          <button 
            className={`pit-tab-btn ${activeTab === 'diagnostics' ? 'active' : ''}`}
            onClick={() => setActiveTab('diagnostics')}
          >
            Coverage Report
          </button>
        </div>
      </div>

      {/* 2. TAB 1: STRATEGY TIMELINE (ALL DRIVERS) */}
      {activeTab === 'strategy' && (
        <div className="pit-tab-content pit-strategy-view">
          <div className="pit-strategy-intro">
            <span>Verified stint transitions & tyre compound evolutions for every real driver in the session.</span>
          </div>

          <div className="pit-strategy-list scrollable-pit-list">
            {driversList.map(d => {
              const isSelected = d.driver_id === selectedDriver;
              const stops = d.pit_stops || [];
              const hasStops = stops.length > 0;

              return (
                <div 
                  key={d.driver_id} 
                  className={`pit-strategy-driver-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => selectDriver(d.driver_id)}
                >
                  <div className="pit-driver-meta-strip" style={{ borderLeftColor: d.team_color }}>
                    <div className="pit-driver-code-box">
                      <strong className="p-code">{d.driver_id}</strong>
                      <span className="p-num">#{d.driver_number || 0}</span>
                    </div>
                    <div className="p-name-team">
                      <span className="p-fullname">{d.full_name || d.driver_name}</span>
                      <span className="p-team">{d.team}</span>
                    </div>
                    <div className="p-stops-count-badge">
                      {stops.length} {stops.length === 1 ? 'Stop' : 'Stops'}
                    </div>
                  </div>

                  <div className="pit-stops-timeline-row">
                    {!hasStops ? (
                      <span className="zero-stops-text">Zero pit stops recorded (Single-stint / Running)</span>
                    ) : (
                      stops.map(ps => (
                        <div key={ps.stop_number} className="pit-event-pill">
                          <div className="pit-event-header">
                            <span className="pit-event-lap">L{ps.lap}</span>
                            <span className="pit-event-num">Stop #{ps.stop_number}</span>
                          </div>

                          <div className="pit-compound-transition">
                            <span className="c-tag" style={{ color: getCompoundColor(ps.compound_before) }}>
                              {ps.compound_before}
                            </span>
                            <span className="c-arrow">→</span>
                            <span className="c-tag" style={{ color: getCompoundColor(ps.compound_after) }}>
                              {ps.compound_after}
                            </span>
                          </div>

                          <div className="pit-event-duration">
                            <strong>{ps.duration}s</strong>
                            <span className="transit-sub">({ps.lane_duration || '—'}s lane)</span>
                          </div>

                          {ps.position_before !== null && ps.position_after !== null && (
                            <div className="pit-pos-change-tag">
                              <span>P{ps.position_before} → P{ps.position_after}</span>
                              <span className={`delta-val ${ps.position_delta > 0 ? 'pos-gained' : ps.position_delta < 0 ? 'pos-lost' : 'pos-even'}`}>
                                ({ps.position_delta > 0 ? `+${ps.position_delta}` : ps.position_delta})
                              </span>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. TAB 2: SUMMARY TABLE */}
      {activeTab === 'summary' && (
        <div className="pit-tab-content pit-summary-view">
          <div className="pit-table-wrapper">
            <table className="pit-data-table">
              <thead>
                <tr>
                  <th>Driver</th>
                  <th>Team</th>
                  <th>Stops</th>
                  <th>Pit Laps</th>
                  <th>Total Stationary Time</th>
                  <th>Average Stop</th>
                  <th>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {summaryTableRows.map(row => {
                  const isSelected = row.driver_id === selectedDriver;
                  return (
                    <tr 
                      key={row.driver_id} 
                      className={`pit-table-row ${isSelected ? 'selected-row' : ''}`}
                      onClick={() => selectDriver(row.driver_id)}
                    >
                      <td className="driver-cell">
                        <span className="team-indicator-dot" style={{ backgroundColor: row.team_color }}></span>
                        <strong>{row.driver_id}</strong>
                        <span className="cell-sub">{row.full_name}</span>
                      </td>
                      <td>{row.team}</td>
                      <td>
                        <span className={`stops-pill ${row.stops_count > 0 ? 'has-stops' : 'zero-stops'}`}>
                          {row.stops_count}
                        </span>
                      </td>
                      <td>{row.laps}</td>
                      <td className="time-cell highlight">{row.total_time}</td>
                      <td className="time-cell">{row.avg_time}</td>
                      <td className="strategy-cell">{row.strategy}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. TAB 3: OBSERVED PIT STOP RANKING */}
      {activeTab === 'ranking' && (
        <div className="pit-tab-content pit-ranking-view">
          <div className="pit-ranking-disclaimer">
            <span className="disclaimer-badge">OBSERVED DURATION RANKING</span>
            <span>Observed stationary wheel-change duration ranking recorded during session events.</span>
          </div>

          <div className="pit-ranking-grid">
            {observedRankings.map((rk, idx) => (
              <div 
                key={`${rk.driver_id}_${rk.stop_number}_${rk.lap}`}
                className={`ranking-card ${idx === 0 ? 'gold' : idx === 1 ? 'silver' : idx === 2 ? 'bronze' : ''} ${rk.driver_id === selectedDriver ? 'selected-driver' : ''}`}
                onClick={() => selectDriver(rk.driver_id)}
              >
                <div className="ranking-position-badge">
                  #{idx + 1}
                </div>

                <div className="ranking-driver-info">
                  <span className="rk-driver" style={{ color: rk.team_color }}>{rk.driver_id}</span>
                  <span className="rk-name">{rk.full_name}</span>
                  <span className="rk-lap">Lap {rk.lap} (Stop #{rk.stop_number})</span>
                </div>

                <div className="ranking-compounds">
                  <span style={{ color: getCompoundColor(rk.compound_before) }}>{rk.compound_before}</span>
                  <span>→</span>
                  <span style={{ color: getCompoundColor(rk.compound_after) }}>{rk.compound_after}</span>
                </div>

                <div className="ranking-time-box">
                  <strong className="rk-duration">{rk.duration}s</strong>
                  <span className="rk-lane-sub">{rk.lane_duration ? `${rk.lane_duration}s lane` : ''}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. TAB 4: HEAD-TO-HEAD COMPARISON */}
      {activeTab === 'h2h' && (
        <div className="pit-tab-content pit-h2h-view">
          <div className="h2h-selectors-bar">
            <div className="h2h-selector-wrap">
              <label>Driver A:</label>
              <select 
                className="h2h-select"
                value={h2hDriverA}
                onChange={(e) => setH2hDriverA(e.target.value)}
              >
                {driversList.map(d => (
                  <option key={d.driver_id} value={d.driver_id}>
                    {d.driver_id} — {d.full_name} ({d.pit_stop_count} stops)
                  </option>
                ))}
              </select>
            </div>

            <div className="h2h-vs-badge">VS</div>

            <div className="h2h-selector-wrap">
              <label>Driver B:</label>
              <select 
                className="h2h-select"
                value={h2hDriverB}
                onChange={(e) => setH2hDriverB(e.target.value)}
              >
                {driversList.map(d => (
                  <option key={d.driver_id} value={d.driver_id}>
                    {d.driver_id} — {d.full_name} ({d.pit_stop_count} stops)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {h2hComparison && (
            <div className="h2h-comparison-cards-cluster">
              <div className="h2h-driver-column driver-a" style={{ borderColor: h2hComparison.driverA.team_color }}>
                <div className="h2h-driver-header">
                  <h3 style={{ color: h2hComparison.driverA.team_color }}>{h2hComparison.driverA.driver_id}</h3>
                  <span>{h2hComparison.driverA.full_name}</span>
                  <span className="h2h-team-sub">{h2hComparison.driverA.team}</span>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Total Pit Stops</span>
                  <strong className="h2h-val">{h2hComparison.stopsCountA}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">First Pit Stop</span>
                  <strong className="h2h-val">{h2hComparison.firstStopA}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Total Stationary Time</span>
                  <strong className="h2h-val highlight">{h2hComparison.totalTimeA}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Average Stop Duration</span>
                  <strong className="h2h-val">{h2hComparison.avgTimeA}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Tyre Compound Strategy</span>
                  <strong className="h2h-val">{h2hComparison.stratA}</strong>
                </div>
              </div>

              <div className="h2h-driver-column driver-b" style={{ borderColor: h2hComparison.driverB.team_color }}>
                <div className="h2h-driver-header">
                  <h3 style={{ color: h2hComparison.driverB.team_color }}>{h2hComparison.driverB.driver_id}</h3>
                  <span>{h2hComparison.driverB.full_name}</span>
                  <span className="h2h-team-sub">{h2hComparison.driverB.team}</span>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Total Pit Stops</span>
                  <strong className="h2h-val">{h2hComparison.stopsCountB}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">First Pit Stop</span>
                  <strong className="h2h-val">{h2hComparison.firstStopB}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Total Stationary Time</span>
                  <strong className="h2h-val highlight">{h2hComparison.totalTimeB}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Average Stop Duration</span>
                  <strong className="h2h-val">{h2hComparison.avgTimeB}</strong>
                </div>
                <div className="h2h-stat-box">
                  <span className="h2h-lbl">Tyre Compound Strategy</span>
                  <strong className="h2h-val">{h2hComparison.stratB}</strong>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 6. TAB 5: DIAGNOSTIC COVERAGE REPORT */}
      {activeTab === 'diagnostics' && (
        <div className="pit-tab-content pit-diagnostics-view">
          <div className="diag-intro">
            <h4>DRIVER COVERAGE DIAGNOSTIC REPORT</h4>
            <span>Authoritative verification of real pit stop telemetry per driver in {sessionPitStops.session_id}.</span>
          </div>

          <div className="diag-table-wrap">
            <table className="diag-table">
              <thead>
                <tr>
                  <th>DRIVER</th>
                  <th>STOPS</th>
                  <th>PIT DATA</th>
                </tr>
              </thead>
              <tbody>
                {driversList.map(d => (
                  <tr key={d.driver_id}>
                    <td className="diag-drv-cell">
                      <span className="team-indicator-dot" style={{ backgroundColor: d.team_color }}></span>
                      <strong>{d.driver_id}</strong>
                      <span className="diag-name-sub">{d.full_name}</span>
                    </td>
                    <td className="diag-stops-cell">{d.pit_stop_count}</td>
                    <td className="diag-status-cell">
                      <span className={`diag-tag ${d.data_status === 'AVAILABLE' ? 'available' : 'insufficient'}`}>
                        {d.data_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Diagnostic Footer Counters */}
          <div className="diag-footer-summary">
            <div className="diag-counter-item">
              <span className="cnt-lbl">Total Drivers:</span>
              <strong className="cnt-val">{sessionPitStops.driver_count}</strong>
            </div>
            <div className="diag-counter-item">
              <span className="cnt-lbl">Drivers with Pit Stops:</span>
              <strong className="cnt-val">{sessionPitStops.drivers_with_pit_stops}</strong>
            </div>
            <div className="diag-counter-item">
              <span className="cnt-lbl">Drivers with Zero Pit Stops:</span>
              <strong className="cnt-val">{sessionPitStops.drivers_zero_pit_stops}</strong>
            </div>
            <div className="diag-counter-item">
              <span className="cnt-lbl">Drivers with Insufficient Data:</span>
              <strong className="cnt-val">{sessionPitStops.drivers_insufficient_data}</strong>
            </div>
            <div className="diag-counter-item highlight">
              <span className="cnt-lbl">Total Verified Pit Stops:</span>
              <strong className="cnt-val">{sessionPitStops.total_pit_stops}</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

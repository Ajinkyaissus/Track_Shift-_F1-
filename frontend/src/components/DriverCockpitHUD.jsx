import { useMemo } from 'react';
import { useCircuit } from '../context/CircuitContext';
import { CountryFlag } from '../utils/countryFlags';

function getCompoundColor(compound) {
  const c = (compound || '').toUpperCase();
  if (c === 'SOFT') return '#E10600';
  if (c === 'MEDIUM') return '#FFB800';
  if (c === 'HARD') return '#FFFFFF';
  if (c === 'INTERMEDIATE') return '#39B54A';
  if (c === 'WET') return '#00AEEF';
  return '#888888';
}

function getTeamColor(team, hexFromBackend) {
  if (hexFromBackend && hexFromBackend.startsWith('#') && hexFromBackend.length >= 4) {
    return hexFromBackend;
  }
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

export default function DriverCockpitHUD() {
  const { 
    sessionTelemetry, 
    sessionPitStops,
    selectedDriver, 
    currentDriverLapTelemetry, 
    currentLeaderboard, 
    replayLap, 
    totalLaps, 
    replayProgress, 
    stintLedger,
    circuitMapData 
  } = useCircuit();

  const driverPitData = useMemo(() => {
    if (!sessionPitStops?.drivers || !selectedDriver) return null;
    return sessionPitStops.drivers.find(d => d.driver_id === selectedDriver) || null;
  }, [sessionPitStops, selectedDriver]);

  const driverMeta = useMemo(() => {
    return sessionTelemetry?.drivers?.find(d => d.driver_id === selectedDriver) || {
      driver_id: selectedDriver || 'VER',
      driver_number: 1,
      full_name: selectedDriver || 'Driver',
      team: 'Formula 1',
      team_color: '#E10600',
      compound: 'HARD',
      country_code: '',
      nationality: '',
      profile_image: `/drivers/${(selectedDriver || 'ver').toLowerCase()}.webp`,
      reputation_tag: 'neutral',
      telemetry_available: true,
      tyre_analysis_available: true,
      tcn_available: true
    };
  }, [sessionTelemetry, selectedDriver]);

  const weather = sessionTelemetry?.weather || {
    air_temp: 28.5,
    track_temp: 36.0,
    weather_flag: 'dry',
    humidity: 48,
    track_evolution_index: 2.2
  };

  const hasTelemetry = Boolean(currentDriverLapTelemetry && driverMeta.telemetry_available !== false);

  // Position & Leaderboard info for selected driver
  const driverLeaderboardEntry = useMemo(() => {
    if (!currentLeaderboard) return null;
    return currentLeaderboard.find(row => row.driver_id === selectedDriver);
  }, [currentLeaderboard, selectedDriver]);

  const position = driverLeaderboardEntry?.position || 1;
  const lapTimeFormatted = currentDriverLapTelemetry?.lap_time ? `${currentDriverLapTelemetry.lap_time.toFixed(3)}s` : (driverLeaderboardEntry?.lap_time ? `${driverLeaderboardEntry.lap_time.toFixed(3)}s` : '—');
  const portraitSrc = driverMeta.profile_image || `/drivers/${(driverMeta.driver_id || '').toLowerCase()}.webp`;
  const driverNum = driverMeta.driver_number || driverMeta.number || 0;

  // Derive live throttle, brake, speed, gear from authentic circuit telemetry points along lap progress
  const liveTelemetry = useMemo(() => {
    if (!hasTelemetry || !currentDriverLapTelemetry) {
      return null;
    }

    const base = currentDriverLapTelemetry;
    const pts = circuitMapData?.points;
    let speed = 220;
    let throttle = 100;
    let brake = false;

    if (pts && pts.length > 0) {
      const pointIdx = Math.min(pts.length - 1, Math.max(0, Math.floor(replayProgress * pts.length)));
      const pt = pts[pointIdx];
      if (pt) {
        speed = pt.speed ? Math.round(pt.speed) : (pt.Speed ? Math.round(pt.Speed) : 220);
        throttle = pt.throttle !== undefined ? Math.round(pt.throttle) : (pt.Throttle !== undefined ? Math.round(pt.Throttle) : 100);
        brake = pt.brake !== undefined ? Boolean(pt.brake > 0.1 || pt.brake === true) : (pt.Brake !== undefined ? Boolean(pt.Brake > 0.1 || pt.Brake === true) : false);
      }
    }

    const gear = speed > 295 ? 8 : speed > 255 ? 7 : speed > 215 ? 6 : speed > 170 ? 5 : speed > 125 ? 4 : speed > 85 ? 3 : 2;
    const inDrsZone = Boolean(circuitMapData?.drs_zones?.some(z => replayProgress >= z.start_pct && replayProgress <= z.end_pct));
    const drs = inDrsZone && !brake;

    // Debt from ledger if available
    const ledgerRow = stintLedger?.series?.find(s => s.lap_number === replayLap);
    const debt = ledgerRow ? ledgerRow.cumulative_debt : base.cumulative_debt;
    const residual = ledgerRow ? ledgerRow.residual : base.residual;

    return {
      speed,
      throttle,
      brake,
      gear,
      drs,
      fuel: base.fuel_load_est || 90.0,
      tyre_age: base.tyre_age || replayLap,
      debt: Number(debt || 0),
      residual: Number(residual || 0),
      braking_agg: base.braking_aggression,
      throttle_smoothness: base.throttle_transient_smoothness
    };
  }, [hasTelemetry, currentDriverLapTelemetry, circuitMapData, replayProgress, replayLap, stintLedger]);

  const compound = driverMeta.compound || (currentDriverLapTelemetry?.compound) || 'HARD';
  const compoundColor = getCompoundColor(compound);
  const teamColor = getTeamColor(driverMeta.team, driverMeta.team_color);

  return (
    <div className="cockpit-hud-container">
      {/* 1. Session Weather Widget */}
      <div className="hud-panel weather-panel">
        <div className="panel-header-small">
          <span className="panel-tag">SESSION WEATHER</span>
          <span className={`weather-status-pill ${(weather.weather_flag || 'dry').toLowerCase()}`}>
            {(weather.weather_flag || 'dry').toUpperCase()}
          </span>
        </div>
        <div className="weather-grid">
          <div className="weather-item">
            <span className="w-label">AIR TEMP</span>
            <span className="w-val">{weather.air_temp}°C</span>
          </div>
          <div className="weather-item">
            <span className="w-label">TRACK TEMP</span>
            <span className="w-val">{weather.track_temp}°C</span>
          </div>
          <div className="weather-item">
            <span className="w-label">HUMIDITY</span>
            <span className="w-val">{weather.humidity}%</span>
          </div>
          <div className="weather-item">
            <span className="w-label">TRACK EVO</span>
            <span className="w-val">{weather.track_evolution_index}</span>
          </div>
        </div>
      </div>

      {/* 2. Selected Driver Cockpit Card (Broadcast Style with Portrait) */}
      <div className="hud-panel driver-panel" style={{ borderTop: `4px solid ${teamColor}` }}>
        <div className="driver-broadcast-card">
          {/* Portrait Column */}
          <div className="driver-portrait-col">
            <div className="driver-main-portrait-wrap" style={{ borderColor: teamColor }}>
              <img
                src={portraitSrc}
                alt={`${driverMeta.full_name || driverMeta.name || driverMeta.driver_id} profile`}
                className="driver-main-portrait-img"
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = "/drivers/fallback_driver.webp";
                }}
              />
              <div className="driver-pos-ribbon" style={{ backgroundColor: teamColor }}>
                P{position}
              </div>
            </div>
          </div>

          {/* Identity & Details Column */}
          <div className="driver-broadcast-info">
            <div className="driver-tag-row">
              <CountryFlag code={driverMeta.country_code || driverMeta.nationality} size="md" />
              <span className="driver-code-prominent">{driverMeta.driver_id}</span>
              {driverNum > 0 && (
                <span className="driver-num-tag" style={{ borderColor: teamColor, color: teamColor }}>
                  #{driverNum}
                </span>
              )}
              <span className="driver-rep-badge">{driverMeta.reputation_tag || 'neutral'}</span>
            </div>

            <h3 className="driver-full-name">{driverMeta.full_name || driverMeta.name || driverMeta.driver_id}</h3>
            <span className="driver-team-name">{driverMeta.team}</span>

            {/* Quick broadcast telemetry pill row */}
            <div className="broadcast-stats-strip">
              <div className="b-stat">
                <span className="b-label">LAP</span>
                <span className="b-val">{replayLap}/{totalLaps}</span>
              </div>
              <div className="b-stat">
                <span className="b-label">LAST LAP</span>
                <span className="b-val">{lapTimeFormatted}</span>
              </div>
              <div className="b-stat">
                <span className="b-label">TYRE</span>
                <span className="b-val" style={{ color: compoundColor }}>
                  {compound[0]} ({liveTelemetry?.tyre_age ?? driverMeta.tyre_age_start ?? 0}L)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Scientific Telemetry & Analysis Availability Status */}
        <div className="driver-availability-strip">
          <div className="avail-item">
            <span className="avail-label">ROSTER</span>
            <span className="avail-badge ready">PARTICIPATING</span>
          </div>
          <div className="avail-item">
            <span className="avail-label">TELEMETRY</span>
            <span className={`avail-badge ${hasTelemetry ? 'ready' : 'limited'}`}>
              {hasTelemetry ? 'AVAILABLE' : 'LIMITED'}
            </span>
          </div>
          <div className="avail-item">
            <span className="avail-label">TYRE ML</span>
            <span className={`avail-badge ${driverMeta.tyre_analysis_available ? 'ready' : 'limited'}`}>
              {driverMeta.tyre_analysis_available ? 'READY' : 'INSUFFICIENT'}
            </span>
          </div>
          <div className="avail-item">
            <span className="avail-label">TCN DL</span>
            <span className={`avail-badge ${hasTelemetry ? 'ready' : 'limited'}`}>
              {hasTelemetry ? 'READY' : 'INSUFFICIENT'}
            </span>
          </div>
        </div>

        {/* Live Gauges or Honest Notice */}
        {hasTelemetry && liveTelemetry ? (
          <>
            <div className="gauges-cluster">
              {/* Speed & Gear */}
              <div className="gauge-speed-row">
                <div className="speed-display">
                  <span className="gauge-label">SPEED</span>
                  <div className="speed-number">
                    {liveTelemetry.speed} <span className="speed-unit">KM/H</span>
                  </div>
                </div>
                <div className="gear-display">
                  <span className="gauge-label">GEAR</span>
                  <div className="gear-number">{liveTelemetry.gear}</div>
                </div>
                <div className={`drs-display ${liveTelemetry.drs ? 'active' : ''}`}>
                  <span className="gauge-label">DRS</span>
                  <div className="drs-text">{liveTelemetry.drs ? 'ACTIVE' : 'OFF'}</div>
                </div>
              </div>

              {/* Throttle & Brake Bars */}
              <div className="pedal-bars-container">
                <div className="pedal-bar-row">
                  <span className="pedal-label">THROTTLE</span>
                  <div className="bar-track">
                    <div 
                      className="bar-fill throttle-fill" 
                      style={{ width: `${liveTelemetry.throttle}%` }}
                    ></div>
                  </div>
                  <span className="pedal-pct">{liveTelemetry.throttle}%</span>
                </div>

                <div className="pedal-bar-row">
                  <span className="pedal-label">BRAKE</span>
                  <div className="bar-track">
                    <div 
                      className="bar-fill brake-fill" 
                      style={{ width: liveTelemetry.brake ? '85%' : '0%' }}
                    ></div>
                  </div>
                  <span className="pedal-pct">{liveTelemetry.brake ? 'ACTIVE' : '0%'}</span>
                </div>
              </div>
            </div>

            {/* Tyre Intelligence HUD */}
            <div className="tyre-intelligence-hud">
              <div className="panel-header-small">
                <span className="panel-tag">TYRE & DEBT STATE</span>
                <span 
                  className="compound-badge" 
                  style={{ borderColor: compoundColor, color: compoundColor }}
                >
                  ● {compound}
                </span>
              </div>

              <div className="tyre-stats-grid">
                <div className="tyre-stat-card">
                  <span className="tyre-stat-label">TYRE AGE</span>
                  <span className="tyre-stat-val">{liveTelemetry.tyre_age} Laps</span>
                </div>
                <div className="tyre-stat-card">
                  <span className="tyre-stat-label">FUEL LOAD</span>
                  <span className="tyre-stat-val">{liveTelemetry.fuel} kg</span>
                </div>
                <div className="tyre-stat-card debt-card">
                  <span className="tyre-stat-label">TYRE DEBT</span>
                  <span className={`tyre-stat-val ${liveTelemetry.debt > 0 ? 'debt-positive' : 'credit-positive'}`}>
                    {liveTelemetry.debt > 0 ? `+${liveTelemetry.debt.toFixed(3)}s` : `${liveTelemetry.debt.toFixed(3)}s`}
                  </span>
                </div>
                <div className="tyre-stat-card">
                  <span className="tyre-stat-label">LAP RESIDUAL</span>
                  <span className={`tyre-stat-val ${liveTelemetry.residual > 0 ? 'debt-positive' : 'credit-positive'}`}>
                    {liveTelemetry.residual > 0 ? `+${liveTelemetry.residual.toFixed(3)}s` : `${liveTelemetry.residual.toFixed(3)}s`}
                  </span>
                </div>
              </div>
            </div>

            {/* Driver Pit Profile Card */}
            {driverPitData && (
              <div className="driver-pit-profile-hud">
                <div className="panel-header-small">
                  <span className="panel-tag">DRIVER PIT PROFILE</span>
                  <span className="pit-summary-tag">
                    {driverPitData.pit_stop_count} {driverPitData.pit_stop_count === 1 ? 'Stop' : 'Stops'}
                  </span>
                </div>

                <div className="pit-profile-metrics-row">
                  <div className="pit-prof-metric">
                    <span className="prof-lbl">Total Stationary</span>
                    <strong className="prof-val">
                      {driverPitData.pit_stops?.reduce((acc, s) => acc + (s.duration || 0), 0).toFixed(2)}s
                    </strong>
                  </div>
                  <div className="pit-prof-metric">
                    <span className="prof-lbl">Average Stop</span>
                    <strong className="prof-val">
                      {driverPitData.pit_stops?.length > 0 
                        ? (driverPitData.pit_stops.reduce((acc, s) => acc + (s.duration || 0), 0) / driverPitData.pit_stops.length).toFixed(2) + 's'
                        : '—'}
                    </strong>
                  </div>
                </div>

                <div className="pit-stops-individual-list">
                  {driverPitData.pit_stops?.length === 0 ? (
                    <div className="pit-stop-empty-note">Zero verified pit stops (Single-stint / Running)</div>
                  ) : (
                    driverPitData.pit_stops.map(ps => (
                      <div key={ps.stop_number} className="hud-pit-stop-item">
                        <div className="hud-stop-header">
                          <strong className="hud-stop-num">PIT STOP #{ps.stop_number}</strong>
                          <span className="hud-stop-lap">Lap {ps.lap}</span>
                          <span className="hud-stop-dur">{ps.duration}s</span>
                        </div>
                        <div className="hud-stop-details">
                          <span className="hud-compounds">
                            {ps.compound_before} → {ps.compound_after}
                          </span>
                          <span className="hud-age">
                            Age {ps.tyre_age_before}L → {ps.tyre_age_after}L
                          </span>
                        </div>
                        {ps.position_before !== null && ps.position_after !== null && (
                          <div className="hud-position-delta-row">
                            <span className="hud-pos-lbl">POSITION CHANGE ACROSS PIT STOP:</span>
                            <span className="hud-pos-val">
                              P{ps.position_before} → P{ps.position_after}
                              <span className={`pos-delta-pill ${ps.position_delta > 0 ? 'gain' : ps.position_delta < 0 ? 'loss' : 'even'}`}>
                                ({ps.position_delta > 0 ? `+${ps.position_delta}` : ps.position_delta})
                              </span>
                            </span>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="insufficient-telemetry-notice">
            <div className="notice-icon">ℹ️</div>
            <div className="notice-content">
              <h4>Insufficient High-Frequency Telemetry</h4>
              <p>
                Driver participated in this FastF1 session, but high-frequency telemetry channels were not captured for deep ML/DL analysis.
              </p>
              <p className="notice-sub">
                Standings and stint roster entries remain fully visible in the session leaderboard.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

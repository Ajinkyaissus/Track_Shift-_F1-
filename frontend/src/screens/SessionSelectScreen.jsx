import { useCircuit } from '../context/CircuitContext';
import { CountryFlag, getCountryName } from '../utils/countryFlags';

export default function SessionSelectScreen() {
  const { 
    selectedCircuit, 
    circuitDetail, 
    availableSessions, 
    selectSession, 
    selectCircuit, 
    loadingStage, 
    error 
  } = useCircuit();

  const country = circuitDetail?.country || getCountryName(circuitDetail?.country_code);

  return (
    <div className="session-select-container">
      {/* Navigation Breadcrumb with prominent ← WORLD button */}
      <div className="breadcrumb-bar">
        <button className="world-nav-btn" onClick={() => selectCircuit(null)} title="Return to Global F1 World View">
          🌍 WORLD
        </button>
        <span className="breadcrumb-separator">/</span>
        <div className="breadcrumb-country-badge">
          <CountryFlag code={circuitDetail?.country_code} size="sm" />
          <span className="breadcrumb-country">{country?.toUpperCase()}</span>
        </div>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">{circuitDetail?.name || selectedCircuit}</span>
      </div>

      {error && (
        <div className="error-banner">
          ⚠️ {error}
        </div>
      )}

      {/* Circuit Header Panel */}
      <div className="circuit-header-panel">
        <div className="header-left">
          <div className="flag-title-row">
            <CountryFlag code={circuitDetail?.country_code} size="xl" />
            <div>
              <div className="circuit-country-tag">{country?.toUpperCase()}</div>
              <h1 className="circuit-main-title">{circuitDetail?.name || selectedCircuit}</h1>
              <span className="circuit-sub-location">
                📍 {circuitDetail?.location}, {country} ({circuitDetail?.lat?.toFixed(2)}°N, {circuitDetail?.lon?.toFixed(2)}°E)
              </span>
            </div>
          </div>
        </div>

        <div className="header-stats">
          <div className="stat-box">
            <span className="stat-label">Corners</span>
            <span className="stat-val">{circuitDetail?.corners_count || 16}</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Recorded Laps</span>
            <span className="stat-val">{circuitDetail?.total_laps_recorded || 50}</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Stints</span>
            <span className="stat-val">{circuitDetail?.total_stints_recorded || 4}</span>
          </div>
        </div>
      </div>

      {/* Sessions Section */}
      <div className="session-list-section">
        <div className="section-title-row">
          <h2 className="section-heading">Available Grand Prix Sessions</h2>
          <span className="section-subtext">Select a verified session to launch the historical telemetry replay dashboard</span>
        </div>

        {loadingStage === 'circuit' ? (
          <div className="session-grid">
            {[1, 2].map(n => (
              <div key={n} className="session-card skeleton" style={{ height: '180px' }}></div>
            ))}
          </div>
        ) : availableSessions.length === 0 ? (
          <div className="panel empty-panel">
            <p>No verified sessions found for this circuit.</p>
            <button className="race-btn active" onClick={() => selectCircuit(null)}>← Return to World</button>
          </div>
        ) : (
          <div className="session-grid">
            {availableSessions.map(session => (
              <div
                key={session.session_id}
                className="session-card"
                onClick={() => selectSession(selectedCircuit, session.session_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') selectSession(selectedCircuit, session.session_id); }}
              >
                <div className="session-card-top">
                  <span className="session-type-badge">{session.session_type === 'R' ? 'RACE (R)' : session.session_type}</span>
                  <span className="session-season-tag">{session.season || 2024}</span>
                </div>

                <h3 className="session-event-name">{session.event_name || `${session.season} Grand Prix`}</h3>
                <div className="session-round-info">Round {session.round || 1} · {session.event_date || '2024 Championship'}</div>

                <div className="session-meta-pills">
                  <span className="meta-pill">
                    🌤 Weather: <strong>{(session.weather_flag || 'dry').toUpperCase()}</strong>
                  </span>
                  <span className="meta-pill">
                    📈 Track Evolution: <strong>{session.track_evolution_index || 2.2}</strong>
                  </span>
                  <span className="meta-pill">
                    ⏱ FastF1 Real GPS: <strong>VERIFIED</strong>
                  </span>
                </div>

                <div className="session-card-action">
                  <span>Enter Race Dashboard</span>
                  <span className="action-arrow">→</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

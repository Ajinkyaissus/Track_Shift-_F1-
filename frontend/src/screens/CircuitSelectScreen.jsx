import { useState } from 'react';
import { useCircuit } from '../context/CircuitContext';
import GlobalF1Globe from '../components/GlobalF1Globe';
import { CountryFlag, getCountryName } from '../utils/countryFlags';

const CIRCUIT_LENGTHS = {
  spa: "7.004 km",
  silverstone: "5.891 km",
  monza: "5.793 km",
  jeddah: "6.174 km",
  bahrain: "5.412 km",
  suzuka: "5.807 km",
  cota: "5.513 km",
  interlagos: "4.309 km",
  hungaroring: "4.381 km",
  albert_park: "5.278 km",
  singapore: "4.940 km",
  abu_dhabi: "5.281 km",
  monaco: "3.337 km"
};

export default function CircuitSelectScreen() {
  const { circuits, selectCircuit, error } = useCircuit();
  const [viewMode, setViewMode] = useState('globe'); // 'globe' | 'grid'
  const [searchQuery, setSearchQuery] = useState('');

  const filteredCircuits = circuits.filter(c => 
    !searchQuery.trim() ||
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.country?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.location?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="circuit-selection-master">
      {error && (
        <div className="error-banner">
          ⚠️ {error}
        </div>
      )}

      {/* View Switcher Bar (3D Globe vs Grid Gallery) */}
      <div className="view-mode-bar">
        <div className="view-mode-pills">
          <button 
            className={`view-pill ${viewMode === 'globe' ? 'active' : ''}`}
            onClick={() => setViewMode('globe')}
          >
            🌍 3D Global World View
          </button>
          <button 
            className={`view-pill ${viewMode === 'grid' ? 'active' : ''}`}
            onClick={() => setViewMode('grid')}
          >
            🏁 Circuit Grid List ({circuits.length})
          </button>
        </div>
      </div>

      {viewMode === 'globe' ? (
        /* Primary 3D Global F1 World View */
        <GlobalF1Globe 
          onSelectCircuit={selectCircuit} 
          onSwitchToGrid={() => setViewMode('grid')}
        />
      ) : (
        /* Accessible High-Density Grid View with Country Flags */
        <div className="circuit-select-container">
          <div className="hero-banner">
            <div className="hero-badge">
              <span className="pulse-dot"></span>
              <span>13 VERIFIED F1 CIRCUITS</span>
            </div>
            <h1 className="hero-title">Grand Prix Circuits Directory</h1>
            <p className="hero-subtitle">
              Select any verified FIA Formula 1 circuit to inspect sessions and launch historical telemetry replay.
            </p>

            <div className="search-bar-container">
              <input
                type="text"
                className="circuit-search-input"
                placeholder="Search circuit name, country, or location..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <div className="circuit-count-badge">
                {filteredCircuits.length} / {circuits.length} Circuits Available
              </div>
            </div>
          </div>

          <div className="circuit-grid">
            {filteredCircuits.map(circuit => {
              const trackLength = CIRCUIT_LENGTHS[circuit.track_id] || '5.3 km';
              const country = circuit.country || getCountryName(circuit.country_code);

              return (
                <div 
                  key={circuit.track_id} 
                  className="circuit-card"
                  onClick={() => selectCircuit(circuit.track_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') selectCircuit(circuit.track_id); }}
                >
                  <div className="card-top">
                    <div className="country-info">
                      <CountryFlag code={circuit.country_code} size="sm" />
                      <span className="country-name">{country}</span>
                    </div>
                    <span className="track-id-tag">#{circuit.track_id}</span>
                  </div>

                  <h3 className="circuit-name">{circuit.name}</h3>
                  <div className="circuit-location">{circuit.location}, {country}</div>

                  <div className="card-specs">
                    <div className="spec-item">
                      <span className="spec-label">Track Length</span>
                      <span className="spec-value">{trackLength}</span>
                    </div>
                    <div className="spec-item">
                      <span className="spec-label">Verified Sessions</span>
                      <span className="spec-value">{circuit.verified_sessions || 1}</span>
                    </div>
                    <div className="spec-item">
                      <span className="spec-label">Recorded Stints</span>
                      <span className="spec-value">{circuit.stint_count || 0}</span>
                    </div>
                  </div>

                  <div className="card-badges">
                    <span className={`status-badge ${circuit.map_available ? 'active' : ''}`}>
                      🗺 {circuit.map_available ? 'GPS Geometry' : 'No Map'}
                    </span>
                    <span className={`status-badge ${circuit.telemetry_available ? 'active-red' : ''}`}>
                      📡 {circuit.telemetry_available ? 'Telemetry Ready' : 'Offline'}
                    </span>
                  </div>

                  <div className="card-footer">
                    <span className="card-action-text">Launch Telemetry Replay</span>
                    <span className="card-arrow">→</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

import { useMemo } from 'react';

const COUNTRY_FLAGS = {
  IT: "🇮🇹",
  BH: "🇧🇭",
  GB: "🇬🇧",
  JP: "🇯🇵",
  BE: "🇧🇪",
  MC: "🇲🇨",
  AU: "🇦🇺",
  SA: "🇸🇦",
  HU: "🇭🇺",
  SG: "🇸🇬",
  US: "🇺🇸",
  BR: "🇧🇷",
  AE: "🇦🇪"
};

export default function CircuitSelector({
  availableSeasons = [2025, 2024],
  selectedSeason = 2024,
  onSelectSeason,
  circuits = [],
  selectedCircuit,
  onSelectCircuit,
  sessions = [],
  selectedSession,
  onSelectSession,
  drivers = [],
  selectedDriver,
  onSelectDriver,
  compounds = [],
  selectedCompound,
  onSelectCompound
}) {
  const currentCircuitData = useMemo(() => {
    return circuits.find(c => c.track_id === selectedCircuit);
  }, [circuits, selectedCircuit]);

  return (
    <div className="panel" style={{ marginBottom: '1.5rem', background: '#12121C', border: '1px solid #222233' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.8rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.3rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', color: 'var(--accent-red)', textTransform: 'uppercase' }}>
              Multi-Season FastF1 Telemetry Platform
            </span>
            {/* Global Season Selector Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', background: '#181826', padding: '0.15rem 0.25rem', borderRadius: '6px', border: '1px solid #2A2A3C' }}>
              {availableSeasons.map(yr => (
                <button
                  key={yr}
                  onClick={() => onSelectSeason && onSelectSeason(yr)}
                  style={{
                    background: selectedSeason === yr ? 'var(--accent-red)' : 'transparent',
                    color: selectedSeason === yr ? '#FFF' : '#888',
                    border: 'none',
                    padding: '0.2rem 0.65rem',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: selectedSeason === yr ? 800 : 600,
                    fontSize: '0.75rem',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {yr}
                </button>
              ))}
            </div>
          </div>
          <h2 style={{ margin: '0.2rem 0 0 0', fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {currentCircuitData ? `${COUNTRY_FLAGS[currentCircuitData.country_code] || '🏁'} ${currentCircuitData.name} (${selectedSeason})` : `Select ${selectedSeason} Grand Prix Circuit`}
          </h2>
        </div>


        {currentCircuitData && (
          <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
            <span style={{ 
              fontSize: '0.75rem', 
              padding: '0.25rem 0.6rem', 
              borderRadius: '4px', 
              background: currentCircuitData.map_available ? 'rgba(0, 210, 190, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              color: currentCircuitData.map_available ? '#00D2BE' : '#888',
              border: `1px solid ${currentCircuitData.map_available ? '#00D2BE' : '#444'}`
            }}>
              🗺 Real Map {currentCircuitData.map_available ? '✓' : '—'}
            </span>
            <span style={{ 
              fontSize: '0.75rem', 
              padding: '0.25rem 0.6rem', 
              borderRadius: '4px', 
              background: currentCircuitData.telemetry_available ? 'rgba(225, 6, 0, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              color: currentCircuitData.telemetry_available ? '#FF4444' : '#888',
              border: `1px solid ${currentCircuitData.telemetry_available ? '#FF4444' : '#444'}`
            }}>
              📡 Telemetry {currentCircuitData.telemetry_available ? '✓' : '—'}
            </span>
          </div>
        )}
      </div>

      {/* Circuit Pills Grid */}
      <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.6rem', scrollbarWidth: 'thin' }}>
        {circuits.map(c => {
          const isSelected = c.track_id === selectedCircuit;
          const flag = COUNTRY_FLAGS[c.country_code] || '🏁';
          return (
            <button
              key={c.track_id}
              onClick={() => onSelectCircuit(c.track_id)}
              style={{
                background: isSelected ? 'var(--accent-red)' : '#1A1A26',
                color: isSelected ? '#FFF' : '#AAA',
                border: isSelected ? '1px solid var(--accent-red)' : '1px solid #2E2E40',
                padding: '0.45rem 0.85rem',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: isSelected ? 700 : 500,
                fontSize: '0.85rem',
                whiteSpace: 'nowrap',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                transition: 'all 0.15s ease'
              }}
            >
              <span>{flag}</span>
              <span>{c.name.replace("Autodromo Nazionale ", "").replace("Circuit de ", "").replace(" International Racing Course", "").replace(" Circuit", "")}</span>
            </button>
          );
        })}
      </div>

      {/* Cascade Filter Controls (Session, Driver, Compound) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #1E1E2C' }}>
        {/* Session Selector */}
        <div>
          <label style={{ fontSize: '0.75rem', color: '#888', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: '0.3rem' }}>
            Session
          </label>
          <select
            value={selectedSession || ''}
            onChange={(e) => onSelectSession && onSelectSession(e.target.value)}
            style={{ width: '100%', background: '#181824', color: '#FFF', border: '1px solid #333346', padding: '0.45rem 0.75rem', borderRadius: '4px' }}
          >
            {sessions.length > 0 ? (
              sessions.map(s => (
                <option key={s.session_id} value={s.session_id}>
                  {s.season} {s.event_name || s.session_id} ({s.session_type || 'R'})
                </option>
              ))
            ) : (
              <option value="">Race (R) — Verified Telemetry</option>
            )}
          </select>
        </div>

        {/* Driver Selector */}
        <div>
          <label style={{ fontSize: '0.75rem', color: '#888', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: '0.3rem' }}>
            Driver
          </label>
          <select
            value={selectedDriver || ''}
            onChange={(e) => onSelectDriver && onSelectDriver(e.target.value)}
            style={{ width: '100%', background: '#181824', color: '#FFF', border: '1px solid #333346', padding: '0.45rem 0.75rem', borderRadius: '4px' }}
          >
            <option value="">All Verified Drivers ({drivers.length})</option>
            {drivers.map(d => (
              <option key={d.driver_id || d} value={d.driver_id || d}>
                {d.driver_id || d} {d.full_name ? `— ${d.full_name}` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Compound Selector */}
        <div>
          <label style={{ fontSize: '0.75rem', color: '#888', fontWeight: 600, textTransform: 'uppercase', display: 'block', marginBottom: '0.3rem' }}>
            Tyre Compound
          </label>
          <select
            value={selectedCompound || ''}
            onChange={(e) => onSelectCompound && onSelectCompound(e.target.value)}
            style={{ width: '100%', background: '#181824', color: '#FFF', border: '1px solid #333346', padding: '0.45rem 0.75rem', borderRadius: '4px' }}
          >
            <option value="">All Compounds</option>
            {compounds.map(c => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

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

export default function SessionLeaderboard() {
  const { 
    currentLeaderboard, 
    sessionTelemetry,
    selectedDriver, 
    comparisonDriver, 
    selectDriver, 
    selectComparisonDriver,
    replayLap,
    totalLaps,
    selectedTeam,
    setSelectedTeam,
    selectedCompound,
    setSelectedCompound,
    driverSearchQuery,
    setDriverSearchQuery
  } = useCircuit();

  // Extract dynamic list of teams from session roster
  const availableTeams = useMemo(() => {
    if (!sessionTelemetry?.drivers) return [];
    const teams = new Set();
    sessionTelemetry.drivers.forEach(d => {
      if (d.team) teams.add(d.team);
    });
    return Array.from(teams).sort();
  }, [sessionTelemetry]);

  // Extract dynamic compounds from session
  const availableCompounds = useMemo(() => {
    if (!sessionTelemetry?.drivers) return ['SOFT', 'MEDIUM', 'HARD'];
    const compounds = new Set();
    sessionTelemetry.drivers.forEach(d => {
      if (d.compound && d.compound !== 'UNKNOWN') compounds.add(d.compound.toUpperCase());
    });
    if (compounds.size === 0) return ['SOFT', 'MEDIUM', 'HARD'];
    return Array.from(compounds).sort();
  }, [sessionTelemetry]);

  // Filter leaderboard rows based on search, team, and compound
  const filteredLeaderboard = useMemo(() => {
    if (!currentLeaderboard || currentLeaderboard.length === 0) {
      // Fallback: If currentLeaderboard is somehow empty, use sessionTelemetry.drivers directly
      if (sessionTelemetry?.drivers) {
        return sessionTelemetry.drivers.map((d, idx) => ({
          position: idx + 1,
          driver_id: d.driver_id,
          full_name: d.full_name || d.name || d.driver_id,
          team: d.team,
          team_color: d.team_color,
          country_code: d.country_code,
          nationality: d.nationality,
          compound: d.compound || 'HARD',
          tyre_age: 0,
          gap_to_leader: 0.0,
          interval: 0.0,
          cumulative_debt: 0.0,
          telemetry_available: Boolean(d.telemetry_available),
          status: d.telemetry_available ? 'Running' : 'Insufficient telemetry for this analysis'
        }));
      }
      return [];
    }

    return currentLeaderboard.filter(row => {
      // Search filter (matches driver code, full name, or team)
      if (driverSearchQuery.trim()) {
        const query = driverSearchQuery.toLowerCase().trim();
        const matchCode = (row.driver_id || '').toLowerCase().includes(query);
        const matchName = (row.full_name || '').toLowerCase().includes(query);
        const matchTeam = (row.team || '').toLowerCase().includes(query);
        const matchNum = String(row.driver_number || row.number || '').includes(query);
        if (!matchCode && !matchName && !matchTeam && !matchNum) return false;
      }

      // Team filter
      if (selectedTeam && selectedTeam !== 'ALL') {
        if (row.team !== selectedTeam) return false;
      }

      // Compound filter
      if (selectedCompound && selectedCompound !== 'ALL') {
        if ((row.compound || '').toUpperCase() !== selectedCompound.toUpperCase()) return false;
      }

      return true;
    });
  }, [currentLeaderboard, sessionTelemetry, driverSearchQuery, selectedTeam, selectedCompound]);

  const totalDriversCount = sessionTelemetry?.driver_count || sessionTelemetry?.drivers?.length || currentLeaderboard.length || 0;

  return (
    <div className="leaderboard-panel-container">
      {/* 1. Header & Live Indicator */}
      <div className="leaderboard-header">
        <div>
          <span className="panel-tag">SESSION LEADERBOARD</span>
          <h3 className="leaderboard-title">
            ALL DRIVERS ({totalDriversCount}) · Lap {replayLap}/{totalLaps}
          </h3>
        </div>
        <span className="live-indicator">LIVE REPLAY</span>
      </div>

      {/* 2. Interactive Search & Filters Bar */}
      <div className="leaderboard-filters-bar">
        {/* Search Input */}
        <div className="search-input-wrapper">
          <input
            type="text"
            className="driver-search-field"
            placeholder="Search driver, #, or team..."
            value={driverSearchQuery}
            onChange={(e) => setDriverSearchQuery(e.target.value)}
          />
          {driverSearchQuery && (
            <button 
              className="search-clear-btn"
              onClick={() => setDriverSearchQuery('')}
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        {/* Filter Dropdowns */}
        <div className="filter-dropdowns-row">
          {/* Team Filter */}
          <select 
            className="filter-select-dropdown"
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
          >
            <option value="ALL">All Teams ({availableTeams.length})</option>
            {availableTeams.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {/* Compound Filter */}
          <select 
            className="filter-select-dropdown"
            value={selectedCompound}
            onChange={(e) => setSelectedCompound(e.target.value)}
          >
            <option value="ALL">All Compounds</option>
            {availableCompounds.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      {/* 3. Driver Table (Scrollable full session roster) */}
      <div className="leaderboard-table-wrapper">
        <table className="leaderboard-table">
          <thead>
            <tr>
              <th className="th-pos">POS</th>
              <th className="th-driver">DRIVER</th>
              <th className="th-gap">GAP</th>
              <th className="th-int">INT</th>
              <th className="th-tyre">TYRE</th>
              <th className="th-debt">DEBT</th>
              <th className="th-action">VS</th>
            </tr>
          </thead>
          <tbody>
            {filteredLeaderboard.length === 0 ? (
              <tr>
                <td colSpan="7" className="empty-leaderboard-cell">
                  {driverSearchQuery || selectedTeam !== 'ALL' || selectedCompound !== 'ALL'
                    ? "No drivers match the current filters."
                    : "Loading session standings..."}
                </td>
              </tr>
            ) : (
              filteredLeaderboard.map((row) => {
                const isSelected = row.driver_id === selectedDriver;
                const isCompare = row.driver_id === comparisonDriver;
                const compoundColor = getCompoundColor(row.compound);
                const teamColor = getTeamColor(row.team, row.team_color);
                const hasTel = row.telemetry_available !== false;
                const portraitSrc = row.profile_image || `/drivers/${(row.driver_id || '').toLowerCase()}.webp`;
                const driverNum = row.driver_number || row.number || 0;

                return (
                  <tr 
                    key={row.driver_id}
                    className={`leaderboard-row ${isSelected ? 'selected-row' : ''} ${isCompare ? 'compare-row' : ''} ${!hasTel ? 'limited-telemetry-row' : ''}`}
                    onClick={() => selectDriver(row.driver_id)}
                  >
                    {/* Position */}
                    <td className="cell-pos">
                      <div className="pos-badge" style={{ borderLeft: `3px solid ${teamColor}` }}>
                        {row.position}
                      </div>
                    </td>

                    {/* Driver Portrait & Identity */}
                    <td className="cell-driver">
                      <div className="driver-portrait-identity-row">
                        {/* Compact Portrait */}
                        <div className="driver-mini-portrait-wrap" style={{ borderColor: teamColor }}>
                          <img 
                            src={portraitSrc} 
                            alt={`${row.full_name || row.driver_id} profile`}
                            className="driver-mini-portrait-img"
                            loading="lazy"
                            onError={(e) => {
                              e.currentTarget.onerror = null;
                              e.currentTarget.src = "/drivers/fallback_driver.webp";
                            }}
                          />
                        </div>

                        {/* Text & Flag Cluster */}
                        <div className="driver-name-block">
                          <div className="driver-code-row">
                            {driverNum > 0 && (
                              <span className="driver-num-badge" style={{ color: teamColor }}>
                                #{driverNum}
                              </span>
                            )}
                            <strong className="driver-code-text">{row.driver_id}</strong>
                            <CountryFlag code={row.country_code || row.nationality} size="sm" />
                          </div>
                          <span className="driver-team-sub" title={row.full_name}>
                            {row.team?.split(' ')[0] || ''}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Gap to Leader */}
                    <td className="cell-gap">
                      {row.position === 1 && hasTel ? (
                        <span className="leader-tag">LEADER</span>
                      ) : hasTel ? (
                        `+${(row.gap_to_leader || 0).toFixed(3)}s`
                      ) : (
                        <span className="telemetry-na-tag" title="Insufficient telemetry for this analysis">NO TEL</span>
                      )}
                    </td>

                    {/* Interval */}
                    <td className="cell-int">
                      {row.position === 1 || !hasTel ? '—' : `+${(row.interval || 0).toFixed(3)}s`}
                    </td>

                    {/* Tyre Compound & Age */}
                    <td className="cell-tyre">
                      {hasTel && row.compound && row.compound !== 'UNKNOWN' ? (
                        <div className="tyre-pill-small" style={{ borderColor: compoundColor }}>
                          <span style={{ color: compoundColor }}>{row.compound[0]}</span>
                          <span className="tyre-age-text">{row.tyre_age || 0}L</span>
                        </div>
                      ) : (
                        <span className="cell-dim-dash">—</span>
                      )}
                    </td>

                    {/* Tyre Debt */}
                    <td className={`cell-debt ${row.cumulative_debt > 0 ? 'debt-pos' : 'credit-pos'}`}>
                      {hasTel ? (
                        row.cumulative_debt > 0 ? `+${row.cumulative_debt.toFixed(2)}s` : `${row.cumulative_debt.toFixed(2)}s`
                      ) : (
                        <span className="cell-dim-dash">—</span>
                      )}
                    </td>

                    {/* VS Comparison Toggle */}
                    <td className="cell-action" onClick={(e) => e.stopPropagation()}>
                      <button 
                        className={`vs-btn ${isCompare ? 'active' : ''}`}
                        onClick={() => selectComparisonDriver(row.driver_id)}
                        title={isCompare ? "Remove from comparison" : `Compare with ${row.driver_id}`}
                      >
                        VS
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 4. Footer */}
      <div className="leaderboard-footer">
        <span className="footer-hint">
          Showing <strong>{filteredLeaderboard.length}</strong> of <strong>{totalDriversCount}</strong> drivers · Click row to inspect
        </span>
      </div>
    </div>
  );
}

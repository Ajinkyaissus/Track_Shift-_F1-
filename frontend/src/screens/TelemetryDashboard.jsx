import { useMemo } from 'react';
import { useCircuit } from '../context/CircuitContext';
import CircuitMap from '../components/CircuitMap';
import DriverCockpitHUD from '../components/DriverCockpitHUD';
import SessionLeaderboard from '../components/SessionLeaderboard';
import ReplayControlBar from '../components/ReplayControlBar';
import TelemetryTabs from '../components/TelemetryTabs';
import TrackShiftIntelligencePanel from '../components/TrackShiftIntelligencePanel';
import { CountryFlag, getCountryName } from '../utils/countryFlags';

export default function TelemetryDashboard() {
  const {
    selectedCircuit,
    circuitDetail,
    circuitMapData,
    selectedSession,
    sessionTelemetry,
    selectedDriver,
    comparisonDriver,
    selectDriver,
    selectCircuit,
    replayLap,
    replayProgress,
    totalLaps,
    isPlaying,
    loadingStage,
    error
  } = useCircuit();

  const countryCode = sessionTelemetry?.country_code || circuitDetail?.country_code;
  const countryName = sessionTelemetry?.country || circuitDetail?.country || getCountryName(countryCode);

  const sessionTitle = useMemo(() => {
    if (sessionTelemetry) {
      return `${sessionTelemetry.season || 2024} ${sessionTelemetry.event_name || 'Grand Prix'}`;
    }
    return '2024 Formula 1 Grand Prix';
  }, [sessionTelemetry]);

  const circuitName = useMemo(() => {
    return sessionTelemetry?.circuit_name || circuitDetail?.name || selectedCircuit || 'Circuit';
  }, [sessionTelemetry, circuitDetail, selectedCircuit]);

  if (loadingStage === 'session') {
    return (
      <div className="dashboard-loading-container">
        <div className="loading-box">
          <div className="pulse-dot"></div>
          <h2>Loading Historical Telemetry Session...</h2>
          <p className="loading-sub">{circuitName} · {selectedSession}</p>
        </div>
      </div>
    );
  }

  if (error || !sessionTelemetry) {
    return (
      <div className="dashboard-error-container">
        <div className="error-box">
          <h2>DATA UNAVAILABLE</h2>
          <p>{error || "Telemetry unavailable for this session."}</p>
          <div className="error-actions">
            <button className="race-btn active" onClick={() => selectCircuit(selectedCircuit)}>
              Select Another Session
            </button>
            <button className="back-btn" onClick={() => selectCircuit(null)}>
              ← Return to World
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-layout">
      {/* 1. HEADER */}
      <header className="dashboard-header">
        <div className="header-branding">
          <button 
            className="header-world-btn" 
            onClick={() => selectCircuit(null)}
            title="Return to Global F1 World View"
          >
            🌍 WORLD
          </button>

          <div className="header-breadcrumb-cluster">
            <div className="breadcrumb-country-badge" onClick={() => selectCircuit(null)} style={{ cursor: 'pointer' }}>
              <CountryFlag code={countryCode} size="sm" />
              <span className="breadcrumb-country">{countryName?.toUpperCase()}</span>
            </div>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-circuit-tag">{circuitName}</span>
          </div>

          <div className="session-title-cluster">
            <h1 className="header-session-name">{sessionTitle}</h1>
          </div>
        </div>

        <div className="header-right-tools">
          {/* Explicit Historical Replay Badge */}
          <div className="replay-badge-container">
            <span className={isPlaying ? "pulse-dot" : "idle-dot"}></span>
            <span className="replay-badge-text">HISTORICAL TELEMETRY REPLAY</span>
          </div>

          {/* Navigation Shortcuts */}
          <div className="header-nav-btns">
            <button 
              className="header-switch-btn"
              onClick={() => selectCircuit(selectedCircuit)}
              title="Switch session for current circuit"
            >
              Sessions
            </button>
            <button 
              className="header-switch-btn outline"
              onClick={() => selectCircuit(null)}
              title="Return to Global F1 World View"
            >
              Globe
            </button>
          </div>
        </div>
      </header>

      {/* 2. MAIN 3-COLUMN WORKSPACE (Left: HUD, Center: Map, Right: Leaderboard) */}
      <main className="dashboard-workspace">
        {/* LEFT PANEL: Cockpit & Tyre HUD */}
        <aside className="workspace-left-panel">
          <DriverCockpitHUD />
        </aside>

        {/* CENTER PANEL: Interactive Circuit Geometry Map */}
        <section className="workspace-center-map">
          <CircuitMap
            mapData={circuitMapData}
            drivers={sessionTelemetry?.drivers || []}
            selectedDriver={selectedDriver}
            comparisonDriver={comparisonDriver}
            replayProgress={replayProgress}
            replayLap={replayLap}
            totalLaps={totalLaps}
            isPlaying={isPlaying}
            onSelectDriver={selectDriver}
            weatherData={sessionTelemetry?.weather}
          />
        </section>

        {/* RIGHT PANEL: Session-Aware Dynamic Leaderboard */}
        <aside className="workspace-right-panel">
          <SessionLeaderboard />
        </aside>
      </main>

      {/* 3. BOTTOM SECTION: Controls, Timeline, Telemetry Charts & TrackShift Intelligence */}
      <footer className="dashboard-bottom-section">
        {/* Replay Controls & Lap Timeline */}
        <ReplayControlBar />

        {/* Telemetry Tabs (Speed, Throttle, Brake, Gear, Delta, Tyre Debt, Behaviour, TCN) */}
        <TelemetryTabs />

        {/* Dedicated TrackShift Intelligence Panel */}
        <TrackShiftIntelligencePanel />
      </footer>
    </div>
  );
}

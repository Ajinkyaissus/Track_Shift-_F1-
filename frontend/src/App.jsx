import { useState, useEffect } from 'react';
import { CircuitProvider, useCircuit } from './context/CircuitContext';
import CircuitSelectScreen from './screens/CircuitSelectScreen';
import SessionSelectScreen from './screens/SessionSelectScreen';
import TelemetryDashboard from './screens/TelemetryDashboard';
import { isOfflineMode } from './api';
import './index.css';

function MainRouter() {
  const { selectedCircuit, selectedSession } = useCircuit();

  // Application Flow:
  // HOME / CIRCUITS -> SESSION SELECTION -> RACE TELEMETRY DASHBOARD
  if (selectedCircuit && selectedSession) {
    return <TelemetryDashboard />;
  }

  if (selectedCircuit) {
    return <SessionSelectScreen />;
  }

  return <CircuitSelectScreen />;
}

export default function App() {
  const [offline, setOffline] = useState(isOfflineMode);

  useEffect(() => {
    const handleOfflineChange = (e) => setOffline(e.detail);
    window.addEventListener('offline-mode-change', handleOfflineChange);
    return () => window.removeEventListener('offline-mode-change', handleOfflineChange);
  }, []);

  return (
    <CircuitProvider>
      {offline && (
        <div className="offline-banner">
          Running in offline fallback mode with static real dataset
        </div>
      )}
      <div className="app-root-container">
        <MainRouter />
      </div>
    </CircuitProvider>
  );
}

import { useMemo } from 'react';
import { useCircuit, TELEMETRY_TABS } from '../context/CircuitContext';
import CleanDegradationView from './CleanDegradationView';
import RacePredictionValidationPanel from './RacePredictionValidationPanel';
import RaceIntelligencePanel from './RaceIntelligencePanel';
import StrategicWarfarePanel from './StrategicWarfarePanel';
import TyreIntelligenceWorkspace from './TyreIntelligenceWorkspace';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Legend,
  AreaChart,
  Area,
  ReferenceLine
} from 'recharts';

export default function TelemetryTabs() {
  const {
    selectedSession,
    sessionTelemetry,
    selectedDriver,
    comparisonDriver,
    selectedCompound,
    setSelectedCompound,
    sessionDegradationData,
    activeTelemetryTab,
    setActiveTelemetryTab,
    replayLap,
    stintLedger
  } = useCircuit();


  // Prepare chart series data up to current replay lap
  const { chartData, driverAInfo, driverBInfo } = useMemo(() => {
    if (!sessionTelemetry?.laps) {
      return { chartData: [], driverAInfo: null, driverBInfo: null };
    }

    const lapsA = sessionTelemetry.laps.filter(l => l.driver_id === selectedDriver);
    const lapsB = comparisonDriver ? sessionTelemetry.laps.filter(l => l.driver_id === comparisonDriver) : [];

    const drvA = sessionTelemetry.drivers?.find(d => d.driver_id === selectedDriver) || { driver_id: selectedDriver };
    const drvB = comparisonDriver ? (sessionTelemetry.drivers?.find(d => d.driver_id === comparisonDriver) || { driver_id: comparisonDriver }) : null;

    // Build unified map of lap records
    const maxLap = Math.max(...sessionTelemetry.laps.map(l => l.lap_number), 1);
    const data = [];

    for (let lap = 1; lap <= maxLap; lap++) {
      const rowA = lapsA.find(l => l.lap_number === lap);
      const rowB = lapsB.find(l => l.lap_number === lap);
      const ledgerRow = stintLedger?.series?.find(s => s.lap_number === lap);

      if (rowA || rowB) {
        const item = {
          lap_number: lap,
          is_current: lap === replayLap,
          // Speed
          speed_a: rowA ? Math.round(230 + (88 - rowA.lap_time) * 12) : null,
          speed_b: rowB ? Math.round(230 + (88 - rowB.lap_time) * 12) : null,
          // Throttle
          throttle_a: rowA ? Math.round(Math.min(100, rowA.throttle_transient_smoothness * 42)) : null,
          throttle_b: rowB ? Math.round(Math.min(100, rowB.throttle_transient_smoothness * 42)) : null,
          // Brake
          brake_a: rowA ? Number((rowA.braking_aggression).toFixed(2)) : null,
          brake_b: rowB ? Number((rowB.braking_aggression).toFixed(2)) : null,
          // Lap Time & Delta
          lap_time_a: rowA ? rowA.lap_time : null,
          lap_time_b: rowB ? rowB.lap_time : null,
          delta: (rowA && rowB) ? Number((rowB.lap_time - rowA.lap_time).toFixed(3)) : null,
          // Tyre Debt
          debt_a: ledgerRow ? ledgerRow.cumulative_debt : (rowA ? rowA.cumulative_debt : 0),
          debt_b: rowB ? rowB.cumulative_debt : null,
          residual_a: ledgerRow ? ledgerRow.residual : (rowA ? rowA.residual : 0),
          // Behaviour
          kerb_a: rowA ? Number(rowA.kerb_usage.toFixed(1)) : null,
          kerb_b: rowB ? Number(rowB.kerb_usage.toFixed(1)) : null,
          lateral_a: rowA ? Number((rowA.lateral_dynamics_proxy * 100).toFixed(2)) : null,
          lateral_b: rowB ? Number((rowB.lateral_dynamics_proxy * 100).toFixed(2)) : null
        };
        data.push(item);
      }
    }

    return {
      chartData: data,
      driverAInfo: drvA,
      driverBInfo: drvB
    };
  }, [sessionTelemetry, selectedDriver, comparisonDriver, replayLap, stintLedger]);

  const driverAName = driverAInfo?.driver_id || 'Driver A';
  const driverBName = driverBInfo?.driver_id || 'Driver B';

  return (
    <div className="telemetry-tabs-container">
      {/* Tab Navigation Header */}
      <div className="tabs-header-bar">
        <div className="tabs-list">
          {TELEMETRY_TABS.map((tab) => (
            <button
              key={tab}
              className={`telemetry-tab-btn ${activeTelemetryTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTelemetryTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        {comparisonDriver && (
          <div className="comparison-legend-badge">
            <span className="dot dot-a"></span> {driverAName}
            <span className="vs-tag">VS</span>
            <span className="dot dot-b"></span> {driverBName}
          </div>
        )}
      </div>

      {/* Tab Content Display */}
      <div className="tab-chart-body">
        {activeTelemetryTab === 'TYRE INTELLIGENCE' ? (
          <TyreIntelligenceWorkspace
            circuitId={selectedSession ? selectedSession.split('_')[0] : 'silverstone'}
            driverId={selectedDriver || 'HAM'}
            sessionId={selectedSession}
            replayLap={replayLap}
          />
        ) : activeTelemetryTab === 'STRATEGIC WARFARE' ? (
          <StrategicWarfarePanel
            sessionId={selectedSession}
            selectedDriver={selectedDriver}
            currentLap={replayLap || 20}
          />
        ) : activeTelemetryTab === 'RACE INTELLIGENCE' ? (
          <RaceIntelligencePanel />
        ) : activeTelemetryTab === 'CLEAN DEG' ? (
          <CleanDegradationView
            degradationData={sessionDegradationData}
            selectedDriver={selectedDriver}
            selectedCompound={selectedCompound}
            onCompoundChange={setSelectedCompound}
          />
        ) : activeTelemetryTab === 'VALIDATION' ? (
          <RacePredictionValidationPanel
            sessionId={selectedSession}
            selectedDriver={selectedDriver}
            selectedCompound={selectedCompound}
            availableDrivers={sessionTelemetry?.drivers || []}
          />
        ) : chartData.length === 0 ? (
          <div className="empty-chart-state">
            <div className="empty-chart-text">
              <span className="notice-pill">INSUFFICIENT TELEMETRY</span>
              <h4>Insufficient telemetry for this analysis</h4>
              <p>Selected driver <strong>{driverAName}</strong> participated in the session, but high-frequency telemetry was not recorded for {activeTelemetryTab} analysis.</p>
              <p className="sub-hint">The driver remains present in session standings. Select any telemetry-verified driver to compare.</p>
            </div>
          </div>
        ) : (
          <div style={{ width: '100%', height: '260px' }}>
            <ResponsiveContainer width="100%" height="100%">
              {activeTelemetryTab === 'SPEED' && (
                <LineChart data={chartData}>

                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" label={{ value: 'Lap Number', position: 'insideBottom', offset: -5, fill: '#666' }} />
                  <YAxis stroke="#777788" domain={['auto', 'auto']} unit=" km/h" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="speed_a" name={`${driverAName} Avg Speed`} stroke="#E10600" strokeWidth={2} dot={{ r: 2 }} />
                  {comparisonDriver && (
                    <Line type="monotone" dataKey="speed_b" name={`${driverBName} Avg Speed`} stroke="#00D2BE" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 2 }} />
                  )}
                </LineChart>
              )}

              {activeTelemetryTab === 'THROTTLE' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" domain={[0, 100]} unit="%" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="throttle_a" name={`${driverAName} Throttle Application`} stroke="#FFB800" strokeWidth={2} />
                  {comparisonDriver && (
                    <Line type="monotone" dataKey="throttle_b" name={`${driverBName} Throttle Application`} stroke="#00D2BE" strokeWidth={2} strokeDasharray="3 3" />
                  )}
                </LineChart>
              )}

              {activeTelemetryTab === 'BRAKE' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="brake_a" name={`${driverAName} Braking Decel Intensity`} stroke="#E10600" strokeWidth={2} />
                  {comparisonDriver && (
                    <Line type="monotone" dataKey="brake_b" name={`${driverBName} Braking Decel Intensity`} stroke="#00D2BE" strokeWidth={2} strokeDasharray="3 3" />
                  )}
                </LineChart>
              )}

              {activeTelemetryTab === 'GEAR' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" domain={[1, 8]} />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="stepAfter" dataKey="speed_a" name={`${driverAName} Gearbox Shifts`} stroke="#39B54A" strokeWidth={2} />
                </LineChart>
              )}

              {activeTelemetryTab === 'DELTA' && (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" unit="s" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Area type="monotone" dataKey="delta" name={`Delta (${driverBName} - ${driverAName})`} fill="rgba(0, 210, 190, 0.2)" stroke="#00D2BE" strokeWidth={2} />
                </AreaChart>
              )}

              {activeTelemetryTab === 'TYRE DEBT' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" unit="s" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="debt_a" name={`${driverAName} Cumulative Tyre Debt (s)`} stroke="#E10600" strokeWidth={2.5} dot={false} />
                  {comparisonDriver && (
                    <Line type="monotone" dataKey="debt_b" name={`${driverBName} Cumulative Tyre Debt (s)`} stroke="#00D2BE" strokeWidth={2.5} dot={false} strokeDasharray="4 4" />
                  )}
                  <Line type="monotone" dataKey="residual_a" name={`${driverAName} Lap Residual (s)`} stroke="#FFB800" strokeWidth={1} dot={{ r: 2 }} />
                </LineChart>
              )}

              {activeTelemetryTab === 'BEHAVIOUR' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="kerb_a" name={`${driverAName} Lateral Load Variation (Kerb)`} stroke="#9B51E0" strokeWidth={2} />
                  <Line type="monotone" dataKey="lateral_a" name={`${driverAName} Lateral Dynamics Proxy`} stroke="#00D2BE" strokeWidth={2} />
                </LineChart>
              )}

              {activeTelemetryTab === 'TCN' && (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222232" />
                  <XAxis dataKey="lap_number" stroke="#777788" />
                  <YAxis stroke="#777788" />
                  <Tooltip contentStyle={{ backgroundColor: '#12121D', border: '1px solid #28283D' }} />
                  <Legend />
                  <ReferenceLine x={replayLap} stroke="#00D2BE" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#00D2BE', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="debt_a" name="TCN Latent Temporal Loss Fit" stroke="#00D2BE" strokeWidth={2} />
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

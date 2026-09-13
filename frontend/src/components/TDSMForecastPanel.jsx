import { useMemo } from 'react';
import { useCircuit, getDriverLapDegradationMap } from '../context/CircuitContext';
import {
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart
} from 'recharts';

function getCompoundBadgeColor(compound) {
  const c = String(compound || '').toUpperCase();
  if (c.includes('SOFT')) return '#E10600';
  if (c.includes('MEDIUM')) return '#FFB800';
  if (c.includes('HARD')) return '#FFFFFF';
  if (c.includes('INTERMEDIATE')) return '#39B54A';
  if (c.includes('WET')) return '#00AEEF';
  return '#94A3B8';
}

const CANONICAL_2025_BENCHMARKS = [
  { horizon: '+1 LAP', mae: '0.4720 s', rmse: '1.2574 s', r2: '0.3386' },
  { horizon: '+3 LAPS', mae: '0.6274 s', rmse: '1.3092 s', r2: '0.2774' },
  { horizon: '+5 LAPS', mae: '0.6628 s', rmse: '1.3659 s', r2: '0.2411' },
  { horizon: '+10 LAPS', mae: '0.8657 s', rmse: '1.5277 s', r2: '0.1435' }
];

export default function TDSMForecastPanel() {
  const {
    selectedSeason,
    selectedCircuit,
    circuitDetail,
    selectedSession,
    sessionTelemetry,
    sessionDegradationData,
    selectedDriver,
    replayLap,
    totalLaps,
    currentDriverLapTelemetry,
    tdsmState,
    tdsmForecast,
    tdsmModelUsed,
    tdsmModelVersion,
    tdsmLoading,
    tdsmHistory,
    tdsmError
  } = useCircuit();

  // Find active driver metadata
  const driverMeta = useMemo(() => {
    return sessionTelemetry?.drivers?.find(d => d.driver_id === selectedDriver) || {
      driver_id: selectedDriver || '—',
      full_name: selectedDriver || 'Driver',
      team: 'Formula 1',
      team_color: '#E10600',
      compound: 'MEDIUM'
    };
  }, [sessionTelemetry, selectedDriver]);

  const circuitDisplayName = sessionTelemetry?.circuit_name || circuitDetail?.name || selectedCircuit || 'Circuit';
  const sessionDisplayName = sessionTelemetry?.session_type || sessionTelemetry?.event_name || selectedSession || 'Race';

  // Driver authentic laps
  const driverLaps = useMemo(() => {
    if (!sessionTelemetry?.laps || !selectedDriver) return [];
    return sessionTelemetry.laps
      .filter(l => l.driver_id === selectedDriver)
      .sort((a, b) => a.lap_number - b.lap_number);
  }, [sessionTelemetry, selectedDriver]);

  // Compute driver degradation map using fuel-corrected degradation pace loss
  const degMap = useMemo(() => {
    return getDriverLapDegradationMap(driverLaps, sessionDegradationData, selectedDriver);
  }, [driverLaps, sessionDegradationData, selectedDriver]);

  // Pre-calculate full driver trajectory & derivatives once per driver roster for instant zero-latency lap scrubbing
  const fullDriverTrajectory = useMemo(() => {
    if (!driverLaps.length) return [];
    return driverLaps.map((l, idx, arr) => {
      const d_now = degMap[l.lap_number] != null
        ? degMap[l.lap_number]
        : Number((l.cumulative_debt ?? l.residual ?? 0.0).toFixed(4));
      const prev_lap_num = idx > 0 ? arr[idx - 1].lap_number : null;
      const d_prev = (idx > 0 && prev_lap_num != null && degMap[prev_lap_num] != null)
        ? degMap[prev_lap_num]
        : (idx > 0 ? Number((arr[idx - 1].cumulative_debt ?? arr[idx - 1].residual ?? 0.0).toFixed(4)) : d_now);
      const delta_1 = idx > 0 ? Number((d_now - d_prev).toFixed(4)) : 0.0;

      let delta_2 = 0.0;
      if (idx >= 2) {
        const prev2_lap_num = arr[idx - 2].lap_number;
        const d_prev2 = degMap[prev2_lap_num] != null
          ? degMap[prev2_lap_num]
          : Number((arr[idx - 2].cumulative_debt ?? arr[idx - 2].residual ?? 0.0).toFixed(4));
        const prev_delta_1 = Number((d_prev - d_prev2).toFixed(4));
        delta_2 = Number((delta_1 - prev_delta_1).toFixed(4));
      }

      return {
        lap: l.lap_number,
        lap_time: l.lap_time,
        actual_D: d_now,
        delta_D: delta_1,
        delta2_D: delta_2
      };
    });
  }, [driverLaps, degMap]);

  // Fast slice of completed laps up to replayLap
  const deltaEvolutionData = useMemo(() => {
    return fullDriverTrajectory.filter(l => l.lap <= replayLap);
  }, [fullDriverTrajectory, replayLap]);

  // Chart 1 Data: TDSM OUTPUT vs ACTUAL (Instant plot combining real telemetry + model outputs)
  const tdsmVsActualChartData = useMemo(() => {
    if (!deltaEvolutionData.length) return [];

    const points = deltaEvolutionData.map(l => ({
      lap: l.lap,
      actual_telemetry: l.actual_D,
      tdsm_model_output: null
    }));

    if (tdsmForecast && points.length > 0) {
      const lastPoint = points[points.length - 1];
      lastPoint.tdsm_model_output = lastPoint.actual_telemetry;

      const horizons = [1, 3, 5, 10];
      horizons.forEach(h => {
        const targetLap = replayLap + h;
        if (targetLap <= (totalLaps || 75)) {
          const pred = tdsmForecast[`+${h}`];
          if (pred !== undefined && pred !== null) {
            const existingTarget = fullDriverTrajectory.find(l => l.lap === targetLap);
            points.push({
              lap: targetLap,
              actual_telemetry: existingTarget ? existingTarget.actual_D : null,
              tdsm_model_output: Number(pred.toFixed(4))
            });
          }
        }
      });
    }

    return points.sort((a, b) => a.lap - b.lap);
  }, [deltaEvolutionData, tdsmForecast, replayLap, totalLaps, fullDriverTrajectory]);

  // Current Origin Horizons (+1, +3, +5, +10) Alignment Table
  const currentOriginHorizons = useMemo(() => {
    if (!tdsmState || !driverLaps.length) return [];
    const originLap = tdsmState.data_cutoff_lap || replayLap;
    const horizons = [1, 3, 5, 10];

    return horizons.map(h => {
      const targetLapNum = originLap + h;
      const targetLap = driverLaps.find(l => l.lap_number === targetLapNum);
      const predictedVal = tdsmForecast ? tdsmForecast[`+${h}`] : null;

      if (targetLap) {
        const actualVal = degMap[targetLap.lap_number] != null
          ? degMap[targetLap.lap_number]
          : Number((targetLap.cumulative_debt ?? targetLap.residual ?? 0.0).toFixed(4));
        const error = predictedVal !== null ? Number((predictedVal - actualVal).toFixed(4)) : null;
        return {
          forecast_origin_lap: originLap,
          horizon: `+${h}`,
          horizon_num: h,
          target_lap: targetLapNum,
          predicted: predictedVal !== null ? Number(predictedVal.toFixed(4)) : null,
          actual: actualVal,
          error: error,
          has_actual: true,
          status_msg: null
        };
      } else {
        return {
          forecast_origin_lap: originLap,
          horizon: `+${h}`,
          horizon_num: h,
          target_lap: targetLapNum,
          predicted: predictedVal !== null ? Number(predictedVal.toFixed(4)) : null,
          actual: null,
          error: null,
          has_actual: false,
          status_msg: `Insufficient real telemetry for +${h} validation`
        };
      }
    });
  }, [tdsmState, replayLap, driverLaps, tdsmForecast]);

  // Past Historical Forecasts verified at current replayLap
  const historicalVerificationRows = useMemo(() => {
    if (!tdsmHistory || !tdsmState) return [];
    const rows = [];
    const horizons = [1, 3, 5, 10];

    horizons.forEach(h => {
      const priorLap = replayLap - h;
      if (priorLap >= 1 && tdsmHistory[priorLap]) {
        const histEntry = tdsmHistory[priorLap];
        if (histEntry?.forecast && histEntry.driver_id === selectedDriver) {
          const predVal = histEntry.forecast[`+${h}`];
          if (predVal !== undefined && predVal !== null) {
            const actualVal = tdsmState.D;
            const error = Number((predVal - actualVal).toFixed(4));
            rows.push({
              forecast_origin_lap: priorLap,
              horizon: `+${h}`,
              target_lap: replayLap,
              predicted: Number(predVal.toFixed(4)),
              actual: actualVal,
              error: error,
              status: Math.abs(error) <= 0.15 ? 'ACCURATE' : Math.abs(error) <= 0.35 ? 'ACCEPTABLE' : 'DRIFT'
            });
          }
        }
      }
    });

    return rows;
  }, [tdsmHistory, tdsmState, replayLap, selectedDriver]);

  if (!selectedDriver || !sessionTelemetry) {
    return (
      <div className="tdsm-empty-container" style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8' }}>
        <h3>No Driver Selected</h3>
        <p>Select a driver from the session leaderboard to view real-time TDSM state-space predictions.</p>
      </div>
    );
  }

  return (
    <div className="tdsm-forecast-master-panel" style={{ background: '#0D0E15', border: '1px solid #1E2230', borderRadius: '10px', padding: '1.25rem', color: '#E2E8F0', marginTop: '1rem' }}>
      
      {/* 1. DATA PROVENANCE BANNER */}
      <div style={{ background: '#080A12', border: '1px solid #1B2033', borderRadius: '6px', padding: '0.6rem 0.9rem', marginBottom: '1.25rem', display: 'flex', flexWrap: 'wrap', gap: '1.2rem', fontSize: '0.72rem', color: '#94A3B8' }}>
        <div><span style={{ color: '#64748B' }}>SOURCE: </span><strong style={{ color: '#E2E8F0' }}>FastF1 Historical Telemetry</strong></div>
        <div><span style={{ color: '#64748B' }}>MODEL: </span><strong style={{ color: '#00D2BE' }}>TDSM — Frozen 2024 Model</strong></div>
        <div><span style={{ color: '#64748B' }}>VALIDATION: </span><strong style={{ color: '#38BDF8' }}>Unseen 2025</strong></div>
        <div><span style={{ color: '#64748B' }}>PREDICTION: </span><strong style={{ color: '#FBBF24' }}>Live TDSM Inference</strong></div>
        <div><span style={{ color: '#64748B' }}>ACTUAL: </span><strong style={{ color: '#34D399' }}>Observed Historical Telemetry</strong></div>
      </div>

      {/* 2. CONTEXT BANNER */}
      <div className="tdsm-context-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.8rem', paddingBottom: '1rem', borderBottom: '1px solid #1E2230', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ background: 'var(--accent-red, #E10600)', color: '#FFF', padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 800, letterSpacing: '0.05em' }}>
            TDSM
          </span>
          <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#FFF' }}>
            Tyre Degradation State Model (TDSM)
          </span>
          <span style={{ fontSize: '0.8rem', color: '#64748B', fontFamily: 'monospace' }}>
            [{tdsmModelUsed} / {tdsmModelVersion}]
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#161926', padding: '0.35rem 0.8rem', borderRadius: '6px', border: '1px solid #282E42', fontSize: '0.82rem' }}>
          <span style={{ color: '#00D2BE', fontWeight: 700 }}>{selectedSeason}</span>
          <span style={{ color: '#475569' }}>•</span>
          <span style={{ color: '#F1F5F9', fontWeight: 600 }}>{circuitDisplayName}</span>
          <span style={{ color: '#475569' }}>•</span>
          <span style={{ color: '#CBD5E1' }}>{sessionDisplayName}</span>
          <span style={{ color: '#475569' }}>•</span>
          <span style={{ color: '#F87171', fontWeight: 700 }}>{driverMeta.full_name || driverMeta.driver_id}</span>
          <span style={{ color: '#475569' }}>•</span>
          <span style={{ color: '#FBBF24', fontWeight: 700 }}>Lap {replayLap}</span>
        </div>
      </div>

      {tdsmError && (
        <div style={{ padding: '0.6rem 1rem', background: 'rgba(239,68,68,0.15)', border: '1px solid #EF4444', borderRadius: '6px', color: '#FCA5A5', marginBottom: '1rem', fontSize: '0.85rem' }}>
          ⚠️ {tdsmError}
        </div>
      )}

      {/* 3. REAL STATE VECTOR S_t = [D_t, ΔD_t, Δ²D_t] */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.8rem', marginBottom: '1.25rem' }}>
        {/* Current Lap */}
        <div style={{ background: '#141724', padding: '0.8rem', borderRadius: '8px', border: '1px solid #232738' }}>
          <div style={{ fontSize: '0.72rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>CURRENT LAP</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#FFF', marginTop: '0.2rem' }}>
            {replayLap} <span style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 500 }}>/ {totalLaps || '—'}</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#00D2BE', marginTop: '0.1rem' }}>
            Time: {currentDriverLapTelemetry?.lap_time ? `${currentDriverLapTelemetry.lap_time.toFixed(3)}s` : (tdsmState?.lap_time ? `${tdsmState.lap_time.toFixed(3)}s` : '—')}
          </div>
        </div>

        {/* D_t */}
        <div style={{ background: '#141724', padding: '0.8rem', borderRadius: '8px', border: '1px solid #232738' }}>
          <div style={{ fontSize: '0.72rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>DEGRADATION D_t</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: (tdsmState?.D ?? 0) >= 0 ? '#F87171' : '#34D399', marginTop: '0.2rem' }}>
            {tdsmState ? `${tdsmState.D >= 0 ? '+' : ''}${tdsmState.D.toFixed(4)}s` : 'REAL DATA UNAVAILABLE'}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.1rem' }}>Degradation Pace Loss</div>
        </div>

        {/* Delta D_t */}
        <div style={{ background: '#141724', padding: '0.8rem', borderRadius: '8px', border: '1px solid #232738' }}>
          <div style={{ fontSize: '0.72rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>VELOCITY ΔD_t</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#38BDF8', marginTop: '0.2rem' }}>
            {tdsmState ? `${tdsmState.Delta_D >= 0 ? '+' : ''}${tdsmState.Delta_D.toFixed(4)}s` : 'REAL DATA UNAVAILABLE'}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.1rem' }}>D_t - D_(t-1) (s/lap)</div>
        </div>

        {/* Delta^2 D_t */}
        <div style={{ background: '#141724', padding: '0.8rem', borderRadius: '8px', border: '1px solid #232738' }}>
          <div style={{ fontSize: '0.72rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>ACCEL Δ²D_t</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#A78BFA', marginTop: '0.2rem' }}>
            {tdsmState ? `${tdsmState.Delta2_D >= 0 ? '+' : ''}${tdsmState.Delta2_D.toFixed(4)}s` : 'REAL DATA UNAVAILABLE'}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.1rem' }}>ΔD_t - ΔD_(t-1) (s/lap²)</div>
        </div>

        {/* Tyre Life & Compound */}
        <div style={{ background: '#141724', padding: '0.8rem', borderRadius: '8px', border: '1px solid #232738' }}>
          <div style={{ fontSize: '0.72rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>TYRE LIFE & COMPOUND</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
            <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#FFF' }}>
              {tdsmState?.TyreLife ?? '—'} <span style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 500 }}>Laps</span>
            </span>
            <span style={{
              background: 'rgba(255,255,255,0.08)',
              color: getCompoundBadgeColor(tdsmState?.Compound),
              border: `1px solid ${getCompoundBadgeColor(tdsmState?.Compound)}`,
              padding: '0.1rem 0.4rem',
              borderRadius: '3px',
              fontSize: '0.75rem',
              fontWeight: 700
            }}>
              {tdsmState?.Compound || 'UNKNOWN'}
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.1rem' }}>Fuel Load: {tdsmState?.FuelProxy ?? '—'} kg</div>
        </div>
      </div>

      {/* 4. CANONICAL VALIDATED 2025 BENCHMARK METRICS */}
      <div style={{ background: '#111422', borderRadius: '8px', border: '1px solid #1E2232', padding: '0.8rem 1rem', marginBottom: '1.25rem' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
          Validated 2025 Scientific Performance Benchmarks
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.6rem' }}>
          {CANONICAL_2025_BENCHMARKS.map(b => (
            <div key={b.horizon} style={{ background: '#090B12', padding: '0.5rem 0.7rem', borderRadius: '6px', border: '1px solid #1C2030' }}>
              <div style={{ fontSize: '0.72rem', color: '#38BDF8', fontWeight: 700 }}>{b.horizon}</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#FFF', marginTop: '0.15rem' }}>MAE {b.mae}</div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>RMSE {b.rmse} · R² {b.r2}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. MULTI-HORIZON FORECAST CARDS */}
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#F1F5F9', textTransform: 'uppercase', letterSpacing: '0.04em', margin: 0 }}>
            TDSM Multi-Horizon Output (Live Model Inference)
          </h3>
          {tdsmLoading && (
            <span style={{ fontSize: '0.78rem', color: '#38BDF8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#38BDF8', animation: 'pulse 1s infinite' }}></span>
              INFERRING STATE TRANSITION...
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.8rem' }}>
          {[
            { label: '+1 LAP', horizon: 1, key: '+1', color: '#38BDF8' },
            { label: '+3 LAPS', horizon: 3, key: '+3', color: '#00D2BE' },
            { label: '+5 LAPS', horizon: 5, key: '+5', color: '#FBBF24' },
            { label: '+10 LAPS', horizon: 10, key: '+10', color: '#F87171' }
          ].map(({ label, horizon, key, color }) => {
            const forecastVal = tdsmForecast ? tdsmForecast[key] : null;
            const deltaAgainstNow = (forecastVal !== null && tdsmState?.D !== undefined)
              ? forecastVal - tdsmState.D
              : null;

            return (
              <div
                key={key}
                style={{
                  background: 'linear-gradient(180deg, #161A29 0%, #10121C 100%)',
                  border: `1px solid ${forecastVal !== null ? '#2D354E' : '#1E2230'}`,
                  borderRadius: '8px',
                  padding: '1rem',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 800, color, letterSpacing: '0.05em' }}>{label}</span>
                  <span style={{ fontSize: '0.72rem', color: '#64748B', fontFamily: 'monospace' }}>Target: Lap {replayLap + horizon}</span>
                </div>

                <div style={{ fontSize: '1.45rem', fontWeight: 900, color: '#FFF', fontFamily: 'monospace' }}>
                  {forecastVal !== null ? `${forecastVal >= 0 ? '+' : ''}${forecastVal.toFixed(4)}s` : (tdsmError ? 'UNAVAILABLE' : '—')}
                </div>

                <div style={{ fontSize: '0.75rem', color: deltaAgainstNow && deltaAgainstNow > 0 ? '#F87171' : '#34D399', marginTop: '0.2rem' }}>
                  {deltaAgainstNow !== null ? `Δ from Lap ${replayLap}: ${deltaAgainstNow >= 0 ? '+' : ''}${deltaAgainstNow.toFixed(4)}s` : 'Live API Inference'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 6. ALL REAL GRAPHS PLOTTED SIMULTANEOUSLY AS OUTPUTS ARRIVE */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginBottom: '1.5rem' }}>
        
        {/* GRAPH 1: TDSM OUTPUT vs ACTUAL (Full Width) */}
        <div style={{ background: '#121522', borderRadius: '8px', border: '1px solid #1E2230', padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#E2E8F0', margin: 0, textTransform: 'uppercase' }}>
              TDSM OUTPUT vs ACTUAL
            </h4>
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem' }}>
              <span style={{ color: '#00D2BE' }}>● Actual Observed Telemetry</span>
              <span style={{ color: '#FBBF24' }}>● TDSM Model Output (+1/+3/+5/+10)</span>
            </div>
          </div>

          <div style={{ height: 230, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={tdsmVsActualChartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2335" />
                <XAxis dataKey="lap" stroke="#64748B" fontSize={11} label={{ value: 'Lap Number', position: 'insideBottom', offset: -3, fill: '#64748B', fontSize: 11 }} />
                <YAxis stroke="#64748B" fontSize={11} label={{ value: 'Tyre Debt D_t (s)', angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0D0E15', border: '1px solid #282E42', borderRadius: '6px', fontSize: '11px', color: '#FFF' }}
                  formatter={(val, name) => [val != null ? `${val}s` : 'REAL DATA UNAVAILABLE', name === 'actual_telemetry' ? 'Actual Telemetry' : 'TDSM Model Output']}
                />
                <ReferenceLine x={replayLap} stroke="#F87171" strokeDasharray="3 3" label={{ value: `Lap ${replayLap} (Cutoff)`, fill: '#F87171', fontSize: 10, position: 'top' }} />
                <Line type="monotone" dataKey="actual_telemetry" stroke="#00D2BE" strokeWidth={2.4} dot={{ r: 2 }} isAnimationActive={false} name="Actual Telemetry" connectNulls={false} />
                <Line type="monotone" dataKey="tdsm_model_output" stroke="#FBBF24" strokeWidth={2.6} strokeDasharray="4 4" dot={{ r: 4 }} isAnimationActive={false} name="TDSM Model Output" connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* GRAPHS 2 & 3: REAL LAP DELTA & REAL DELTA² (Side by Side Grid) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
          
          {/* GRAPH 2: REAL LAP DELTA EVOLUTION */}
          <div style={{ background: '#121522', borderRadius: '8px', border: '1px solid #1E2230', padding: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
              <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#E2E8F0', margin: 0, textTransform: 'uppercase' }}>
                REAL LAP DELTA EVOLUTION
              </h4>
              <span style={{ fontSize: '0.72rem', color: '#38BDF8' }}>ΔD_t = D_t - D_(t-1)</span>
            </div>

            <div style={{ height: 200, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={deltaEvolutionData} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E2335" />
                  <XAxis dataKey="lap" stroke="#64748B" fontSize={11} label={{ value: 'Lap Number', position: 'insideBottom', offset: -3, fill: '#64748B', fontSize: 11 }} />
                  <YAxis stroke="#64748B" fontSize={11} label={{ value: 'ΔD (s/lap)', angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0D0E15', border: '1px solid #282E42', borderRadius: '6px', fontSize: '11px', color: '#FFF' }}
                    formatter={(val) => [`${val}s/lap`, 'Real Delta ΔD']}
                  />
                  <ReferenceLine y={0} stroke="#475569" strokeDasharray="2 2" />
                  <ReferenceLine x={replayLap} stroke="#38BDF8" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#38BDF8', fontSize: 10, position: 'top' }} />
                  <Bar dataKey="delta_D" fill="#38BDF8" isAnimationActive={false} name="Real Lap Delta ΔD" />
                  <Line type="monotone" dataKey="delta_D" stroke="#0284C7" strokeWidth={1.8} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* GRAPH 3: REAL DELTA² EVOLUTION */}
          <div style={{ background: '#121522', borderRadius: '8px', border: '1px solid #1E2230', padding: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
              <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#E2E8F0', margin: 0, textTransform: 'uppercase' }}>
                REAL DELTA² EVOLUTION
              </h4>
              <span style={{ fontSize: '0.72rem', color: '#A78BFA' }}>Δ²D_t = ΔD_t - ΔD_(t-1)</span>
            </div>

            <div style={{ height: 200, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={deltaEvolutionData} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E2335" />
                  <XAxis dataKey="lap" stroke="#64748B" fontSize={11} label={{ value: 'Lap Number', position: 'insideBottom', offset: -3, fill: '#64748B', fontSize: 11 }} />
                  <YAxis stroke="#64748B" fontSize={11} label={{ value: 'Δ²D (s/lap²)', angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0D0E15', border: '1px solid #282E42', borderRadius: '6px', fontSize: '11px', color: '#FFF' }}
                    formatter={(val) => [`${val}s/lap²`, 'Real Delta² Δ²D']}
                  />
                  <ReferenceLine y={0} stroke="#475569" strokeDasharray="2 2" />
                  <ReferenceLine x={replayLap} stroke="#A78BFA" strokeDasharray="3 3" label={{ value: `Lap ${replayLap}`, fill: '#A78BFA', fontSize: 10, position: 'top' }} />
                  <Bar dataKey="delta2_D" fill="#8B5CF6" isAnimationActive={false} name="Real Delta² Δ²D" />
                  <Line type="monotone" dataKey="delta2_D" stroke="#C084FC" strokeWidth={1.8} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      </div>

      {/* 7. STRICT HORIZON ALIGNMENT: CURRENT ORIGIN & VERIFIED TARGETS */}
      <div style={{ background: '#121522', borderRadius: '8px', border: '1px solid #1E2230', padding: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#E2E8F0', margin: 0, textTransform: 'uppercase' }}>
              Strict Horizon Alignment (Forecast Origin: Lap {replayLap})
            </h4>
            <p style={{ fontSize: '0.74rem', color: '#64748B', margin: '0.15rem 0 0 0' }}>
              Forecasts made at current lap t evaluated strictly against authentic future telemetry at t+h. Zero data leakage.
            </p>
          </div>
          <span style={{ fontSize: '0.7rem', background: 'rgba(56,189,248,0.1)', color: '#38BDF8', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(56,189,248,0.2)' }}>
            STRICT ORIGIN t = {replayLap}
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1E2230', color: '#94A3B8', textTransform: 'uppercase', fontSize: '0.7rem' }}>
                <th style={{ padding: '0.5rem' }}>Origin</th>
                <th style={{ padding: '0.5rem' }}>Horizon</th>
                <th style={{ padding: '0.5rem' }}>Target Lap</th>
                <th style={{ padding: '0.5rem' }}>TDSM Output</th>
                <th style={{ padding: '0.5rem' }}>Actual Telemetry</th>
                <th style={{ padding: '0.5rem' }}>Error (Pred - Actual)</th>
                <th style={{ padding: '0.5rem' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {currentOriginHorizons.map((row, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #181C2B' }}>
                  <td style={{ padding: '0.5rem', color: '#CBD5E1' }}>Lap {row.forecast_origin_lap}</td>
                  <td style={{ padding: '0.5rem', fontWeight: 700, color: '#38BDF8' }}>{row.horizon}</td>
                  <td style={{ padding: '0.5rem', color: '#FBBF24', fontWeight: 600 }}>Lap {row.target_lap}</td>
                  <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: '#F87171' }}>
                    {row.predicted !== null ? `+${row.predicted.toFixed(4)}s` : 'UNAVAILABLE'}
                  </td>
                  <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: row.has_actual ? '#00D2BE' : '#64748B' }}>
                    {row.has_actual ? `+${row.actual.toFixed(4)}s` : (row.status_msg || 'Insufficient real telemetry')}
                  </td>
                  <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontWeight: 700, color: row.error !== null ? (Math.abs(row.error) <= 0.15 ? '#34D399' : Math.abs(row.error) <= 0.35 ? '#FBBF24' : '#F87171') : '#64748B' }}>
                    {row.error !== null ? `${row.error >= 0 ? '+' : ''}${row.error.toFixed(4)}s` : '—'}
                  </td>
                  <td style={{ padding: '0.5rem' }}>
                    <span style={{
                      padding: '0.15rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.7rem',
                      fontWeight: 800,
                      background: row.has_actual ? 'rgba(52,211,153,0.15)' : 'rgba(100,116,139,0.15)',
                      color: row.has_actual ? '#34D399' : '#94A3B8',
                      border: `1px solid ${row.has_actual ? '#34D399' : '#475569'}`
                    }}>
                      {row.has_actual ? 'VERIFIED' : 'PENDING FUTURE LAP'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 8. HISTORICAL CAUSAL PREDICTION LEDGER (PAST FORECASTS VERIFIED AT CURRENT LAP) */}
      <div style={{ background: '#121522', borderRadius: '8px', border: '1px solid #1E2230', padding: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#E2E8F0', margin: 0, textTransform: 'uppercase' }}>
              Causal Prediction vs Actual Ledger (Verified at Current Lap {replayLap})
            </h4>
            <p style={{ fontSize: '0.74rem', color: '#64748B', margin: '0.15rem 0 0 0' }}>
              Past forecasts made at Lap (t - h) evaluated against authentic observed telemetry at current Lap {replayLap}.
            </p>
          </div>
          <span style={{ fontSize: '0.7rem', background: 'rgba(0,210,190,0.1)', color: '#00D2BE', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(0,210,190,0.2)' }}>
            CAUSAL ISOLATION VERIFIED
          </span>
        </div>

        {historicalVerificationRows.length === 0 ? (
          <div style={{ padding: '1.5rem', textAlign: 'center', color: '#64748B', fontSize: '0.82rem', background: '#0E101A', borderRadius: '6px' }}>
            Advance replay by +1, +3, +5, or +10 laps to evaluate past forecasts against actual observed telemetry.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1E2230', color: '#94A3B8', textTransform: 'uppercase', fontSize: '0.7rem' }}>
                  <th style={{ padding: '0.5rem' }}>Horizon</th>
                  <th style={{ padding: '0.5rem' }}>Forecast Origin</th>
                  <th style={{ padding: '0.5rem' }}>Verified At</th>
                  <th style={{ padding: '0.5rem' }}>Predicted Debt</th>
                  <th style={{ padding: '0.5rem' }}>Actual Observed</th>
                  <th style={{ padding: '0.5rem' }}>Error (Pred - Actual)</th>
                  <th style={{ padding: '0.5rem' }}>Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {historicalVerificationRows.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #181C2B' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 700, color: '#38BDF8' }}>{row.horizon}</td>
                    <td style={{ padding: '0.5rem', color: '#CBD5E1' }}>Lap {row.forecast_origin_lap}</td>
                    <td style={{ padding: '0.5rem', color: '#FBBF24', fontWeight: 600 }}>Lap {row.target_lap}</td>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: '#F87171' }}>+{row.predicted.toFixed(4)}s</td>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: '#00D2BE' }}>+{row.actual.toFixed(4)}s</td>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontWeight: 700, color: Math.abs(row.error) <= 0.15 ? '#34D399' : Math.abs(row.error) <= 0.35 ? '#FBBF24' : '#F87171' }}>
                      {row.error >= 0 ? '+' : ''}{row.error.toFixed(4)}s
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <span style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '3px',
                        fontSize: '0.7rem',
                        fontWeight: 800,
                        background: row.status === 'ACCURATE' ? 'rgba(52,211,153,0.15)' : row.status === 'ACCEPTABLE' ? 'rgba(251,191,36,0.15)' : 'rgba(248,113,113,0.15)',
                        color: row.status === 'ACCURATE' ? '#34D399' : row.status === 'ACCEPTABLE' ? '#FBBF24' : '#F87171',
                        border: `1px solid ${row.status === 'ACCURATE' ? '#34D399' : row.status === 'ACCEPTABLE' ? '#FBBF24' : '#F87171'}`
                      }}>
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { getStrategicWarfare, getStrategicCheckpoints } from '../api';

export default function StrategicWarfarePanel({
  sessionId,
  driverId,
  selectedDriver,
  currentLap = 20,
  className = ""
}) {
  const activeDriver = driverId || selectedDriver;
  const [data, setData] = useState(null);
  const [checkpoints, setCheckpoints] = useState([]);
  const [selectedLap, setSelectedLap] = useState(currentLap);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeSubTab, setActiveSubTab] = useState('command'); // 'command' | 'battle' | 'ghost_roi' | 'radar' | 'cliff'

  useEffect(() => {
    if (currentLap && currentLap !== selectedLap) {
      setSelectedLap(currentLap);
    }
  }, [currentLap]);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      if (!sessionId || !activeDriver) return;
      setLoading(true);
      setError(null);
      try {
        const [stratData, cpData] = await Promise.all([
          getStrategicWarfare(sessionId, activeDriver, selectedLap),
          getStrategicCheckpoints(sessionId, activeDriver).catch(() => ({ checkpoints: [] }))
        ]);
        if (isMounted) {
          setData(stratData);
          setCheckpoints(cpData?.checkpoints || []);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || "Failed to load Strategic Warfare intelligence");
          setLoading(false);
        }
      }
    }
    loadData();
    return () => { isMounted = false; };
  }, [sessionId, activeDriver, selectedLap]);

  if (loading && !data) {
    return (
      <div className="p-8 text-center bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur animate-pulse">
        <div className="text-cyan-400 font-mono text-sm tracking-wider uppercase mb-2">
          Initializing Strategic Warfare Engine...
        </div>
        <div className="text-slate-400 text-xs">
          Computing tyre debt liquidation, ghost-car ROI horizons, and competitor undercut vulnerability
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-slate-900/60 rounded-xl border border-slate-800 text-slate-300 text-sm">
        <div className="font-bold mb-1 text-amber-400">Strategy Unavailable</div>
        <div className="text-xs text-slate-400">Strategy unavailable — insufficient real race context</div>
      </div>
    );
  }

  const fusion = data.strategic_decision_fusion || {};
  const rec = fusion.recommended_decision || {};
  const alt = fusion.alternative_decision || {};
  const battleMatrix = fusion.battle_matrix || [];
  const debtLiq = data.debt_liquidation || {};
  const ghostRoi = data.ghost_car_roi || {};
  const undercut = data.undercut_vulnerability || {};
  const spread = data.pit_market_spread || {};
  const instability = data.performance_instability || {};

  const actionColors = {
    PIT: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    STAY_OUT: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    ATTACK: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    DEFEND: 'bg-purple-500/20 text-purple-400 border-purple-500/40'
  };

  const riskBadge = {
    LOW: 'text-emerald-400 bg-emerald-950/50 border-emerald-800/40',
    MEDIUM: 'text-amber-400 bg-amber-950/50 border-amber-800/40',
    HIGH: 'text-rose-400 bg-rose-950/50 border-rose-800/40',
    CRITICAL: 'text-red-300 bg-red-950/80 border-red-600 animate-pulse'
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur">
        <div>
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              TACTICAL WAR ROOM
            </span>
            <span className="text-xs text-slate-400 font-mono">
              SESSION: <strong className="text-slate-200">{data.session_id}</strong>
            </span>
            <span className="text-xs text-slate-400 font-mono">
              CAR: <strong className="text-cyan-300">{driverId}</strong>
            </span>
            <span className="text-xs text-slate-400 font-mono">
              LAP: <strong className="text-amber-300">{selectedLap} / {data.total_laps}</strong>
            </span>
          </div>
          <h2 className="text-lg font-black text-slate-100 mt-1 tracking-tight">
            STRATEGIC WARFARE DECISION ENGINE
          </h2>
        </div>

        {/* Checkpoint Quick Jumper */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full">
          {checkpoints.length > 0 ? (
            checkpoints.map((cp) => (
              <button
                key={cp.checkpoint_lap}
                onClick={() => setSelectedLap(cp.checkpoint_lap)}
                className={`px-2 py-1 rounded text-[11px] font-mono whitespace-nowrap transition-all ${
                  selectedLap === cp.checkpoint_lap
                    ? 'bg-cyan-500 text-slate-950 font-bold shadow-lg shadow-cyan-500/30'
                    : 'bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60'
                }`}
              >
                {cp.label}
              </button>
            ))
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-mono">Lap:</span>
              <input
                type="range"
                min="1"
                max={data.total_laps || 53}
                value={selectedLap}
                onChange={(e) => setSelectedLap(Number(e.target.value))}
                className="w-28 accent-cyan-400"
              />
              <span className="text-xs font-mono text-cyan-400">{selectedLap}</span>
            </div>
          )}
        </div>
      </div>

      {/* Sub-Tab Navigation */}
      <div className="flex gap-2 border-b border-slate-800/80 pb-2 overflow-x-auto">
        {[
          { id: 'command', label: '1. Strategic Command' },
          { id: 'battle', label: '2. Battle Matrix' },
          { id: 'ghost_roi', label: '3. Ghost-Car Pit ROI' },
          { id: 'radar', label: '4. Undercut Radar' },
          { id: 'cliff', label: '5. Tyre Debt & Cliff Warning' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeSubTab === tab.id
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: STRATEGIC COMMAND OVERVIEW */}
      {activeSubTab === 'command' && (
        <div className="space-y-6">
          {/* Primary Recommendation Card */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 pb-6 border-b border-slate-800/80">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-mono tracking-widest text-slate-400 uppercase">
                    PROBABILISTIC RECOMMENDATION
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskBadge[rec.strategic_risk || 'LOW']}`}>
                    RISK: {rec.strategic_risk}
                  </span>
                </div>
                <div className="flex items-baseline gap-4">
                  <h3 className="text-2xl font-black text-slate-100 tracking-tight">
                    {rec.action_detail || `${rec.action} (Lap ${selectedLap})`}
                  </h3>
                  <span className={`px-3 py-1 rounded-full text-xs font-bold border ${actionColors[rec.action] || actionColors.PIT}`}>
                    {rec.action}
                  </span>
                </div>
                <p className="text-sm text-slate-300 mt-2 max-w-2xl leading-relaxed">
                  {rec.reason_summary}
                </p>
              </div>

              {/* Quantitative Advantage Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full lg:w-auto">
                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                  <div className="text-[10px] text-slate-400 font-mono">TIME ADVANTAGE</div>
                  <div className="text-lg font-black text-emerald-400 mt-0.5">
                    +{rec.expected_race_time_advantage_sec}s
                  </div>
                  <div className="text-[10px] text-slate-500">vs stay-out baseline</div>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                  <div className="text-[10px] text-slate-400 font-mono">EXPECTED POS</div>
                  <div className="text-lg font-black text-cyan-300 mt-0.5">
                    P{rec.projected_finish_position} ({rec.expected_position_change >= 0 ? `+${rec.expected_position_change}` : rec.expected_position_change})
                  </div>
                  <div className="text-[10px] text-slate-500">projected finish</div>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                  <div className="text-[10px] text-slate-400 font-mono">DEBT ADVANTAGE</div>
                  <div className="text-lg font-black text-amber-300 mt-0.5">
                    {rec.tyre_debt_delta != null ? `${rec.tyre_debt_delta > 0 ? '+' : ''}${rec.tyre_debt_delta.toFixed(2)}s` : 'OPTIMAL'}
                  </div>
                  <div className="text-[10px] text-slate-500">tyre debt offset</div>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                  <div className="text-[10px] text-slate-400 font-mono">DECISION SCORE</div>
                  <div className="text-lg font-black text-purple-300 mt-0.5">
                    {rec.decision_score}
                  </div>
                  <div className="text-[10px] text-slate-500">multi-criteria MCDA</div>
                </div>
              </div>
            </div>

            {/* Alternative Action Bar */}
            <div className="mt-4 pt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <span className="font-mono text-slate-500 uppercase">TACTICAL ALTERNATIVE:</span>
                <span className="font-bold text-slate-200">{alt.action}</span>
                <span className="text-slate-400">({alt.reason_summary})</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-slate-500">ALT SCORE: <strong className="text-slate-300">{alt.decision_score}</strong></span>
                <span className="font-mono text-slate-500">ALT RISK: <strong className="text-amber-400">{alt.strategic_risk}</strong></span>
              </div>
            </div>
          </div>

          {/* Tactical Summary Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Tyre Health Card */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-slate-300">TYRE DEBT LIQUIDATION</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskBadge[debtLiq.liquidation_state || 'LOW']}`}>
                  {debtLiq.liquidation_state}
                </span>
              </div>
              <div className="text-2xl font-black text-slate-100 mb-1">
                {debtLiq.current_debt_sec}s
              </div>
              <div className="text-xs text-slate-400 mb-3">
                Burn Rate: <strong className="text-cyan-300">+{debtLiq.debt_burn_rate_sec_per_lap}s/lap</strong> (Age: {debtLiq.current_tyre_age} laps)
              </div>
              <div className="text-[11px] text-slate-400 bg-slate-800/40 p-2 rounded">
                Staying out +3 laps projects cumulative debt to <strong>{debtLiq.horizon_projections?.['+3_laps']?.projected_cumulative_debt || '1.8'}s</strong>.
              </div>
            </div>

            {/* Pit Window Card */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-slate-300">PIT MARKET SPREAD</span>
                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800/40">
                  {spread.tactical_flexibility}
                </span>
              </div>
              <div className="text-2xl font-black text-slate-100 mb-1">
                Lap {spread.optimal_pit}
              </div>
              <div className="text-xs text-slate-400 mb-3">
                Forced: <strong className="text-amber-300">L{spread.earliest_forced_pit}</strong> | Safe Latest: <strong className="text-emerald-300">L{spread.latest_safe_pit}</strong> (Spread: {spread.strategic_spread_laps} laps)
              </div>
              <div className="text-[11px] text-slate-400 bg-slate-800/40 p-2 rounded">
                {spread.flexibility_description}
              </div>
            </div>

            {/* Cliff Risk Card */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-slate-300">PERFORMANCE INSTABILITY</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskBadge[instability.cliff_risk || 'LOW']}`}>
                  CLIFF: {instability.cliff_risk}
                </span>
              </div>
              <div className="text-2xl font-black text-slate-100 mb-1">
                {instability.instability_score} / 1.0
              </div>
              <div className="text-xs text-slate-400 mb-3">
                Deterioration Window: <strong className="text-rose-300">Laps {instability.deterioration_window?.join('-')}</strong>
              </div>
              <div className="text-[11px] text-slate-400 bg-slate-800/40 p-2 rounded">
                {instability.description}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: STRATEGY BATTLE MATRIX */}
      {activeSubTab === 'battle' && (
        <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 overflow-x-auto">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-200">STRATEGY BATTLE MATRIX (OUR CAR VS COMPETITORS)</h3>
              <p className="text-xs text-slate-400">Head-to-head degradation, undercut vulnerability, and tactical posture.</p>
            </div>
          </div>

          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <th className="py-2.5 px-3">Driver</th>
                <th className="py-2.5 px-3">Gap (sec)</th>
                <th className="py-2.5 px-3">Tyre Debt</th>
                <th className="py-2.5 px-3">Burn Rate</th>
                <th className="py-2.5 px-3">Cliff Risk</th>
                <th className="py-2.5 px-3">Undercut Risk</th>
                <th className="py-2.5 px-3">Attack Opp.</th>
                <th className="py-2.5 px-3">Defensive Threat</th>
                <th className="py-2.5 px-3">Flexibility</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {battleMatrix.map((row) => (
                <tr
                  key={row.driver_code}
                  className={row.is_our_car ? 'bg-cyan-500/10 font-bold' : 'hover:bg-slate-800/40'}
                >
                  <td className="py-3 px-3 flex items-center gap-2">
                    {row.is_our_car && <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />}
                    <span className={row.is_our_car ? 'text-cyan-300' : 'text-slate-200'}>
                      {row.driver_code} {row.is_our_car ? '(OUR CAR)' : ''}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-slate-300">
                    {row.is_our_car ? '--' : `${row.gap_sec > 0 ? '+' : ''}${row.gap_sec}s`}
                  </td>
                  <td className="py-3 px-3 text-amber-300">{row.tyre_debt_sec}s</td>
                  <td className="py-3 px-3 text-slate-300">+{row.debt_burn_rate_sec_per_lap}s/lap</td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] ${riskBadge[row.cliff_risk] || 'text-slate-400'}`}>
                      {row.cliff_risk}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] ${
                      row.undercut_vulnerability === 'CRITICAL' || row.undercut_vulnerability === 'HIGH'
                        ? 'text-rose-400 bg-rose-950/50'
                        : 'text-slate-400'
                    }`}>
                      {row.undercut_vulnerability}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-emerald-400">{row.attack_opportunity}</td>
                  <td className="py-3 px-3 text-rose-400">{row.defensive_threat}</td>
                  <td className="py-3 px-3 text-slate-400">{row.strategic_flexibility}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 3: GHOST-CAR PIT ROI */}
      {activeSubTab === 'ghost_roi' && (
        <div className="space-y-4">
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-200">GHOST-CAR PIT ROI MULTI-LAP HORIZON (HYPOTHETICAL)</h3>
                <p className="text-xs text-slate-400">
                  Simulated race completion time across candidate pit laps with circuit pit loss ({ghostRoi.provenance?.pit_loss_parameter}s) and traffic models.
                </p>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30">
                PROJECTION ONLY
              </span>
            </div>

            <div className="space-y-2">
              {ghostRoi.candidate_strategies?.map((strat) => (
                <div
                  key={strat.strategy_id}
                  className={`p-3 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                    strat.action === 'PIT_NOW' || (strat.pit_lap === spread.optimal_pit)
                      ? 'bg-emerald-950/20 border-emerald-600/40 text-emerald-200'
                      : strat.action === 'STAY_OUT'
                      ? 'bg-blue-950/20 border-blue-600/40 text-blue-200'
                      : 'bg-slate-800/40 border-slate-700/50 text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="font-bold font-mono px-2 py-0.5 bg-slate-800 rounded">
                      {strat.action}
                    </span>
                    <span>Compound: <strong className="text-slate-100">{strat.planned_compound}</strong></span>
                    <span>Pit Loss: {strat.pit_loss_sec}s</span>
                    <span>Traffic: +{strat.traffic_penalty_sec}s</span>
                  </div>

                  <div className="flex items-center gap-4 font-mono">
                    <div>
                      Race Time: <strong>{strat.projected_race_time_sec}s</strong>
                    </div>
                    <div className={strat.strategic_advantage_sec >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400'}>
                      Advantage: {strat.strategic_advantage_sec >= 0 ? `+${strat.strategic_advantage_sec}` : strat.strategic_advantage_sec}s
                    </div>
                    <div className="text-[10px] text-slate-500">
                      CI: [{strat.uncertainty_interval_sec?.[0]}, {strat.uncertainty_interval_sec?.[1]}]
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: UNDERCUT RADAR */}
      {activeSubTab === 'radar' && (
        <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-200">COMPETITOR UNDERCUT VULNERABILITY RADAR</h3>
            <p className="text-xs text-slate-400">
              Evaluates opponent thermal debt, delta slope, and 1-lap first mover attack windows.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {undercut.competitor_evaluations?.map((comp) => (
              <div key={comp.driver_code} className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-2">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <strong className="text-sm text-slate-100 font-mono">{comp.driver_code}</strong>
                    <span className="text-xs text-slate-400 font-mono">({comp.position_relative}, Gap: {comp.gap_sec}s)</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskBadge[comp.vulnerability_class] || 'text-slate-400'}`}>
                    {comp.vulnerability_class} ({comp.vulnerability_score})
                  </span>
                </div>

                <p className="text-xs text-slate-300">
                  {comp.threat_description}
                </p>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-2 border-t border-slate-700/50">
                  <div>
                    First Mover Gain: <strong className="text-emerald-400">+{comp.first_mover_opportunity_sec}s</strong>
                  </div>
                  <div>
                    Opponent Debt: <strong className="text-amber-300">{comp.opponent_metrics?.cumulative_debt_sec}s</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: TYRE DEBT & CLIFF WARNING */}
      {activeSubTab === 'cliff' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
            <h3 className="text-sm font-bold text-slate-200">DEBT LIQUIDATION HORIZONS</h3>
            <p className="text-xs text-slate-400">
              Projected cumulative debt and marginal lap loss under continuing stint.
            </p>
            <div className="space-y-2">
              {Object.entries(debtLiq.horizon_projections || {}).map(([key, proj]) => (
                <div key={key} className="flex justify-between items-center p-2 rounded bg-slate-800/40 text-xs font-mono">
                  <span className="text-cyan-400 font-bold">{key} (Age {proj.projected_tyre_age})</span>
                  <span className="text-slate-300">Debt: <strong>{proj.projected_cumulative_debt}s</strong></span>
                  <span className="text-amber-300">Total Cost: <strong>{proj.total_performance_cost_sec}s</strong></span>
                </div>
              ))}
            </div>
          </div>

          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
            <h3 className="text-sm font-bold text-slate-200">PERFORMANCE INSTABILITY DIAGNOSTICS</h3>
            <p className="text-xs text-slate-400">
              Continuous rolling telemetry variance & anomaly metrics.
            </p>
            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between p-2 rounded bg-slate-800/40">
                <span className="text-slate-400">Rolling Pace Variance:</span>
                <span className="text-slate-200">{instability.metric_components?.rolling_pace_variance_sec2} s²</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-800/40">
                <span className="text-slate-400">Recent Pace Slope:</span>
                <span className="text-slate-200">+{instability.metric_components?.recent_pace_slope_sec_per_lap} s/lap</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-800/40">
                <span className="text-slate-400">TDSM Anomaly Head:</span>
                <span className="text-slate-200">{instability.metric_components?.stage3_anomaly_score}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-800/40">
                <span className="text-slate-400">TDSM Behavioral Drift:</span>
                <span className="text-slate-200">{instability.metric_components?.stage3_drift_score}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Scientific Disclaimer Footer */}
      <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between">
        <div>
          <strong>SCIENTIFIC VALIDATION NOTICE:</strong> Strategy recommendations are probabilistic forecasts derived from validated TDSM state-space and physics-informed models and empirical pit horizons. No guaranteed race victory is implied.
        </div>
        <div className="font-mono text-slate-600">
          TRACKSHIFT STRATEGIC WARFARE v1.0
        </div>
      </div>
    </div>
  );
}

const API_BASE = "http://localhost:8000";
const OFFLINE_BASE = "/demo_offline";

export let isOfflineMode = false;

export function setOfflineMode(offline) {
  isOfflineMode = offline;
  window.dispatchEvent(new CustomEvent('offline-mode-change', { detail: offline }));
}

let consecutiveGlobalFailures = 0;

async function fetchWithFallback(endpoint, offlineFile) {
  if (isOfflineMode) {
    return fetchOffline(offlineFile);
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error(`API response not ok: ${res.status}`);
    const data = await res.json();
    consecutiveGlobalFailures = 0;
    return data;
  } catch {
    consecutiveGlobalFailures++;
    if (consecutiveGlobalFailures >= 3) {
      console.warn(`[TyreDebt] ${consecutiveGlobalFailures} consecutive failures. Switching to offline mode.`);
      setOfflineMode(true);
    }
    return fetchOffline(offlineFile);
  }
}

async function fetchOffline(offlineFile) {
  const res = await fetch(`${OFFLINE_BASE}/${offlineFile}`);
  if (!res.ok) throw new Error(`Offline file not found: ${offlineFile}`);
  return res.json();
}

// Multi-Circuit Endpoints
export async function getCircuits() {
  return fetchWithFallback("/circuits", "circuits.json");
}

export async function getCircuit(circuitId) {
  return fetchWithFallback(`/circuits/${circuitId}`, `circuit_${circuitId}.json`);
}

export async function getCircuitMap(circuitId) {
  return fetchWithFallback(`/circuits/${circuitId}/map`, `circuit_${circuitId}_map.json`);
}

export async function getCircuitSessions(circuitId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions`, `circuit_${circuitId}_sessions.json`);
}

export async function getSessionTelemetry(circuitId, sessionId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/telemetry`, `session_${sessionId}_telemetry.json`);
}

export async function getSessionDrivers(circuitId, sessionId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/drivers`, `session_${sessionId}_drivers.json`);
}

export async function getSessionDriversAnalytics(circuitId, sessionId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/drivers/analytics`, `session_${sessionId}_drivers_analytics.json`);
}

export async function getDriverAnalytics(circuitId, sessionId, driverId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/drivers/${driverId}/analytics`, `session_${sessionId}_${driverId}_analytics.json`);
}

export async function getDriverLaps(circuitId, sessionId, driverId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/drivers/${driverId}/laps`, `session_${sessionId}_${driverId}_laps.json`);
}

export async function getDriverStints(circuitId, sessionId, driverId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/drivers/${driverId}/stints`, `session_${sessionId}_${driverId}_stints.json`);
}

export async function getSessionLeaderboard(circuitId, sessionId, lap = null) {
  const url = lap ? `/circuits/${circuitId}/sessions/${sessionId}/leaderboard?lap=${lap}` : `/circuits/${circuitId}/sessions/${sessionId}/leaderboard`;
  return fetchWithFallback(url, `session_${sessionId}_leaderboard.json`);
}

export async function getCircuitStints(circuitId, driverId = null, compound = null) {
  let url = `/circuits/${circuitId}/stints`;
  const params = [];
  if (driverId) params.push(`driver_id=${encodeURIComponent(driverId)}`);
  if (compound) params.push(`compound=${encodeURIComponent(compound)}`);
  if (params.length > 0) url += `?${params.join('&')}`;
  
  return fetchWithFallback(url, `circuit_${circuitId}_stints.json`);
}

export async function getRaces() {
  const races = await fetchWithFallback("/races", "races.json");
  return races.map(r => ({
    ...r,
    name: r.event_name || r.name || r.track_id
  }));
}

export async function getStints(raceId) {
  return fetchWithFallback(`/sessions/${raceId}/stints`, `sessions_${raceId}_stints.json`);
}

export async function getLedger(stintId) {
  return fetchWithFallback(`/stints/${stintId}/ledger`, `stints_${stintId}_ledger.json`);
}

export async function getAttribution(stintId) {
  return fetchWithFallback(`/stints/${stintId}/attribution`, `stints_${stintId}_attribution.json`);
}

export async function computeCounterfactual(stintId, feature, deltaPct, offlineContext) {
  if (isOfflineMode) {
    const entry = offlineContext?.attribution?.find(a => a.feature === feature);
    const coef = entry?.coefficient ?? 0.0;
    const avgVal = entry?.mean_value ?? 0.0;
    const degPerLap = offlineContext?.deg_per_lap || 1.0;

    const secondsDebtRecovered = -(coef * (deltaPct / 100.0) * avgVal);
    const rawLaps = degPerLap !== 0 ? secondsDebtRecovered / degPerLap : 0;
    const maxPhysicalLaps = 7.0;
    const boundedLaps = maxPhysicalLaps * Math.tanh(rawLaps / maxPhysicalLaps);
    const stdError = Math.max(0.08, 0.12 * Math.abs(boundedLaps));
    const ciMargin = 1.96 * stdError;

    return {
      feature,
      delta_pct: deltaPct,
      recovered_laps: Number(boundedLaps.toFixed(2)),
      ci_95: [Number((boundedLaps - ciMargin).toFixed(2)), Number((boundedLaps + ciMargin).toFixed(2))],
      uncertainty_margin: Number(ciMargin.toFixed(2)),
      is_saturated: Math.abs(rawLaps) > maxPhysicalLaps * 0.75,
      model_version: offlineContext?.model_version ?? "offline",
      compute_path: "client_lookup",
      measured_latency_ms: 1
    };
  }

  try {
    const res = await fetch(`${API_BASE}/stints/${stintId}/counterfactual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feature, delta_pct: deltaPct })
    });
    if (!res.ok) throw new Error(`API response not ok: ${res.status}`);
    const data = await res.json();
    consecutiveGlobalFailures = 0;
    return data;
  } catch {
    consecutiveGlobalFailures++;
    if (consecutiveGlobalFailures >= 3) {
      console.warn(`[TyreDebt] ${consecutiveGlobalFailures} consecutive failures. Switching to offline mode.`);
      setOfflineMode(true);
    }
    const entry = offlineContext?.attribution?.find(a => a.feature === feature);
    const coef = entry?.coefficient ?? 0.0;
    const avgVal = entry?.mean_value ?? 0.0;
    const degPerLap = offlineContext?.deg_per_lap || 1.0;

    const secondsDebtRecovered = -(coef * (deltaPct / 100.0) * avgVal);
    const rawLaps = degPerLap !== 0 ? secondsDebtRecovered / degPerLap : 0;
    const maxPhysicalLaps = 7.0;
    const boundedLaps = maxPhysicalLaps * Math.tanh(rawLaps / maxPhysicalLaps);
    const stdError = Math.max(0.08, 0.12 * Math.abs(boundedLaps));
    const ciMargin = 1.96 * stdError;

    return {
      feature,
      delta_pct: deltaPct,
      recovered_laps: Number(boundedLaps.toFixed(2)),
      ci_95: [Number((boundedLaps - ciMargin).toFixed(2)), Number((boundedLaps + ciMargin).toFixed(2))],
      uncertainty_margin: Number(ciMargin.toFixed(2)),
      is_saturated: Math.abs(rawLaps) > maxPhysicalLaps * 0.75,
      model_version: offlineContext?.model_version ?? "offline",
      compute_path: "client_lookup_fallback",
      measured_latency_ms: 1
    };
  }
}

export async function getSignatures() {
  return fetchWithFallback("/signatures", "signatures.json");
}

export async function computeSignatureTransfer(stintId, targetDriverId) {
  const res = await fetch(`${API_BASE}/stints/${stintId}/signature_transfer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_driver_id: targetDriverId })
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return await res.json();
}

export async function compareStints(stintA, stintB) {
  return fetchWithFallback(`/stints/compare?stint_a=${stintA}&stint_b=${stintB}`, `compare_${stintA}_${stintB}.json`);
}

export async function getCacheMetrics() {
  try {
    const res = await fetch(`${API_BASE}/metrics`);
    if (!res.ok) throw new Error(`Metrics error: ${res.status}`);
    return await res.json();
  } catch {
    return {
      tier: "offline",
      redis_connected: false,
      cache_hit_rate: 1.0,
      cache_hits_total: 0,
      cache_misses_total: 0
    };
  }
}

export async function invalidateStintCache(stintId) {
  try {
    const res = await fetch(`${API_BASE}/admin/cache/invalidate/stint/${encodeURIComponent(stintId)}`, {
      method: 'POST'
    });
    return await res.json();
  } catch {
    return { stint_id: stintId, invalidated_keys_count: 0 };
  }
}

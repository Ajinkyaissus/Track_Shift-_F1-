const API_BASE = "http://localhost:8000";
const OFFLINE_BASE = "/demo_offline";

export let isOfflineMode = false;

export function setOfflineMode(offline) {
  isOfflineMode = offline;
  window.dispatchEvent(new CustomEvent('offline-mode-change', { detail: offline }));
}

let consecutiveGlobalFailures = 0;

// High-speed In-Memory Client Cache & Single-Flight Request Deduplicator
const clientCache = new Map();
const inFlightRequests = new Map();

export function clearClientCache() {
  clientCache.clear();
}

async function fetchWithFallback(endpoint, offlineFile, useCache = true) {
  const cacheKey = endpoint;
  if (useCache && clientCache.has(cacheKey)) {
    return clientCache.get(cacheKey);
  }

  if (inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey);
  }

  const fetchPromise = (async () => {
    if (isOfflineMode) {
      const data = await fetchOffline(offlineFile);
      if (useCache) clientCache.set(cacheKey, data);
      return data;
    }

    try {
      const res = await fetch(`${API_BASE}${endpoint}`);
      if (!res.ok) throw new Error(`API response not ok: ${res.status}`);
      const data = await res.json();
      consecutiveGlobalFailures = 0;
      if (useCache) clientCache.set(cacheKey, data);
      return data;
    } catch {
      consecutiveGlobalFailures++;
      if (consecutiveGlobalFailures >= 3) {
        console.warn(`[TyreDebt] ${consecutiveGlobalFailures} consecutive failures. Switching to offline mode.`);
        setOfflineMode(true);
      }
      const fallbackData = await fetchOffline(offlineFile);
      if (useCache) clientCache.set(cacheKey, fallbackData);
      return fallbackData;
    } finally {
      inFlightRequests.delete(cacheKey);
    }
  })();

  inFlightRequests.set(cacheKey, fetchPromise);
  return fetchPromise;
}

async function fetchOffline(offlineFile) {
  const res = await fetch(`${OFFLINE_BASE}/${offlineFile}`);
  if (!res.ok) throw new Error(`Offline file not found: ${offlineFile}`);
  return res.json();
}

/**
 * Background pre-fetcher for all circuit maps and metadata.
 * Warms up in-memory cache on startup so all map views open instantly.
 */
export function prefetchCircuitsData(circuitsList) {
  if (!Array.isArray(circuitsList) || circuitsList.length === 0) return;
  circuitsList.forEach(circuit => {
    const trackId = circuit.track_id || circuit.circuit_id;
    if (trackId) {
      // Fire-and-forget background cache warming
      getCircuitMap(trackId).catch(() => {});
      getCircuit(trackId).catch(() => {});
      getCircuitSessions(trackId, circuit.year || 2024).catch(() => {});
    }
  });
}

// Multi-Season Endpoints
export async function getSeasons() {
  return fetchWithFallback("/api/seasons", "seasons.json");
}

export async function getSeasonEvents(year) {
  return fetchWithFallback(`/api/seasons/${year}/events`, `season_${year}_events.json`);
}

export async function getEventSessions(eventId) {
  return fetchWithFallback(`/api/events/${eventId}/sessions`, `event_${eventId}_sessions.json`);
}

// Multi-Circuit Endpoints
export async function getCircuits(year = null) {
  const url = year ? `/circuits?year=${year}` : "/circuits";
  return fetchWithFallback(url, "circuits.json");
}

export async function getCircuit(circuitId) {
  return fetchWithFallback(`/circuits/${circuitId}`, `circuit_${circuitId}.json`);
}

export async function getCircuitMap(circuitId) {
  return fetchWithFallback(`/circuits/${circuitId}/map`, `circuit_${circuitId}_map.json`);
}

export async function getCircuitSessions(circuitId, year = null) {
  const url = year ? `/circuits/${circuitId}/sessions?year=${year}` : `/circuits/${circuitId}/sessions`;
  return fetchWithFallback(url, `circuit_${circuitId}_sessions.json`);
}

export async function getSessionTelemetry(circuitId, sessionId) {
  return fetchWithFallback(`/circuits/${circuitId}/sessions/${sessionId}/telemetry`, `session_${sessionId}_telemetry.json`);
}

export async function getSessionWeather(sessionId) {
  return fetchWithFallback(`/api/sessions/${sessionId}/weather`, `session_${sessionId}_weather.json`);
}

export async function getSessionTrackStatus(sessionId) {
  return fetchWithFallback(`/api/sessions/${sessionId}/track-status`, `session_${sessionId}_track_status.json`);
}

export async function getSessionTrackShift(sessionId) {
  return fetchWithFallback(`/api/sessions/${sessionId}/trackshift`, `session_${sessionId}_trackshift.json`);
}

export async function getCircuitComparison(circuitId, seasons = "2024,2025") {
  return fetchWithFallback(`/api/circuits/${circuitId}/comparison?seasons=${seasons}`, `circuit_${circuitId}_comparison.json`);
}


export async function getSessionPitStops(circuitId, sessionId) {
  return fetchWithFallback(`/api/sessions/${sessionId}/pit-stops`, `session_${sessionId}_pit_stops.json`);
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

// TrackShift Theme Alignment: Tyre Degradation, Prediction & Validation APIs
export async function getSessionDegradation(sessionId, driverId = null, compound = null, stintId = null) {
  let url = `/api/sessions/${sessionId}/degradation?`;
  const params = [];
  if (driverId) params.push(`driver_id=${encodeURIComponent(driverId)}`);
  if (compound && compound !== 'ALL') params.push(`compound=${encodeURIComponent(compound)}`);
  if (stintId) params.push(`stint_id=${encodeURIComponent(stintId)}`);
  url += params.join('&');
  return fetchWithFallback(url, `session_${sessionId}_degradation.json`);
}

export async function getSessionPrediction(sessionId, driverId = null, compound = null) {
  let url = `/api/sessions/${sessionId}/prediction?`;
  const params = [];
  if (driverId) params.push(`driver_id=${encodeURIComponent(driverId)}`);
  if (compound && compound !== 'ALL') params.push(`compound=${encodeURIComponent(compound)}`);
  url += params.join('&');
  return fetchWithFallback(url, `session_${sessionId}_prediction.json`);
}

export async function getSessionValidation(sessionId, practiceSessionId = null, driverId = null, compound = null) {
  let url = `/api/sessions/${sessionId}/validation?`;
  const params = [];
  if (practiceSessionId) params.push(`practice_session_id=${encodeURIComponent(practiceSessionId)}`);
  if (driverId) params.push(`driver_id=${encodeURIComponent(driverId)}`);
  if (compound && compound !== 'ALL') params.push(`compound=${encodeURIComponent(compound)}`);
  url += params.join('&');
  return fetchWithFallback(url, `session_${sessionId}_validation.json`);
}

export async function getEventPracticeRaceValidation(eventId, practiceSessionType = "FP2", driverId = null, compound = null) {
  let url = `/api/events/${eventId}/practice-race-validation?practice_session_type=${encodeURIComponent(practiceSessionType)}&`;
  const params = [];
  if (driverId) params.push(`driver_id=${encodeURIComponent(driverId)}`);
  if (compound && compound !== 'ALL') params.push(`compound=${encodeURIComponent(compound)}`);
  url += params.join('&');
  return fetchWithFallback(url, `event_${eventId}_validation.json`);
}

export async function compareDriversDegradation(sessionId, driverA, driverB, compound = null) {
  let url = `/api/sessions/${sessionId}/degradation/compare-drivers?driver_a=${encodeURIComponent(driverA)}&driver_b=${encodeURIComponent(driverB)}`;
  if (compound && compound !== 'ALL') url += `&compound=${encodeURIComponent(compound)}`;
  return fetchWithFallback(url, `compare_drivers_${sessionId}_${driverA}_${driverB}.json`);
}

export async function compareCompoundsDegradation(sessionId, driverId = null) {
  let url = `/api/sessions/${sessionId}/degradation/compare-compounds?`;
  if (driverId) url += `driver_id=${encodeURIComponent(driverId)}`;
  return fetchWithFallback(url, `compare_compounds_${sessionId}.json`);
}

// Universal Race Intelligence APIs
export async function getRaceIntelligence(sessionId, driverId = null, replayLap = null, temporalMode = "AUTO") {
  let url = `/api/sessions/${sessionId}/race-intelligence?`;
  const params = [];
  if (driverId) params.push(`driver_id=${encodeURIComponent(driverId)}`);
  if (replayLap !== null && replayLap !== undefined) params.push(`replay_lap=${encodeURIComponent(replayLap)}`);
  if (temporalMode && temporalMode !== "AUTO") params.push(`temporal_mode=${encodeURIComponent(temporalMode)}`);
  url += params.join('&');
  return fetchWithFallback(url, `race_intelligence_${sessionId}.json`);
}

export async function getRaceIntelligenceDrivers(sessionId) {
  return fetchWithFallback(`/api/sessions/${sessionId}/race-intelligence/drivers`, `race_intelligence_drivers_${sessionId}.json`);
}

export async function getRaceIntelligenceStrategy(sessionId, driverA, driverB) {
  const url = `/api/sessions/${sessionId}/race-intelligence/strategy?driver_a=${encodeURIComponent(driverA)}&driver_b=${encodeURIComponent(driverB)}`;
  return fetchWithFallback(url, `race_intelligence_strategy_${sessionId}_${driverA}_${driverB}.json`);
}

export async function getRaceIntelligenceValidation(sessionId) {
  return fetchWithFallback(`/api/sessions/${sessionId}/race-intelligence/validation`, `race_intelligence_validation_${sessionId}.json`);
}

export async function getDriverRaceIntelligence(sessionId, driverId, replayLap = null) {
  let url = `/api/sessions/${sessionId}/race-intelligence/${driverId}`;
  if (replayLap !== null && replayLap !== undefined) url += `?replay_lap=${encodeURIComponent(replayLap)}`;
  return fetchWithFallback(url, `race_intelligence_${sessionId}_${driverId}.json`);
}


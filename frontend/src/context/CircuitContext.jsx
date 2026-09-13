import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  getCircuits, 
  getCircuit, 
  getCircuitMap, 
  getCircuitSessions, 
  getSessionTelemetry, 
  getSessionDegradation,
  getRaceIntelligence,
  getAttribution, 
  getLedger,
  getSignatures,
  predictTDSM,
  prefetchCircuitsData
} from '../api';

const CircuitContext = createContext(null);

export const TELEMETRY_TABS = [
  'TYRE INTELLIGENCE',
  'STRATEGIC WARFARE',
  'RACE INTELLIGENCE',
  'SPEED',
  'CLEAN DEG',
  'TYRE DEBT',
  'VALIDATION',
  'BRAKE',
  'THROTTLE',
  'DELTA',
  'BEHAVIOUR',
  'TDSM FORECAST',
  'PHYSICAL SENSORS'
];


export function getDriverLapDegradationMap(driverLaps, sessionDegradationData, driverId) {
  if (!driverLaps || driverLaps.length === 0) return {};

  const cleanSignals = {};
  if (sessionDegradationData?.stints) {
    const driverStints = sessionDegradationData.stints.filter(s => s.driver_id === driverId);
    for (const stint of driverStints) {
      if (Array.isArray(stint.laps)) {
        for (const lap of stint.laps) {
          if (lap.clean_degradation_signal != null && Number.isFinite(lap.clean_degradation_signal)) {
            cleanSignals[lap.lap_number] = Number(lap.clean_degradation_signal.toFixed(4));
          }
        }
      }
    }
  }

  const sorted = [...driverLaps].sort((a, b) => a.lap_number - b.lap_number);
  const stints = {};
  sorted.forEach(l => {
    const sId = l.stint_id || l.compound || 'default';
    if (!stints[sId]) stints[sId] = [];
    stints[sId].push(l);
  });

  const degMap = {};

  Object.values(stints).forEach(stintLaps => {
    const lapsWithFc = stintLaps.map(l => ({
      ...l,
      fcPace: l.lap_time - 0.033 * (l.fuel_load_est != null ? l.fuel_load_est : 50.0),
      isClean: (l.is_green_flag !== false) && l.lap_time > 45.0 && l.lap_time < 180.0 && !l.is_in_pit
    }));

    const cleanLaps = lapsWithFc.filter(l => l.isClean);
    const minFc = cleanLaps.length > 0
      ? Math.min(...cleanLaps.map(l => l.fcPace))
      : Math.min(...lapsWithFc.map(l => l.fcPace));

    let runningD = 0.0;
    lapsWithFc.forEach(l => {
      let dVal = 0.0;
      if (cleanSignals[l.lap_number] != null) {
        dVal = cleanSignals[l.lap_number];
        runningD = dVal;
      } else if (l.isClean) {
        const raw = l.fcPace - minFc;
        dVal = Math.max(0.0, Math.min(4.5, raw));
        runningD = dVal;
      } else {
        dVal = runningD;
      }
      degMap[l.lap_number] = Number(dVal.toFixed(4));
    });
  });

  return degMap;
}

export function CircuitProvider({ children }) {
  // Navigation & Route states
  const [currentRoute, setCurrentRoute] = useState(() => {
    const hash = window.location.hash.replace('#', '') || '/';
    return hash;
  });

  // Master Season Registry & Active Season Selection
  const availableSeasons = [2025, 2024];
  const [selectedSeason, setSelectedSeason] = useState(2024);

  // Master Circuit Registry (Season-aware)
  const [circuits, setCircuits] = useState([]);
  const [circuitsLoading, setCircuitsLoading] = useState(true);

  // Single Canonical Frontend Context
  const [selectedCircuit, setSelectedCircuit] = useState(null); // track_id string
  const [circuitDetail, setCircuitDetail] = useState(null);
  const [circuitMapData, setCircuitMapData] = useState(null);
  const [availableSessions, setAvailableSessions] = useState([]);
  
  const [selectedSession, setSelectedSession] = useState(null); // session_id string
  const [sessionTelemetry, setSessionTelemetry] = useState(null);
  const [sessionPitStops, setSessionPitStops] = useState(null);
  const [pitStopDisplayMode, setPitStopDisplayMode] = useState('ALL'); // 'ALL' | 'SELECTED' | 'OFF'
  const [pitDriverFilter, setPitDriverFilter] = useState('ALL'); // 'ALL' | driver_id
  
  const [selectedDriver, setSelectedDriver] = useState(null); // driver_id string (e.g. "VER")
  const [comparisonDriver, setComparisonDriver] = useState(null); // driver_id string for VS mode
  
  const [selectedStint, setSelectedStint] = useState(null);
  const [selectedCompound, setSelectedCompound] = useState('ALL');
  const [selectedTeam, setSelectedTeam] = useState('ALL');
  const [driverSearchQuery, setDriverSearchQuery] = useState('');

  // Stint-level TrackShift ML/DL states
  const [stintLedger, setStintLedger] = useState(null);
  const [stintAttribution, setStintAttribution] = useState(null);
  const [driverSignatures, setDriverSignatures] = useState([]);
  const [sessionDegradationData, setSessionDegradationData] = useState(null);
  const [raceIntelligenceData, setRaceIntelligenceData] = useState(null);
  const [raceIntelligenceLoading, setRaceIntelligenceLoading] = useState(false);

  // TDSM State-Space & Multi-Horizon Prediction State
  const [tdsmState, setTdsmState] = useState(null); // { D, Delta_D, Delta2_D, TyreLife, Compound, FuelProxy, data_cutoff_lap, lap_time }
  const [tdsmForecast, setTdsmForecast] = useState(null); // { "+1": ..., "+3": ..., "+5": ..., "+10": ... }
  const [tdsmModelUsed, setTdsmModelUsed] = useState('TDSM');
  const [tdsmModelVersion, setTdsmModelVersion] = useState('TDSM-v2.0-StateTransition');
  const [tdsmLoading, setTdsmLoading] = useState(false);
  const [tdsmHistory, setTdsmHistory] = useState({}); // { [lap]: { forecast, state, observed_actual_D, driver_id } }
  const [tdsmError, setTdsmError] = useState(null);
  const tdsmReqSeqRef = useRef(0);


  // Replay Engine State
  const [replayLap, setReplayLap] = useState(1);
  const [replayProgress, setReplayProgress] = useState(0.0); // 0.0 to 1.0 along current lap
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1, 2, 4, 8

  // Telemetry Tab - Primary default is RACE INTELLIGENCE
  const [activeTelemetryTab, setActiveTelemetryTab] = useState('RACE INTELLIGENCE');

  // Loading & Error States across dependency stages
  const [loadingStage, setLoadingStage] = useState(null); // 'circuits' | 'circuit' | 'session' | 'stint' | null
  const [loadingMessage, setLoadingMessage] = useState(null);
  const [error, setError] = useState(null);

  // Sync hash routing with window history
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '') || '/';
      setCurrentRoute(hash);
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = useCallback((path) => {
    window.location.hash = path;
    setCurrentRoute(path);
  }, []);

  // 1. Initial Load & Season Change: Fetch Circuits for Selected Season
  useEffect(() => {
    setCircuitsLoading(true);
    getCircuits(selectedSeason)
      .then(data => {
        const list = data || [];
        setCircuits(list);
        setCircuitsLoading(false);
        if (list.length > 0) {
          prefetchCircuitsData(list);
        }
      })
      .catch(err => {
        console.error(`Circuits fetch error for season ${selectedSeason}:`, err);
        setError(`Failed to load circuits for season ${selectedSeason}.`);
        setCircuitsLoading(false);
      });

    getSignatures()
      .then(sigs => setDriverSignatures(sigs || []))
      .catch(err => console.warn("Signatures fetch:", err));
  }, [selectedSeason]);

  // Season Switcher Function: Clears all stale circuit, session, driver, and TDSM data immediately
  const selectSeason = useCallback((season) => {
    const numSeason = Number(season);
    if (numSeason === selectedSeason) return;

    setSelectedSeason(numSeason);
    setSelectedCircuit(null);
    setCircuitDetail(null);
    setCircuitMapData(null);
    setAvailableSessions([]);
    setSelectedSession(null);
    setSessionTelemetry(null);
    setSessionPitStops(null);
    setPitDriverFilter('ALL');
    setSelectedDriver(null);
    setComparisonDriver(null);
    setSelectedStint(null);
    setStintLedger(null);
    setStintAttribution(null);
    setTdsmState(null);
    setTdsmForecast(null);
    setTdsmHistory({});
    setTdsmLoading(false);
    setTdsmError(null);
    setReplayLap(1);
    setReplayProgress(0);
    setIsPlaying(false);
    setError(null);
    navigateTo('/circuits');
  }, [selectedSeason, navigateTo]);


  // Request Sequence IDs for race-condition cancellation
  const circuitReqSeqRef = useRef(0);
  const sessionReqSeqRef = useRef(0);

  // 2. Select Circuit: Cleanly unmount prior data and load new circuit geometry & sessions
  const selectCircuit = useCallback(async (circuitId) => {
    const currentSeq = ++circuitReqSeqRef.current;
    if (!circuitId) {
      setSelectedCircuit(null);
      setCircuitDetail(null);
      setCircuitMapData(null);
      setAvailableSessions([]);
      setSelectedSession(null);
      setSessionTelemetry(null);
      setSessionPitStops(null);
      setPitDriverFilter('ALL');
      setSelectedDriver(null);
      setComparisonDriver(null);
      setSelectedStint(null);
      setStintLedger(null);
      setStintAttribution(null);
      setTdsmState(null);
      setTdsmForecast(null);
      setTdsmHistory({});
      setTdsmLoading(false);
      setTdsmError(null);
      setReplayLap(1);
      setReplayProgress(0);
      setIsPlaying(false);
      navigateTo('/circuits');
      return;
    }

    // STRICT ISOLATION: Purge all existing session & driver & TDSM data immediately
    setSelectedCircuit(circuitId);
    setCircuitDetail(null);
    setCircuitMapData(null);
    setAvailableSessions([]);
    setSelectedSession(null);
    setSessionTelemetry(null);
    setSessionPitStops(null);
    setPitDriverFilter('ALL');
    setSelectedDriver(null);
    setComparisonDriver(null);
    setSelectedStint(null);
    setStintLedger(null);
    setStintAttribution(null);
    setTdsmState(null);
    setTdsmForecast(null);
    setTdsmHistory({});
    setTdsmLoading(false);
    setTdsmError(null);
    setReplayLap(1);
    setReplayProgress(0);
    setIsPlaying(false);
    setError(null);
    setLoadingStage('circuit');

    navigateTo(`/circuit/${circuitId}`);

    try {
      // Parallel load circuit detail, map, and sessions for this circuit only
      const [detail, map, sess] = await Promise.all([
        getCircuit(circuitId),
        getCircuitMap(circuitId).catch(() => null),
        getCircuitSessions(circuitId, selectedSeason).catch(() => [])
      ]);

      if (currentSeq !== circuitReqSeqRef.current) return; // Discard stale request

      setCircuitDetail(detail);
      setCircuitMapData(map);
      setAvailableSessions(sess || []);
      setLoadingStage(null);
    } catch (err) {
      if (currentSeq !== circuitReqSeqRef.current) return;
      console.error(`Error loading circuit ${circuitId}:`, err);
      setError(`Telemetry unavailable for circuit '${circuitId}'.`);
      setLoadingStage(null);
    }
  }, [selectedSeason, navigateTo]);


  // 3. Select Session: Load session telemetry, laps, drivers, stints
  const selectSession = useCallback(async (circuitId, sessionId) => {
    if (!circuitId || !sessionId) return;
    const currentSeq = ++sessionReqSeqRef.current;

    setSelectedCircuit(circuitId);
    setSelectedSession(sessionId);
    setSelectedDriver(null);
    setComparisonDriver(null);
    setSelectedStint(null);
    setStintLedger(null);
    setStintAttribution(null);
    setSessionPitStops(null);
    setPitDriverFilter('ALL');
    setTdsmState(null);
    setTdsmForecast(null);
    setTdsmHistory({});
    setTdsmLoading(false);
    setTdsmError(null);
    setReplayLap(1);
    setReplayProgress(0);
    setIsPlaying(false);
    setError(null);
    setLoadingStage('session');
    setLoadingMessage('Loading session metadata & driver roster...');

    navigateTo(`/circuit/${circuitId}/session/${sessionId}`);

    try {
      // 1. Ensure map geometry is loaded
      let map = circuitMapData;
      if (!map || map.circuit_id !== circuitId) {
        setLoadingMessage('Building high-precision circuit GPS corridor...');
        map = await getCircuitMap(circuitId).catch(() => null);
        if (currentSeq === sessionReqSeqRef.current) {
          setCircuitMapData(map);
        }
      }

      // 2. Fetch session telemetry
      setLoadingMessage('Loading authentic FastF1 telemetry channels...');
      const telemetryData = await getSessionTelemetry(circuitId, sessionId);
      if (currentSeq !== sessionReqSeqRef.current) return; // Discard stale request

      setSessionTelemetry(telemetryData);
      setSessionPitStops(telemetryData?.pit_stops || null);

      // 3. Auto-select first driver dynamically if available
      if (telemetryData.drivers && telemetryData.drivers.length > 0) {
        const firstDriver = telemetryData.drivers[0];
        setSelectedDriver(firstDriver.driver_id);
        setSelectedStint(firstDriver.stint_id);
        setSelectedCompound(firstDriver.compound);

        // Load stint ledger and attribution
        if (firstDriver.stint_id) {
          setLoadingMessage('Calculating Baseline Degradation Prior & Tyre Debt...');
          getLedger(firstDriver.stint_id).then(d => {
            if (currentSeq === sessionReqSeqRef.current) setStintLedger(d);
          }).catch(() => {});
          getAttribution(firstDriver.stint_id).then(d => {
            if (currentSeq === sessionReqSeqRef.current) setStintAttribution(d);
          }).catch(() => {});
        }

        // Set comparison driver to second driver if available
        if (telemetryData.drivers.length > 1) {
          setComparisonDriver(telemetryData.drivers[1].driver_id);
        }
      }

      // 4. Fetch clean degradation & contextual factors for the session
      getSessionDegradation(sessionId).then(d => {
        if (currentSeq === sessionReqSeqRef.current) setSessionDegradationData(d);
      }).catch(() => {});

      // 5. Fetch Universal Race Intelligence
      setRaceIntelligenceLoading(true);
      setLoadingMessage('Inferring TDSM State Transitions & Universal Race Forecast...');
      getRaceIntelligence(sessionId, null, 1).then(d => {
        if (currentSeq === sessionReqSeqRef.current) {
          setRaceIntelligenceData(d);
          setRaceIntelligenceLoading(false);
        }
      }).catch(err => {
        console.warn("Race intelligence fetch error:", err);
        if (currentSeq === sessionReqSeqRef.current) setRaceIntelligenceLoading(false);
      });

      setLoadingStage(null);
      setLoadingMessage(null);

    } catch (err) {
      if (currentSeq !== sessionReqSeqRef.current) return;
      console.error(`Error loading session ${sessionId}:`, err);
      setError(`Telemetry unavailable for this session.`);
      setLoadingStage(null);
      setLoadingMessage(null);
    }
  }, [circuitMapData, navigateTo]);

  // 4. Select Primary Driver: Update stint, compound, ledger, attribution
  const selectDriver = useCallback((driverId) => {
    if (!driverId || !sessionTelemetry) return;
    setSelectedDriver(driverId);
    setTdsmForecast(null);
    setTdsmLoading(true);

    const driverStint = sessionTelemetry.drivers?.find(d => d.driver_id === driverId);
    if (driverStint) {
      setSelectedStint(driverStint.stint_id);
      setSelectedCompound(driverStint.compound);

      if (driverStint.stint_id) {
        getLedger(driverStint.stint_id).then(setStintLedger).catch(() => setStintLedger(null));
        getAttribution(driverStint.stint_id).then(setStintAttribution).catch(() => setStintAttribution(null));
      }
    }
  }, [sessionTelemetry]);

  // Reactive TDSM State-Space Prediction Engine
  // Derived causally from selectedDriver's authentic telemetry rows up to replayLap
  useEffect(() => {
    if (!sessionTelemetry?.laps || !selectedDriver || !replayLap) {
      setTdsmState(null);
      setTdsmForecast(null);
      setTdsmLoading(false);
      return;
    }

    const driverLaps = sessionTelemetry.laps
      .filter(l => l.driver_id === selectedDriver)
      .sort((a, b) => a.lap_number - b.lap_number);

    if (driverLaps.length === 0) {
      setTdsmState(null);
      setTdsmForecast(null);
      setTdsmLoading(false);
      return;
    }

    // Find authentic current lap record — DO NOT substitute fake laps
    const currLap = driverLaps.find(l => l.lap_number === replayLap) ||
      (replayLap < driverLaps[0].lap_number ? driverLaps[0] : driverLaps[driverLaps.length - 1]);
    if (!currLap) {
      setTdsmState(null);
      setTdsmForecast(null);
      setTdsmLoading(false);
      setTdsmError(`REAL DATA UNAVAILABLE FOR LAP ${replayLap}`);
      return;
    }

    // Compute S_t = [D_t, Delta_D_t, Delta2_D_t] strictly from authentic telemetry
    const degMap = getDriverLapDegradationMap(driverLaps, sessionDegradationData, selectedDriver);
    const D_t = degMap[currLap.lap_number] != null 
      ? degMap[currLap.lap_number] 
      : Number((currLap.cumulative_debt ?? currLap.residual ?? 0.0).toFixed(4));

    // Previous lap for 1st derivative Delta_D (0 on initial lap)
    const prevLap = driverLaps.find(l => l.lap_number === currLap.lap_number - 1);
    const prev_D = prevLap 
      ? (degMap[prevLap.lap_number] != null ? degMap[prevLap.lap_number] : (prevLap.cumulative_debt ?? prevLap.residual ?? 0.0)) 
      : D_t;
    const Delta_D_t = prevLap ? Number((D_t - prev_D).toFixed(4)) : 0.0;

    // 2 laps back for 2nd derivative Delta2_D
    const prevLap2 = driverLaps.find(l => l.lap_number === currLap.lap_number - 2);
    const prev_Delta_D = (prevLap && prevLap2)
      ? ((degMap[prevLap.lap_number] ?? prevLap.cumulative_debt ?? 0.0) - (degMap[prevLap2.lap_number] ?? prevLap2.cumulative_debt ?? 0.0))
      : Delta_D_t;
    const Delta2_D_t = Number((Delta_D_t - prev_Delta_D).toFixed(4));

    const tyreLife = Number(currLap.tyre_age ?? replayLap);
    const compound = String(currLap.compound || selectedCompound || 'MEDIUM').toUpperCase();
    const fuelProxy = currLap.fuel_load_est != null ? Number(currLap.fuel_load_est.toFixed(1)) : 50.0;

    const currentState = {
      D: D_t,
      Delta_D: Delta_D_t,
      Delta2_D: Delta2_D_t,
      TyreLife: tyreLife,
      Compound: compound,
      FuelProxy: fuelProxy,
      data_cutoff_lap: currLap.lap_number,
      lap_time: currLap.lap_time
    };

    setTdsmState(currentState);
    setTdsmLoading(true);
    setTdsmError(null);

    const currentSeq = ++tdsmReqSeqRef.current;
    const currentDriver = selectedDriver;
    const currentLapNum = currLap.lap_number;

    predictTDSM(currentState)
      .then(res => {
        // Discard response if sequence has changed or selection moved
        if (currentSeq !== tdsmReqSeqRef.current) return;

        setTdsmForecast(res.forecast || null);
        setTdsmModelUsed(res.model_used || 'TDSM');
        setTdsmModelVersion(res.model_version || 'TDSM-v2.0');
        setTdsmLoading(false);

        // Strict Horizon Alignment: evaluate actual future telemetry targets from authentic session laps
        const horizons = [1, 3, 5, 10];
        const targets = {};
        horizons.forEach(h => {
          const targetLapNum = currentLapNum + h;
          const targetLap = driverLaps.find(l => l.lap_number === targetLapNum);
          const pred = res.forecast?.[`+${h}`];
          if (targetLap) {
            const actual_D = degMap[targetLap.lap_number] != null
              ? degMap[targetLap.lap_number]
              : Number((targetLap.cumulative_debt ?? targetLap.residual ?? 0.0).toFixed(4));
            targets[`+${h}`] = {
              target_lap: targetLapNum,
              predicted: pred != null ? Number(pred.toFixed(4)) : null,
              actual: actual_D,
              error: pred != null ? Number((pred - actual_D).toFixed(4)) : null,
              available: true
            };
          } else {
            targets[`+${h}`] = {
              target_lap: targetLapNum,
              predicted: pred != null ? Number(pred.toFixed(4)) : null,
              actual: null,
              error: null,
              available: false,
              message: `Insufficient real telemetry for +${h} validation`
            };
          }
        });

        // Store into prediction history with strict forecast origin and targets
        setTdsmHistory(prev => ({
          ...prev,
          [currentLapNum]: {
            forecast_origin_lap: currentLapNum,
            forecast: res.forecast,
            state: currentState,
            observed_actual_D: D_t,
            driver_id: currentDriver,
            targets
          }
        }));
      })
      .catch(err => {
        if (currentSeq !== tdsmReqSeqRef.current) return;
        console.warn("TDSM prediction error:", err);
        setTdsmError("TDSM unavailable");
        setTdsmLoading(false);
      });

  }, [sessionTelemetry, selectedDriver, replayLap, selectedCompound, sessionDegradationData]);

  // 5. Select Comparison Driver (Driver B)
  const selectComparisonDriver = useCallback((driverId) => {
    setComparisonDriver(prev => prev === driverId ? null : driverId);
  }, []);

  // 6. Parse URL Hash on direct link / reload
  useEffect(() => {
    if (circuits.length === 0) return;

    const parts = currentRoute.split('/').filter(Boolean);
    // Routes:
    // /circuits or / -> Home
    // /circuit/:circuitId -> Session Select
    // /circuit/:circuitId/session/:sessionId -> Dashboard
    if (parts[0] === 'circuit' && parts[1]) {
      const cId = parts[1];
      if (parts[2] === 'session' && parts[3]) {
        const sId = parts[3];
        if (selectedCircuit !== cId || selectedSession !== sId) {
          selectSession(cId, sId);
        }
      } else {
        if (selectedCircuit !== cId || selectedSession !== null) {
          selectCircuit(cId);
        }
      }
    }
  }, [currentRoute, circuits, selectCircuit, selectSession, selectedCircuit, selectedSession]);

  // 7. Replay Loop Engine (Smoothed interpolation along actual session lap count)
  const totalLaps = useMemo(() => {
    return sessionTelemetry?.total_laps || 20;
  }, [sessionTelemetry]);

  useEffect(() => {
    if (!isPlaying) return;

    const tickIntervalMs = 50; // 20 FPS updates
    // A standard lap in real time is ~85s; in replay demo mode, 1 lap takes ~6s / playbackSpeed
    const lapDurationMs = 6000 / playbackSpeed;
    const progressStep = tickIntervalMs / lapDurationMs;

    const timer = setInterval(() => {
      setReplayProgress(prevProgress => {
        const nextProgress = prevProgress + progressStep;
        if (nextProgress >= 1.0) {
          setReplayLap(prevLap => {
            if (prevLap >= totalLaps) {
              setIsPlaying(false);
              return totalLaps;
            }
            return prevLap + 1;
          });
          return 0.0;
        }
        return nextProgress;
      });
    }, tickIntervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, playbackSpeed, totalLaps]);

  // Replay Controls
  const togglePlay = useCallback(() => setIsPlaying(p => !p), []);
  const stepReplay = useCallback((delta) => {
    setReplayLap(prev => {
      const next = prev + delta;
      return Math.max(1, Math.min(totalLaps, next));
    });
    setReplayProgress(0);
  }, [totalLaps]);

  const resetReplay = useCallback(() => {
    setIsPlaying(false);
    setReplayLap(1);
    setReplayProgress(0);
  }, []);

  // Keyboard Shortcuts Handler
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        stepReplay(-1);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        stepReplay(1);
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        resetReplay();
      } else if (['1', '2', '3', '4'].includes(e.key)) {
        const speedMap = { '1': 1, '2': 2, '3': 4, '4': 8 };
        setPlaybackSpeed(speedMap[e.key]);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, stepReplay, resetReplay]);

  // Leaderboard for current replay lap
  const currentLeaderboard = useMemo(() => {
    if (!sessionTelemetry?.leaderboards_by_lap) return [];
    return sessionTelemetry.leaderboards_by_lap[String(replayLap)] || [];
  }, [sessionTelemetry, replayLap]);

  // Selected driver's current lap telemetry row
  const currentDriverLapTelemetry = useMemo(() => {
    if (!sessionTelemetry?.laps || !selectedDriver) return null;
    const driverLaps = sessionTelemetry.laps.filter(l => l.driver_id === selectedDriver);
    if (driverLaps.length === 0) return null;
    const exact = driverLaps.find(l => l.lap_number === replayLap);
    if (exact) return exact;
    if (replayLap < driverLaps[0].lap_number) return driverLaps[0];
    return driverLaps[driverLaps.length - 1];
  }, [sessionTelemetry, selectedDriver, replayLap]);

  // Comparison driver's current lap telemetry row
  const comparisonDriverLapTelemetry = useMemo(() => {
    if (!sessionTelemetry?.laps || !comparisonDriver) return null;
    const driverLaps = sessionTelemetry.laps.filter(l => l.driver_id === comparisonDriver);
    if (driverLaps.length === 0) return null;
    const exact = driverLaps.find(l => l.lap_number === replayLap);
    if (exact) return exact;
    if (replayLap < driverLaps[0].lap_number) return driverLaps[0];
    return driverLaps[driverLaps.length - 1];
  }, [sessionTelemetry, comparisonDriver, replayLap]);

  const contextValue = {
    // Navigation & Season
    currentRoute,
    navigateTo,
    availableSeasons,
    selectedSeason,
    selectSeason,

    // Circuit Data
    circuits,
    circuitsLoading,
    selectedCircuit,

    circuitDetail,
    circuitMapData,
    availableSessions,
    selectCircuit,

    // Session Data
    selectedSession,
    sessionTelemetry,
    sessionPitStops,
    pitStopDisplayMode,
    setPitStopDisplayMode,
    pitDriverFilter,
    setPitDriverFilter,
    selectSession,

    // Drivers & Stints
    selectedDriver,
    comparisonDriver,
    selectedStint,
    selectedCompound,
    setSelectedCompound,
    selectedTeam,
    setSelectedTeam,
    driverSearchQuery,
    setDriverSearchQuery,
    selectDriver,
    selectComparisonDriver,

    // TrackShift ML/DL Stint Data
    stintLedger,
    stintAttribution,
    driverSignatures,
    sessionDegradationData,
    setSessionDegradationData,
    raceIntelligenceData,
    setRaceIntelligenceData,
    raceIntelligenceLoading,

    // TDSM State-Space Prediction & Validation
    tdsmState,
    tdsmForecast,
    tdsmModelUsed,
    tdsmModelVersion,
    tdsmLoading,
    tdsmHistory,
    tdsmError,

    // Replay State & Controls
    replayLap,
    replayProgress,
    totalLaps,
    isPlaying,
    playbackSpeed,
    setReplayLap,
    togglePlay,
    setPlaybackSpeed,
    stepReplay,
    resetReplay,

    // Telemetry Tab
    activeTelemetryTab,
    setActiveTelemetryTab,

    // Derived Live State
    currentLeaderboard,
    currentDriverLapTelemetry,
    comparisonDriverLapTelemetry,

    // Status
    loadingStage,
    loadingMessage,
    error,
    clearError: () => setError(null)
  };

  return (
    <CircuitContext.Provider value={contextValue}>
      {children}
    </CircuitContext.Provider>
  );
}

export function useCircuit() {
  const ctx = useContext(CircuitContext);
  if (!ctx) {
    throw new Error('useCircuit must be used within a CircuitProvider');
  }
  return ctx;
}

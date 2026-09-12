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
  'TCN'
];


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

  // Season Switcher Function: Clears all stale circuit, session, and driver data immediately
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
      setReplayLap(1);
      setReplayProgress(0);
      setIsPlaying(false);
      navigateTo('/circuits');
      return;
    }

    // STRICT ISOLATION: Purge all existing session & driver data immediately
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

      // 3. Auto-select first driver if available
      if (telemetryData.drivers && telemetryData.drivers.length > 0) {
        const firstDriver = telemetryData.drivers[0];
        setSelectedDriver(firstDriver.driver_id);
        setSelectedStint(firstDriver.stint_id);
        setSelectedCompound(firstDriver.compound);

        // Load stint ledger and attribution
        if (firstDriver.stint_id) {
          setLoadingMessage('Calculating Stage 1 Baseline & Stage 2 Tyre Debt...');
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
      setLoadingMessage('Inferring Stage 3 TCN Behavioral Intelligence & Race Forecast...');
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
    return sessionTelemetry.laps.find(
      l => l.driver_id === selectedDriver && l.lap_number === replayLap
    ) || null;
  }, [sessionTelemetry, selectedDriver, replayLap]);

  // Comparison driver's current lap telemetry row
  const comparisonDriverLapTelemetry = useMemo(() => {
    if (!sessionTelemetry?.laps || !comparisonDriver) return null;
    return sessionTelemetry.laps.find(
      l => l.driver_id === comparisonDriver && l.lap_number === replayLap
    ) || null;
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

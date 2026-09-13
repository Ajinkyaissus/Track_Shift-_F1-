import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useCircuit } from '../context/CircuitContext';
import { computeDriverLabelLayout, buildTrackObstacles } from '../utils/mapCollisionEngine';

/**
 * TrackShift Professional Multilayer F1 Telemetry Map System
 * 
 * - Authoritative Reference Centerline: Real FastF1 GPS geometry
 * - Visual Track Corridor: Substantial asphalt corridor, runoff envelope, edges & borders
 * - Visual Hierarchy: Runoff -> Outer Border -> Asphalt -> Edge Lines -> Reference Line ->
 *                     Sectors -> DRS -> Curbs -> Start/Finish -> Corners -> Trails -> Cars -> Labels -> Overlays
 * - Proportionate Scaling: Proportions calibrated to circuit bounding box (85-90% viewport fill)
 * - Directional Cars: Real session drivers with heading angles and telemetry
 * - Intelligent Collision-Free Driver Labels with Dynamic Leader Connector Lines
 */
export default function CircuitMap({
  mapData,
  drivers = [],
  selectedDriver = null,
  comparisonDriver = null,
  replayProgress = 0.0,
  replayLap = 1,
  totalLaps = 20,
  isPlaying = false,
  onSelectDriver = null,
  weatherData = null
}) {
  const svgContainerRef = useRef(null);
  const {
    sessionPitStops,
    pitStopDisplayMode,
    setPitStopDisplayMode,
    pitDriverFilter,
    setPitDriverFilter
  } = useCircuit();
  // Visual layer & telemetry overlay modes
  const [activeOverlay, setActiveOverlay] = useState('normal'); // 'normal' | 'speed' | 'brake' | 'throttle' | 'tyre_debt'
  const [carDisplayMode, setCarDisplayMode] = useState('all'); // 'all' | 'selected' | 'none'
  const [labelMode, setLabelMode] = useState('auto'); // 'auto' | 'all' | 'selected' | 'none'
  const [showCurbs, setShowCurbs] = useState(true);
  const [showDRS, setShowDRS] = useState(true);
  const [showSectors, setShowSectors] = useState(true);
  const [showTrails, setShowTrails] = useState(true);
  const [followDriver, setFollowDriver] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });

  // Hover states
  const [hoveredCorner, setHoveredCorner] = useState(null);
  const [hoveredDriver, setHoveredDriver] = useState(null);
  const [hoveredPitStop, setHoveredPitStop] = useState(null);

  // Reset zoom & pan when circuit changes
  useEffect(() => {
    setZoomLevel(1.0);
    setPanOffset({ x: 0, y: 0 });
    setFollowDriver(false);
  }, [mapData?.circuit_id]);

  // =========================================================================
  // 1. STATIC GEOMETRY & PROPORTIONAL SCALING ENGINE
  // =========================================================================
  const circuitGeometry = useMemo(() => {
    if (!mapData || !mapData.points || mapData.points.length === 0) {
      return null;
    }

    // Authoritative reference centerline from FastF1 GPS
    const referenceCenterline = mapData.points;
    const isRotated = referenceCenterline[0].x_rot !== undefined;

    const xs = referenceCenterline.map(p => isRotated ? p.x_rot : p.x);
    const ys = referenceCenterline.map(p => isRotated ? p.y_rot : p.y);

    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    const width = maxX - minX || 1;
    const height = maxY - minY || 1;
    const D = Math.max(width, height) || 1000;

    // Viewport padding: tight 7% to guarantee circuit occupies 85-90% of map area
    const padX = width * 0.07;
    const padY = height * 0.07;

    const baseViewBox = {
      x: minX - padX,
      y: -maxY - padY,
      width: width + padX * 2,
      height: height + padY * 2,
      minX, maxX, minY, maxY,
      D
    };

    // Proportional visual scale tokens (calibrated across all 13 circuits)
    const scales = {
      asphaltWidth: Math.max(16, D * 0.024),
      runoffWidth: Math.max(26, D * 0.040),
      edgeWidth: Math.max(18, D * 0.027),
      refLineWidth: Math.max(1.2, D * 0.0016),
      curbWidth: Math.max(6, D * 0.008),
      curbDashSize: Math.max(12, D * 0.015),
      carRadius: Math.max(7, D * 0.010),
      carArrowLen: Math.max(14, D * 0.020),
      cornerBadgeR: Math.max(9, D * 0.012),
      cornerFontSize: Math.max(7.5, D * 0.0095),
      gateLen: Math.max(24, D * 0.038),
      sfGateLen: Math.max(24, D * 0.038),
      cornerOffset: Math.max(22, D * 0.030)
    };

    // Generate continuous smooth path for reference centerline
    const pathSegments = referenceCenterline.map((p, i) => {
      const px = isRotated ? p.x_rot : p.x;
      const py = isRotated ? -p.y_rot : -p.y;
      return `${i === 0 ? 'M' : 'L'} ${px.toFixed(1)} ${py.toFixed(1)}`;
    });
    const mainPathD = pathSegments.join(' ') + ' Z';

    const maxDist = referenceCenterline[referenceCenterline.length - 1]?.distance || mapData.length_m || 5000;

    // Helper for sub-paths (Sectors, DRS, etc.)
    const getSubPathD = (startPct, endPct) => {
      const startDist = startPct * maxDist;
      const endDist = endPct * maxDist;
      
      const subPoints = referenceCenterline.filter(p => {
        const d = p.distance || 0;
        if (startPct <= endPct) {
          return d >= startDist && d <= endDist;
        } else {
          return d >= startDist || d <= endDist;
        }
      });

      if (subPoints.length < 2) return '';
      return subPoints.map((p, i) => {
        const px = isRotated ? p.x_rot : p.x;
        const py = isRotated ? -p.y_rot : -p.y;
        return `${i === 0 ? 'M' : 'L'} ${px.toFixed(1)} ${py.toFixed(1)}`;
      }).join(' ');
    };

    // Helper to get point and normal at a given distance ratio
    const getPointAndNormalAtPct = (pct) => {
      const targetDist = pct * maxDist;
      let closestIdx = 0;
      let minDiff = Infinity;
      const N = referenceCenterline.length;
      for (let i = 0; i < N; i++) {
        const diff = Math.abs((referenceCenterline[i].distance || (i / N * maxDist)) - targetDist);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = i;
        }
      }
      const pt = referenceCenterline[closestIdx];
      const prevP = referenceCenterline[(closestIdx - 2 + N) % N];
      const nextP = referenceCenterline[(closestIdx + 2) % N];
      const px = isRotated ? pt.x_rot : pt.x;
      const py = isRotated ? -pt.y_rot : -pt.y;
      const dx = isRotated ? nextP.x_rot - prevP.x_rot : nextP.x - prevP.x;
      const dy = isRotated ? -(nextP.y_rot - prevP.y_rot) : -(nextP.y - prevP.y);
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const nx = -dy / len;
      const ny = dx / len;
      return { x: px, y: py, nx, ny, dx: dx / len, dy: dy / len };
    };

    // Sector definitions & boundary gate lines
    const sectors = (mapData.sectors || [
      { id: 1, name: "Sector 1", start_pct: 0.0, end_pct: 0.33 },
      { id: 2, name: "Sector 2", start_pct: 0.33, end_pct: 0.67 },
      { id: 3, name: "Sector 3", start_pct: 0.67, end_pct: 1.0 }
    ]).map(s => {
      const boundaryGate = getPointAndNormalAtPct(s.end_pct);
      return {
        ...s,
        pathD: getSubPathD(s.start_pct, s.end_pct),
        boundaryGate
      };
    });

    // DRS zones
    const drsZones = (mapData.drs_zones || []).map(drs => {
      const drsStart = getPointAndNormalAtPct(drs.start_pct);
      return {
        ...drs,
        pathD: getSubPathD(drs.start_pct, drs.end_pct),
        startPt: drsStart
      };
    });

    // Real Corner metadata & tangent-offset badges
    const N = referenceCenterline.length;
    const mappedCorners = (mapData.corners || []).map(c => {
      let cx = c.x;
      let cy = c.y;
      if (isRotated && mapData.rotation) {
        const rad = (mapData.rotation * Math.PI) / 180.0;
        const rx = c.x * Math.cos(rad) - c.y * Math.sin(rad);
        const ry = c.x * Math.sin(rad) + c.y * Math.cos(rad);
        cx = rx;
        cy = ry;
      }

      // Find closest reference point for tangent normal calculation
      let closestIdx = 0;
      let minD = Infinity;
      for (let i = 0; i < N; i++) {
        const px = isRotated ? referenceCenterline[i].x_rot : referenceCenterline[i].x;
        const py = isRotated ? referenceCenterline[i].y_rot : referenceCenterline[i].y;
        const d = (px - cx) ** 2 + (py - cy) ** 2;
        if (d < minD) {
          minD = d;
          closestIdx = i;
        }
      }

      const prevP = referenceCenterline[(closestIdx - 4 + N) % N];
      const nextP = referenceCenterline[(closestIdx + 4) % N];
      const dx = (isRotated ? nextP.x_rot - prevP.x_rot : nextP.x - prevP.x);
      const dy = (isRotated ? -(nextP.y_rot - prevP.y_rot) : -(nextP.y - prevP.y));
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      
      const nx = -dy / len;
      const ny = dx / len;
      const pt = referenceCenterline[closestIdx];

      return {
        ...c,
        svgX: cx,
        svgY: -cy,
        badgeX: cx + nx * scales.cornerOffset,
        badgeY: -cy + ny * scales.cornerOffset,
        speed: pt ? pt.speed : 180,
        throttle: pt ? pt.throttle : 80,
        brake: pt ? pt.brake : false,
        name: c.corner_name || null
      };
    });

    // Solid alternating Curbs along corner apex sections
    const curbSegments = mappedCorners.map(c => {
      const idx = referenceCenterline.findIndex(p => Math.abs((p.distance || 0) - (c.distance || 0)) < 50);
      if (idx === -1) return null;
      const startIdx = Math.max(0, idx - 8);
      const endIdx = Math.min(N - 1, idx + 8);
      const curbPts = referenceCenterline.slice(startIdx, endIdx);
      if (curbPts.length < 2) return null;

      const d = curbPts.map((p, i) => {
        const px = isRotated ? p.x_rot : p.x;
        const py = isRotated ? -p.y_rot : -p.y;
        return `${i === 0 ? 'M' : 'L'} ${px.toFixed(1)} ${py.toFixed(1)}`;
      }).join(' ');

      return { corner: c.corner_number, pathD: d };
    }).filter(Boolean);

    // Start / Finish Line gate
    const sfGate = getPointAndNormalAtPct(0.0);

    // Pit lane path (if available)
    let pitPathD = null;
    if (mapData.pit_lane?.has_data) {
      const entryPct = mapData.pit_lane.entry_pct || 0.94;
      const exitPct = mapData.pit_lane.exit_pct || 0.06;
      pitPathD = getSubPathD(entryPct, 1.0) + ' ' + getSubPathD(0.0, exitPct);
    }

    return {
      referenceCenterline,
      isRotated,
      maxDist,
      baseViewBox,
      scales,
      mainPathD,
      sectors,
      drsZones,
      corners: mappedCorners,
      curbSegments,
      sfGate,
      pitPathD,
      getPointAndNormalAtPct
    };
  }, [mapData]);

  // =========================================================================
  // 1b. ALL-DRIVER PIT STOP EVENTS COMPUTATION & MAP POSITIONING
  // =========================================================================
  const mappedPitStops = useMemo(() => {
    if (!sessionPitStops || !sessionPitStops.drivers || !circuitGeometry) return [];
    if (pitStopDisplayMode === 'OFF') return [];

    const { sfGate, scales } = circuitGeometry;
    const pitCenter = sfGate || { x: 0, y: 0, nx: 0, ny: 1, dx: 1, dy: 0 };

    let activeDrivers = sessionPitStops.drivers.filter(d => d.pit_stop_count > 0);
    if (pitStopDisplayMode === 'SELECTED') {
      activeDrivers = activeDrivers.filter(d => d.driver_id === selectedDriver);
    } else if (pitDriverFilter && pitDriverFilter !== 'ALL') {
      activeDrivers = activeDrivers.filter(d => d.driver_id === pitDriverFilter);
    }

    const events = [];
    const totalCount = Math.max(1, activeDrivers.length);

    activeDrivers.forEach((drv, drvIdx) => {
      const dId = drv.driver_id;
      const dCol = drv.team_color || '#E10600';
      const stops = drv.pit_stops || [];

      stops.forEach((ps, sIdx) => {
        // Stagger positions along the pit corridor
        const staggerX = (drvIdx - totalCount / 2) * (scales.carRadius * 3.2);
        const staggerY = (sIdx) * (scales.carRadius * 1.8);
        const normalDist = scales.asphaltWidth * 2.0 + staggerY;

        const posX = pitCenter.x + pitCenter.nx * normalDist + pitCenter.dx * staggerX;
        const posY = pitCenter.y + pitCenter.ny * normalDist + pitCenter.dy * staggerX;
        const isActiveInReplay = replayLap === ps.lap;

        events.push({
          key: `pit-${dId}-${ps.stop_number}-${ps.lap}`,
          driver_id: dId,
          driver_name: drv.full_name || dId,
          team: drv.team,
          team_color: dCol,
          stop_number: ps.stop_number,
          lap: ps.lap,
          duration: ps.duration,
          lane_duration: ps.lane_duration,
          compound_before: ps.compound_before,
          compound_after: ps.compound_after,
          tyre_age_before: ps.tyre_age_before,
          tyre_age_after: ps.tyre_age_after,
          position_before: ps.position_before,
          position_after: ps.position_after,
          position_delta: ps.position_delta,
          pit_entry_time: ps.pit_entry_time,
          pit_exit_time: ps.pit_exit_time,
          x: posX,
          y: posY,
          isActiveInReplay
        });
      });
    });

    return events;
  }, [sessionPitStops, pitStopDisplayMode, pitDriverFilter, selectedDriver, circuitGeometry, replayLap]);

  // =========================================================================
  // 2. DYNAMIC TELEMETRY CARS, HEADINGS, TRAILS & ANALYTICS
  // =========================================================================
  const { driverPositions, activeTelemetry, activeSectorId, inDRSZone, selectedCarPos } = useMemo(() => {
    if (!circuitGeometry || !circuitGeometry.referenceCenterline.length) {
      return { driverPositions: [], activeTelemetry: null, activeSectorId: 1, inDRSZone: false, selectedCarPos: null };
    }

    const { referenceCenterline, isRotated, maxDist, sectors, drsZones } = circuitGeometry;
    const N = referenceCenterline.length;
    const computed = [];
    let selTelemetry = null;
    let inDRS = false;
    let currentDist = replayProgress * maxDist;
    let activeSec = 1;

    // Active sector detection
    for (const sec of sectors) {
      const sDist = sec.start_pct * maxDist;
      const eDist = sec.end_pct * maxDist;
      if (currentDist >= sDist && currentDist <= eDist) {
        activeSec = sec.id;
        break;
      }
    }

    // Real session drivers
    const effectiveDrivers = (drivers && drivers.length > 0) ? drivers : [];

    effectiveDrivers.forEach((drv, idx) => {
      const driverId = drv.driver_id || drv;
      const isPrimary = driverId === selectedDriver;
      const isCompare = driverId === comparisonDriver;
      const profileImage = drv.profile_image || `/drivers/${(driverId || '').toLowerCase()}.webp`;

      // Real historical telemetry positioning progress per driver
      let offset = 0;
      if (drv.gap_to_leader !== undefined && drv.gap_to_leader !== null && drv.gap_to_leader >= 0) {
        const lapTimeEst = drv.lap_time && drv.lap_time > 0 ? drv.lap_time : 85.0;
        offset = -(drv.gap_to_leader / lapTimeEst);
      } else if (drv.position) {
        offset = -((drv.position - 1) * 0.018);
      } else {
        offset = isPrimary ? 0 : isCompare ? -0.02 : -(idx * 0.018);
      }
      let drvProgress = (replayProgress + offset) % 1.0;
      if (drvProgress < 0) drvProgress += 1.0;

      const pointIdx = Math.min(N - 1, Math.max(0, Math.floor(drvProgress * N)));
      const pt = referenceCenterline[pointIdx];

      if (pt) {
        const carX = isRotated ? pt.x_rot : pt.x;
        const carY = isRotated ? -pt.y_rot : -pt.y;

        // Tangent heading angle calculation
        const prevIdx = (pointIdx - 3 + N) % N;
        const nextIdx = (pointIdx + 3) % N;
        const pPrev = referenceCenterline[prevIdx];
        const pNext = referenceCenterline[nextIdx];

        const dx = (isRotated ? pNext.x_rot - pPrev.x_rot : pNext.x - pPrev.x);
        const dy = (isRotated ? -(pNext.y_rot - pPrev.y_rot) : -(pNext.y - pPrev.y));
        const headingDeg = (Math.atan2(dy, dx) * 180) / Math.PI;

        // Historical trajectory trail (last 24 points)
        let trailD = '';
        if (showTrails && (isPrimary || isCompare || labelMode === 'all')) {
          const trailLength = isPrimary ? 28 : isCompare ? 20 : 12;
          const trailPts = [];
          for (let t = 0; t < trailLength; t++) {
            const tIdx = (pointIdx - t + N) % N;
            const tp = referenceCenterline[tIdx];
            if (tp) {
              const tx = isRotated ? tp.x_rot : tp.x;
              const ty = isRotated ? -tp.y_rot : -tp.y;
              trailPts.push(`${t === 0 ? 'M' : 'L'} ${tx.toFixed(1)} ${ty.toFixed(1)}`);
            }
          }
          trailD = trailPts.join(' ');
        }

        // Selected driver DRS zone detection
        if (isPrimary) {
          const carDist = pt.distance || (drvProgress * maxDist);
          for (const drs of drsZones) {
            const sDist = drs.start_pct * maxDist;
            const eDist = drs.end_pct * maxDist;
            if (carDist >= sDist && carDist <= eDist) {
              inDRS = true;
              break;
            }
          }

          selTelemetry = {
            speed: pt.speed || 285,
            throttle: pt.throttle || 95,
            brake: pt.brake || false,
            distance: pt.distance || currentDist,
            gear: pt.speed > 290 ? 8 : pt.speed > 250 ? 7 : pt.speed > 200 ? 6 : pt.speed > 150 ? 5 : pt.speed > 110 ? 4 : 3,
            heading: headingDeg,
            inDRS
          };
        }

        computed.push({
          driver_id: driverId,
          full_name: drv.full_name || drv.name || driverId,
          number: drv.driver_number || drv.number || (idx + 1),
          team: drv.team || '',
          team_color: drv.team_color || '#E10600',
          profile_image: profileImage,
          position: drv.position || (idx + 1),
          compound: drv.compound || 'HARD',
          tyre_age: drv.tyre_age || replayLap,
          cumulative_debt: drv.cumulative_debt ?? 0.0,
          isPrimary,
          isCompare,
          x: carX,
          y: carY,
          heading: headingDeg,
          trailD,
          speed: pt.speed || 260,
          throttle: pt.throttle || 90,
          brake: pt.brake || false
        });
      }
    });

    const primaryCar = computed.find(c => c.isPrimary);

    return {
      driverPositions: computed,
      activeTelemetry: selTelemetry,
      activeSectorId: activeSec,
      inDRSZone: inDRS,
      selectedCarPos: primaryCar ? { x: primaryCar.x, y: primaryCar.y } : null
    };
  }, [circuitGeometry, drivers, selectedDriver, comparisonDriver, replayProgress, replayLap, showTrails]);

  // =========================================================================
  // 2b. STATIC & DYNAMIC TRACK OBSTACLES FOR COLLISION ENGINE
  // =========================================================================
  const trackObstacles = useMemo(() => {
    if (!circuitGeometry) return [];
    return buildTrackObstacles({
      corners: circuitGeometry.corners,
      drsZones: circuitGeometry.drsZones,
      sectors: circuitGeometry.sectors,
      sfGate: circuitGeometry.sfGate,
      pitStops: mappedPitStops,
      scales: circuitGeometry.scales
    });
  }, [circuitGeometry, mappedPitStops]);

  // =========================================================================
  // 2c. INTELLIGENT COLLISION-FREE DRIVER LABEL LAYOUT & LEADER LINES
  // =========================================================================
  const { labels: positionedLabels } = useMemo(() => {
    if (!circuitGeometry || !driverPositions.length) {
      return { labels: [] };
    }
    return computeDriverLabelLayout({
      driverPositions,
      obstacles: trackObstacles,
      selectedDriver,
      comparisonDriver,
      hoveredDriver,
      labelMode,
      carDisplayMode,
      zoomLevel,
      scales: circuitGeometry.scales
    });
  }, [circuitGeometry, driverPositions, trackObstacles, selectedDriver, comparisonDriver, hoveredDriver, labelMode, carDisplayMode, zoomLevel]);

  // Filter cars based on carDisplayMode
  const visibleCars = useMemo(() => {
    if (carDisplayMode === 'none') return [];
    if (carDisplayMode === 'selected') {
      return driverPositions.filter(drv => drv.isPrimary || drv.isCompare);
    }
    return driverPositions;
  }, [driverPositions, carDisplayMode]);

  // =========================================================================
  // 3. CAMERA & VIEWPORT ENGINE (FIT TO TRACK & FOLLOW DRIVER)
  // =========================================================================
  const fitToTrack = useCallback(() => {
    setZoomLevel(1.0);
    setPanOffset({ x: 0, y: 0 });
    setFollowDriver(false);
  }, []);

  const activeViewBox = useMemo(() => {
    if (!circuitGeometry) return '0 0 1000 1000';
    const { baseViewBox } = circuitGeometry;

    let targetW = baseViewBox.width / zoomLevel;
    let targetH = baseViewBox.height / zoomLevel;
    let targetX = baseViewBox.x + panOffset.x;
    let targetY = baseViewBox.y + panOffset.y;

    if (followDriver && selectedCarPos) {
      targetX = selectedCarPos.x - targetW / 2;
      targetY = selectedCarPos.y - targetH / 2;
    } else {
      targetX += (baseViewBox.width - targetW) / 2;
      targetY += (baseViewBox.height - targetH) / 2;
    }

    return `${targetX.toFixed(1)} ${targetY.toFixed(1)} ${targetW.toFixed(1)} ${targetH.toFixed(1)}`;
  }, [circuitGeometry, zoomLevel, panOffset, followDriver, selectedCarPos]);

  // Analytical color helpers
  const getSpeedStroke = (speed) => {
    if (speed < 110) return '#4A0E4E';
    if (speed < 170) return '#1A659E';
    if (speed < 230) return '#00D2BE';
    if (speed < 280) return '#FFB800';
    return '#E10600';
  };

  const getTyreDebtStroke = (debt) => {
    if (debt <= 0.1) return '#00D2BE';
    if (debt <= 0.35) return '#FFB800';
    return '#E10600';
  };

  if (!circuitGeometry) {
    return (
      <div className="circuit-map-wrapper empty-map">
        <div className="empty-state-content">
          <div className="pulse-dot"></div>
          <span>Track geometry unavailable</span>
        </div>
      </div>
    );
  }

  const {
    scales,
    mainPathD,
    sectors,
    drsZones,
    corners,
    curbSegments,
    sfGate,
    pitPathD,
    referenceCenterline
  } = circuitGeometry;

  return (
    <div className="circuit-map-wrapper" ref={svgContainerRef}>
      {/* 1. BROADCAST TOP HUD */}
      <div className="map-broadcast-hud">
        <div className="hud-track-meta">
          <div className="hud-title-row">
            <span className="hud-circuit-badge">F1 GPS TELEMETRY</span>
            <h3 className="hud-circuit-name">{mapData.name}</h3>
          </div>
          <div className="hud-badges-row">
            <span className="hud-chip">Length: <strong>{mapData.length_m ? `${(mapData.length_m / 1000).toFixed(3)} km` : `${(referenceCenterline.length * 4.5 / 1000).toFixed(2)} km`}</strong></span>
            <span className="hud-chip">Corners: <strong>{corners.length}</strong></span>
            <span className="hud-chip">DRS Zones: <strong>{drsZones.length}</strong></span>
            <span className="hud-chip verified">✓ FastF1 Real GPS</span>
          </div>
        </div>

        <div className="hud-status-cluster">
          <div className="hud-lap-badge">
            <span className={isPlaying ? "pulse-dot active" : "idle-dot"}></span>
            <span className="hud-lap-text">LAP {replayLap} / {totalLaps}</span>
          </div>
          <div className="hud-flag-badge">
            <span className="flag-dot green"></span>
            <span>TRACK: GREEN</span>
          </div>
          <div className="hud-sector-indicator">
            <span className={`sec-pill ${activeSectorId === 1 ? 'active' : ''}`}>S1</span>
            <span className={`sec-pill ${activeSectorId === 2 ? 'active' : ''}`}>S2</span>
            <span className={`sec-pill ${activeSectorId === 3 ? 'active' : ''}`}>S3</span>
          </div>
          {weatherData && (
            <div className="hud-weather-chip">
              <span>⛅ {weatherData.air_temp || 28}°C Air · {weatherData.track_temp || 35}°C Track</span>
            </div>
          )}
        </div>
      </div>

      {/* 2. MAP CONTROLS TOOLBAR */}
      <div className="map-toolbar-container">
        <div className="toolbar-group">
          <span className="toolbar-label">TELEMETRY LAYER</span>
          <div className="toolbar-buttons">
            <button
              className={`toolbar-btn ${activeOverlay === 'normal' ? 'active' : ''}`}
              onClick={() => setActiveOverlay('normal')}
              title="Standard Racing Surface & Reference Centerline"
            >
              Trace
            </button>
            <button
              className={`toolbar-btn ${activeOverlay === 'speed' ? 'active' : ''}`}
              onClick={() => setActiveOverlay('speed')}
              title="Speed Heatmap (km/h Telemetry-derived)"
            >
              Speed Map
            </button>
            <button
              className={`toolbar-btn ${activeOverlay === 'brake' ? 'active' : ''}`}
              onClick={() => setActiveOverlay('brake')}
              title="Braking Deceleration Zones"
            >
              Braking
            </button>
            <button
              className={`toolbar-btn ${activeOverlay === 'throttle' ? 'active' : ''}`}
              onClick={() => setActiveOverlay('throttle')}
              title="Throttle Application Overlay"
            >
              Throttle
            </button>
            <button
              className={`toolbar-btn highlight ${activeOverlay === 'tyre_debt' ? 'active' : ''}`}
              onClick={() => setActiveOverlay('tyre_debt')}
              title="TrackShift Tyre Debt Trajectory Map"
            >
              Tyre Debt
            </button>
          </div>
        </div>

        <div className="toolbar-group toggles-group">
          <button
            className={`tool-toggle-btn ${showCurbs ? 'active' : ''}`}
            onClick={() => setShowCurbs(!showCurbs)}
            title="Toggle Curbs & Apex Blocks"
          >
            Curbs
          </button>
          <button
            className={`tool-toggle-btn ${showSectors ? 'active' : ''}`}
            onClick={() => setShowSectors(!showSectors)}
            title="Toggle S1/S2/S3 Sector Bands & Gates"
          >
            Sectors
          </button>
          <button
            className={`tool-toggle-btn ${showDRS && drsZones.length > 0 ? 'active' : ''}`}
            onClick={() => drsZones.length > 0 && setShowDRS(!showDRS)}
            title={drsZones.length > 0 ? "Toggle DRS Zones" : "DRS Zones Unavailable for this Circuit"}
            style={{ opacity: drsZones.length > 0 ? 1 : 0.5, cursor: drsZones.length > 0 ? 'pointer' : 'not-allowed' }}
          >
            {drsZones.length > 0 ? "DRS" : "DRS [UNAVAILABLE]"}
          </button>

          <button
            className={`tool-toggle-btn ${showTrails ? 'active' : ''}`}
            onClick={() => setShowTrails(!showTrails)}
            title="Toggle Driver Telemetry Trails"
          >
            Trails
          </button>
          <button
            className={`tool-toggle-btn ${followDriver ? 'active' : ''}`}
            onClick={() => setFollowDriver(!followDriver)}
            title="Follow Selected Driver Camera"
          >
            {followDriver ? "Following" : "Follow Cam"}
          </button>
        </div>

        {/* Pit Stop Layer Modes & Driver Filter */}
        <div className="toolbar-group pit-stop-controls">
          <span className="pit-ctrl-label">PIT STOPS:</span>
          <div className="segmented-control">
            <button 
              className={`seg-btn ${pitStopDisplayMode === 'ALL' ? 'active' : ''}`}
              onClick={() => setPitStopDisplayMode('ALL')}
              title="Show All Driver Pit Stops"
            >
              All Drivers
            </button>
            <button 
              className={`seg-btn ${pitStopDisplayMode === 'SELECTED' ? 'active' : ''}`}
              onClick={() => setPitStopDisplayMode('SELECTED')}
              title="Show Selected Driver Pit Stops"
            >
              Selected
            </button>
            <button 
              className={`seg-btn ${pitStopDisplayMode === 'OFF' ? 'active' : ''}`}
              onClick={() => setPitStopDisplayMode('OFF')}
              title="Hide Pit Stop Markers"
            >
              Off
            </button>
          </div>

          {pitStopDisplayMode !== 'OFF' && sessionPitStops?.drivers && (
            <select
              className="pit-driver-filter-select"
              value={pitDriverFilter || 'ALL'}
              onChange={(e) => setPitDriverFilter(e.target.value)}
              title="Filter Pit Stops by Driver"
            >
              <option value="ALL">ALL DRIVERS ({sessionPitStops.total_pit_stops} STOPS)</option>
              {sessionPitStops.drivers.map(d => (
                <option key={d.driver_id} value={d.driver_id}>
                  {d.driver_id} ({d.pit_stop_count} stops)
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Cars Visibility Control */}
        <div className="toolbar-group">
          <span className="toolbar-label">CARS:</span>
          <div className="segmented-control">
            <button 
              className={`seg-btn ${carDisplayMode === 'all' ? 'active' : ''}`}
              onClick={() => setCarDisplayMode('all')}
              title="Show All Session Cars on Track"
            >
              All Cars
            </button>
            <button 
              className={`seg-btn ${carDisplayMode === 'selected' ? 'active' : ''}`}
              onClick={() => setCarDisplayMode('selected')}
              title="Show Only Selected & Comparison Cars"
            >
              Selected
            </button>
            <button 
              className={`seg-btn ${carDisplayMode === 'none' ? 'active' : ''}`}
              onClick={() => setCarDisplayMode('none')}
              title="Hide Car Markers"
            >
              None
            </button>
          </div>
        </div>

        {/* Labels Collision Avoidance Control */}
        <div className="toolbar-group">
          <span className="toolbar-label">LABELS:</span>
          <div className="segmented-control">
            <button 
              className={`seg-btn ${labelMode === 'auto' ? 'active' : ''}`}
              onClick={() => setLabelMode('auto')}
              title="Intelligent Priority & Collision Avoidance"
            >
              Auto
            </button>
            <button 
              className={`seg-btn ${labelMode === 'all' ? 'active' : ''}`}
              onClick={() => setLabelMode('all')}
              title="Display All Driver Labels with Leader Lines"
            >
              All
            </button>
            <button 
              className={`seg-btn ${labelMode === 'selected' ? 'active' : ''}`}
              onClick={() => setLabelMode('selected')}
              title="Show Only Selected Driver Labels"
            >
              Selected
            </button>
            <button 
              className={`seg-btn ${labelMode === 'none' ? 'active' : ''}`}
              onClick={() => setLabelMode('none')}
              title="Hide All Driver Labels"
            >
              None
            </button>
          </div>
        </div>

        <div className="toolbar-group camera-controls">
          <button 
            className="cam-btn" 
            onClick={() => setZoomLevel(prev => Math.min(prev + 0.35, 4.0))} 
            title="Zoom In"
          >
            +
          </button>
          <button 
            className="cam-btn" 
            onClick={() => setZoomLevel(prev => Math.max(prev - 0.35, 0.75))} 
            title="Zoom Out"
          >
            -
          </button>
          <button 
            className="cam-btn reset" 
            onClick={fitToTrack} 
            title="Fit Track to Viewport"
          >
            Fit
          </button>
        </div>
      </div>

      {/* 3. MULTILAYER SVG CANVAS */}
      <div className="svg-canvas-container">
        <svg
          viewBox={activeViewBox}
          className="circuit-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <pattern id="circuitGrid" width="100" height="100" patternUnits="userSpaceOnUse">
              <path d="M 100 0 L 0 0 0 100" fill="none" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />
            </pattern>

            <filter id="carGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id="drsGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Checkered Start/Finish Gate Pattern */}
            <pattern id="checkeredGate" width="10" height="10" patternUnits="userSpaceOnUse">
              <rect width="5" height="5" fill="#FFFFFF" />
              <rect x="5" width="5" height="5" fill="#111118" />
              <rect y="5" width="5" height="5" fill="#111118" />
              <rect x="5" y="5" width="5" height="5" fill="#FFFFFF" />
            </pattern>
          </defs>

          {/* ================= LAYER 1: AMBIENT GRID ================= */}
          <rect
            x={circuitGeometry.baseViewBox.x - 3000}
            y={circuitGeometry.baseViewBox.y - 3000}
            width={circuitGeometry.baseViewBox.width + 6000}
            height={circuitGeometry.baseViewBox.height + 6000}
            fill="url(#circuitGrid)"
          />

          {/* ================= LAYER 2: RUNOFF & CONTEXT ENVELOPE ================= */}
          <path
            d={mainPathD}
            fill="none"
            stroke="#131420"
            strokeWidth={scales.runoffWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* ================= LAYER 3: TRACK OUTER SHADOW & BORDER ================= */}
          <path
            d={mainPathD}
            fill="none"
            stroke="#090A10"
            strokeWidth={scales.edgeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* ================= LAYER 4: TRACK ASPHALT SURFACE ================= */}
          <path
            d={mainPathD}
            fill="none"
            stroke="#1D1E2C"
            strokeWidth={scales.asphaltWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* ================= LAYER 5: TRACK LIMIT BOUNDARY LINES ================= */}
          <path
            d={mainPathD}
            fill="none"
            stroke="rgba(255, 255, 255, 0.12)"
            strokeWidth={scales.asphaltWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="2 12"
          />

          {/* ================= LAYER 6: SUBTLE REFERENCE CENTERLINE ================= */}
          <path
            d={mainPathD}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={scales.refLineWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="4 6"
          />

          {/* ================= LAYER 7: SECTOR DIVISIONS & GATES ================= */}
          {showSectors && sectors.map((sec) => {
            const isSecActive = activeSectorId === sec.id;
            const secColor = sec.id === 1 ? '#00D2BE' : sec.id === 2 ? '#FFB800' : '#BF5AF2';
            const g = sec.boundaryGate;
            const hx = g.nx * (scales.gateLen / 2);
            const hy = g.ny * (scales.gateLen / 2);

            return (
              <g key={`sec-${sec.id}`} className={`sector-layer ${isSecActive ? 'active-sector' : ''}`}>
                {/* Sector Path Strip */}
                <path
                  d={sec.pathD}
                  fill="none"
                  stroke={secColor}
                  strokeWidth={isSecActive ? scales.asphaltWidth * 0.25 : scales.asphaltWidth * 0.15}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeOpacity={isSecActive ? "0.9" : "0.4"}
                />

                {/* Perpendicular Sector Boundary Gate Line */}
                <line
                  x1={g.x - hx}
                  y1={g.y - hy}
                  x2={g.x + hx}
                  y2={g.y + hy}
                  stroke={secColor}
                  strokeWidth={scales.refLineWidth * 2}
                  strokeDasharray="4 3"
                />
                
                {/* Sector Badge Indicator */}
                <text
                  x={g.x + g.nx * (scales.asphaltWidth * 0.9)}
                  y={g.y + g.ny * (scales.asphaltWidth * 0.9)}
                  fill={secColor}
                  fontSize={scales.cornerFontSize}
                  fontWeight="800"
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  S{sec.id}
                </text>
              </g>
            );
          })}

          {/* ================= LAYER 8: DRS ZONES ================= */}
          {showDRS && drsZones.map((drs, i) => (
            <g key={`drs-${i}`} className="drs-zone-group">
              <path
                d={drs.pathD}
                fill="none"
                stroke="#00E676"
                strokeWidth={scales.asphaltWidth * 0.55}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeOpacity="0.85"
                filter="url(#drsGlow)"
              />
              {/* DRS Badge Tag */}
              <text
                x={drs.startPt.x + drs.startPt.nx * (scales.asphaltWidth * 0.85)}
                y={drs.startPt.y + drs.startPt.ny * (scales.asphaltWidth * 0.85)}
                fill="#00E676"
                fontSize={scales.cornerFontSize}
                fontWeight="800"
                textAnchor="middle"
                dominantBaseline="central"
              >
                DRS
              </text>
            </g>
          ))}

          {/* ================= LAYER 9: SOLID ALTERNATING CURBS ================= */}
          {showCurbs && curbSegments.map((curb, i) => (
            <g key={`curb-${i}`} className="circuit-curb-group">
              {/* Red Curb Segments */}
              <path
                d={curb.pathD}
                fill="none"
                stroke="#E10600"
                strokeWidth={scales.curbWidth}
                strokeLinecap="butt"
                strokeLinejoin="round"
                strokeDasharray={`${scales.curbDashSize} ${scales.curbDashSize}`}
                opacity="0.95"
              />
              {/* White Curb Segments */}
              <path
                d={curb.pathD}
                fill="none"
                stroke="#FFFFFF"
                strokeWidth={scales.curbWidth}
                strokeLinecap="butt"
                strokeLinejoin="round"
                strokeDasharray={`${scales.curbDashSize} ${scales.curbDashSize}`}
                strokeDashoffset={scales.curbDashSize}
                opacity="0.95"
              />
            </g>
          ))}

          {/* ================= LAYER 10: PIT LANE ================= */}
          {pitPathD && (
            <g className="pit-lane-layer">
              <path
                d={pitPathD}
                fill="none"
                stroke="#474960"
                strokeWidth={scales.asphaltWidth * 0.45}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="6 4"
              />
            </g>
          )}

          {/* ================= LAYER 10b: ALL-DRIVER PIT STOP MARKERS ================= */}
          {mappedPitStops.length > 0 && (
            <g className="pit-stops-layer">
              {mappedPitStops.map((ps) => {
                const isSelected = ps.driver_id === selectedDriver;
                const rSize = scales.carRadius * (ps.isActiveInReplay ? 1.35 : 1.1);

                return (
                  <g
                    key={ps.key}
                    transform={`translate(${ps.x}, ${ps.y})`}
                    onClick={() => onSelectDriver && onSelectDriver(ps.driver_id)}
                    onMouseEnter={() => setHoveredPitStop(ps)}
                    onMouseLeave={() => setHoveredPitStop(null)}
                    style={{ cursor: 'pointer' }}
                    className={`pit-marker-group ${ps.isActiveInReplay ? 'active-replay-pit' : ''} ${isSelected ? 'selected-driver-pit' : ''}`}
                  >
                    {/* Active In-Replay Glowing Pulse Halo */}
                    {ps.isActiveInReplay && (
                      <circle
                        r={rSize * 2.2}
                        fill="rgba(255, 184, 0, 0.25)"
                        stroke="#FFB800"
                        strokeWidth={scales.refLineWidth * 1.5}
                      >
                        <animate attributeName="r" values={`${rSize * 1.5};${rSize * 2.5};${rSize * 1.5}`} dur="1.0s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.9;0.2;0.9" dur="1.0s" repeatCount="indefinite" />
                      </circle>
                    )}

                    {/* Outer Border Marker */}
                    <circle
                      r={rSize}
                      fill="#0C0D16"
                      stroke={ps.team_color}
                      strokeWidth={isSelected || ps.isActiveInReplay ? scales.refLineWidth * 2.5 : scales.refLineWidth * 1.5}
                    />

                    {/* Pit Stop Icon / Stop Dot */}
                    <circle
                      r={rSize * 0.45}
                      fill={ps.isActiveInReplay ? "#FFB800" : ps.team_color}
                    />

                    {/* Distinct Driver Identity Tag Badge */}
                    <g transform={`translate(0, ${-rSize * 1.6})`} className="pit-driver-badge">
                      <rect
                        x={-scales.asphaltWidth * 1.3}
                        y={-scales.cornerFontSize * 1.3}
                        width={scales.asphaltWidth * 2.6}
                        height={scales.cornerFontSize * 2.4}
                        rx="4"
                        fill="#0A0B14"
                        stroke={ps.team_color}
                        strokeWidth={scales.refLineWidth * 1.2}
                      />
                      <text
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#FFFFFF"
                        fontSize={scales.cornerFontSize * 0.95}
                        fontWeight="900"
                        y={-scales.cornerFontSize * 0.25}
                      >
                        {ps.driver_id} #{ps.stop_number}
                      </text>
                      <text
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#A0A5BD"
                        fontSize={scales.cornerFontSize * 0.72}
                        fontWeight="700"
                        y={scales.cornerFontSize * 0.6}
                      >
                        L{ps.lap} · {ps.duration}s
                      </text>
                    </g>
                  </g>
                );
              })}
            </g>
          )}

          {/* ================= LAYER 11: CHECKERED START / FINISH GATE ================= */}
          {sfGate && (
            <g className="start-finish-group">
              <line
                x1={sfGate.x - sfGate.nx * (scales.sfGateLen / 2)}
                y1={sfGate.y - sfGate.ny * (scales.sfGateLen / 2)}
                x2={sfGate.x + sfGate.nx * (scales.sfGateLen / 2)}
                y2={sfGate.y + sfGate.ny * (scales.sfGateLen / 2)}
                stroke="url(#checkeredGate)"
                strokeWidth={scales.asphaltWidth * 0.35}
                strokeLinecap="butt"
              />
              <text
                x={sfGate.x + sfGate.nx * (scales.asphaltWidth * 1.1)}
                y={sfGate.y + sfGate.ny * (scales.asphaltWidth * 1.1)}
                textAnchor="middle"
                dominantBaseline="central"
                fill="#FFFFFF"
                fontSize={scales.cornerFontSize * 0.9}
                fontWeight="800"
                letterSpacing="0.5"
              >
                START / FINISH
              </text>
            </g>
          )}

          {/* ================= LAYER 12: ANALYTICAL TELEMETRY OVERLAYS ================= */}
          {activeOverlay === 'speed' && (
            <g className="speed-heatmap-layer">
              {referenceCenterline.map((p, idx) => {
                if (idx % 2 !== 0 && idx < referenceCenterline.length - 1) return null;
                const nextP = referenceCenterline[Math.min(referenceCenterline.length - 1, idx + 2)];
                const x1 = circuitGeometry.isRotated ? p.x_rot : p.x;
                const y1 = circuitGeometry.isRotated ? -p.y_rot : -p.y;
                const x2 = circuitGeometry.isRotated ? nextP.x_rot : nextP.x;
                const y2 = circuitGeometry.isRotated ? -nextP.y_rot : -nextP.y;
                const col = getSpeedStroke(p.speed || 250);
                return (
                  <line
                    key={`spd-${idx}`}
                    x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke={col}
                    strokeWidth={scales.asphaltWidth * 0.5}
                    strokeLinecap="round"
                  />
                );
              })}
            </g>
          )}

          {activeOverlay === 'brake' && (
            <g className="brake-overlay-layer">
              {referenceCenterline.map((p, idx) => {
                if (!p.brake && (p.speed_delta || 0) > -1.5) return null;
                const x1 = circuitGeometry.isRotated ? p.x_rot : p.x;
                const y1 = circuitGeometry.isRotated ? -p.y_rot : -p.y;
                return (
                  <circle
                    key={`brk-${idx}`}
                    cx={x1} cy={y1}
                    r={scales.asphaltWidth * 0.4}
                    fill="rgba(225, 6, 0, 0.55)"
                  />
                );
              })}
            </g>
          )}

          {activeOverlay === 'throttle' && (
            <g className="throttle-overlay-layer">
              {referenceCenterline.map((p, idx) => {
                if (idx % 3 !== 0) return null;
                const x1 = circuitGeometry.isRotated ? p.x_rot : p.x;
                const y1 = circuitGeometry.isRotated ? -p.y_rot : -p.y;
                const thr = p.throttle || 100;
                const col = thr > 80 ? '#00E676' : thr > 50 ? '#FFB800' : '#FF3B30';
                return (
                  <circle
                    key={`thr-${idx}`}
                    cx={x1} cy={y1}
                    r={thr > 80 ? scales.asphaltWidth * 0.25 : scales.asphaltWidth * 0.18}
                    fill={col}
                    opacity="0.85"
                  />
                );
              })}
            </g>
          )}

          {activeOverlay === 'tyre_debt' && (
            <g className="tyre-debt-overlay-layer">
              {referenceCenterline.map((p, idx) => {
                if (idx % 2 !== 0 && idx < referenceCenterline.length - 1) return null;
                const nextP = referenceCenterline[Math.min(referenceCenterline.length - 1, idx + 2)];
                const x1 = circuitGeometry.isRotated ? p.x_rot : p.x;
                const y1 = circuitGeometry.isRotated ? -p.y_rot : -p.y;
                const x2 = circuitGeometry.isRotated ? nextP.x_rot : nextP.x;
                const y2 = circuitGeometry.isRotated ? -nextP.y_rot : -nextP.y;
                
                // Real track-point tyre wear degradation stress derived from braking deceleration and corner load
                const speedVal = p.speed || (p.Speed || 220);
                const isHeavyBraking = p.brake || (p.Brake && p.Brake > 0.1) || speedVal < 140;
                const isCornerApex = speedVal < 190 && (p.throttle || p.Throttle || 100) < 80;
                const baseDebt = driverPositions.find(d => d.isPrimary)?.cumulative_debt || 0.15;
                const pointDebtStress = isHeavyBraking 
                  ? Math.min(1.0, baseDebt * 1.5 + 0.35)
                  : isCornerApex 
                    ? Math.min(1.0, baseDebt * 1.2 + 0.20)
                    : Math.max(0.02, baseDebt * 0.4);
                const col = getTyreDebtStroke(pointDebtStress);
                return (
                  <line
                    key={`deb-${idx}`}
                    x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke={col}
                    strokeWidth={isHeavyBraking || isCornerApex ? scales.asphaltWidth * 0.6 : scales.asphaltWidth * 0.35}
                    strokeLinecap="round"
                    strokeOpacity={isHeavyBraking ? "0.95" : "0.75"}
                  />
                );
              })}
            </g>
          )}

          {/* ================= LAYER 13: CORNER NUMBER BADGES (T1...TN) ================= */}
          {corners.map((c, idx) => (
            <g
              key={`corner-${idx}`}
              transform={`translate(${c.badgeX}, ${c.badgeY})`}
              onMouseEnter={() => setHoveredCorner(c)}
              onMouseLeave={() => setHoveredCorner(null)}
              className="corner-badge-group"
              style={{ cursor: 'pointer' }}
            >
              <circle
                r={scales.cornerBadgeR}
                fill="#0E0F17"
                stroke={hoveredCorner?.corner_number === c.corner_number ? "#00D2BE" : "#E10600"}
                strokeWidth={scales.refLineWidth * 1.5}
              />
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fill="#FFFFFF"
                fontSize={scales.cornerFontSize}
                fontWeight="800"
              >
                {c.corner_number}{c.corner_letter || ''}
              </text>
            </g>
          ))}

          {/* ================= LAYER 14: DRIVER TELEMETRY TRAILS ================= */}
          {showTrails && visibleCars.map((drv) => {
            if (!drv.trailD) return null;
            const trailColor = drv.isPrimary ? '#E10600' : drv.isCompare ? '#00D2BE' : drv.team_color;
            return (
              <path
                key={`trail-${drv.driver_id}`}
                d={drv.trailD}
                fill="none"
                stroke={trailColor}
                strokeWidth={drv.isPrimary ? scales.asphaltWidth * 0.35 : scales.asphaltWidth * 0.2}
                strokeLinecap="round"
                strokeOpacity={drv.isPrimary ? "0.8" : "0.5"}
              />
            );
          })}

          {/* ================= LAYER 15: DIRECTIONAL TELEMETRY CARS (EXACT GPS POSITIONS) ================= */}
          {visibleCars.map((drv) => {
            const isPrimary = drv.isPrimary;
            const isCompare = drv.isCompare;
            const markerColor = isPrimary ? '#E10600' : isCompare ? '#00D2BE' : (drv.team_color || '#787A8E');

            const arrowLen = isPrimary ? scales.carArrowLen * 1.25 : scales.carArrowLen;
            const arrowW = isPrimary ? scales.carArrowLen * 0.65 : scales.carArrowLen * 0.5;

            return (
              <g
                key={`car-${drv.driver_id}`}
                transform={`translate(${drv.x}, ${drv.y})`}
                onClick={() => onSelectDriver && onSelectDriver(drv.driver_id)}
                onMouseEnter={() => setHoveredDriver(drv)}
                onMouseLeave={() => setHoveredDriver(null)}
                style={{ cursor: 'pointer' }}
                className={`map-car-marker ${isPrimary ? 'primary' : isCompare ? 'compare' : 'other'}`}
              >
                {/* Glowing Aura Ring for Selected / Comparison */}
                {(isPrimary || isCompare) && (
                  <circle
                    r={arrowLen * 1.5}
                    fill={isPrimary ? "rgba(225, 6, 0, 0.25)" : "rgba(0, 210, 190, 0.25)"}
                    filter="url(#carGlow)"
                  >
                    <animate attributeName="r" values={`${arrowLen * 1.2};${arrowLen * 1.8};${arrowLen * 1.2}`} dur="1.2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.8;0.2;0.8" dur="1.2s" repeatCount="indefinite" />
                  </circle>
                )}

                {/* Rotated Motorsport Directional Vehicle Silhouette */}
                <g transform={`rotate(${drv.heading})`}>
                  <polygon
                    points={`${arrowLen * 0.8},0 ${-arrowLen * 0.5},${-arrowW * 0.6} ${-arrowLen * 0.2},0 ${-arrowLen * 0.5},${arrowW * 0.6}`}
                    fill={markerColor}
                    stroke={isPrimary || isCompare ? "#FFFFFF" : "rgba(255,255,255,0.75)"}
                    strokeWidth={isPrimary ? scales.refLineWidth * 1.8 : scales.refLineWidth}
                  />
                  <circle r={isPrimary ? scales.carRadius * 0.4 : scales.carRadius * 0.3} fill="#0A0A10" />
                </g>
              </g>
            );
          })}

          {/* ================= LAYER 16: INTELLIGENT DRIVER LABELS & DYNAMIC LEADER LINES ================= */}
          <g className="driver-labels-layer">
            {/* 16a. Dynamic Leader / Connector Lines */}
            {positionedLabels.map((lbl) => {
              if (!lbl.needsLeader) return null;
              const ldr = lbl.leader;
              const leaderColor = lbl.isSelected ? '#E10600' : lbl.isCompare ? '#00D2BE' : (lbl.drv.team_color || '#8E92A4');

              return (
                <g key={`leader-${lbl.driver_id}`} className="driver-leader-group">
                  {/* Subtle connector line terminating at exact car telemetry position */}
                  <line
                    x1={ldr.startX}
                    y1={ldr.startY}
                    x2={ldr.endX}
                    y2={ldr.endY}
                    stroke={leaderColor}
                    strokeWidth={lbl.isSelected ? scales.refLineWidth * 1.6 : scales.refLineWidth * 1.1}
                    strokeDasharray={lbl.isSelected ? "none" : "3 2"}
                    strokeOpacity={lbl.isSelected ? "0.9" : "0.65"}
                  />
                  {/* Small termination dot at car marker */}
                  <circle
                    cx={ldr.endX}
                    cy={ldr.endY}
                    r={scales.refLineWidth * 1.5}
                    fill={leaderColor}
                    opacity="0.85"
                  />
                </g>
              );
            })}

            {/* 16b. Collision-Avoidant Placed Driver Labels */}
            {positionedLabels.map((lbl) => {
              const drv = lbl.drv;
              const isSelected = lbl.isSelected;
              const isCompare = lbl.isCompare;
              const isHovered = lbl.isHovered;
              const badgeColor = isSelected ? '#E10600' : isCompare ? '#00D2BE' : (drv.team_color || '#787A8E');

              const halfW = lbl.width / 2;
              const halfH = lbl.height / 2;

              return (
                <g
                  key={`label-${drv.driver_id}`}
                  transform={`translate(${lbl.labelX}, ${lbl.labelY})`}
                  onClick={() => onSelectDriver && onSelectDriver(drv.driver_id)}
                  onMouseEnter={() => setHoveredDriver(drv)}
                  onMouseLeave={() => setHoveredDriver(null)}
                  style={{ cursor: 'pointer' }}
                  className={`driver-map-label ${isSelected ? 'selected' : isCompare ? 'compare' : 'standard'} ${isHovered ? 'hovered' : ''}`}
                >
                  {isSelected ? (
                    /* Detailed High-Priority Selected Driver Card */
                    <g className="selected-driver-card">
                      {/* Background card with glassmorphic dark container & team border */}
                      <rect
                        x={-halfW}
                        y={-halfH}
                        width={lbl.width}
                        height={lbl.height}
                        rx="4"
                        fill="#0A0B14"
                        fillOpacity="0.95"
                        stroke="#E10600"
                        strokeWidth={scales.refLineWidth * 1.8}
                      />
                      {/* Left team accent bar */}
                      <rect
                        x={-halfW}
                        y={-halfH}
                        width={scales.refLineWidth * 3.5}
                        height={lbl.height}
                        rx="2"
                        fill={drv.team_color || '#E10600'}
                      />
                      {/* Top row: Code + Position */}
                      <text
                        x={-halfW + scales.refLineWidth * 6}
                        y={-halfH + scales.cornerFontSize * 1.1}
                        fill="#FFFFFF"
                        fontSize={scales.cornerFontSize * 1.1}
                        fontWeight="900"
                        dominantBaseline="central"
                      >
                        {drv.driver_id}
                      </text>
                      <text
                        x={halfW - scales.refLineWidth * 4}
                        y={-halfH + scales.cornerFontSize * 1.1}
                        fill="#FFB800"
                        fontSize={scales.cornerFontSize * 0.95}
                        fontWeight="800"
                        textAnchor="end"
                        dominantBaseline="central"
                      >
                        P{drv.position}
                      </text>
                      {/* Bottom row: Compound + Tyre Debt */}
                      <text
                        x={-halfW + scales.refLineWidth * 6}
                        y={halfH - scales.cornerFontSize * 0.9}
                        fill="#A0A5BD"
                        fontSize={scales.cornerFontSize * 0.75}
                        fontWeight="700"
                        dominantBaseline="central"
                      >
                        {drv.compound || 'HARD'}
                      </text>
                      <text
                        x={halfW - scales.refLineWidth * 4}
                        y={halfH - scales.cornerFontSize * 0.9}
                        fill={drv.cumulative_debt > 0 ? '#E10600' : '#00D2BE'}
                        fontSize={scales.cornerFontSize * 0.75}
                        fontWeight="800"
                        textAnchor="end"
                        dominantBaseline="central"
                      >
                        {drv.cumulative_debt > 0 ? `+${drv.cumulative_debt.toFixed(1)}s` : `${(drv.cumulative_debt || 0).toFixed(1)}s`}
                      </text>
                    </g>
                  ) : (
                    /* Sleek Compact Driver Pill */
                    <g className="compact-driver-pill">
                      <rect
                        x={-halfW}
                        y={-halfH}
                        width={lbl.width}
                        height={lbl.height}
                        rx="3"
                        fill="#0B0C15"
                        fillOpacity="0.92"
                        stroke={badgeColor}
                        strokeWidth={isCompare ? scales.refLineWidth * 1.5 : scales.refLineWidth * 1.1}
                      />
                      {/* Left team dot indicator */}
                      <circle
                        cx={-halfW + scales.cornerFontSize * 0.7}
                        cy={0}
                        r={scales.cornerFontSize * 0.35}
                        fill={drv.team_color || '#8E92A4'}
                      />
                      {/* Driver abbreviation code */}
                      <text
                        x={-halfW + scales.cornerFontSize * 1.3}
                        y={0}
                        fill="#FFFFFF"
                        fontSize={scales.cornerFontSize * 0.9}
                        fontWeight="800"
                        dominantBaseline="central"
                      >
                        {drv.driver_id}
                      </text>
                      {/* Position badge (visible at zoom or on compare) */}
                      {(zoomLevel > 1.2 || isCompare || drv.position <= 3) && (
                        <text
                          x={halfW - scales.cornerFontSize * 0.5}
                          y={0}
                          fill={drv.position === 1 ? '#FFB800' : '#8E91A8'}
                          fontSize={scales.cornerFontSize * 0.75}
                          fontWeight="700"
                          textAnchor="end"
                          dominantBaseline="central"
                        >
                          P{drv.position}
                        </text>
                      )}
                    </g>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* 4. HOVERED DRIVER DETAILED CARD */}
        {hoveredDriver && (
          <div className="driver-map-tooltip">
            <div className="map-tooltip-portrait-wrap" style={{ borderColor: hoveredDriver.team_color }}>
              <img
                src={hoveredDriver.profile_image}
                alt={`${hoveredDriver.full_name} portrait`}
                className="map-tooltip-portrait-img"
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = "/drivers/fallback_driver.webp";
                }}
              />
            </div>
            <div className="map-tooltip-info">
              <div className="map-tooltip-header-row">
                <strong className="map-tooltip-code">{hoveredDriver.driver_id}</strong>
                <span className="map-tooltip-name">{hoveredDriver.full_name}</span>
                <span className="map-tooltip-pos">P{hoveredDriver.position}</span>
              </div>
              <div className="map-tooltip-stats-row">
                <span>Speed: <strong>{Math.round(hoveredDriver.speed)} km/h</strong></span>
                <span>Tyre: <strong>{hoveredDriver.compound} ({hoveredDriver.tyre_age}L)</strong></span>
                <span>Debt: <strong className={hoveredDriver.cumulative_debt > 0 ? 'debt-pos' : 'credit-pos'}>
                  {hoveredDriver.cumulative_debt > 0 ? `+${hoveredDriver.cumulative_debt.toFixed(2)}s` : `${hoveredDriver.cumulative_debt.toFixed(2)}s`}
                </strong></span>
              </div>
            </div>
          </div>
        )}

        {/* 4b. HOVERED PIT STOP DETAILED CARD */}
        {hoveredPitStop && (
          <div className="pit-stop-map-tooltip">
            <div className="pit-tooltip-header" style={{ borderLeftColor: hoveredPitStop.team_color }}>
              <div className="pit-tooltip-title-row">
                <span className="pit-tooltip-driver" style={{ color: hoveredPitStop.team_color }}>
                  {hoveredPitStop.driver_id}
                </span>
                <span className="pit-tooltip-badge">PIT STOP #{hoveredPitStop.stop_number}</span>
                <span className="pit-tooltip-lap">LAP {hoveredPitStop.lap}</span>
              </div>
              <span className="pit-tooltip-team">{hoveredPitStop.team}</span>
            </div>

            <div className="pit-tooltip-body">
              <div className="pit-tooltip-stat">
                <span className="stat-lbl">Stop Duration:</span>
                <strong className="stat-val highlight">{hoveredPitStop.duration} s</strong>
              </div>
              {hoveredPitStop.lane_duration && (
                <div className="pit-tooltip-stat">
                  <span className="stat-lbl">Lane Transit:</span>
                  <strong className="stat-val">{hoveredPitStop.lane_duration} s</strong>
                </div>
              )}
              <div className="pit-tooltip-stat">
                <span className="stat-lbl">Compound Change:</span>
                <strong className="stat-val tyre-trans">
                  {hoveredPitStop.compound_before} → {hoveredPitStop.compound_after}
                </strong>
              </div>
              <div className="pit-tooltip-stat">
                <span className="stat-lbl">Tyre Life:</span>
                <strong className="stat-val">
                  Age {hoveredPitStop.tyre_age_before}L → {hoveredPitStop.tyre_age_after}L
                </strong>
              </div>
              {hoveredPitStop.position_before !== null && hoveredPitStop.position_after !== null && (
                <div className="pit-tooltip-stat position-stat">
                  <span className="stat-lbl">POSITION CHANGE ACROSS PIT STOP:</span>
                  <strong className="stat-val">
                    P{hoveredPitStop.position_before} → P{hoveredPitStop.position_after}
                    <span className={`pos-delta-tag ${hoveredPitStop.position_delta > 0 ? 'gained' : hoveredPitStop.position_delta < 0 ? 'lost' : 'even'}`}>
                      ({hoveredPitStop.position_delta > 0 ? `+${hoveredPitStop.position_delta}` : hoveredPitStop.position_delta})
                    </span>
                  </strong>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 5. HOVERED CORNER METRICS TOOLTIP */}
        {hoveredCorner && !hoveredDriver && (
          <div className="corner-tooltip">
            <div className="corner-tooltip-header">
              <span className="corner-tag">APEX</span>
              <strong>Turn {hoveredCorner.corner_number}{hoveredCorner.corner_letter || ''} {hoveredCorner.name ? `— ${hoveredCorner.name}` : ''}</strong>
            </div>
            <div className="corner-tooltip-body">
              <span>Apex Distance: <strong>{Math.round(hoveredCorner.distance || 0)}m</strong></span>
              <span>Speed: <strong>{Math.round(hoveredCorner.speed)} km/h</strong></span>
              <span>Throttle: <strong>{Math.round(hoveredCorner.throttle)}%</strong></span>
              <span>Brake: <strong>{hoveredCorner.brake ? 'ACTIVE' : 'OFF'}</strong></span>
            </div>
          </div>
        )}

        {/* 6. COCKPIT TELEMETRY STRIP */}
        {activeTelemetry && (
          <div className="map-cockpit-strip">
            <div className="cockpit-item">
              <span className="item-label">SPEED</span>
              <div className="item-value speed">{Math.round(activeTelemetry.speed)} <span className="unit">KM/H</span></div>
            </div>
            <div className="cockpit-item">
              <span className="item-label">GEAR</span>
              <div className="item-value gear">{activeTelemetry.gear}</div>
            </div>
            <div className="cockpit-item">
              <span className="item-label">THROTTLE</span>
              <div className="item-value throttle">{Math.round(activeTelemetry.throttle)}%</div>
            </div>
            <div className="cockpit-item">
              <span className="item-label">BRAKE</span>
              <div className={`item-value brake ${activeTelemetry.brake ? 'active' : ''}`}>
                {activeTelemetry.brake ? 'ON' : 'OFF'}
              </div>
            </div>
            <div className="cockpit-item">
              <span className="item-label">DRS</span>
              <div className={`item-value drs ${inDRSZone ? 'active' : ''}`}>
                {inDRSZone ? 'OPEN' : 'CLOSED'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

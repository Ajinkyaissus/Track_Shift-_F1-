/**
 * TrackShift High-Performance 2D Map Collision & Label Layout Engine
 *
 * Implements:
 * 1. Priority scoring for all session drivers
 * 2. Static track obstacle registration (Corners, DRS, Sectors, Pit Stops, Start/Finish)
 * 3. 8-directional candidate anchor search with radial expansion
 * 4. Cluster detection & staggered angular dispersion for tight sections (e.g. Monaco hairpin)
 * 5. Connector / leader lines pointing directly from displaced labels to exact car GPS coordinates
 * 6. Zoom-dependent label detail scaling
 */

/**
 * Check if two axis-aligned bounding boxes (AABBs) intersect
 */
export function checkAABBIntersection(boxA, boxB, margin = 2) {
  return (
    boxA.x - margin < boxB.x + boxB.width &&
    boxA.x + boxA.width + margin > boxB.x &&
    boxA.y - margin < boxB.y + boxB.height &&
    boxA.y + boxA.height + margin > boxB.y
  );
}

/**
 * Calculate dynamic priority score for a driver
 */
export function computeDriverPriority(drv, { selectedDriver, comparisonDriver, hoveredDriver, driverPositions = [] }) {
  const dId = drv.driver_id;
  if (dId === selectedDriver) return 100;
  if (hoveredDriver && dId === hoveredDriver.driver_id) return 95;
  if (dId === comparisonDriver) return 90;

  // Check proximity to selected driver
  if (selectedDriver) {
    const selCar = driverPositions.find(d => d.driver_id === selectedDriver);
    if (selCar) {
      const dist = Math.hypot(drv.x - selCar.x, drv.y - selCar.y);
      if (dist < 100) return 80;
    }
  }

  // Active pit event or special state
  if (drv.in_pit) return 75;

  // Race leader (P1)
  if (drv.position === 1) return 70;
  if (drv.position === 2) return 66;
  if (drv.position === 3) return 63;

  // Base score decreasing with field position
  const pos = drv.position || 20;
  return Math.max(20, 55 - pos * 1.2);
}

/**
 * Build obstacle bounding boxes from static circuit elements and pit markers
 */
export function buildTrackObstacles({ corners = [], drsZones = [], sectors = [], sfGate = null, pitStops = [], scales }) {
  const obstacles = [];
  const pad = scales.refLineWidth || 2;

  // 1. Corner badges (T1..TN)
  corners.forEach(c => {
    const r = (scales.cornerBadgeR || 10) + pad;
    obstacles.push({
      id: `corner-${c.corner_number}`,
      type: 'corner',
      priority: 60,
      x: c.badgeX - r,
      y: c.badgeY - r,
      width: r * 2,
      height: r * 2
    });
  });

  // 2. DRS start/end badges
  drsZones.forEach((drs, idx) => {
    if (drs.startPt) {
      const bw = scales.asphaltWidth * 1.4;
      const bh = scales.cornerFontSize * 1.8;
      const bx = drs.startPt.x + drs.startPt.nx * (scales.asphaltWidth * 0.85);
      const by = drs.startPt.y + drs.startPt.ny * (scales.asphaltWidth * 0.85);
      obstacles.push({
        id: `drs-${idx}`,
        type: 'drs',
        priority: 45,
        x: bx - bw / 2,
        y: by - bh / 2,
        width: bw,
        height: bh
      });
    }
  });

  // 3. Sector badges (S1..S3)
  sectors.forEach(sec => {
    if (sec.boundaryGate) {
      const g = sec.boundaryGate;
      const bw = scales.asphaltWidth * 1.2;
      const bh = scales.cornerFontSize * 1.8;
      const bx = g.x + g.nx * (scales.asphaltWidth * 0.9);
      const by = g.y + g.ny * (scales.asphaltWidth * 0.9);
      obstacles.push({
        id: `sector-${sec.id}`,
        type: 'sector',
        priority: 40,
        x: bx - bw / 2,
        y: by - bh / 2,
        width: bw,
        height: bh
      });
    }
  });

  // 4. Start/Finish gate
  if (sfGate) {
    const bw = scales.asphaltWidth * 2.2;
    const bh = scales.cornerFontSize * 1.8;
    const bx = sfGate.x + sfGate.nx * (scales.asphaltWidth * 1.1);
    const by = sfGate.y + sfGate.ny * (scales.asphaltWidth * 1.1);
    obstacles.push({
      id: 'sfGate',
      type: 'sfGate',
      priority: 50,
      x: bx - bw / 2,
      y: by - bh / 2,
      width: bw,
      height: bh
    });
  }

  // 5. Mapped Pit Stop markers
  pitStops.forEach(ps => {
    const r = (scales.carRadius || 8) * 1.5;
    obstacles.push({
      id: ps.key,
      type: 'pitStop',
      priority: ps.isActiveInReplay ? 85 : 55,
      x: ps.x - r,
      y: ps.y - r,
      width: r * 2,
      height: r * 2
    });
  });

  return obstacles;
}

/**
 * 8 candidate directional vectors for anchor placement
 */
const ANCHOR_DIRECTIONS = [
  { name: 'TOP', dx: 0, dy: -1, cost: 1.0 },
  { name: 'TOP_RIGHT', dx: 0.707, dy: -0.707, cost: 1.15 },
  { name: 'RIGHT', dx: 1, dy: 0, cost: 1.2 },
  { name: 'BOTTOM_RIGHT', dx: 0.707, dy: 0.707, cost: 1.3 },
  { name: 'BOTTOM', dx: 0, dy: 1, cost: 1.25 },
  { name: 'BOTTOM_LEFT', dx: -0.707, dy: 0.707, cost: 1.35 },
  { name: 'LEFT', dx: -1, dy: 0, cost: 1.2 },
  { name: 'TOP_LEFT', dx: -0.707, dy: -0.707, cost: 1.15 },
];

/**
 * Compute intelligent non-overlapping layout for driver labels
 */
export function computeDriverLabelLayout({
  driverPositions = [],
  obstacles = [],
  selectedDriver = null,
  comparisonDriver = null,
  hoveredDriver = null,
  labelMode = 'auto', // 'auto' | 'all' | 'selected' | 'none'
  _carDisplayMode = 'all', // 'all' | 'selected' | 'none'
  zoomLevel = 1.0,
  scales
}) {
  if (labelMode === 'none' || !driverPositions.length) {
    return { labels: [], clusters: [] };
  }

  const placedBoxes = [...obstacles];
  const results = [];

  // Sort drivers by priority score (descending)
  const scoredDrivers = driverPositions.map(drv => {
    const priority = computeDriverPriority(drv, {
      selectedDriver,
      comparisonDriver,
      hoveredDriver,
      driverPositions
    });
    const isSelected = drv.driver_id === selectedDriver;
    const isCompare = drv.driver_id === comparisonDriver;
    const isHovered = hoveredDriver && drv.driver_id === hoveredDriver.driver_id;

    return {
      drv,
      priority,
      isSelected,
      isCompare,
      isHovered
    };
  }).sort((a, b) => b.priority - a.priority);

  // Determine standard label dimensions
  const baseFontSize = scales.cornerFontSize || 8;
  const baseAsphalt = scales.asphaltWidth || 20;

  // Selected driver card dimensions (prominent)
  const selectedCardWidth = Math.max(68, baseAsphalt * 2.6);
  const selectedCardHeight = Math.max(30, baseFontSize * 3.4);

  // Compact abbreviation badge dimensions
  const compactWidth = Math.max(34, baseAsphalt * 1.5);
  const compactHeight = Math.max(16, baseFontSize * 1.85);

  const baseDistance = Math.max(22, baseAsphalt * 1.1);
  const distanceMultipliers = [1.0, 1.6, 2.3, 3.1, 4.0];

  // Cluster threshold: cars closer than this in screen space belong to a dense pack
  const clusterDistThreshold = Math.max(30, baseAsphalt * 1.3);

  // Identify clusters
  const clusters = [];
  const visited = new Set();

  for (let i = 0; i < driverPositions.length; i++) {
    const d1 = driverPositions[i];
    if (visited.has(d1.driver_id)) continue;

    const clusterGroup = [d1];
    visited.add(d1.driver_id);

    for (let j = i + 1; j < driverPositions.length; j++) {
      const d2 = driverPositions[j];
      if (visited.has(d2.driver_id)) continue;
      const d = Math.hypot(d1.x - d2.x, d1.y - d2.y);
      if (d < clusterDistThreshold) {
        clusterGroup.push(d2);
        visited.add(d2.driver_id);
      }
    }

    if (clusterGroup.length >= 3) {
      const cx = clusterGroup.reduce((sum, d) => sum + d.x, 0) / clusterGroup.length;
      const cy = clusterGroup.reduce((sum, d) => sum + d.y, 0) / clusterGroup.length;
      clusters.push({
        id: `cluster-${i}`,
        drivers: clusterGroup,
        centroid: { x: cx, y: cy },
        count: clusterGroup.length
      });
    }
  }

  // Iterate over scored drivers to find collision-free label placements
  for (const item of scoredDrivers) {
    const { drv, priority, isSelected, isCompare, isHovered } = item;

    // Visibility filter:
    // If labelMode is 'selected', only show selected & comparison
    if (labelMode === 'selected' && !isSelected && !isCompare) {
      continue;
    }

    // In 'auto' mode at standard zoom: if priority is low and cars are crowded, drop non-critical labels
    // But in 'all' mode: always position every label
    const isImportant = isSelected || isCompare || isHovered || priority >= 65 || zoomLevel > 1.4;
    if (labelMode === 'auto' && !isImportant && priority < 45) {
      continue;
    }

    const width = isSelected ? selectedCardWidth : compactWidth;
    const height = isSelected ? selectedCardHeight : compactHeight;

    let bestPlacement = null;
    let minCost = Infinity;

    // Check candidate positions across expanding distance rings
    for (const distMult of distanceMultipliers) {
      const dist = baseDistance * distMult;

      for (const dir of ANCHOR_DIRECTIONS) {
        // Label center target
        const targetX = drv.x + dir.dx * dist;
        const targetY = drv.y + dir.dy * dist;

        const candidateBox = {
          x: targetX - width / 2,
          y: targetY - height / 2,
          width,
          height
        };

        // Check collision against placed boxes
        let hasCollision = false;
        for (const placed of placedBoxes) {
          if (checkAABBIntersection(candidateBox, placed, 3)) {
            hasCollision = true;
            break;
          }
        }

        if (!hasCollision) {
          const cost = dist * dir.cost;
          if (cost < minCost) {
            minCost = cost;
            bestPlacement = {
              candidateBox,
              labelX: targetX,
              labelY: targetY,
              dirName: dir.name,
              distance: dist
            };
          }
        }
      }

      // If we found a valid candidate at this distance tier, we can stop expanding further
      if (bestPlacement) break;
    }

    // If no candidate was found and labelMode is 'all' or it is selected:
    // Force a fallback staggered slot with leader line so no driver is lost
    if (!bestPlacement && (labelMode === 'all' || isSelected || isCompare || isHovered)) {
      const fallbackAngle = (results.length * 37) * (Math.PI / 180);
      const fallbackDist = baseDistance * 3.6;
      const targetX = drv.x + Math.cos(fallbackAngle) * fallbackDist;
      const targetY = drv.y + Math.sin(fallbackAngle) * fallbackDist;

      bestPlacement = {
        candidateBox: {
          x: targetX - width / 2,
          y: targetY - height / 2,
          width,
          height
        },
        labelX: targetX,
        labelY: targetY,
        dirName: 'STAGGERED',
        distance: fallbackDist
      };
    }

    if (bestPlacement) {
      placedBoxes.push(bestPlacement.candidateBox);

      // Determine connector line endpoints
      const carX = drv.x;
      const carY = drv.y;
      const lx = bestPlacement.labelX;
      const ly = bestPlacement.labelY;

      // Displacement from car
      const displacement = Math.hypot(lx - carX, ly - carY);
      const needsLeader = displacement > (scales.carArrowLen || 14) * 0.9;

      // Compute anchor edge point on label box closest to car
      let anchorX = lx;
      let anchorY = ly;
      if (needsLeader) {
        const halfW = width / 2;
        const halfH = height / 2;
        const dx = carX - lx;
        const dy = carY - ly;

        if (Math.abs(dx) * halfH > Math.abs(dy) * halfW) {
          anchorX = dx > 0 ? lx + halfW : lx - halfW;
          anchorY = ly + (dy / Math.abs(dx)) * halfW;
        } else {
          anchorY = dy > 0 ? ly + halfH : ly - halfH;
          anchorX = lx + (dx / Math.abs(dy)) * halfH;
        }
      }

      results.push({
        driver_id: drv.driver_id,
        drv,
        priority,
        isSelected,
        isCompare,
        isHovered,
        box: bestPlacement.candidateBox,
        labelX: lx,
        labelY: ly,
        width,
        height,
        needsLeader,
        leader: {
          startX: anchorX,
          startY: anchorY,
          endX: carX,
          endY: carY
        }
      });
    }
  }

  return {
    labels: results,
    clusters
  };
}

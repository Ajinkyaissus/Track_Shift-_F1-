/**
 * TrackShift F1 Geographic Registry & 3D Spherical Coordinate Utilities
 * Real geographical coordinates for all 13 backend-verified Formula 1 circuits
 * and world continental polygon landmasses for the 3D globe visualization.
 */

export const F1_CIRCUIT_GEO = [
  {
    circuit_id: "monza",
    name: "Autodromo Nazionale Monza",
    country: "Italy",
    country_code: "IT",
    flag: "🇮🇹",
    location: "Monza",
    lat: 45.6156,
    lon: 9.2811,
    length_km: 5.793,
    turns: 11
  },
  {
    circuit_id: "spa",
    name: "Circuit de Spa-Francorchamps",
    country: "Belgium",
    country_code: "BE",
    flag: "🇧🇪",
    location: "Stavelot",
    lat: 50.4372,
    lon: 5.9714,
    length_km: 7.004,
    turns: 19
  },
  {
    circuit_id: "silverstone",
    name: "Silverstone Circuit",
    country: "United Kingdom",
    country_code: "GB",
    flag: "🇬🇧",
    location: "Silverstone",
    lat: 52.0786,
    lon: -1.0169,
    length_km: 5.891,
    turns: 18
  },
  {
    circuit_id: "monaco",
    name: "Circuit de Monaco",
    country: "Monaco",
    country_code: "MC",
    flag: "🇲🇨",
    location: "Monte Carlo",
    lat: 43.7347,
    lon: 7.4206,
    length_km: 3.337,
    turns: 19
  },
  {
    circuit_id: "hungaroring",
    name: "Hungaroring",
    country: "Hungary",
    country_code: "HU",
    flag: "🇭🇺",
    location: "Mogyoród",
    lat: 47.5789,
    lon: 19.2486,
    length_km: 4.381,
    turns: 14
  },
  {
    circuit_id: "bahrain",
    name: "Bahrain International Circuit",
    country: "Bahrain",
    country_code: "BH",
    flag: "🇧🇭",
    location: "Sakhir",
    lat: 26.0325,
    lon: 50.5106,
    length_km: 5.412,
    turns: 15
  },
  {
    circuit_id: "jeddah",
    name: "Jeddah Corniche Circuit",
    country: "Saudi Arabia",
    country_code: "SA",
    flag: "🇸🇦",
    location: "Jeddah",
    lat: 21.6319,
    lon: 39.1044,
    length_km: 6.174,
    turns: 27
  },
  {
    circuit_id: "abu_dhabi",
    name: "Yas Marina Circuit",
    country: "United Arab Emirates",
    country_code: "AE",
    flag: "🇦🇪",
    location: "Abu Dhabi",
    lat: 24.4672,
    lon: 54.6031,
    length_km: 5.281,
    turns: 16
  },
  {
    circuit_id: "cota",
    name: "Circuit of the Americas",
    country: "United States",
    country_code: "US",
    flag: "🇺🇸",
    location: "Austin, Texas",
    lat: 30.1328,
    lon: -97.6411,
    length_km: 5.513,
    turns: 20
  },
  {
    circuit_id: "interlagos",
    name: "Autódromo José Carlos Pace",
    country: "Brazil",
    country_code: "BR",
    flag: "🇧🇷",
    location: "São Paulo",
    lat: -23.7036,
    lon: -46.6997,
    length_km: 4.309,
    turns: 15
  },
  {
    circuit_id: "suzuka",
    name: "Suzuka International Racing Course",
    country: "Japan",
    country_code: "JP",
    flag: "🇯🇵",
    location: "Suzuka",
    lat: 34.8431,
    lon: 136.541,
    length_km: 5.807,
    turns: 18
  },
  {
    circuit_id: "singapore",
    name: "Marina Bay Street Circuit",
    country: "Singapore",
    country_code: "SG",
    flag: "🇸🇬",
    location: "Marina Bay",
    lat: 1.2914,
    lon: 103.864,
    length_km: 4.940,
    turns: 19
  },
  {
    circuit_id: "albert_park",
    name: "Albert Park Circuit",
    country: "Australia",
    country_code: "AU",
    flag: "🇦🇺",
    location: "Melbourne",
    lat: -37.8497,
    lon: 144.968,
    length_km: 5.278,
    turns: 14
  }
];

/**
 * World continental outlines defined as closed polygon rings in [lon, lat] degrees.
 * Covers North America, South America, Europe, Africa, Asia, Australia, UK, Japan, Scandinavia, etc.
 */
export const WORLD_CONTINENTS = [
  // North America
  [
    [-168, 66], [-160, 56], [-140, 60], [-130, 50], [-124, 40], [-117, 32], [-105, 20],
    [-97, 18], [-87, 14], [-80, 8], [-77, 8], [-80, 22], [-81, 25], [-80, 31],
    [-75, 35], [-70, 42], [-64, 46], [-55, 52], [-60, 60], [-80, 62], [-95, 70],
    [-120, 72], [-140, 70], [-160, 71], [-168, 66]
  ],
  // South America
  [
    [-77, 8], [-72, 11], [-60, 8], [-50, 0], [-35, -5], [-35, -10], [-38, -18],
    [-44, -23], [-50, -30], [-55, -40], [-65, -54], [-74, -52], [-73, -40],
    [-71, -30], [-76, -15], [-81, -5], [-77, 8]
  ],
  // Europe
  [
    [-9, 36], [-9, 43], [-1, 44], [-4, 48], [2, 51], [8, 54], [10, 58], [15, 56],
    [24, 60], [28, 70], [40, 68], [45, 60], [30, 46], [28, 41], [22, 38], [15, 38],
    [12, 44], [4, 43], [0, 40], [-5, 36], [-9, 36]
  ],
  // Scandinavia
  [
    [5, 58], [10, 58], [12, 56], [18, 59], [24, 66], [28, 71], [20, 70], [14, 65],
    [8, 62], [5, 58]
  ],
  // Great Britain & Ireland
  [
    [-5, 50], [-1, 50], [1, 52], [0, 54], [-2, 57], [-4, 58], [-6, 56], [-4, 53],
    [-5, 51], [-5, 50]
  ],
  [
    [-10, 51], [-6, 52], [-6, 55], [-9, 55], [-10, 51]
  ],
  // Africa
  [
    [-5, 36], [10, 37], [25, 32], [32, 31], [35, 27], [43, 12], [51, 11], [45, 0],
    [40, -10], [35, -25], [28, -33], [18, -34], [12, -20], [8, -5], [2, 5],
    [-15, 12], [-17, 15], [-13, 28], [-5, 36]
  ],
  // Middle East & Arabian Peninsula
  [
    [32, 31], [36, 35], [44, 37], [50, 30], [56, 26], [60, 22], [54, 16], [45, 12],
    [43, 13], [35, 27], [32, 31]
  ],
  // Asia & Eurasia
  [
    [40, 68], [60, 70], [80, 73], [110, 74], [140, 72], [170, 66], [180, 60],
    [160, 52], [140, 48], [130, 40], [120, 32], [118, 22], [108, 18], [105, 10],
    [100, 2], [104, 1], [98, 8], [92, 22], [80, 16], [78, 8], [72, 20], [68, 24],
    [60, 25], [50, 30], [45, 40], [40, 50], [40, 68]
  ],
  // Japan (Honshu / Hokkaido)
  [
    [130, 33], [133, 34], [136, 35], [140, 36], [142, 40], [144, 44], [141, 45],
    [140, 41], [138, 38], [135, 35], [131, 34], [130, 33]
  ],
  // Australia
  [
    [114, -22], [122, -16], [136, -12], [142, -10], [146, -18], [153, -28],
    [150, -36], [144, -38], [138, -35], [130, -32], [116, -34], [114, -22]
  ],
  // Italy (Detailed Boot)
  [
    [8, 45], [12, 46], [13, 45], [12, 44], [15, 42], [18, 40], [16, 39],
    [16, 38], [15, 40], [14, 41], [12, 43], [10, 44], [8, 45]
  ]
];

/**
 * 3D Spherical Trigonometry & Matrix Math
 */

/**
 * Converts Latitude & Longitude (degrees) to 3D Cartesian coordinates on a sphere of given radius.
 * lat: [-90, 90], lon: [-180, 180]
 */
export function latLonToVector3(lat, lon, radius = 1) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);

  const x = -radius * Math.sin(phi) * Math.cos(theta);
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);

  return { x, y, z };
}

/**
 * Rotates a 3D point around X and Y axes (Euler angles in radians)
 */
export function rotateVector3(point, rotX, rotY) {
  // Rotate around Y axis (yaw / longitude)
  const cosY = Math.cos(rotY);
  const sinY = Math.sin(rotY);
  const x1 = point.x * cosY + point.z * sinY;
  const z1 = -point.x * sinY + point.z * cosY;
  const y1 = point.y;

  // Rotate around X axis (pitch / latitude)
  const cosX = Math.cos(rotX);
  const sinX = Math.sin(rotX);
  const y2 = y1 * cosX - z1 * sinX;
  const z2 = y1 * sinX + z1 * cosX;
  const x2 = x1;

  return { x: x2, y: y2, z: z2 };
}

/**
 * Projects a rotated 3D point to 2D Canvas screen space.
 * Returns { screenX, screenY, visible, scale, depth }
 */
export function projectVector3ToScreen(point, centerX, centerY, sphereRadius) {
  // Orthographic projection with subtle depth shading
  const screenX = centerX + point.x * sphereRadius;
  const screenY = centerY - point.y * sphereRadius;
  // Visible if z > -0.05 (front facing hemisphere)
  const visible = point.z > -0.05;
  const depth = point.z; // -1 to 1

  return {
    screenX,
    screenY,
    visible,
    depth
  };
}

/**
 * Calculates camera target rotation angles (rotX, rotY) to center a specific (lat, lon) on the screen.
 */
export function calculateCameraTarget(lat, lon) {
  // Target pitch: rotate around X to bring latitude to center (Y=0, Z=1)
  const targetRotX = (lat * Math.PI) / 180;
  // Target yaw: rotate around Y to bring longitude to center facing +Z
  const targetRotY = -((lon * Math.PI) / 180) - Math.PI / 2;

  return {
    rotX: targetRotX,
    rotY: targetRotY
  };
}

/**
 * Cubic ease-in-out easing function for smooth cinematic camera fly-to animations
 */
export function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

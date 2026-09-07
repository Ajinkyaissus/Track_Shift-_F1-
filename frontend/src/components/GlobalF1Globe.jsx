import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as THREE from 'three';
import { useCircuit } from '../context/CircuitContext';
import { CountryFlag, getCountryName } from '../utils/countryFlags';

const CIRCUIT_SPECS = {
  monza: { length: "5.793 km", turns: 11, drsZones: 2, firstGp: "1950", grandPrix: "Italian Grand Prix", date: "Sep 2024" },
  spa: { length: "7.004 km", turns: 19, drsZones: 2, firstGp: "1950", grandPrix: "Belgian Grand Prix", date: "Jul 2024" },
  silverstone: { length: "5.891 km", turns: 18, drsZones: 2, firstGp: "1950", grandPrix: "British Grand Prix", date: "Jul 2024" },
  monaco: { length: "3.337 km", turns: 19, drsZones: 1, firstGp: "1950", grandPrix: "Monaco Grand Prix", date: "May 2024" },
  hungaroring: { length: "4.381 km", turns: 14, drsZones: 2, firstGp: "1986", grandPrix: "Hungarian Grand Prix", date: "Jul 2024" },
  bahrain: { length: "5.412 km", turns: 15, drsZones: 3, firstGp: "2004", grandPrix: "Bahrain Grand Prix", date: "Mar 2024" },
  jeddah: { length: "6.174 km", turns: 27, drsZones: 3, firstGp: "2021", grandPrix: "Saudi Arabian Grand Prix", date: "Mar 2024" },
  abu_dhabi: { length: "5.281 km", turns: 16, drsZones: 2, firstGp: "2009", grandPrix: "Abu Dhabi Grand Prix", date: "Dec 2024" },
  cota: { length: "5.513 km", turns: 20, drsZones: 2, firstGp: "2012", grandPrix: "United States Grand Prix", date: "Oct 2024" },
  interlagos: { length: "4.309 km", turns: 15, drsZones: 2, firstGp: "1973", grandPrix: "São Paulo Grand Prix", date: "Nov 2024" },
  suzuka: { length: "5.807 km", turns: 18, drsZones: 1, firstGp: "1987", grandPrix: "Japanese Grand Prix", date: "Apr 2024" },
  singapore: { length: "4.940 km", turns: 19, drsZones: 4, firstGp: "2008", grandPrix: "Singapore Grand Prix", date: "Sep 2024" },
  albert_park: { length: "5.278 km", turns: 14, drsZones: 4, firstGp: "1996", grandPrix: "Australian Grand Prix", date: "Mar 2024" }
};

// Earth Radius in 3D Units
const EARTH_RADIUS = 2.0;
const CLOUD_RADIUS = EARTH_RADIUS * 1.008;
const MARKER_RADIUS = EARTH_RADIUS * 1.012;

// Convert Geo (Lat, Lon) to 3D Cartesian coordinates on sphere
function latLonToVector3(lat, lon, radius = MARKER_RADIUS) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  const x = -radius * Math.sin(phi) * Math.cos(theta);
  const y = radius * Math.cos(phi);
  const z = radius * Math.sin(phi) * Math.sin(theta);
  return new THREE.Vector3(x, y, z);
}

// Cubic easing for cinematic camera movement
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// Create a subtle high-resolution procedural cloud texture canvas
function createProceduralCloudTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = 'rgba(0,0,0,0)';
  ctx.fillRect(0, 0, 1024, 512);

  // Cloud bands
  for (let i = 0; i < 180; i++) {
    const x = Math.random() * 1024;
    const y = 80 + Math.random() * 352;
    const radius = 30 + Math.random() * 90;
    const opacity = 0.05 + Math.random() * 0.16;

    const grad = ctx.createRadialGradient(x, y, 0, x, y, radius);
    grad.addColorStop(0, `rgba(255, 255, 255, ${opacity})`);
    grad.addColorStop(0.6, `rgba(240, 245, 255, ${opacity * 0.5})`);
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  return texture;
}

export default function GlobalF1Globe({ onSelectCircuit }) {
  const containerRef = useRef(null);
  const { circuits } = useCircuit();
  
  const [selectedCircuit, setSelectedCircuit] = useState(null);
  const [hoveredCircuit, setHoveredCircuit] = useState(null);
  const [mouseScreenPos, setMouseScreenPos] = useState({ x: 0, y: 0 });
  const [isTransitioning, setIsTransitioning] = useState(false);

  // References for Three.js state
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const earthGroupRef = useRef(null);
  const cloudsMeshRef = useRef(null);
  const markersGroupRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const flyToAnimIdRef = useRef(null);
  
  const isDraggingRef = useRef(false);
  const dragStartPosRef = useRef({ x: 0, y: 0 });
  const previousMousePositionRef = useRef({ x: 0, y: 0 });
  const cameraDistanceRef = useRef(5.1);
  const targetCameraDistanceRef = useRef(5.1);
  const earthRotationRef = useRef({ x: 0.22, y: -0.5 });
  const targetEarthRotationRef = useRef({ x: 0.22, y: -0.5 });
  const markerMeshesRef = useRef([]);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseVecRef = useRef(new THREE.Vector2());

  // Check prefers-reduced-motion
  const prefersReducedMotion = useMemo(() => {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }, []);

  // Initialize Three.js WebGL Scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // 1. Scene Setup
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // 2. Camera Setup
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, cameraDistanceRef.current);
    cameraRef.current = camera;

    // 3. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ 
      antialias: true, 
      alpha: true, 
      powerPreference: 'high-performance' 
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 4. Lights: Sun (Directional Light) + Ambient Deep Space Light
    const sunLight = new THREE.DirectionalLight(0xffffff, 2.3);
    sunLight.position.set(6, 3, 5);
    scene.add(sunLight);

    const ambientLight = new THREE.AmbientLight(0x0e1424, 0.42);
    scene.add(ambientLight);

    // 5. Starfield Background
    const starGeometry = new THREE.BufferGeometry();
    const starCount = 1500;
    const starPositions = new Float32Array(starCount * 3);
    const starColors = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount; i++) {
      const radius = 65 + Math.random() * 45;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      starPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      starPositions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      starPositions[i * 3 + 2] = radius * Math.cos(phi);

      const brightness = 0.45 + Math.random() * 0.55;
      starColors[i * 3] = brightness * 0.88;
      starColors[i * 3 + 1] = brightness * 0.94;
      starColors[i * 3 + 2] = brightness;
    }

    starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    starGeometry.setAttribute('color', new THREE.BufferAttribute(starColors, 3));
    const starMaterial = new THREE.PointsMaterial({
      size: 0.85,
      vertexColors: true,
      transparent: true,
      opacity: 0.8
    });
    const starField = new THREE.Points(starGeometry, starMaterial);
    scene.add(starField);

    // 6. Earth Group
    const earthGroup = new THREE.Group();
    earthGroup.rotation.x = earthRotationRef.current.x;
    earthGroup.rotation.y = earthRotationRef.current.y;
    scene.add(earthGroup);
    earthGroupRef.current = earthGroup;

    // 7. Load Textures
    const textureLoader = new THREE.TextureLoader();
    const dayTexture = textureLoader.load('/textures/earth-day.jpg');
    const nightTexture = textureLoader.load('/textures/earth-night.jpg');
    const waterTexture = textureLoader.load('/textures/earth-water.png');
    const bumpTexture = textureLoader.load('/textures/earth-topology.png');

    dayTexture.colorSpace = THREE.SRGBColorSpace;
    nightTexture.colorSpace = THREE.SRGBColorSpace;

    // Custom Photorealistic Day/Night Earth Shader Material
    const earthMaterial = new THREE.ShaderMaterial({
      uniforms: {
        dayTexture: { value: dayTexture },
        nightTexture: { value: nightTexture },
        waterTexture: { value: waterTexture },
        bumpTexture: { value: bumpTexture },
        sunPosition: { value: sunLight.position }
      },
      vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec3 vSunDirection;
        uniform vec3 sunPosition;

        void main() {
          vUv = uv;
          vec4 worldPos = modelMatrix * vec4(position, 1.0);
          vPosition = worldPos.xyz;
          vNormal = normalize(mat3(modelMatrix) * normal);
          vSunDirection = normalize(sunPosition - worldPos.xyz);
          gl_Position = projectionMatrix * viewMatrix * worldPos;
        }
      `,
      fragmentShader: `
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec3 vSunDirection;
        uniform sampler2D dayTexture;
        uniform sampler2D nightTexture;
        uniform sampler2D waterTexture;
        uniform sampler2D bumpTexture;

        void main() {
          vec3 norm = normalize(vNormal);
          vec3 sunDir = normalize(vSunDirection);
          vec3 viewDir = normalize(cameraPosition - vPosition);
          
          float diffuse = dot(norm, sunDir);
          
          vec4 dayColor = texture2D(dayTexture, vUv);
          vec4 nightColor = texture2D(nightTexture, vUv);
          vec4 waterColor = texture2D(waterTexture, vUv);
          
          // Day/night terminator threshold
          float dayFactor = smoothstep(-0.12, 0.22, diffuse);
          
          // Specular highlights on oceans
          vec3 halfVector = normalize(sunDir + viewDir);
          float specular = pow(max(dot(norm, halfVector), 0.0), 32.0) * (1.0 - waterColor.r) * 0.44 * dayFactor;
          
          // Composite Day and Night with warm city light glow
          vec3 baseDay = dayColor.rgb * max(diffuse, 0.04) + vec3(specular);
          vec3 baseNight = nightColor.rgb * 1.75;
          vec3 finalColor = mix(baseNight, baseDay, dayFactor);
          
          // Subtle atmospheric rim Fresnel
          float fresnel = pow(1.0 - max(dot(norm, viewDir), 0.0), 3.2);
          vec3 atmosphereGlow = vec3(0.18, 0.45, 0.85) * fresnel * 0.55 * max(dayFactor, 0.25);
          
          gl_FragColor = vec4(finalColor + atmosphereGlow, 1.0);
        }
      `
    });

    const earthGeometry = new THREE.SphereGeometry(EARTH_RADIUS, 64, 64);
    const earthMesh = new THREE.Mesh(earthGeometry, earthMaterial);
    earthGroup.add(earthMesh);

    // 8. Separate Clouds Sphere Layer (Radius R * 1.008)
    const cloudsTexture = createProceduralCloudTexture();
    const cloudsMaterial = new THREE.MeshStandardMaterial({
      map: cloudsTexture,
      transparent: true,
      opacity: 0.28,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const cloudsGeometry = new THREE.SphereGeometry(CLOUD_RADIUS, 64, 64);
    const cloudsMesh = new THREE.Mesh(cloudsGeometry, cloudsMaterial);
    earthGroup.add(cloudsMesh);
    cloudsMeshRef.current = cloudsMesh;

    // 9. Outer Atmospheric Blue Glow Layer
    const atmosphereGeometry = new THREE.SphereGeometry(EARTH_RADIUS * 1.035, 64, 64);
    const atmosphereMaterial = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vPosition;
        void main() {
          vNormal = normalize(mat3(modelMatrix) * normal);
          vec4 worldPos = modelMatrix * vec4(position, 1.0);
          vPosition = worldPos.xyz;
          gl_Position = projectionMatrix * viewMatrix * worldPos;
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        varying vec3 vPosition;
        void main() {
          vec3 norm = normalize(vNormal);
          vec3 viewDir = normalize(cameraPosition - vPosition);
          float fresnel = pow(1.0 - max(dot(norm, viewDir), 0.0), 4.2);
          gl_FragColor = vec4(0.22, 0.58, 1.0, fresnel * 0.72);
        }
      `,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      transparent: true
    });
    const atmosphereMesh = new THREE.Mesh(atmosphereGeometry, atmosphereMaterial);
    earthGroup.add(atmosphereMesh);

    // 10. Markers Group
    const markersGroup = new THREE.Group();
    earthGroup.add(markersGroup);
    markersGroupRef.current = markersGroup;

    // 11. Animation Loop
    let lastTime = performance.now();
    const animate = () => {
      const now = performance.now();
      const _delta = (now - lastTime) / 1000;
      lastTime = now;

      // Inertial damping of Earth rotation
      if (!isDraggingRef.current) {
        earthRotationRef.current.x += (targetEarthRotationRef.current.x - earthRotationRef.current.x) * 0.12;
        earthRotationRef.current.y += (targetEarthRotationRef.current.y - earthRotationRef.current.y) * 0.12;
        
        // Idle slow rotation if not interacting and motion allowed
        if (!prefersReducedMotion && !selectedCircuit && !flyToAnimIdRef.current) {
          targetEarthRotationRef.current.y += 0.0012;
        }
      }

      // Safeguard against NaN
      if (!isNaN(earthRotationRef.current.x) && !isNaN(earthRotationRef.current.y)) {
        earthGroup.rotation.x = earthRotationRef.current.x;
        earthGroup.rotation.y = earthRotationRef.current.y;
      }

      // Slow independent cloud drift
      if (cloudsMeshRef.current && !prefersReducedMotion) {
        cloudsMeshRef.current.rotation.y += 0.0003;
      }

      // Smooth zoom distance damping
      if (!isNaN(targetCameraDistanceRef.current)) {
        cameraDistanceRef.current += (targetCameraDistanceRef.current - cameraDistanceRef.current) * 0.1;
        camera.position.z = cameraDistanceRef.current;
      }

      // Animate pulsing beacon markers
      const pulseTime = now * 0.003;
      markerMeshesRef.current.forEach(item => {
        if (item.pulseRing) {
          const s = 1.0 + 0.35 * Math.sin(pulseTime + item.pulseOffset);
          item.pulseRing.scale.set(s, s, s);
        }
        if (item.beam) {
          const b = 0.75 + 0.25 * Math.sin(pulseTime * 1.5 + item.pulseOffset);
          item.beam.material.opacity = b;
        }
      });

      renderer.render(scene, camera);
      animFrameIdRef.current = requestAnimationFrame(animate);
    };

    animFrameIdRef.current = requestAnimationFrame(animate);

    // Resize Handler
    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w > 0 && h > 0) {
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      if (flyToAnimIdRef.current) cancelAnimationFrame(flyToAnimIdRef.current);
      renderer.dispose();
      earthGeometry.dispose();
      earthMaterial.dispose();
      cloudsGeometry.dispose();
      cloudsMaterial.dispose();
      cloudsTexture.dispose();
      atmosphereGeometry.dispose();
      atmosphereMaterial.dispose();
      starGeometry.dispose();
      starMaterial.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [prefersReducedMotion]);

  // Generate 3D Circuit Markers on Earth Surface with Flag Billboards
  useEffect(() => {
    const markersGroup = markersGroupRef.current;
    if (!markersGroup || !circuits.length) return;

    // Clear previous markers
    while (markersGroup.children.length > 0) {
      const child = markersGroup.children[0];
      markersGroup.remove(child);
    }
    markerMeshesRef.current = [];

    circuits.forEach((circuit, index) => {
      const { lat, lon, track_id } = circuit;
      if (typeof lat !== 'number' || typeof lon !== 'number') return;

      const pos = latLonToVector3(lat, lon, MARKER_RADIUS);
      const normal = pos.clone().normalize();

      const markerNode = new THREE.Group();
      markerNode.position.copy(pos);
      markerNode.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);

      // 1. Core Glowing Sphere Pin
      const coreGeo = new THREE.SphereGeometry(0.024, 16, 16);
      const coreMat = new THREE.MeshBasicMaterial({ color: 0xff1e28 });
      const coreMesh = new THREE.Mesh(coreGeo, coreMat);
      coreMesh.position.y = 0.02;
      markerNode.add(coreMesh);

      // 2. Base Ground Pulse Ring
      const ringGeo = new THREE.RingGeometry(0.022, 0.042, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xff3b30,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.85
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.rotation.x = Math.PI / 2;
      markerNode.add(ringMesh);

      // 3. Vertical 3D Light Pillar Beam
      const beamHeight = 0.16;
      const beamGeo = new THREE.CylinderGeometry(0.003, 0.009, beamHeight, 12);
      const beamMat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.85
      });
      const beamMesh = new THREE.Mesh(beamGeo, beamMat);
      beamMesh.position.y = beamHeight / 2;
      markerNode.add(beamMesh);

      // 4. Invisible Interactive Raycast Hit Sphere
      const hitGeo = new THREE.SphereGeometry(0.08, 12, 12);
      const hitMat = new THREE.MeshBasicMaterial({ visible: false });
      const hitMesh = new THREE.Mesh(hitGeo, hitMat);
      hitMesh.userData = { circuit };
      markerNode.add(hitMesh);

      markersGroup.add(markerNode);

      markerMeshesRef.current.push({
        track_id,
        circuit,
        hitMesh,
        pulseRing: ringMesh,
        beam: beamMesh,
        core: coreMesh,
        pulseOffset: index * 0.4
      });
    });
  }, [circuits]);

  // Raycasting for Mouse Hover & Click
  const handlePointerMove = useCallback((e) => {
    const container = containerRef.current;
    if (!container || !cameraRef.current || isDraggingRef.current) return;

    const rect = container.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    setMouseScreenPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });

    mouseVecRef.current.set(x, y);
    raycasterRef.current.setFromCamera(mouseVecRef.current, cameraRef.current);

    const hitObjects = markerMeshesRef.current.map(m => m.hitMesh);
    const intersects = raycasterRef.current.intersectObjects(hitObjects, true);

    if (intersects.length > 0) {
      const circuit = intersects[0].object.userData.circuit;
      setHoveredCircuit(circuit);
      container.style.cursor = 'pointer';
    } else {
      setHoveredCircuit(null);
      container.style.cursor = isDraggingRef.current ? 'grabbing' : 'grab';
    }
  }, []);

  // Mouse Drag / Touch Rotation & Click Handling with Pointer Capture
  const handlePointerDown = (e) => {
    // If a fly-to animation was active, cancel it smoothly so user has full control
    if (flyToAnimIdRef.current) {
      cancelAnimationFrame(flyToAnimIdRef.current);
      flyToAnimIdRef.current = null;
      setIsTransitioning(false);
    }

    isDraggingRef.current = true;
    dragStartPosRef.current = { x: e.clientX, y: e.clientY };
    previousMousePositionRef.current = { x: e.clientX, y: e.clientY };

    if (e.currentTarget && e.currentTarget.setPointerCapture) {
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        // Ignore fallback
      }
    }

    if (containerRef.current) containerRef.current.style.cursor = 'grabbing';
  };

  const handlePointerUp = (e) => {
    const wasDraggingDist = Math.hypot(
      e.clientX - dragStartPosRef.current.x,
      e.clientY - dragStartPosRef.current.y
    );
    isDraggingRef.current = false;

    if (e.currentTarget && e.currentTarget.releasePointerCapture) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // Ignore fallback
      }
    }

    if (containerRef.current) containerRef.current.style.cursor = 'grab';

    // If mouse didn't drag significantly (< 6px), treat as Click
    if (wasDraggingDist < 6) {
      const container = containerRef.current;
      if (!container || !cameraRef.current) return;

      const rect = container.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      mouseVecRef.current.set(x, y);
      raycasterRef.current.setFromCamera(mouseVecRef.current, cameraRef.current);

      const hitObjects = markerMeshesRef.current.map(m => m.hitMesh);
      const intersects = raycasterRef.current.intersectObjects(hitObjects, true);

      if (intersects.length > 0) {
        const clickedCircuit = intersects[0].object.userData.circuit;
        triggerFlyToCircuit(clickedCircuit);
      }
    }
  };

  const handlePointerCancel = () => {
    isDraggingRef.current = false;
    if (containerRef.current) containerRef.current.style.cursor = 'grab';
  };

  const handlePointerDrag = (e) => {
    if (!isDraggingRef.current) {
      handlePointerMove(e);
      return;
    }

    const deltaX = e.clientX - previousMousePositionRef.current.x;
    const deltaY = e.clientY - previousMousePositionRef.current.y;

    previousMousePositionRef.current = { x: e.clientX, y: e.clientY };

    targetEarthRotationRef.current.y += deltaX * 0.005;
    targetEarthRotationRef.current.x += deltaY * 0.005;

    // Clamp pitch
    targetEarthRotationRef.current.x = Math.max(-1.1, Math.min(1.1, targetEarthRotationRef.current.x));
  };

  const handleWheel = (e) => {
    e.preventDefault();
    targetCameraDistanceRef.current += e.deltaY * 0.0035;
    targetCameraDistanceRef.current = Math.max(2.8, Math.min(6.8, targetCameraDistanceRef.current));
  };

  // Cinematic Camera Fly-To Interpolation
  const triggerFlyToCircuit = (circuit) => {
    if (!circuit) return;
    setSelectedCircuit(circuit);

    // Cancel any ongoing fly-to
    if (flyToAnimIdRef.current) {
      cancelAnimationFrame(flyToAnimIdRef.current);
      flyToAnimIdRef.current = null;
    }

    const { lat, lon } = circuit;
    const startRotX = earthRotationRef.current.x;
    const startRotY = earthRotationRef.current.y;
    const startDist = cameraDistanceRef.current;

    // Calculate target Euler angles so the circuit faces camera (+Z)
    const targetRotX = (lat * Math.PI) / 180;
    const targetRotY = -((lon + 180) * Math.PI) / 180;
    const targetDist = 3.3;

    // Handle 2PI rotation shortest path
    let diffY = (targetRotY - startRotY) % (Math.PI * 2);
    if (diffY < -Math.PI) diffY += Math.PI * 2;
    if (diffY > Math.PI) diffY -= Math.PI * 2;
    const endRotY = startRotY + diffY;

    setIsTransitioning(true);
    const duration = prefersReducedMotion ? 300 : 1100;
    const startTime = performance.now();

    const animateFlyTo = (time) => {
      const elapsed = time - startTime;
      const progress = Math.min(1, elapsed / duration);
      const eased = easeInOutCubic(progress);

      earthRotationRef.current.x = startRotX + (targetRotX - startRotX) * eased;
      earthRotationRef.current.y = startRotY + (endRotY - startRotY) * eased;
      targetEarthRotationRef.current.x = earthRotationRef.current.x;
      targetEarthRotationRef.current.y = earthRotationRef.current.y;

      cameraDistanceRef.current = startDist + (targetDist - startDist) * eased;
      targetCameraDistanceRef.current = cameraDistanceRef.current;

      if (progress < 1) {
        flyToAnimIdRef.current = requestAnimationFrame(animateFlyTo);
      } else {
        flyToAnimIdRef.current = null;
        setIsTransitioning(false);
      }
    };

    flyToAnimIdRef.current = requestAnimationFrame(animateFlyTo);
  };

  // Enter Selected Circuit
  const handleEnterCircuit = () => {
    if (!selectedCircuit) return;
    setIsTransitioning(true);
    targetCameraDistanceRef.current = 2.4;

    setTimeout(() => {
      onSelectCircuit(selectedCircuit.track_id);
    }, 450);
  };

  // Reset Globe View
  const handleResetGlobe = () => {
    if (flyToAnimIdRef.current) {
      cancelAnimationFrame(flyToAnimIdRef.current);
      flyToAnimIdRef.current = null;
    }
    setIsTransitioning(false);
    setSelectedCircuit(null);
    targetEarthRotationRef.current = { x: 0.22, y: -0.5 };
    targetCameraDistanceRef.current = 5.1;
  };

  const specs = selectedCircuit ? (CIRCUIT_SPECS[selectedCircuit.track_id] || {}) : {};
  const countryName = selectedCircuit ? (selectedCircuit.country || getCountryName(selectedCircuit.country_code)) : '';

  return (
    <div className="globe-explorer-container">
      {/* Top Header Hierarchy */}
      <div className="globe-overlay-top">
        <div className="globe-brand-block">
          <div className="globe-pill-badge">
            <span className="pulse-red-dot"></span>
            <span>2024 SEASON • 13 CIRCUITS • REAL FASTF1 DATA</span>
          </div>
          <h1 className="globe-main-title">TRACKSHIFT /</h1>
          <p className="globe-sub-title">
            REAL F1 TELEMETRY • GLOBAL CIRCUIT EXPLORER • TYRE DEGRADATION INTELLIGENCE
          </p>
        </div>

        <div className="globe-top-controls">
          <button 
            className="globe-ctrl-btn secondary"
            onClick={handleResetGlobe}
            title="Reset Globe Orientation"
          >
            🔄 Reset Earth View
          </button>
        </div>
      </div>

      {/* 3D WebGL Canvas Viewport with Touch & Pointer Capturing */}
      <div 
        ref={containerRef}
        className="globe-canvas-viewport"
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
        onPointerMove={handlePointerDrag}
        onWheel={handleWheel}
      />

      {/* Hover Marker Tooltip with Country Flag */}
      {hoveredCircuit && !selectedCircuit && (
        <div 
          className="globe-hover-tooltip"
          style={{
            left: `${mouseScreenPos.x + 16}px`,
            top: `${mouseScreenPos.y - 32}px`
          }}
        >
          <CountryFlag code={hoveredCircuit.country_code} size="md" />
          <div className="tooltip-info">
            <div className="tooltip-name">{hoveredCircuit.name}</div>
            <div className="tooltip-country">{hoveredCircuit.country || getCountryName(hoveredCircuit.country_code)}</div>
            <div className="tooltip-meta">
              {CIRCUIT_SPECS[hoveredCircuit.track_id]?.length || '5.4 km'} • {CIRCUIT_SPECS[hoveredCircuit.track_id]?.turns || 16} Corners
            </div>
          </div>
        </div>
      )}

      {/* Selected Circuit Right Glassmorphic Panel with Flag */}
      {selectedCircuit && (
        <div className={`globe-selected-panel ${isTransitioning ? 'transitioning' : ''}`}>
          <div className="panel-header">
            <div className="panel-flag-row">
              <CountryFlag code={selectedCircuit.country_code} size="lg" />
              <div className="panel-country-col">
                <span className="panel-country-title">{countryName.toUpperCase()}</span>
                <span className="panel-gp-title">{specs.grandPrix || 'FIA Formula 1 World Championship'}</span>
              </div>
              <button className="panel-close-btn" onClick={() => setSelectedCircuit(null)}>✕</button>
            </div>
            <h2 className="panel-circuit-name">{selectedCircuit.name}</h2>
          </div>

          <div className="panel-body">
            <div className="panel-specs-grid">
              <div className="panel-spec-box">
                <span className="spec-label">Country</span>
                <span className="spec-val">{countryName}</span>
              </div>
              <div className="panel-spec-box">
                <span className="spec-label">First Grand Prix</span>
                <span className="spec-val">{specs.firstGp || '1950'}</span>
              </div>
              <div className="panel-spec-box">
                <span className="spec-label">Circuit Length</span>
                <span className="spec-val">{specs.length || '5.3 km'}</span>
              </div>
              <div className="panel-spec-box">
                <span className="spec-label">Corners</span>
                <span className="spec-val">{specs.turns || 15} Turns</span>
              </div>
              <div className="panel-spec-box">
                <span className="spec-label">DRS Zones</span>
                <span className="spec-val">{specs.drsZones || 2} Zones</span>
              </div>
              <div className="panel-spec-box">
                <span className="spec-label">Telemetry Status</span>
                <span className="spec-val status-ok">Available</span>
              </div>
            </div>

            <div className="panel-features-list">
              <div className="feature-item">
                <span className="feature-icon">📡</span>
                <span>FastF1 GPS Telemetry Synchronized</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">🧠</span>
                <span>Stage 3 TCN Behavioral Analysis</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">📈</span>
                <span>Stage 4 Observational Sensitivity</span>
              </div>
            </div>

            <button 
              className="enter-circuit-action-btn"
              onClick={handleEnterCircuit}
              disabled={isTransitioning}
            >
              <span>{isTransitioning ? "LOCKING ONTO CIRCUIT..." : `EXPLORE ${selectedCircuit.name.toUpperCase()}`}</span>
              <span className="btn-arrow">→</span>
            </button>
          </div>
        </div>
      )}

      {/* Bottom Global Statistics Bar */}
      <div className="globe-bottom-stats-bar">
        <div className="stat-col">
          <span className="stat-number">13</span>
          <span className="stat-label">Verified Circuits</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-col">
          <span className="stat-number">1,021</span>
          <span className="stat-label">Laps in Dataset</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-col">
          <span className="stat-number">REAL GPS</span>
          <span className="stat-label">Track Geometry</span>
        </div>
        <div className="stat-divider" />
        <div className="stat-col">
          <span className="stat-number">TYRE INTELLIGENCE</span>
          <span className="stat-label">Degradation Analysis</span>
        </div>
      </div>
    </div>
  );
}

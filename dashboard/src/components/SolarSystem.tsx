import { useMemo, useRef, useEffect, useCallback, Suspense } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { OrbitControls, Line, Html, useTexture } from '@react-three/drei';
import * as THREE from 'three';
import { useStore } from '../store/store';
import type { CameraPreset } from '../store/store';
import { allPlanetPositionsAtDate, interpolateDate } from '../lib/orbits';

const AU = 1.496e8;

function toScene(pos: [number, number, number]): [number, number, number] {
  return [pos[0] / AU, pos[2] / AU, -pos[1] / AU];
}

const PLANET_CONFIG: Record<string, {
  color: string; size: number; orbitColor: string;
  texture?: string; atmosphere?: string; ring?: boolean;
}> = {
  mercury: { color: '#b0a090', size: 0.02,  orbitColor: '#6a6058', texture: '/textures/mercury.jpg' },
  venus:   { color: '#e8c870', size: 0.035, orbitColor: '#6a6048', texture: '/textures/venus.jpg' },
  earth:   { color: '#4499dd', size: 0.035, orbitColor: '#3a5a80', texture: '/textures/earth_daymap.jpg', atmosphere: '#4488ff' },
  mars:    { color: '#cc6644', size: 0.025, orbitColor: '#6a3a20', texture: '/textures/mars.jpg' },
  jupiter: { color: '#d4a060', size: 0.08,  orbitColor: '#5a5038', texture: '/textures/jupiter.jpg' },
  saturn:  { color: '#e8d090', size: 0.065, orbitColor: '#5a5038', texture: '/textures/saturn.jpg', ring: true },
  uranus:  { color: '#88ccdd', size: 0.04,  orbitColor: '#2a4848', texture: '/textures/uranus.jpg' },
  neptune: { color: '#4466cc', size: 0.04,  orbitColor: '#2a3058', texture: '/textures/neptune.jpg' },
};

const CAMERA_PRESETS: Record<CameraPreset, { pos: [number, number, number]; target: [number, number, number] }> = {
  'default': { pos: [0, 4, 6], target: [0, 0, 0] },
  'top-down': { pos: [0, 10, 0.01], target: [0, 0, 0] },
  'inner-system': { pos: [0, 2.5, 3], target: [0, 0, 0] },
  'outer-system': { pos: [0, 12, 18], target: [0, 0, 0] },
};

function SunBody() {
  const texture = useTexture('/textures/sun.jpg');
  return (
    <group>
      {/* Core */}
      <mesh>
        <sphereGeometry args={[0.08, 48, 48]} />
        <meshBasicMaterial map={texture} />
      </mesh>
      {/* Inner glow */}
      <mesh>
        <sphereGeometry args={[0.11, 32, 32]} />
        <meshBasicMaterial color="#ffcc44" transparent opacity={0.15} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* Outer corona */}
      <mesh>
        <sphereGeometry args={[0.18, 32, 32]} />
        <meshBasicMaterial color="#ff8800" transparent opacity={0.04} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <pointLight color="#ffeedd" intensity={2.0} decay={0} />
    </group>
  );
}

function TexturedPlanet({ name, position }: { name: string; position: [number, number, number] }) {
  const config = PLANET_CONFIG[name] || { color: '#888', size: 0.035 };
  const scaledPos = toScene(position);
  const meshRef = useRef<THREE.Mesh>(null);

  // Slow rotation
  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.y += delta * 0.1;
  });

  const texture = config.texture ? useTexture(config.texture) : null;

  return (
    <group position={scaledPos}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[config.size, 32, 32]} />
        {texture ? (
          <meshPhongMaterial map={texture} shininess={4} />
        ) : (
          <meshBasicMaterial color={config.color} />
        )}
      </mesh>
      {/* Atmosphere glow */}
      {config.atmosphere && (
        <mesh>
          <sphereGeometry args={[config.size * 1.15, 32, 32]} />
          <meshBasicMaterial
            color={config.atmosphere}
            transparent opacity={0.06}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            side={THREE.BackSide}
          />
        </mesh>
      )}
      {/* Saturn ring */}
      {config.ring && <SaturnRing size={config.size} />}
      {/* Label */}
      <Html distanceFactor={6} style={{ pointerEvents: 'none' }}>
        <div style={{
          color: '#7888a0', fontSize: '9px', fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase', letterSpacing: '1px', whiteSpace: 'nowrap',
          transform: 'translateY(-16px)', textAlign: 'center',
          textShadow: '0 0 8px rgba(6,10,18,1)',
        }}>
          {name}
        </div>
      </Html>
    </group>
  );
}

function SaturnRing({ size }: { size: number }) {
  const ringTex = useTexture('/textures/saturn_ring.png');
  return (
    <mesh rotation={[-Math.PI / 2.3, 0, 0]}>
      <ringGeometry args={[size * 1.4, size * 2.2, 64]} />
      <meshBasicMaterial
        map={ringTex}
        transparent
        opacity={0.7}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

function OrbitPath({ positions, color }: { positions: [number, number, number][]; color: string }) {
  const points = useMemo(() => positions.map(p => new THREE.Vector3(...toScene(p))), [positions]);
  if (points.length < 2) return null;
  return <Line points={points} color={color} lineWidth={1} transparent opacity={0.45} />;
}

function FlybyMarker({ position, body, isLaunch, isArrival }: {
  position: THREE.Vector3; body: string; isLaunch: boolean; isArrival: boolean;
}) {
  const color = isLaunch ? '#33ddc4' : isArrival ? '#e8a838' :
    PLANET_CONFIG[body.toLowerCase()]?.color || '#888888';

  return (
    <group position={position}>
      {/* Core dot */}
      <mesh>
        <sphereGeometry args={[0.014, 12, 12]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {/* Ring indicator for flybys */}
      {!isLaunch && !isArrival && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.025, 0.035, 24]} />
          <meshBasicMaterial color={color} transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      )}
      {/* Glow */}
      <mesh>
        <sphereGeometry args={[0.04, 12, 12]} />
        <meshBasicMaterial color={color} transparent opacity={0.06} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

function TransferArc({ positions, progress, events }: {
  positions: [number, number, number][];
  progress: number;
  events?: any[];
}) {
  const allPoints = useMemo(() => positions.map(p => new THREE.Vector3(...toScene(p))), [positions]);

  const cutIdx = Math.max(1, Math.floor(progress * (allPoints.length - 1)));
  const traversed = allPoints.slice(0, cutIdx + 1);
  const remaining = allPoints.slice(cutIdx);

  const t = progress * (allPoints.length - 1);
  const i = Math.floor(t);
  const frac = t - i;
  const scPos = i < allPoints.length - 1
    ? new THREE.Vector3().lerpVectors(allPoints[i], allPoints[i + 1], frac)
    : allPoints[allPoints.length - 1];

  // Compute flyby marker positions from events (reference missions)
  const flybyMarkers = useMemo(() => {
    if (!events || events.length < 2) return [];
    return events.map((ev, idx) => {
      // Position: use heliocentric_position_km if available, else estimate from trajectory
      let pos: THREE.Vector3;
      if (ev.heliocentric_position_km) {
        pos = new THREE.Vector3(...toScene(ev.heliocentric_position_km));
      } else {
        // Estimate position along trajectory
        const frac = idx / (events.length - 1);
        const ptIdx = Math.round(frac * (allPoints.length - 1));
        pos = allPoints[ptIdx] || allPoints[0];
      }
      return {
        pos,
        body: ev.body as string,
        isLaunch: ev.type === 'launch',
        isArrival: ev.type === 'arrival',
      };
    });
  }, [events, allPoints]);

  return (
    <group>
      {/* Full arc dim */}
      <Line points={allPoints} color="#22b8a0" lineWidth={1} transparent opacity={0.06} />
      {/* Traversed */}
      {traversed.length >= 2 && <Line points={traversed} color="#33ddc4" lineWidth={2} />}
      {/* Remaining */}
      {remaining.length >= 2 && <Line points={remaining} color="#22b8a0" lineWidth={1} transparent opacity={0.2} />}

      {/* Flyby markers (from reference missions) */}
      {flybyMarkers.map((m, idx) => (
        <FlybyMarker key={idx} position={m.pos} body={m.body} isLaunch={m.isLaunch} isArrival={m.isArrival} />
      ))}

      {/* Fallback departure/arrival markers (for regular transfers without events) */}
      {!events && (
        <>
          <mesh position={allPoints[0]}>
            <sphereGeometry args={[0.012, 12, 12]} />
            <meshBasicMaterial color="#33ddc4" />
          </mesh>
          <mesh position={allPoints[allPoints.length - 1]}>
            <sphereGeometry args={[0.012, 12, 12]} />
            <meshBasicMaterial color="#e8a838" />
          </mesh>
        </>
      )}

      {/* Spacecraft */}
      <mesh position={scPos}>
        <sphereGeometry args={[0.018, 12, 12]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>
      <mesh position={scPos}>
        <sphereGeometry args={[0.035, 12, 12]} />
        <meshBasicMaterial color="#00f0ff" transparent opacity={0.08} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

function AnimationDriver() {
  const { animationPlaying, animationProgress, transfer, setAnimationProgress, setAnimationPlaying } = useStore();
  useFrame((_, delta) => {
    if (!animationPlaying) return;
    // Estimate mission duration to scale playback speed
    let tofDays = transfer?.tof_days || 0;
    if (tofDays <= 0 && transfer?.departure_utc && transfer?.arrival_utc) {
      const dep = new Date(transfer.departure_utc).getTime();
      const arr = new Date(transfer.arrival_utc).getTime();
      tofDays = Math.max(1, (arr - dep) / 86400000);
    }
    // Scale: short transfers (~300d) play in ~15s, long missions (~4000d+) play in ~30s
    const targetSeconds = tofDays > 2000 ? 30 : tofDays > 500 ? 20 : 15;
    const speed = 1 / targetSeconds;
    const p = animationProgress + delta * speed;
    if (p >= 1) { setAnimationProgress(1); setAnimationPlaying(false); }
    else { setAnimationProgress(p); }
  });
  return null;
}

function Starfield() {
  const pointsRef = useRef<THREE.Points>(null);

  const geometry = useMemo(() => {
    const count = 4000;
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 50 + Math.random() * 50;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return geo;
  }, []);

  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d')!;
    const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0, 'rgba(255,255,255,1)');
    gradient.addColorStop(0.2, 'rgba(220,225,240,0.6)');
    gradient.addColorStop(0.5, 'rgba(180,190,220,0.15)');
    gradient.addColorStop(1, 'rgba(180,190,220,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(canvas);
  }, []);

  const material = useMemo(() => {
    return new THREE.PointsMaterial({
      map: texture,
      size: 0.6,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.88,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      color: new THREE.Color('#c8d0e8'),
    });
  }, [texture]);

  return <points ref={pointsRef} geometry={geometry} material={material} />;
}

function EclipticGrid() {
  const lines = useMemo(() => {
    const result: THREE.Vector3[][] = [];
    for (let r = 1; r <= 5; r++) {
      const pts: THREE.Vector3[] = [];
      for (let a = 0; a <= 64; a++) {
        const theta = (a / 64) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(theta) * r, 0, Math.sin(theta) * r));
      }
      result.push(pts);
    }
    return result;
  }, []);
  return (
    <group>
      {lines.map((pts, i) => (
        <Line key={i} points={pts} color="#0e1628" lineWidth={0.5} transparent opacity={0.4} />
      ))}
    </group>
  );
}

function CameraController() {
  const { camera } = useThree();
  const { cameraTarget, cameraPreset, planets, setCameraTarget, setCameraPreset } = useStore();
  const controlsRef = useRef<any>(null);

  useEffect(() => {
    if (!cameraPreset) return;
    const preset = CAMERA_PRESETS[cameraPreset];
    if (!preset) return;
    camera.position.set(...preset.pos);
    if (controlsRef.current) {
      controlsRef.current.target.set(...preset.target);
      controlsRef.current.update();
    }
    setCameraPreset(null);
  }, [cameraPreset, camera, setCameraPreset]);

  useEffect(() => {
    if (!cameraTarget || planets.length === 0) return;
    const planet = planets.find(p => p.name === cameraTarget);
    if (!planet) return;
    const pos = toScene(planet.position);
    camera.position.set(pos[0] + 0.5, pos[1] + 0.7, pos[2] + 0.5);
    if (controlsRef.current) {
      controlsRef.current.target.set(pos[0], pos[1], pos[2]);
      controlsRef.current.update();
    }
    setCameraTarget(null);
  }, [cameraTarget, planets, camera, setCameraTarget]);

  return (
    <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.05} minDistance={0.2} maxDistance={40} rotateSpeed={0.5} />
  );
}

function Scene() {
  const { planets, orbits, transfer, animationProgress, referenceMission } = useStore();

  // Compute animated planet positions when a transfer is active
  // During animation, interpolate the current date and compute positions client-side
  const animatedPlanets = useMemo(() => {
    if (!transfer || !transfer.departure_utc || !transfer.arrival_utc || animationProgress <= 0) {
      return planets;
    }
    const depDate = transfer.departure_utc.slice(0, 10);
    const arrDate = transfer.arrival_utc.slice(0, 10);
    if (!depDate || !arrDate || depDate === arrDate) return planets;

    const currentDate = interpolateDate(depDate, arrDate, animationProgress);
    const animPositions = allPlanetPositionsAtDate(currentDate);

    return planets.map(p => {
      const animPos = animPositions[p.name];
      if (animPos) {
        return { ...p, position: animPos as [number, number, number] };
      }
      return p;
    });
  }, [planets, transfer, animationProgress]);

  return (
    <>
      <ambientLight color="#080812" intensity={0.1} />

      <Starfield />

      <Suspense fallback={null}>
        <SunBody />
        {animatedPlanets.map((p) => (
          <TexturedPlanet key={p.name} name={p.name} position={p.position} />
        ))}
      </Suspense>

      <EclipticGrid />

      {Array.from(orbits.entries()).map(([body, orbit]) => (
        <OrbitPath key={body} positions={orbit.positions} color={PLANET_CONFIG[body]?.orbitColor || '#181e2e'} />
      ))}

      {transfer?.trajectory_positions && (
        <TransferArc
          positions={transfer.trajectory_positions}
          progress={animationProgress}
          events={referenceMission?.events}
        />
      )}

      <AnimationDriver />
      <CameraController />
    </>
  );
}

// --- Camera + Animation Controls (HTML overlay) ---

function CameraControls() {
  const { setCameraPreset, setCameraTarget, transfer, animationPlaying, animationProgress,
          setAnimationPlaying, setAnimationProgress } = useStore();

  const presets: { key: CameraPreset; label: string }[] = [
    { key: 'default', label: 'Persp' },
    { key: 'top-down', label: 'Top' },
    { key: 'inner-system', label: 'Inner' },
    { key: 'outer-system', label: 'Outer' },
  ];
  const bodies = ['earth', 'mars', 'venus', 'jupiter', 'saturn'];

  const togglePlay = useCallback(() => {
    if (animationProgress >= 1) { setAnimationProgress(0); setAnimationPlaying(true); }
    else { setAnimationPlaying(!animationPlaying); }
  }, [animationPlaying, animationProgress, setAnimationPlaying, setAnimationProgress]);

  const overlayBtn: React.CSSProperties = {
    padding: '5px 12px', background: 'rgba(6,10,18,0.8)', border: '1px solid var(--panel-border)',
    borderRadius: '3px', color: 'var(--text-secondary)', fontSize: '10px', fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px', textTransform: 'uppercase', cursor: 'pointer', backdropFilter: 'blur(6px)',
  };

  return (
    <>
      {/* Camera presets — top left */}
      <div style={{ position: 'absolute', top: '10px', left: '10px', display: 'flex', gap: '4px', pointerEvents: 'auto' }}>
        {presets.map(({ key, label }) => (
          <button key={key} onClick={() => setCameraPreset(key)} style={overlayBtn}>{label}</button>
        ))}
      </div>
      {/* Planet focus — top right */}
      <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', gap: '4px', pointerEvents: 'auto' }}>
        {bodies.map(b => (
          <button key={b} onClick={() => setCameraTarget(b)} style={{
            ...overlayBtn, border: '1px solid rgba(255,255,255,0.06)',
            color: PLANET_CONFIG[b]?.color || '#888',
          }}>
            {b}
          </button>
        ))}
      </div>
      {transfer && (
        <div style={{
          position: 'absolute', bottom: '12px', left: '50%', transform: 'translateX(-50%)',
          display: 'flex', alignItems: 'center', gap: '8px', pointerEvents: 'auto',
          background: 'rgba(6,10,18,0.85)', border: '1px solid var(--panel-border)',
          borderRadius: '4px', padding: '6px 14px', backdropFilter: 'blur(8px)',
        }}>
          <button onClick={togglePlay} style={{
            width: '24px', height: '24px', background: 'none', border: '1px solid var(--cyan)',
            borderRadius: '3px', color: 'var(--cyan)', fontSize: '10px', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {animationPlaying ? '❚❚' : '▶'}
          </button>
          <input type="range" min="0" max="1" step="0.002" value={animationProgress}
            onChange={(e) => { setAnimationProgress(parseFloat(e.target.value)); setAnimationPlaying(false); }}
            style={{ width: '200px', accentColor: 'var(--cyan)' }}
          />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', minWidth: '80px' }}>
            {transfer?.departure_utc && transfer?.arrival_utc
              ? interpolateDate(transfer.departure_utc.slice(0, 10), transfer.arrival_utc.slice(0, 10), animationProgress)
              : `Day ${Math.round(animationProgress * (transfer?.tof_days || 0))}`}
          </span>
        </div>
      )}
    </>
  );
}

export function SolarSystem() {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas camera={{ position: [0, 4, 6], fov: 45, near: 0.001, far: 200 }} gl={{ antialias: true }}>
        <color attach="background" args={['#020408']} />
        <Scene />
      </Canvas>
      <CameraControls />
    </div>
  );
}

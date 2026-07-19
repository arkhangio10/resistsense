"use client";

import { Line, MeshDistortMaterial, OrbitControls, Trail } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import type { CSSProperties } from "react";
import * as THREE from "three";

export type SimulationOutcome =
  | "idle"
  | "probable_failure"
  | "probable_efficacy"
  | "no_call";

type BioSimulationProps = {
  antibiotic: string;
  confidence: number | null;
  outcome: SimulationOutcome;
};

const OUTCOME_COPY: Record<
  SimulationOutcome,
  { accent: string; detail: string; label: string }
> = {
  idle: {
    accent: "#7df8e8",
    label: "AWAITING GENOME",
    detail: "Upload an assembled E. coli genome to begin the evidence readout.",
  },
  probable_failure: {
    accent: "#ff6259",
    label: "PROBABLE RESISTANCE",
    detail: "The bacterium remains viable while the antibiotic signal is repelled.",
  },
  probable_efficacy: {
    accent: "#40e0c1",
    label: "PROBABLE SUSCEPTIBILITY",
    detail: "The antibiotic signal reaches the bacterium and viability collapses.",
  },
  no_call: {
    accent: "#f2ba55",
    label: "NO-CALL · INSUFFICIENT EVIDENCE",
    detail: "The system abstains, so no biological response is inferred.",
  },
};

const cycleProgress = (elapsed: number, outcome: SimulationOutcome) => {
  if (outcome === "no_call" || outcome === "idle") return 0;
  return Math.min(1, (elapsed % 8) / 6.4);
};

function GenomeHelix({ outcome }: { outcome: SimulationOutcome }) {
  const group = useRef<THREE.Group>(null);
  const points = useMemo(
    () =>
      Array.from({ length: 18 }, (_, index) => {
        const fraction = index / 17;
        return {
          angle: fraction * Math.PI * 5,
          y: (fraction - 0.5) * 2,
        };
      }),
    [],
  );

  useFrame((state) => {
    if (!group.current) return;
    const progress = cycleProgress(state.clock.getElapsedTime(), outcome);
    group.current.rotation.y = state.clock.getElapsedTime() * 0.55;
    const collapse =
      outcome === "probable_efficacy" ? Math.max(0, (progress - 0.56) / 0.44) : 0;
    group.current.scale.setScalar(1 - collapse * 0.5);
    group.current.rotation.z = collapse * 1.2;
  });

  return (
    <group ref={group}>
      {points.map((point, index) => {
        const x = Math.cos(point.angle) * 0.3;
        const z = Math.sin(point.angle) * 0.3;
        return (
          <group key={index} position={[0, point.y, 0]}>
            <mesh position={[x, 0, z]}>
              <sphereGeometry args={[0.07, 8, 8]} />
              <meshStandardMaterial color="#31d9ff" emissive="#087ea4" emissiveIntensity={1.4} />
            </mesh>
            <mesh position={[-x, 0, -z]}>
              <sphereGeometry args={[0.07, 8, 8]} />
              <meshStandardMaterial color="#ff66bc" emissive="#a60b63" emissiveIntensity={1.3} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function SurfacePili({ color }: { color: string }) {
  const pili = useMemo(
    () =>
      Array.from({ length: 24 }, (_, index) => {
        const angle = index * 2.39996;
        const y = -1.3 + ((index * 7) % 24) * (2.6 / 23);
        const direction = new THREE.Vector3(
          Math.cos(angle),
          Math.sin(index * 1.71) * 0.16,
          Math.sin(angle),
        ).normalize();
        const origin = new THREE.Vector3(
          Math.cos(angle) * 0.84,
          y,
          Math.sin(angle) * 0.84,
        );
        const length = 0.24 + ((index * 5) % 9) * 0.035;
        const midpoint = origin
          .clone()
          .add(direction.clone().multiplyScalar(length / 2));
        const quaternion = new THREE.Quaternion().setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          direction,
        );
        return { length, midpoint, quaternion };
      }),
    [],
  );

  return pili.map((pilus, index) => (
    <mesh
      key={index}
      position={pilus.midpoint}
      quaternion={pilus.quaternion}
    >
      <cylinderGeometry args={[0.012, 0.024, pilus.length, 6]} />
      <meshBasicMaterial color={color} transparent opacity={0.58} />
    </mesh>
  ));
}

function MembraneNodes({ color }: { color: string }) {
  const nodes = useMemo(
    () =>
      Array.from({ length: 28 }, (_, index) => {
        const angle = index * 2.39996;
        const y = -1.22 + ((index * 11) % 28) * (2.44 / 27);
        return new THREE.Vector3(
          Math.cos(angle) * 0.87,
          y,
          Math.sin(angle) * 0.87,
        );
      }),
    [],
  );

  return nodes.map((position, index) => (
    <mesh key={index} position={position}>
      <sphereGeometry args={[0.035, 7, 7]} />
      <meshBasicMaterial color={color} transparent opacity={0.7} />
    </mesh>
  ));
}

function Flagella({ color }: { color: string }) {
  const strands = useMemo(
    () =>
      Array.from({ length: 3 }, (_, strand) => {
        const side = strand === 2 ? -1 : 1;
        return Array.from({ length: 32 }, (_, index) => {
          const progress = index / 31;
          const wave = progress * Math.PI * (3.5 + strand * 0.45);
          return new THREE.Vector3(
            Math.sin(wave + strand * 1.4) * (0.12 + progress * 0.32),
            side * (1.48 + progress * (2.5 + strand * 0.18)),
            Math.cos(wave + strand) * (0.08 + progress * 0.2),
          );
        });
      }),
    [],
  );

  return strands.map((points, index) => (
    <Line
      key={index}
      points={points}
      color={color}
      lineWidth={0.72}
      transparent
      opacity={0.5 - index * 0.08}
    />
  ));
}

function Bacterium({ outcome }: { outcome: SimulationOutcome }) {
  const group = useRef<THREE.Group>(null);
  const shield = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!group.current || !shield.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const susceptible = outcome === "probable_efficacy";
    const resistant = outcome === "probable_failure";
    const collapse = susceptible ? Math.max(0, (progress - 0.58) / 0.42) : 0;

    group.current.rotation.z = Math.sin(elapsed * 0.35) * 0.13;
    group.current.rotation.x = Math.sin(elapsed * 0.23) * 0.08;
    group.current.position.y = Math.sin(elapsed * 0.8) * 0.12;
    group.current.position.x = collapse * Math.sin(elapsed * 36) * 0.08;
    group.current.scale.setScalar(THREE.MathUtils.lerp(1, 0.56, collapse));

    const shieldScale = resistant
      ? THREE.MathUtils.smoothstep(progress, 0.28, 0.62) * 2.15
      : 0.001;
    shield.current.scale.setScalar(Math.max(0.001, shieldScale));
    shield.current.rotation.y = elapsed * 0.6;
  });

  const resistant = outcome === "probable_failure";
  const idle = outcome === "idle";
  const neutral = outcome === "no_call" || idle;
  const bodyColor = resistant
    ? "#d7ff58"
    : idle
      ? "#7df8e8"
      : neutral
        ? "#e1a94b"
        : "#27c8ef";
  const bodyEmissive = resistant
    ? "#667c12"
    : idle
      ? "#075f62"
      : neutral
        ? "#74521c"
        : "#075f99";

  return (
    <group ref={group}>
      <mesh ref={shield} scale={0.001}>
        <sphereGeometry args={[1, 24, 24]} />
        <meshBasicMaterial color="#49ffc2" transparent opacity={0.12} wireframe />
      </mesh>
      <group rotation={[0, 0, Math.PI / 2]}>
        <mesh>
          <capsuleGeometry args={[0.88, 1.55, 20, 36]} />
          <MeshDistortMaterial
            color={bodyColor}
            emissive={bodyEmissive}
            emissiveIntensity={1.05}
            distort={resistant ? 0.1 : neutral ? 0.06 : 0.22}
            speed={resistant ? 1.2 : neutral ? 0.5 : 2.4}
            transparent
            opacity={0.42}
            roughness={0.18}
          />
        </mesh>
        <mesh scale={0.8}>
          <capsuleGeometry args={[0.88, 1.55, 14, 28]} />
          <meshStandardMaterial
            color={bodyColor}
            emissive={bodyEmissive}
            emissiveIntensity={0.8}
            transparent
            opacity={0.24}
          />
        </mesh>
        {[-0.58, 0, 0.58].map((position) => (
          <mesh key={position} position={[0, position, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.79, 0.015, 6, 42]} />
            <meshBasicMaterial color={bodyColor} transparent opacity={0.28} />
          </mesh>
        ))}
        <SurfacePili color={bodyColor} />
        <MembraneNodes color={bodyColor} />
        <Flagella color={bodyColor} />
        <GenomeHelix outcome={outcome} />
      </group>
    </group>
  );
}

type ParticleSeed = {
  direction: THREE.Vector3;
  distance: number;
  phase: number;
};

function DrugParticle({
  outcome,
  seed,
}: {
  outcome: SimulationOutcome;
  seed: ParticleSeed;
}) {
  const mesh = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!mesh.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const wave = Math.sin(elapsed * 1.4 + seed.phase) * 0.18;
    let radius = seed.distance;

    if (outcome === "probable_efficacy") {
      const approach = THREE.MathUtils.smoothstep(progress, 0.05, 0.82);
      radius = THREE.MathUtils.lerp(seed.distance, 0.18, approach);
    } else if (outcome === "probable_failure") {
      if (progress < 0.5) {
        radius = THREE.MathUtils.lerp(seed.distance, 2.2, progress / 0.5);
      } else {
        radius = THREE.MathUtils.lerp(2.2, seed.distance + 3, (progress - 0.5) / 0.5);
      }
    }

    mesh.current.position.copy(seed.direction).multiplyScalar(radius);
    mesh.current.position.y += wave;
    const visibleScale =
      outcome === "probable_efficacy" && progress > 0.88
        ? Math.max(0.08, 1 - (progress - 0.88) * 7)
        : 1;
    mesh.current.scale.setScalar(visibleScale);
  });

  return (
    <Trail width={0.28} length={2.3} color="#ffd477" attenuation={(value) => value * value}>
      <mesh ref={mesh} position={seed.direction.clone().multiplyScalar(seed.distance)}>
        <sphereGeometry args={[0.11, 12, 12]} />
        <meshStandardMaterial color="#fff2c0" emissive="#ffad33" emissiveIntensity={3.2} />
      </mesh>
    </Trail>
  );
}

function AntibioticSwarm({ outcome }: { outcome: SimulationOutcome }) {
  const seeds = useMemo(
    () =>
      Array.from({ length: 22 }, (_, index) => {
        const fraction = (index + 0.5) / 22;
        const polar = Math.acos(1 - 2 * fraction);
        const azimuth = Math.PI * (1 + Math.sqrt(5)) * index;
        const direction = new THREE.Vector3(
          Math.sin(polar) * Math.cos(azimuth),
          Math.cos(polar),
          Math.sin(polar) * Math.sin(azimuth),
        ).normalize();
        return {
          direction,
          distance: 4.2 + ((index * 7) % 22) * (3.2 / 21),
          phase: fraction * Math.PI * 2,
        };
      }),
    [],
  );

  return seeds.map((seed, index) => (
    <DrugParticle key={index} outcome={outcome} seed={seed} />
  ));
}

function Scene({ outcome }: { outcome: SimulationOutcome }) {
  return (
    <>
      <color attach="background" args={["#120609"]} />
      <fog attach="fog" args={["#18070b", 10, 25]} />
      <ambientLight intensity={0.55} color="#ff8181" />
      <pointLight position={[6, 7, 8]} intensity={18} color="#ff6b73" />
      <pointLight position={[-7, -4, 5]} intensity={14} color="#45e8ff" />
      <Bacterium outcome={outcome} />
      <AntibioticSwarm outcome={outcome} />
      <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.55} />
    </>
  );
}

const formatDrug = (name: string) =>
  name
    .split("/")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("/");

export default function BioSimulation({
  antibiotic,
  confidence,
  outcome,
}: BioSimulationProps) {
  const copy = OUTCOME_COPY[outcome];

  return (
    <div className="bio-simulation" style={{ "--simulation-accent": copy.accent } as CSSProperties}>
      <div className="simulation-overlay">
        <span>ILLUSTRATIVE RESPONSE</span>
        <h3>{formatDrug(antibiotic)}</h3>
        <strong>{copy.label}</strong>
        <p>{copy.detail}</p>
        <small>
          Calibrated confidence: {confidence === null ? "Unavailable" : `${Math.round(confidence * 100)}%`}
        </small>
      </div>
      <Canvas
        key={`${antibiotic}:${outcome}`}
        camera={{ position: [0, 0, 7.5], fov: 44 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
      >
        <Scene outcome={outcome} />
      </Canvas>
      <p className="simulation-caveat">
        Symbolic visualization of the model outcome, not a mechanism-of-action or treatment simulation.
      </p>
    </div>
  );
}

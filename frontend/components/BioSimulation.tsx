"use client";

import { Line, MeshDistortMaterial, OrbitControls, Trail } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
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

type MechanismKind =
  | "cell_wall"
  | "dna_replication"
  | "translation"
  | "folate"
  | "unknown";

type MechanismProfile = {
  kind: MechanismKind;
  target: string;
  susceptibleStages: [string, string, string];
  resistantStages: [string, string, string];
  susceptibleDetail: string;
  resistantDetail: string;
};

const MECHANISMS: Record<string, MechanismProfile> = {
  ampicillin: {
    kind: "cell_wall",
    target: "Peptidoglycan synthesis / PBPs",
    susceptibleStages: ["PBP engagement", "Localized bulging", "Envelope rupture"],
    resistantStages: ["Limited target effect", "Envelope maintained", "Growth preserved"],
    susceptibleDetail: "A mechanism-informed sequence of wall weakening, membrane bulging, and lysis.",
    resistantDetail: "The envelope remains intact while antibiotic engagement is shown as ineffective or diverted.",
  },
  cefotaxime: {
    kind: "cell_wall",
    target: "Peptidoglycan synthesis / PBP3",
    susceptibleStages: ["PBP engagement", "Filamentation + bulge", "Envelope rupture"],
    resistantStages: ["Limited target effect", "Division retained", "Envelope maintained"],
    susceptibleDetail: "A mechanism-informed sequence of filamentation, membrane bulging, and lysis.",
    resistantDetail: "The envelope remains intact while antibiotic engagement is shown as ineffective or diverted.",
  },
  ciprofloxacin: {
    kind: "dna_replication",
    target: "DNA gyrase / topoisomerase IV",
    susceptibleStages: ["Target engagement", "SOS filamentation", "DNA replication arrest"],
    resistantStages: ["Target effect limited", "Replication retained", "Cell structure maintained"],
    susceptibleDetail: "DNA stress is represented by nucleoid compaction and filamentation, not explosive lysis.",
    resistantDetail: "The nucleoid and cell structure remain stable while target engagement is shown as limited.",
  },
  gentamicin: {
    kind: "translation",
    target: "30S ribosome / 16S rRNA",
    susceptibleStages: ["Ribosome binding", "Mistranslation stress", "Membrane leakage"],
    resistantStages: ["Drug effect limited", "Translation retained", "Membrane maintained"],
    susceptibleDetail: "Ribosomal stress, mistranslation, and progressive membrane permeability are illustrated.",
    resistantDetail: "Ribosomal activity and membrane integrity remain visually preserved.",
  },
  "trimethoprim/sulfamethoxazole": {
    kind: "folate",
    target: "Sequential folate synthesis",
    susceptibleStages: ["DHPS + DHFR blockade", "Nucleotide depletion", "Growth arrest"],
    resistantStages: ["Folate bypass retained", "Metabolic flow continues", "Growth preserved"],
    susceptibleDetail: "Metabolic flow slows as folate-dependent nucleotide production is interrupted.",
    resistantDetail: "Folate-pathway flow remains visible to represent preserved metabolic function.",
  },
};

const UNKNOWN_MECHANISM: MechanismProfile = {
  kind: "unknown",
  target: "Antibiotic-specific cellular target",
  susceptibleStages: ["Target engagement", "Cellular stress", "Growth impaired"],
  resistantStages: ["Effect limited", "Core function retained", "Structure maintained"],
  susceptibleDetail: "A generalized mechanism-informed stress response is illustrated.",
  resistantDetail: "Cellular structure remains intact while antibiotic effect is shown as limited.",
};

const mechanismFor = (antibiotic: string) =>
  MECHANISMS[antibiotic.toLowerCase()] || UNKNOWN_MECHANISM;

const OUTCOME_COPY: Record<
  SimulationOutcome,
  { accent: string; label: string }
> = {
  idle: {
    accent: "#7df8e8",
    label: "AWAITING GENOME",
  },
  probable_failure: {
    accent: "#ff6259",
    label: "RESISTANCE-ASSOCIATED GENOMIC SIGNAL",
  },
  probable_efficacy: {
    accent: "#40e0c1",
    label: "SUSCEPTIBILITY-COMPATIBLE GENOMIC SIGNAL",
  },
  no_call: {
    accent: "#f2ba55",
    label: "NO-CALL · NO RESPONSE INFERRED",
  },
};

const cycleProgress = (elapsed: number, outcome: SimulationOutcome) => {
  if (outcome === "no_call" || outcome === "idle") return 0;
  return Math.min(1, (elapsed % 8) / 6.4);
};

function GenomeHelix({
  outcome,
  mechanism,
}: {
  outcome: SimulationOutcome;
  mechanism: MechanismKind;
}) {
  const group = useRef<THREE.Group>(null);
  const helix = useMemo(() => {
    const points = Array.from({ length: 22 }, (_, index) => {
      const fraction = index / 21;
      return {
        angle: fraction * Math.PI * 5,
        y: (fraction - 0.5) * 2.15,
      };
    });
    return {
      points,
      strandA: points.map(
        (point) =>
          new THREE.Vector3(
            Math.cos(point.angle) * 0.3,
            point.y,
            Math.sin(point.angle) * 0.3,
          ),
      ),
      strandB: points.map(
        (point) =>
          new THREE.Vector3(
            -Math.cos(point.angle) * 0.3,
            point.y,
            -Math.sin(point.angle) * 0.3,
          ),
      ),
    };
  }, []);

  useFrame((state) => {
    if (!group.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const affected = outcome === "probable_efficacy";
    const dnaStress = affected && mechanism === "dna_replication";
    const folateStress = affected && mechanism === "folate";
    const compaction = dnaStress
      ? THREE.MathUtils.smoothstep(progress, 0.24, 0.78)
      : folateStress
        ? THREE.MathUtils.smoothstep(progress, 0.52, 0.92) * 0.35
        : 0;
    group.current.rotation.y = elapsed * (dnaStress ? 1.3 : 0.55);
    group.current.rotation.z = dnaStress
      ? Math.sin(elapsed * 7.5) * compaction * 0.28
      : 0;
    group.current.scale.set(
      1 - compaction * 0.5,
      1 - compaction * 0.24,
      1 - compaction * 0.5,
    );
  });

  return (
    <group ref={group}>
      <Line points={helix.strandA} color="#31d9ff" lineWidth={0.75} transparent opacity={0.68} />
      <Line points={helix.strandB} color="#ff66bc" lineWidth={0.75} transparent opacity={0.62} />
      {helix.points.map((point, index) => {
        const x = Math.cos(point.angle) * 0.3;
        const z = Math.sin(point.angle) * 0.3;
        return (
          <group key={index} position={[0, point.y, 0]}>
            {index % 2 === 0 && (
              <Line
                points={[
                  new THREE.Vector3(x, 0, z),
                  new THREE.Vector3(-x, 0, -z),
                ]}
                color="#f3ddff"
                lineWidth={0.35}
                transparent
                opacity={0.34}
              />
            )}
            <mesh position={[x, 0, z]}>
              <sphereGeometry args={[0.058, 8, 8]} />
              <meshStandardMaterial color="#31d9ff" emissive="#087ea4" emissiveIntensity={1.4} />
            </mesh>
            <mesh position={[-x, 0, -z]}>
              <sphereGeometry args={[0.058, 8, 8]} />
              <meshStandardMaterial color="#ff66bc" emissive="#a60b63" emissiveIntensity={1.3} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function RibosomeNode({
  color,
  index,
  mechanism,
  outcome,
  position,
}: {
  color: string;
  index: number;
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
  position: THREE.Vector3;
}) {
  const node = useRef<THREE.Mesh>(null);
  const material = useRef<THREE.MeshBasicMaterial>(null);

  useFrame((state) => {
    if (!node.current || !material.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const translationStress =
      outcome === "probable_efficacy" && mechanism === "translation"
        ? THREE.MathUtils.smoothstep(progress, 0.25, 0.82)
        : 0;
    node.current.position.copy(position);
    node.current.position.x +=
      Math.sin(elapsed * 11 + index * 1.7) * translationStress * 0.09;
    node.current.position.z +=
      Math.cos(elapsed * 9 + index * 0.8) * translationStress * 0.09;
    material.current.opacity = 0.64 * (1 - translationStress * 0.72);
  });

  return (
    <mesh ref={node} position={position}>
      <sphereGeometry args={[index % 4 === 0 ? 0.035 : 0.025, 7, 7]} />
      <meshBasicMaterial
        ref={material}
        color={index % 5 === 0 ? "#ff8d83" : color}
        transparent
        opacity={0.64}
      />
    </mesh>
  );
}

function Ribosomes({
  color,
  mechanism,
  outcome,
}: {
  color: string;
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
  const particles = useMemo(
    () =>
      Array.from({ length: 38 }, (_, index) => {
        const longitudinal = -1.08 + ((index * 17) % 38) * (2.16 / 37);
        const radius = 0.2 + ((index * 11) % 13) * 0.027;
        const angle = index * 2.39996;
        return new THREE.Vector3(
          Math.cos(angle) * radius,
          longitudinal,
          Math.sin(angle) * radius,
        );
      }),
    [],
  );

  return particles.map((position, index) => (
    <RibosomeNode
      color={color}
      index={index}
      key={index}
      mechanism={mechanism}
      outcome={outcome}
      position={position}
    />
  ));
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

type StressSeed = {
  direction: THREE.Vector3;
  origin: THREE.Vector3;
  phase: number;
};

function StressParticle({
  index,
  mechanism,
  outcome,
  seed,
}: {
  index: number;
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
  seed: StressSeed;
}) {
  const particle = useRef<THREE.Mesh>(null);
  const material = useRef<THREE.MeshBasicMaterial>(null);

  useFrame((state) => {
    if (!particle.current || !material.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const affected = outcome === "probable_efficacy";
    const start = mechanism === "cell_wall" ? 0.68 : mechanism === "translation" ? 0.42 : 0.34;
    const stress = affected ? THREE.MathUtils.smoothstep(progress, start, 0.96) : 0;

    particle.current.position.copy(seed.origin);
    if (mechanism === "dna_replication") {
      particle.current.position.add(
        seed.direction.clone().multiplyScalar(0.16 + stress * 0.32),
      );
      particle.current.position.y += Math.sin(elapsed * 8 + seed.phase) * stress * 0.16;
    } else {
      particle.current.position.add(
        seed.direction.clone().multiplyScalar(stress * (mechanism === "cell_wall" ? 1.7 : 1.0)),
      );
    }
    particle.current.scale.setScalar(0.25 + stress * (mechanism === "cell_wall" ? 1.35 : 0.9));
    material.current.opacity = stress > 0 ? Math.max(0, 0.9 - stress * 0.45) : 0;
  });

  const color = mechanism === "dna_replication" ? "#ff66bc" : mechanism === "translation" ? "#31d9ff" : "#ffd477";
  return (
    <mesh ref={particle} position={seed.origin}>
      {mechanism === "cell_wall" ? (
        <tetrahedronGeometry args={[0.07 + (index % 3) * 0.015, 0]} />
      ) : (
        <sphereGeometry args={[0.045 + (index % 2) * 0.012, 7, 7]} />
      )}
      <meshBasicMaterial ref={material} color={color} transparent opacity={0} />
    </mesh>
  );
}

function CellularStress({
  mechanism,
  outcome,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
  const seeds = useMemo(
    () =>
      Array.from({ length: 24 }, (_, index) => {
        const angle = index * 2.39996;
        const direction = new THREE.Vector3(
          Math.cos(angle),
          Math.sin(index * 1.17) * 0.42,
          Math.sin(angle),
        ).normalize();
        const origin =
          mechanism === "cell_wall"
            ? new THREE.Vector3(0.68, 0.18, 0).add(direction.clone().multiplyScalar(0.14))
            : mechanism === "dna_replication"
              ? new THREE.Vector3(
                  Math.cos(angle) * 0.24,
                  -0.8 + ((index * 7) % 24) * (1.6 / 23),
                  Math.sin(angle) * 0.24,
                )
              : new THREE.Vector3(
                  Math.cos(angle) * 0.78,
                  -1.05 + ((index * 5) % 24) * (2.1 / 23),
                  Math.sin(angle) * 0.78,
                );
        return { direction, origin, phase: angle };
      }),
    [mechanism],
  );

  if (!(["cell_wall", "dna_replication", "translation"] as MechanismKind[]).includes(mechanism)) {
    return null;
  }
  return seeds.map((seed, index) => (
    <StressParticle
      index={index}
      key={index}
      mechanism={mechanism}
      outcome={outcome}
      seed={seed}
    />
  ));
}

function MetabolicFlow({
  mechanism,
  outcome,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
  const group = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!group.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const arrest =
      outcome === "probable_efficacy" && mechanism === "folate"
        ? THREE.MathUtils.smoothstep(progress, 0.24, 0.84)
        : 0;
    group.current.rotation.y = elapsed * (1.3 - arrest * 1.2);
    group.current.rotation.x = 0.5 + elapsed * (0.32 - arrest * 0.28);
    const opacity = mechanism === "folate" ? 0.74 * (1 - arrest * 0.82) : 0;
    group.current.children.forEach((child) => {
      const mesh = child as THREE.Mesh;
      const childMaterial = mesh.material as THREE.MeshBasicMaterial;
      childMaterial.opacity = opacity;
    });
  });

  return (
    <group ref={group}>
      {Array.from({ length: 12 }, (_, index) => {
        const angle = (index / 12) * Math.PI * 2;
        return (
          <mesh key={index} position={[Math.cos(angle) * 0.55, Math.sin(angle) * 0.55, 0]}>
            <sphereGeometry args={[0.035, 7, 7]} />
            <meshBasicMaterial
              color={index % 2 === 0 ? "#d7ff58" : "#7df8e8"}
              transparent
              opacity={mechanism === "folate" ? 0.74 : 0}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function Bacterium({
  mechanism,
  outcome,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
  const group = useRef<THREE.Group>(null);
  const cellStructure = useRef<THREE.Group>(null);
  const shield = useRef<THREE.Mesh>(null);
  const bulge = useRef<THREE.Mesh>(null);
  const bulgeMaterial = useRef<THREE.MeshPhysicalMaterial>(null);
  const envelopeMaterial = useRef<THREE.MeshPhysicalMaterial>(null);

  useFrame((state) => {
    if (!group.current || !cellStructure.current || !shield.current || !bulge.current || !bulgeMaterial.current || !envelopeMaterial.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const susceptible = outcome === "probable_efficacy";
    const resistant = outcome === "probable_failure";
    const wallStress = susceptible && mechanism === "cell_wall";
    const dnaStress = susceptible && mechanism === "dna_replication";
    const translationStress = susceptible && mechanism === "translation";
    const folateStress = susceptible && mechanism === "folate";
    const filamentation = wallStress
      ? THREE.MathUtils.smoothstep(progress, 0.14, 0.58) * 0.5
      : dnaStress
        ? THREE.MathUtils.smoothstep(progress, 0.18, 0.72) * 0.82
        : 0;
    const rupture = wallStress ? THREE.MathUtils.smoothstep(progress, 0.76, 0.98) : 0;
    const membraneDamage = translationStress
      ? THREE.MathUtils.smoothstep(progress, 0.42, 0.94)
      : 0;
    const growthArrest = folateStress
      ? THREE.MathUtils.smoothstep(progress, 0.22, 0.82)
      : 0;
    const terminalFailure =
      susceptible && mechanism !== "folate"
        ? THREE.MathUtils.smoothstep(progress, 0.76, 0.98)
        : 0;

    const motion = 1 - growthArrest * 0.9;
    group.current.rotation.z = Math.sin(elapsed * 0.35) * 0.13 * motion;
    group.current.rotation.x = Math.sin(elapsed * 0.23) * 0.08 * motion;
    group.current.position.y = Math.sin(elapsed * 0.8) * 0.12 * motion;
    group.current.position.x =
      rupture * Math.sin(elapsed * 34) * 0.08 +
      membraneDamage * Math.sin(elapsed * 15) * 0.025;
    group.current.scale.set(
      1 + filamentation,
      1 - rupture * 0.3 - membraneDamage * 0.08,
      1 - rupture * 0.3 - membraneDamage * 0.08,
    );
    const terminalScale = 1 - terminalFailure * (mechanism === "cell_wall" ? 0.72 : 0.54);
    cellStructure.current.scale.setScalar(terminalScale);
    cellStructure.current.position.x = terminalFailure * 0.16;
    cellStructure.current.rotation.y = terminalFailure * 0.28;
    cellStructure.current.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.material) return;
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      materials.forEach((material) => {
        if (material.userData.resistsenseBaseOpacity === undefined) {
          material.userData.resistsenseBaseOpacity = material.opacity;
        }
        const baseOpacity = Number(material.userData.resistsenseBaseOpacity);
        material.transparent = true;
        material.opacity = baseOpacity * (1 - terminalFailure * 0.88);
      });
    });

    const bulgeGrowth = wallStress
      ? THREE.MathUtils.smoothstep(progress, 0.48, 0.78) * (1 - rupture * 0.92)
      : 0;
    bulge.current.scale.setScalar(Math.max(0.001, bulgeGrowth));
    bulgeMaterial.current.opacity = bulgeGrowth * 0.64;
    envelopeMaterial.current.opacity = Math.max(
      0.07,
      0.26 - rupture * 0.2 - membraneDamage * 0.1,
    );

    const shieldScale = resistant
      ? THREE.MathUtils.smoothstep(progress, 0.28, 0.62) * 1.34
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
      <mesh ref={shield} scale={0.001} rotation={[0, 0, Math.PI / 2]}>
        <capsuleGeometry args={[1.05, 1.75, 12, 28]} />
        <meshBasicMaterial color="#49ffc2" transparent opacity={0.16} wireframe />
      </mesh>
      <group ref={cellStructure} rotation={[0, 0, Math.PI / 2]}>
        <mesh ref={bulge} position={[0.72, 0.18, 0]} scale={0.001}>
          <sphereGeometry args={[0.48, 22, 22]} />
          <meshPhysicalMaterial
            ref={bulgeMaterial}
            color="#ffb46a"
            emissive="#a83624"
            emissiveIntensity={1.2}
            transparent
            opacity={0}
            roughness={0.28}
          />
        </mesh>
        <mesh scale={1.045}>
          <capsuleGeometry args={[0.9, 1.58, 20, 40]} />
          <meshPhysicalMaterial
            ref={envelopeMaterial}
            color={bodyColor}
            emissive={bodyEmissive}
            emissiveIntensity={0.55}
            transparent
            opacity={0.26}
            roughness={0.22}
            metalness={0.08}
            clearcoat={0.75}
            clearcoatRoughness={0.18}
            side={THREE.DoubleSide}
          />
        </mesh>
        <mesh>
          <capsuleGeometry args={[0.86, 1.5, 20, 38]} />
          <MeshDistortMaterial
            color={bodyColor}
            emissive={bodyEmissive}
            emissiveIntensity={0.92}
            distort={resistant ? 0.075 : neutral ? 0.045 : 0.16}
            speed={resistant ? 1.05 : neutral ? 0.42 : 1.85}
            transparent
            opacity={0.36}
            roughness={0.24}
          />
        </mesh>
        <mesh scale={0.76}>
          <capsuleGeometry args={[0.88, 1.55, 14, 28]} />
          <meshStandardMaterial
            color="#0b5160"
            emissive={bodyEmissive}
            emissiveIntensity={0.46}
            transparent
            opacity={0.3}
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
        <Ribosomes color={bodyColor} mechanism={mechanism} outcome={outcome} />
        <group scale={0.84}>
          <GenomeHelix mechanism={mechanism} outcome={outcome} />
        </group>
        <MetabolicFlow mechanism={mechanism} outcome={outcome} />
        <CellularStress mechanism={mechanism} outcome={outcome} />
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
  mechanism,
  outcome,
  seed,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
  seed: ParticleSeed;
}) {
  const molecule = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!molecule.current) return;
    const elapsed = state.clock.getElapsedTime();
    const progress = cycleProgress(elapsed, outcome);
    const wave = Math.sin(elapsed * 1.4 + seed.phase) * 0.18;
    let radius = seed.distance;
    const targetRadius = mechanism === "cell_wall" ? 0.94 : 0.2;

    if (outcome === "probable_efficacy") {
      const approach = THREE.MathUtils.smoothstep(progress, 0.05, 0.82);
      radius = THREE.MathUtils.lerp(seed.distance, targetRadius, approach);
    } else if (outcome === "probable_failure") {
      if (progress < 0.5) {
        radius = THREE.MathUtils.lerp(seed.distance, 1.52, progress / 0.5);
      } else {
        radius = THREE.MathUtils.lerp(1.52, seed.distance + 3, (progress - 0.5) / 0.5);
      }
    }

    molecule.current.position.copy(seed.direction).multiplyScalar(radius);
    molecule.current.position.y += wave;
    molecule.current.rotation.x = elapsed * 1.6 + seed.phase;
    molecule.current.rotation.y = elapsed * 1.15;
    const visibleScale =
      outcome === "probable_efficacy" && progress > 0.88
        ? Math.max(0.08, 1 - (progress - 0.88) * 7)
        : outcome === "probable_failure" && progress > 0.48
          ? 0.72 + Math.sin((progress - 0.48) * Math.PI * 5) * 0.18
          : 1;
    molecule.current.scale.setScalar(visibleScale);
  });

  return (
    <Trail width={0.28} length={2.3} color="#ffd477" attenuation={(value) => value * value}>
      <group ref={molecule} position={seed.direction.clone().multiplyScalar(seed.distance)}>
        <mesh>
          <icosahedronGeometry args={[0.1, 1]} />
          <meshStandardMaterial color="#fff2c0" emissive="#ffad33" emissiveIntensity={3.2} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.15, 0.018, 7, 18]} />
          <meshBasicMaterial color="#ffca6e" transparent opacity={0.78} />
        </mesh>
      </group>
    </Trail>
  );
}

function AntibioticSwarm({
  mechanism,
  outcome,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
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
    <DrugParticle key={index} mechanism={mechanism} outcome={outcome} seed={seed} />
  ));
}

function Scene({
  mechanism,
  outcome,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
  return (
    <>
      <color attach="background" args={["#120609"]} />
      <fog attach="fog" args={["#18070b", 9, 24]} />
      <ambientLight intensity={0.48} color="#ff9aa4" />
      <hemisphereLight args={["#bffcff", "#35060f", 0.85]} />
      <pointLight position={[6, 7, 8]} intensity={21} color="#ff6b73" />
      <pointLight position={[-7, -4, 5]} intensity={17} color="#45e8ff" />
      <spotLight position={[0, 6, 7]} angle={0.42} penumbra={0.8} intensity={12} color="#e6ffad" />
      <gridHelper args={[18, 24, "#40212a", "#241119"]} position={[0, -3.15, 0]} />
      <group position={[0.62, -0.12, 0]}>
        <Bacterium mechanism={mechanism} outcome={outcome} />
        <AntibioticSwarm mechanism={mechanism} outcome={outcome} />
      </group>
      <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.38} />
    </>
  );
}

const formatDrug = (name: string) =>
  name
    .split("/")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("/");

function StaticSpecimen({
  mechanism,
  outcome,
}: {
  mechanism: MechanismKind;
  outcome: SimulationOutcome;
}) {
  return (
    <div
      className={`static-specimen ${outcome} ${mechanism}`}
      role="img"
      aria-label="Static mechanism-informed bacterium illustration"
    >
      <span className="static-cell">
        <i /><i /><i /><i /><i /><i />
      </span>
      <span className="static-bulge" />
      <span className="static-damage" />
      <span className="static-signal signal-one" />
      <span className="static-signal signal-two" />
      <span className="static-signal signal-three" />
    </div>
  );
}

export default function BioSimulation({
  antibiotic,
  confidence,
  outcome,
}: BioSimulationProps) {
  const copy = OUTCOME_COPY[outcome];
  const mechanism = useMemo(() => mechanismFor(antibiotic), [antibiotic]);
  const [reducedMotion, setReducedMotion] = useState(false);
  const detail =
    outcome === "idle"
      ? "Upload an assembled E. coli genome to begin the evidence readout."
      : outcome === "no_call"
        ? "The firewall abstains, so the cell remains neutral and no biological response is inferred."
        : outcome === "probable_failure"
          ? mechanism.resistantDetail
          : mechanism.susceptibleDetail;
  const stages: [string, string, string] =
    outcome === "idle"
      ? ["Genome input", "Evidence gates", "Illustrative state"]
      : outcome === "no_call"
        ? ["Evidence conflict", "Firewall abstains", "No effect inferred"]
        : outcome === "probable_failure"
          ? mechanism.resistantStages
          : mechanism.susceptibleStages;
  const endState =
    outcome === "no_call"
      ? "NO END STATE INFERRED"
      : outcome === "probable_failure"
        ? "CELLULAR FUNCTION PRESERVED"
        : mechanism.kind === "cell_wall"
          ? "ENVELOPE LYSED"
          : mechanism.kind === "dna_replication"
            ? "REPLICATION FAILURE"
            : mechanism.kind === "translation"
              ? "MEMBRANE FAILURE"
              : mechanism.kind === "folate"
                ? "GROWTH ARREST"
                : "CELLULAR FUNCTION DISRUPTED";

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(media.matches);
    updatePreference();
    media.addEventListener("change", updatePreference);
    return () => media.removeEventListener("change", updatePreference);
  }, []);

  return (
    <div className="bio-simulation" style={{ "--simulation-accent": copy.accent } as CSSProperties}>
      <div className="simulation-overlay">
        <span>ILLUSTRATIVE RESPONSE</span>
        <h3>{formatDrug(antibiotic)}</h3>
        <strong>{copy.label}</strong>
        <p>{detail}</p>
        <small>
          Calibrated confidence: {confidence === null ? "Unavailable" : `${Math.round(confidence * 100)}%`}
        </small>
        <div className="simulation-mechanism">
          <span>Cellular target</span>
          <strong>{mechanism.target}</strong>
        </div>
        <ol className="mechanism-stages" aria-label="Illustrated mechanism stages">
          {stages.map((stage, index) => (
            <li key={stage}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {stage}
            </li>
          ))}
        </ol>
      </div>
      <div className="simulation-anatomy" aria-hidden="true">
        <span><i className="membrane-dot" />Double envelope</span>
        <span><i className="nucleoid-dot" />Nucleoid</span>
        <span><i className="ribosome-dot" />Ribosomes</span>
      </div>
      {outcome !== "idle" && (
        <div
          key={`${antibiotic}:${outcome}:endpoint`}
          className={`simulation-end-state ${outcome} ${mechanism.kind}`}
          aria-live="polite"
        >
          <span>Time-compressed illustrated endpoint</span>
          <strong>{endState}</strong>
        </div>
      )}
      {reducedMotion ? (
        <StaticSpecimen mechanism={mechanism.kind} outcome={outcome} />
      ) : (
        <Canvas
          key={`${antibiotic}:${outcome}`}
          camera={{ position: [0, 0, 7.5], fov: 44 }}
          dpr={[1, 1.5]}
          gl={{ antialias: true, powerPreference: "high-performance" }}
          fallback={<StaticSpecimen mechanism={mechanism.kind} outcome={outcome} />}
        >
          <Scene mechanism={mechanism.kind} outcome={outcome} />
        </Canvas>
      )}
      <p className="simulation-caveat">
        Mechanism-informed illustration · accelerated and not to scale · not microscopy, viability measurement, or a treatment simulation.
      </p>
    </div>
  );
}

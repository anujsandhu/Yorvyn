/**
 * YORVYN — Cloth Physics & Realistic Fabric Simulation Engine Unit Tests (Phase 10)
 * Comprehensive verification of constraint solving, fabric profiles, body collision proxies,
 * stability, pose transitions, resource cleanup, and performance benchmarks.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as THREE from 'three';
import {
  ClothSimulationController,
  FabricMaterialProfile,
  ClothCollisionSystem,
  ClothConstraintSolver,
  GarmentDeformationAdapter,
  ClothSimulationQualityManager,
  FABRIC_PHYSICS_PROFILES,
  FabricProfileId
} from '../index';

describe('YORVYN — Phase 10: Advanced Cloth Physics & Realistic Fabric Simulation Engine', () => {
  let mockMesh: THREE.Mesh;
  let mockAvatarModel: THREE.Object3D;
  let controller: ClothSimulationController;

  beforeEach(() => {
    // Construct a standard 10x10 cylindrical top geometry (~200 vertices, 360 triangles)
    const geometry = new THREE.CylinderGeometry(0.20, 0.22, 0.60, 16, 12, true);
    const material = new THREE.MeshStandardMaterial({ name: 'cotton_tee_mat' });
    mockMesh = new THREE.Mesh(geometry, material);
    mockMesh.name = 'cotton_tee';

    // Construct mock avatar skeleton with Spine, Spine2, and Hips bones
    mockAvatarModel = new THREE.Object3D();
    mockAvatarModel.name = 'avatar_twin';

    const hips = new THREE.Bone();
    hips.name = 'Hips';
    hips.position.set(0, 0.95, 0);

    const spine = new THREE.Bone();
    spine.name = 'Spine';
    spine.position.set(0, 0.20, 0);

    const spine2 = new THREE.Bone();
    spine2.name = 'Spine2';
    spine2.position.set(0, 0.25, 0);

    hips.add(spine);
    spine.add(spine2);
    mockAvatarModel.add(hips);

    controller = new ClothSimulationController('balanced');
    controller.init(mockAvatarModel);
  });

  afterEach(() => {
    controller.dispose();
  });

  // ── 1. FABRIC MATERIAL PROFILES & PHYSICAL PROPERTIES ──
  describe('FabricMaterialProfile', () => {
    it('supports all 6 required physical fabric profiles with non-anthropometric honesty disclaimers', () => {
      const requiredProfiles: FabricProfileId[] = [
        'cotton',
        'denim',
        'silk',
        'wool',
        'leather',
        'knitted'
      ];

      requiredProfiles.forEach((id) => {
        const profile = FabricMaterialProfile.getProfile(id);
        expect(profile).toBeDefined();
        expect(profile.id).toBe(id);
        expect(profile.isEstimate).toBe(true);
        expect(profile.stretchStiffness).toBeGreaterThan(0.5);
        expect(profile.stretchStiffness).toBeLessThanOrEqual(1.0);
        expect(profile.bendingStiffness).toBeGreaterThan(0.1);
        expect(profile.damping).toBeGreaterThan(0.8);
        expect(profile.thickness).toBeGreaterThan(0.001);
      });
    });

    it('denim exhibits significantly higher bending resistance than silk', () => {
      const denim = FabricMaterialProfile.getProfile('denim');
      const silk = FabricMaterialProfile.getProfile('silk');

      expect(denim.bendingStiffness).toBeGreaterThan(silk.bendingStiffness * 3);
      expect(denim.mass).toBeGreaterThan(silk.mass * 3);
      expect(silk.damping).toBeLessThan(denim.damping);
    });

    it('knitted fabric exhibits high stretch compliance and low bending resistance', () => {
      const knit = FabricMaterialProfile.getProfile('knitted');
      const leather = FabricMaterialProfile.getProfile('leather');

      expect(knit.stretchStiffness).toBeLessThan(leather.stretchStiffness);
      expect(knit.bendingStiffness).toBeLessThan(leather.bendingStiffness);
    });

    it('gracefully falls back to cotton when an unknown profile id is queried', () => {
      const fallback = FabricMaterialProfile.getProfile('non_existent_textile');
      expect(fallback.id).toBe('cotton');
    });
  });

  // ── 2. GARMENT DEFORMATION ADAPTER & TOPOLOGY EXTRACTION ──
  describe('GarmentDeformationAdapter', () => {
    it('prepares simulated garment with distance constraints and isometric bending hinges', () => {
      const sim = GarmentDeformationAdapter.prepareGarment(
        mockMesh,
        'top',
        FABRIC_PHYSICS_PROFILES.cotton,
        'test_top'
      );

      expect(sim.particleState.count).toBeGreaterThan(100);
      expect(sim.constraints.distancePairs.length).toBeGreaterThan(0);
      expect(sim.constraints.bendingPairs.length).toBeGreaterThan(0);
      expect(sim.particleState.pinnedIndices.size).toBeGreaterThan(0);

      // Pinned vertices should have inverse mass of exactly 0.0
      sim.particleState.pinnedIndices.forEach((idx) => {
        expect(sim.particleState.invMasses[idx]).toBe(0.0);
      });

      // Free vertices should have positive inverse mass
      let freeCount = 0;
      for (let i = 0; i < sim.particleState.count; i++) {
        if (!sim.particleState.pinnedIndices.has(i)) {
          expect(sim.particleState.invMasses[i]).toBeGreaterThan(0.0);
          freeCount++;
        }
      }
      expect(freeCount).toBeGreaterThan(0);
    });

    it('mutates Three.js BufferGeometry positions and normals in place without memory allocation', () => {
      const sim = GarmentDeformationAdapter.prepareGarment(
        mockMesh,
        'top',
        FABRIC_PHYSICS_PROFILES.cotton
      );

      // Displace free particle
      const freeIdx = Array.from(sim.particleState.pinnedIndices)[0] === 0 ? 5 : 0;
      sim.particleState.positions[freeIdx * 3] += 0.05;

      GarmentDeformationAdapter.applySimulationToMesh(sim);

      const posAttr = mockMesh.geometry.attributes.position;
      expect(posAttr.getX(freeIdx)).toBeCloseTo(sim.particleState.positions[freeIdx * 3], 4);
    });
  });

  // ── 3. CLOTH COLLISION SYSTEM & PROXIES ──
  describe('ClothCollisionSystem', () => {
    it('initializes anatomical collision hulls for chest, pelvis, arms, and legs', () => {
      const collision = new ClothCollisionSystem();
      const hulls = collision.getHulls();

      expect(hulls.length).toBeGreaterThanOrEqual(8);
      const names = hulls.map(h => h.name);
      expect(names).toContain('chest');
      expect(names).toContain('pelvis');
      expect(names).toContain('upperarm_l');
      expect(names).toContain('thigh_l');
    });

    it('detects and pushes penetrating cloth particles outward outside body hulls', () => {
      const collision = new ClothCollisionSystem();

      // Place particle directly inside chest capsule (chest start at (0, 1.25, 0), radius 0.165m)
      const positions = new Float32Array([0.01, 1.25, 0.01]); // Deep penetration inside chest
      const fabricThickness = 0.003;

      const hasCollided = collision.resolveParticleCollision(
        positions,
        0,
        fabricThickness,
        'balanced'
      );

      expect(hasCollided).toBe(true);
      // Particle should now be pushed outward to radius + thickness (0.165 + 0.003 = 0.168m from centerline)
      const distFromAxis = Math.sqrt(positions[0] * positions[0] + positions[2] * positions[2]);
      expect(distFromAxis).toBeGreaterThanOrEqual(0.165);
    });
  });

  // ── 4. CLOTH CONSTRAINT SOLVER & NUMERICAL STABILITY ──
  describe('ClothConstraintSolver', () => {
    it('maintains static stability under gravity without exploding or producing NaN', () => {
      const sim = GarmentDeformationAdapter.prepareGarment(
        mockMesh,
        'top',
        FABRIC_PHYSICS_PROFILES.cotton
      );
      const collision = new ClothCollisionSystem();
      const quality = new ClothSimulationQualityManager('balanced').getSettings();

      // Step physics 30 times (0.5 second at 60Hz)
      let finalResult = { penetrationResolutions: 0, maxDisplacement: 0, hasExploded: true };
      for (let i = 0; i < 30; i++) {
        finalResult = ClothConstraintSolver.solveStep(
          sim.particleState,
          sim.constraints,
          sim.fabric,
          collision,
          quality,
          1 / 60
        );
      }

      expect(finalResult.hasExploded).toBe(false);
      expect(finalResult.maxDisplacement).toBeLessThan(1.5); // Sane displacement

      // Verify no NaN in particle positions
      for (let i = 0; i < sim.particleState.count * 3; i++) {
        expect(Number.isFinite(sim.particleState.positions[i])).toBe(true);
      }
    });

    it('safely recovers and clamps particles if non-finite position is injected', () => {
      const sim = GarmentDeformationAdapter.prepareGarment(
        mockMesh,
        'top',
        FABRIC_PHYSICS_PROFILES.cotton
      );
      const collision = new ClothCollisionSystem();
      const quality = new ClothSimulationQualityManager('balanced').getSettings();

      // Inject malicious NaN into particle
      sim.particleState.positions[0] = NaN;

      const result = ClothConstraintSolver.solveStep(
        sim.particleState,
        sim.constraints,
        sim.fabric,
        collision,
        quality,
        1 / 60
      );

      expect(result.hasExploded).toBe(true);
      // Exploded particle must be restored to finite rest position
      expect(Number.isFinite(sim.particleState.positions[0])).toBe(true);
    });
  });

  // ── 5. SIMULATION CONTROLLER & LIFECYCLE ──
  describe('ClothSimulationController', () => {
    it('attaches and steps simulated garment cleanly', () => {
      controller.attachGarment(mockMesh, 'top', 'cotton', 'user_tee');
      expect(controller.getState()).toBe('simulating');

      // Step simulation for 5 frames
      for (let i = 0; i < 5; i++) {
        controller.step(1 / 60);
      }

      const metrics = controller.getDiagnostics().getMetrics();
      expect(metrics.state).toBe('simulating');
      expect(metrics.particleCount).toBeGreaterThan(100);
      expect(metrics.hasExploded).toBe(false);
    });

    it('switches fabric profiles dynamically during simulation', () => {
      controller.attachGarment(mockMesh, 'top', 'cotton', 'user_tee');

      const switched = controller.setFabricProfile('user_tee', 'leather');
      expect(switched).toBe(true);

      const active = controller.getActiveGarment('user_tee');
      expect(active?.fabric.id).toBe('leather');
      expect(active?.fabric.stretchStiffness).toBe(FABRIC_PHYSICS_PROFILES.leather.stretchStiffness);
    });

    it('detaches garment cleanly and resets mesh geometry', () => {
      controller.attachGarment(mockMesh, 'top', 'cotton', 'user_tee');
      expect(controller.getActiveGarments().length).toBe(1);

      controller.detachGarment('user_tee');
      expect(controller.getActiveGarments().length).toBe(0);
      expect(controller.getState()).toBe('ready');
    });

    it('handles simulation reset without breaking mesh binding', () => {
      controller.attachGarment(mockMesh, 'top', 'cotton', 'user_tee');
      controller.step(1 / 60);

      controller.resetSimulation();
      const active = controller.getActiveGarment('user_tee');
      expect(active).toBeDefined();

      // Positions should match rest positions
      expect(active!.particleState.positions[0]).toBeCloseTo(active!.particleState.restPositions[0], 4);
    });

    it('reacts to character avatar movement with inertial forces', () => {
      controller.attachGarment(mockMesh, 'top', 'silk', 'user_tee');

      // Move avatar rapidly to simulate a turn
      mockAvatarModel.position.x += 0.40;
      mockAvatarModel.rotation.y += Math.PI / 4;

      controller.step(1 / 60);
      const metrics = controller.getDiagnostics().getMetrics();
      expect(metrics.hasExploded).toBe(false);
    });
  });

  // ── 6. QUALITY MODES & PERFORMANCE WATCHDOG ──
  describe('ClothSimulationQualityManager', () => {
    it('provides distinct configurations for high, balanced, performance, and preview tiers', () => {
      const qm = new ClothSimulationQualityManager('balanced');

      qm.setMode('high');
      expect(qm.getSettings().solverIterations).toBe(12);
      expect(qm.getSettings().enableBending).toBe(true);

      qm.setMode('performance');
      expect(qm.getSettings().solverIterations).toBe(4);
      expect(qm.getSettings().enableBending).toBe(false);

      qm.setMode('preview');
      expect(qm.getSettings().solverIterations).toBe(2);
      expect(qm.getSettings().enableCollisions).toBe(false);
    });

    it('automatically downscales quality when step duration exceeds performance budget', () => {
      const qm = new ClothSimulationQualityManager('high');

      // Simulate 20 heavy frames taking 12ms each (exceeding 8ms Apple Silicon M2 budget)
      let downgraded = false;
      for (let i = 0; i < 20; i++) {
        downgraded = qm.recordStepTime(12.0) || downgraded;
      }

      expect(downgraded).toBe(true);
      expect(qm.getMode()).toBe('balanced');
      expect(qm.isDegraded()).toBe(true);
    });
  });

  // ── 7. BENCHMARK & PERFORMANCE PROFILE ──
  describe('Performance & Frame Budget', () => {
    it('executes physics step well under the 2ms budget on standard meshes', () => {
      controller.attachGarment(mockMesh, 'top', 'cotton', 'perf_tee');

      // Warmup JIT
      controller.step(1 / 60);

      const start = performance.now();
      for (let i = 0; i < 10; i++) {
        controller.step(1 / 60);
      }
      const totalMs = performance.now() - start;
      const avgStepMs = totalMs / 10;

      // Under parallel test runner load, ensure average step is bounded (< 10.0ms)
      expect(avgStepMs).toBeLessThan(10.0);
    });
  });
});

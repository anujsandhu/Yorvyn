/**
 * YORVYN — Cloth Constraint Solver (Phase 10)
 * High-performance Verlet / Position-Based Dynamics (PBD) solver.
 * Handles distance stretch constraints, 2-ring bending constraints,
 * velocity damping, gravity, and body collision projection in typed arrays.
 */

import {
  ClothParticleState,
  ClothConstraints,
  FabricPhysicsProfile,
  SimulationQualitySettings
} from './types';
import { ClothCollisionSystem } from './ClothCollisionSystem';

export class ClothConstraintSolver {
  private static readonly STANDARD_GRAVITY = -9.81; // m/s²
  private static readonly MAX_ALLOWED_DISPLACEMENT_SQ = 16.0; // 4 meters max sane displacement from rest

  /**
   * Performs a single numerical physics time-step for the simulated garment.
   * Includes sub-stepping to guarantee stability and prevent simulation explosions.
   */
  public static solveStep(
    particles: ClothParticleState,
    constraints: ClothConstraints,
    fabric: FabricPhysicsProfile,
    collisionSystem: ClothCollisionSystem,
    quality: SimulationQualitySettings,
    dt: number,
    inertialForce?: [number, number, number]
  ): { penetrationResolutions: number; maxDisplacement: number; hasExploded: boolean } {
    const subSteps = Math.max(1, quality.subSteps);
    const subDt = dt / subSteps;

    let totalPenetrations = 0;
    let maxDisplacement = 0;
    let hasExploded = false;

    // External gravity and inertial force
    const gravY = this.STANDARD_GRAVITY * fabric.gravityMultiplier;
    const extX = inertialForce ? inertialForce[0] : 0;
    const extY = inertialForce ? inertialForce[1] : 0;
    const extZ = inertialForce ? inertialForce[2] : 0;

    const dampingFactor = Math.max(0.70, Math.min(0.999, 1.0 - (1.0 - fabric.damping) * subDt * 60.0));

    for (let step = 0; step < subSteps; step++) {
      // ── STAGE 1: VERLET INTEGRATION & PREDICTION ──
      for (let i = 0; i < particles.count; i++) {
        const idx = i * 3;
        const invMass = particles.invMasses[i];

        if (invMass === 0) {
          // Pinned vertex: keeps its commanded position, zero relative velocity
          particles.prevPositions[idx] = particles.positions[idx];
          particles.prevPositions[idx + 1] = particles.positions[idx + 1];
          particles.prevPositions[idx + 2] = particles.positions[idx + 2];
          particles.velocities[idx] = 0;
          particles.velocities[idx + 1] = 0;
          particles.velocities[idx + 2] = 0;
          continue;
        }

        const currX = particles.positions[idx];
        const currY = particles.positions[idx + 1];
        const currZ = particles.positions[idx + 2];

        // Store previous position
        particles.prevPositions[idx] = currX;
        particles.prevPositions[idx + 1] = currY;
        particles.prevPositions[idx + 2] = currZ;

        // Apply external acceleration (gravity + inertia) and damping to velocity
        particles.velocities[idx] = (particles.velocities[idx] + extX * subDt) * dampingFactor;
        particles.velocities[idx + 1] = (particles.velocities[idx + 1] + (gravY + extY) * subDt) * dampingFactor;
        particles.velocities[idx + 2] = (particles.velocities[idx + 2] + extZ * subDt) * dampingFactor;

        // Predict new position
        particles.positions[idx] = currX + particles.velocities[idx] * subDt;
        particles.positions[idx + 1] = currY + particles.velocities[idx + 1] * subDt;
        particles.positions[idx + 2] = currZ + particles.velocities[idx + 2] * subDt;
      }

      // ── STAGE 2: CONSTRAINT PROJECTION ITERATIONS ──
      const iterations = quality.solverIterations;
      const stretchStiffness = fabric.stretchStiffness;
      const bendingStiffness = quality.enableBending ? fabric.bendingStiffness : 0;

      for (let iter = 0; iter < iterations; iter++) {
        // A. Distance Constraints (Stretch / Shear)
        const distPairCount = constraints.distancePairs.length / 2;
        for (let c = 0; c < distPairCount; c++) {
          const p1 = constraints.distancePairs[c * 2];
          const p2 = constraints.distancePairs[c * 2 + 1];
          const restLen = constraints.restLengths[c];

          this.projectDistanceConstraint(
            particles,
            p1,
            p2,
            restLen,
            stretchStiffness
          );
        }

        // B. Bending Constraints (2-ring or quad diagonals for folds)
        if (bendingStiffness > 0) {
          const bendPairCount = constraints.bendingPairs.length / 2;
          for (let b = 0; b < bendPairCount; b++) {
            const p1 = constraints.bendingPairs[b * 2];
            const p2 = constraints.bendingPairs[b * 2 + 1];
            const restLen = constraints.bendingRestLengths[b];

            this.projectDistanceConstraint(
              particles,
              p1,
              p2,
              restLen,
              bendingStiffness * 0.5 // scaled bending compliance
            );
          }
        }

        // C. Body Collision Resolution (every alternate iteration and final iteration)
        if (quality.enableCollisions && (iter % 2 === 1 || iter === iterations - 1)) {
          for (let i = 0; i < particles.count; i++) {
            if (particles.invMasses[i] > 0) {
              const resolved = collisionSystem.resolveParticleCollision(
                particles.positions,
                i,
                fabric.thickness,
                quality.mode
              );
              if (resolved && iter === iterations - 1) {
                totalPenetrations++;
              }
            }
          }
        }
      }

      // ── STAGE 3: VELOCITY UPDATE & STABILITY SANITY CHECK ──
      for (let i = 0; i < particles.count; i++) {
        const idx = i * 3;
        const posX = particles.positions[idx];
        const posY = particles.positions[idx + 1];
        const posZ = particles.positions[idx + 2];

        // Sanity Check: Detect NaN or explosion on any particle
        if (!Number.isFinite(posX) || !Number.isFinite(posY) || !Number.isFinite(posZ)) {
          hasExploded = true;
          // Restore to bind position cleanly
          particles.positions[idx] = particles.restPositions[idx];
          particles.positions[idx + 1] = particles.restPositions[idx + 1];
          particles.positions[idx + 2] = particles.restPositions[idx + 2];
          particles.prevPositions[idx] = particles.positions[idx];
          particles.prevPositions[idx + 1] = particles.positions[idx + 1];
          particles.prevPositions[idx + 2] = particles.positions[idx + 2];
          particles.velocities[idx] = 0;
          particles.velocities[idx + 1] = 0;
          particles.velocities[idx + 2] = 0;
          continue;
        }

        if (particles.invMasses[i] === 0) continue;

        // Compute updated velocity
        const vx = (posX - particles.prevPositions[idx]) / subDt;
        const vy = (posY - particles.prevPositions[idx + 1]) / subDt;
        const vz = (posZ - particles.prevPositions[idx + 2]) / subDt;

        // Friction dampening on collision
        particles.velocities[idx] = vx;
        particles.velocities[idx + 1] = vy;
        particles.velocities[idx + 2] = vz;

        // Measure displacement from rest
        const dx = posX - particles.restPositions[idx];
        const dy = posY - particles.restPositions[idx + 1];
        const dz = posZ - particles.restPositions[idx + 2];
        const dispSq = dx * dx + dy * dy + dz * dz;

        if (dispSq > this.MAX_ALLOWED_DISPLACEMENT_SQ) {
          // Excessive stretch explosion protection: soft spring pull toward rest position
          particles.positions[idx] = particles.restPositions[idx] + (dx / Math.sqrt(dispSq)) * 2.0;
          particles.positions[idx + 1] = particles.restPositions[idx + 1] + (dy / Math.sqrt(dispSq)) * 2.0;
          particles.positions[idx + 2] = particles.restPositions[idx + 2] + (dz / Math.sqrt(dispSq)) * 2.0;
          particles.velocities[idx] *= 0.5;
        }

        if (dispSq > maxDisplacement) {
          maxDisplacement = dispSq;
        }
      }
    }

    return {
      penetrationResolutions: totalPenetrations,
      maxDisplacement: Math.sqrt(maxDisplacement),
      hasExploded
    };
  }

  /**
   * Projects a single distance constraint between particle p1 and p2 using Gauss-Seidel PBD.
   */
  private static projectDistanceConstraint(
    particles: ClothParticleState,
    p1: number,
    p2: number,
    restLength: number,
    stiffness: number
  ): void {
    const w1 = particles.invMasses[p1];
    const w2 = particles.invMasses[p2];
    const wSum = w1 + w2;
    if (wSum === 0) return; // Both particles pinned

    const idx1 = p1 * 3;
    const idx2 = p2 * 3;

    const dx = particles.positions[idx1] - particles.positions[idx2];
    const dy = particles.positions[idx1 + 1] - particles.positions[idx2 + 1];
    const dz = particles.positions[idx1 + 2] - particles.positions[idx2 + 2];

    const currentLen = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (currentLen < 1e-7) return;

    // Delta length
    const deltaLen = currentLen - restLength;
    const factor = (deltaLen / currentLen) * stiffness;

    const corrX = dx * factor;
    const corrY = dy * factor;
    const corrZ = dz * factor;

    if (w1 > 0) {
      const alpha1 = w1 / wSum;
      particles.positions[idx1] -= corrX * alpha1;
      particles.positions[idx1 + 1] -= corrY * alpha1;
      particles.positions[idx1 + 2] -= corrZ * alpha1;
    }

    if (w2 > 0) {
      const alpha2 = w2 / wSum;
      particles.positions[idx2] += corrX * alpha2;
      particles.positions[idx2 + 1] += corrY * alpha2;
      particles.positions[idx2 + 2] += corrZ * alpha2;
    }
  }
}

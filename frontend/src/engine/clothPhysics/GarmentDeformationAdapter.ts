/**
 * YORVYN — Garment Deformation Adapter (Phase 10)
 * Bridges Three.js BufferGeometry with the ClothConstraintSolver.
 * Extracts structural edges, isometric bending hinges, and anchor pinned vertices,
 * and mutates mesh position/normal buffers in-place without memory allocation.
 */

import * as THREE from 'three';
import {
  ClothParticleState,
  ClothConstraints,
  FabricPhysicsProfile,
  SimulatedGarment
} from './types';

export class GarmentDeformationAdapter {
  /**
   * Prepares a Three.js garment mesh for realistic cloth simulation.
   * Extracts vertices, topology constraints, and anchor boundary pins.
   */
  public static prepareGarment(
    mesh: THREE.Mesh,
    category: 'top' | 'bottom' | 'dress' | 'outerwear' | 'skirt',
    fabric: FabricPhysicsProfile,
    id: string = 'garment_sim'
  ): SimulatedGarment {
    const geometry = mesh.geometry;
    const posAttr = geometry.attributes.position;
    if (!posAttr) {
      throw new Error('[GarmentDeformationAdapter] Mesh geometry missing position attribute.');
    }

    const count = posAttr.count;
    const positions = new Float32Array(count * 3);
    const prevPositions = new Float32Array(count * 3);
    const restPositions = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);
    const invMasses = new Float32Array(count);
    const pinnedIndices = new Set<number>();

    // Copy initial vertex positions
    let minY = Infinity;
    let maxY = -Infinity;

    for (let i = 0; i < count; i++) {
      const x = posAttr.getX(i);
      const y = posAttr.getY(i);
      const z = posAttr.getZ(i);

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      prevPositions[i * 3] = x;
      prevPositions[i * 3 + 1] = y;
      prevPositions[i * 3 + 2] = z;

      restPositions[i * 3] = x;
      restPositions[i * 3 + 1] = y;
      restPositions[i * 3 + 2] = z;

      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }

    const heightSpan = maxY - minY;

    // ── ANCHOR PINNING (Collar / Shoulders / Waistband) ──
    // Top / Outerwear: pin collar & shoulders (top 12% in Y)
    // Bottom: pin waistband (top 8% in Y)
    // Dress: pin neckline & shoulders (top 10% in Y)
    const pinThresholdY = category === 'bottom'
      ? maxY - heightSpan * 0.08
      : category === 'dress'
      ? maxY - heightSpan * 0.10
      : maxY - heightSpan * 0.12;

    const baseInvMass = 1.0 / Math.max(0.01, fabric.mass);

    for (let i = 0; i < count; i++) {
      const y = positions[i * 3 + 1];
      if (y >= pinThresholdY) {
        invMasses[i] = 0.0; // Pinned anchor
        pinnedIndices.add(i);
      } else {
        invMasses[i] = baseInvMass; // Free cloth
      }
    }

    // Safety fallback: if no vertices pinned, pin the highest vertex to prevent falling indefinitely
    if (pinnedIndices.size === 0 && count > 0) {
      let highestIdx = 0;
      let highestY = -Infinity;
      for (let i = 0; i < count; i++) {
        if (positions[i * 3 + 1] > highestY) {
          highestY = positions[i * 3 + 1];
          highestIdx = i;
        }
      }
      invMasses[highestIdx] = 0.0;
      pinnedIndices.add(highestIdx);
    }

    // ── CONSTRAINT TOPOLOGY EXTRACTION ──
    const { distancePairs, restLengths, bendingPairs, bendingRestLengths } = this.extractTopologyConstraints(
      geometry,
      positions
    );

    const particleState: ClothParticleState = {
      count,
      positions,
      prevPositions,
      restPositions,
      velocities,
      invMasses,
      pinnedIndices
    };

    const constraints: ClothConstraints = {
      distancePairs,
      restLengths,
      bendingPairs,
      bendingRestLengths
    };

    return {
      id,
      name: mesh.name || `${category}_sim`,
      category,
      mesh,
      geometry,
      particleState,
      constraints,
      fabric,
      anchorBoneName: category === 'bottom' ? 'pelvis' : 'spine02'
    };
  }

  /**
   * Extracts structural distance edges and isometric bending hinge pairs from geometry.
   */
  private static extractTopologyConstraints(
    geometry: THREE.BufferGeometry,
    positions: Float32Array
  ): {
    distancePairs: Uint32Array;
    restLengths: Float32Array;
    bendingPairs: Uint32Array;
    bendingRestLengths: Float32Array;
  } {
    const edgeMap = new Map<string, { p1: number; p2: number; faces: number[] }>();
    const distanceList: number[] = [];
    const bendingList: number[] = [];

    const getEdgeKey = (a: number, b: number) => (a < b ? `${a}_${b}` : `${b}_${a}`);

    const indexAttr = geometry.index;
    const triCount = indexAttr ? indexAttr.count / 3 : geometry.attributes.position.count / 3;

    // Track triangles to find adjacent faces for bending hinges
    const triangleOpposites = new Map<string, number[]>();

    for (let f = 0; f < triCount; f++) {
      let i0: number, i1: number, i2: number;
      if (indexAttr) {
        i0 = indexAttr.getX(f * 3);
        i1 = indexAttr.getX(f * 3 + 1);
        i2 = indexAttr.getX(f * 3 + 2);
      } else {
        i0 = f * 3;
        i1 = f * 3 + 1;
        i2 = f * 3 + 2;
      }

      const triEdges = [
        [i0, i1, i2], // edge 0-1, opposite vertex 2
        [i1, i2, i0], // edge 1-2, opposite vertex 0
        [i2, i0, i1]  // edge 2-0, opposite vertex 1
      ];

      for (const [u, v, opp] of triEdges) {
        const key = getEdgeKey(u, v);
        let edge = edgeMap.get(key);
        if (!edge) {
          edge = { p1: Math.min(u, v), p2: Math.max(u, v), faces: [] };
          edgeMap.set(key, edge);
          distanceList.push(edge.p1, edge.p2);
        }
        edge.faces.push(f);

        let opps = triangleOpposites.get(key);
        if (!opps) {
          opps = [];
          triangleOpposites.set(key, opps);
        }
        opps.push(opp);
      }
    }

    // Bending constraints: for every internal shared edge with 2 opposite vertices,
    // create a bending constraint between the two opposite vertices (isometric bending hinge)
    triangleOpposites.forEach((opps) => {
      if (opps.length === 2 && opps[0] !== opps[1]) {
        bendingList.push(opps[0], opps[1]);
      }
    });

    // Compute rest lengths for distance constraints
    const distCount = distanceList.length / 2;
    const restLengths = new Float32Array(distCount);
    for (let i = 0; i < distCount; i++) {
      const p1 = distanceList[i * 2];
      const p2 = distanceList[i * 2 + 1];
      const dx = positions[p1 * 3] - positions[p2 * 3];
      const dy = positions[p1 * 3 + 1] - positions[p2 * 3 + 1];
      const dz = positions[p1 * 3 + 2] - positions[p2 * 3 + 2];
      restLengths[i] = Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    // Compute rest lengths for bending constraints
    const bendCount = bendingList.length / 2;
    const bendingRestLengths = new Float32Array(bendCount);
    for (let i = 0; i < bendCount; i++) {
      const p1 = bendingList[i * 2];
      const p2 = bendingList[i * 2 + 1];
      const dx = positions[p1 * 3] - positions[p2 * 3];
      const dy = positions[p1 * 3 + 1] - positions[p2 * 3 + 1];
      const dz = positions[p1 * 3 + 2] - positions[p2 * 3 + 2];
      bendingRestLengths[i] = Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    return {
      distancePairs: new Uint32Array(distanceList),
      restLengths,
      bendingPairs: new Uint32Array(bendingList),
      bendingRestLengths
    };
  }

  /**
   * Applies the simulated particle positions directly back to the Three.js mesh.
   * Recomputes vertex normals and bounding volumes in-place without memory allocation.
   */
  public static applySimulationToMesh(simGarment: SimulatedGarment): void {
    const geometry = simGarment.geometry;
    const posAttr = geometry.attributes.position as THREE.BufferAttribute;
    const array = posAttr.array as Float32Array;

    // Mutate buffer array in-place
    array.set(simGarment.particleState.positions);
    posAttr.needsUpdate = true;

    // Recompute surface normals for correct PBR shading and reflections
    geometry.computeVertexNormals();
    if (geometry.attributes.normal) {
      geometry.attributes.normal.needsUpdate = true;
    }

    // Refresh bounding volumes
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
  }

  /**
   * Resets simulated garment to its original rest pose.
   */
  public static resetToRestPose(simGarment: SimulatedGarment): void {
    const p = simGarment.particleState;
    p.positions.set(p.restPositions);
    p.prevPositions.set(p.restPositions);
    p.velocities.fill(0);
    this.applySimulationToMesh(simGarment);
  }
}


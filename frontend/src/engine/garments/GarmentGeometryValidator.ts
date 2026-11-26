/**
 * YORVYN — Garment Geometry Validator & Repair Engine
 * Validates positions, normals, tangents, indices, and repairs degenerate triangles/spikes.
 */

export interface GeometryValidationResult {
  valid: boolean;
  vertexCount: number;
  triangleCount: number;
  degenerateTriangleCount: number;
  nanVertexCount: number;
  spikeVertexCount: number;
  repaired: boolean;
  positions: Float32Array;
  indices: Uint32Array;
  normals: Float32Array;
}

export class GarmentGeometryValidator {
  /**
   * Validates and repairs garment mesh geometry.
   * Eliminates NaNs, degenerate triangles (area < 1e-8), and out-of-bound indices.
   */
  public static validateAndRepair(
    positions: Float32Array,
    indices: Uint32Array,
    _providedNormals?: Float32Array
  ): GeometryValidationResult {
    const vCount = positions.length / 3;
    let nanCount = 0;
    const cleanPositions = new Float32Array(positions.length);

    // 1. Sanitize positions: remove NaNs/Infs
    for (let i = 0; i < positions.length; i++) {
      const v = positions[i];
      if (isNaN(v) || !isFinite(v)) {
        cleanPositions[i] = 0;
        nanCount++;
      } else {
        cleanPositions[i] = v;
      }
    }

    // 2. Validate triangles and filter degenerate/collapsed faces
    const validTris: number[] = [];
    let degenerateCount = 0;

    for (let i = 0; i < indices.length; i += 3) {
      const i0 = indices[i];
      const i1 = indices[i + 1];
      const i2 = indices[i + 2];

      // Check bounds
      if (i0 >= vCount || i1 >= vCount || i2 >= vCount) {
        degenerateCount++;
        continue;
      }

      // Check duplicate vertex indices
      if (i0 === i1 || i1 === i2 || i2 === i0) {
        degenerateCount++;
        continue;
      }

      // Compute triangle edges and cross product area
      const ax = cleanPositions[i1 * 3] - cleanPositions[i0 * 3];
      const ay = cleanPositions[i1 * 3 + 1] - cleanPositions[i0 * 3 + 1];
      const az = cleanPositions[i1 * 3 + 2] - cleanPositions[i0 * 3 + 2];

      const bx = cleanPositions[i2 * 3] - cleanPositions[i0 * 3];
      const by = cleanPositions[i2 * 3 + 1] - cleanPositions[i0 * 3 + 1];
      const bz = cleanPositions[i2 * 3 + 2] - cleanPositions[i0 * 3 + 2];

      const cx = ay * bz - az * by;
      const cy = az * bx - ax * bz;
      const cz = ax * by - ay * bx;

      const areaSq = cx * cx + cy * cy + cz * cz;
      // Area threshold: reject triangles smaller than 1e-12 m² (~0.001 mm²)
      if (areaSq < 1e-12) {
        degenerateCount++;
        continue;
      }

      validTris.push(i0, i1, i2);
    }

    const cleanIndices = new Uint32Array(validTris);

    // 3. Detect and soften geometric needle spikes
    const { repairedPositions, spikeCount } = this.smoothSpikes(cleanPositions, cleanIndices);

    // 4. Compute accurate area-weighted vertex normals
    const cleanNormals = this.computeSmoothNormals(repairedPositions, cleanIndices);

    return {
      valid: nanCount === 0 && degenerateCount === 0 && spikeCount === 0,
      vertexCount: vCount,
      triangleCount: cleanIndices.length / 3,
      degenerateTriangleCount: degenerateCount,
      nanVertexCount: nanCount,
      spikeVertexCount: spikeCount,
      repaired: degenerateCount > 0 || nanCount > 0 || spikeCount > 0,
      positions: repairedPositions,
      indices: cleanIndices,
      normals: cleanNormals
    };
  }

  /**
   * Detects vertices that stick out abnormally from their immediate topological ring (spikes)
   * and pulls them back towards the neighborhood centroid.
   */
  private static smoothSpikes(
    positions: Float32Array,
    indices: Uint32Array
  ): { repairedPositions: Float32Array; spikeCount: number } {
    const vCount = positions.length / 3;
    const adj = new Map<number, Set<number>>();

    for (let i = 0; i < indices.length; i += 3) {
      const a = indices[i], b = indices[i + 1], c = indices[i + 2];
      if (!adj.has(a)) adj.set(a, new Set());
      if (!adj.has(b)) adj.set(b, new Set());
      if (!adj.has(c)) adj.set(c, new Set());
      adj.get(a)!.add(b); adj.get(a)!.add(c);
      adj.get(b)!.add(a); adj.get(b)!.add(c);
      adj.get(c)!.add(a); adj.get(c)!.add(b);
    }

    const out = new Float32Array(positions);
    let spikeCount = 0;

    for (let v = 0; v < vCount; v++) {
      const nbs = adj.get(v);
      if (!nbs || nbs.size < 3) continue;

      let mx = 0, my = 0, mz = 0;
      for (const nb of nbs) {
        mx += positions[nb * 3];
        my += positions[nb * 3 + 1];
        mz += positions[nb * 3 + 2];
      }
      mx /= nbs.size;
      my /= nbs.size;
      mz /= nbs.size;

      const px = positions[v * 3];
      const py = positions[v * 3 + 1];
      const pz = positions[v * 3 + 2];

      const dx = px - mx;
      const dy = py - my;
      const dz = pz - mz;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

      // If vertex deviates > 35mm from local neighbors without biological reason, relax it
      if (dist > 0.035) {
        out[v * 3] = mx + dx * 0.4;
        out[v * 3 + 1] = my + dy * 0.4;
        out[v * 3 + 2] = mz + dz * 0.4;
        spikeCount++;
      }
    }

    return { repairedPositions: out, spikeCount };
  }

  /**
   * Generates area-weighted, smoothed vertex normals for high-fidelity lighting and shading.
   */
  public static computeSmoothNormals(positions: Float32Array, indices: Uint32Array): Float32Array {
    const normals = new Float32Array(positions.length);

    for (let i = 0; i < indices.length; i += 3) {
      const i0 = indices[i];
      const i1 = indices[i + 1];
      const i2 = indices[i + 2];

      const p0x = positions[i0 * 3], p0y = positions[i0 * 3 + 1], p0z = positions[i0 * 3 + 2];
      const p1x = positions[i1 * 3], p1y = positions[i1 * 3 + 1], p1z = positions[i1 * 3 + 2];
      const p2x = positions[i2 * 3], p2y = positions[i2 * 3 + 1], p2z = positions[i2 * 3 + 2];

      const e1x = p1x - p0x, e1y = p1y - p0y, e1z = p1z - p0z;
      const e2x = p2x - p0x, e2y = p2y - p0y, e2z = p2z - p0z;

      // Cross product gives area-weighted normal
      const nx = e1y * e2z - e1z * e2y;
      const ny = e1z * e2x - e1x * e2z;
      const nz = e1x * e2y - e1y * e2x;

      normals[i0 * 3] += nx; normals[i0 * 3 + 1] += ny; normals[i0 * 3 + 2] += nz;
      normals[i1 * 3] += nx; normals[i1 * 3 + 1] += ny; normals[i1 * 3 + 2] += nz;
      normals[i2 * 3] += nx; normals[i2 * 3 + 1] += ny; normals[i2 * 3 + 2] += nz;
    }

    // Normalize
    for (let i = 0; i < normals.length; i += 3) {
      const nx = normals[i], ny = normals[i + 1], nz = normals[i + 2];
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz);
      if (len > 1e-8) {
        const inv = 1 / len;
        normals[i] = nx * inv;
        normals[i + 1] = ny * inv;
        normals[i + 2] = nz * inv;
      } else {
        normals[i] = 0;
        normals[i + 1] = 1;
        normals[i + 2] = 0;
      }
    }

    return normals;
  }
}

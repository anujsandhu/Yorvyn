/**
 * YORVYN — Live Mannequin Camera Director (Phase 6)
 * Computes deterministic, smooth inspection camera framing and angle transitions.
 * Supports Front (0°), Side (90°), Back (180°), Full-Body, and Close-Up Portrait framing.
 */

import * as THREE from 'three';

export interface CameraOrbitState {
  position: THREE.Vector3;
  target: THREE.Vector3;
  distance: number;
  azimuthAngleRad: number;
}

export interface CameraTransitionInterpolation {
  startTime: number;
  durationMs: number;
  startPos: THREE.Vector3;
  targetPos: THREE.Vector3;
  startTarget: THREE.Vector3;
  endTarget: THREE.Vector3;
  isTransitioning: boolean;
}

export class LiveMannequinCameraDirector {
  /**
   * Calculates the camera position for a specific inspection angle around the avatar.
   * angleRad: 0 = Front, Math.PI / 2 = 90° Side profile, Math.PI = 180° Rear inspection.
   */
  public static computeInspectionPosition(
    target: THREE.Vector3,
    distance: number,
    angleRad: number,
    elevationY: number = 0.05
  ): THREE.Vector3 {
    // Spherical coordinates around target: X = sin(angle) * dist, Z = cos(angle) * dist
    const x = target.x + distance * Math.sin(angleRad);
    const z = target.z + distance * Math.cos(angleRad);
    const y = target.y + elevationY;
    return new THREE.Vector3(x, y, z);
  }

  /**
   * Generates camera framing parameters tailored to mannequin stature and view mode.
   */
  public static getFraming(
    viewMode: 'full' | 'portrait',
    characterHeightMeters: number = 1.78
  ): { position: THREE.Vector3; target: THREE.Vector3; distance: number } {
    const H = Math.max(1.2, characterHeightMeters);

    if (viewMode === 'portrait') {
      const target = new THREE.Vector3(0, H * 0.72, 0);
      const position = new THREE.Vector3(0, H * 0.74, 2.20);
      return {
        target,
        position,
        distance: position.distanceTo(target)
      };
    }

    // Full-body view: centers at waist/hips, framing full stature
    const target = new THREE.Vector3(0, H * 0.46, 0);
    const position = new THREE.Vector3(0, H * 0.50, 4.35);
    return {
      target,
      position,
      distance: position.distanceTo(target)
    };
  }

  /**
   * Computes a cubic ease-out interpolation step between camera start and target vectors.
   */
  public static interpolateStep(
    transition: CameraTransitionInterpolation,
    currentTimeMs: number
  ): { position: THREE.Vector3; target: THREE.Vector3; completed: boolean } {
    const elapsed = currentTimeMs - transition.startTime;
    const progress = Math.min(1.0, Math.max(0.0, elapsed / transition.durationMs));
    // Cubic ease-out: 1 - (1 - p)^3
    const ease = 1.0 - Math.pow(1.0 - progress, 3);

    const position = new THREE.Vector3().lerpVectors(
      transition.startPos,
      transition.targetPos,
      ease
    );
    const target = new THREE.Vector3().lerpVectors(
      transition.startTarget,
      transition.endTarget,
      ease
    );

    return {
      position,
      target,
      completed: progress >= 1.0
    };
  }
}


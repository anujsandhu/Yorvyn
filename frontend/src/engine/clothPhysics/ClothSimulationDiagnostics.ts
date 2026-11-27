/**
 * YORVYN — Cloth Simulation Diagnostics (Phase 10)
 * Real-time performance metrics, stability telemetry, and failure telemetry.
 */

import { ClothDiagnosticMetrics } from './types';

export class ClothSimulationDiagnostics {
  private metrics: ClothDiagnosticMetrics = {
    state: 'uninitialized',
    qualityMode: 'balanced',
    fps: 60,
    stepTimeMs: 0,
    particleCount: 0,
    distanceConstraintCount: 0,
    bendingConstraintCount: 0,
    activeCollisionHulls: 0,
    penetrationResolutions: 0,
    maxDisplacementMeters: 0,
    hasExploded: false,
    isDegraded: false,
    fabricProfile: 'cotton'
  };

  private frameCount = 0;
  private lastFpsTime = performance.now();
  private listeners: ((metrics: ClothDiagnosticMetrics) => void)[] = [];

  public updateMetrics(partial: Partial<ClothDiagnosticMetrics>): void {
    Object.assign(this.metrics, partial);

    // Frame rate computation
    this.frameCount++;
    const now = performance.now();
    const elapsed = now - this.lastFpsTime;
    if (elapsed >= 1000) {
      this.metrics.fps = Math.round((this.frameCount * 1000) / elapsed);
      this.frameCount = 0;
      this.lastFpsTime = now;
      this.notifyListeners();
    }
  }

  public getMetrics(): ClothDiagnosticMetrics {
    return { ...this.metrics };
  }

  public subscribe(listener: (metrics: ClothDiagnosticMetrics) => void): () => void {
    this.listeners.push(listener);
    listener(this.metrics);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notifyListeners(): void {
    for (const listener of this.listeners) {
      try {
        listener(this.metrics);
      } catch (e) {
        console.error('[ClothSimulationDiagnostics] Error in listener:', e);
      }
    }
  }

  public formatReport(): string {
    const m = this.metrics;
    return `[ClothPhysics] State: ${m.state.toUpperCase()} | Mode: ${m.qualityMode} | Fabric: ${m.fabricProfile} | FPS: ${m.fps} | Step: ${m.stepTimeMs.toFixed(2)}ms | Particles: ${m.particleCount} | Constraints: ${m.distanceConstraintCount + m.bendingConstraintCount} | PenResolutions: ${m.penetrationResolutions} | Exploded: ${m.hasExploded ? 'YES' : 'No'}`;
  }
}

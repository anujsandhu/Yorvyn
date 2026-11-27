/**
 * YORVYN — Cloth Simulation Quality Manager (Phase 10)
 * Manages adaptive quality modes (High, Balanced, Performance, Preview)
 * and dynamic performance profiling to guarantee 60fps on Apple Silicon M2 hardware.
 */

import { SimulationQualityMode, SimulationQualitySettings } from './types';

export const QUALITY_PRESETS: Record<SimulationQualityMode, SimulationQualitySettings> = {
  high: {
    mode: 'high',
    subSteps: 3,
    solverIterations: 12,
    enableBending: true,
    enableCollisions: true,
    collisionProxyDetail: 'full',
    fixedTimeStep: 1 / 90,
    maxActiveVertices: 4000
  },

  balanced: {
    mode: 'balanced',
    subSteps: 2,
    solverIterations: 8,
    enableBending: true,
    enableCollisions: true,
    collisionProxyDetail: 'full',
    fixedTimeStep: 1 / 60,
    maxActiveVertices: 2500
  },

  performance: {
    mode: 'performance',
    subSteps: 1,
    solverIterations: 4,
    enableBending: false,
    enableCollisions: true,
    collisionProxyDetail: 'simplified',
    fixedTimeStep: 1 / 60,
    maxActiveVertices: 1500
  },

  preview: {
    mode: 'preview',
    subSteps: 1,
    solverIterations: 2,
    enableBending: false,
    enableCollisions: false,
    collisionProxyDetail: 'minimal',
    fixedTimeStep: 1 / 30,
    maxActiveVertices: 800
  }
};

export class ClothSimulationQualityManager {
  private currentMode: SimulationQualityMode;
  private settings: SimulationQualitySettings;
  private recentStepTimes: number[] = [];
  private readonly MAX_SAMPLES = 20;
  private isAutoDegraded: boolean = false;

  constructor(initialMode: SimulationQualityMode = 'balanced') {
    this.currentMode = initialMode;
    this.settings = { ...QUALITY_PRESETS[initialMode] };
  }

  public getSettings(): SimulationQualitySettings {
    return this.settings;
  }

  public getMode(): SimulationQualityMode {
    return this.currentMode;
  }

  public setMode(mode: SimulationQualityMode): void {
    this.currentMode = mode;
    this.settings = { ...QUALITY_PRESETS[mode] };
    this.isAutoDegraded = false;
    this.recentStepTimes = [];
  }

  /**
   * Records a physics step execution duration and checks for adaptive downscaling.
   * If step times consistently exceed 8ms, downscales to a lighter tier to protect 60fps WebGL rendering.
   */
  public recordStepTime(durationMs: number): boolean {
    this.recentStepTimes.push(durationMs);
    if (this.recentStepTimes.length > this.MAX_SAMPLES) {
      this.recentStepTimes.shift();
    }

    if (this.recentStepTimes.length >= this.MAX_SAMPLES) {
      const avg = this.recentStepTimes.reduce((a, b) => a + b, 0) / this.recentStepTimes.length;

      // If average step time exceeds 8.0ms and we are on High or Balanced, adaptively downgrade
      if (avg > 8.0 && !this.isAutoDegraded) {
        if (this.currentMode === 'high') {
          this.setMode('balanced');
          this.isAutoDegraded = true;
          return true;
        } else if (this.currentMode === 'balanced') {
          this.setMode('performance');
          this.isAutoDegraded = true;
          return true;
        }
      }
    }

    return false;
  }

  public isDegraded(): boolean {
    return this.isAutoDegraded;
  }

  public resetAdaptiveState(): void {
    this.recentStepTimes = [];
    this.isAutoDegraded = false;
  }
}


/**
 * Yorvyn Technology Library — Three.js 3D Renderer
 * Viewport lifecycle, ACESFilmic tone mapping, studio lighting, and framing standards.
 */

export interface StudioViewportOptions {
  container: HTMLElement;
  canvas: HTMLCanvasElement;
  enableShadows?: boolean;
  enableDamping?: boolean;
  antialias?: boolean;
  exposure?: number; // default: 1.15
  initialCameraView?: 'full' | 'portrait';
}

export interface CameraFramingConfig {
  position: [number, number, number];
  target: [number, number, number];
  fov: number;
  minDistance: number;
  maxDistance: number;
}

export interface StudioLightingPreset {
  keyLight: { color: string; intensity: number; position: [number, number, number] };
  fillLight: { color: string; intensity: number; position: [number, number, number] };
  rimLight: { color: string; intensity: number; position: [number, number, number] };
  ambientLight: { color: string; intensity: number };
  exposure: number;
}

export interface IThreeStudioRenderer {
  initialize(options: StudioViewportOptions): void;
  resize(width: number, height: number): void;
  setCameraMode(mode: 'full' | 'portrait', characterHeightMeters: number): void;
  zoomIn(): void;
  zoomOut(): void;
  resetView(): void;
  toggleWireframe(enabled: boolean): void;
  dispose(): void;
}

/**
 * Calculates deterministic camera framing preserving full head-to-waist
 * visibility for portrait mode, or full head-to-toe for full-body view.
 */
export function calculateCameraFraming(
  mode: 'full' | 'portrait',
  characterHeightMeters: number = 1.78
): CameraFramingConfig {
  const H = Math.max(1.0, characterHeightMeters);

  if (mode === 'portrait') {
    return {
      position: [0, H * 0.67, 2.45],
      target: [0, H * 0.65, 0],
      fov: 30,
      minDistance: 0.90,
      maxDistance: 6.00
    };
  }

  // Full-body view: center around avatar midpoint
  return {
    position: [0, H * 0.50, 4.45],
    target: [0, H * 0.48, 0],
    fov: 30,
    minDistance: 0.90,
    maxDistance: 6.00
  };
}

export const YORVYN_STUDIO_LIGHTING: StudioLightingPreset = {
  keyLight: {
    color: '#FFFFFF',
    intensity: 1.8,
    position: [2.5, 3.5, 2.5]
  },
  fillLight: {
    color: '#E0F2FE', // subtle light sky blue bounce
    intensity: 1.0,
    position: [-2.5, 2.0, 2.0]
  },
  rimLight: {
    color: '#BAE6FD',
    intensity: 1.4,
    position: [0.0, 3.0, -3.0]
  },
  ambientLight: {
    color: '#F0F9FF',
    intensity: 0.65
  },
  exposure: 1.15
};

export class HeadlessStudioRenderer implements IThreeStudioRenderer {
  private width = 800;
  private height = 600;
  private currentMode: 'full' | 'portrait' = 'portrait';
  private charHeight = 1.70;
  private wireframeEnabled = false;

  public initialize(options: StudioViewportOptions): void {
    this.currentMode = options.initialCameraView ?? 'portrait';
  }

  public resize(width: number, height: number): void {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
  }

  public setCameraMode(mode: 'full' | 'portrait', characterHeightMeters: number): void {
    this.currentMode = mode;
    this.charHeight = characterHeightMeters;
  }

  public zoomIn(): void {
    // Zoom step logic
  }

  public zoomOut(): void {
    // Zoom step logic
  }

  public resetView(): void {
    // Reset view logic
  }

  public toggleWireframe(enabled: boolean): void {
    this.wireframeEnabled = enabled;
  }

  public getFraming(): CameraFramingConfig {
    return calculateCameraFraming(this.currentMode, this.charHeight);
  }

  public getDimensions(): { width: number; height: number } {
    return { width: this.width, height: this.height };
  }

  public isWireframe(): boolean {
    return this.wireframeEnabled;
  }

  public dispose(): void {
    // Cleanup
  }
}

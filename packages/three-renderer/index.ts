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

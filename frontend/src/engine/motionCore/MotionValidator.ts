/**
 * YORVYN MotionCore — Runtime Performance Evaluator & Animated GLB Export Validator
 */

import type {
  AnimatedExportValidation,
  ExportAnimationKind,
  MotionPerformanceTelemetry,
  MotionState,
} from './MotionTypes';
import type { ComputeSelectionSummary } from './ComputeOrchestrator';

export class MotionPerformanceEvaluator {
  private frameTimesMs: number[] = [];
  private simTimesMs: number[] = [];
  private droppedFrames = 0;
  private readonly maxWindow = 120;

  public recordFrame(
    renderFrameMs: number,
    simulationStepMs: number
  ): { p50: number; p95: number; p99: number; fps: number; droppedFrames: number } {
    const rMs = Math.max(0.1, Number.isFinite(renderFrameMs) ? renderFrameMs : 16.67);
    const sMs = Math.max(0, Number.isFinite(simulationStepMs) ? simulationStepMs : 0);
    if (rMs > 34.0) this.droppedFrames++;

    this.frameTimesMs.push(rMs);
    this.simTimesMs.push(sMs);
    if (this.frameTimesMs.length > this.maxWindow) this.frameTimesMs.shift();
    if (this.simTimesMs.length > this.maxWindow) this.simTimesMs.shift();

    const sorted = [...this.frameTimesMs].sort((a, b) => a - b);
    const pct = (q: number) => sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * q))] || rMs;
    const p50 = Number(pct(0.5).toFixed(2));
    const p95 = Number(pct(0.95).toFixed(2));
    const p99 = Number(pct(0.99).toFixed(2));
    const avg = this.frameTimesMs.reduce((a, b) => a + b, 0) / this.frameTimesMs.length;
    const fps = Number((1000 / Math.max(1, avg)).toFixed(1));
    return { p50, p95, p99, fps, droppedFrames: this.droppedFrames };
  }

  public buildTelemetry(
    state: MotionState,
    compute: ComputeSelectionSummary,
    dyn: {
      renderFrameMs: number;
      simulationStepMs: number;
      activeClothVertices: number;
      constraintCount: number;
      collisionCount: number;
      secondaryNodeCount: number;
      workerExecutionMs?: number;
    }
  ): MotionPerformanceTelemetry {
    const stats = this.recordFrame(dyn.renderFrameMs, dyn.simulationStepMs);
    const memPerf = (typeof performance !== 'undefined' ? (performance as any).memory : undefined);
    const memoryMb = memPerf && Number.isFinite(memPerf.usedJSHeapSize)
      ? Number((memPerf.usedJSHeapSize / (1024 * 1024)).toFixed(1))
      : null;

    return {
      state,
      qualityTier: compute.qualityTier,
      renderBackend: compute.renderBackend,
      physicsBackend: compute.physicsBackend,
      webgpuExperimentalOnly: true,
      isSoftwareRendered: compute.isSoftwareRendered,
      renderFrameMs: Number(dyn.renderFrameMs.toFixed(2)),
      simulationStepMs: Number(dyn.simulationStepMs.toFixed(2)),
      p50FrameMs: stats.p50,
      p95FrameMs: stats.p95,
      p99FrameMs: stats.p99,
      fps: stats.fps,
      droppedFrames: stats.droppedFrames,
      activeClothVertices: dyn.activeClothVertices,
      constraintCount: dyn.constraintCount,
      collisionCount: dyn.collisionCount,
      secondaryNodeCount: dyn.secondaryNodeCount,
      workerExecutionMs: dyn.workerExecutionMs ?? 0,
      memoryMb,
    };
  }

  public reset(): void {
    this.frameTimesMs = [];
    this.simTimesMs = [];
    this.droppedFrames = 0;
  }
}

/**
 * Validates binary GLB v2 payload and classifies honest export mode
 * without claiming baked cloth deformation unless morph/vertex delta tracks exist.
 */
export function validateAnimatedGLBExport(
  glbBytes: Uint8Array,
  opts?: { claimedBakedCloth?: boolean }
): AnimatedExportValidation {
  const issues: string[] = [];
  if (!glbBytes || glbBytes.byteLength < 20) {
    return {
      isValid: false,
      exportKind: 'static_garment_export',
      clipCount: 0,
      boneCount: 0,
      hasGarmentAttachment: false,
      hasBakedClothDeformation: false,
      byteLength: glbBytes?.byteLength || 0,
      issues: ['GLB buffer is empty or truncated.'],
    };
  }

  const dv = new DataView(glbBytes.buffer, glbBytes.byteOffset, glbBytes.byteLength);
  const magic = dv.getUint32(0, true);
  const version = dv.getUint32(4, true);
  const jsonLen = dv.getUint32(12, true);
  if (magic !== 0x46546c67 || version !== 2 || 20 + jsonLen > glbBytes.byteLength) {
    return {
      isValid: false,
      exportKind: 'static_garment_export',
      clipCount: 0,
      boneCount: 0,
      hasGarmentAttachment: false,
      hasBakedClothDeformation: false,
      byteLength: glbBytes.byteLength,
      issues: ['Invalid binary glTF 2.0 header.'],
    };
  }

  const gltf = JSON.parse(new TextDecoder().decode(glbBytes.subarray(20, 20 + jsonLen)));
  const skins: any[] = gltf.skins || [];
  const animations: any[] = gltf.animations || [];
  const nodes: any[] = gltf.nodes || [];
  const meshes: any[] = gltf.meshes || [];

  const boneCount = skins.reduce((sum, s) => sum + (Array.isArray(s.joints) ? s.joints.length : 0), 0);
  const hasGarmentAttachment = nodes.some(
    (n) => n?.extras?.component_id || n?.extras?.isCustomAiGarment || n?.extras?.garment_attached
  );
  const hasBakedClothDeformation = animations.some((anim) =>
    (anim.channels || []).some((ch: any) => ch?.target?.path === 'weights') &&
    meshes.some((m) => (m.primitives || []).some((p: any) => Array.isArray(p.targets) && p.targets.length > 0))
  );

  if (opts?.claimedBakedCloth && !hasBakedClothDeformation) {
    issues.push('Exported asset contains skeletal/blend-shape channels without validated baked cloth simulation tracks.');
  }

  let exportKind: ExportAnimationKind = 'static_garment_export';
  if (animations.length > 0) {
    exportKind = hasBakedClothDeformation
      ? 'baked_simulation_export'
      : hasGarmentAttachment
      ? 'skeletal_with_garment_deformation'
      : 'skeletal_animation_export';
  }

  return {
    isValid: issues.length === 0,
    exportKind,
    clipCount: animations.length,
    boneCount,
    hasGarmentAttachment,
    hasBakedClothDeformation,
    byteLength: glbBytes.byteLength,
    issues,
  };
}

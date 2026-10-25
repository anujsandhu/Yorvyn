/**
 * Yorvyn Technology Library — AI Adapters
 * Decoupled inference worker interface separating local CPU pipelines from remote GPU clusters.
 */

import { TemporaryGarmentInput, GarmentUnderstandingResult } from '../garment-reconstruction';
import { Garment3DAsset } from '../garment-core';
import { JobProgressInfo } from '../shared-types';

export type WorkerExecutionTarget = 'local_cpu_worker' | 'remote_gpu_cluster';

export interface IAIWorkerAdapter {
  readonly adapterName: string;
  readonly executionTarget: WorkerExecutionTarget;
  readonly isAvailable: boolean;

  /** Health-check worker latency and memory availability */
  checkHealth(): Promise<{ available: boolean; latencyMs: number; vramMb?: number }>;

  /** Dispatch 3D garment generation job to the target worker */
  processGenerationJob(
    input: TemporaryGarmentInput,
    analysis: GarmentUnderstandingResult,
    onProgress: (info: JobProgressInfo) => void
  ): Promise<Garment3DAsset>;
}

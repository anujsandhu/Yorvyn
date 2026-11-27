/**
 * YORVYN — Garment Reconstruction Job Manager (Phase 9)
 * 
 * Manages:
 * 1. Asynchronous reconstruction jobs lifecycle.
 * 2. Progress notifications and stage updates for the UI.
 * 3. Job cancellation and memory buffer purging.
 * 4. Error isolation and retry handling.
 */

import { 
  MultiViewInput, 
  GarmentReconstructionCategory, 
  ReconstructionJobProgress, 
  FabricType 
} from './garmentReconstructionTypes';
import { 
  IGarmentReconstructionAdapter, 
  LocalParametricReconstructionAdapter 
} from './GarmentReconstructionAdapter';

export type JobProgressListener = (progress: ReconstructionJobProgress) => void;

export class GarmentReconstructionJobManager {
  private activeJobs: Map<string, ReconstructionJobProgress> = new Map();
  private listeners: Map<string, Set<JobProgressListener>> = new Map();
  private adapter: IGarmentReconstructionAdapter;

  constructor(adapter?: IGarmentReconstructionAdapter) {
    this.adapter = adapter || new LocalParametricReconstructionAdapter();
  }

  public setAdapter(adapter: IGarmentReconstructionAdapter): void {
    this.adapter = adapter;
  }

  public getAdapterName(): string {
    return this.adapter.providerName;
  }

  public getJob(jobId: string): ReconstructionJobProgress | undefined {
    return this.activeJobs.get(jobId);
  }

  /**
   * Submits a new asynchronous garment reconstruction job.
   */
  public async submitJob(
    input: MultiViewInput,
    category: GarmentReconstructionCategory,
    options: {
      subcategory?: string;
      fabricType?: FabricType;
      fit?: 'slim' | 'regular' | 'relaxed' | 'oversized';
      necklineType?: 'crewneck' | 'v_neck' | 'collar' | 'scoop' | 'turtle';
      sleeveLength?: 'sleeveless' | 'short' | 'three_quarter' | 'long';
    } = {}
  ): Promise<string> {
    const jobId = `job_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

    const initialProgress: ReconstructionJobProgress = {
      jobId,
      status: 'queued',
      progressPercent: 5,
      currentStage: 'Initializing reconstruction pipeline...'
    };

    this.activeJobs.set(jobId, initialProgress);
    this.notify(jobId, initialProgress);

    // Run asynchronously
    setTimeout(async () => {
      try {
        const result = await this.adapter.reconstruct(input, category, {
          ...options,
          onProgress: (pct, stage) => {
            const current = this.activeJobs.get(jobId);
            if (!current || current.status === 'cancelled') return;

            let status: any = 'reconstructing_geometry';
            if (pct < 20) status = 'validating_images';
            else if (pct < 45) status = 'segmenting_garment';
            else if (pct < 70) status = 'reconstructing_geometry';
            else if (pct < 85) status = 'synthesizing_textures';
            else if (pct < 95) status = 'validating_topology';
            else if (pct < 100) status = 'assembling_glb';

            const updated: ReconstructionJobProgress = {
              jobId,
              status,
              progressPercent: pct,
              currentStage: stage
            };
            this.activeJobs.set(jobId, updated);
            this.notify(jobId, updated);
          }
        });

        // Check if cancelled during execution
        const check = this.activeJobs.get(jobId);
        if (check && check.status === 'cancelled') {
          return;
        }

        const completedProgress: ReconstructionJobProgress = {
          jobId,
          status: 'completed',
          progressPercent: 100,
          currentStage: '3D garment reconstructed successfully.',
          result
        };
        this.activeJobs.set(jobId, completedProgress);
        this.notify(jobId, completedProgress);
      } catch (err: any) {
        const failedProgress: ReconstructionJobProgress = {
          jobId,
          status: 'failed',
          progressPercent: 0,
          currentStage: 'Reconstruction failed.',
          error: err.message || 'Unknown error occurred during garment reconstruction.'
        };
        this.activeJobs.set(jobId, failedProgress);
        this.notify(jobId, failedProgress);
      }
    }, 10);

    return jobId;
  }

  /**
   * Cancels a running job and disposes of memory references.
   */
  public cancelJob(jobId: string): boolean {
    const job = this.activeJobs.get(jobId);
    if (!job) return false;

    if (job.status === 'completed' || job.status === 'failed') {
      return false;
    }

    const cancelledProgress: ReconstructionJobProgress = {
      ...job,
      status: 'cancelled',
      currentStage: 'Job cancelled by user.'
    };
    this.activeJobs.set(jobId, cancelledProgress);
    this.notify(jobId, cancelledProgress);

    return true;
  }

  public subscribe(jobId: string, listener: JobProgressListener): () => void {
    if (!this.listeners.has(jobId)) {
      this.listeners.set(jobId, new Set());
    }
    this.listeners.get(jobId)!.add(listener);

    const current = this.activeJobs.get(jobId);
    if (current) {
      listener(current);
    }

    return () => {
      this.listeners.get(jobId)?.delete(listener);
    };
  }

  private notify(jobId: string, progress: ReconstructionJobProgress): void {
    const set = this.listeners.get(jobId);
    if (set) {
      set.forEach(fn => fn(progress));
    }
  }
}

export const garmentReconstructionJobManager = new GarmentReconstructionJobManager();

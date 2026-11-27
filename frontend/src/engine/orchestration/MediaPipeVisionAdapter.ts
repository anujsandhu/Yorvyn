/**
 * YORVYN — MediaPipe Tasks Vision Adapter (Phase 13)
 * Provides client-side pose and anatomical landmark estimation for
 * garment positioning, avatar alignment, and framing checks.
 */

export interface PoseLandmark {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}

export interface GarmentAlignmentAnchors {
  shoulderLeft: PoseLandmark;
  shoulderRight: PoseLandmark;
  hipLeft: PoseLandmark;
  hipRight: PoseLandmark;
  neckCenter: PoseLandmark;
  shoulderWidthNormalized: number;
  torsoHeightNormalized: number;
  confidence: number;
}

export class MediaPipeVisionAdapter {
  private static landmarkerInstance: any = null;
  private static isInitializing = false;

  public static async isSupported(): Promise<boolean> {
    return typeof WebAssembly !== 'undefined' && typeof window !== 'undefined';
  }

  /**
   * Lazily loads and initializes PoseLandmarker.
   */
  public static async getPoseLandmarker(): Promise<any> {
    if (this.landmarkerInstance) return this.landmarkerInstance;
    if (this.isInitializing) {
      while (this.isInitializing) {
        await new Promise((r) => setTimeout(r, 50));
      }
      return this.landmarkerInstance;
    }

    this.isInitializing = true;
    try {
      const vision = await import('@mediapipe/tasks-vision');
      const filesetResolver = await vision.FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
      );
      this.landmarkerInstance = await vision.PoseLandmarker.createFromOptions(filesetResolver, {
        baseOptions: {
          modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task',
          delegate: 'GPU'
        },
        runningMode: 'IMAGE',
        numPoses: 1
      });
      return this.landmarkerInstance;
    } catch (e) {
      console.warn('[MediaPipeVisionAdapter] GPU delegate initialization failed, falling back to CPU:', e);
      try {
        const vision = await import('@mediapipe/tasks-vision');
        const filesetResolver = await vision.FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
        );
        this.landmarkerInstance = await vision.PoseLandmarker.createFromOptions(filesetResolver, {
          baseOptions: {
            modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task',
            delegate: 'CPU'
          },
          runningMode: 'IMAGE',
          numPoses: 1
        });
        return this.landmarkerInstance;
      } catch (fallbackErr) {
        console.warn('[MediaPipeVisionAdapter] PoseLandmarker unavailable:', fallbackErr);
        throw fallbackErr;
      }
    } finally {
      this.isInitializing = false;
    }
  }

  /**
   * Extracts anatomical anchors for garment fitting and perspective scaling.
   */
  public static async extractGarmentAnchors(imageElement: HTMLImageElement | HTMLCanvasElement): Promise<GarmentAlignmentAnchors | null> {
    try {
      const landmarker = await this.getPoseLandmarker();
      const result = landmarker.detect(imageElement);

      if (!result || !result.landmarks || result.landmarks.length === 0) {
        return null;
      }

      const landmarks: PoseLandmark[] = result.landmarks[0];
      // MediaPipe Pose landmarks:
      // 11: left shoulder, 12: right shoulder
      // 23: left hip, 24: right hip
      const lShoulder = landmarks[11];
      const rShoulder = landmarks[12];
      const lHip = landmarks[23];
      const rHip = landmarks[24];

      if (!lShoulder || !rShoulder || !lHip || !rHip) {
        return null;
      }

      const neckCenter: PoseLandmark = {
        x: (lShoulder.x + rShoulder.x) / 2,
        y: (lShoulder.y + rShoulder.y) / 2,
        z: (lShoulder.z + rShoulder.z) / 2,
        visibility: Math.min(lShoulder.visibility || 1, rShoulder.visibility || 1)
      };

      const dx = rShoulder.x - lShoulder.x;
      const dy = rShoulder.y - lShoulder.y;
      const shoulderWidth = Math.sqrt(dx * dx + dy * dy);

      const hipCenterY = (lHip.y + rHip.y) / 2;
      const torsoHeight = Math.abs(hipCenterY - neckCenter.y);

      return {
        shoulderLeft: lShoulder,
        shoulderRight: rShoulder,
        hipLeft: lHip,
        hipRight: rHip,
        neckCenter,
        shoulderWidthNormalized: Math.round(shoulderWidth * 1000) / 1000,
        torsoHeightNormalized: Math.round(torsoHeight * 1000) / 1000,
        confidence: Math.round(((lShoulder.visibility || 0.9) + (rShoulder.visibility || 0.9)) / 2 * 100) / 100
      };
    } catch {
      return null;
    }
  }
}


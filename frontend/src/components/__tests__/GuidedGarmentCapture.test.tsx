/**
 * Phase 17.5 Frontend Tests — Live Frame Analyzer, GuidedGarmentCapture & Capture API Client.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { analyzeLivePreviewImageData } from '../../utils/captureFrameAnalyzer';
import { GuidedGarmentCapture } from '../capture/GuidedGarmentCapture';
import { intelligenceApi, intelligenceHttp } from '../../services/intelligenceApi';

describe('Phase 17.5 Live Capture Frame Analyzer', () => {
  it('flags dark underexposed frames with clear lighting guidance', () => {
    const w = 64;
    const h = 64;
    const data = new Uint8ClampedArray(w * h * 4).fill(15);
    for (let i = 3; i < data.length; i += 4) data[i] = 255;
    const res = analyzeLivePreviewImageData(data, w, h);
    expect(res.usable).toBe(false);
    expect(res.primaryIssue).toBe('poor_lighting');
    expect(res.instruction.toLowerCase()).toContain('lighting');
  });

  it('flags flat blurry frames without edges cleanly', () => {
    const w = 64;
    const h = 64;
    const data = new Uint8ClampedArray(w * h * 4);
    for (let i = 0; i < w * h; i++) {
      data[i * 4] = 130;
      data[i * 4 + 1] = 130;
      data[i * 4 + 2] = 130;
      data[i * 4 + 3] = 255;
    }
    const res = analyzeLivePreviewImageData(data, w, h);
    expect(res.usable).toBe(false);
    expect(res.primaryIssue).toBe('blur_detected');
  });

  it('accepts sharp, well-lit, centered garment silhouettes without edge clipping', () => {
    const w = 64;
    const h = 64;
    const data = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const p = (y * w + x) * 4;
        const insideGarment = x >= 14 && x <= 50 && y >= 10 && y <= 52;
        if (insideGarment) {
          const stripe = ((x + y) % 4 < 2) ? 35 : 85;
          data[p] = stripe;
          data[p + 1] = stripe + 20;
          data[p + 2] = stripe + 60;
        } else {
          data[p] = 235;
          data[p + 1] = 235;
          data[p + 2] = 235;
        }
        data[p + 3] = 255;
      }
    }
    const res = analyzeLivePreviewImageData(data, w, h);
    expect(res.usable).toBe(true);
    expect(res.primaryIssue).toBeNull();
    expect(res.sharpness).toBeGreaterThanOrEqual(0.22);
    expect(res.exposure).toBeGreaterThanOrEqual(0.42);
  });
});

describe('Phase 17.5 GuidedGarmentCapture & Intelligence Capture API', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('exports GuidedGarmentCapture component and calls capture endpoints cleanly', async () => {
    expect(typeof GuidedGarmentCapture).toBe('function');
    const postSpy = vi.spyOn(intelligenceHttp, 'post').mockResolvedValue({
      data: { session_id: 'cap_fe_1', readiness: { outcome: 'MORE_EVIDENCE_REQUIRED' } },
    });
    const getSpy = vi.spyOn(intelligenceHttp, 'get').mockResolvedValue({
      data: { session_id: 'cap_fe_1', images: [] },
    });
    const delSpy = vi.spyOn(intelligenceHttp, 'delete').mockResolvedValue({
      data: { deleted: true },
    });

    const created = await intelligenceApi.createCaptureSession({
      garment_category: 'tops',
      capture_mode: 'hanger',
    });
    expect(created.session_id).toBe('cap_fe_1');
    expect(postSpy).toHaveBeenCalledWith('/capture/sessions', {
      garment_category: 'tops',
      capture_mode: 'hanger',
    });

    await intelligenceApi.getCaptureSession('cap_fe_1');
    expect(getSpy).toHaveBeenCalledWith('/capture/sessions/cap_fe_1');

    await intelligenceApi.evaluateCaptureReadiness('cap_fe_1');
    expect(postSpy).toHaveBeenCalledWith('/capture/sessions/cap_fe_1/evaluate');

    await intelligenceApi.finalizeCaptureSession('cap_fe_1', 'idem_1');
    expect(postSpy).toHaveBeenCalledWith('/capture/sessions/cap_fe_1/finalize', {
      idempotency_key: 'idem_1',
    });

    await intelligenceApi.cancelCaptureSession('cap_fe_1');
    expect(delSpy).toHaveBeenCalledWith('/capture/sessions/cap_fe_1');
  });
});

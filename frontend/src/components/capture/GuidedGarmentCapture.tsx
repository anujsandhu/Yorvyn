/**
 * YORVYN Phase 17.5 — Guided Live Garment Capture Component.
 *
 * Implements explicit-permission camera preview, front/back switching, adaptive multi-view
 * checklists (Hanger / Mannequin / Flat-Lay / Worn), throttled local quality feedback,
 * deliberate still capture, server-authoritative Reconstruction Readiness Gate,
 * and idempotent durable reconstruction handoff.
 */
import React, { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { intelligenceApi } from '../../services/intelligenceApi';
import { analyzeLivePreviewImageData, LiveFrameQualityMetrics } from '../../utils/captureFrameAnalyzer';

export type GuidedCaptureMode = 'hanger' | 'mannequin' | 'flat_lay' | 'worn';

interface GuidedGarmentCaptureProps {
  initialCategory?: string;
  onJobCreated: (jobId: string, readiness?: any) => void;
  onSwitchToUpload?: () => void;
}

const CAPTURE_MODES: Array<{ id: GuidedCaptureMode; label: string; summary: string }> = [
  { id: 'hanger', label: 'Hanger Mode', summary: 'Hanging cleanly on a plain background' },
  { id: 'mannequin', label: 'Mannequin Mode', summary: 'Upright mannequin with clear seams' },
  { id: 'flat_lay', label: 'Flat-Lay Mode', summary: 'Flat surface (front/back; side volume inferred)' },
  { id: 'worn', label: 'Worn-Garment Mode', summary: 'Neutral pose, avoid unnecessary face framing' },
];

const CATEGORIES = [
  { id: 'tops', label: 'T-Shirt / Top' },
  { id: 'bottoms', label: 'Trousers / Jeans' },
  { id: 'outerwear', label: 'Jacket / Outerwear' },
  { id: 'dresses_and_skirts', label: 'Dress / Skirt' },
  { id: 'footwear', label: 'Footwear' },
];

export const GuidedGarmentCapture: React.FC<GuidedGarmentCaptureProps> = ({
  initialCategory = 'tops',
  onJobCreated,
  onSwitchToUpload,
}) => {
  const [category, setCategory] = useState(initialCategory);
  const [captureMode, setCaptureMode] = useState<GuidedCaptureMode>('hanger');
  const [session, setSession] = useState<any | null>(null);
  const [readiness, setReadiness] = useState<any | null>(null);
  const [capturedViews, setCapturedViews] = useState<any[]>([]);
  const [activeView, setActiveView] = useState<string>('front');

  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [liveMetrics, setLiveMetrics] = useState<LiveFrameQualityMetrics | null>(null);
  const [busy, setBusy] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analysisCanvasRef = useRef<HTMLCanvasElement | null>(null);

  const stopCameraStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  useEffect(() => {
    return () => {
      stopCameraStream();
    };
  }, []);

  // Throttled (~350ms) local preview analysis — never uploads preview frames continuously
  useEffect(() => {
    if (!cameraActive) return;
    const timer = window.setInterval(() => {
      const vid = videoRef.current;
      if (!vid || vid.readyState < 2 || !vid.videoWidth) return;
      if (!analysisCanvasRef.current) {
        analysisCanvasRef.current = document.createElement('canvas');
      }
      const c = analysisCanvasRef.current;
      c.width = 160;
      c.height = Math.max(90, Math.round((vid.videoHeight / vid.videoWidth) * 160));
      const ctx = c.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(vid, 0, 0, c.width, c.height);
      const imgData = ctx.getImageData(0, 0, c.width, c.height);
      setLiveMetrics(analyzeLivePreviewImageData(imgData.data, c.width, c.height));
    }, 350);
    return () => window.clearInterval(timer);
  }, [cameraActive]);

  const startSession = async (cat = category, mode = captureMode) => {
    setBusy(true);
    setCameraError(null);
    try {
      const created = await intelligenceApi.createCaptureSession({
        garment_category: cat,
        capture_mode: mode,
        consent_granted: true,
      });
      setSession(created);
      setReadiness(created.readiness || null);
      setCapturedViews(created.images || []);
      const firstReq = created?.readiness?.required_views?.[0] || 'front';
      setActiveView(firstReq);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Could not start capture session.');
    } finally {
      setBusy(false);
    }
  };

  const openCamera = async (overrideDeviceId?: string, overrideFacing?: 'environment' | 'user') => {
    setCameraError(null);
    if (typeof window !== 'undefined' && !window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      setCameraError('Live camera requires HTTPS (a secure browser context). Please use Upload Prepared Photos.');
      return;
    }
    if (!navigator?.mediaDevices?.getUserMedia) {
      setCameraError('Camera API is unsupported in this browser. Please switch to Upload Prepared Photos.');
      return;
    }

    stopCameraStream();
    const targetFacing = overrideFacing || facingMode;
    try {
      const constraints: MediaStreamConstraints = {
        audio: false,
        video: overrideDeviceId
          ? { deviceId: { exact: overrideDeviceId }, width: { ideal: 1280 }, height: { ideal: 1600 } }
          : { facingMode: targetFacing, width: { ideal: 1280 }, height: { ideal: 1600 } },
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setCameraActive(true);
      const allDevs = await navigator.mediaDevices.enumerateDevices();
      setDevices(allDevs.filter((d) => d.kind === 'videoinput'));
    } catch (err: any) {
      const name = err?.name || '';
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setCameraError('Camera permission denied. Allow camera access in browser settings or upload prepared photos.');
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setCameraError('No camera detected on this device. Switch to Upload Prepared Photos.');
      } else {
        setCameraError(`Unable to start camera (${err?.message || name || 'unknown error'}).`);
      }
    }
  };

  const handleCaptureStill = async () => {
    if (!session || !videoRef.current || !cameraActive) return;
    const vid = videoRef.current;
    if (!vid.videoWidth || !vid.videoHeight) {
      toast.error('Camera frame not ready yet.');
      return;
    }

    setBusy(true);
    try {
      const snap = document.createElement('canvas');
      snap.width = vid.videoWidth;
      snap.height = vid.videoHeight;
      const ctx = snap.getContext('2d');
      if (!ctx) throw new Error('Canvas unavailable');
      ctx.drawImage(vid, 0, 0, snap.width, snap.height);
      const blob: Blob = await new Promise((resolve, reject) =>
        snap.toBlob((b) => (b ? resolve(b) : reject(new Error('Image capture encoding failed'))), 'image/webp', 0.92)
      );

      const res = await intelligenceApi.uploadCapturedView(session.session_id, blob, activeView);
      const updatedSession = await intelligenceApi.getCaptureSession(session.session_id);
      setSession(updatedSession);
      setCapturedViews(updatedSession.images || []);
      setReadiness(res.readiness || updatedSession.readiness);

      if (res.captured_view?.quality?.usable) {
        toast.success(`Captured ${activeView.replace('_', ' ')} cleanly.`);
        const nextMissing = res.readiness?.missing_required_views?.[0];
        if (nextMissing) setActiveView(nextMissing);
      } else {
        toast.error(res.captured_view?.quality?.corrective_instruction || 'Retake needed for clearer quality.');
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Capture upload failed. Please retry.');
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveView = async (imageId: string) => {
    if (!session) return;
    setBusy(true);
    try {
      const res = await intelligenceApi.deleteCapturedView(session.session_id, imageId);
      const updated = await intelligenceApi.getCaptureSession(session.session_id);
      setSession(updated);
      setCapturedViews(updated.images || []);
      setReadiness(res.readiness);
    } catch {
      toast.error('Could not remove captured view.');
    } finally {
      setBusy(false);
    }
  };

  const handleFinalize = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const res = await intelligenceApi.finalizeCaptureSession(session.session_id);
      stopCameraStream();
      toast.success('Capture verified. Starting 3D garment reconstruction.');
      onJobCreated(res.job_id, res.readiness);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Readiness gate blocked reconstruction.');
    } finally {
      setBusy(false);
    }
  };

  const handleCancelSession = async () => {
    stopCameraStream();
    if (session) {
      await intelligenceApi.cancelCaptureSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setReadiness(null);
    setCapturedViews([]);
  };

  const requiredViews: string[] = readiness?.required_views || ['front', 'back'];
  const recommendedViews: string[] = (readiness?.missing_recommended_views || []).slice(0, 4);
  const viewSlots = Array.from(new Set([...requiredViews, ...recommendedViews, ...capturedViews.map((v) => v.view_label)]));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Step 1 & 2: Garment Category & Capture Mode */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        <div>
          <label className="photo3d-label">1. Garment Category</label>
          <select
            className="photo3d-select"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              if (session) void startSession(e.target.value, captureMode);
            }}
          >
            {CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="photo3d-label">2. Capture Method</label>
          <select
            className="photo3d-select"
            value={captureMode}
            onChange={(e) => {
              const m = e.target.value as GuidedCaptureMode;
              setCaptureMode(m);
              if (session) void startSession(category, m);
            }}
          >
            {CAPTURE_MODES.map((m) => (
              <option key={m.id} value={m.id}>{m.label} — {m.summary}</option>
            ))}
          </select>
        </div>
      </div>

      {!session ? (
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button type="button" className="photo3d-btn-primary" disabled={busy} onClick={() => void startSession()}>
            Start Guided Capture Session
          </button>
          {onSwitchToUpload && (
            <button type="button" className="photo3d-btn-ghost" onClick={onSwitchToUpload}>
              Use Prepared Photos Instead
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Instructions & Privacy Banner */}
          <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(15,23,42,0.04)', fontSize: '0.85rem' }}>
            <strong>Capture Instructions ({CAPTURE_MODES.find((m) => m.id === captureMode)?.label}):</strong>
            <ul style={{ margin: '0.35rem 0 0.35rem 1.2rem', padding: 0 }}>
              {(session.mode_instructions || []).map((inst: string, idx: number) => (
                <li key={idx}>{inst}</li>
              ))}
            </ul>
            <div style={{ opacity: 0.8 }}>
              Privacy: Live camera frames stay local; still photos upload only when you click Capture.
            </div>
          </div>

          {/* Camera Controls & Live Preview */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
            {!cameraActive ? (
              <button type="button" className="photo3d-btn-primary" onClick={() => void openCamera()}>
                Open Camera
              </button>
            ) : (
              <>
                <span style={{ padding: '0.2rem 0.6rem', borderRadius: '999px', background: '#16a34a', color: '#fff', fontSize: '0.78rem' }}>
                  Camera Active
                </span>
                <button
                  type="button"
                  className="photo3d-btn-ghost"
                  onClick={() => {
                    const next = facingMode === 'environment' ? 'user' : 'environment';
                    setFacingMode(next);
                    void openCamera(undefined, next);
                  }}
                >
                  Flip Camera
                </button>
                {devices.length > 1 && (
                  <select
                    className="photo3d-select"
                    style={{ maxWidth: '220px' }}
                    value={selectedDeviceId}
                    onChange={(e) => {
                      setSelectedDeviceId(e.target.value);
                      void openCamera(e.target.value);
                    }}
                  >
                    <option value="">Default Camera</option>
                    {devices.map((d, i) => (
                      <option key={d.deviceId} value={d.deviceId}>{d.label || `Camera ${i + 1}`}</option>
                    ))}
                  </select>
                )}
                <button type="button" className="photo3d-btn-ghost" onClick={stopCameraStream}>
                  Close Camera
                </button>
              </>
            )}
            <button type="button" className="photo3d-btn-ghost" onClick={() => void handleCancelSession()}>
              Cancel Session
            </button>
          </div>

          {cameraError && (
            <div className="photo3d-error-banner" role="alert">
              <span>{cameraError}</span>
            </div>
          )}

          {cameraActive && (
            <div style={{ position: 'relative', borderRadius: '10px', overflow: 'hidden', background: '#0f172a', maxHeight: '360px' }}>
              <video ref={videoRef} playsInline muted style={{ width: '100%', maxHeight: '360px', objectFit: 'contain', display: 'block' }} />
              {/* Framing Overlay Guide */}
              <div
                style={{
                  position: 'absolute',
                  inset: '8% 18%',
                  border: `2px dashed ${liveMetrics?.usable ? '#22c55e' : '#f59e0b'}`,
                  borderRadius: '12px',
                  pointerEvents: 'none',
                }}
              />
              {liveMetrics && (
                <div
                  style={{
                    position: 'absolute',
                    left: 12,
                    right: 12,
                    bottom: 12,
                    padding: '0.5rem 0.75rem',
                    borderRadius: '8px',
                    background: 'rgba(15,23,42,0.84)',
                    color: '#fff',
                    fontSize: '0.84rem',
                  }}
                >
                  <div><strong>Next:</strong> {liveMetrics.instruction}</div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.85, marginTop: '0.2rem' }}>
                    Sharpness: {Math.round(liveMetrics.sharpness * 100)}% | Lighting: {Math.round(liveMetrics.exposure * 100)}% | Visibility: {Math.round(liveMetrics.garmentVisibility * 100)}%
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Adaptive Multi-View Checklist & Deliberate Capture */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
            {viewSlots.map((slot) => {
              const rec = capturedViews.find((v) => v.view_label === slot);
              const isReq = requiredViews.includes(slot);
              const isSelected = activeView === slot;
              return (
                <button
                  key={slot}
                  type="button"
                  onClick={() => setActiveView(slot)}
                  className={isSelected ? 'photo3d-btn-primary' : 'photo3d-btn-ghost'}
                  style={{ fontSize: '0.8rem', padding: '0.35rem 0.65rem' }}
                >
                  {slot.replace('_', ' ')} {isReq ? '*' : ''} {rec ? (rec.quality?.usable ? '✓' : '!') : ''}
                </button>
              );
            })}
          </div>

          {cameraActive && (
            <button type="button" className="photo3d-btn-primary" disabled={busy} onClick={() => void handleCaptureStill()}>
              {busy ? 'Validating...' : `Capture ${activeView.replace('_', ' ')}`}
            </button>
          )}

          {/* Captured Views & Quality Breakdown */}
          {capturedViews.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {capturedViews.map((v) => (
                <div key={v.image_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.45rem 0.65rem', borderRadius: '6px', border: '1px solid rgba(148,163,184,0.35)', fontSize: '0.82rem' }}>
                  <div>
                    <strong>{v.view_label}</strong> ({v.evidence_state}) — Sharp {Math.round(v.quality.sharpness * 100)}%, Light {Math.round(v.quality.exposure * 100)}%
                    {v.quality.corrective_instruction && (
                      <div style={{ color: '#b45309' }}>{v.quality.corrective_instruction}</div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button type="button" className="photo3d-btn-ghost" onClick={() => setActiveView(v.view_label)}>Retake</button>
                    <button type="button" className="photo3d-btn-ghost" onClick={() => void handleRemoveView(v.image_id)}>Remove</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Server-Side Reconstruction Readiness Gate */}
          {readiness && (
            <div style={{ padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(148,163,184,0.45)', fontSize: '0.85rem' }}>
              <div><strong>Readiness Status:</strong> {readiness.outcome} ({readiness.session_status})</div>
              <div style={{ marginTop: '0.2rem' }}>{readiness.summary_reason}</div>
              {readiness.next_instruction && (
                <div style={{ marginTop: '0.2rem' }}><strong>Guidance:</strong> {readiness.next_instruction}</div>
              )}
              {(readiness.limitations || []).length > 0 && (
                <ul style={{ margin: '0.35rem 0 0 1.2rem', padding: 0, opacity: 0.85 }}>
                  {readiness.limitations.map((lim: string, i: number) => <li key={i}>{lim}</li>)}
                </ul>
              )}
              <div style={{ marginTop: '0.65rem' }}>
                <button
                  type="button"
                  className="photo3d-btn-primary"
                  disabled={busy || !readiness.can_reconstruct}
                  onClick={() => void handleFinalize()}
                >
                  Generate 3D Garment
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

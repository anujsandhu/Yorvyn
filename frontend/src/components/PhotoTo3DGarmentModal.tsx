/**
 * Yorvyn — AI Photo-to-3D Garment Generator Modal
 * Complete end-to-end user workflow:
 * 1. Upload front (and optional back) garment photograph.
 * 2. Asynchronous AI reconstruction progress tracking.
 * 3. Interactive rotatable 3D preview of the generated garment.
 * 4. Approval and saving to My Wardrobe (original photo is permanently deleted).
 */

import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { 
  Upload, X, Check, AlertCircle, RefreshCw, Sparkles, 
  ShieldCheck, Eye, Save, Shirt, ChevronRight
} from 'lucide-react';
import { fashionApi } from '../services/fashionApi';
import { GarmentGenJob, GarmentGenResult } from '../types/fashion';
import './PhotoTo3DGarmentModal.css';

interface PhotoTo3DGarmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGarmentSaved: (savedItem: any) => void;
  onWearImmediately?: (savedItem: any) => void;
}

type ModalStep = 'upload' | 'processing' | 'preview';

export const PhotoTo3DGarmentModal: React.FC<PhotoTo3DGarmentModalProps> = ({
  isOpen,
  onClose,
  onGarmentSaved,
  onWearImmediately
}) => {
  // Wizard state
  const [step, setStep] = useState<ModalStep>('upload');
  const [category, setCategory] = useState<string>('top');
  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [frontPreviewUrl, setFrontPreviewUrl] = useState<string | null>(null);
  const [backPreviewUrl, setBackPreviewUrl] = useState<string | null>(null);

  // Job progress state
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [currentStage, setCurrentStage] = useState<string>('Initializing AI generation...');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GarmentGenResult | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // 3D Preview Canvas refs
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const previewSceneRef = useRef<THREE.Scene | null>(null);
  const previewRendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const previewControlsRef = useRef<OrbitControls | null>(null);
  const animFrameIdRef = useRef<number | null>(null);

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      if (frontPreviewUrl) URL.revokeObjectURL(frontPreviewUrl);
      if (backPreviewUrl) URL.revokeObjectURL(backPreviewUrl);
    };
  }, [frontPreviewUrl, backPreviewUrl]);

  // Handle Front File selection
  const handleFrontFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      setError('Image exceeds 15MB limit. Please select a smaller photo.');
      return;
    }
    setError(null);
    setFrontFile(file);
    if (frontPreviewUrl) URL.revokeObjectURL(frontPreviewUrl);
    setFrontPreviewUrl(URL.createObjectURL(file));
  };

  // Handle Back File selection
  const handleBackFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      setError('Image exceeds 15MB limit.');
      return;
    }
    setBackFile(file);
    if (backPreviewUrl) URL.revokeObjectURL(backPreviewUrl);
    setBackPreviewUrl(URL.createObjectURL(file));
  };

  // Start Generation
  const handleStartGeneration = async () => {
    if (!frontFile) {
      setError('Please upload at least a front photograph of the garment.');
      return;
    }

    setError(null);
    setStep('processing');
    setProgress(5);
    setCurrentStage('Uploading photo to private processing worker...');

    try {
      const response = await fashionApi.createGarment3DJob(frontFile, category, backFile || undefined);
      setJobId(response.job_id);

      // Start Polling Job
      pollJobStatus(response.job_id);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to submit garment generation job.');
      setStep('upload');
    }
  };

  // Polling logic
  const pollJobStatus = (id: string) => {
    const interval = setInterval(async () => {
      try {
        const job: GarmentGenJob = await fashionApi.getGarment3DJobStatus(id);

        setProgress(job.progress);
        setCurrentStage(job.current_stage);

        if (job.status === 'completed' && job.result) {
          clearInterval(interval);
          setResult(job.result);
          setStep('preview');
        } else if (job.status === 'failed') {
          clearInterval(interval);
          setError(job.error || 'Garment reconstruction failed. Please check image contrast and try again.');
          setStep('upload');
        } else if (job.status === 'cancelled') {
          clearInterval(interval);
          setStep('upload');
        }
      } catch (pollErr: any) {
        clearInterval(interval);
        setError('Lost connection to processing worker. Please retry.');
        setStep('upload');
      }
    }, 600);
  };

  // Cancel Job
  const handleCancelJob = async () => {
    if (jobId) {
      try {
        await fashionApi.cancelGarment3DJob(jobId);
      } catch (e) {
        // ignore
      }
    }
    setStep('upload');
    setProgress(0);
    setJobId(null);
  };

  // Initialize Rotatable 3D Preview when step is 'preview'
  useEffect(() => {
    if (step !== 'preview' || !result || !previewCanvasRef.current) return;

    const canvas = previewCanvasRef.current;
    const width = canvas.parentElement?.clientWidth || 400;
    const height = canvas.parentElement?.clientHeight || 400;

    // 1. Renderer
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    previewRendererRef.current = renderer;

    // 2. Scene
    const scene = new THREE.Scene();
    previewSceneRef.current = scene;

    // 3. Camera
    const camera = new THREE.PerspectiveCamera(34, width / height, 0.05, 20);
    camera.position.set(0, 0, 1.8);

    // 4. Controls
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.5;
    controls.maxDistance = 3.5;
    controls.minDistance = 0.6;
    previewControlsRef.current = controls;

    // 5. Studio Lighting
    const ambLight = new THREE.AmbientLight(0xffffff, 1.1);
    scene.add(ambLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.8);
    dirLight.position.set(1.5, 2.5, 2.0);
    scene.add(dirLight);

    const rimLight = new THREE.DirectionalLight(0xbae6fd, 1.2);
    rimLight.position.set(-1.8, 1.2, -1.5);
    scene.add(rimLight);

    // 6. Load Generated GLB
    const loader = new GLTFLoader();
    loader.load(result.glb_url, (gltf) => {
      const model = gltf.scene;

      // Center model bounding box around origin for comfortable rotation
      const box = new THREE.Box3().setFromObject(model);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());

      model.position.x += (model.position.x - center.x);
      model.position.y += (model.position.y - center.y);
      model.position.z += (model.position.z - center.z);

      const maxDim = Math.max(size.x, size.y, size.z);
      if (maxDim > 0) {
        const targetScale = 1.0 / maxDim;
        model.scale.setScalar(targetScale * 0.95);
      }

      scene.add(model);
    });

    // 7. Render loop
    const animate = () => {
      animFrameIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      renderer.dispose();
    };
  }, [step, result]);

  // Save to My Wardrobe
  const handleSaveToWardrobe = async () => {
    if (!jobId || !result) return;
    setIsSaving(true);
    try {
      const saveResponse = await fashionApi.saveGarment3DToWardrobe(jobId);
      setSavedSuccess(true);
      onGarmentSaved(saveResponse.item);
    } catch (err: any) {
      setError('Failed to save 3D garment to My Wardrobe.');
    } finally {
      setIsSaving(false);
    }
  };

  // Reset wizard for another garment
  const handleReset = () => {
    setStep('upload');
    setFrontFile(null);
    setBackFile(null);
    if (frontPreviewUrl) URL.revokeObjectURL(frontPreviewUrl);
    if (backPreviewUrl) URL.revokeObjectURL(backPreviewUrl);
    setFrontPreviewUrl(null);
    setBackPreviewUrl(null);
    setResult(null);
    setSavedSuccess(false);
    setError(null);
    setJobId(null);
  };

  if (!isOpen) return null;

  return (
    <div className="photo3d-modal-overlay" onClick={onClose} aria-modal="true" role="dialog">
      <div className="photo3d-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="photo3d-modal-header">
          <div className="photo3d-header-title">
            <span className="photo3d-brand-badge">
              <Sparkles size={14} className="sparkle-icon" /> Yorvyn Atelier AI
            </span>
            <h2>Photo to 3D Garment</h2>
          </div>
          <button className="photo3d-close-btn" onClick={onClose} aria-label="Close Modal">
            <X size={20} />
          </button>
        </header>

        {/* Error Alert */}
        {error && (
          <div className="photo3d-error-banner">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* ── STEP 1: UPLOAD ── */}
        {step === 'upload' && (
          <div className="photo3d-step-body">
            <p className="photo3d-intro-text">
              Transform your own clothing photographs into a wearable 3D digital garment for your Yorvyn avatar.
            </p>

            {/* Category Selector */}
            <div className="photo3d-form-group">
              <label className="photo3d-label">Garment Category</label>
              <div className="photo3d-category-pill-row">
                {[
                  { id: 'top', label: 'Tops & Shirts' },
                  { id: 'bottom', label: 'Trousers & Pants' },
                  { id: 'outerwear', label: 'Jackets & Coats' },
                  { id: 'dress', label: 'Dresses' },
                  { id: 'skirt', label: 'Skirts' }
                ].map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    className={`photo3d-cat-pill ${category === cat.id ? 'active' : ''}`}
                    onClick={() => setCategory(cat.id)}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Photo Upload Dropzones */}
            <div className="photo3d-upload-grid">
              {/* Front Photo (Required) */}
              <div className="photo3d-dropzone-wrap">
                <label className="photo3d-label">
                  Front Photograph <span className="photo3d-required-tag">Required</span>
                </label>
                <label className={`photo3d-dropzone ${frontPreviewUrl ? 'has-file' : ''}`}>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={handleFrontFileChange}
                    className="photo3d-hidden-input"
                  />
                  {frontPreviewUrl ? (
                    <div className="photo3d-preview-thumb">
                      <img src={frontPreviewUrl} alt="Front View" />
                      <div className="photo3d-thumb-overlay">Click to change</div>
                    </div>
                  ) : (
                    <div className="photo3d-dropzone-prompt">
                      <div className="photo3d-upload-circle">
                        <Upload size={22} />
                      </div>
                      <span className="photo3d-drop-headline">Upload Front Photo</span>
                      <span className="photo3d-drop-sub">PNG, JPG, or WEBP up to 15MB</span>
                    </div>
                  )}
                </label>
              </div>

              {/* Back Photo (Optional) */}
              <div className="photo3d-dropzone-wrap">
                <label className="photo3d-label">
                  Back Photograph <span className="photo3d-optional-tag">Optional</span>
                </label>
                <label className={`photo3d-dropzone ${backPreviewUrl ? 'has-file' : ''}`}>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={handleBackFileChange}
                    className="photo3d-hidden-input"
                  />
                  {backPreviewUrl ? (
                    <div className="photo3d-preview-thumb">
                      <img src={backPreviewUrl} alt="Back View" />
                      <div className="photo3d-thumb-overlay">Click to change</div>
                    </div>
                  ) : (
                    <div className="photo3d-dropzone-prompt">
                      <div className="photo3d-upload-circle secondary">
                        <Upload size={22} />
                      </div>
                      <span className="photo3d-drop-headline">Upload Back Photo</span>
                      <span className="photo3d-drop-sub">Provides accurate rear seams</span>
                    </div>
                  )}
                </label>
              </div>
            </div>

            {/* Privacy Guarantee Banner */}
            <div className="photo3d-privacy-card">
              <ShieldCheck size={20} className="privacy-badge-icon" />
              <div className="privacy-text">
                <strong>Zero Image Retention Guarantee</strong>
                <p>
                  Your photograph is processed in temporary private memory and is permanently purged immediately after 3D reconstruction. Only the generated 3D model is saved to your wardrobe.
                </p>
              </div>
            </div>

            {/* Footer Action */}
            <div className="photo3d-footer">
              <button className="photo3d-btn-ghost" onClick={onClose}>
                Cancel
              </button>
              <button
                className="photo3d-btn-primary"
                disabled={!frontFile}
                onClick={handleStartGeneration}
              >
                <span>Reconstruct 3D Garment</span>
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 2: PROCESSING ── */}
        {step === 'processing' && (
          <div className="photo3d-step-body processing-layout">
            <div className="photo3d-progress-orb">
              <div className="photo3d-spinner-ring" />
              <span className="photo3d-progress-pct">{progress}%</span>
            </div>

            <h3 className="photo3d-stage-title">{currentStage}</h3>

            <div className="photo3d-progress-bar-container">
              <div className="photo3d-progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>

            <ul className="photo3d-stage-checklist">
              <li className={progress >= 20 ? 'done' : 'active'}>
                <span className="chk-icon">{progress >= 20 ? <Check size={14} /> : '1'}</span>
                <span>Garment segmentation & feature analysis</span>
              </li>
              <li className={progress >= 45 ? 'done' : progress >= 20 ? 'active' : ''}>
                <span className="chk-icon">{progress >= 45 ? <Check size={14} /> : '2'}</span>
                <span>3D wearable geometry reconstruction</span>
              </li>
              <li className={progress >= 65 ? 'done' : progress >= 45 ? 'active' : ''}>
                <span className="chk-icon">{progress >= 65 ? <Check size={14} /> : '3'}</span>
                <span>Seamless PBR texture & material synthesis</span>
              </li>
              <li className={progress >= 85 ? 'done' : progress >= 65 ? 'active' : ''}>
                <span className="chk-icon">{progress >= 85 ? <Check size={14} /> : '4'}</span>
                <span>Ara 3D Gen anatomic rig assembly</span>
              </li>
              <li className={progress >= 95 ? 'done' : progress >= 85 ? 'active' : ''}>
                <span className="chk-icon">{progress >= 95 ? <Check size={14} /> : '5'}</span>
                <span>Rendering derived 3D studio preview</span>
              </li>
            </ul>

            <div className="photo3d-footer center">
              <button className="photo3d-btn-ghost danger" onClick={handleCancelJob}>
                Cancel Generation
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 3: 3D PREVIEW & APPROVAL ── */}
        {step === 'preview' && result && (
          <div className="photo3d-step-body preview-layout">
            <div className="photo3d-preview-split">
              {/* Interactive Rotatable 3D Canvas */}
              <div className="photo3d-canvas-wrap">
                <canvas ref={previewCanvasRef} className="photo3d-three-canvas" />
                <div className="photo3d-canvas-overlay-tip">
                  <Eye size={14} /> Drag to rotate 360° | Scroll to zoom
                </div>
              </div>

              {/* Garment Specifications & Metadata */}
              <div className="photo3d-meta-pane">
                <div className="meta-garment-title">
                  <span className="meta-category-badge">{result.category.toUpperCase()}</span>
                  <h3>{result.garment_name}</h3>
                  <span className="meta-sub">{result.subcategory.replace('_', ' ')}</span>
                </div>

                <div className="meta-attributes-grid">
                  <div className="meta-attr-card">
                    <span className="attr-label">Primary Color</span>
                    <div className="attr-val-row">
                      <span 
                        className="color-dot-swatch" 
                        style={{ backgroundColor: result.features.primary_color_hex }} 
                      />
                      <span className="attr-val-text">{result.features.primary_color_name}</span>
                    </div>
                  </div>

                  <div className="meta-attr-card">
                    <span className="attr-label">Fabric / Pattern</span>
                    <span className="attr-val-text">
                      {result.features.pattern.replace('_', ' ').toUpperCase()}
                    </span>
                  </div>

                  <div className="meta-attr-card">
                    <span className="attr-label">Polygon Count</span>
                    <span className="attr-val-text">
                      {result.mesh_triangle_count.toLocaleString()} Tris
                    </span>
                  </div>

                  <div className="meta-attr-card">
                    <span className="attr-label">Ara 3D Compatibility</span>
                    <span className="attr-val-text green">
                      Rig Ready & Fitted
                    </span>
                  </div>
                </div>

                {/* Privacy Badge Reminder */}
                <div className="photo3d-privacy-pill">
                  <ShieldCheck size={16} />
                  <span>Original photo erased from memory. Ready to store 3D asset.</span>
                </div>

                {/* Actions */}
                <div className="photo3d-preview-actions">
                  <button
                    className="photo3d-btn-primary save-btn"
                    onClick={handleSaveToWardrobe}
                    disabled={isSaving || savedSuccess}
                  >
                    {savedSuccess ? (
                      <>
                        <Check size={18} />
                        <span>Saved to My Wardrobe</span>
                      </>
                    ) : (
                      <>
                        <Save size={18} />
                        <span>{isSaving ? 'Saving...' : 'Save to My Wardrobe'}</span>
                      </>
                    )}
                  </button>

                  {onWearImmediately && (
                    <button
                      className="photo3d-btn-secondary wear-btn"
                      onClick={() => {
                        onWearImmediately(result);
                        onClose();
                      }}
                    >
                      <Shirt size={18} />
                      <span>Wear on Avatar Now</span>
                    </button>
                  )}

                  <button className="photo3d-btn-ghost" onClick={handleReset}>
                    <RefreshCw size={16} />
                    <span>Reconstruct Another Photo</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

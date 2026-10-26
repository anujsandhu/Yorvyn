/**
 * Multi-Step Personal Profile & 3D Avatar Onboarding Wizard — Yorvyn
 *
 * Implements:
 * - Step 1: Basic Profile (Display Name, Age, Units)
 * - Step 2: Skin Tone (Visual swatches, undertone mappings)
 * - Step 3: Height & Body Type (Interactive slider, respectful silhouette presets)
 * - Step 4: Hair & Virtual Avatar Presentation (Hair color swatches, gender/neutral presentation)
 * - Step 5: 3D Avatar Preview & Final Confirmation (Real Three.js character rendering, summary, persistence)
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  User,
  Ruler,
  Palette,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Check,
  RotateCcw,
  ShieldCheck
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../../context/AuthContext';
import { profileService, OnboardingProfileData } from '../../services/profile/profileService';
import { AtmosphereBackground } from '../../components/AtmosphereBackground';
import './OnboardingWizard.css';

// ── Swatch & Preset Definitions ──────────────────────────────────────────────

export interface SkinToneOption {
  id: string;
  name: string;
  hex: string;
  undertone: 'cool-bright' | 'warm-bright' | 'warm-neutral' | 'warm-deep' | 'cool-deep' | 'neutral-deep';
  description: string;
}

export const SKIN_TONES: SkinToneOption[] = [
  { id: 'porcelain', name: 'Porcelain Fair', hex: '#f9d4b8', undertone: 'cool-bright', description: 'Fair with cool rosy undertones' },
  { id: 'ivory', name: 'Warm Ivory', hex: '#f3c299', undertone: 'warm-bright', description: 'Light with warm golden peach undertones' },
  { id: 'sand', name: 'Golden Sand', hex: '#e0a574', undertone: 'warm-neutral', description: 'Medium with warm honey undertones' },
  { id: 'amber', name: 'Warm Amber', hex: '#c68642', undertone: 'warm-deep', description: 'Rich tan with warm golden undertones' },
  { id: 'almond', name: 'Chestnut Almond', hex: '#8d5524', undertone: 'cool-deep', description: 'Deep rich brown with balanced undertones' },
  { id: 'espresso', name: 'Obsidian Espresso', hex: '#4a2912', undertone: 'neutral-deep', description: 'Deep dark brown with rich undertones' },
];

export interface HairColorOption {
  id: string;
  name: string;
  hex: string;
}

export const HAIR_COLORS: HairColorOption[] = [
  { id: 'jet_black', name: 'Jet Black', hex: '#111111' },
  { id: 'dark_espresso', name: 'Dark Espresso', hex: '#3a2312' },
  { id: 'warm_chestnut', name: 'Warm Chestnut', hex: '#6a3b1a' },
  { id: 'honey_blonde', name: 'Honey Blonde', hex: '#d4a359' },
  { id: 'platinum_blonde', name: 'Platinum Blonde', hex: '#e6d8b8' },
  { id: 'auburn_copper', name: 'Auburn Copper', hex: '#8c2d19' },
  { id: 'silver_grey', name: 'Silver Ash', hex: '#a0a0a0' },
];

export interface BodyTypeOption {
  id: string;
  name: string;
  description: string;
  muscleValue: number;
  weightValue: number;
}

export const BODY_TYPES: BodyTypeOption[] = [
  { id: 'slender', name: 'Slender / Lean', description: 'Refined, narrow silhouette with slender frame', muscleValue: 0.3, weightValue: 0.35 },
  { id: 'athletic', name: 'Athletic / Tapered', description: 'Sculpted shoulders, active posture, tapered waist', muscleValue: 0.75, weightValue: 0.5 },
  { id: 'regular', name: 'Balanced / Regular', description: 'Natural balanced humanoid proportions', muscleValue: 0.5, weightValue: 0.5 },
  { id: 'curvy', name: 'Curvy / Full', description: 'Soft contours with accentuated silhouette', muscleValue: 0.4, weightValue: 0.65 },
  { id: 'broad', name: 'Broad / Robust', description: 'Broader chest, shoulders, and solid presence', muscleValue: 0.7, weightValue: 0.7 },
];

export function OnboardingWizard() {
  const navigate = useNavigate();
  const { user, profile, refreshProfile } = useAuth();
  
  // Step index: 1 to 5
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form State
  const [displayName, setDisplayName] = useState(profile?.displayName || user?.displayName || 'Alex');
  const [age, setAge] = useState<number>(profile?.age || 26);
  const [heightUnit, setHeightUnit] = useState<'cm' | 'ft'>(profile?.heightUnit || 'cm');
  const [heightValue, setHeightValue] = useState<number>(profile?.heightValue || 175);
  
  const [selectedSkinTone, setSelectedSkinTone] = useState<SkinToneOption>(() => {
    return SKIN_TONES.find(t => t.id === profile?.skinToneId) || SKIN_TONES[1];
  });
  
  const [selectedBodyType, setSelectedBodyType] = useState<BodyTypeOption>(() => {
    return BODY_TYPES.find(b => b.id === profile?.bodyType) || BODY_TYPES[1];
  });
  
  const [selectedHairColor, setSelectedHairColor] = useState<HairColorOption>(() => {
    return HAIR_COLORS.find(h => h.id === profile?.hairColourId) || HAIR_COLORS[1];
  });
  
  const [avatarPresentation, setAvatarPresentation] = useState<'feminine' | 'masculine' | 'neutral'>(
    profile?.avatarGenderPresentation || 'neutral'
  );

  // 3D Canvas Reference for Step 5
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);

  // Step 5 3D Preview initialization
  useEffect(() => {
    if (currentStep !== 5 || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const width = canvas.parentElement?.clientWidth || 380;
    const height = 480;

    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    camera.position.set(0, 1.2, 2.8);

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 0.95, 0);
    controls.maxPolarAngle = Math.PI / 2 + 0.1;
    controls.minDistance = 1.5;
    controls.maxDistance = 4.2;

    // Ambient & Studio Directional Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xfff5ea, 1.2);
    keyLight.position.set(2, 4, 3);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xebf5ff, 0.6);
    fillLight.position.set(-2, 2, 2);
    scene.add(fillLight);

    // Build the Parametric 3D Mannequin Mesh
    const mannequinGroup = new THREE.Group();
    modelGroupRef.current = mannequinGroup;
    scene.add(mannequinGroup);

    // Materials
    const skinMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(selectedSkinTone.hex),
      roughness: 0.65,
      metalness: 0.08
    });

    const hairMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(selectedHairColor.hex),
      roughness: 0.45,
      metalness: 0.15
    });

    const clothTopMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(avatarPresentation === 'feminine' ? '#2c3e50' : '#1e293b'),
      roughness: 0.75
    });

    const clothBottomMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#334155'),
      roughness: 0.85
    });

    // Proportions calculated from selected attributes
    const scaleY = (heightValue / 175) * 1.0;
    const bodyWidth = 1.0 + (selectedBodyType.weightValue - 0.5) * 0.4;
    const shoulderWidth = avatarPresentation === 'masculine' ? 1.15 : avatarPresentation === 'feminine' ? 0.95 : 1.05;

    // 1. Head
    const headGeom = new THREE.SphereGeometry(0.12, 24, 24);
    headGeom.scale(0.9, 1.15, 0.95);
    const head = new THREE.Mesh(headGeom, skinMat);
    head.position.set(0, 1.62 * scaleY, 0);
    mannequinGroup.add(head);

    // 2. Hair Style
    const hairGeom = new THREE.SphereGeometry(0.13, 20, 20);
    hairGeom.scale(0.95, 0.85, 1.05);
    const hair = new THREE.Mesh(hairGeom, hairMat);
    hair.position.set(0, 1.68 * scaleY, -0.02);
    mannequinGroup.add(hair);

    // 3. Torso
    const torsoGeom = new THREE.CylinderGeometry(
      0.18 * bodyWidth * shoulderWidth,
      0.15 * bodyWidth,
      0.55 * scaleY,
      20
    );
    const torso = new THREE.Mesh(torsoGeom, clothTopMat);
    torso.position.set(0, 1.25 * scaleY, 0);
    mannequinGroup.add(torso);

    // 4. Pelvis / Hips
    const hipGeom = new THREE.CylinderGeometry(0.15 * bodyWidth, 0.17 * bodyWidth, 0.18 * scaleY, 18);
    const hips = new THREE.Mesh(hipGeom, clothBottomMat);
    hips.position.set(0, 0.95 * scaleY, 0);
    mannequinGroup.add(hips);

    // 5. Legs
    const legGeom = new THREE.CylinderGeometry(0.065 * bodyWidth, 0.045, 0.85 * scaleY, 16);
    const leftLeg = new THREE.Mesh(legGeom, clothBottomMat);
    leftLeg.position.set(-0.09 * bodyWidth, 0.45 * scaleY, 0);
    const rightLeg = new THREE.Mesh(legGeom, clothBottomMat);
    rightLeg.position.set(0.09 * bodyWidth, 0.45 * scaleY, 0);
    mannequinGroup.add(leftLeg, rightLeg);

    // 6. Arms
    const armGeom = new THREE.CylinderGeometry(0.045 * bodyWidth, 0.038, 0.65 * scaleY, 16);
    const leftArm = new THREE.Mesh(armGeom, skinMat);
    leftArm.position.set(-0.24 * bodyWidth * shoulderWidth, 1.2 * scaleY, 0);
    leftArm.rotation.z = 0.12;
    const rightArm = new THREE.Mesh(armGeom, skinMat);
    rightArm.position.set(0.24 * bodyWidth * shoulderWidth, 1.2 * scaleY, 0);
    rightArm.rotation.z = -0.12;
    mannequinGroup.add(leftArm, rightArm);

    // Subtle gentle pedestal shadow ring
    const shadowGeom = new THREE.RingGeometry(0.05, 0.45, 32);
    const shadowMat = new THREE.MeshBasicMaterial({
      color: 0x94a3b8,
      transparent: true,
      opacity: 0.25,
      side: THREE.DoubleSide
    });
    const shadow = new THREE.Mesh(shadowGeom, shadowMat);
    shadow.rotation.x = Math.PI / 2;
    shadow.position.y = 0.01;
    scene.add(shadow);

    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      // Gentle idle subtle sway
      mannequinGroup.rotation.y = Math.sin(Date.now() * 0.0006) * 0.08;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      controls.dispose();
      renderer.dispose();
    };
  }, [currentStep, heightValue, selectedSkinTone, selectedHairColor, selectedBodyType, avatarPresentation]);

  // Height conversion helpers
  const handleHeightChange = (val: number) => {
    setHeightValue(val);
  };

  const cmToFtIn = (cm: number) => {
    const totalInches = cm / 2.54;
    const feet = Math.floor(totalInches / 12);
    const inches = Math.round(totalInches % 12);
    return `${feet}'${inches}"`;
  };

  const handleNext = () => {
    if (currentStep === 1) {
      if (!displayName.trim()) {
        toast.error('Please enter a display name.');
        return;
      }
      if (age < 13 || age > 110) {
        toast.error('Please provide a valid age (13+).');
        return;
      }
    }
    setCurrentStep(prev => Math.min(prev + 1, 5));
  };

  const handleBack = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleComplete = async () => {
    if (!user?.id) {
      toast.error('Session not found. Please log in.');
      navigate('/login');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: OnboardingProfileData = {
        displayName: displayName.trim(),
        age,
        heightValue,
        heightUnit,
        bodyType: selectedBodyType.id,
        skinToneId: selectedSkinTone.id,
        skinToneHex: selectedSkinTone.hex,
        hairColourId: selectedHairColor.id,
        hairColourHex: selectedHairColor.hex,
        avatarGenderPresentation: avatarPresentation,
        avatarConfiguration: {
          gender: avatarPresentation === 'feminine' ? 0.1 : avatarPresentation === 'masculine' ? 0.9 : 0.5,
          height: (heightValue - 140) / 75,
          muscle: selectedBodyType.muscleValue,
          weight: selectedBodyType.weightValue,
          skinTint: selectedSkinTone.hex,
          hairColor: selectedHairColor.hex,
          hair: avatarPresentation === 'feminine' ? 'ponytail01' : 'short01',
          outfit: avatarPresentation === 'feminine' ? 'female_casualsuit01' : 'suit01'
        },
        onboardingCompleted: true
      };

      await profileService.completeOnboarding(user.id, payload);
      await refreshProfile();
      toast.success('Avatar profile personalized! Welcome to Yorvyn.');
      navigate('/', { replace: true });
    } catch (err: any) {
      toast.error(err?.message || 'Failed to save profile. Retrying...');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="onboarding-root">
      <AtmosphereBackground 
        lowlightColor={0x93c5fd}
        highlightColor={0xffffff}
        midtoneColor={0xbfdbfe}
        baseColor={0xe0f2fe}
        blurFactor={0.5}
        speed={0.35}
      />

      <div className="onboarding-container">
        {/* Progress Bar Header */}
        <div className="onboarding-progress-header">
          <div className="onboarding-steps-indicator">
            {[1, 2, 3, 4, 5].map((stepNum) => (
              <div
                key={stepNum}
                className={`step-bubble ${currentStep === stepNum ? 'active' : ''} ${currentStep > stepNum ? 'completed' : ''}`}
              >
                {currentStep > stepNum ? <Check size={14} /> : stepNum}
              </div>
            ))}
          </div>
          <p className="onboarding-step-label">
            Step {currentStep} of 5 —{' '}
            {currentStep === 1 && 'Basic Profile'}
            {currentStep === 2 && 'Skin Tone'}
            {currentStep === 3 && 'Height & Body Silhouette'}
            {currentStep === 4 && 'Hair & Virtual Appearance'}
            {currentStep === 5 && 'Avatar Preview & Confirmation'}
          </p>
        </div>

        {/* Wizard Card Body */}
        <div className="onboarding-card">
          {/* ── STEP 1: Basic Profile ── */}
          {currentStep === 1 && (
            <div className="onboarding-step-body animate-fade-in">
              <div className="step-icon-badge">
                <User size={24} />
              </div>
              <h2 className="step-heading">Personalize Your Profile</h2>
              <p className="step-subtext">
                Tell us your styling name and baseline preferences. We collect minimal information strictly for tailoring avatar ergonomics and virtual fit.
              </p>

              <div className="step-field-group">
                <label className="step-field-label">Display Name / Alias</label>
                <input
                  type="text"
                  className="step-text-input"
                  placeholder="e.g. Alex, Maya, Liam"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  maxLength={40}
                  required
                />
              </div>

              <div className="step-field-row">
                <div className="step-field-group flex-1">
                  <label className="step-field-label">Age</label>
                  <input
                    type="number"
                    className="step-text-input"
                    min={14}
                    max={100}
                    value={age}
                    onChange={(e) => setAge(parseInt(e.target.value) || 20)}
                  />
                  <span className="privacy-pill-hint">
                    <ShieldCheck size={12} /> Kept strictly private
                  </span>
                </div>

                <div className="step-field-group flex-1">
                  <label className="step-field-label">Measurement Units</label>
                  <div className="unit-toggle-group">
                    <button
                      type="button"
                      className={`unit-btn ${heightUnit === 'cm' ? 'active' : ''}`}
                      onClick={() => setHeightUnit('cm')}
                    >
                      Metric (cm)
                    </button>
                    <button
                      type="button"
                      className={`unit-btn ${heightUnit === 'ft' ? 'active' : ''}`}
                      onClick={() => setHeightUnit('ft')}
                    >
                      Imperial (ft/in)
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── STEP 2: Skin Tone ── */}
          {currentStep === 2 && (
            <div className="onboarding-step-body animate-fade-in">
              <div className="step-icon-badge">
                <Palette size={24} />
              </div>
              <h2 className="step-heading">Choose Avatar Skin Tone</h2>
              <p className="step-subtext">
                Select your preferred 3D avatar skin tone. This configures the character's lighting response and seasonal colour compatibility palette.
              </p>

              <div className="swatch-grid">
                {SKIN_TONES.map((tone) => (
                  <button
                    key={tone.id}
                    type="button"
                    className={`tone-card ${selectedSkinTone.id === tone.id ? 'selected' : ''}`}
                    onClick={() => setSelectedSkinTone(tone)}
                  >
                    <div
                      className="swatch-circle"
                      style={{ backgroundColor: tone.hex }}
                    />
                    <div className="tone-meta">
                      <span className="tone-title">{tone.name}</span>
                      <span className="tone-desc">{tone.undertone}</span>
                    </div>
                    {selectedSkinTone.id === tone.id && (
                      <div className="swatch-check">
                        <Check size={14} />
                      </div>
                    )}
                  </button>
                ))}
              </div>

              <div className="swatch-callout">
                <span>Selected Undertone:</span> <strong>{selectedSkinTone.description}</strong>
              </div>
            </div>
          )}

          {/* ── STEP 3: Height & Body Type ── */}
          {currentStep === 3 && (
            <div className="onboarding-step-body animate-fade-in">
              <div className="step-icon-badge">
                <Ruler size={24} />
              </div>
              <h2 className="step-heading">Height & Body Silhouette</h2>
              <p className="step-subtext">
                Customize avatar stature and proportions. Note: body type is an approximate 3D mannequin configuration, not a medical measurement.
              </p>

              {/* Height Slider */}
              <div className="height-slider-box">
                <div className="height-display-header">
                  <span>Avatar Height</span>
                  <span className="height-value-badge">
                    {heightValue} cm ({cmToFtIn(heightValue)})
                  </span>
                </div>
                <input
                  type="range"
                  min={145}
                  max={210}
                  step={1}
                  value={heightValue}
                  onChange={(e) => handleHeightChange(Number(e.target.value))}
                  className="slider-input"
                />
                <div className="slider-range-labels">
                  <span>145 cm (4'9")</span>
                  <span>175 cm (5'9")</span>
                  <span>210 cm (6'11")</span>
                </div>
              </div>

              {/* Body Type Presets */}
              <label className="step-field-label" style={{ marginTop: '20px' }}>
                Body Silhouette Preset
              </label>
              <div className="body-preset-grid">
                {BODY_TYPES.map((bt) => (
                  <button
                    key={bt.id}
                    type="button"
                    className={`body-preset-card ${selectedBodyType.id === bt.id ? 'selected' : ''}`}
                    onClick={() => setSelectedBodyType(bt)}
                  >
                    <div className="body-preset-title">{bt.name}</div>
                    <div className="body-preset-desc">{bt.description}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── STEP 4: Hair & Avatar Presentation ── */}
          {currentStep === 4 && (
            <div className="onboarding-step-body animate-fade-in">
              <div className="step-icon-badge">
                <Sparkles size={24} />
              </div>
              <h2 className="step-heading">Hair & Virtual Appearance</h2>
              <p className="step-subtext">
                Define the virtual presentation of your character. Personalize hair color and select your preferred presentation aesthetic.
              </p>

              {/* Virtual Presentation */}
              <label className="step-field-label">Avatar Presentation Mode</label>
              <div className="presentation-tabs">
                <button
                  type="button"
                  className={`presentation-tab ${avatarPresentation === 'feminine' ? 'active' : ''}`}
                  onClick={() => setAvatarPresentation('feminine')}
                >
                  Feminine
                </button>
                <button
                  type="button"
                  className={`presentation-tab ${avatarPresentation === 'neutral' ? 'active' : ''}`}
                  onClick={() => setAvatarPresentation('neutral')}
                >
                  Neutral / Non-Binary
                </button>
                <button
                  type="button"
                  className={`presentation-tab ${avatarPresentation === 'masculine' ? 'active' : ''}`}
                  onClick={() => setAvatarPresentation('masculine')}
                >
                  Masculine
                </button>
              </div>

              {/* Hair Color Swatches */}
              <label className="step-field-label" style={{ marginTop: '22px' }}>
                Hair Color
              </label>
              <div className="hair-swatches-row">
                {HAIR_COLORS.map((hair) => (
                  <button
                    key={hair.id}
                    type="button"
                    className={`hair-swatch-btn ${selectedHairColor.id === hair.id ? 'selected' : ''}`}
                    onClick={() => setSelectedHairColor(hair)}
                    title={hair.name}
                  >
                    <span className="hair-circle" style={{ backgroundColor: hair.hex }} />
                    <span className="hair-name">{hair.name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── STEP 5: Avatar Preview & Confirmation ── */}
          {currentStep === 5 && (
            <div className="onboarding-step-body animate-fade-in">
              <h2 className="step-heading">Inspect Your 3D Avatar</h2>
              <p className="step-subtext">
                Your character has been synthesized using your personal attributes. Rotate to inspect the silhouette and confirm to enter Yorvyn.
              </p>

              <div className="preview-split-layout">
                {/* 3D Canvas Viewport */}
                <div className="canvas-wrapper">
                  <canvas ref={canvasRef} className="preview-canvas" />
                  <div className="canvas-hint-pill">
                    <RotateCcw size={13} /> Drag to rotate 3D character
                  </div>
                </div>

                {/* Summary Recap Cards */}
                <div className="summary-col">
                  <div className="summary-card">
                    <span className="summary-card-label">Profile</span>
                    <span className="summary-card-val">{displayName}, {age} years</span>
                  </div>

                  <div className="summary-card">
                    <span className="summary-card-label">Height & Silhouette</span>
                    <span className="summary-card-val">
                      {heightValue} cm ({cmToFtIn(heightValue)}) • {selectedBodyType.name}
                    </span>
                  </div>

                  <div className="summary-card">
                    <span className="summary-card-label">Skin Tone & Undertone</span>
                    <div className="summary-color-row">
                      <span className="mini-color-dot" style={{ backgroundColor: selectedSkinTone.hex }} />
                      <span>{selectedSkinTone.name} ({selectedSkinTone.undertone})</span>
                    </div>
                  </div>

                  <div className="summary-card">
                    <span className="summary-card-label">Hair & Presentation</span>
                    <div className="summary-color-row">
                      <span className="mini-color-dot" style={{ backgroundColor: selectedHairColor.hex }} />
                      <span>{selectedHairColor.name} • {avatarPresentation}</span>
                    </div>
                  </div>

                  <p className="summary-note">
                    You can fine-tune your measurements and outfit customizations anytime in Settings.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Wizard Action Footer */}
          <div className="onboarding-card-footer">
            {currentStep > 1 ? (
              <button
                type="button"
                className="onboarding-back-btn"
                onClick={handleBack}
                disabled={isSubmitting}
              >
                <ArrowLeft size={16} /> Back
              </button>
            ) : <div />}

            {currentStep < 5 ? (
              <button
                type="button"
                className="onboarding-next-btn"
                onClick={handleNext}
              >
                Continue <ArrowRight size={16} />
              </button>
            ) : (
              <button
                type="button"
                className="onboarding-confirm-btn"
                onClick={handleComplete}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Personalizing...' : 'Confirm & Enter Yorvyn'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

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
import {
  ArrowRight,
  ArrowLeft,
  Check,
  ArrowCounterClockwise,
  ShieldCheck
} from '../../components/icons';
import toast from 'react-hot-toast';
import { useAuth } from '../../context/AuthContext';
import { profileService, OnboardingProfileData } from '../../services/profile/profileService';
import { fashionApi } from '../../services/fashionApi';
import { AtmosphereBackground } from '../../components/AtmosphereBackground';
import { avatarEngine as araEngine } from '../../engine/ara/avatarStudioService';
import { AvatarStudioViewer } from '../../components/AvatarStudioViewer';
import { AvatarSkeletonLoader } from '../../components/SkeletonLoader';
import { HumanParams, DEFAULT_PARAMS } from '../../engine/ara/core/params';
import { Character } from '../../engine/ara/core/human';
import { AssetLibrary } from '../../engine/ara/core/assets';
import {
  SilhouetteMannequinVisual,
  SkinToneMannequinVisual,
  PresentationVisual,
  HairColorSwatchVisual,
  HairStyleMannequinVisual,
} from './SilhouetteMannequinVisual';
import gsap from 'gsap';
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

export interface HairStyleOption {
  id: string;
  name: string;
}

export const HAIR_STYLES: HairStyleOption[] = [
  { id: 'short02', name: 'Short Textured' },
  { id: 'short04', name: 'Executive Side Part' },
  { id: 'short01', name: 'Classic Taper' },
  { id: 'bob01', name: 'Classic Bob' },
  { id: 'bob02', name: 'Wavy Bob' },
  { id: 'long01', name: 'Flowing Layers' },
  { id: 'ponytail01', name: 'Sleek Ponytail' },
  { id: 'braid01', name: 'Crown Braids' },
  { id: 'afro01', name: 'Natural Volume Afro' },
  { id: 'buzz', name: 'Studio Buzz' },
  { id: 'none', name: 'Clean Shaved' },
  { id: 'receding', name: 'Receding Classic' },
];

export interface BodyTypeOption {
  id: string;
  name: string;
  tag: string;
  description: string;
  muscleValue: number;
  weightValue: number;
}

export const BODY_TYPES: BodyTypeOption[] = [
  { id: 'slender', name: 'Slim', tag: 'Slender', description: 'Refined narrow silhouette with tailored drape', muscleValue: 0.3, weightValue: 0.35 },
  { id: 'athletic', name: 'Athletic', tag: 'V-Taper', description: 'Sculpted shoulders, active posture, tapered waist', muscleValue: 0.75, weightValue: 0.5 },
  { id: 'regular', name: 'Average', tag: 'Proportional', description: 'Natural balanced humanoid proportions', muscleValue: 0.5, weightValue: 0.5 },
  { id: 'broad', name: 'Broad', tag: 'Power Build', description: 'Broader chest, wide shoulders, solid presence', muscleValue: 0.7, weightValue: 0.7 },
  { id: 'curvy', name: 'Curvy', tag: 'Hourglass', description: 'Soft contours with accentuated silhouette drape', muscleValue: 0.4, weightValue: 0.65 },
  { id: 'fuller', name: 'Fuller', tag: 'Full Frame', description: 'Generous contours with comfortable drape', muscleValue: 0.4, weightValue: 0.8 },
];

export interface StaturePresetOption {
  id: 'petite' | 'classic' | 'studio' | 'statuesque';
  label: string;
  cm: number;
  ft: string;
  desc: string;
}

export const STATURE_PRESETS: StaturePresetOption[] = [
  { id: 'petite', label: 'Petite', cm: 160, ft: '5\'3"', desc: 'Compact tailored proportions' },
  { id: 'classic', label: 'Classic', cm: 170, ft: '5\'7"', desc: 'Standard atelier balance' },
  { id: 'studio', label: 'Studio', cm: 178, ft: '5\'10"', desc: 'Runway model silhouette' },
  { id: 'statuesque', label: 'Statuesque', cm: 188, ft: '6\'2"', desc: 'Elongated couture stature' },
];

export function OnboardingWizard() {
  const navigate = useNavigate();
  const { user, profile, refreshProfile } = useAuth();
  
  // Step index: 1 to 5
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form State
  const [displayName, setDisplayName] = useState(profile?.displayName || user?.displayName || '');
  const [age, setAge] = useState<number>(profile?.age || 26);
  const [gender, setGender] = useState<'female' | 'male' | 'non-binary'>(
    (profile?.gender as any) || 'female'
  );
  const [phoneNumber, setPhoneNumber] = useState<string>(profile?.phoneNumber || '');
  const [location, setLocation] = useState<string>(profile?.location || '');
  const [heightUnit, setHeightUnit] = useState<'cm' | 'ft'>(profile?.heightUnit || 'cm');
  const [heightValue, setHeightValue] = useState<number>(profile?.heightValue || 175);
  const [weightValue, setWeightValue] = useState<number>(profile?.weightValue || 65);
  const [weightUnit, setWeightUnit] = useState<'kg' | 'lbs'>(profile?.weightUnit || 'kg');
  
  const [selectedSkinTone, setSelectedSkinTone] = useState<SkinToneOption>(() => {
    return SKIN_TONES.find(t => t.id === profile?.skinToneId) || SKIN_TONES[1];
  });
  
  const [selectedBodyType, setSelectedBodyType] = useState<BodyTypeOption>(() => {
    return BODY_TYPES.find(b => b.id === profile?.bodyType) || BODY_TYPES[1];
  });
  
  const [selectedHairColor, setSelectedHairColor] = useState<HairColorOption>(() => {
    return HAIR_COLORS.find(h => h.id === profile?.hairColourId) || HAIR_COLORS[1];
  });

  const [selectedHairStyle, setSelectedHairStyle] = useState<string>(() => {
    return profile?.avatarConfiguration?.hair || 'short02';
  });
  
  const [avatarPresentation, setAvatarPresentation] = useState<'feminine' | 'masculine' | 'neutral'>(
    profile?.avatarGenderPresentation || 'neutral'
  );

  // Phase 9: Explicit Privacy & Ephemeral Processing Consent
  const [ephemeralProcessingConsent, setEphemeralProcessingConsent] = useState<boolean>(true);
  const [aiTrainingOptIn, setAiTrainingOptIn] = useState<boolean>(false);

  // Dynamic Camera Zoom Mode (Portrait / Half-Body for Hair, Full-Body Fitted for Body Type)
  const [onboardingViewMode, setOnboardingViewMode] = useState<'full' | 'portrait'>('full');

  useEffect(() => {
    if (currentStep === 4) {
      setOnboardingViewMode('portrait');
    } else {
      setOnboardingViewMode('full');
    }
  }, [currentStep]);

  // GSAP Animation Refs & State
  const [direction, setDirection] = useState<'forward' | 'backward'>('forward');
  const cardRef = useRef<HTMLDivElement | null>(null);
  const stepBodyRef = useRef<HTMLDivElement | null>(null);
  const isFirstMount = useRef(true);

  // Initial cinematic entrance animation on mount
  useEffect(() => {
    if (cardRef.current) {
      gsap.fromTo(
        cardRef.current,
        { opacity: 0, y: 35, scale: 0.96 },
        { opacity: 1, y: 0, scale: 1, duration: 0.65, ease: 'power3.out' }
      );
    }
    // Background pre-warm 3D engine catalog so Step 5 generation is fast
    araEngine.init().catch((err) => console.log('3D engine catalog background warmup:', err));
  }, []);

  // Step change transition animation
  useEffect(() => {
    if (!stepBodyRef.current) return;

    if (isFirstMount.current) {
      isFirstMount.current = false;
      animateStepIn('forward');
      return;
    }

    animateStepIn(direction);
  }, [currentStep]);

  const animateStepIn = (dir: 'forward' | 'backward') => {
    if (!stepBodyRef.current) return;
    const xOffset = dir === 'forward' ? 36 : -36;

    // Smooth card content slide-fade
    gsap.fromTo(
      stepBodyRef.current,
      { opacity: 0, x: xOffset },
      { opacity: 1, x: 0, duration: 0.42, ease: 'power3.out', clearProps: 'transform' }
    );


    // Typography stagger
    const heading = stepBodyRef.current.querySelector('.step-heading');
    const subtext = stepBodyRef.current.querySelector('.step-subtext');
    if (heading || subtext) {
      gsap.fromTo(
        [heading, subtext].filter(Boolean),
        { y: 14, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.38, stagger: 0.06, ease: 'power2.out' }
      );
    }

    // Interactive card options stagger
    const cards = stepBodyRef.current.querySelectorAll(
      '.tone-card, .body-preset-card, .hair-swatch-btn, .step-field-group, .height-slider-box, .summary-card'
    );
    if (cards.length > 0) {
      gsap.fromTo(
        cards,
        { y: 16, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.35, stagger: 0.035, ease: 'power2.out' }
      );
    }

    // 3D canvas viewport in step 5
    const canvasWrap = stepBodyRef.current.querySelector('.canvas-wrapper');
    if (canvasWrap) {
      gsap.fromTo(
        canvasWrap,
        { scale: 0.92, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.5, ease: 'power2.out' }
      );
    }

    // Active progress bubble bounce
    const activeBubble = document.querySelector('.step-bubble.active');
    if (activeBubble) {
      gsap.fromTo(
        activeBubble,
        { scale: 0.8 },
        { scale: 1.1, duration: 0.35, ease: 'back.out(2)' }
      );
    }
  };

  // Real 3D Avatar Character state
  const [character, setCharacter] = useState<Character | null>(null);
  const [library, setLibrary] = useState<AssetLibrary | null>(null);
  const [characterLoading, setCharacterLoading] = useState(true);
  const [loadingLabel, setLoadingLabel] = useState('Generating your 3D avatar...');

  // Live 3D character generator (runs immediately on mount and debounces updates)
  useEffect(() => {
    let active = true;

    const timer = setTimeout(async () => {
      try {
        if (!character) {
          setCharacterLoading(true);
        }
        await araEngine.init((label) => {
          if (active) setLoadingLabel(label);
        });
        const lib = araEngine.getLibrary();
        if (active) setLibrary(lib);

        const params: HumanParams = {
          ...DEFAULT_PARAMS,
          name: displayName || 'Yorvyn User',
          gender: avatarPresentation === 'feminine' ? 0.0 : avatarPresentation === 'masculine' ? 1.0 : 0.5,
          age: Math.min(Math.max((age - 10) / 60, 0.2), 0.8),
          height: 0.5, // Fixed natural baseline height (height concept removed from 3D model)
          muscle: selectedBodyType.muscleValue,
          weight: selectedBodyType.weightValue,
          skinTint: selectedSkinTone.hex,
          hairColor: selectedHairColor.hex,
          hairTint: selectedHairColor.hex,
          hair: selectedHairStyle === 'receding' ? 'short03' : selectedHairStyle,
          outfit: avatarPresentation === 'feminine' ? 'female_casualsuit01' : 'male_casualsuit02',
          shoes: 'shoes01',
          restPose: 'A',
          animations: true,
        };

        const built = await araEngine.generateCharacter(params, (stage) => {
          if (active) setLoadingLabel(stage);
        });

        if (active) {
          setCharacter(built);
          setCharacterLoading(false);
        }
      } catch (err: any) {
        console.warn('Failed to generate real 3D avatar:', err);
        if (active) setCharacterLoading(false);
      }
    }, character ? 1000 : 0);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [displayName, age, selectedBodyType, avatarPresentation, selectedHairStyle]);


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
    setDirection('forward');
    setCurrentStep(prev => Math.min(prev + 1, 5));
  };

  const handleBack = () => {
    setDirection('backward');
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  // Live Instant Material Color Updates
  const handleSelectSkinTone = (tone: SkinToneOption, e?: React.MouseEvent) => {
    if (e) {
      gsap.fromTo(e.currentTarget, { scale: 0.94 }, { scale: 1, duration: 0.25, ease: 'back.out(2)' });
    }
    setSelectedSkinTone(tone);
    if (character) {
      setCharacter({
        ...character,
        params: {
          ...character.params,
          skinTint: tone.hex
        }
      });
    }
  };

  const handleSelectBodyType = (bt: BodyTypeOption, e?: React.MouseEvent) => {
    if (e) {
      gsap.fromTo(e.currentTarget, { scale: 0.96 }, { scale: 1, duration: 0.25, ease: 'back.out(2)' });
    }
    setSelectedBodyType(bt);
    setOnboardingViewMode('full');
  };

  const handleSelectHairColor = (hair: HairColorOption, e?: React.MouseEvent) => {
    if (e) {
      gsap.fromTo(e.currentTarget, { scale: 0.94 }, { scale: 1, duration: 0.25, ease: 'back.out(2)' });
    }
    setSelectedHairColor(hair);
    setOnboardingViewMode('portrait');
    if (character) {
      setCharacter({
        ...character,
        params: {
          ...character.params,
          hairColor: hair.hex,
          hairTint: hair.hex
        }
      });
    }
  };

  const handleSelectHairStyle = (styleId: string, e?: React.MouseEvent) => {
    if (e) {
      gsap.fromTo(e.currentTarget, { scale: 0.94 }, { scale: 1, duration: 0.2, ease: 'back.out(2)' });
    }
    setSelectedHairStyle(styleId);
    setOnboardingViewMode('portrait');
    if (character) {
      const realHair = styleId === 'receding' ? 'short03' : styleId;
      setCharacter({
        ...character,
        params: {
          ...character.params,
          hair: realHair,
        }
      });
    }
  };

  const handleSelectPresentation = (pres: 'feminine' | 'masculine' | 'neutral', e?: React.MouseEvent) => {
    if (e) {
      gsap.fromTo(e.currentTarget, { scale: 0.95 }, { scale: 1, duration: 0.25, ease: 'back.out(2)' });
    }
    setAvatarPresentation(pres);
    setOnboardingViewMode('full');
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
        gender,
        phoneNumber: phoneNumber.trim(),
        location: location.trim(),
        heightValue,
        heightUnit,
        weightValue,
        weightUnit,
        bodyType: selectedBodyType.id,
        skinToneId: selectedSkinTone.id,
        skinToneHex: selectedSkinTone.hex,
        hairColourId: selectedHairColor.id,
        hairColourHex: selectedHairColor.hex,
        avatarGenderPresentation: avatarPresentation,
        avatarConfiguration: {
          gender: avatarPresentation === 'feminine' ? 0.1 : avatarPresentation === 'masculine' ? 0.9 : 0.5,
          height: 0.5,
          muscle: selectedBodyType.muscleValue,
          weight: selectedBodyType.weightValue,
          skinTint: selectedSkinTone.hex,
          hairColor: selectedHairColor.hex,
          hair: selectedHairStyle === 'receding' ? 'short03' : selectedHairStyle,
          outfit: avatarPresentation === 'feminine' ? 'female_casualsuit01' : 'male_casualsuit02'
        },
        onboardingCompleted: true
      };

      await profileService.completeOnboarding(user.id, payload);

      // Phase 9: Persist Privacy & Processing Consent to Supabase / Backend
      try {
        await fashionApi.updateUserConsent({
          ephemeral_processing_accepted: ephemeralProcessingConsent,
          ai_training_opt_in: aiTrainingOptIn,
          terms_version: '2026.1'
        }, user.id);
      } catch (consentErr) {
        console.warn('Privacy consent backend sync notice:', consentErr);
      }

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
            {currentStep === 1 && 'Personal Profile'}
            {currentStep === 2 && 'Skin Tone'}
            {currentStep === 3 && 'Body Silhouette'}
            {currentStep === 4 && 'Hairstyle & Appearance'}
            {currentStep === 5 && 'Review Profile'}
          </p>
        </div>

        {/* Wizard Card Body */}
        <div ref={cardRef} className="onboarding-card">
          <div className="wizard-split-layout">
            {/* Left: Persistent 3D Avatar Viewport across ALL steps */}
            <div className="wizard-avatar-column">
              <div className="canvas-wrapper">
                {character ? (
                  <AvatarStudioViewer
                    character={character}
                    lib={library}
                    loading={characterLoading}
                    loadingLabel={loadingLabel}
                    viewMode={onboardingViewMode}
                    showSunglasses={false}
                    activeAnimation="idle"
                    bodySilhouetteId={selectedBodyType.id}
                    isOnboarding={true}
                  />
                ) : (
                  <AvatarSkeletonLoader
                    loadingLabel={loadingLabel}
                    theme="light"
                    title="Yorvyn Avatar"
                  />
                )}
                <div className="canvas-hint-pill">
                  <ArrowCounterClockwise size={13} /> Drag to rotate your 3D model
                </div>
              </div>
            </div>

            {/* Right: Step-by-Step Configuration Panels */}
            <div className="wizard-step-column">
              {/* ── STEP 1: Basic Profile ── */}
              {currentStep === 1 && (
                <div ref={stepBodyRef} className="onboarding-step-body">
                  <div className="step-header-fixed">
                    <h2 className="step-heading">Personal Profile</h2>
                    <p className="step-subtext">
                      Set your styling profile and measurements.
                    </p>
                  </div>

                  <div className="step-scroll-content">
                    {/* Full Name */}
                    <div className="step-field-group">
                      <label className="step-field-label">Full Name / Alias</label>
                      <input
                        type="text"
                        className="step-text-input"
                        placeholder="e.g. Aarav, Ananya, Kabir, Priya"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        maxLength={40}
                        required
                      />
                    </div>

                    {/* Gender Selector */}
                    <div className="step-field-group">
                      <label className="step-field-label">Gender</label>
                      <div className="gender-segmented-track" role="radiogroup" aria-label="Gender">
                        {[
                          { id: 'female', label: 'Female' },
                          { id: 'male', label: 'Male' },
                          { id: 'non-binary', label: 'Non-binary' },
                        ].map((opt) => (
                          <button
                            key={opt.id}
                            type="button"
                            role="radio"
                            aria-checked={gender === opt.id}
                            className={`gender-segmented-pill ${gender === opt.id ? 'active' : ''}`}
                            onClick={() => {
                              setGender(opt.id as any);
                              if (opt.id === 'female') setAvatarPresentation('feminine');
                              else if (opt.id === 'male') setAvatarPresentation('masculine');
                              else setAvatarPresentation('neutral');
                            }}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Phone & Age */}
                    <div className="step-field-row">
                      <div className="step-field-group flex-1">
                        <label className="step-field-label">Phone Number</label>
                        <input
                          type="tel"
                          className="step-text-input"
                          placeholder="+91 98765 43210"
                          value={phoneNumber}
                          onChange={(e) => setPhoneNumber(e.target.value)}
                        />
                      </div>
                      <div className="step-field-group" style={{ width: '100px' }}>
                        <label className="step-field-label">Age</label>
                        <input
                          type="number"
                          className="step-text-input"
                          min={13}
                          max={110}
                          value={age}
                          onChange={(e) => setAge(parseInt(e.target.value) || 20)}
                        />
                      </div>
                    </div>

                    {/* Location */}
                    <div className="step-field-group">
                      <label className="step-field-label">Location / City</label>
                      <input
                        type="text"
                        className="step-text-input"
                        placeholder="e.g. Mumbai, Delhi, Bengaluru, Jaipur"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        maxLength={60}
                      />
                    </div>

                    {/* Height & Weight */}
                    <div className="step-field-row">
                      <div className="step-field-group flex-1">
                        <label className="step-field-label">Height</label>
                        <div className="input-with-unit">
                          <input
                            type="number"
                            className="step-text-input"
                            value={heightValue}
                            onChange={(e) => setHeightValue(Number(e.target.value))}
                            min={100}
                            max={250}
                          />
                          <div className="inline-unit-toggle">
                            <button
                              type="button"
                              className={`unit-pill ${heightUnit === 'cm' ? 'active' : ''}`}
                              onClick={() => setHeightUnit('cm')}
                            >
                              cm
                            </button>
                            <button
                              type="button"
                              className={`unit-pill ${heightUnit === 'ft' ? 'active' : ''}`}
                              onClick={() => setHeightUnit('ft')}
                            >
                              ft
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="step-field-group flex-1">
                        <label className="step-field-label">Weight</label>
                        <div className="input-with-unit">
                          <input
                            type="number"
                            className="step-text-input"
                            value={weightValue}
                            onChange={(e) => setWeightValue(Number(e.target.value))}
                            min={30}
                            max={300}
                          />
                          <div className="inline-unit-toggle">
                            <button
                              type="button"
                              className={`unit-pill ${weightUnit === 'kg' ? 'active' : ''}`}
                              onClick={() => setWeightUnit('kg')}
                            >
                              kg
                            </button>
                            <button
                              type="button"
                              className={`unit-pill ${weightUnit === 'lbs' ? 'active' : ''}`}
                              onClick={() => setWeightUnit('lbs')}
                            >
                              lbs
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── STEP 2: Skin Tone ── */}
              {currentStep === 2 && (
                <div ref={stepBodyRef} className="onboarding-step-body">
                  <div className="step-header-fixed">
                    <h2 className="step-heading">Skin Tone</h2>
                    <p className="step-subtext">
                      Select your avatar's complexion.
                    </p>
                  </div>

                  <div className="step-scroll-content">
                    <div className="squircle-grid squircle-grid-3" role="radiogroup" aria-label="Avatar Skin Tone">
                      {SKIN_TONES.map((tone) => {
                        const isSelected = selectedSkinTone.id === tone.id;
                        return (
                          <button
                            key={tone.id}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            className={`squircle-card ${isSelected ? 'selected' : ''}`}
                            onClick={(e) => handleSelectSkinTone(tone, e)}
                            aria-label={tone.name}
                          >
                            {isSelected && (
                              <div className="squircle-check-badge">
                                <Check size={11} strokeWidth={3} />
                              </div>
                            )}
                            <SkinToneMannequinVisual
                              hex={tone.hex}
                              isSelected={isSelected}
                            />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* ── STEP 3: Body Silhouette ── */}
              {currentStep === 3 && (
                <div ref={stepBodyRef} className="onboarding-step-body">
                  <div className="step-header-fixed">
                    <h2 className="step-heading">Body Silhouette</h2>
                    <p className="step-subtext">
                      Select your body archetype.
                    </p>
                  </div>

                  <div className="step-scroll-content">
                    <div className="squircle-grid squircle-grid-3" role="radiogroup" aria-label="Body Silhouette">
                      {BODY_TYPES.map((bt) => {
                        const isSelected = selectedBodyType.id === bt.id;
                        return (
                          <button
                            key={bt.id}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            className={`squircle-card body-card ${isSelected ? 'selected' : ''}`}
                            onClick={(e) => handleSelectBodyType(bt, e)}
                            aria-label={bt.name}
                          >
                            {isSelected && (
                              <div className="squircle-check-badge">
                                <Check size={11} strokeWidth={3} />
                              </div>
                            )}
                            <SilhouetteMannequinVisual
                              type={bt.id as any}
                              isSelected={isSelected}
                            />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* ── STEP 4: Hair & Virtual Appearance ── */}
              {currentStep === 4 && (
                <div ref={stepBodyRef} className="onboarding-step-body">
                  <div className="step-header-fixed">
                    <h2 className="step-heading">Hairstyle & Appearance</h2>
                    <p className="step-subtext">
                      Choose hairstyle, hair color, and silhouette.
                    </p>
                  </div>

                  <div className="step-scroll-content">
                    {/* Hairstyles Grid */}
                    <label className="step-field-label" style={{ marginBottom: '8px', display: 'block' }}>Hairstyle</label>
                    <div className="squircle-grid squircle-grid-4" role="radiogroup" aria-label="Hairstyle">
                      {HAIR_STYLES.map((style) => {
                        const isSelected = selectedHairStyle === style.id;
                        return (
                          <button
                            key={style.id}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            className={`squircle-card ${isSelected ? 'selected' : ''}`}
                            onClick={(e) => handleSelectHairStyle(style.id, e)}
                            aria-label={style.name}
                          >
                            {isSelected && (
                              <div className="squircle-check-badge">
                                <Check size={11} strokeWidth={3} />
                              </div>
                            )}
                            <HairStyleMannequinVisual
                              styleId={style.id}
                              hairColorHex={selectedHairColor.hex}
                              isSelected={isSelected}
                            />
                          </button>
                        );
                      })}
                    </div>

                    {/* Hair Color Swatches */}
                    <label className="step-field-label" style={{ marginTop: '16px', marginBottom: '8px', display: 'block' }}>Hair Color</label>
                    <div className="squircle-grid squircle-grid-4" role="radiogroup" aria-label="Hair Color">
                      {HAIR_COLORS.map((hair) => {
                        const isSelected = selectedHairColor.id === hair.id;
                        return (
                          <button
                            key={hair.id}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            className={`squircle-card ${isSelected ? 'selected' : ''}`}
                            onClick={(e) => handleSelectHairColor(hair, e)}
                            aria-label={hair.name}
                          >
                            {isSelected && (
                              <div className="squircle-check-badge">
                                <Check size={11} strokeWidth={3} />
                              </div>
                            )}
                            <HairColorSwatchVisual
                              hex={hair.hex}
                              name={hair.name}
                              isSelected={isSelected}
                            />
                          </button>
                        );
                      })}
                    </div>

                    {/* Virtual Presentation */}
                    <label className="step-field-label" style={{ marginTop: '16px', marginBottom: '8px', display: 'block' }}>Silhouette</label>
                    <div className="squircle-grid squircle-grid-3" role="radiogroup" aria-label="Styling Silhouette">
                      {(['feminine', 'neutral', 'masculine'] as const).map((pres) => {
                        const isSelected = avatarPresentation === pres;
                        const label = pres.charAt(0).toUpperCase() + pres.slice(1);
                        return (
                          <button
                            key={pres}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            className={`squircle-card ${isSelected ? 'selected' : ''}`}
                            onClick={(e) => handleSelectPresentation(pres, e)}
                            aria-label={label}
                          >
                            {isSelected && (
                              <div className="squircle-check-badge">
                                <Check size={11} strokeWidth={3} />
                              </div>
                            )}
                            <PresentationVisual
                              presentation={pres}
                              isSelected={isSelected}
                            />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* ── STEP 5: Avatar Preview & Confirmation ── */}
              {currentStep === 5 && (
                <div ref={stepBodyRef} className="onboarding-step-body">
                  <div className="step-header-fixed">
                    <h2 className="step-heading">Review Profile</h2>
                    <p className="step-subtext">
                      Your 3D avatar is ready.
                    </p>
                  </div>

                  <div className="step-scroll-content">
                    <div className="summary-col">
                      <div className="summary-card">
                        <span className="summary-card-label">Identity</span>
                        <span className="summary-card-val">
                          {displayName}, {age} yrs • {gender === 'female' ? 'Female' : gender === 'male' ? 'Male' : 'Non-binary'}
                        </span>
                      </div>

                      <div className="summary-card">
                        <span className="summary-card-label">Contact & Location</span>
                        <span className="summary-card-val">
                          {phoneNumber || 'No phone provided'} • {location || 'Global'}
                        </span>
                      </div>

                      <div className="summary-card">
                        <span className="summary-card-label">Measurements & Silhouette</span>
                        <span className="summary-card-val">
                          {heightValue} {heightUnit} • {weightValue} {weightUnit} • {selectedBodyType.name}
                        </span>
                      </div>

                      <div className="summary-card">
                        <span className="summary-card-label">Skin Tone</span>
                        <div className="summary-color-row">
                          <span className="mini-color-dot" style={{ backgroundColor: selectedSkinTone.hex }} />
                          <span>{selectedSkinTone.name}</span>
                        </div>
                      </div>

                      <div className="summary-card">
                        <span className="summary-card-label">Hair & Silhouette</span>
                        <div className="summary-color-row">
                          <span className="mini-color-dot" style={{ backgroundColor: selectedHairColor.hex }} />
                          <span>{selectedHairColor.name} • {avatarPresentation}</span>
                        </div>
                      </div>

                      {/* Phase 9: Explicit Privacy & Ephemeral Processing Agreement */}
                      <div className="summary-card" style={{ border: '1px solid rgba(96, 165, 250, 0.3)', background: 'rgba(30, 41, 59, 0.45)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
                          <ShieldCheck size={18} style={{ color: '#60a5fa' }} />
                          <span className="summary-card-label" style={{ color: '#93c5fd', fontWeight: 600, textTransform: 'none' }}>
                            Privacy & AI Transparency
                          </span>
                        </div>

                        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', cursor: 'pointer', marginBottom: '0.6rem' }}>
                          <input
                            type="checkbox"
                            checked={ephemeralProcessingConsent}
                            onChange={(e) => setEphemeralProcessingConsent(e.target.checked)}
                            style={{ marginTop: '0.2rem', accentColor: '#3b82f6' }}
                          />
                          <span style={{ fontSize: '0.8rem', color: '#e2e8f0', lineHeight: 1.35 }}>
                            <strong>Ephemeral 3D Reconstruction:</strong> Images are used strictly to reconstruct 3D garments and fit your avatar, then deleted immediately. (Required)
                          </span>
                        </label>

                        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={aiTrainingOptIn}
                            onChange={(e) => setAiTrainingOptIn(e.target.checked)}
                            style={{ marginTop: '0.2rem', accentColor: '#3b82f6' }}
                          />
                          <span style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.35 }}>
                            <strong>Model Training Opt-In:</strong> Help improve Yorvyn's neural reconstruction with anonymized clothing data. (Optional, default OFF)
                          </span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

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
                disabled={isSubmitting || !ephemeralProcessingConsent}
                title={!ephemeralProcessingConsent ? 'Ephemeral processing consent is required to create your 3D avatar' : ''}
              >
                {isSubmitting ? 'Personalizing...' : 'Confirm & Enter Studio'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

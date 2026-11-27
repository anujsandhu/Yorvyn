/**
 * YORVYN — PHASE 7: Complete Snap-Style 3D Avatar Creator Studio Component
 * 
 * Bitmoji & modern virtual character creation experience:
 * - 13 categories (Body, Face, Eyes, Brows, Nose, Mouth, Ears, Hair, Beard, Skin, Clothing, Accs, Emotes)
 * - Visual preset cards with live active badges
 * - Fine-tuning sliders with zero-center markers and live numerical feedback
 * - Comprehensive color swatch grids (hair, eyes, skin, lips)
 * - Undo / Redo history with keyboard shortcuts
 * - "Hold to Compare" original vs current appearance
 * - Granular per-category resets & safe confirmation for full character reset
 * - Seamless camera framing director integration
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { luxuryToast } from '../../utils/luxuryToast';
import {
  Eye,
  Sparkle,
  ArrowCounterClockwise,
  ArrowClockwise,
  Check,
  FloppyDisk,
  Trash,
  ArrowsOut,
  User,
  Scissors,
  Smiley,
  Sunglasses,
  Camera
} from '../icons';
import {
  AvatarCreatorCategory,
  CategorySubView,
  AvatarCreatorHistory
} from '../../engine/avatarCreator/avatarCreatorTypes';
import {
  CATEGORY_TABS,
  AVATAR_SLIDERS,
  AVATAR_PRESETS,
  HAIR_COLOR_SWATCHES,
  EYE_COLOR_SWATCHES,
  LIP_COLOR_SWATCHES,
  CLOTHING_COLOR_SWATCHES
} from '../../engine/avatarCreator/avatarCreatorAssetRegistry';
import { AvatarCreatorEngine } from '../../engine/avatarCreator/avatarCreatorEngine';
import { AvatarStudioViewerHandle } from '../AvatarStudioViewer';
import { AvatarProfile } from '../../types/avatarProfile';
import { AvatarMannequinThumbnail } from './AvatarMannequinThumbnail';
import './AvatarCreatorStudio.css';

export interface AvatarCreatorStudioProps {
  engine: AvatarCreatorEngine;
  viewerRef?: React.RefObject<AvatarStudioViewerHandle>;
  onProfileChange?: (profile: AvatarProfile) => void;
  userId?: string;
  onSaveSuccess?: () => void;
  selectedCategory?: AvatarCreatorCategory;
  onCategoryChange?: (category: AvatarCreatorCategory) => void;
  hideInternalCategoryTabs?: boolean;
}

export type AvatarMainGroup = 'general' | 'hair' | 'face' | 'body' | 'additional';

export interface AvatarSubOption {
  id: string;
  label: string;
  category: AvatarCreatorCategory;
  subView: CategorySubView;
  isSpecialPhoto?: boolean;
}

export interface AvatarMainGroupMeta {
  id: AvatarMainGroup;
  label: string;
  icon: React.ComponentType<any>;
  cameraFocus: 'full' | 'head' | 'torso';
  subOptions: AvatarSubOption[];
}

export const AVATAR_GROUPS: AvatarMainGroupMeta[] = [
  {
    id: 'general',
    label: 'General',
    icon: User,
    cameraFocus: 'full',
    subOptions: [
      { id: 'photo_ref', label: 'Reference / Scan', category: 'body', subView: 'styling', isSpecialPhoto: true },
      { id: 'body_base', label: 'Body Base', category: 'body', subView: 'presets' },
      { id: 'face_base', label: 'Face Base', category: 'face', subView: 'presets' },
      { id: 'skin_base', label: 'Skin Complexion', category: 'skin', subView: 'colors' }
    ]
  },
  {
    id: 'hair',
    label: 'Hair',
    icon: Scissors,
    cameraFocus: 'head',
    subOptions: [
      { id: 'hairstyles', label: 'Hairstyles', category: 'hair', subView: 'presets' },
      { id: 'hair_length', label: 'Length & Volume', category: 'hair', subView: 'sliders' },
      { id: 'hair_colour', label: 'Hair Colour', category: 'hair', subView: 'colors' },
      { id: 'facial_hair', label: 'Facial Hair', category: 'facial_hair', subView: 'presets' },
      { id: 'beard_colour', label: 'Beard Colour', category: 'facial_hair', subView: 'colors' }
    ]
  },
  {
    id: 'face',
    label: 'Face',
    icon: Smiley,
    cameraFocus: 'head',
    subOptions: [
      { id: 'face_shape', label: 'Face Shape', category: 'face', subView: 'presets' },
      { id: 'jaw_chin', label: 'Jaw & Contours', category: 'face', subView: 'sliders' },
      { id: 'eyes', label: 'Eyes & Gaze', category: 'eyes', subView: 'sliders' },
      { id: 'eye_colour', label: 'Eye Iris Tone', category: 'eyes', subView: 'colors' },
      { id: 'eyebrows', label: 'Eyebrows', category: 'eyebrows', subView: 'sliders' },
      { id: 'nose', label: 'Nose Profile', category: 'nose', subView: 'sliders' },
      { id: 'lips', label: 'Lips & Mouth', category: 'mouth', subView: 'sliders' },
      { id: 'lip_tint', label: 'Lip Tint', category: 'mouth', subView: 'colors' },
      { id: 'ears', label: 'Ears', category: 'ears', subView: 'sliders' }
    ]
  },
  {
    id: 'body',
    label: 'Body',
    icon: ArrowsOut,
    cameraFocus: 'full',
    subOptions: [
      { id: 'height_stature', label: 'Height & Stature', category: 'body', subView: 'sliders' },
      { id: 'silhouette', label: 'Body Silhouette', category: 'body', subView: 'presets' },
      { id: 'proportions', label: 'Torso & Shoulders', category: 'body', subView: 'sliders' }
    ]
  },
  {
    id: 'additional',
    label: 'Additional',
    icon: Sunglasses,
    cameraFocus: 'torso',
    subOptions: [
      { id: 'glasses', label: 'Glasses & Eyewear', category: 'accessories', subView: 'presets' },
      { id: 'emotes', label: 'Expressions & Emotes', category: 'expressions', subView: 'styling' }
    ]
  }
];

export const AvatarCreatorStudio: React.FC<AvatarCreatorStudioProps> = ({
  engine,
  viewerRef,
  onProfileChange,
  userId = '',
  onSaveSuccess,
  selectedCategory,
  onCategoryChange,
  hideInternalCategoryTabs = false
}) => {
  const [activeMainGroup, setActiveMainGroup] = useState<AvatarMainGroup>('hair');
  const [activeSubOptionId, setActiveSubOptionId] = useState<string>('hairstyles');
  const [activeCategory, setActiveCategory] = useState<AvatarCreatorCategory>(selectedCategory || 'hair');
  const [activeSubView, setActiveSubView] = useState<CategorySubView>('presets');

  // Synchronize category if passed from Level 2 Secondary Navigation
  useEffect(() => {
    if (selectedCategory && selectedCategory !== activeCategory) {
      setActiveCategory(selectedCategory);
      const targetMeta = CATEGORY_TABS.find(t => t.id === selectedCategory);
      if (targetMeta?.subViews.length) {
        setActiveSubView(targetMeta.subViews[0]);
      }
    }
  }, [selectedCategory, activeCategory]);
  const [profile, setProfile] = useState<AvatarProfile>(() => engine.getProfile());
  const [history, setHistory] = useState<AvatarCreatorHistory>(() => engine.getHistory());
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [showResetModal, setShowResetModal] = useState<boolean>(false);

  // Subscribe to Engine State Changes
  useEffect(() => {
    const unsubscribe = engine.subscribe((newProfile, newHistory, comparing) => {
      setProfile(newProfile);
      setHistory(newHistory);
      setIsComparing(comparing);
      onProfileChange?.(newProfile);
    });
    return unsubscribe;
  }, [engine, onProfileChange]);

  // Active Category Meta
  const currentTabMeta = useMemo(() => {
    return CATEGORY_TABS.find(t => t.id === activeCategory) || CATEGORY_TABS[0];
  }, [activeCategory]);

  const currentGroupMeta = useMemo(() => {
    return AVATAR_GROUPS.find(g => g.id === activeMainGroup) || AVATAR_GROUPS[0];
  }, [activeMainGroup]);

  // Handle switching between the 5 top categories
  const handleMainGroupSwitch = useCallback((group: AvatarMainGroup) => {
    setActiveMainGroup(group);
    const groupMeta = AVATAR_GROUPS.find(g => g.id === group) || AVATAR_GROUPS[0];
    if (groupMeta.cameraFocus === 'head') {
      viewerRef?.current?.focusHead?.();
    } else if (groupMeta.cameraFocus === 'torso') {
      viewerRef?.current?.focusTorso?.();
    } else {
      viewerRef?.current?.focusFullBody?.();
    }

    const firstSub = groupMeta.subOptions[0];
    if (firstSub) {
      setActiveSubOptionId(firstSub.id);
      setActiveCategory(firstSub.category);
      setActiveSubView(firstSub.subView);
      onCategoryChange?.(firstSub.category);
    }
  }, [viewerRef, onCategoryChange]);

  // Handle switching sub-options within active category
  const handleSubOptionSwitch = useCallback((sub: AvatarSubOption) => {
    setActiveSubOptionId(sub.id);
    setActiveCategory(sub.category);
    setActiveSubView(sub.subView);
    onCategoryChange?.(sub.category);

    const targetMeta = CATEGORY_TABS.find(t => t.id === sub.category);
    if (!targetMeta || !viewerRef?.current) return;
    if (targetMeta.cameraFocus === 'head') viewerRef.current.focusHead?.();
    else if (targetMeta.cameraFocus === 'torso') viewerRef.current.focusTorso?.();
    else if (targetMeta.cameraFocus === 'feet') viewerRef.current.focusFeet?.();
    else viewerRef.current.focusFullBody?.();
  }, [viewerRef]);

  // Ensure activeSubView is valid for the selected category
  useEffect(() => {
    if (!currentTabMeta.subViews.includes(activeSubView)) {
      setActiveSubView(currentTabMeta.subViews[0]);
    }
  }, [currentTabMeta, activeSubView]);


  // Keyboard Shortcuts (Cmd+Z / Cmd+Shift+Z)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const modKey = isMac ? e.metaKey : e.ctrlKey;

      if (modKey && e.key === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          if (engine.redo()) {
            luxuryToast.redo('Redo');
          }
        } else {
          if (engine.undo()) {
            luxuryToast.undo('Undo');
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [engine]);

  // Save Character Profile
  const handleSave = async () => {
    setIsSaving(true);
    try {
      await engine.save(userId);
      luxuryToast.saved('Avatar profile saved permanently!');
      onSaveSuccess?.();
    } catch (err: any) {
      luxuryToast.error('Failed to save profile: ' + (err.message || 'Network error'));
    } finally {
      setIsSaving(false);
    }
  };

  // Helper to read nested profile values
  const getNestedValue = (path: string, defaultValue: number): number => {
    const keys = path.split('.');
    let curr: any = profile;
    for (const k of keys) {
      if (curr && typeof curr === 'object' && k in curr) {
        curr = curr[k];
      } else {
        return defaultValue;
      }
    }
    return typeof curr === 'number' ? curr : defaultValue;
  };

  // Helper to update a slider value
  const handleSliderChange = (slider: typeof AVATAR_SLIDERS['body'][0], value: number) => {
    if (!slider.profilePath) return;

    const [domain, field] = slider.profilePath.split('.');
    if (domain === 'proportions') {
      engine.updateProfile(
        { proportions: { ...profile.proportions, [field]: value } },
        activeCategory,
        `Adjusted ${slider.label}`
      );
    } else if (domain === 'face') {
      engine.updateProfile(
        { face: { ...profile.face, [field]: value } },
        activeCategory,
        `Adjusted ${slider.label}`
      );
    } else if (domain === 'appearance') {
      engine.updateProfile(
        { appearance: { ...profile.appearance, [field]: value } },
        activeCategory,
        `Adjusted ${slider.label}`
      );
    }
  };

  // Render Preset Cards — VISUAL-ONLY 3D MANNEQUIN SELECTION
  const renderPresets = () => {
    const presets = AVATAR_PRESETS[activeCategory] || [];
    if (presets.length === 0) {
      return (
        <div style={{ padding: '2rem 1rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
          No preset options for this category.
        </div>
      );
    }

    return (
      <div className={`presets-grid ${activeCategory === 'body' ? 'body-presets-grid' : ''}`}>
        {presets.map((preset) => {
          // Check active state
          let isActive = false;
          if (activeCategory === 'body' && profile.proportions.silhouette === preset.id) isActive = true;
          if (activeCategory === 'face' && profile.face.faceShapePreset === preset.id) isActive = true;
          if (activeCategory === 'hair' && profile.appearance.hairStyleId === preset.id) isActive = true;
          if (activeCategory === 'facial_hair' && profile.appearance.facialHairId === preset.id) isActive = true;
          if (activeCategory === 'skin' && profile.appearance.skinToneId === preset.id) isActive = true;
          if (activeCategory === 'clothing') {
            if (preset.id === 'undress_mannequin' && profile.wardrobe.isBareMannequin) isActive = true;
            else if (profile.wardrobe.outfitId === preset.id || profile.wardrobe.topId === preset.id) isActive = true;
          }
          if (activeCategory === 'accessories') {
            if (preset.id === 'sunglasses' && profile.wardrobe.sunglasses) isActive = true;
            else if (profile.wardrobe.accessories.includes(preset.id)) isActive = true;
          }
          if (activeCategory === 'expressions' && profile.face.restingExpression === preset.id) isActive = true;

          return (
            <motion.div
              key={preset.id}
              className={`preset-card visual-only ${isActive ? 'active' : ''} ${activeCategory === 'body' ? 'body-preset-card' : ''}`}
              onClick={() => {
                const patch = preset.apply(profile);
                engine.updateProfile(patch, activeCategory, `Applied ${preset.name}`);
              }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              role="button"
              tabIndex={0}
              aria-label={preset.name}
              aria-pressed={isActive}
            >
              <div className="preset-visual-container">
                <AvatarMannequinThumbnail
                  category={activeCategory}
                  presetId={preset.id}
                  preset={preset}
                />
              </div>

              {isActive && (
                <div className="preset-selected-pip" aria-hidden="true">
                  <Check size={11} weight="bold" />
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    );
  };

  // Render Fine Tuning Sliders
  const renderSliders = () => {
    const sliders = AVATAR_SLIDERS[activeCategory] || [];
    if (sliders.length === 0) {
      return (
        <div style={{ padding: '2rem 1rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
          No sliders defined for this category.
        </div>
      );
    }

    return (
      <div className="sliders-list">
        {sliders.map((slider) => {
          const val = slider.profilePath ? getNestedValue(slider.profilePath, slider.defaultValue) : slider.defaultValue;
          const displayVal = slider.unit === 'cm'
            ? `${Math.round(val)} cm`
            : slider.unit === '%'
              ? `${Math.round(val * 100)}%`
              : slider.bipolar
                ? (val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2))
                : val.toFixed(2);

          return (
            <div key={slider.id} className="slider-card">
              <div className="slider-header">
                <span className="slider-label">{slider.label}</span>
                <div className="slider-val-wrap">
                  <span className="slider-value-readout">{displayVal}</span>
                  {slider.bipolar && (
                    <button
                      type="button"
                      className="slider-reset-zero"
                      onClick={() => handleSliderChange(slider, 0.0)}
                      title="Reset to neutral center"
                    >
                      <ArrowCounterClockwise size={12} />
                    </button>
                  )}
                </div>
              </div>
              <div className="slider-track-wrap">
                <input
                  type="range"
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  value={val}
                  onChange={(e) => handleSliderChange(slider, parseFloat(e.target.value))}
                  className="range-input"
                />
                {slider.bipolar && <div className="bipolar-center-indicator" />}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // Render Color Swatches
  const renderColors = () => {
    let swatches = HAIR_COLOR_SWATCHES;
    let currentColor = profile.appearance.hairColorHex;
    let title = 'Hairstyle & Fiber Color Tone';
    let onColorSelect = (hex: string) => {
      engine.updateProfile(
        { appearance: { ...profile.appearance, hairColorHex: hex } },
        activeCategory,
        'Changed hair color'
      );
    };

    if (activeCategory === 'eyes') {
      swatches = EYE_COLOR_SWATCHES;
      currentColor = EYE_COLOR_SWATCHES.find(e => e.id === profile.appearance.eyeColorId)?.hex || '#6b4423';
      title = 'Photorealistic Iris Color';
      onColorSelect = (hex: string) => {
        const found = EYE_COLOR_SWATCHES.find(e => e.hex.toLowerCase() === hex.toLowerCase());
        engine.updateProfile(
          { appearance: { ...profile.appearance, eyeColorId: found?.id || 'brownlight' } },
          'eyes',
          'Changed eye color'
        );
      };
    } else if (activeCategory === 'mouth') {
      swatches = LIP_COLOR_SWATCHES;
      currentColor = profile.face.lipColorHex || '#d48b76';
      title = 'Lipstick & Lip Tint Swatches';
      onColorSelect = (hex: string) => {
        engine.updateProfile(
          { face: { ...profile.face, lipColorHex: hex } },
          'mouth',
          'Changed lip color'
        );
      };
    } else if (activeCategory === 'facial_hair') {
      swatches = HAIR_COLOR_SWATCHES;
      currentColor = profile.appearance.facialHairColorHex;
      title = 'Beard & Mustache Color Tone';
      onColorSelect = (hex: string) => {
        engine.updateProfile(
          { appearance: { ...profile.appearance, facialHairColorHex: hex } },
          'facial_hair',
          'Changed beard color'
        );
      };
    } else if (activeCategory === 'skin') {
      currentColor = profile.appearance.skinToneHex;
      title = 'Skin Undertones & Complexion Tint';
      onColorSelect = (hex: string) => {
        engine.updateProfile(
          { appearance: { ...profile.appearance, skinToneHex: hex } },
          'skin',
          'Changed skin tone tint'
        );
      };
    } else if (activeCategory === 'clothing') {
      swatches = CLOTHING_COLOR_SWATCHES;
      currentColor = profile.wardrobe.garmentStyles?.default?.color || '#0f172a';
      title = 'Garment Color & Fabric Hue';
      onColorSelect = (hex: string) => {
        engine.updateProfile(
          {
            wardrobe: {
              ...profile.wardrobe,
              garmentStyles: {
                ...(profile.wardrobe.garmentStyles || {}),
                default: {
                  ...(profile.wardrobe.garmentStyles?.default || {}),
                  color: hex
                }
              }
            }
          },
          'clothing',
          'Changed clothing color'
        );
      };
    }

    return (
      <div className="color-swatches-section">
        <div className="color-swatches-grid" role="radiogroup" aria-label={title}>
          {swatches.map((swatch) => {
            const isSelected = currentColor?.toLowerCase() === swatch.hex.toLowerCase();
            return (
              <button
                key={swatch.id}
                type="button"
                className={`color-swatch-circle ${isSelected ? 'active' : ''}`}
                style={{ backgroundColor: swatch.hex }}
                onClick={() => {
                  onColorSelect(swatch.hex);
                }}
                aria-label={swatch.name}
                aria-checked={isSelected}
                role="radio"
              >
                {isSelected && <Check size={14} color="#ffffff" weight="bold" />}
              </button>
            );
          })}
        </div>

        {/* Custom Hex Color Picker */}
        <div className="custom-color-picker-row">
          <input
            type="color"
            value={currentColor || '#ffffff'}
            onChange={(e) => onColorSelect(e.target.value)}
            className="custom-color-input"
            title="Custom Palette Hue"
            aria-label="Custom Palette Hue"
          />
        </div>
      </div>
    );
  };

  // Render Additional Styling / Emotes (Visual-Only Mannequins)
  const renderStyling = () => {
    if (activeCategory === 'clothing') {
      const isBare = profile.wardrobe.isBareMannequin;
      return (
        <div className="styling-section">
          <div className="presets-grid">
            <motion.div
              className={`preset-card visual-only ${isBare ? 'active' : ''}`}
              onClick={() => {
                engine.updateProfile(
                  {
                    wardrobe: {
                      ...profile.wardrobe,
                      isBareMannequin: true,
                      outfitId: 'none',
                      topId: 'none',
                      bottomId: 'none',
                      shoesId: 'none',
                      outerwearId: 'none'
                    }
                  },
                  'clothing',
                  'Undressed to bare mannequin base'
                );
                toast.success('Undressed to bare mannequin');
              }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              role="button"
              tabIndex={0}
              aria-label="Bare Atelier Mannequin Base"
              title="Bare Atelier Mannequin Base"
              aria-pressed={isBare}
            >
              <div className="preset-visual-container">
                <AvatarMannequinThumbnail
                  category="clothing"
                  presetId="undress_mannequin"
                  preset={{
                    id: 'undress_mannequin',
                    category: 'clothing',
                    name: 'Bare Atelier Mannequin Base',
                    apply: () => ({})
                  }}
                />
              </div>
              {isBare && (
                <div className="preset-selected-pip" aria-hidden="true">
                  <Check size={11} weight="bold" />
                </div>
              )}
            </motion.div>
          </div>
        </div>
      );
    }

    if (activeCategory === 'expressions') {
      const anims = [
        { id: 'Idle', name: 'Natural Breathing Idle' },
        { id: 'Wave', name: 'Friendly Wave' },
        { id: 'Thumbs Up', name: 'Positive Thumbs Up' },
        { id: 'Thumbs Down', name: 'Critique Thumbs Down' },
        { id: 'Turn', name: '360° Runway Spin' },
        { id: 'Present Outfit', name: 'Editorial Outfit Present' },
        { id: 'Look at Garment', name: 'Garment Inspection' }
      ];

      return (
        <div className="styling-section">
          <div className="presets-grid">
            {anims.map((anim) => (
              <motion.button
                key={anim.id}
                type="button"
                className="preset-card visual-only"
                onClick={() => {
                  viewerRef?.current?.playReaction(anim.id);
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                aria-label={anim.name}
              >
                <div className="preset-visual-container">
                  <AvatarMannequinThumbnail
                    category="expressions"
                    presetId={anim.id}
                    preset={{
                      id: anim.id,
                      category: 'expressions',
                      name: anim.name,
                      apply: () => ({})
                    }}
                  />
                </div>
              </motion.button>
            ))}
          </div>
        </div>
      );
    }

    return renderPresets();
  };

  // Render Photo / AI Reference Scan View
  const renderPhotoRefView = () => (
    <div className="avatar-photo-ref-panel">
      <div className="photo-ref-glass-card">
        <div className="photo-ref-icon-circle">
          <Camera size={36} weight="regular" />
        </div>
        <h4 className="photo-ref-title">AI Photo Scan & Face Capture</h4>
        <p className="photo-ref-desc">
          Capture or upload your portrait to analyze facial structure, skin tone,
          and hair texture, generating your photorealistic 3D twin instantly.
        </p>
        <button
          type="button"
          className="photo-ref-launch-btn"
          onClick={() => {
            luxuryToast.info('Use the photo tool inside the Studio tray');
          }}
        >
          <Sparkle size={15} weight="fill" />
          <span>Launch AI Photo Scan</span>
        </button>
      </div>
    </div>
  );

  return (
    <div className="avatar-creator-container">
      {/* ── Top Bar with Undo / Redo / Compare / Reset / Save ── */}
      <div className="avatar-creator-topbar">
        <div className="topbar-group">
          <button
            type="button"
            className="topbar-btn"
            onClick={() => {
              if (engine.undo()) luxuryToast.undo('Undo');
            }}
            disabled={!history.canUndo}
            title="Undo last modification (Cmd+Z)"
          >
            <ArrowCounterClockwise size={14} weight="bold" />
            <span>Undo</span>
          </button>
          <button
            type="button"
            className="topbar-btn"
            onClick={() => {
              if (engine.redo()) luxuryToast.redo('Redo');
            }}
            disabled={!history.canRedo}
            title="Redo (Cmd+Shift+Z)"
          >
            <ArrowClockwise size={14} weight="bold" />
            <span>Redo</span>
          </button>
        </div>

        <div className="topbar-group">
          {/* Hold / Click to Compare Button */}
          <button
            type="button"
            className={`topbar-btn compare-btn ${isComparing ? 'comparing' : ''}`}
            onMouseDown={() => engine.setComparing(true)}
            onMouseUp={() => engine.setComparing(false)}
            onMouseLeave={() => engine.setComparing(false)}
            onTouchStart={() => engine.setComparing(true)}
            onTouchEnd={() => engine.setComparing(false)}
            title="Hold to temporarily compare with initial character"
          >
            <Eye size={14} weight="bold" />
            <span>{isComparing ? 'Comparing...' : 'Compare'}</span>
          </button>

          {/* Reset Active Category */}
          <button
            type="button"
            className="topbar-btn"
            onClick={() => {
              engine.resetCategory(activeCategory);
              toast.success(`Reset ${currentTabMeta.label} to defaults`, { duration: 1200 });
            }}
            title={`Reset only ${currentTabMeta.label} without altering other features`}
          >
            <span>Reset {currentTabMeta.label}</span>
          </button>

          {/* Reset All (with confirmation dialog) */}
          <button
            type="button"
            className="topbar-btn"
            onClick={() => setShowResetModal(true)}
            title="Reset entire avatar back to initial baseline"
          >
            <Trash size={14} />
          </button>

          {/* Save Avatar */}
          <button
            type="button"
            className="topbar-btn save-btn"
            onClick={handleSave}
            disabled={isSaving}
          >
            <FloppyDisk size={14} weight="bold" />
            <span>{isSaving ? 'Saving...' : 'Save'}</span>
          </button>
        </div>
      </div>

      {/* ── Internal Category Carousel (Rendered when used standalone) ── */}
      {!hideInternalCategoryTabs ? (
        <>
          <div className="avatar-creator-groups-bar" role="tablist" aria-label="Avatar Customization Categories">
            <div className="avatar-creator-groups-scroll">
              {AVATAR_GROUPS.map((group) => {
                const isActive = activeMainGroup === group.id;
                const IconComp = group.icon;
                return (
                  <button
                    key={group.id}
                    type="button"
                    className={`avatar-group-capsule-btn ${isActive ? 'active' : ''}`}
                    onClick={() => handleMainGroupSwitch(group.id)}
                    role="tab"
                    aria-selected={isActive}
                  >
                    <div className="avatar-group-icon-wrap">
                      <IconComp size={16} weight={isActive ? 'fill' : 'regular'} />
                    </div>
                    <span className="avatar-group-label">{group.label}</span>
                    {isActive && (
                      <motion.span
                        layoutId="avatar-group-active-dot"
                        className="avatar-group-active-dot"
                        transition={{ type: 'spring', stiffness: 500, damping: 32 }}
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="avatar-suboptions-bar">
            <div className="avatar-suboptions-scroll">
              {currentGroupMeta.subOptions.map((sub) => {
                const isSubActive = activeSubOptionId === sub.id;
                return (
                  <button
                    key={sub.id}
                    type="button"
                    className={`avatar-suboption-pill ${isSubActive ? 'active' : ''}`}
                    onClick={() => handleSubOptionSwitch(sub)}
                  >
                    {sub.label}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      ) : (
        /* ── Sub-view Segmented Switcher when driven by Tray Level 2 Navigation ── */
        currentTabMeta.subViews.length > 1 && (
          <div className="avatar-subview-selector">
            <div className="subview-segmented-wrap">
              {currentTabMeta.subViews.map((sub) => {
                const isSubActive = activeSubView === sub;
                return (
                  <button
                    key={sub}
                    type="button"
                    className={`subview-segment-btn ${isSubActive ? 'active' : ''}`}
                    onClick={() => setActiveSubView(sub)}
                  >
                    {sub === 'presets' && 'Presets'}
                    {sub === 'sliders' && 'Fine Tuning'}
                    {sub === 'colors' && 'Color Swatches'}
                    {sub === 'styling' && (activeCategory === 'expressions' ? 'Emotes' : 'Styles')}
                  </button>
                );
              })}
            </div>
          </div>
        )
      )}

      {/* ── Main Category Body Scroll ── */}
      <div className="avatar-creator-body-scroll">
        <AnimatePresence mode="wait">
          <motion.div
            key={`${activeMainGroup}_${activeSubOptionId}_${activeCategory}_${activeSubView}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16 }}
            style={{ width: '100%' }}
          >
            {activeSubOptionId === 'photo_ref'
              ? renderPhotoRefView()
              : activeSubView === 'presets'
                ? renderPresets()
                : activeSubView === 'sliders'
                  ? renderSliders()
                  : activeSubView === 'colors'
                    ? renderColors()
                    : renderStyling()}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Confirmation Modal for Reset Entire Character ── */}
      {showResetModal && (
        <div className="modal-overlay" onClick={() => setShowResetModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Reset Entire Character?</h3>
            <p>
              This will restore all facial features, body proportions, hairstyles, and clothing
              back to the atelier factory baseline.
            </p>
            <div className="modal-dialog-actions">
              <button
                type="button"
                className="modal-cancel-btn"
                onClick={() => setShowResetModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal-confirm-btn"
                onClick={() => {
                  engine.resetEntireCharacter();
                  setShowResetModal(false);
                  toast.success('Character reset to defaults');
                }}
              >
                Confirm Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

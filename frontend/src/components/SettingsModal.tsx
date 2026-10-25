import React, { useState, useEffect } from 'react';
import { 
  X, 
  User, 
  Palette, 
  CloudSun, 
  Shirt, 
  RotateCcw, 
  ExternalLink, 
  Sliders, 
  Check, 
  Bot,
  Sparkles
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { UserProfile } from '../types/fashion';
import { fashionApi } from '../services/fashionApi';
import './SettingsModal.css';

export type PoseType = 'standing' | 'crossed_arms' | 'hands_pockets';
export type SceneType = 'studio' | 'sky_clouds' | 'sunset' | 'night';

export interface AvatarLook {
  topId: string;
  bottomId: string;
  shoesId: string;
  outerwearId?: string;
  sunglasses: boolean;
  pose: PoseType;
  scene: SceneType;
  hairStyle: string;
  hairColor: string;
  skinTone: string;
}

interface SettingsModalProps {
  isOpen?: boolean;
  onClose: () => void;
  profile?: UserProfile | null;
  userProfile?: UserProfile | null;
  onProfileUpdate?: (profile: UserProfile) => void;
  currentLook?: AvatarLook;
  onLookChange?: (look: AvatarLook) => void;
  currentParams?: any;
  onApplyCharacterPreset?: (params: any) => void;
}

type SettingsTab = 'profile' | 'color_season' | 'wardrobe' | 'environment' | 'ai_stylist';

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  profile,
  userProfile,
  onProfileUpdate,
  currentLook,
  onLookChange,
  currentParams,
  onApplyCharacterPreset
}) => {
  const effectiveProfile = profile || userProfile;
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [saving, setSaving] = useState(false);

  // Character Model State (Girl vs Boy)
  const [characterGender, setCharacterGender] = useState<'boy' | 'girl'>(() => {
    if (currentParams?.gender !== undefined) {
      return currentParams.gender < 0.5 ? 'girl' : 'boy';
    }
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('yorvyn_avatar_character');
      if (saved === 'girl' || saved === 'female') return 'girl';
    }
    return 'boy';
  });
  const [selectedGirlHair, setSelectedGirlHair] = useState('ponytail01');
  const [selectedGirlOutfit, setSelectedGirlOutfit] = useState('female_casualsuit01');

  // Form states
  const [name, setName] = useState(effectiveProfile?.name || 'Alex Hunter');
  const [bodyShape, setBodyShape] = useState(effectiveProfile?.body_shape || 'trapezoid');
  const [colorSeason, setColorSeason] = useState(effectiveProfile?.color_season || 'deep_autumn');
  const [skinTone, setSkinTone] = useState(currentLook?.skinTone || '#ffffff');
  const [hairColor, setHairColor] = useState(currentLook?.hairColor || '#1e293b');
  const [temperature, setTemperature] = useState(24);
  const [weatherCondition, setWeatherCondition] = useState('sunny');
  const [stylistVibe, setStylistVibe] = useState('modern_minimalist');
  const [analytics, setAnalytics] = useState<{ total_items?: number; completion_score?: number } | null>(null);

  useEffect(() => {
    if (isOpen) {
      fashionApi.getAnalytics()
        .then((res: any) => setAnalytics(res))
        .catch(() => setAnalytics({ total_items: 8, completion_score: 92 }));
    }
  }, [isOpen]);

  const handleQuickSwitch = (type: 'girl' | 'boy') => {
    setCharacterGender(type);
    const isGirl = type === 'girl';
    const charParams = isGirl ? {
      gender: 0.0,
      age: 0.42,
      muscle: 0.40,
      weight: 0.38,
      height: 0.54,
      proportions: 0.85,
      breastSize: 0.55,
      breastFirmness: 0.60,
      skin: 'young_caucasian_female',
      skinTint: skinTone,
      hair: selectedGirlHair,
      hairColor,
      facialHair: 'none',
      outfit: selectedGirlOutfit,
      shoes: 'shoes03',
      eyebrows: 'eyebrow010',
      eyelashes: 'eyelashes02',
      eyes: 'green'
    } : {
      gender: 1.0,
      age: 0.45,
      muscle: 0.65,
      weight: 0.45,
      height: 0.65,
      proportions: 0.85,
      breastSize: 0.0,
      breastFirmness: 0.0,
      skin: 'young_caucasian_male',
      skinTint: skinTone,
      hair: 'short01',
      hairColor,
      facialHair: 'stubble',
      outfit: 'male_casualsuit01',
      shoes: 'shoes01',
      eyebrows: 'eyebrow001',
      eyelashes: 'eyelashes01',
      eyes: 'brownlight'
    };

    if (typeof window !== 'undefined') {
      localStorage.setItem('yorvyn_avatar_character', type);
      localStorage.setItem('yorvyn_avatar_params', JSON.stringify(charParams));
      window.dispatchEvent(new CustomEvent('yorvyn:change_avatar_character', { 
        detail: { character: type, params: charParams } 
      }));
    }

    if (onApplyCharacterPreset) {
      onApplyCharacterPreset(charParams);
    }

    fashionApi.saveAvatarConfig(charParams).catch(() => {});
    toast.success(`Switched to 3D ${isGirl ? 'Girl Character (Elena)' : 'Boy Character (Alex)'}!`, { 
      icon: isGirl ? '👧' : '👦',
      duration: 2500
    });
  };

  const updateGirlSpecifics = (hair: string, outfit: string) => {
    setSelectedGirlHair(hair);
    setSelectedGirlOutfit(outfit);
    if (characterGender === 'girl') {
      const charParams = {
        gender: 0.0,
        age: 0.42,
        muscle: 0.40,
        weight: 0.38,
        height: 0.54,
        proportions: 0.85,
        breastSize: 0.55,
        breastFirmness: 0.60,
        skin: 'young_caucasian_female',
        skinTint: skinTone,
        hair,
        hairColor,
        facialHair: 'none',
        outfit,
        shoes: 'shoes03',
        eyebrows: 'eyebrow010',
        eyelashes: 'eyelashes02',
        eyes: 'green'
      };
      if (typeof window !== 'undefined') {
        localStorage.setItem('yorvyn_avatar_params', JSON.stringify(charParams));
        window.dispatchEvent(new CustomEvent('yorvyn:change_avatar_character', { 
          detail: { character: 'girl', params: charParams } 
        }));
      }
      if (onApplyCharacterPreset) {
        onApplyCharacterPreset(charParams);
      }
      fashionApi.saveAvatarConfig(charParams).catch(() => {});
    }
  };

  if (!isOpen) return null;

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const isGirl = characterGender === 'girl';
      const charParams = isGirl ? {
        gender: 0.0,
        age: 0.42,
        muscle: 0.40,
        weight: 0.38,
        height: 0.54,
        proportions: 0.85,
        breastSize: 0.55,
        breastFirmness: 0.60,
        skin: 'young_caucasian_female',
        skinTint: skinTone,
        hair: selectedGirlHair,
        hairColor,
        facialHair: 'none',
        outfit: selectedGirlOutfit,
        shoes: 'shoes03',
        eyebrows: 'eyebrow010',
        eyelashes: 'eyelashes02',
        eyes: 'green'
      } : {
        gender: 1.0,
        age: 0.45,
        muscle: 0.65,
        weight: 0.45,
        height: 0.65,
        proportions: 0.85,
        breastSize: 0.0,
        breastFirmness: 0.0,
        skin: 'young_caucasian_male',
        skinTint: skinTone,
        hair: 'short01',
        hairColor,
        facialHair: 'stubble',
        outfit: 'male_casualsuit01',
        shoes: 'shoes01',
        eyebrows: 'eyebrow001',
        eyelashes: 'eyelashes01',
        eyes: 'brownlight'
      };

      if (typeof window !== 'undefined') {
        localStorage.setItem('yorvyn_avatar_character', characterGender);
        localStorage.setItem('yorvyn_avatar_params', JSON.stringify(charParams));
        window.dispatchEvent(new CustomEvent('yorvyn:change_avatar_character', { 
          detail: { character: characterGender, params: charParams } 
        }));
      }

      if (onApplyCharacterPreset) {
        onApplyCharacterPreset(charParams);
      }

      fashionApi.saveAvatarConfig(charParams).catch(() => {});

      const updated = await fashionApi.updateProfile({
        name,
        body_shape: bodyShape as any,
        color_season: colorSeason as any,
      });
      if (onProfileUpdate) onProfileUpdate(updated);
      if (onLookChange && currentLook) {
        onLookChange({
          ...currentLook,
          skinTone,
          hairColor
        });
      }
      toast.success(`${isGirl ? 'Girl' : 'Boy'} character settings saved!`);
      onClose();
    } catch (err) {
      toast.success('Character settings applied locally');
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleResetToScreenshotDefault = () => {
    if (onLookChange) {
      onLookChange({
        topId: 'sig-polo',
        bottomId: 'sig-jeans',
        shoesId: 'sig-sneakers',
        outerwearId: undefined,
        sunglasses: true,
        pose: 'standing',
        scene: 'studio',
        hairStyle: 'textured_fringe',
        hairColor: '#1e1b18',
        skinTone: '#fcd34d'
      });
      toast.success('Reset to signature look from screenshot');
    }
  };

  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <div className="settings-modal-window" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="settings-modal-header">
          <div className="settings-header-title">
            <Sliders size={20} className="settings-icon-badge" />
            <div>
              <h2>Yorvyn Studio Settings</h2>
              <p>Configure personal geometry, color palette, wardrobe intelligence & stylist</p>
            </div>
          </div>
          <button className="settings-close-btn" onClick={onClose} aria-label="Close settings">
            <X size={20} />
          </button>
        </div>

        {/* Navigation Sidebar & Content Layout */}
        <div className="settings-modal-body">
          <div className="settings-nav-sidebar">
            <button 
              className={`settings-nav-item ${activeTab === 'profile' ? 'active' : ''}`}
              onClick={() => setActiveTab('profile')}
            >
              <User size={18} />
              <span>Identity & Body</span>
            </button>

            <button 
              className={`settings-nav-item ${activeTab === 'color_season' ? 'active' : ''}`}
              onClick={() => setActiveTab('color_season')}
            >
              <Palette size={18} />
              <span>Color Season</span>
            </button>

            <button 
              className={`settings-nav-item ${activeTab === 'wardrobe' ? 'active' : ''}`}
              onClick={() => setActiveTab('wardrobe')}
            >
              <Shirt size={18} />
              <span>Wardrobe Hub</span>
            </button>

            <button 
              className={`settings-nav-item ${activeTab === 'environment' ? 'active' : ''}`}
              onClick={() => setActiveTab('environment')}
            >
              <CloudSun size={18} />
              <span>Weather & Context</span>
            </button>

            <button 
              className={`settings-nav-item ${activeTab === 'ai_stylist' ? 'active' : ''}`}
              onClick={() => setActiveTab('ai_stylist')}
            >
              <Bot size={18} />
              <span>AI Stylist</span>
            </button>
          </div>

          <div className="settings-content-pane">
            {/* ── TAB 1: Profile & Body Geometry ── */}
            {activeTab === 'profile' && (
              <div className="settings-section">
                <h3>Personal Identity & Avatar Fit</h3>
                <p className="section-desc">Select your 3D model baseline and fine-tune physical proportions for tailor-accurate clothing drape.</p>

                {/* 3D Character Model Selection (Girl vs Boy) */}
                <div className="setting-field-group">
                  <div className="section-subtitle-row">
                    <label>3D Character Avatar Model</label>
                    <span className="helper-tag">Live 3D Switch</span>
                  </div>

                  <div className="character-model-selector-grid">
                    {/* GIRL CHARACTER CARD */}
                    <div 
                      className={`char-model-card ${characterGender === 'girl' ? 'active' : ''}`}
                      onClick={() => handleQuickSwitch('girl')}
                    >
                      <div className="char-model-card-top">
                        <div className="char-model-icon-circle girl">
                          <Sparkles size={18} />
                        </div>
                        <div className="char-badge-pill girl">Girl Character</div>
                        {characterGender === 'girl' && (
                          <div className="char-active-indicator">
                            <Check size={14} />
                            <span>Active</span>
                          </div>
                        )}
                      </div>

                      <div className="char-model-body">
                        <h4>Elena — Girl Avatar</h4>
                        <p>Curated feminine silhouette, high ponytail, contoured waist, and chic tailored fit.</p>
                      </div>

                      {characterGender === 'girl' && (
                        <div className="char-model-suboptions">
                          <div className="suboption-label">Hairstyle</div>
                          <div className="suboption-chips">
                            {[
                              { id: 'ponytail01', name: 'High Ponytail' },
                              { id: 'long01', name: 'Long Flowing' },
                              { id: 'bob02', name: 'Parisian Bob' },
                              { id: 'braid01', name: 'Braided' },
                            ].map(h => (
                              <button
                                key={h.id}
                                type="button"
                                className={`suboption-chip ${selectedGirlHair === h.id ? 'active' : ''}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  updateGirlSpecifics(h.id, selectedGirlOutfit);
                                }}
                              >
                                {h.name}
                              </button>
                            ))}
                          </div>

                          <div className="suboption-label" style={{ marginTop: '0.5rem' }}>Default Outfit</div>
                          <div className="suboption-chips">
                            {[
                              { id: 'female_casualsuit01', name: 'Casual Chic' },
                              { id: 'female_elegantsuit01', name: 'Tailored Blazer' },
                              { id: 'female_sportsuit01', name: 'Sport Fit' },
                              { id: 'female_casualsuit02', name: 'Weekend Denim' },
                            ].map(o => (
                              <button
                                key={o.id}
                                type="button"
                                className={`suboption-chip ${selectedGirlOutfit === o.id ? 'active' : ''}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  updateGirlSpecifics(selectedGirlHair, o.id);
                                }}
                              >
                                {o.name}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      <button 
                        type="button" 
                        className={`char-select-btn ${characterGender === 'girl' ? 'current' : ''}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleQuickSwitch('girl');
                        }}
                      >
                        {characterGender === 'girl' ? '✓ Selected as 3D Model' : 'Switch to Girl Character'}
                      </button>
                    </div>

                    {/* BOY CHARACTER CARD */}
                    <div 
                      className={`char-model-card ${characterGender === 'boy' ? 'active' : ''}`}
                      onClick={() => handleQuickSwitch('boy')}
                    >
                      <div className="char-model-card-top">
                        <div className="char-model-icon-circle boy">
                          <User size={18} />
                        </div>
                        <div className="char-badge-pill boy">Boy Character</div>
                        {characterGender === 'boy' && (
                          <div className="char-active-indicator">
                            <Check size={14} />
                            <span>Active</span>
                          </div>
                        )}
                      </div>

                      <div className="char-model-body">
                        <h4>Alex — Boy Avatar</h4>
                        <p>Athletic masculine baseline with textured short crop, polo streetwear, and signature sneakers.</p>
                      </div>

                      <button 
                        type="button" 
                        className={`char-select-btn ${characterGender === 'boy' ? 'current' : ''}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleQuickSwitch('boy');
                        }}
                      >
                        {characterGender === 'boy' ? '✓ Selected as 3D Model' : 'Switch to Boy Character'}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="setting-field-group">
                  <label>Full Name or Moniker</label>
                  <input 
                    type="text" 
                    value={name} 
                    onChange={e => setName(e.target.value)} 
                    className="settings-input" 
                  />
                </div>

                <div className="setting-field-group">
                  <label>Body Proportions & Silhouette</label>
                  <div className="shape-chips-grid">
                    {[
                      { id: 'trapezoid', label: 'Trapezoid (Athletic Balanced)' },
                      { id: 'inverted_triangle', label: 'Inverted Triangle (Broad Shoulders)' },
                      { id: 'rectangle', label: 'Rectangle (Straight Linear)' },
                      { id: 'hourglass', label: 'Hourglass (Defined Waist)' },
                      { id: 'oval', label: 'Oval (Soft Center)' }
                    ].map(shape => (
                      <button
                        key={shape.id}
                        type="button"
                        className={`shape-chip-btn ${bodyShape === shape.id ? 'active' : ''}`}
                        onClick={() => setBodyShape(shape.id)}
                      >
                        {bodyShape === shape.id && <Check size={14} />}
                        <span>{shape.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="setting-field-group">
                  <label>Avatar Skin Tone Complexion</label>
                  <div className="color-swatch-row">
                    {[
                      { hex: '#fcd34d', name: 'Warm Golden' },
                      { hex: '#fed7aa', name: 'Fair Ivory' },
                      { hex: '#d97706', name: 'Caramel Bronze' },
                      { hex: '#b45309', name: 'Rich Chestnut' },
                      { hex: '#78350f', name: 'Deep Espresso' }
                    ].map(tone => (
                      <button
                        key={tone.hex}
                        type="button"
                        className={`swatch-circle-btn ${skinTone === tone.hex ? 'active' : ''}`}
                        style={{ backgroundColor: tone.hex }}
                        onClick={() => setSkinTone(tone.hex)}
                        title={tone.name}
                      >
                        {skinTone === tone.hex && <Check size={14} color="#000" />}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="setting-field-group">
                  <label>Hair Tone</label>
                  <div className="color-swatch-row">
                    {[
                      { hex: '#1e1b18', name: 'Jet Onyx' },
                      { hex: '#3d2b1f', name: 'Dark Chestnut' },
                      { hex: '#78350f', name: 'Warm Amber' },
                      { hex: '#94a3b8', name: 'Silver Slate' },
                      { hex: '#fbbf24', name: 'Bleached Blonde' }
                    ].map(color => (
                      <button
                        key={color.hex}
                        type="button"
                        className={`swatch-circle-btn ${hairColor === color.hex ? 'active' : ''}`}
                        style={{ backgroundColor: color.hex }}
                        onClick={() => setHairColor(color.hex)}
                        title={color.name}
                      >
                        {hairColor === color.hex && <Check size={14} color="#fff" />}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB 2: Color Season Analysis ── */}
            {activeTab === 'color_season' && (
              <div className="settings-section">
                <h3>Color Season & Chromatic Harmony</h3>
                <p className="section-desc">Algorithmically matches clothing hues against your skin, hair, and eye undertones.</p>

                <div className="season-cards-grid">
                  {[
                    { 
                      id: 'deep_autumn', 
                      title: 'Deep Autumn', 
                      palette: ['#78350f', '#064e3b', '#b91c1c', '#f59e0b'],
                      desc: 'Rich, warm, and grounded tones with high saturation.' 
                    },
                    { 
                      id: 'warm_spring', 
                      title: 'Warm Spring', 
                      palette: ['#f97316', '#10b981', '#38bdf8', '#fbbf24'],
                      desc: 'Clear, vibrant golden undertones that radiate energy.' 
                    },
                    { 
                      id: 'cool_summer', 
                      title: 'Cool Summer', 
                      palette: ['#3b82f6', '#ec4899', '#64748b', '#c084fc'],
                      desc: 'Soft, muted, and powdery pastels with blue undertones.' 
                    },
                    { 
                      id: 'deep_winter', 
                      title: 'Deep Winter', 
                      palette: ['#0f172a', '#dc2626', '#ffffff', '#4338ca'],
                      desc: 'High contrast, sharp jewel tones and crisp monochromes.' 
                    }
                  ].map(season => (
                    <div 
                      key={season.id}
                      className={`season-card ${colorSeason === season.id ? 'active' : ''}`}
                      onClick={() => setColorSeason(season.id)}
                    >
                      <div className="season-card-header">
                        <h4>{season.title}</h4>
                        {colorSeason === season.id && <Check size={16} className="season-check-icon" />}
                      </div>
                      <div className="season-swatches">
                        {season.palette.map((c, i) => (
                          <span key={i} className="season-swatch" style={{ backgroundColor: c }} />
                        ))}
                      </div>
                      <p>{season.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── TAB 3: Digital Wardrobe Hub ── */}
            {activeTab === 'wardrobe' && (
              <div className="settings-section">
                <h3>Digital Wardrobe Intelligence</h3>
                <p className="section-desc">Manage your digitized clothes, purchase history, and capsule utilization.</p>

                <div className="analytics-stat-row">
                  <div className="stat-card">
                    <span className="stat-num">{analytics?.total_items || 8}</span>
                    <span className="stat-label">Digitized Items</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-num">{analytics?.completion_score || 94}%</span>
                    <span className="stat-label">Capsule Completeness</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-num">32+</span>
                    <span className="stat-label">AI Outfits Generated</span>
                  </div>
                </div>

                <div className="quick-nav-actions">
                  <button 
                    className="quick-link-btn"
                    onClick={() => { onClose(); navigate('/wardrobe'); }}
                  >
                    <span>Open Full Digital Wardrobe</span>
                    <ExternalLink size={16} />
                  </button>

                  <button 
                    className="quick-link-btn"
                    onClick={() => { onClose(); navigate('/outfits'); }}
                  >
                    <span>Launch Outfit Studio (Capsule Generator)</span>
                    <ExternalLink size={16} />
                  </button>

                  <button 
                    className="quick-link-btn"
                    onClick={() => { onClose(); navigate('/avatar'); }}
                  >
                    <span>Full Avatar 3D Customizer</span>
                    <ExternalLink size={16} />
                  </button>
                </div>
              </div>
            )}

            {/* ── TAB 4: Environment & Weather ── */}
            {activeTab === 'environment' && (
              <div className="settings-section">
                <h3>Weather Simulation & Environment</h3>
                <p className="section-desc">Simulate ambient temperature to dynamically adapt outerwear and fabric recommendations.</p>

                <div className="setting-field-group">
                  <div className="slider-label-row">
                    <label>Simulated Ambient Temperature</label>
                    <span className="slider-value-pill">{temperature}°C</span>
                  </div>
                  <input 
                    type="range" 
                    min="5" 
                    max="40" 
                    value={temperature}
                    onChange={e => setTemperature(parseInt(e.target.value))}
                    className="settings-range-slider"
                  />
                  <div className="slider-ticks">
                    <span>5°C (Winter Coat)</span>
                    <span>22°C (Polo & Jeans)</span>
                    <span>38°C (Linen / Summer)</span>
                  </div>
                </div>

                <div className="setting-field-group">
                  <label>Weather Condition</label>
                  <div className="weather-chip-row">
                    {[
                      { id: 'sunny', label: '☀️ Clear & Sunny' },
                      { id: 'cloudy', label: '⛅ Overcast / Clouds' },
                      { id: 'rain', label: '🌧️ Rain / Drizzle' },
                      { id: 'breeze', label: '💨 Crisp Wind' }
                    ].map(w => (
                      <button
                        key={w.id}
                        type="button"
                        className={`weather-chip ${weatherCondition === w.id ? 'active' : ''}`}
                        onClick={() => setWeatherCondition(w.id)}
                      >
                        {w.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB 5: AI Stylist & Quick Actions ── */}
            {activeTab === 'ai_stylist' && (
              <div className="settings-section">
                <h3>Yorvyn AI Stylist Configuration</h3>
                <p className="section-desc">Personalize conversational tone, aesthetic preference, and aesthetic rules.</p>

                <div className="setting-field-group">
                  <label>Stylist Aesthetic Vibe</label>
                  <div className="vibe-selection-grid">
                    {[
                      { id: 'modern_minimalist', label: 'Modern Minimalist', desc: 'Monochromatic, clean lines, quiet luxury (like the Polo & Baggy Jeans look).' },
                      { id: 'old_money', label: 'Old Money Preppy', desc: 'Structured tailoring, Ralph Lauren knitwear, loafers, and neutral tones.' },
                      { id: 'streetwear', label: 'Streetwear & Denim', desc: 'Diesel oversized silhouettes, graphic elements, relaxed denim, and chunky kicks.' }
                    ].map(vibe => (
                      <div 
                        key={vibe.id} 
                        className={`vibe-card ${stylistVibe === vibe.id ? 'active' : ''}`}
                        onClick={() => setStylistVibe(vibe.id)}
                      >
                        <div className="vibe-card-title">
                          <strong>{vibe.label}</strong>
                          {stylistVibe === vibe.id && <Check size={16} />}
                        </div>
                        <p>{vibe.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="stylist-direct-chat-banner">
                  <div>
                    <h4>Ask Yorvyn AI Stylist Live</h4>
                    <p>Get instant outfit recommendations tailored to today's schedule and look.</p>
                  </div>
                  <button 
                    className="pill-action-btn primary"
                    onClick={() => { onClose(); navigate('/stylist'); }}
                  >
                    Open Stylist Chat
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="settings-modal-footer">
          <button 
            type="button" 
            className="settings-reset-link"
            onClick={handleResetToScreenshotDefault}
          >
            <RotateCcw size={15} />
            <span>Reset Look to Screenshot</span>
          </button>

          <div className="footer-actions-right">
            <button type="button" className="settings-cancel-btn" onClick={onClose}>
              Cancel
            </button>
            <button 
              type="button" 
              className="settings-save-btn" 
              onClick={handleSaveProfile}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

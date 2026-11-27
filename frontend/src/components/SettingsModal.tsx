import React, { useState, useEffect } from 'react';
import { 
  X, 
  User, 
  Palette, 
  SunHorizon, 
  TShirt, 
  ArrowCounterClockwise, 
  SlidersHorizontal, 
  Check, 
  Robot,
  Sparkle,
  SignOut,
  Trash,
  WarningCircle,
  ShieldCheck,
  EnvelopeSimple,
  Minus,
  Plus
} from './icons';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { UserProfile } from '../types/fashion';
import { fashionApi } from '../services/fashionApi';
import { useAuth } from '../context/AuthContext';
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
  onClose?: () => void;
  embedded?: boolean;
  profile?: UserProfile | null;
  userProfile?: UserProfile | null;
  initialProfile?: UserProfile | null;
  onProfileUpdate?: (profile: UserProfile) => void;
  onSaveProfile?: (profile: UserProfile) => void;
  currentLook?: AvatarLook;
  onLookChange?: (look: AvatarLook) => void;
  currentParams?: any;
  onApplyCharacterPreset?: (params: any) => void;
}

type SettingsTab = 'profile' | 'color_season' | 'wardrobe' | 'environment' | 'ai_stylist';

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen = true,
  onClose,
  embedded = false,
  profile,
  userProfile,
  initialProfile,
  onProfileUpdate,
  onSaveProfile,
  currentLook,
  onLookChange,
  currentParams,
  onApplyCharacterPreset
}) => {
  const effectiveProfile = profile || userProfile || initialProfile;
  const navigate = useNavigate();
  const { user, profile: authProfile, signOut, deleteAccount, saveProfile: saveAuthProfile } = useAuth();

  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [saving, setSaving] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');

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
  const [name, setName] = useState(effectiveProfile?.name || authProfile?.displayName || user?.displayName || 'Alex Hunter');
  const [gender, setGender] = useState<'female' | 'male' | 'non-binary'>(
    (authProfile?.gender as any) || 'female'
  );
  const [phoneNumber, setPhoneNumber] = useState<string>(authProfile?.phoneNumber || '');
  const [location, setLocation] = useState<string>(authProfile?.location || '');
  const [age, setAge] = useState<number>(authProfile?.age || 26);
  const [heightValue, setHeightValue] = useState<number>(effectiveProfile?.height_cm || authProfile?.heightValue || 175);
  const [heightUnit] = useState<'cm' | 'ft'>(authProfile?.heightUnit || 'cm');
  const [weightValue, setWeightValue] = useState<number>(authProfile?.weightValue || 65);
  const [weightUnit, setWeightUnit] = useState<'kg' | 'lbs'>(authProfile?.weightUnit || 'kg');
  const [bodyShape, setBodyShape] = useState(effectiveProfile?.body_shape || authProfile?.bodyType || 'athletic_tapered');
  const [colorSeason, setColorSeason] = useState(effectiveProfile?.color_season || 'autumn');
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
      outfit: 'male_casualsuit02',
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
        outfit: 'male_casualsuit02',
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

      // Save to Auth/Profile service
      if (saveAuthProfile) {
        saveAuthProfile({
          displayName: name,
          gender,
          phoneNumber,
          location,
          age,
          heightValue,
          heightUnit,
          weightValue,
          weightUnit,
          bodyType: bodyShape as any,
        }).catch(() => {});
      }

      const updated = await fashionApi.updateProfile({
        name,
        body_shape: bodyShape as any,
        color_season: colorSeason as any,
        height_cm: heightValue,
      });

      if (onProfileUpdate) onProfileUpdate(updated);
      if (onSaveProfile) onSaveProfile(updated);

      if (onLookChange && currentLook) {
        onLookChange({
          ...currentLook,
          skinTone,
          hairColor
        });
      }
      toast.success('Studio settings saved successfully!');
      if (onClose) onClose();
    } catch (err) {
      toast.success('Settings applied locally');
      if (onClose) onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleSignOut = async () => {
    try {
      setIsLoggingOut(true);
      await signOut();
      toast.success('Signed out of Yorvyn');
      if (onClose) onClose();
      navigate('/login');
    } catch (err: any) {
      toast.error(err.message || 'Error signing out');
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleDeleteAccount = async () => {
    try {
      setIsDeleting(true);
      const res = await deleteAccount();
      if (res?.error) {
        toast.error(res.error);
        setIsDeleting(false);
        return;
      }
      toast.success('Your account has been deleted.');
      if (onClose) onClose();
      navigate('/login');
    } catch (err: any) {
      toast.error('Failed to delete account');
      setIsDeleting(false);
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

  const cmToFtIn = (cm: number) => {
    const totalInches = cm / 2.54;
    const feet = Math.floor(totalInches / 12);
    const inches = Math.round(totalInches % 12);
    return `${feet}'${inches}"`;
  };

  const panelContent = (
    <aside 
      className={`settings-modal-window ${embedded ? 'embedded-settings-panel' : 'side-drawer'}`} 
      onClick={e => e.stopPropagation()} 
      aria-label="Studio Settings Panel"
    >
      {/* Header */}
      <div className="settings-modal-header">
        <div className="settings-header-title">
          <SlidersHorizontal size={20} className="settings-icon-badge" />
          <div>
            <h2>Settings & Profile</h2>
            <p>Profile identity, measurements, 3D avatar twin & studio settings</p>
          </div>
        </div>
        {onClose && (
          <button className="settings-close-btn" onClick={onClose} aria-label="Close settings">
            <X size={20} />
          </button>
        )}
      </div>

        {/* Horizontal Navigation Strip for Side Drawer */}
        <nav className="settings-nav-strip" aria-label="Settings Categories">
          <button 
            type="button"
            className={`settings-nav-tab-pill ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            <User size={15} />
            <span>Profile & Identity</span>
          </button>

          <button 
            type="button"
            className={`settings-nav-tab-pill ${activeTab === 'color_season' ? 'active' : ''}`}
            onClick={() => setActiveTab('color_season')}
          >
            <Palette size={15} />
            <span>Color Season</span>
          </button>

          <button 
            type="button"
            className={`settings-nav-tab-pill ${activeTab === 'wardrobe' ? 'active' : ''}`}
            onClick={() => setActiveTab('wardrobe')}
          >
            <TShirt size={15} />
            <span>Wardrobe</span>
          </button>

          <button 
            type="button"
            className={`settings-nav-tab-pill ${activeTab === 'environment' ? 'active' : ''}`}
            onClick={() => setActiveTab('environment')}
          >
            <SunHorizon size={15} />
            <span>Atmosphere</span>
          </button>

          <button 
            type="button"
            className={`settings-nav-tab-pill ${activeTab === 'ai_stylist' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai_stylist')}
          >
            <Robot size={15} />
            <span>AI Stylist</span>
          </button>
        </nav>

        {/* Main Content Pane */}
        <div className="settings-content-pane">
          {/* ── TAB 1: Profile, Identity, Measurements & Account ── */}
          {activeTab === 'profile' && (
            <div className="settings-section">
              {/* Account Identity Card */}
              <div className="settings-account-card">
                <div className="sac-avatar-badge">
                  {user?.photoURL ? (
                    <img src={user.photoURL} alt={name} className="sac-avatar-img" />
                  ) : (
                    <div className="sac-avatar-initials">
                      {name?.[0]?.toUpperCase() || 'Y'}
                    </div>
                  )}
                </div>
                <div className="sac-info">
                  <div className="sac-name-row">
                    <span className="sac-name">{name}</span>
                    <span className="sac-badge">
                      <ShieldCheck size={12} /> Verified
                    </span>
                  </div>
                  <span className="sac-email">
                    <EnvelopeSimple size={12} /> {user?.email || 'Authenticated Member'}
                  </span>
                </div>
              </div>

              <h3>Personal Identity & Avatar Fit</h3>
              <p className="section-desc">Fine-tune physical proportions, 3D character silhouette, and manage your account.</p>

              {/* Full Name / Moniker */}
              <div className="setting-field-group">
                <label>Display Name or Moniker</label>
                <input 
                  type="text" 
                  value={name} 
                  onChange={e => setName(e.target.value)} 
                  className="settings-input" 
                  placeholder="e.g. Aarav Sharma, Priya Patel"
                />
              </div>

              {/* Gender Preference */}
              <div className="setting-field-group">
                <label>Gender Preference</label>
                <div className="gender-segmented-track" style={{ display: 'flex', gap: '6px', background: '#f1f5f9', padding: '4px', borderRadius: '12px', marginTop: '4px' }}>
                  {[
                    { id: 'female', label: 'Female' },
                    { id: 'male', label: 'Male' },
                    { id: 'non-binary', label: 'Non-binary' },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      style={{
                        flex: 1,
                        padding: '8px 12px',
                        borderRadius: '9px',
                        border: 'none',
                        background: gender === opt.id ? '#0f172a' : 'transparent',
                        color: gender === opt.id ? '#ffffff' : '#64748b',
                        fontWeight: 600,
                        fontSize: '13px',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                      onClick={() => setGender(opt.id as any)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Phone & Age */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <div className="setting-field-group" style={{ flex: 1 }}>
                  <label>Phone Number</label>
                  <input
                    type="tel"
                    className="settings-input"
                    placeholder="+91 98765 43210"
                    value={phoneNumber}
                    onChange={e => setPhoneNumber(e.target.value)}
                  />
                </div>
                <div className="setting-field-group" style={{ width: '90px' }}>
                  <label>Age</label>
                  <input
                    type="number"
                    className="settings-input"
                    min={13}
                    max={110}
                    value={age}
                    onChange={e => setAge(parseInt(e.target.value) || 20)}
                  />
                </div>
              </div>

              {/* Location */}
              <div className="setting-field-group">
                <label>Location / City</label>
                <input
                  type="text"
                  className="settings-input"
                  placeholder="e.g. Mumbai, Delhi, Bengaluru, Jaipur"
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  maxLength={60}
                />
              </div>

              {/* Weight */}
              <div className="setting-field-group">
                <div className="section-subtitle-row">
                  <label>Weight</label>
                  <span className="helper-badge">{weightValue} {weightUnit}</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input
                    type="number"
                    className="settings-input"
                    value={weightValue}
                    onChange={e => setWeightValue(Number(e.target.value))}
                    min={30}
                    max={300}
                    style={{ flex: 1 }}
                  />
                  <div style={{ display: 'flex', background: '#f1f5f9', borderRadius: '10px', padding: '3px' }}>
                    <button
                      type="button"
                      style={{
                        border: 'none',
                        background: weightUnit === 'kg' ? '#0f172a' : 'transparent',
                        color: weightUnit === 'kg' ? '#fff' : '#64748b',
                        borderRadius: '8px',
                        padding: '6px 12px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                      onClick={() => setWeightUnit('kg')}
                    >
                      kg
                    </button>
                    <button
                      type="button"
                      style={{
                        border: 'none',
                        background: weightUnit === 'lbs' ? '#0f172a' : 'transparent',
                        color: weightUnit === 'lbs' ? '#fff' : '#64748b',
                        borderRadius: '8px',
                        padding: '6px 12px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                      onClick={() => setWeightUnit('lbs')}
                    >
                      lbs
                    </button>
                  </div>
                </div>
              </div>

              {/* Stature & Height Calibration */}
              <div className="setting-field-group">
                <div className="section-subtitle-row">
                  <label>Stature Calibration</label>
                  <span className="helper-badge">{heightValue} cm • {cmToFtIn(heightValue)}</span>
                </div>

                <div className="settings-height-slider-wrap">
                  <div className="shs-stepper-row">
                    <button
                      type="button"
                      className="shs-btn"
                      onClick={() => setHeightValue(v => Math.max(145, v - 1))}
                    >
                      <Minus size={13} />
                    </button>
                    <input
                      type="range"
                      min={145}
                      max={210}
                      step={1}
                      value={heightValue}
                      onChange={e => setHeightValue(Number(e.target.value))}
                      className="drawer-range-slider"
                    />
                    <button
                      type="button"
                      className="shs-btn"
                      onClick={() => setHeightValue(v => Math.min(210, v + 1))}
                    >
                      <Plus size={13} />
                    </button>
                  </div>

                  <div className="settings-stature-chips">
                    {[
                      { label: 'Petite', cm: 160, ft: '5\'3"' },
                      { label: 'Classic', cm: 170, ft: '5\'7"' },
                      { label: 'Studio', cm: 178, ft: '5\'10"' },
                      { label: 'Statuesque', cm: 188, ft: '6\'2"' },
                    ].map(st => (
                      <button
                        key={st.cm}
                        type="button"
                        className={`settings-mini-chip ${Math.abs(heightValue - st.cm) <= 2 ? 'active' : ''}`}
                        onClick={() => setHeightValue(st.cm)}
                      >
                        <strong>{st.label}</strong>
                        <span>{st.ft}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* 3D Character Model Selection (Girl vs Boy) */}
              <div className="setting-field-group">
                <div className="section-subtitle-row">
                  <label>3D Character Avatar Baseline</label>
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
                        <Sparkle size={16} />
                      </div>
                      <div className="char-badge-pill girl">Girl Character</div>
                      {characterGender === 'girl' && (
                        <div className="char-active-indicator">
                          <Check size={13} />
                          <span>Active</span>
                        </div>
                      )}
                    </div>

                    <div className="char-model-body">
                      <h4>Elena — Girl Avatar</h4>
                      <p>Feminine silhouette, high ponytail, contoured waist, and chic tailored fit.</p>
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
                        <User size={16} />
                      </div>
                      <div className="char-badge-pill boy">Boy Character</div>
                      {characterGender === 'boy' && (
                        <div className="char-active-indicator">
                          <Check size={13} />
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

              {/* Body Proportions & Silhouette */}
              <div className="setting-field-group">
                <label>Body Proportions & Silhouette</label>
                <div className="shape-chips-grid">
                  {[
                    { id: 'athletic_tapered', label: 'V-Taper (Athletic Sculpted)' },
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
                      onClick={() => setBodyShape(shape.id as any)}
                    >
                      {bodyShape === shape.id && <Check size={13} />}
                      <span>{shape.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Avatar Skin Tone Complexion */}
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

              {/* Hair Color */}
              <div className="setting-field-group">
                <label>Hair Color</label>
                <div className="color-swatch-row">
                  {[
                    { hex: '#111111', name: 'Jet Black' },
                    { hex: '#3a2312', name: 'Dark Espresso' },
                    { hex: '#6a3b1a', name: 'Warm Chestnut' },
                    { hex: '#d4a359', name: 'Honey Blonde' },
                    { hex: '#8c2d19', name: 'Auburn Copper' },
                    { hex: '#a0a0a0', name: 'Silver Ash' },
                  ].map(hair => (
                    <button
                      key={hair.hex}
                      type="button"
                      className={`swatch-circle-btn ${hairColor === hair.hex ? 'active' : ''}`}
                      style={{ backgroundColor: hair.hex }}
                      onClick={() => setHairColor(hair.hex)}
                      title={hair.name}
                    >
                      {hairColor === hair.hex && <Check size={14} color="#fff" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Account Management & Security Section */}
              <div className="settings-account-security-section">
                <h4 className="sec-heading">Account Session & Security</h4>

                {/* Log Out Action */}
                <div className="security-action-row">
                  <div className="sar-info">
                    <strong>Log Out of Yorvyn</strong>
                    <p>Safely ends your current authentication session on this device.</p>
                  </div>
                  <button
                    type="button"
                    className="settings-logout-btn"
                    onClick={handleSignOut}
                    disabled={isLoggingOut}
                  >
                    <SignOut size={15} />
                    <span>{isLoggingOut ? 'Signing out...' : 'Log Out'}</span>
                  </button>
                </div>

                {/* Danger Zone: Delete Account */}
                <div className="danger-zone-box">
                  <div className="dz-header">
                    <WarningCircle size={17} className="dz-alert-icon" />
                    <div>
                      <strong>Danger Zone — Delete Account</strong>
                      <p>Permanently deletes your account, personal measurements, wardrobe catalog, and saved avatar configurations. This action cannot be reversed.</p>
                    </div>
                  </div>

                  {!showDeleteConfirm ? (
                    <button
                      type="button"
                      className="settings-delete-account-btn"
                      onClick={() => setShowDeleteConfirm(true)}
                    >
                      <Trash size={15} />
                      <span>Delete My Account</span>
                    </button>
                  ) : (
                    <div className="dz-confirm-pane">
                      <p className="dz-confirm-warning">
                        Please confirm: Type <strong>DELETE</strong> below to permanently delete your account and all data.
                      </p>
                      <input
                        type="text"
                        className="settings-input dz-input"
                        placeholder="Type DELETE to confirm"
                        value={deleteConfirmText}
                        onChange={e => setDeleteConfirmText(e.target.value)}
                      />
                      <div className="dz-actions-row">
                        <button
                          type="button"
                          className="dz-cancel-btn"
                          onClick={() => {
                            setShowDeleteConfirm(false);
                            setDeleteConfirmText('');
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="dz-confirm-btn"
                          disabled={deleteConfirmText !== 'DELETE' || isDeleting}
                          onClick={handleDeleteAccount}
                        >
                          <Trash size={14} />
                          <span>{isDeleting ? 'Deleting...' : 'Permanently Delete'}</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 2: Color Season ── */}
          {activeTab === 'color_season' && (
            <div className="settings-section">
              <h3>Color Season & Palette Harmony</h3>
              <p className="section-desc">Colorimetry parameters drive our AI garment recommendations to complement your natural complexion undertones.</p>

              <div className="season-cards-grid">
                {[
                  { id: 'deep_autumn', label: 'Deep Autumn', desc: 'Warm, rich, earthy palette (Rust, Terracotta, Olive, Caramel)', colors: ['#9a3412', '#78350f', '#3f6212', '#c2410c'] },
                  { id: 'soft_summer', label: 'Soft Summer', desc: 'Cool, muted, powdery hues (Slate Blue, Lavender, Rose Taupe, Sage)', colors: ['#475569', '#64748b', '#94a3b8', '#a855f7'] },
                  { id: 'warm_spring', label: 'Warm Spring', desc: 'Bright, radiant, clear warm tones (Coral, Marigold, Peach, Mint)', colors: ['#f97316', '#eab308', '#ec4899', '#10b981'] },
                  { id: 'true_winter', label: 'True Winter', desc: 'High contrast, jewel tones (Midnight Navy, Emerald, Crimson, Pure Black)', colors: ['#0f172a', '#065f46', '#991b1b', '#1e1b4b'] },
                ].map(season => (
                  <div 
                    key={season.id} 
                    className={`season-card ${colorSeason === season.id ? 'active' : ''}`}
                    onClick={() => setColorSeason(season.id as any)}
                  >
                    <div className="season-card-header">
                      <strong>{season.label}</strong>
                      {colorSeason === season.id && <Check size={16} />}
                    </div>
                    <p>{season.desc}</p>
                    <div className="season-swatches-strip">
                      {season.colors.map(c => (
                        <span key={c} className="swatch-strip-pill" style={{ backgroundColor: c }} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── TAB 3: Wardrobe Hub ── */}
          {activeTab === 'wardrobe' && (
            <div className="settings-section">
              <h3>Wardrobe Analytics & Sync</h3>
              <p className="section-desc">Review connected catalog status, digitization depth, and cloud asset cache.</p>

              <div className="wardrobe-stats-grid">
                <div className="stat-card">
                  <span className="stat-label">Digitized Garments</span>
                  <strong className="stat-val">{analytics?.total_items || 8} Items</strong>
                  <span className="stat-sub">Across 5 Style Layers</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Color Match Score</span>
                  <strong className="stat-val">{analytics?.completion_score || 94}%</strong>
                  <span className="stat-sub">Calibrated to Season</span>
                </div>
              </div>

              <div className="wardrobe-hub-actions">
                <button 
                  className="pill-action-btn dark-pill full-width"
                  onClick={() => { if (onClose) onClose(); navigate('/wardrobe'); }}
                >
                  <TShirt size={16} />
                  <span>Open Full Wardrobe Atelier</span>
                </button>
              </div>
            </div>
          )}

          {/* ── TAB 4: Environment & Atmosphere ── */}
          {activeTab === 'environment' && (
            <div className="settings-section">
              <h3>Weather & Context Simulation</h3>
              <p className="section-desc">Test your outfit against real-time ambient conditions, light warmth, and climate.</p>

              <div className="setting-field-group">
                <label>Simulated Ambient Temperature (°C)</label>
                <div className="temp-slider-wrap">
                  <input 
                    type="range" min="0" max="40" step="1" 
                    value={temperature} 
                    onChange={e => setTemperature(Number(e.target.value))} 
                    className="drawer-range-slider"
                  />
                  <span className="temp-badge">{temperature}°C ({Math.round(temperature * 1.8 + 32)}°F)</span>
                </div>
              </div>

              <div className="setting-field-group">
                <label>Weather Condition</label>
                <div className="shape-chips-grid">
                  {[
                    { id: 'sunny', label: 'Clear Skies & Sunny' },
                    { id: 'cloudy', label: 'Overcast & Cool' },
                    { id: 'rainy', label: 'Drizzle & Rain' },
                    { id: 'breezy', label: 'Breezy & Chilly' }
                  ].map(w => (
                    <button
                      key={w.id}
                      type="button"
                      className={`shape-chip-btn ${weatherCondition === w.id ? 'active' : ''}`}
                      onClick={() => setWeatherCondition(w.id)}
                    >
                      {weatherCondition === w.id && <Check size={14} />}
                      <span>{w.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 5: AI Stylist Intelligence ── */}
          {activeTab === 'ai_stylist' && (
            <div className="settings-section">
              <h3>Yorvyn AI Stylist Persona</h3>
              <p className="section-desc">Customize recommendation tone, brand alignment, and aesthetic guidance philosophy.</p>

              <div className="setting-field-group">
                <label>Styling Direction & Philosophy</label>
                <div className="stylist-vibes-list">
                  {[
                    { id: 'modern_minimalist', label: 'Modern Architectural Minimalist', desc: 'Clean tailoring, neutral palettes, quiet luxury textures and impeccable proportions.' },
                    { id: 'bold_editorial', label: 'Bold Runway & High-Contrast', desc: 'Statement silhouettes, chromatic accents, fashion-forward silhouettes and elevated edge.' },
                    { id: 'relaxed_european', label: 'Relaxed European Contemporary', desc: 'Soft drape, linen/cashmere layering, understated sprezzatura and day-to-evening versatility.' }
                  ].map(vibe => (
                    <div 
                      key={vibe.id}
                      className={`stylist-vibe-card ${stylistVibe === vibe.id ? 'active' : ''}`}
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
                  onClick={() => { if (onClose) onClose(); navigate('/stylist'); }}
                >
                  Open Stylist Chat
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="settings-modal-footer">
          <button 
            type="button" 
            className="settings-reset-link"
            onClick={handleResetToScreenshotDefault}
          >
            <ArrowCounterClockwise size={15} />
            <span>Reset Look</span>
          </button>

          <div className="footer-actions-right">
            {onClose && (
              <button type="button" className="settings-cancel-btn" onClick={onClose}>
                {embedded ? 'Back to Studio' : 'Cancel'}
              </button>
            )}
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
      </aside>
  );

  if (embedded) {
    return panelContent;
  }

  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      {panelContent}
    </div>
  );
};

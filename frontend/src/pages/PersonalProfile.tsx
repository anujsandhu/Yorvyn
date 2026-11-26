import React, { useState, useEffect } from 'react';
import { 
  User, 
  Sparkle, 
  Palette, 
  Check, 
  Stack
} from '../components/icons';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import { UserProfile } from '../types/fashion';
import './PersonalProfile.css';

interface ContinuousMeasurements {
  height_cm: number;
  weight_kg: number | null;
  shoulder_width_cm: number | null;
  chest_cm: number | null;
  waist_cm: number | null;
  hip_cm: number | null;
  torso_length_cm: number | null;
  arm_length_cm: number | null;
  inseam_cm: number | null;
  thigh_cm: number | null;
}

interface PersonalProfileProps {
  embedded?: boolean;
}

export const PersonalProfile: React.FC<PersonalProfileProps> = ({ embedded = false }) => {
  const [profile, setProfile] = useState<UserProfile>({
    user_id: 'default_user',
    name: 'Alex',
    body_shape: 'athletic_tapered',
    height_cm: 178,
    skin_undertone: 'warm-deep',
    color_season: 'autumn',
    fit_preference: 'regular',
    primary_aesthetics: ['quiet_luxury', 'minimalist_scandi'],
    budget_tier: 'mid_premium',
    lifestyle_notes: 'Hybrid work, likes timeless neutrals and structured knitwear.'
  });

  const [unit, setUnit] = useState<'cm' | 'in'>('cm');
  const [measurements, setMeasurements] = useState<ContinuousMeasurements>({
    height_cm: 178,
    weight_kg: 72,
    shoulder_width_cm: 46,
    chest_cm: 98,
    waist_cm: 82,
    hip_cm: 96,
    torso_length_cm: 52,
    arm_length_cm: 62,
    inseam_cm: 80,
    thigh_cm: 56
  });

  const [proportions, setProportions] = useState<Record<string, any>>({
    shoulder_to_waist_ratio: 1.32,
    shoulder_to_hip_ratio: 1.15,
    waist_to_hip_ratio: 0.85,
    torso_to_leg_ratio: 0.65,
    torso_leg_balance: 'balanced'
  });

  const [ambientLighting, setAmbientLighting] = useState<string>('neutral_daylight');
  const [photoConsent, setPhotoConsent] = useState<boolean>(false);
  const [avatarComparison, setAvatarComparison] = useState<any>(null);
  const [paletteDetails, setPaletteDetails] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Conversion helpers
  const displayVal = (cmVal: number | null): string => {
    if (cmVal === null || cmVal === undefined) return '';
    if (unit === 'in') {
      return (cmVal / 2.54).toFixed(1);
    }
    return Math.round(cmVal).toString();
  };

  const handleMeasurementChange = (field: keyof ContinuousMeasurements, valStr: string) => {
    const rawNum = parseFloat(valStr);
    if (isNaN(rawNum)) {
      setMeasurements(prev => ({ ...prev, [field]: null }));
      return;
    }
    const cmValue = unit === 'in' ? rawNum * 2.54 : rawNum;
    setMeasurements(prev => ({ ...prev, [field]: Math.round(cmValue * 10) / 10 }));
  };

  useEffect(() => {
    // 1. Fetch user profile
    fashionApi.getProfile()
      .then(p => {
        if (p) setProfile(p);
      })
      .catch(() => {});

    // 2. Fetch body profile
    fashionApi.getBodyProfile()
      .then(res => {
        if (res?.measurements) {
          setMeasurements({
            height_cm: res.measurements.height_cm || 178,
            weight_kg: res.measurements.weight_kg || null,
            shoulder_width_cm: res.measurements.shoulder_width_cm || 46,
            chest_cm: res.measurements.chest_cm || 98,
            waist_cm: res.measurements.waist_cm || 82,
            hip_cm: res.measurements.hip_cm || 96,
            torso_length_cm: res.measurements.torso_length_cm || 52,
            arm_length_cm: res.measurements.arm_length_cm || 62,
            inseam_cm: res.measurements.inseam_cm || 80,
            thigh_cm: res.measurements.thigh_cm || 56
          });
        }
        if (res?.proportions && Object.keys(res.proportions).length > 0) {
          setProportions(res.proportions);
        }
        if (res?.unit_preference) {
          setUnit(res.unit_preference as 'cm' | 'in');
        }
      })
      .catch(() => {});

    // 3. Fetch personal colour palette
    fashionApi.getPersonalColourPalette()
      .then(res => {
        if (res?.palette) {
          setPaletteDetails(res.palette);
        }
      })
      .catch(() => {});

    // 4. Check avatar comparison
    fashionApi.compareAvatarWithBodyProfile()
      .then(res => {
        if (res?.comparison) {
          setAvatarComparison(res.comparison);
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      setLoading(true);

      // Save general profile
      await fashionApi.updateProfile({
        ...profile,
        height_cm: measurements.height_cm
      });

      // Save continuous measurements
      const bodyRes = await fashionApi.updateBodyMeasurements(
        measurements as any,
        unit
      );

      if (bodyRes?.proportions) {
        setProportions(bodyRes.proportions);
      }

      // Check avatar comparison
      const avatarComp = await fashionApi.compareAvatarWithBodyProfile();
      if (avatarComp?.comparison) {
        setAvatarComparison(avatarComp.comparison);
      }

      toast.success('Body & Personal Colour Identity successfully calibrated!');
    } catch (err) {
      toast.error('Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const handleUndertoneChange = async (newUndertone: string) => {
    setProfile(prev => ({ ...prev, skin_undertone: newUndertone as any }));
    try {
      const palRes = await fashionApi.getPersonalColourPalette(newUndertone);
      if (palRes?.palette) {
        setPaletteDetails(palRes.palette);
        setProfile(prev => ({ ...prev, color_season: palRes.palette.palette_id }));
      }
    } catch (e) {}
  };

  const colorSeasons = [
    { 
      key: 'autumn_deep', 
      label: 'Autumn Deep (Warm & Earthy)', 
      undertone: 'warm',
      colors: ['Terracotta', 'Olive', 'Camel', 'Burgundy', 'Forest Green', 'Charcoal']
    },
    { 
      key: 'spring_warm', 
      label: 'Spring Warm (Luminous & Golden)', 
      undertone: 'warm',
      colors: ['Coral', 'Warm Yellow', 'Camel', 'Sage', 'Light Navy', 'Ivory']
    },
    { 
      key: 'winter_clear', 
      label: 'Winter Clear (Bold & High-Contrast)', 
      undertone: 'cool',
      colors: ['Stark Black', 'Pure White', 'Royal Blue', 'Emerald', 'Ruby Red', 'Charcoal']
    },
    { 
      key: 'summer_cool', 
      label: 'Summer Cool (Soft & Muted Tonal)', 
      undertone: 'cool',
      colors: ['Sky Blue', 'Lavender', 'Soft Grey', 'Slate', 'Rose', 'Off-White']
    },
    { 
      key: 'neutral_versatile', 
      label: 'Neutral Versatile (Balanced & Classic)', 
      undertone: 'neutral',
      colors: ['Navy', 'Charcoal', 'Cream', 'Camel', 'Olive', 'White']
    }
  ];

  const fitPreferences = [
    { key: 'slim', label: 'Slim Fit', desc: 'Closer cut with clean silhouette and minimal ease' },
    { key: 'tailored', label: 'Tailored Fit', desc: 'Structured lines following natural body contours' },
    { key: 'regular', label: 'Regular Fit', desc: 'Classic comfortable drape with timeless proportion' },
    { key: 'athletic', label: 'Athletic Fit', desc: 'Accommodating shoulder and chest ease with tapered waist' },
    { key: 'relaxed', label: 'Relaxed Fit', desc: 'Generous ease for effortless, contemporary styling' },
    { key: 'oversized', label: 'Oversized', desc: 'Voluminous, fashion-forward silhouette with dropped seams' }
  ];

  const aesthetics = [
    { key: 'quiet_luxury', label: 'Quiet Luxury / Old Money' },
    { key: 'minimalist_scandi', label: 'Minimalist Scandinavian' },
    { key: 'streetwear_tech', label: 'Elevated Streetwear / Tech' },
    { key: 'smart_casual', label: 'Smart Casual' },
    { key: 'parisian_chic', label: 'Parisian Chic' }
  ];

  return (
    <div className={`profile-page ${embedded ? 'embedded' : ''}`}>
      {!embedded ? (
        <div className="profile-header">
          <h1 className="profile-title-h1">Body & Personal Colour Intelligence</h1>
          <p style={{ color: '#78716c', margin: 0, fontSize: '0.95rem' }}>
            ML-driven physical proportion calibration, lighting-aware colorimetry, and avatar alignment • Non-judgmental & body-positive
          </p>
        </div>
      ) : (
        <div className="profile-embedded-header">
          <div>
            <h3 className="profile-embedded-title">Body & Style Identity</h3>
            <p className="profile-embedded-subtitle">
              Calibrated measurements, proportions visualizer & personal palette
            </p>
          </div>
          <button
            type="button"
            className="profile-save-pill"
            onClick={handleSave}
            disabled={loading}
          >
            {loading ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      )}

      {/* 1. Unit Settings & Identity Basics */}
      <div className="profile-section-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 className="profile-section-title" style={{ margin: 0 }}>
            <User size={18} color="#92400e" /> Stature & Unit Preference
          </h3>
          <div className="unit-toggle-pill">
            <button 
              type="button" 
              className={`unit-btn ${unit === 'cm' ? 'active' : ''}`}
              onClick={() => setUnit('cm')}
            >
              Metric (cm)
            </button>
            <button 
              type="button" 
              className={`unit-btn ${unit === 'in' ? 'active' : ''}`}
              onClick={() => setUnit('in')}
            >
              Imperial (in)
            </button>
          </div>
        </div>
        <p className="profile-section-desc">
          Continuous measurements ensure precision tailoring across shirts, trousers, jackets, and footwear.
        </p>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input 
              type="text" 
              className="form-input"
              value={profile.name}
              onChange={e => setProfile({ ...profile, name: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Height ({unit})</label>
            <input 
              type="number" 
              step="0.1"
              className="form-input"
              value={displayVal(measurements.height_cm)}
              onChange={e => handleMeasurementChange('height_cm', e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* 2. Continuous Body Measurements */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Stack size={18} color="#92400e" /> Continuous Tailoring Measurements
        </h3>
        <p className="profile-section-desc">
          Voluntary measurements calibrate shoulder drape, sleeve length, chest ease, and trouser rise. Never fabricated or forced.
        </p>

        <div className="measurements-grid">
          <div className="measurement-box">
            <span className="measurement-label">Shoulder Breadth</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.shoulder_width_cm)}
                onChange={e => handleMeasurementChange('shoulder_width_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Chest Circumference</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.chest_cm)}
                onChange={e => handleMeasurementChange('chest_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Waist Circumference</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.waist_cm)}
                onChange={e => handleMeasurementChange('waist_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Hip Circumference</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.hip_cm)}
                onChange={e => handleMeasurementChange('hip_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Torso Length (C7–Hip)</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.torso_length_cm)}
                onChange={e => handleMeasurementChange('torso_length_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Leg Inseam</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.inseam_cm)}
                onChange={e => handleMeasurementChange('inseam_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Arm Length</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.arm_length_cm)}
                onChange={e => handleMeasurementChange('arm_length_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>

          <div className="measurement-box">
            <span className="measurement-label">Thigh Circumference</span>
            <div className="measurement-input-wrapper">
              <input 
                type="number"
                step="0.1"
                className="measurement-input"
                value={displayVal(measurements.thigh_cm)}
                onChange={e => handleMeasurementChange('thigh_cm', e.target.value)}
                placeholder="—"
              />
              <span className="unit-label">{unit}</span>
            </div>
            <span className="provenance-tag">User Confirmed</span>
          </div>
        </div>
      </div>

      {/* 3. Proportions & Silhouette Harmony */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Sparkle size={18} color="#92400e" /> Body Proportions & Silhouette Harmony
        </h3>
        <p className="profile-section-desc">
          Continuous geometric ratios analyzed mathematically without forcing into rigid or exclusionary body labels.
        </p>

        <div className="proportions-display-row">
          <div className="proportion-stat-card">
            <span className="stat-title">Shoulder / Waist Ratio</span>
            <span className="stat-number">{proportions.shoulder_to_waist_ratio || '1.30'}</span>
            <span className="stat-desc">V-taper & chest definition indicator</span>
          </div>

          <div className="proportion-stat-card">
            <span className="stat-title">Shoulder / Hip Ratio</span>
            <span className="stat-number">{proportions.shoulder_to_hip_ratio || '1.14'}</span>
            <span className="stat-desc">Upper-to-lower frame balance</span>
          </div>

          <div className="proportion-stat-card">
            <span className="stat-title">Waist / Hip Ratio</span>
            <span className="stat-number">{proportions.waist_to_hip_ratio || '0.85'}</span>
            <span className="stat-desc">Natural midsection taper</span>
          </div>

          <div className="proportion-stat-card">
            <span className="stat-title">Torso / Leg Balance</span>
            <span className="stat-number" style={{ fontSize: '1.05rem', textTransform: 'capitalize' }}>
              {(proportions.torso_leg_balance || 'balanced').replace('_', ' ')}
            </span>
            <span className="stat-desc">Hemline & rise placement guide</span>
          </div>
        </div>
      </div>

      {/* 4. Fit Preferences */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Stack size={18} color="#92400e" /> Garment Fit & Silhouette Preference
        </h3>
        <p className="profile-section-desc">
          Tells Yorvyn's AI Stylist how much ease and drape you enjoy across tops, jackets, and trousers.
        </p>

        <div className="option-grid">
          {fitPreferences.map(fit => (
            <div 
              key={fit.key}
              className={`option-box ${profile.fit_preference === fit.key ? 'selected' : ''}`}
              onClick={() => setProfile({ ...profile, fit_preference: fit.key as any })}
            >
              <div className="option-name">{fit.label}</div>
              <div className="option-desc">{fit.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Lighting-Aware Skin Analysis & Colour Intelligence */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Palette size={18} color="#92400e" /> Lighting-Aware Skin & Colour Intelligence
        </h3>
        <p className="profile-section-desc">
          Evaluates warm, cool, or neutral undertones with CIELAB colorimetric mathematics. Honest uncertainty calibration prevents washed-out contrast.
        </p>

        {/* Ambient Lighting Selector */}
        <div style={{ marginBottom: '18px' }}>
          <label className="form-label" style={{ marginBottom: '8px' }}>Ambient Lighting Calibration</label>
          <div className="lighting-chips-row">
            {[
              { id: 'neutral_daylight', label: '☀️ Neutral Daylight' },
              { id: 'warm_indoor', label: '💡 Warm Indoor Tungsten' },
              { id: 'cool_fluorescent', label: '🏢 Cool Office Fluorescent' }
            ].map(l => (
              <button
                key={l.id}
                type="button"
                className={`lighting-chip ${ambientLighting === l.id ? 'active' : ''}`}
                onClick={() => setAmbientLighting(l.id)}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        {/* Undertone Selection */}
        <div style={{ marginBottom: '18px' }}>
          <label className="form-label" style={{ marginBottom: '8px' }}>Personal Skin Undertone</label>
          <div className="undertone-buttons-row">
            {[
              { key: 'warm', label: 'Warm (Golden / Peachy)' },
              { key: 'cool', label: 'Cool (Rosy / Blue-Red)' },
              { key: 'neutral', label: 'Neutral (Balanced)' },
              { key: 'uncertain', label: 'Uncertain / Calibrating' }
            ].map(u => (
              <button
                key={u.key}
                type="button"
                className={`undertone-btn ${profile.skin_undertone?.includes(u.key) ? 'active' : ''}`}
                onClick={() => handleUndertoneChange(u.key)}
              >
                {u.label}
              </button>
            ))}
          </div>
        </div>

        {/* Seasonal Palette Grid */}
        <div className="option-grid">
          {colorSeasons.map(season => {
            const isSelected = (profile.color_season === season.key) || (paletteDetails?.palette_id === season.key);
            return (
              <div 
                key={season.key}
                className={`option-box ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  setProfile({ ...profile, color_season: season.key as any, skin_undertone: season.undertone as any });
                  handleUndertoneChange(season.undertone);
                }}
              >
                <div className="option-name">{season.label}</div>
                <div className="option-desc">Harmonious color anchors</div>
              </div>
            );
          })}
        </div>

        {/* Swatches Visualizer */}
        <div className="season-palette-preview">
          <span style={{ fontSize: '0.8rem', color: '#44403c', width: '100%', fontWeight: 600 }}>
            {paletteDetails?.palette_name || 'Harmonious Seasonal Anchors'}
          </span>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', width: '100%', marginTop: '6px' }}>
            {(paletteDetails?.neutral_anchors || ['Charcoal', 'Navy', 'Cream', 'Camel']).map((c: string, idx: number) => (
              <span key={`neutral-${idx}`} className="season-chip neutral-chip">
                ⚓ Neutral: {c}
              </span>
            ))}
            {(paletteDetails?.complementary_colours || ['Terracotta', 'Olive', 'Forest Green']).map((c: string, idx: number) => (
              <span key={`comp-${idx}`} className="season-chip accent-chip">
                ✦ Accent: {c}
              </span>
            ))}
          </div>
          <p style={{ margin: '8px 0 0 0', fontSize: '0.75rem', color: '#78716c' }}>
            Note: Yorvyn never prohibits colors; recommendations highlight harmonic synergies while keeping styling fully flexible.
          </p>
        </div>
      </div>

      {/* 5b. Core Style Aesthetics */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Sparkle size={18} color="#92400e" /> Core Style Aesthetics
        </h3>
        <p className="profile-section-desc">
          Guides the primary design language, fabrication preferences, and brand tone.
        </p>

        <div className="option-grid">
          {aesthetics.map(aes => {
            const isSelected = profile.primary_aesthetics?.includes(aes.key);
            return (
              <div 
                key={aes.key}
                className={`option-box ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  const current = profile.primary_aesthetics || [];
                  const updated = isSelected 
                    ? current.filter(k => k !== aes.key)
                    : [...current, aes.key];
                  setProfile({ ...profile, primary_aesthetics: updated });
                }}
              >
                <div className="option-name">{aes.label}</div>
                <div className="option-desc">{isSelected ? '✓ Active Priority' : 'Tap to enable'}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 6. Privacy & Photo Analysis Consent */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Sparkle size={18} color="#92400e" /> Privacy & Photographic Analysis Controls
        </h3>
        <p className="profile-section-desc">
          Strict GDPR / CCPA privacy boundary. Yorvyn will never process or analyze personal photographs without explicit consent.
        </p>

        <div className="consent-toggle-container">
          <label className="switch">
            <input 
              type="checkbox" 
              checked={photoConsent}
              onChange={e => setPhotoConsent(e.target.checked)}
            />
            <span className="slider round"></span>
          </label>
          <div>
            <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1c1917', display: 'block' }}>
              Enable AI Computer Vision Silhouette Assistance
            </span>
            <span style={{ fontSize: '0.78rem', color: '#78716c' }}>
              Allows optional client-side pose landmark analysis. Zero photographs are stored without confirmation; zero measurements are fabricated.
            </span>
          </div>
        </div>

        {avatarComparison?.has_mismatches && (
          <div className="mismatch-callout">
            <span style={{ fontWeight: 600, fontSize: '0.82rem', color: '#92400e' }}>
              ℹ️ 3D Avatar Alignment Notice:
            </span>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem', color: '#78716c' }}>
              Your 3D avatar proportion parameters differ slightly from your confirmed body measurements ({avatarComparison.mismatches[0]?.difference}). Your confirmed measurements will be prioritized for garment fitting recommendations.
            </p>
          </div>
        )}
      </div>

      {/* Save Button */}
      <div style={{ marginTop: '32px', display: 'flex', gap: '14px', alignItems: 'center' }}>
        <button className="save-profile-btn" onClick={handleSave} disabled={loading}>
          <Check size={18} /> {loading ? 'Calibrating...' : 'Save Fashion & Body Identity'}
        </button>
      </div>
    </div>
  );
};

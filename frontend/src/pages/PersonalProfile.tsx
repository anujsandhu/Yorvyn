import React, { useState, useEffect } from 'react';
import { 
  User, 
  Sparkles, 
  Palette, 
  Check, 
  Layers
} from 'lucide-react';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import { UserProfile } from '../types/fashion';
import './PersonalProfile.css';

export const PersonalProfile: React.FC = () => {
  const [profile, setProfile] = useState<UserProfile>({
    user_id: 'default_user',
    name: 'Alex',
    body_shape: 'athletic_tapered',
    height_cm: 178,
    skin_undertone: 'warm-bright',
    color_season: 'autumn',
    fit_preference: 'relaxed_tailored',
    primary_aesthetics: ['quiet_luxury', 'minimalist_scandi'],
    budget_tier: 'mid_premium',
    lifestyle_notes: 'Hybrid work, likes timeless neutrals and structured knitwear.'
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fashionApi.getProfile().then(setProfile).catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      setLoading(true);
      const updated = await fashionApi.updateProfile(profile);
      setProfile(updated);
      toast.success('Personal fashion identity updated!');
    } catch (err) {
      toast.error('Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const bodyShapes = [
    { key: 'athletic_tapered', label: 'Athletic / Tapered', desc: 'Broader shoulders tapering to a defined waist' },
    { key: 'rectangle', label: 'Balanced / Straight', desc: 'Proportional shoulders and hips with clean geometric drape' },
    { key: 'hourglass', label: 'Curved / Hourglass', desc: 'Balanced bust/shoulders and hips with defined waist' },
    { key: 'inverted_triangle', label: 'Inverted Triangle', desc: 'Prominent shoulder line requiring balanced lower silhouettes' },
    { key: 'pear', label: 'A-Frame / Pear', desc: 'Wider hip proportion; benefits from structured shoulder layering' }
  ];

  const colorSeasons = [
    { 
      key: 'autumn', 
      label: 'Autumn (Warm & Deep)', 
      undertone: 'warm-deep',
      colors: ['Terracotta', 'Olive', 'Camel', 'Burgundy', 'Forest Green', 'Rust']
    },
    { 
      key: 'spring', 
      label: 'Spring (Warm & Bright)', 
      undertone: 'warm-bright',
      colors: ['Coral', 'Warm Yellow', 'Camel', 'Sage', 'Light Navy', 'Cream']
    },
    { 
      key: 'winter', 
      label: 'Winter (Cool & Bright)', 
      undertone: 'cool-bright',
      colors: ['Stark Black', 'Pure White', 'Royal Blue', 'Emerald', 'Ruby Red']
    },
    { 
      key: 'summer', 
      label: 'Summer (Cool & Soft)', 
      undertone: 'cool-soft',
      colors: ['Sky Blue', 'Lavender', 'Soft Grey', 'Rose', 'Off-White']
    }
  ];

  const aesthetics = [
    { key: 'quiet_luxury', label: 'Quiet Luxury / Old Money' },
    { key: 'minimalist_scandi', label: 'Minimalist Scandinavian' },
    { key: 'streetwear_tech', label: 'Elevated Streetwear / Tech' },
    { key: 'smart_casual', label: 'Smart Casual' },
    { key: 'parisian_chic', label: 'Parisian Chic' }
  ];

  return (
    <div className="profile-page">
      <div className="profile-header">
        <h1 className="profile-title-h1">Personal Identity & Style Profile</h1>
        <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.95rem' }}>
          User-controlled fashion identity • Grounds all recommendation and visual fitting algorithms
        </p>
      </div>

      {/* Basic Identity */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <User size={18} color="#d4af37" /> Profile Basics
        </h3>
        <p className="profile-section-desc">Your personal styling name and height for proportional drape calculation.</p>
        
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
            <label className="form-label">Height (cm)</label>
            <input 
              type="number" 
              className="form-input"
              value={profile.height_cm}
              onChange={e => setProfile({ ...profile, height_cm: Number(e.target.value) })}
            />
          </div>
        </div>
      </div>

      {/* Body Geometry Profile */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Layers size={18} color="#d4af37" /> Body Geometry & Proportion
        </h3>
        <p className="profile-section-desc">Informs silhouette balancing, hemline lengths, and tailoring recommendations.</p>

        <div className="option-grid">
          {bodyShapes.map(shape => (
            <div 
              key={shape.key}
              className={`option-box ${profile.body_shape === shape.key ? 'selected' : ''}`}
              onClick={() => setProfile({ ...profile, body_shape: shape.key as any })}
            >
              <div className="option-name">{shape.label}</div>
              <div className="option-desc">{shape.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Color Season & Palette */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Palette size={18} color="#d4af37" /> Seasonal Color Analysis
        </h3>
        <p className="profile-section-desc">Identifies harmonious undertones to prevent washed-out facial contrast.</p>

        <div className="option-grid">
          {colorSeasons.map(season => (
            <div 
              key={season.key}
              className={`option-box ${profile.color_season === season.key ? 'selected' : ''}`}
              onClick={() => setProfile({ ...profile, color_season: season.key as any, skin_undertone: season.undertone as any })}
            >
              <div className="option-name">{season.label}</div>
              <div className="option-desc">Optimal undertone calibration</div>
            </div>
          ))}
        </div>

        {/* Selected Palette Preview */}
        <div className="season-palette-preview">
          <span style={{ fontSize: '0.78rem', color: '#94a3b8', width: '100%', marginBottom: '4px' }}>
            Recommended {profile.color_season?.toUpperCase()} Color Palette Anchors:
          </span>
          {colorSeasons.find(s => s.key === profile.color_season)?.colors.map((c, i) => (
            <span key={i} className="season-chip">
              ● {c}
            </span>
          ))}
        </div>
      </div>

      {/* Aesthetics */}
      <div className="profile-section-card">
        <h3 className="profile-section-title">
          <Sparkles size={18} color="#d4af37" /> Core Style Aesthetics
        </h3>
        <p className="profile-section-desc">Guides the primary design language, fabrication preferences, and brand tone.</p>

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

      {/* Save Button */}
      <div style={{ marginTop: '32px' }}>
        <button className="save-profile-btn" onClick={handleSave} disabled={loading}>
          <Check size={18} /> {loading ? 'Saving Changes...' : 'Save Fashion Identity'}
        </button>
      </div>
    </div>
  );
};

import React, { useState, useEffect, useRef } from 'react';
import { 
  Plus, 
  Trash, 
  Heart, 
  Sparkle,
  UploadSimple,
  X
} from '../components/icons';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import {
  intelligenceApi,
  type ExternalWebReference,
  type HybridRecommendationItem,
  type WardrobeRecommendationItem,
} from '../services/intelligenceApi';
import { Garment, ClosetAnalytics, GarmentCategory } from '../types/fashion';
import './DigitalWardrobe.css';

export const DigitalWardrobe: React.FC = () => {
  const [items, setItems] = useState<Garment[]>([]);
  const [analytics, setAnalytics] = useState<ClosetAnalytics | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [matchedIds, setMatchedIds] = useState<string[] | null>(null);
  const [recommendations, setRecommendations] = useState<WardrobeRecommendationItem[]>([]);
  const [hybridRecs, setHybridRecs] = useState<HybridRecommendationItem[]>([]);
  const [exploreCategories, setExploreCategories] = useState<string[]>([]);
  const [trendRefs, setTrendRefs] = useState<ExternalWebReference[]>([]);
  const [recColdStart, setRecColdStart] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form State
  const [newItemName, setNewItemName] = useState('');
  const [newItemCategory, setNewItemCategory] = useState<GarmentCategory>('top');
  const [newItemColor, setNewItemColor] = useState('black');
  const [newItemBrand, setNewItemBrand] = useState('Acne Studios');
  const [newItemWarmth, setNewItemWarmth] = useState(5);
  const [newItemFormality, setNewItemFormality] = useState(5);
  const [newItemImageUrl, setNewItemImageUrl] = useState('');
  const [newItemImageName, setNewItemImageName] = useState('');
  const [newItemInputMode, setNewItemInputMode] = useState<'upload' | 'url'>('upload');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Please upload an image file (PNG, JPG, or WEBP)');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error('Image file exceeds 15MB limit');
      return;
    }
    setNewItemImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setNewItemImageUrl(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Please upload an image file (PNG, JPG, or WEBP)');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error('Image file exceeds 15MB limit');
      return;
    }
    setNewItemImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setNewItemImageUrl(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleClearImage = () => {
    setNewItemImageUrl('');
    setNewItemImageName('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  useEffect(() => {
    loadWardrobeData();
  }, [selectedCategory]);

  const refreshWardrobeRecommendations = (anchor?: Garment) => {
    intelligenceApi.getHybridRecommendations({
      mode: 'neural_hybrid',
      surface: 'wardrobe',
      anchorItem: anchor ? (anchor as any) : undefined,
      topK: 4,
    })
      .then((res) => {
        setHybridRecs(res.recommendations || []);
        setExploreCategories(Object.keys(res.category_recommendations || {}).slice(0, 3));
        setRecColdStart(Boolean(res.cold_start_mode));
      })
      .catch(() => {
        intelligenceApi.getWardrobeRecommendations().then(setRecommendations).catch(() => {});
      });
  };

  useEffect(() => {
    refreshWardrobeRecommendations();
  }, []);

  const handleRecommendationFeedback = async (rec: HybridRecommendationItem, interactionType: 'liked' | 'recommendation_dismissed') => {
    try {
      await intelligenceApi.recordRecommendationFeedback({
        interactionType,
        itemData: rec as any,
        sessionId: 'wardrobe_discovery',
      });
      toast.success(interactionType === 'liked' ? `Saved style signal for "${rec.name}"` : `Dismissed "${rec.name}"`);
      refreshWardrobeRecommendations();
    } catch {
      toast.error('Could not update recommendation preference');
    }
  };

  const handleSmartSearch = async (queryText: string) => {
    setSearchQuery(queryText);
    const trimmed = queryText.trim();
    if (!trimmed) {
      setMatchedIds(null);
      return;
    }
    try {
      const matches = await intelligenceApi.rankWardrobeSearch(trimmed, items, 20);
      setMatchedIds(matches.filter((m) => m.similarity_score > 0.05).map((m) => m.item_id));
    } catch {
      const lower = trimmed.toLowerCase();
      setMatchedIds(
        items
          .filter((it) => `${it.name} ${it.color} ${it.brand} ${it.category}`.toLowerCase().includes(lower))
          .map((it) => String(it.id)),
      );
    }
  };

  const loadWardrobeData = async () => {
    try {
      setLoading(true);
      const [wardrobeRes, analyticsRes] = await Promise.all([
        fashionApi.getWardrobe(selectedCategory === 'all' ? undefined : selectedCategory),
        fashionApi.getAnalytics()
      ]);
      setItems(wardrobeRes.items || []);
      setAnalytics(analyticsRes);
    } catch (err) {
      toast.error('Failed to load wardrobe pieces');
    } finally {
      setLoading(false);
    }
  };

  const handleAddItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim()) {
      toast.error('Please enter a garment name');
      return;
    }

    try {
      const added = await fashionApi.addGarment({
        name: newItemName,
        category: newItemCategory,
        color: newItemColor,
        brand: newItemBrand,
        warmth: Number(newItemWarmth),
        formality: Number(newItemFormality),
        image_url: newItemImageUrl || 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=600&q=80'
      });
      setItems(prev => [added, ...prev]);
      toast.success('Garment digitized into wardrobe!');
      setIsModalOpen(false);
      // Reset
      setNewItemName('');
      setNewItemImageUrl('');
      // Reload analytics
      fashionApi.getAnalytics().then(setAnalytics);
    } catch (err) {
      toast.error('Failed to add garment');
    }
  };

  const handleDeleteItem = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to remove this piece from your digital closet?')) return;
    try {
      await fashionApi.deleteGarment(id);
      setItems(prev => prev.filter(item => item.id !== id));
      toast.success('Garment removed');
      fashionApi.getAnalytics().then(setAnalytics);
    } catch (err) {
      toast.error('Failed to remove garment');
    }
  };

  const handleToggleFavorite = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const updated = await fashionApi.toggleFavorite(id);
      setItems(prev => prev.map(item => item.id === id ? { ...item, favorite: updated.favorite } : item));
    } catch (err) {
      toast.error('Could not update favorite');
    }
  };

  const categories = [
    { key: 'all', label: 'All Pieces' },
    { key: 'top', label: 'Tops & Knitwear' },
    { key: 'bottom', label: 'Trousers & Denim' },
    { key: 'outerwear', label: 'Outerwear & Coats' },
    { key: 'footwear', label: 'Shoes & Boots' },
    { key: 'accessory', label: 'Accessories' }
  ];

  return (
    <div className="wardrobe-studio-page">
      {/* Header */}
      <div className="wardrobe-header">
        <div>
          <h1 className="wardrobe-title-h1">Digital Wardrobe Studio</h1>
          <p className="wardrobe-subtitle">
            Curated closet state • Computer Vision tagged • Personal Knowledge Graph grounded
          </p>
        </div>
        <button className="add-garment-btn" onClick={() => setIsModalOpen(true)}>
          <Plus size={18} /> Digitize New Piece
        </button>
      </div>

      {/* Analytics Row */}
      {analytics && (
        <div className="wardrobe-analytics-row">
          <div className="analytics-card">
            <div className="analytics-metric-num">{analytics.total_items}</div>
            <div className="analytics-metric-label">Digitized Wardrobe Staples</div>
          </div>
          <div className="analytics-card">
            <div className="analytics-metric-num">{analytics.closet_utilization_rate}%</div>
            <div className="analytics-metric-label">Closet Utilization Rate</div>
          </div>
          <div className="analytics-card">
            <div className="analytics-metric-num">{Object.keys(analytics.color_palette_distribution || {}).length}</div>
            <div className="analytics-metric-label">Unique Palette Accents</div>
          </div>
          <div className="analytics-card">
            <div className="analytics-metric-num" style={{ color: '#10b981' }}>
              {analytics.most_worn_staples?.[0]?.name ? analytics.most_worn_staples[0].brand : 'COS'}
            </div>
            <div className="analytics-metric-label">Most Worn Brand Anchor</div>
          </div>
        </div>
      )}

      {/* Category Tabs + Smart Wardrobe Search */}
      <div className="wardrobe-tabs-bar" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {categories.map(c => (
            <button
              key={c.key}
              className={`wardrobe-tab ${selectedCategory === c.key ? 'active' : ''}`}
              onClick={() => setSelectedCategory(c.key)}
            >
              {c.label}
            </button>
          ))}
        </div>
        <input
          type="search"
          aria-label="Smart wardrobe search"
          placeholder="Smart search (e.g. navy denim jacket, minimal)"
          value={searchQuery}
          onChange={(e) => handleSmartSearch(e.target.value)}
          style={{
            minWidth: 250,
            padding: '8px 12px',
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,0.14)',
            background: 'rgba(15, 23, 42, 0.72)',
            color: '#f8fafc',
            fontSize: '0.84rem',
          }}
        />
      </div>

      {(hybridRecs.length > 0 || recommendations.length > 0) && (
        <div
          data-testid="wardrobe-smart-recommendations"
          style={{
            marginBottom: 16,
            padding: '10px 14px',
            borderRadius: 12,
            background: 'rgba(212, 175, 55, 0.08)',
            border: '1px solid rgba(212, 175, 55, 0.22)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
            fontSize: '0.8rem',
            color: '#e2e8f0',
          }}
        >
          <Sparkle size={15} color="#d4af37" />
          <strong>Curated for your wardrobe{recColdStart ? ' (Discovery Baseline)' : ''}:</strong>
          {hybridRecs.length > 0
            ? hybridRecs.slice(0, 3).map((rec) => (
                <span
                  key={rec.item_id}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 999,
                    background: 'rgba(15, 23, 42, 0.65)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                  title={rec.reasons.map((r) => r.message).join(' • ')}
                >
                  <span>
                    {rec.name} ({rec.color})
                    {rec.is_exploration ? ' • Explore' : ''}
                  </span>
                  <button
                    type="button"
                    aria-label={`Like ${rec.name}`}
                    onClick={() => handleRecommendationFeedback(rec, 'liked')}
                    style={{ background: 'transparent', border: 'none', color: '#4ade80', cursor: 'pointer', padding: 0, fontSize: '0.75rem' }}
                  >
                    +
                  </button>
                  <button
                    type="button"
                    aria-label={`Dismiss ${rec.name}`}
                    onClick={() => handleRecommendationFeedback(rec, 'recommendation_dismissed')}
                    style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0, fontSize: '0.75rem' }}
                  >
                    ×
                  </button>
                </span>
              ))
            : recommendations.slice(0, 3).map((rec) => (
                <span
                  key={rec.item_id}
                  style={{
                    padding: '3px 9px',
                    borderRadius: 999,
                    background: 'rgba(15, 23, 42, 0.65)',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                  title={rec.rationale.join(' • ')}
                >
                  {rec.name} ({rec.color})
                </span>
              ))}
          {exploreCategories.length > 0 && (
            <span style={{ fontSize: '0.74rem', color: '#cbd5e1' }}>
              Explore categories: {exploreCategories.join(' · ')}
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              intelligenceApi
                .searchExternalWeb(`${selectedCategory === 'all' ? 'seasonal capsule wardrobe' : selectedCategory} fashion trends`, true, 2)
                .then((res) => setTrendRefs(res.external_evidence || []))
                .catch(() => {});
            }}
            style={{
              padding: '3px 9px',
              borderRadius: 999,
              background: 'rgba(15, 23, 42, 0.75)',
              border: '1px solid rgba(147,197,253,0.3)',
              color: '#93c5fd',
              fontSize: '0.72rem',
              cursor: 'pointer',
            }}
          >
            Seasonal Trend Context
          </button>
          {trendRefs.slice(0, 1).map((t, idx) => (
            <a
              key={idx}
              href={t.source_url}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: '0.72rem', color: '#93c5fd' }}
            >
              [External Web Reference — Unverified] {t.source_title || t.domain}
            </a>
          ))}
        </div>
      )}

      {/* Garments Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#94a3b8' }}>
          <Sparkle size={28} className="animate-spin" color="#d4af37" style={{ marginBottom: '12px' }} />
          <div>Synchronizing Digital Wardrobe State...</div>
        </div>
      ) : (
        <div className="garments-grid">
          {(matchedIds ? items.filter((it) => matchedIds.includes(String(it.id))) : items).map(item => (
            <div key={item.id} className="garment-card">
              <div className="garment-image-box">
                <img src={item.image_url} alt={item.name} className="garment-img" />
                <div 
                  className="garment-fav-badge"
                  onClick={(e) => handleToggleFavorite(item.id, e)}
                >
                  <Heart 
                    size={16} 
                    color={item.favorite ? "#ef4444" : "#cbd5e1"} 
                    fill={item.favorite ? "#ef4444" : "none"} 
                  />
                </div>
              </div>

              <div className="garment-details">
                <span className="garment-brand-tag">{item.brand}</span>
                <h3 className="garment-name">{item.name}</h3>

                <div className="garment-badges-row">
                  <span className="garment-badge" style={{ textTransform: 'capitalize' }}>
                    {item.color}
                  </span>
                  <span className="garment-badge">
                    Warmth {item.warmth}/10
                  </span>
                  <span className="garment-badge">
                    Formality {item.formality}/10
                  </span>
                </div>

                <div className="garment-card-footer">
                  <span className="wear-count-text">Worn {item.wear_count} times</span>
                  <button 
                    className="garment-delete-btn"
                    onClick={(e) => handleDeleteItem(item.id, e)}
                    title="Remove piece"
                  >
                    <Trash size={15} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Garment Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h2 className="modal-title">Digitize Clothing Piece</h2>
            <form onSubmit={handleAddItem}>
              <div className="form-group">
                <label className="form-label">Garment Title</label>
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="e.g. Embroidered Bandhgala, Raw Silk Kurta, Linen Nehru Jacket"
                  value={newItemName}
                  onChange={e => setNewItemName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Category</label>
                <select 
                  className="form-select"
                  value={newItemCategory}
                  onChange={e => setNewItemCategory(e.target.value as GarmentCategory)}
                >
                  <option value="top">Top / Knitwear / Shirt</option>
                  <option value="bottom">Bottom / Trousers / Jeans</option>
                  <option value="outerwear">Outerwear / Coat / Jacket</option>
                  <option value="footwear">Footwear / Shoes / Boots</option>
                  <option value="accessory">Accessory / Watch / Bag</option>
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Primary Color</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="e.g. Royal Blue, Emerald Green, Marigold, Crimson"
                    value={newItemColor}
                    onChange={e => setNewItemColor(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Brand</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="e.g. Manyavar, Fabindia, Sabyasachi, Anita Dongre"
                    value={newItemBrand}
                    onChange={e => setNewItemBrand(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Warmth Rating (1 - 10)</label>
                  <input 
                    type="number" 
                    min="1" 
                    max="10" 
                    className="form-input" 
                    value={newItemWarmth}
                    onChange={e => setNewItemWarmth(Number(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Formality (1 - 10)</label>
                  <input 
                    type="number" 
                    min="1" 
                    max="10" 
                    className="form-input" 
                    value={newItemFormality}
                    onChange={e => setNewItemFormality(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label className="form-label" style={{ margin: 0 }}>Cloth Photograph</label>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      type="button"
                      style={{
                        padding: '3px 8px',
                        fontSize: '0.72rem',
                        borderRadius: '6px',
                        border: '1px solid #cbd5e1',
                        background: newItemInputMode === 'upload' ? '#0f172a' : '#f8fafc',
                        color: newItemInputMode === 'upload' ? '#ffffff' : '#64748b',
                        cursor: 'pointer'
                      }}
                      onClick={() => setNewItemInputMode('upload')}
                    >
                      Upload File
                    </button>
                    <button
                      type="button"
                      style={{
                        padding: '3px 8px',
                        fontSize: '0.72rem',
                        borderRadius: '6px',
                        border: '1px solid #cbd5e1',
                        background: newItemInputMode === 'url' ? '#0f172a' : '#f8fafc',
                        color: newItemInputMode === 'url' ? '#ffffff' : '#64748b',
                        cursor: 'pointer'
                      }}
                      onClick={() => setNewItemInputMode('url')}
                    >
                      Image URL
                    </button>
                  </div>
                </div>

                {newItemInputMode === 'upload' ? (
                  <div
                    style={{
                      border: '2px dashed #cbd5e1',
                      borderRadius: '12px',
                      padding: '1rem',
                      textAlign: 'center',
                      background: newItemImageUrl ? '#f0fdf4' : '#f8fafc',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease'
                    }}
                    onDragOver={e => e.preventDefault()}
                    onDrop={handleDrop}
                    onClick={() => !newItemImageUrl && fileInputRef.current?.click()}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/jpg"
                      style={{ display: 'none' }}
                      onChange={handleFileChange}
                    />
                    {newItemImageUrl ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left' }}>
                        <img 
                          src={newItemImageUrl} 
                          alt="Cloth Preview" 
                          style={{ width: '56px', height: '56px', objectFit: 'cover', borderRadius: '8px', border: '1px solid #e2e8f0' }} 
                        />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 600, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {newItemImageName || 'Cloth photo'}
                          </p>
                          <span style={{ fontSize: '0.72rem', color: '#16a34a', fontWeight: 600 }}>Ready to save</span>
                        </div>
                        <button
                          type="button"
                          style={{ background: '#f1f5f9', border: 'none', borderRadius: '50%', width: '28px', height: '28px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleClearImage();
                          }}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                        <UploadSimple size={24} style={{ color: '#64748b' }} />
                        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155' }}>Click to browse cloth photo, or drag & drop</span>
                        <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>PNG, JPG, or WEBP up to 15MB</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <input 
                    type="url" 
                    className="form-input" 
                    placeholder="https://images.unsplash.com/..."
                    value={newItemImageUrl}
                    onChange={e => setNewItemImageUrl(e.target.value)}
                  />
                )}
              </div>

              <div className="modal-actions">
                <button type="button" className="modal-btn cancel" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="modal-btn submit">
                  Save to Wardrobe
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

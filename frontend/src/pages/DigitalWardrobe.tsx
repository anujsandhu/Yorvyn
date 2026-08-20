import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Trash2, 
  Heart, 
  Sparkles
} from 'lucide-react';
import toast from 'react-hot-toast';
import { fashionApi } from '../services/fashionApi';
import { Garment, ClosetAnalytics, GarmentCategory } from '../types/fashion';
import './DigitalWardrobe.css';

export const DigitalWardrobe: React.FC = () => {
  const [items, setItems] = useState<Garment[]>([]);
  const [analytics, setAnalytics] = useState<ClosetAnalytics | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
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

  useEffect(() => {
    loadWardrobeData();
  }, [selectedCategory]);

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

      {/* Category Tabs */}
      <div className="wardrobe-tabs-bar">
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

      {/* Garments Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#94a3b8' }}>
          <Sparkles size={28} className="animate-spin" color="#d4af37" style={{ marginBottom: '12px' }} />
          <div>Synchronizing Digital Wardrobe State...</div>
        </div>
      ) : (
        <div className="garments-grid">
          {items.map(item => (
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
                    <Trash2 size={15} />
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
                  placeholder="e.g. Vintage Double-Breasted Wool Blazer"
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
                    placeholder="e.g. Camel, Navy, Charcoal"
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
                    placeholder="e.g. Loro Piana, COS"
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
                <label className="form-label">Image URL (Optional)</label>
                <input 
                  type="url" 
                  className="form-input" 
                  placeholder="https://images.unsplash.com/..."
                  value={newItemImageUrl}
                  onChange={e => setNewItemImageUrl(e.target.value)}
                />
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

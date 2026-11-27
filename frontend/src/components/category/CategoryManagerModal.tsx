import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Plus,
  Trash,
  Check,
  Eye,
  EyeSlash,
  PushPin,
  PencilSimple,
  UploadSimple,
  ArrowCounterClockwise,
  ArrowUp,
  ArrowDown,
  DotsSixVertical,
  MagnifyingGlass,
  WarningCircle,
  Sparkle
} from '../icons';
import { WardrobeCategory, CategoryItemType } from '../../types/fashion';
import {
  wardrobeCategoryService,
  PRESET_CATEGORY_TEMPLATES
} from '../../services/wardrobeCategoryService';
import { sanitizeSvgString } from '../../utils/svgSanitizer';
import { CategoryIcon, PRESET_ICON_MAP } from './CategoryIcon';
import toast from 'react-hot-toast';
import './CategoryManagerModal.css';

interface CategoryManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId?: string;
  onCategoryChanged?: () => void;
  embedded?: boolean;
}

export const CategoryManagerModal: React.FC<CategoryManagerModalProps> = ({
  isOpen,
  onClose,
  userId,
  onCategoryChanged,
  embedded = false
}) => {
  const [categories, setCategories] = useState<WardrobeCategory[]>([]);
  const [activeTab, setActiveTab] = useState<'manage' | 'add' | 'presets'>('manage');

  // Form State for Adding / Editing Category
  const [editingId, setEditingId] = useState<string | null>(null);
  const [catLabel, setCatLabel] = useState('');
  const [catItemType, setCatItemType] = useState<CategoryItemType>('clothing');
  const [selectedIconKey, setSelectedIconKey] = useState<string>('CoatHanger');
  const [iconSearch, setIconSearch] = useState('');
  const [customSvgCode, setCustomSvgCode] = useState<string>('');
  const [svgFileName, setSvgFileName] = useState<string>('');
  const [svgError, setSvgError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadCategories = () => {
    const list = wardrobeCategoryService.getCategories(userId);
    setCategories(list);
  };

  useEffect(() => {
    if (isOpen) {
      loadCategories();
    }
  }, [isOpen, userId]);

  if (!isOpen) return null;

  const handleToggleVisibility = (cat: WardrobeCategory) => {
    wardrobeCategoryService.toggleVisibility(cat.id, userId);
    loadCategories();
    onCategoryChanged?.();
    toast(cat.isVisible ? `Hidden "${cat.label}" from capsule` : `Shown "${cat.label}" in capsule`, {
      duration: 1500
    });
  };

  const handleTogglePin = (cat: WardrobeCategory) => {
    wardrobeCategoryService.togglePin(cat.id, userId);
    loadCategories();
    onCategoryChanged?.();
  };

  const handleMove = (index: number, direction: 'up' | 'down') => {
    const newIdx = direction === 'up' ? index - 1 : index + 1;
    if (newIdx < 0 || newIdx >= categories.length) return;

    const list = [...categories];
    const temp = list[index];
    list[index] = list[newIdx];
    list[newIdx] = temp;

    const orderedIds = list.map(c => c.id);
    wardrobeCategoryService.reorderCategories(orderedIds, userId);
    setCategories(list);
    onCategoryChanged?.();
  };

  const handleDelete = (cat: WardrobeCategory) => {
    if (cat.isDefault) {
      handleToggleVisibility(cat);
      return;
    }
    wardrobeCategoryService.deleteCategory(cat.id, userId);
    loadCategories();
    onCategoryChanged?.();
    toast.success(`Removed category "${cat.label}"`);
  };

  const handleResetDefaults = () => {
    if (window.confirm('Reset categories to default Yorvyn capsule navigation?')) {
      const reset = wardrobeCategoryService.resetToDefaults(userId);
      setCategories(reset);
      onCategoryChanged?.();
      toast.success('Categories reset to defaults');
    }
  };

  const handleSvgFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.svg') && file.type !== 'image/svg+xml') {
      setSvgError('Please upload a valid .svg vector file.');
      return;
    }

    setSvgFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const rawText = event.target?.result as string;
      const res = sanitizeSvgString(rawText);
      if (res.success && res.sanitizedSvg) {
        setCustomSvgCode(res.sanitizedSvg);
        setSvgError(null);
        toast.success('SVG icon verified and sanitized safely');
      } else {
        setSvgError(res.error || 'Security check failed on uploaded SVG.');
        setCustomSvgCode('');
      }
    };
    reader.readAsText(file);
  };

  const handleSaveCategory = (e: React.FormEvent) => {
    e.preventDefault();
    const label = catLabel.trim();
    if (!label) {
      toast.error('Please enter a category name');
      return;
    }

    if (editingId) {
      // Edit existing
      wardrobeCategoryService.updateCategory(
        editingId,
        {
          label,
          itemType: catItemType,
          iconType: customSvgCode ? 'custom_svg' : 'preset',
          iconKey: selectedIconKey,
          customSvg: customSvgCode || undefined
        },
        userId
      );
      toast.success(`Updated "${label}" category`);
    } else {
      // Create new
      wardrobeCategoryService.addCategory(
        {
          id: `custom_${label.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${Date.now()}`,
          label,
          itemType: catItemType,
          iconType: customSvgCode ? 'custom_svg' : 'preset',
          iconKey: selectedIconKey,
          customSvg: customSvgCode || undefined,
          isVisible: true,
          isPinned: true
        },
        userId
      );
      toast.success(`Created "${label}" category`);
    }

    // Reset Form
    setEditingId(null);
    setCatLabel('');
    setCustomSvgCode('');
    setSvgFileName('');
    setSvgError(null);
    loadCategories();
    onCategoryChanged?.();
    setActiveTab('manage');
  };

  const handleAddPreset = (preset: typeof PRESET_CATEGORY_TEMPLATES[0]) => {
    const existing = categories.find(c => c.id === preset.id || c.label.toLowerCase() === preset.label.toLowerCase());
    if (existing) {
      if (!existing.isVisible) {
        wardrobeCategoryService.toggleVisibility(existing.id, userId);
        loadCategories();
        onCategoryChanged?.();
        toast.success(`Restored "${existing.label}" to navigation capsule`);
      } else {
        toast(`"${preset.label}" is already active in your capsule`);
      }
      return;
    }

    wardrobeCategoryService.addCategory(preset, userId);
    loadCategories();
    onCategoryChanged?.();
    toast.success(`Added "${preset.label}" to categories`);
  };

  const availableIcons = Object.keys(PRESET_ICON_MAP).filter(key =>
    key.toLowerCase().includes(iconSearch.toLowerCase().trim())
  );

  const modalBody = (
    <div className={embedded ? "cat-embedded-dialog" : "cat-modal-dialog"} onClick={e => e.stopPropagation()}>
      {/* Modal Header */}
      {!embedded && (
        <header className="cat-modal-header">
          <div className="cat-modal-title-group">
            <h2 id="cat-modal-title" className="cat-modal-title">Customise Wardrobe Categories</h2>
            <p className="cat-modal-subtitle">Organise fashion garments, accessories, watches, jewellery & lifestyle items</p>
          </div>
          <button
            type="button"
            className="cat-modal-close-btn"
            onClick={onClose}
            aria-label="Close categories manager"
          >
            <X size={18} />
          </button>
        </header>
      )}

        {/* Modal Navigation Tabs */}
        <div className="cat-modal-tabs">
          <button
            type="button"
            className={`cat-modal-tab-btn ${activeTab === 'manage' ? 'active' : ''}`}
            onClick={() => setActiveTab('manage')}
          >
            Manage Capsule ({categories.length})
          </button>
          <button
            type="button"
            className={`cat-modal-tab-btn ${activeTab === 'add' ? 'active' : ''}`}
            onClick={() => {
              setEditingId(null);
              setCatLabel('');
              setCustomSvgCode('');
              setSvgFileName('');
              setActiveTab('add');
            }}
          >
            <Plus size={14} style={{ display: 'inline', marginRight: 4 }} />
            {editingId ? 'Edit Category' : 'Create Custom'}
          </button>
          <button
            type="button"
            className={`cat-modal-tab-btn ${activeTab === 'presets' ? 'active' : ''}`}
            onClick={() => setActiveTab('presets')}
          >
            <Sparkle size={14} style={{ display: 'inline', marginRight: 4 }} />
            Quick Presets
          </button>
        </div>

        {/* Tab 1: Manage Existing Categories */}
        {activeTab === 'manage' && (
          <div className="cat-manage-body">
            <div className="cat-manage-instructions">
              Reorder or hide categories in your horizontal capsule. Pinned items appear first.
            </div>

            <div className="cat-manage-list">
              {categories.map((cat, idx) => (
                <div
                  key={cat.id}
                  className={`cat-item-row ${cat.isVisible === false ? 'is-hidden' : ''}`}
                >
                  <div className="cat-row-drag-handle">
                    <DotsSixVertical size={18} />
                  </div>

                  <div className="cat-row-icon-preview">
                    <CategoryIcon category={cat} size={20} />
                  </div>

                  <div className="cat-row-info">
                    <span className="cat-row-label">{cat.label}</span>
                    <span className="cat-row-type-badge">{cat.itemType}</span>
                    {cat.isDefault && <span className="cat-row-default-badge">System</span>}
                  </div>

                  <div className="cat-row-actions">
                    {/* Move Up */}
                    <button
                      type="button"
                      className="cat-action-circle-btn"
                      onClick={() => handleMove(idx, 'up')}
                      disabled={idx === 0}
                      title="Move Up"
                      aria-label="Move Up"
                    >
                      <ArrowUp size={14} />
                    </button>

                    {/* Move Down */}
                    <button
                      type="button"
                      className="cat-action-circle-btn"
                      onClick={() => handleMove(idx, 'down')}
                      disabled={idx === categories.length - 1}
                      title="Move Down"
                      aria-label="Move Down"
                    >
                      <ArrowDown size={14} />
                    </button>

                    {/* Toggle Pin */}
                    <button
                      type="button"
                      className={`cat-action-circle-btn ${cat.isPinned ? 'active-pin' : ''}`}
                      onClick={() => handleTogglePin(cat)}
                      title={cat.isPinned ? 'Unpin' : 'Pin to Front'}
                      aria-label="Toggle Pin"
                    >
                      <PushPin size={14} weight={cat.isPinned ? 'fill' : 'regular'} />
                    </button>

                    {/* Toggle Visibility */}
                    <button
                      type="button"
                      className={`cat-action-circle-btn ${cat.isVisible === false ? 'is-off' : ''}`}
                      onClick={() => handleToggleVisibility(cat)}
                      title={cat.isVisible === false ? 'Show in Capsule' : 'Hide from Capsule'}
                      aria-label="Toggle Visibility"
                    >
                      {cat.isVisible === false ? <EyeSlash size={14} /> : <Eye size={14} />}
                    </button>

                    {/* Edit */}
                    <button
                      type="button"
                      className="cat-action-circle-btn"
                      onClick={() => {
                        setEditingId(cat.id);
                        setCatLabel(cat.label);
                        setCatItemType(cat.itemType);
                        setSelectedIconKey(cat.iconKey || 'CoatHanger');
                        setCustomSvgCode(cat.customSvg || '');
                        setActiveTab('add');
                      }}
                      title="Edit Category"
                      aria-label="Edit Category"
                    >
                      <PencilSimple size={14} />
                    </button>

                    {/* Delete */}
                    {!cat.isDefault && (
                      <button
                        type="button"
                        className="cat-action-circle-btn delete"
                        onClick={() => handleDelete(cat)}
                        title="Delete Custom Category"
                        aria-label="Delete Custom Category"
                      >
                        <Trash size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="cat-manage-footer">
              <button
                type="button"
                className="cat-reset-btn"
                onClick={handleResetDefaults}
              >
                <ArrowCounterClockwise size={14} />
                <span>Reset to Factory Defaults</span>
              </button>
            </div>
          </div>
        )}

        {/* Tab 2: Create / Edit Category Form */}
        {activeTab === 'add' && (
          <form className="cat-form-body" onSubmit={handleSaveCategory}>
            <div className="cat-form-row">
              <label htmlFor="cat-name-input" className="cat-form-label">Category Name</label>
              <input
                id="cat-name-input"
                type="text"
                className="cat-form-input"
                placeholder="e.g. Watches, Sunglasses, Rings, Perfumes..."
                value={catLabel}
                onChange={e => setCatLabel(e.target.value)}
                maxLength={24}
                required
              />
            </div>

            <div className="cat-form-row">
              <label htmlFor="cat-type-select" className="cat-form-label">Item Classification</label>
              <select
                id="cat-type-select"
                className="cat-form-select"
                value={catItemType}
                onChange={e => setCatItemType(e.target.value as CategoryItemType)}
              >
                <option value="clothing">Clothing (Shirts, Pants, Outerwear)</option>
                <option value="accessory">Accessory (Hats, Sunglasses, Belts)</option>
                <option value="footwear">Footwear (Sneakers, Shoes, Boots)</option>
                <option value="watch">Watch & Horology</option>
                <option value="jewelry">Jewellery & Precious Metals</option>
                <option value="bag">Bags & Luggage</option>
                <option value="fragrance">Fragrance & Scents</option>
                <option value="beauty">Beauty & Cosmetics</option>
                <option value="gadget">Gadget & Wearables</option>
                <option value="collectible">Art & Collectibles</option>
                <option value="custom">Other Custom Category</option>
              </select>
            </div>

            {/* Icon Picker / SVG Upload */}
            <div className="cat-form-row">
              <label className="cat-form-label">Category Icon</label>
              
              {/* Option A: Preset Icon Selector */}
              <div className="cat-icon-search-bar">
                <MagnifyingGlass size={16} />
                <input
                  type="text"
                  placeholder="Filter icon library..."
                  value={iconSearch}
                  onChange={e => setIconSearch(e.target.value)}
                  className="cat-icon-search-input"
                />
              </div>

              <div className="cat-icon-grid">
                {availableIcons.map(key => {
                  const isSelected = selectedIconKey === key && !customSvgCode;
                  return (
                    <button
                      key={key}
                      type="button"
                      className={`cat-icon-choice-btn ${isSelected ? 'selected' : ''}`}
                      onClick={() => {
                        setSelectedIconKey(key);
                        setCustomSvgCode('');
                        setSvgFileName('');
                      }}
                      title={key}
                    >
                      <CategoryIcon iconKey={key} size={22} weight={isSelected ? 'fill' : 'regular'} />
                      <span className="cat-icon-choice-label">{key}</span>
                    </button>
                  );
                })}
              </div>

              {/* Option B: Custom SVG Upload with Security Sanitization */}
              <div className="cat-custom-svg-upload-section">
                <span className="cat-upload-or-text">— OR Upload Custom Vector SVG —</span>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".svg,image/svg+xml"
                  style={{ display: 'none' }}
                  onChange={handleSvgFileUpload}
                />

                <div
                  className={`cat-svg-dropzone ${customSvgCode ? 'has-svg' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {customSvgCode ? (
                    <div className="cat-svg-preview-box">
                      <span
                        className="cat-svg-preview-icon"
                        dangerouslySetInnerHTML={{ __html: customSvgCode }}
                      />
                      <span className="cat-svg-preview-name">{svgFileName || 'Custom SVG verified'}</span>
                      <span className="cat-svg-reupload-hint">Click to replace</span>
                    </div>
                  ) : (
                    <div className="cat-svg-empty-box">
                      <UploadSimple size={24} />
                      <span>Upload clean SVG icon (max 256 KB)</span>
                      <small>Sanitized for XSS security automatically</small>
                    </div>
                  )}
                </div>

                {svgError && (
                  <div className="cat-svg-error-msg" role="alert">
                    <WarningCircle size={14} />
                    <span>{svgError}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Submit Actions */}
            <div className="cat-form-actions">
              <button
                type="button"
                className="cat-cancel-btn"
                onClick={() => setActiveTab('manage')}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="cat-save-btn"
              >
                <Check size={16} />
                <span>{editingId ? 'Save Changes' : 'Create Category'}</span>
              </button>
            </div>
          </form>
        )}

        {/* Tab 3: Quick Add Presets */}
        {activeTab === 'presets' && (
          <div className="cat-presets-body">
            <div className="cat-presets-instructions">
              Quickly add popular lifestyle and luxury categories to your wardrobe navigation with one click:
            </div>

            <div className="cat-presets-grid">
              {PRESET_CATEGORY_TEMPLATES.map(preset => {
                const isAlreadyAdded = categories.some(
                  c => c.id === preset.id || c.label.toLowerCase() === preset.label.toLowerCase()
                );
                return (
                  <div key={preset.id} className="cat-preset-card">
                    <div className="cat-preset-card-icon">
                      <CategoryIcon category={preset as WardrobeCategory} size={24} />
                    </div>
                    <div className="cat-preset-card-info">
                      <h4 className="cat-preset-card-title">{preset.label}</h4>
                      <p className="cat-preset-card-desc">{preset.description}</p>
                    </div>
                    <button
                      type="button"
                      className={`cat-preset-add-btn ${isAlreadyAdded ? 'added' : ''}`}
                      onClick={() => handleAddPreset(preset)}
                    >
                      {isAlreadyAdded ? (
                        <>
                          <Check size={14} />
                          <span>Active</span>
                        </>
                      ) : (
                        <>
                          <Plus size={14} />
                          <span>Add</span>
                        </>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
  );

  if (embedded) {
    return (
      <div className="cat-embedded-wrapper">
        {modalBody}
      </div>
    );
  }

  return (
    <div className="cat-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="cat-modal-title">
      {modalBody}
    </div>
  );
};


import React, { useState, useEffect } from 'react';
import {
  X,
  MagnifyingGlass,
  Clock,
  Sparkle,
  ArrowRight
} from '../icons';
import { aiSessionService, AISearchRecord } from '../../services/aiSessionService';
import './SearchHistoryModal.css';

interface SearchHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSearchQuery?: (query: string) => void;
}

export const SearchHistoryModal: React.FC<SearchHistoryModalProps> = ({
  isOpen,
  onClose,
  onSelectSearchQuery,
}) => {
  const [searches, setSearches] = useState<AISearchRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');

  useEffect(() => {
    if (isOpen) {
      loadSearches();
    }
  }, [isOpen, selectedType]);

  const loadSearches = async () => {
    setLoading(true);
    try {
      const typeParam = selectedType === 'all' ? undefined : selectedType;
      const res = await aiSessionService.listGlobalSearches(
        filterQuery || undefined,
        typeParam
      );
      setSearches(res.items || []);
    } catch (err) {
      console.error('Failed to load global searches', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadSearches();
  };

  if (!isOpen) return null;

  return (
    <div className="ai-search-modal-backdrop" onClick={onClose}>
      <div className="ai-search-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ai-search-modal-header">
          <div className="ai-search-modal-title">
            <Clock size={20} className="gold-icon" />
            <h3>Search History & Provenance</h3>
          </div>
          <button className="ai-search-modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Filter Toolbar */}
        <form className="ai-search-modal-filters" onSubmit={handleSearchSubmit}>
          <div className="ai-search-input-wrap">
            <MagnifyingGlass size={16} />
            <input
              type="text"
              placeholder="Search past styling queries..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
            />
            {filterQuery && (
              <button
                type="button"
                className="clear-filter-btn"
                onClick={() => {
                  setFilterQuery('');
                  loadSearches();
                }}
              >
                <X size={12} />
              </button>
            )}
          </div>

          <div className="ai-search-type-chips">
            {['all', 'outfit', 'garment', 'stylist', 'product', 'wardrobe'].map((t) => (
              <button
                key={t}
                type="button"
                className={`ai-type-chip ${selectedType === t ? 'active' : ''}`}
                onClick={() => setSelectedType(t)}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        </form>

        {/* Searches Table / List */}
        <div className="ai-search-modal-body custom-scrollbar">
          {loading ? (
            <div className="ai-search-loading">
              <Sparkle size={20} className="spin-icon" />
              <span>Retrieving search provenance...</span>
            </div>
          ) : searches.length === 0 ? (
            <div className="ai-search-empty">
              <Clock size={32} />
              <p>No recorded searches match your query</p>
            </div>
          ) : (
            <div className="ai-search-list">
              {searches.map((s) => (
                <div key={s.id} className="ai-search-item">
                  <div className="ai-search-item-header">
                    <span className={`ai-search-badge ${s.search_type}`}>
                      {s.search_type}
                    </span>
                    <span className="ai-search-timestamp">
                      {new Date(s.created_at).toLocaleString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>

                  <div className="ai-search-query">
                    "{s.query}"
                  </div>

                  {s.result_summary && (
                    <div className="ai-search-summary">
                      {s.result_summary}
                    </div>
                  )}

                  <div className="ai-search-footer">
                    <span className="ai-search-provider">
                      Provider: {s.provider || 'yorvyn_hybrid_stylist'}
                    </span>
                    {onSelectSearchQuery && (
                      <button
                        className="ai-rerun-query-btn"
                        onClick={() => {
                          onSelectSearchQuery(s.query);
                          onClose();
                        }}
                      >
                        <span>Re-query</span>
                        <ArrowRight size={13} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

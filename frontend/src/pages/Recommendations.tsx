import { useState, useEffect } from 'react'
import { Sparkles, TrendingUp, Zap, Wind, Heart, Flame, AlertTriangle, Lightbulb } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '../utils/api'
import { RecommendationResponse, Perfume } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ProductModal } from '../components/ProductModal'
import { formatMatchPercent } from '../utils/perfumeDisplay'
import './Recommendations.css'

const QUICK_SUGGESTIONS = [
  {
    icon: Wind,
    label: 'Fresh & Crisp',
    desc: 'Citrus & green notes',
    prompt: 'I want a fresh, crisp fragrance with bright citrus notes like bergamot and lemon, perfect for everyday wear.',
  },
  {
    icon: Heart,
    label: 'Sweet & Romantic',
    desc: 'Floral & vanilla',
    prompt: 'I\'m looking for a sweet, romantic fragrance with floral and vanilla notes - something elegant and feminine.',
  },
  {
    icon: Flame,
    label: 'Bold & Spicy',
    desc: 'Woody & amber',
    prompt: 'I need a bold, spicy fragrance with warm woody and amber notes. Something luxurious and sophisticated.',
  },
  {
    icon: Zap,
    label: 'Energetic & Modern',
    desc: 'Fruity & aromatic',
    prompt: 'I\'m looking for an energetic, modern fragrance with fruity and aromatic notes. Something vibrant and unique.',
  },
]

export function RecommendationsPage() {
  const [searchParams] = useSearchParams()
  const initialPref = searchParams.get('pref') || ''

  const [preferences, setPreferences] = useState(initialPref)
  const [data, setData] = useState<RecommendationResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Perfume | null>(null)

  useEffect(() => {
    if (initialPref) {
      loadRecommendations(initialPref)
    }
  }, [initialPref])

  const loadRecommendations = async (query: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await apiClient.getRecommendations(query, 12)
      setData(res)
    } catch (err: any) {
      // Provide more specific error messages
      let errorMsg = 'Unable to fetch recommendations right now.'
      
      if (!err.response) {
        errorMsg = 'Cannot connect to server. Make sure backend is running on http://localhost:8001'
      } else if (err.response?.status === 404) {
        errorMsg = 'API endpoint not found. Backend may have issues.'
      } else if (err.response?.status === 500) {
        errorMsg = 'Server error: ' + (err.response?.data?.detail || 'Internal server error')
      } else if (err.code === 'ECONNABORTED') {
        errorMsg = 'Request timeout. Server took too long to respond.'
      } else if (err.message === 'Network Error') {
        errorMsg = 'Network error. Check your internet connection and ensure backend is running.'
      } else {
        errorMsg = err.response?.data?.detail || err.message || 'Failed to get recommendations. Ensure backend is running.'
      }
      
      setError(errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuickSuggestion = (prompt: string) => {
    setPreferences(prompt)
    loadRecommendations(prompt)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!preferences.trim()) return
    loadRecommendations(preferences)
  }

  return (
    <div className="recs-page">
      <div className="recs-header">
        <div className="container">
          <h1>AI <em>Perfume Recommendation</em></h1>
          <p>Describe your perfect fragrance, and our ML engine will find the best matches from over 73,000 perfumes.</p>
        </div>
      </div>

      <div className="container">
        <div className="recs-content">
          {/* Premium Form Section */}
          <div className="recs-form-wrap">
            {/* Quick Suggestions */}
            <div className="quick-suggestions-grid">
              {QUICK_SUGGESTIONS.map((suggestion) => {
                const Icon = suggestion.icon
                return (
                  <button
                    key={suggestion.label}
                    className="quick-suggestion-btn"
                    onClick={() => handleQuickSuggestion(suggestion.prompt)}
                    disabled={isLoading}
                    title={suggestion.prompt}
                  >
                    <div className="qs-icon">
                      <Icon size={24} />
                    </div>
                    <div className="qs-content">
                      <h4>{suggestion.label}</h4>
                      <p>{suggestion.desc}</p>
                    </div>
                    <div className="qs-arrow">→</div>
                  </button>
                )
              })}
            </div>

            {/* OR Divider */}
            <div className="form-divider">
              <span>Or describe your perfect scent</span>
            </div>

            {/* Main Form */}
            <form onSubmit={handleSubmit} className="recs-form premium-form">
              <div className="form-group">
                <label htmlFor="pref">
                  <Sparkles size={18} />
                  <span>Your Fragrance Preference</span>
                </label>
                <textarea
                  id="pref"
                  value={preferences}
                  onChange={e => setPreferences(e.target.value)}
                  placeholder="Describe your ideal fragrance in detail... Example: 'Fresh citrus with subtle floral notes, suitable for summer evenings, with a hint of vanilla...'"
                  rows={5}
                  required
                  className="premium-textarea"
                />
                <div className="form-hint">
                  <Lightbulb size={14} />
                  <span>Tip: The more details you provide, the better our AI matches your preferences.</span>
                </div>
              </div>

              <button type="submit" disabled={isLoading} className="btn-rec premium-btn">
                {isLoading ? (
                  <>
                    <span className="spinner"></span>
                    Processing Your Preferences...
                  </>
                ) : (
                  <>
                    <Sparkles size={20} />
                    Find My Perfect Match
                  </>
                )}
              </button>
            </form>

            {error && (
              <div className="error-banner">
                <p><AlertTriangle size={16} /> {error}</p>
              </div>
            )}
          </div>

          {/* Results */}
          {data && data.recommendations && (
            <div className="recs-results">
              <div className="results-header">
                <h2><TrendingUp size={24} /> Top Matches</h2>
                <div className="results-meta">
                  <p className="explanation">{data.explanation}</p>
                </div>
              </div>

              <div className="yb-grid" style={{ marginTop: '32px' }}>
                {data.recommendations.map(perfume => (
                  <ProductCard
                    key={perfume.perfume_id}
                    perfume={{...perfume, id: perfume.perfume_id, price: perfume.price_usd || 0}}
                    onViewDetails={setSelected}
                    badge={`${formatMatchPercent(perfume.final_score)} Match`}
                  />
                ))}
              </div>

              {data.recommendations.length === 0 && (
                <div className="no-results">
                  <p>No matches found for your criteria. Try different keywords!</p>
                </div>
              )}
            </div>
          )}

          {/* Loading state skeleton */}
          {isLoading && (
            <div className="recs-results">
               <div className="results-header skeleton-line w40"></div>
               <div className="yb-grid" style={{ marginTop: '32px' }}>
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="skeleton-card yb-card">
                    <div className="yb-card-arch-container">
                      <div className="yb-card-arch skeleton" style={{ width: '100%', height: '300px', borderRadius: '200px 200px 0 0' }} />
                    </div>
                  </div>
                ))}
               </div>
            </div>
          )}
        </div>
      </div>

      <ProductModal perfume={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  Search,
  Sparkles,
  Star,
  Wand2,
} from 'lucide-react'
import { apiClient } from '../utils/api'
import { Category, Perfume, RecommendationResponse } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ProductModal } from '../components/ProductModal'
import { QuizModal } from '../components/QuizModal'
import { buildAccordPreview, buildAccordTags, formatMatchPercent } from '../utils/perfumeDisplay'
import { Logo } from '../components/Logo'
import './Home.css'

type RecommendationOverrides = {
  preferred_gender?: string
  occasion?: string
  season?: string
  mood?: string
  liked_notes?: string[]
  reference_perfumes?: string[]
}

type ResultMode = 'idle' | 'recommendations' | 'search'

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [premiumCollection, setPremiumCollection] = useState<Perfume[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [selected, setSelected] = useState<Perfume | null>(null)
  const [isQuizOpen, setIsQuizOpen] = useState(false)
  const [preferences, setPreferences] = useState('')
  const [preferredGender, setPreferredGender] = useState('')
  const [occasion, setOccasion] = useState('')
  const [season, setSeason] = useState('')
  const [data, setData] = useState<RecommendationResponse | null>(null)
  const [searchResults, setSearchResults] = useState<Perfume[]>([])
  const [resultMode, setResultMode] = useState<ResultMode>('idle')
  const [isLoading, setIsLoading] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)

  const resultsRef = useRef<HTMLDivElement | null>(null)
  const lastHandledSignature = useRef('')

  useEffect(() => {
    loadHomePage()
  }, [])

  useEffect(() => {
    const pref = searchParams.get('pref')?.trim() || ''
    const q = searchParams.get('q')?.trim() || ''
    const gender = searchParams.get('gender')?.trim() || ''
    const occasionParam = searchParams.get('occasion')?.trim() || ''
    const seasonParam = searchParams.get('season')?.trim() || ''
    const signature = JSON.stringify({ pref, q, gender, occasionParam, seasonParam })

    if (signature === lastHandledSignature.current) return
    lastHandledSignature.current = signature

    if (pref) {
      setPreferences(pref)
      setPreferredGender(gender)
      setOccasion(occasionParam)
      setSeason(seasonParam)
      runPreferenceSearch(
        pref,
        {
          preferred_gender: gender || undefined,
          occasion: occasionParam || undefined,
          season: seasonParam || undefined,
        },
        false,
      )
      return
    }

    if (q) {
      setPreferences(q)
      runDirectSearch(q, false)
    }
  }, [searchParams])

  const fallbackCollection: Perfume[] = [
    { id: 'fallback-1', name: 'Sauvage', brand: 'Dior', family: 'Fresh aromatic', rating: 4.7, price: 12000, description: 'Fresh, aromatic, and versatile.', image_url: null, gender: 'men', accords: 'bergamot pepper ambroxan' },
    { id: 'fallback-2', name: 'Bleu de Chanel', brand: 'Chanel', family: 'Woody aromatic', rating: 4.8, price: 14500, description: 'Clean, woody, and polished.', image_url: null, gender: 'men', accords: 'citrus incense cedar' },
    { id: 'fallback-3', name: 'Good Girl', brand: 'Carolina Herrera', family: 'Floral gourmand', rating: 4.6, price: 11000, description: 'Sweet, floral, and evening-friendly.', image_url: null, gender: 'women', accords: 'jasmine tonka cocoa' },
    { id: 'fallback-4', name: 'Baccarat Rouge 540', brand: 'Maison Francis Kurkdjian', family: 'Amber woody', rating: 4.9, price: 28000, description: 'Warm, airy, and luxurious.', image_url: null, gender: 'unisex', accords: 'saffron amber woods' },
    { id: 'fallback-5', name: 'Terre d’Hermès', brand: 'Hermès', family: 'Woody citrus', rating: 4.5, price: 13000, description: 'Earthy, citrusy, and refined.', image_url: null, gender: 'men', accords: 'orange pepper vetiver' },
    { id: 'fallback-6', name: 'Libre', brand: 'Yves Saint Laurent', family: 'Floral lavender', rating: 4.6, price: 12500, description: 'Bright, floral, and modern.', image_url: null, gender: 'women', accords: 'lavender orange blossom vanilla' },
  ]

  const loadHomePage = async () => {
    setPageError(null)

    try {
      const [catRes, popularRes] = await Promise.allSettled([
        apiClient.getCategories(),
        apiClient.getPopularPerfumes(12),
      ])

      if (catRes.status === 'fulfilled') setCategories(catRes.value.categories || [])
      if (popularRes.status === 'fulfilled') {
        const popular = popularRes.value.popular || []
        setPremiumCollection(popular.slice(0, 6))
      } else {
        setPremiumCollection(fallbackCollection.slice(0, 6))
      }
      return
    } catch {
      setPremiumCollection(fallbackCollection.slice(0, 6))
      setPageError('Showing local preview while the backend starts up.')
    }
  }

  const syncPreferenceParams = (prompt: string, overrides: RecommendationOverrides = {}) => {
    const next = new URLSearchParams()
    next.set('pref', prompt)
    const genderValue = overrides.preferred_gender ?? (preferredGender ? preferredGender.toLowerCase() : '')
    const occasionValue = overrides.occasion ?? occasion
    const seasonValue = overrides.season ?? season
    if (genderValue) next.set('gender', genderValue)
    if (occasionValue) next.set('occasion', occasionValue)
    if (seasonValue) next.set('season', seasonValue)
    lastHandledSignature.current = JSON.stringify({
      pref: prompt,
      q: '',
      gender: genderValue,
      occasionParam: occasionValue,
      seasonParam: seasonValue,
    })
    setSearchParams(next)
  }

  const syncExactSearchParams = (query: string) => {
    const next = new URLSearchParams()
    next.set('q', query)
    lastHandledSignature.current = JSON.stringify({
      pref: '',
      q: query,
      gender: '',
      occasionParam: '',
      seasonParam: '',
    })
    setSearchParams(next)
  }

  const runPreferenceSearch = async (
    prompt: string,
    overrides: RecommendationOverrides = {},
    syncUrl: boolean = true,
  ) => {
    if (!prompt.trim()) return

    if (syncUrl) {
      syncPreferenceParams(prompt, overrides)
    }

    setIsLoading(true)
    setPageError(null)

    try {
      const res = await apiClient.getRecommendations(prompt, 6, {
        preferred_gender: overrides.preferred_gender ?? (preferredGender ? preferredGender.toLowerCase() : undefined),
        occasion: overrides.occasion ?? (occasion || undefined),
        season: overrides.season ?? (season || undefined),
        mood: overrides.mood,
        liked_notes: overrides.liked_notes ?? [],
        reference_perfumes: overrides.reference_perfumes ?? [],
      })
      setData(res)
      setSearchResults([])
      setResultMode('recommendations')
      window.requestAnimationFrame(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (err: any) {
      let errorMsg = 'Unable to fetch recommendations right now.'
      if (err?.response?.data?.detail) {
        errorMsg = typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail)
      } else if (err.message === 'Network Error') {
        errorMsg = 'Backend server unreachable. Make sure backend is running on port 8001.'
      } else if (err.message) {
        errorMsg = err.message
      }
      setPageError(errorMsg)
      setData(null)
      setSearchResults([])
      setResultMode('idle')
    } finally {
      setIsLoading(false)
    }
  }

  const runDirectSearch = async (query: string, syncUrl: boolean = true) => {
    if (!query.trim()) return

    if (syncUrl) {
      syncExactSearchParams(query)
    }

    setIsLoading(true)
    setPageError(null)

    try {
      const res = await apiClient.searchPerfumes(query, 8)
      setSearchResults(res.results || [])
      setData(null)
      setResultMode('search')
      window.requestAnimationFrame(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (err: any) {
      setPageError(err?.response?.data?.detail || 'Unable to search perfumes right now.')
      setSearchResults([])
      setResultMode('search')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    runPreferenceSearch(preferences)
  }

  const handleCategoryPrompt = (category: Category) => {
    const prompt = `Find me a premium ${category.name.toLowerCase()} perfume with a refined signature and strong identity.`
    setPreferences(prompt)
    runPreferenceSearch(prompt, { liked_notes: [category.key] })
  }

  const handleQuizSubmit = (payload: {
    prompt: string
    gender: string
    scent: string
    occasion: string
  }) => {
    const noteTerms = payload.scent
      .toLowerCase()
      .replace(/&/g, ' ')
      .split(/\s+/)
      .filter(term => term.length > 2)

    setPreferences(payload.prompt)
    setPreferredGender(payload.gender)
    setOccasion(payload.occasion)
    runPreferenceSearch(payload.prompt, {
      preferred_gender: payload.gender.toLowerCase(),
      occasion: payload.occasion,
      liked_notes: noteTerms,
    })
  }

  const topResult = data?.recommendations?.[0]
  const moreResults = data?.recommendations?.slice(1) || []
  const topSearchResult = searchResults[0]
  const moreSearchResults = searchResults.slice(1)

  const quickPrompts = [
    {
      label: 'Fresh office',
      prompt: 'I want a fresh citrus perfume for office wear with clean lasting projection.',
      overrides: { occasion: 'office', liked_notes: ['fresh', 'citrus', 'clean'] },
    },
    {
      label: 'Romantic evening',
      prompt: 'Recommend a romantic perfume with rose vanilla and soft amber for date night.',
      overrides: { occasion: 'date', liked_notes: ['rose', 'vanilla', 'amber'] },
    },
    {
      label: 'Luxury oud',
      prompt: 'Find a premium woody oud fragrance with depth, elegance, and long lasting performance.',
      overrides: { occasion: 'night', liked_notes: ['oud', 'woody', 'smoky'] },
    },
  ]

  return (
    <div className="yb-home">
      <section className="yb-hero container">
        <div className="yb-hero-left">
          <div className="yb-eyebrow">
            <Sparkles size={16} />
            <Logo size="xs" />
          </div>
          <h1 className="yb-hero-title">
            FIND YOUR <span>signature</span> SCENT
          </h1>
          <p className="yb-hero-sub">
            Describe your mood, notes, or occasion and discover the best perfume matches ranked from 73,000+ fragrances.
          </p>

          <div className="yb-hero-actions">
            <button className="yb-quiz-btn" onClick={() => setIsQuizOpen(true)}>
              <Wand2 size={18} /> Start AI Scent Finder
            </button>
            <button
              className="yb-secondary-btn"
              onClick={() => document.getElementById('discover')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            >
              <Search size={18} /> Search
            </button>
          </div>
        </div>
      </section>

      <section id="discover" className="yb-discovery-shell container">
        <div className="yb-section-head">
          <div>
            <p className="yb-section-kicker">Preference Search</p>
            <h2 className="yb-section-title">Tell the AI what kind of perfume you want</h2>
          </div>
          <p className="yb-section-sub">
            Search by mood, notes, season, occasion, or a perfume reference. The results below show the perfume
            name, description, notes, and match quality in one place. You can also use the same box for exact perfume-name or brand search.
          </p>
        </div>

        <form className="yb-discovery-panel" onSubmit={handleSubmit}>
          <div className="yb-textarea-wrap">
            <Search size={20} className="yb-textarea-icon" />
            <textarea
              value={preferences}
              onChange={e => setPreferences(e.target.value)}
              placeholder="Examples: fresh citrus for summer mornings, elegant vanilla rose for date night, or something similar to Dior Homme Intense."
              rows={5}
              required
            />
          </div>

          <div className="yb-discovery-controls">
            <label>
              Gender
              <select value={preferredGender} onChange={e => setPreferredGender(e.target.value)}>
                <option value="">Any</option>
                <option value="men">Men</option>
                <option value="women">Women</option>
                <option value="unisex">Unisex</option>
              </select>
            </label>
            <label>
              Occasion
              <select value={occasion} onChange={e => setOccasion(e.target.value)}>
                <option value="">Any</option>
                <option value="office">Office</option>
                <option value="date">Date Night</option>
                <option value="daily">Daily Wear</option>
                <option value="party">Party</option>
                <option value="wedding">Wedding</option>
              </select>
            </label>
            <label>
              Season
              <select value={season} onChange={e => setSeason(e.target.value)}>
                <option value="">Any</option>
                <option value="summer">Summer</option>
                <option value="spring">Spring</option>
                <option value="winter">Winter</option>
                <option value="autumn">Autumn</option>
              </select>
            </label>
          </div>

          <div className="yb-discovery-actions">
            <button type="submit" className="yb-quiz-btn" disabled={isLoading}>
              {isLoading ? 'Ranking Perfumes...' : 'Get Recommendations'}
            </button>
            <button type="button" className="yb-secondary-btn" onClick={() => runDirectSearch(preferences)} disabled={isLoading || !preferences.trim()}>
              <Search size={18} /> Search Exact Perfume
            </button>
            <button type="button" className="yb-secondary-btn" onClick={() => setIsQuizOpen(true)}>
              <Sparkles size={18} /> Guided Quiz
            </button>
          </div>

          <div className="yb-quick-prompt-row">
            {quickPrompts.map(item => (
              <button
                key={item.label}
                type="button"
                className="yb-quick-chip"
                onClick={() => {
                  setPreferences(item.prompt)
                  runPreferenceSearch(item.prompt, item.overrides)
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </form>
      </section>

      <section ref={resultsRef} className="yb-results-shell container">
        <div className="yb-results-header">
          <div>
            <p className="yb-section-kicker">{resultMode === 'search' ? 'Exact Search Output' : 'Recommendation Output'}</p>
            <h2 className="yb-section-title">
              {resultMode === 'search' ? 'Direct perfume search results' : 'Best matches from your preference search'}
            </h2>
          </div>
          {resultMode === 'recommendations' && data && (
            <div className="yb-results-badges">
              <span className="yb-result-badge">Confidence {Math.round(data.confidence * 100)}%</span>
              <span className="yb-result-badge">{data.strategy.replace(/_/g, ' ')}</span>
              {data.fallback_used && (
                <span className="yb-result-badge">Description assist: {data.fallback_provider || 'ai'}</span>
              )}
            </div>
          )}
          {resultMode === 'search' && searchResults.length > 0 && (
            <div className="yb-results-badges">
              <span className="yb-result-badge">{searchResults.length} results</span>
              <span className="yb-result-badge">name / brand / notes search</span>
            </div>
          )}
        </div>

        {pageError && <div className="yb-error-banner">{pageError}</div>}

        {resultMode === 'idle' && !isLoading && (
          <div className="yb-empty-state">
            <p>Start with a preference prompt above and the results will appear here with name, notes, and description.</p>
          </div>
        )}

        {isLoading && (
          <div className="yb-results-loading">
            <div className="yb-skeleton yb-skeleton-large" />
            <div className="yb-skeleton-grid">
              {[...Array(3)].map((_, index) => (
                <div key={index} className="yb-skeleton yb-skeleton-card" />
              ))}
            </div>
          </div>
        )}

        {resultMode === 'recommendations' && data && topResult && !isLoading && (
          <>
            <div className="yb-ai-explainer">{data.explanation}</div>

            <article className="yb-top-result">
              <div className="yb-top-result-header">
                <span className="yb-section-kicker">Top Match</span>
                <span className="yb-top-match-score">{formatMatchPercent(topResult.final_score)} match</span>
              </div>

              <div className="yb-top-result-grid">
                <div className="yb-top-result-media">
                  {topResult.image_url ? (
                    <img src={topResult.image_url} alt={topResult.name} />
                  ) : (
                    <div className="yb-spotlight-placeholder">
                      <span>{topResult.brand.charAt(0)}</span>
                    </div>
                  )}
                </div>

                <div className="yb-top-result-copy">
                  <p className="yb-spotlight-brand">{topResult.brand}</p>
                  <h3>{topResult.name}</h3>
                  <p className="yb-result-description">
                    {topResult.description || 'A strong match with a clean balance of character, notes, and performance.'}
                  </p>
                  <div className="yb-spotlight-notes">
                    {buildAccordTags(topResult.accords, topResult.family, 6).map(note => (
                      <span key={note} className="yb-note-chip">{note}</span>
                    ))}
                  </div>
                  <div className="yb-top-result-stats">
                    <span><Star size={14} /> {topResult.rating.toFixed(1)}</span>
                    <span>ML score {formatMatchPercent(topResult.ml_score)}</span>
                    {topResult.gender && <span>{topResult.gender}</span>}
                  </div>
                  <button className="yb-quiz-btn" onClick={() => setSelected({ ...topResult, id: topResult.perfume_id })}>
                    View Full Details
                  </button>
                </div>
              </div>
            </article>

            {moreResults.length > 0 && (
              <div className="yb-result-list">
                {moreResults.map(result => (
                  <article key={result.perfume_id} className="yb-result-card">
                    <div className="yb-result-card-top">
                      <div>
                        <p className="yb-result-brand">{result.brand}</p>
                        <h3>{result.name}</h3>
                      </div>
                      <div className="yb-result-side-metrics">
                        <strong>{formatMatchPercent(result.final_score)}</strong>
                        <span>match</span>
                      </div>
                    </div>

                    <p className="yb-result-description">
                      {result.description || 'A well-ranked alternative selected from the same preference profile.'}
                    </p>

                    <div className="yb-result-note-row">
                      {buildAccordTags(result.accords, result.family, 5).map(note => (
                        <span key={note} className="yb-note-chip">{note}</span>
                      ))}
                    </div>

                    <div className="yb-result-footer">
                      <div className="yb-result-inline-stats">
                        <span>Rating {result.rating.toFixed(1)}</span>
                        <span>{buildAccordPreview(result.accords, result.family)}</span>
                      </div>
                      <button className="yb-inline-link" onClick={() => setSelected({ ...result, id: result.perfume_id })}>
                        Open perfume <ArrowRight size={16} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}

        {resultMode === 'search' && !isLoading && topSearchResult && (
          <>
            <div className="yb-ai-explainer">
              Exact search results for "{preferences}". These are direct matches from perfume names, brands, notes, and descriptions.
            </div>

            <article className="yb-top-result">
              <div className="yb-top-result-header">
                <span className="yb-section-kicker">Top Search Result</span>
                <span className="yb-top-match-score">{topSearchResult.brand}</span>
              </div>

              <div className="yb-top-result-grid">
                <div className="yb-top-result-media">
                  {topSearchResult.image_url ? (
                    <img src={topSearchResult.image_url} alt={topSearchResult.name} />
                  ) : (
                    <div className="yb-spotlight-placeholder">
                      <span>{topSearchResult.brand.charAt(0)}</span>
                    </div>
                  )}
                </div>

                <div className="yb-top-result-copy">
                  <p className="yb-spotlight-brand">{topSearchResult.brand}</p>
                  <h3>{topSearchResult.name}</h3>
                  <p className="yb-result-description">
                    {topSearchResult.description || 'A direct perfume match from the searchable local collection.'}
                  </p>
                  <div className="yb-spotlight-notes">
                    {buildAccordTags(topSearchResult.accords, topSearchResult.family, 6).map(note => (
                      <span key={note} className="yb-note-chip">{note}</span>
                    ))}
                  </div>
                  <div className="yb-top-result-stats">
                    <span><Star size={14} /> {topSearchResult.rating.toFixed(1)}</span>
                    {topSearchResult.gender && <span>{topSearchResult.gender}</span>}
                    <span>{buildAccordPreview(topSearchResult.accords, topSearchResult.family)}</span>
                  </div>
                  <button className="yb-quiz-btn" onClick={() => setSelected(topSearchResult)}>
                    View Full Details
                  </button>
                </div>
              </div>
            </article>

            {moreSearchResults.length > 0 && (
              <div className="yb-result-list">
                {moreSearchResults.map(result => (
                  <article key={result.id} className="yb-result-card">
                    <div className="yb-result-card-top">
                      <div>
                        <p className="yb-result-brand">{result.brand}</p>
                        <h3>{result.name}</h3>
                      </div>
                      <div className="yb-result-side-metrics">
                        <strong>{result.rating.toFixed(1)}</strong>
                        <span>rating</span>
                      </div>
                    </div>

                    <p className="yb-result-description">
                      {result.description || 'A direct search result from the perfume library.'}
                    </p>

                    <div className="yb-result-note-row">
                      {buildAccordTags(result.accords, result.family, 5).map(note => (
                        <span key={note} className="yb-note-chip">{note}</span>
                      ))}
                    </div>

                    <div className="yb-result-footer">
                      <div className="yb-result-inline-stats">
                        <span>{result.brand}</span>
                        {result.gender && <span>{result.gender}</span>}
                      </div>
                      <button className="yb-inline-link" onClick={() => setSelected(result)}>
                        Open perfume <ArrowRight size={16} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}

        {resultMode === 'search' && !isLoading && searchResults.length === 0 && !pageError && (
          <div className="yb-empty-state">
            <p>No direct perfume results were found. Try another name, brand, or switch to recommendation mode for preference-based matching.</p>
          </div>
        )}
      </section>

      {premiumCollection.length > 0 && (
        <section id="premium" className="yb-section container">
          <div className="yb-section-head">
            <div>
              <p className="yb-section-kicker">Premium Collection</p>
              <h2 className="yb-section-title">Top-Ranked Perfumes</h2>
            </div>
            <p className="yb-section-sub">
              Most-loved fragrances ranked by quality, ratings, and popularity across our database.
            </p>
          </div>

          <div className="yb-grid">
            {premiumCollection.map((perfume, index) => (
              <ProductCard
                key={perfume.id}
                perfume={perfume}
                onViewDetails={setSelected}
                badge={index < 3 ? 'Premium' : 'Popular'}
              />
            ))}
          </div>
        </section>
      )}

      {categories.length > 0 && (
        <section id="library" className="yb-section container yb-library-section">
          <div className="yb-section-head">
            <div>
              <p className="yb-section-kicker">Scent Library</p>
              <h2 className="yb-section-title">Start from a fragrance family</h2>
            </div>
            <p className="yb-section-sub">
              Pick a family and the recommendation engine will generate a stronger prompt for that direction.
            </p>
          </div>

          <div className="cat-grid-modern">
            {categories.slice(0, 8).map(category => (
              <button
                type="button"
                key={category.key}
                className="cat-card-modern"
                onClick={() => handleCategoryPrompt(category)}
              >
                <Search size={28} className="cat-modern-icon" />
                <span className="cat-name">{category.name}</span>
                <span className="cat-count">{category.count.toLocaleString('en-IN')} perfumes</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <ProductModal perfume={selected} onClose={() => setSelected(null)} />
      {isQuizOpen && <QuizModal onClose={() => setIsQuizOpen(false)} onSubmitPreferences={handleQuizSubmit} />}
    </div>
  )
}

/**
 * TopPicks — single "Recommended For You" carousel.
 *
 * - On load: shows top-rated perfumes from the dataset (popular fallback)
 * - As user answers quiz: swaps to ML-ranked recommendations live
 * - One section only, no "Top Picks" duplicate
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { apiClient } from '../utils/api'
import { Perfume } from '../types'
import { useApp } from '../context/AppContext'
import { PerfumeCard, PerfumeCardData } from './PerfumeCard'
import './TopPicks.css'

// ── Skeleton ──────────────────────────────────────────────────────────
function CardSkeleton() {
  return (
    <div className="tp-skeleton-card">
      <div className="tp-sk-img sk-pulse" />
      <div style={{ padding: '8px 10px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="tp-sk-line sk-pulse" style={{ width: '40%', height: 8 }} />
        <div className="tp-sk-line sk-pulse" style={{ width: '80%', height: 12 }} />
        <div className="tp-sk-line sk-pulse" style={{ width: '60%', height: 8 }} />
        <div className="tp-sk-line sk-pulse" style={{ width: '100%', height: 26, borderRadius: 8, marginTop: 4 }} />
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────
interface TopPicksProps {
  onOpenModal: (p: Perfume) => void
}

export function TopPicks({ onOpenModal: _unused }: TopPicksProps) {
  const { survey, wishSet, toggleWishlist, openModal } = useApp()

  // The single list shown — starts as popular, becomes ML-ranked
  const [cards, setCards]       = useState<PerfumeCardData[]>([])
  const [loading, setLoading]   = useState(true)
  const [isPersonalised, setIsPersonalised] = useState(false)

  const trackRef = useRef<HTMLDivElement>(null)
  const [canLeft, setCanLeft]   = useState(false)
  const [canRight, setCanRight] = useState(true)

  // ── Load popular perfumes on mount ───────────────────────────────
  // The API client holds requests until the backend is ready,
  // so the first call will simply wait and succeed — no retries needed.
  useEffect(() => {
    let cancelled = false
    const fallbackCards: PerfumeCardData[] = [
      { id: 'fallback-1', name: 'Sauvage', brand: 'Dior', family: 'Fresh aromatic', rating: 4.7, accords: 'bergamot pepper ambroxan', gender: 'men', label: 'Popular', labelVariant: 'dark' },
      { id: 'fallback-2', name: 'Bleu de Chanel', brand: 'Chanel', family: 'Woody aromatic', rating: 4.8, accords: 'citrus incense cedar', gender: 'men', label: 'Popular', labelVariant: 'dark' },
      { id: 'fallback-3', name: 'Good Girl', brand: 'Carolina Herrera', family: 'Floral gourmand', rating: 4.6, accords: 'jasmine tonka cocoa', gender: 'women', label: 'Popular', labelVariant: 'dark' },
      { id: 'fallback-4', name: 'Baccarat Rouge 540', brand: 'Maison Francis Kurkdjian', family: 'Amber woody', rating: 4.9, accords: 'saffron amber woods', gender: 'unisex', label: 'Popular', labelVariant: 'dark' },
      { id: 'fallback-5', name: 'Terre d’Hermès', brand: 'Hermès', family: 'Woody citrus', rating: 4.5, accords: 'orange pepper vetiver', gender: 'men', label: 'Popular', labelVariant: 'dark' },
      { id: 'fallback-6', name: 'Libre', brand: 'Yves Saint Laurent', family: 'Floral lavender', rating: 4.6, accords: 'lavender orange blossom vanilla', gender: 'women', label: 'Popular', labelVariant: 'dark' },
    ]

    apiClient.getPopularPerfumes(6)
      .then(res => {
        if (cancelled) return
        setCards((res.popular || []).map(p => ({
          id: p.id, name: p.name, brand: p.brand,
          family: p.family, rating: p.rating,
          accords: p.accords, image_url: p.image_url,
          gender: p.gender,
          label: 'Popular', labelVariant: 'dark' as const,
        })))
      })
      .catch(() => {
        if (cancelled) return
        setCards(fallbackCards)
      })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [])

  // ── Swap to ML recommendations as user answers quiz ───────────────
  useEffect(() => {
    const hasAny = survey.gender || survey.mood || survey.occasion || survey.season
    if (!hasAny) return

    const parts: string[] = []
    if (survey.mood)     parts.push(survey.mood)
    if (survey.occasion) parts.push(`for ${survey.occasion}`)
    if (survey.season)   parts.push(`in ${survey.season}`)
    if (survey.gender)   parts.push(survey.gender)

    setLoading(true)

    apiClient.getRecommendations(parts.join(', '), 6, {
      preferred_gender: survey.gender || undefined,
      occasion: survey.occasion || undefined,
      season: survey.season || undefined,
    })
      .then(res => {
        const recs = res.recommendations || []
        if (recs.length > 0) {
          setCards(recs.map(r => {
            // Build "why this matches" from accords vs survey mood
            const moodWords = survey.mood ? survey.mood.split(' ').slice(0, 2) : []
            const accWords  = (r.accords || '').split(' ').slice(0, 3)
            const overlap   = moodWords.filter(w => accWords.some(a => a.includes(w) || w.includes(a)))
            const whyMatch  = overlap.length > 0
              ? `Matches your ${overlap[0]} preference`
              : survey.occasion
                ? `Great for ${survey.occasion}`
                : undefined

            return {
              id: r.perfume_id, name: r.name, brand: r.brand,
              family: r.family, rating: r.rating,
              accords: r.accords, image_url: r.image_url,
              gender: r.gender,
              score: r.final_score,
              labelVariant: 'green' as const,
              whyMatch,
            }
          }))
          setIsPersonalised(true)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [survey.gender, survey.mood, survey.occasion, survey.season])

  // ── Arrow visibility ──────────────────────────────────────────────
  const updateArrows = useCallback(() => {
    const el = trackRef.current
    if (!el) return
    setCanLeft(el.scrollLeft > 8)
    setCanRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 8)
  }, [])

  useEffect(() => {
    const el = trackRef.current
    if (!el) return
    el.addEventListener('scroll', updateArrows, { passive: true })
    const t = setTimeout(updateArrows, 120)
    return () => { el.removeEventListener('scroll', updateArrows); clearTimeout(t) }
  }, [cards, updateArrows])

  const scroll = (dir: 'left' | 'right') => {
    const el = trackRef.current
    if (!el) return
    el.scrollBy({ left: dir === 'right' ? el.clientWidth * 0.72 : -el.clientWidth * 0.72, behavior: 'smooth' })
  }

  // ── Open modal ────────────────────────────────────────────────────
  const handleOpen = useCallback((id: string) => {
    const found = cards.find(c => c.id === id)
    if (!found) return
    openModal({
      id: found.id, name: found.name, brand: found.brand,
      family: found.family ?? '', rating: found.rating, price: 0,
      accords: found.accords, image_url: found.image_url, gender: found.gender,
    })
  }, [cards, openModal])

  // ── Wishlist ──────────────────────────────────────────────────────
  const handleWishlist = useCallback((card: PerfumeCardData) => {
    const item = {
      id: card.id, name: card.name, brand: card.brand,
      accords: card.accords, rating: card.rating,
      image_url: card.image_url, savedAt: Date.now(),
    }
    toggleWishlist(item)
  }, [toggleWishlist])

  // Subtitle changes based on whether we have personalised results
  const subtitle = isPersonalised
    ? 'Matched to your preferences'
    : 'Top-rated fragrances from our dataset'

  return (
    <div className="tp-root">
      <div className="tp-section">

        {/* Header */}
        <div className="tp-section-head">
          <div className="tp-section-left">
            <span className="tp-section-icon">
              <Sparkles size={14} />
            </span>
            <div>
              <h2 className="tp-section-title">Trending right now</h2>
              <AnimatePresence mode="wait">
                <motion.p
                  key={subtitle}
                  className="tp-section-sub"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.2 }}
                >
                  {subtitle}
                </motion.p>
              </AnimatePresence>
            </div>
          </div>

          <div className="tp-section-right">
            <button className="tp-view-all-btn">
              View all →
            </button>
            <div className="tp-arrows">
              <button
                className={`tp-arrow ${!canLeft ? 'tp-arrow-off' : ''}`}
                onClick={() => scroll('left')}
                disabled={!canLeft}
                aria-label="Scroll left"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                className={`tp-arrow ${!canRight ? 'tp-arrow-off' : ''}`}
                onClick={() => scroll('right')}
                disabled={!canRight}
                aria-label="Scroll right"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* Track */}
        <div className="tp-track" ref={trackRef}>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)
            : cards.map((card, i) => (
                <div key={card.id} className="tp-track-item">
                  <PerfumeCard
                    card={card}
                    rank={isPersonalised ? i + 1 : undefined}
                    wishlisted={wishSet.has(card.id)}
                    onOpen={() => handleOpen(card.id)}
                    onWishlist={() => handleWishlist(card)}
                    delay={i * 0.05}
                  />
                </div>
              ))
          }
        </div>

      </div>
    </div>
  )
}

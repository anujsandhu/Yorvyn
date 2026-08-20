/**
 * PerfumeCard — shared card for carousel + chatbot results.
 *
 * ── Image isolation rules ──────────────────────────────────────────
 * 1. Card image state is SEALED at mount. It never re-reads the cache
 *    after the initial load decision is made.
 * 2. Modal image state is COMPLETELY SEPARATE — modal writes to cache
 *    but that write NEVER triggers a card re-render or state change.
 * 3. IntersectionObserver — fetch only starts when card enters viewport.
 * 4. State machine: idle → skeleton → loaded | failed
 *    - idle:     card not yet visible (no fetch, no render)
 *    - skeleton: card visible, fetch in progress (shimmer shown)
 *    - loaded:   image ready, fade-in transition
 *    - failed:   all attempts exhausted, gradient placeholder shown
 *
 * ── Why this prevents the "sudden appearance" bug ─────────────────
 * The old code had `useEffect([card.id])` which re-ran whenever the
 * parent re-rendered. If the modal had written a URL to localStorage
 * between renders, the card would pick it up. Now the effect runs
 * exactly once (on intersection) and never again for that card.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { Star, Heart, ChevronRight } from 'lucide-react'
import { motion } from 'framer-motion'
import { buildAccordTags, formatMatchPercent } from '../utils/perfumeDisplay'
import { apiClient } from '../utils/api'
import { getCachedImage, setCachedImage } from '../utils/imageCache'

export interface PerfumeCardData {
  id: string
  name: string
  brand: string
  family?: string
  rating: number
  accords?: string
  image_url?: string | null
  gender?: string
  score?: number
  label?: string
  labelVariant?: 'dark' | 'green' | 'amber'
  whyMatch?: string
}

interface PerfumeCardProps {
  card: PerfumeCardData
  rank?: number
  wishlisted: boolean
  onOpen: () => void
  onWishlist: () => void
  delay?: number
  badge?: string
}

// ── Image state machine ───────────────────────────────────────────────
type ImgPhase = 'idle' | 'skeleton' | 'loaded' | 'failed'

/**
 * useCardImage — completely isolated image lifecycle.
 *
 * - Starts in 'idle' (no fetch, no render)
 * - Transitions to 'skeleton' only when the card enters the viewport
 * - Reads cache ONCE at that moment — never again
 * - Modal writes to cache but this hook ignores those writes
 *   because it only reads cache during the initial intersection callback
 */
function useCardImage(card: PerfumeCardData) {
  const [phase, setPhase]   = useState<ImgPhase>('idle')
  const [imgUrl, setImgUrl] = useState<string | null>(null)
  const containerRef        = useRef<HTMLDivElement>(null)
  const startedRef          = useRef(false)   // ensures fetch runs exactly once
  const deadRef             = useRef(false)   // true after unmount

  // Sealed fetch — runs exactly once when card enters viewport
  const startFetch = useCallback(() => {
    if (startedRef.current || deadRef.current) return
    startedRef.current = true
    setPhase('skeleton')

    const { name, brand, image_url } = card

    // ── Read cache ONCE (sealed — never re-read) ──────────────────
    const cached = getCachedImage(brand, name)

    if (cached !== undefined) {
      // Cache hit (url or known-null)
      if (cached) {
        setImgUrl(cached)
        // phase stays 'skeleton' — <img> onLoad will set 'loaded'
      } else {
        // Known miss from a previous session — show placeholder immediately
        setPhase('failed')
      }
      return
    }

    // ── Try dataset URL ───────────────────────────────────────────
    if (image_url && image_url.length > 10) {
      setImgUrl(image_url)
      // phase stays 'skeleton' — <img> onLoad/onError resolves
      return
    }

    // ── Fetch from API ────────────────────────────────────────────
    apiClient.getPerfumeImage(name, brand)
      .then(res => {
        if (deadRef.current) return
        const url = res.image_url && res.image_url.length > 10 ? res.image_url : null
        // Write to cache so future renders (and modal) can use it
        setCachedImage(brand, name, url)
        if (url) {
          setImgUrl(url)
        } else {
          setPhase('failed')
        }
      })
      .catch(() => {
        if (!deadRef.current) setPhase('failed')
      })
  }, [card.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // IntersectionObserver — trigger fetch when card enters viewport
  useEffect(() => {
    deadRef.current = false
    const el = containerRef.current
    if (!el) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          startFetch()
          observer.disconnect()
        }
      },
      { rootMargin: '120px', threshold: 0 }  // start 120px before visible
    )
    observer.observe(el)

    return () => {
      observer.disconnect()
      deadRef.current = true
    }
  }, [card.id, startFetch])

  // <img> event handlers
  const handleLoad = useCallback(() => {
    if (!deadRef.current) {
      // Confirm the URL works — update cache with verified URL
      if (imgUrl) setCachedImage(card.brand, card.name, imgUrl)
      setPhase('loaded')
    }
  }, [imgUrl, card.brand, card.name])

  const handleError = useCallback(() => {
    if (deadRef.current) return

    // Dataset URL failed — try API as one-time fallback
    if (imgUrl === card.image_url && card.image_url) {
      apiClient.getPerfumeImage(card.name, card.brand)
        .then(res => {
          if (deadRef.current) return
          const url = res.image_url && res.image_url.length > 10 ? res.image_url : null
          setCachedImage(card.brand, card.name, url)
          if (url && url !== card.image_url) {
            setImgUrl(url)
            // phase stays 'skeleton' — new img onLoad resolves
          } else {
            setPhase('failed')
          }
        })
        .catch(() => { if (!deadRef.current) setPhase('failed') })
    } else {
      setCachedImage(card.brand, card.name, null)
      setPhase('failed')
    }
  }, [imgUrl, card.image_url, card.name, card.brand])

  return { containerRef, phase, imgUrl, handleLoad, handleError }
}

// ── Component ─────────────────────────────────────────────────────────
export function PerfumeCard({ card, rank, wishlisted, onOpen, onWishlist, delay = 0, badge: _badge }: PerfumeCardProps) {
  const { containerRef, phase, imgUrl, handleLoad, handleError } = useCardImage(card)
  const tags  = buildAccordTags(card.accords, card.family, 3)
  const score = formatMatchPercent(card.score)

  const labelBg: Record<string, string> = {
    dark:  'var(--text)',
    green: '#166534',
    amber: '#92400e',
  }
  const variant = card.labelVariant ?? 'dark'

  return (
    <motion.div
      className="rv-ccard"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -2, transition: { duration: 0.14 } }}
    >
      {/* ── Wishlist button — on the card, above everything ── */}
      <button
        className={`rv-ccard-wish ${wishlisted ? 'active' : ''}`}
        onClick={e => { e.stopPropagation(); onWishlist() }}
        aria-label={wishlisted ? 'Remove from wishlist' : 'Save'}
      >
        <Heart size={12} fill={wishlisted ? 'currentColor' : 'none'} />
      </button>

      {/* ── Image area ── */}
      <div className="rv-ccard-img-wrap">
        <div className="rv-ccard-img" ref={containerRef} onClick={onOpen}>

          {phase === 'idle' && (
            <div className="rv-ccard-img-idle" aria-hidden="true" />
          )}

          {phase === 'skeleton' && (
            <div className="rv-ccard-img-skeleton sk-pulse" aria-hidden="true" />
          )}

          {imgUrl && (phase === 'skeleton' || phase === 'loaded') && (
            <img
              src={imgUrl}
              alt={card.name}
              loading="lazy"
              className={`rv-ccard-img-el ${phase === 'loaded' ? 'rv-ccard-img-visible' : ''}`}
              onLoad={handleLoad}
              onError={handleError}
            />
          )}

          {phase === 'failed' && (
            <div className="rv-ccard-ph" aria-label={card.brand}>
              <span>{(card.brand || 'A').charAt(0).toUpperCase()}</span>
            </div>
          )}

          {rank != null && rank <= 3 && (
            <div className="rv-ccard-rank">#{rank}</div>
          )}

          {score ? (
            <div className="rv-ccard-score">{score}</div>
          ) : card.label ? (
            <div className="rv-ccard-score" style={{ background: labelBg[variant], color: '#fff' }}>
              {card.label}
            </div>
          ) : null}
        </div>
      </div>

      {/* ── Card body ── */}
      <div className="rv-ccard-info">
        <p className="rv-ccard-brand">{card.brand}</p>
        <h4 className="rv-ccard-name" onClick={onOpen}>{card.name}</h4>

        {tags.length > 0 && (
          <div className="rv-ccard-tags">
            {tags.map(t => <span key={t} className="rv-ctag">{t}</span>)}
          </div>
        )}

        {card.whyMatch && (
          <p className="rv-ccard-why">{card.whyMatch}</p>
        )}

        <div className="rv-ccard-foot">
          <span className="rv-ccard-rating">
            <Star size={9} fill="currentColor" />
            {card.rating.toFixed(1)}
          </span>
          <button className="rv-ccard-view" onClick={onOpen}>
            View <ChevronRight size={10} />
          </button>
        </div>
      </div>
    </motion.div>
  )
}

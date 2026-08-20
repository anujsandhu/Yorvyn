import { useEffect, useState } from 'react'
import { X, Star, Heart, ExternalLink, ShoppingBag, Info, TrendingUp } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Perfume, ShoppingInfo } from '../types'
import { apiClient } from '../utils/api'
import { buildAccordTags, buildPriceFromApi, buildClientPrice, ClientPriceInfo } from '../utils/perfumeDisplay'
import { getCachedImage } from '../utils/imageCache'
import { useApp } from '../context/AppContext'
import './ProductModal.css'

interface Props {
  perfume: Perfume | null
  onClose: () => void
}

const SHOP_CONFIG: Record<string, { bg: string; fg: string; label: string }> = {
  Amazon:   { bg: '#FF9900', fg: '#111', label: 'Amazon' },
  Flipkart: { bg: '#2874F0', fg: '#fff', label: 'Flipkart' },
  Nykaa:    { bg: '#FC2779', fg: '#fff', label: 'Nykaa' },
  Myntra:   { bg: '#FF3F6C', fg: '#fff', label: 'Myntra' },
}

// ── Price display component ───────────────────────────────────────────
function PriceBlock({ info, loading }: { info: ClientPriceInfo | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="pm-price-loading">
        <div className="pm-price-skeleton sk-pulse" style={{ width: 140, height: 32 }} />
        <div className="pm-price-skeleton sk-pulse" style={{ width: 200, height: 14, marginTop: 6 }} />
      </div>
    )
  }
  if (!info) return null

  return (
    <div className="pm-price-block">
      <div className="pm-price-main">
        <span className="pm-price-value">{info.display}</span>
        {info.isRange && (
          <span className="pm-price-range-label">price range</span>
        )}
      </div>
      <div className="pm-price-meta">
        {info.source === 'dataset_usd' ? (
          <span className="pm-price-source pm-price-source--real">
            <TrendingUp size={10} />
            Live price · {info.note}
          </span>
        ) : (
          <span className="pm-price-source pm-price-source--est">
            <Info size={10} />
            {info.note}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Main modal ────────────────────────────────────────────────────────
export function ProductModal({ perfume, onClose }: Props) {
  const { wishSet, toggleWishlist } = useApp()
  const [imgUrl, setImgUrl]         = useState<string | null>(perfume?.image_url || null)
  const [imgLoading, setImgLoading] = useState(true)
  const [imgFailed, setImgFailed]   = useState(false)

  const [priceInfo, setPriceInfo]   = useState<ClientPriceInfo | null>(null)
  const [priceLoading, setPriceLoading] = useState(true)
  const [shopLinks, setShopLinks]   = useState<ShoppingInfo['links']>([])

  const [description, setDescription] = useState(perfume?.description || '')
  const wishlisted = perfume ? wishSet.has(perfume.id) : false

  useEffect(() => {
    if (!perfume) return

    // ── Reset state ──────────────────────────────────────────────
    setImgLoading(true)
    setImgFailed(false)
    setPriceLoading(true)
    setDescription(perfume.description || '')

    // Show client-side estimate immediately (no loading flash)
    const clientPrice = buildClientPrice(perfume.name, perfume.brand, perfume.price ?? 0)
    setPriceInfo(clientPrice)
    setPriceLoading(false)

    // ── Image ────────────────────────────────────────────────────
    const cached = getCachedImage(perfume.brand, perfume.name)
    if (cached !== undefined) {
      setImgUrl(cached || (perfume.image_url?.length ?? 0) > 10 ? (cached || perfume.image_url!) : null)
      if (!cached && (!perfume.image_url || perfume.image_url.length <= 10)) setImgFailed(true)
      setImgLoading(false)
    } else {
      apiClient.getPerfumeImage(perfume.name, perfume.brand)
        .then(res => {
          const url = res.image_url && res.image_url.length > 10 ? res.image_url : null
          setImgUrl(url || (perfume.image_url?.length ?? 0) > 10 ? (url || perfume.image_url!) : null)
          if (!url && (!perfume.image_url || perfume.image_url.length <= 10)) setImgFailed(true)
        })
        .catch(() => {
          if ((perfume.image_url?.length ?? 0) > 10) setImgUrl(perfume.image_url!)
          else setImgFailed(true)
        })
        .finally(() => setImgLoading(false))
    }

    // ── Accurate price from API ──────────────────────────────────
    apiClient.getShoppingLinks(perfume.name, perfume.brand, perfume.price ?? 0)
      .then(res => {
        const accurate = buildPriceFromApi(res, perfume.name, perfume.brand, perfume.price ?? 0)
        setPriceInfo(accurate)
        setShopLinks(res.links || [])
      })
      .catch(() => {
        // Keep client-side estimate
      })

    // ── Description ──────────────────────────────────────────────
    if (!perfume.description || perfume.description.trim().length < 24) {
      apiClient.enhancePerfumeDescription(perfume.id, perfume.description || '')
        .then(res => { if (res.enhanced_description) setDescription(res.enhanced_description) })
        .catch(() => {})
    }
  }, [perfume?.id])

  const handleWishlist = () => {
    if (!perfume) return
    toggleWishlist({
      id: perfume.id, name: perfume.name, brand: perfume.brand,
      accords: perfume.accords, rating: perfume.rating,
      image_url: imgUrl, savedAt: Date.now(),
    })
  }

  const tags   = buildAccordTags(perfume?.accords, perfume?.family, 8)
  const rating = perfume?.rating ?? 4.0

  if (!perfume) return null

  return (
    <motion.div
      className="pm-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      onClick={onClose}
    >
      <motion.div
        className="pm-panel"
        initial={{ opacity: 0, y: 28, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 28, scale: 0.96 }}
        transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
        onClick={e => e.stopPropagation()}
      >
        {/* Close */}
        <button className="pm-close" onClick={onClose} aria-label="Close modal">
          <X size={15} />
        </button>

        <div className="pm-grid">

          {/* ── LEFT: image ── */}
          <div className="pm-img-col">
            <AnimatePresence mode="wait">
              {imgLoading ? (
                <motion.div key="skel" className="pm-img-skeleton sk-pulse"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
              ) : imgUrl && !imgFailed ? (
                <motion.img
                  key="img"
                  src={imgUrl}
                  alt={perfume.name}
                  className="pm-img"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3 }}
                  onError={() => { setImgFailed(true); setImgUrl(null) }}
                />
              ) : (
                <motion.div key="ph" className="pm-img-placeholder"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <span>{(perfume.brand || 'A').charAt(0).toUpperCase()}</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* ── RIGHT: info ── */}
          <div className="pm-info-col">
            <div className="pm-info-scroll">

              {/* Brand + name */}
              <p className="pm-brand">{perfume.brand}</p>
              <h2 className="pm-name">{perfume.name}</h2>

              {/* Meta row */}
              <div className="pm-meta-row">
                <span className="pm-rating">
                  <Star size={12} fill="currentColor" />
                  {rating.toFixed(1)}
                </span>
                {perfume.gender && (
                  <span className="pm-gender-chip">
                    {perfume.gender === 'women' ? '♀ Women'
                      : perfume.gender === 'men' ? '♂ Men'
                      : '⊕ Unisex'}
                  </span>
                )}
                <button
                  className={`pm-wish-btn ${wishlisted ? 'pm-wish-active' : ''}`}
                  onClick={handleWishlist}
                  aria-label={wishlisted ? 'Remove from wishlist' : 'Save to wishlist'}
                >
                  <Heart size={12} fill={wishlisted ? 'currentColor' : 'none'} />
                  {wishlisted ? 'Saved' : 'Save'}
                </button>
              </div>

              {/* Notes */}
              {tags.length > 0 && (
                <div className="pm-section">
                  <p className="pm-section-label">Notes & Accords</p>
                  <div className="pm-tags">
                    {tags.map(t => <span key={t} className="pm-tag">{t}</span>)}
                  </div>
                </div>
              )}

              {/* Description */}
              {description && description.length > 5 && (
                <div className="pm-section">
                  <p className="pm-section-label">The Experience</p>
                  <p className="pm-desc">{description}</p>
                </div>
              )}

              {/* Price */}
              <div className="pm-section">
                <p className="pm-section-label">
                  <ShoppingBag size={10} />
                  Price in India
                </p>
                <PriceBlock info={priceInfo} loading={priceLoading} />
              </div>

              {/* Buy buttons */}
              {shopLinks.length > 0 && (
                <div className="pm-section">
                  <p className="pm-section-label">Buy now</p>
                  <div className="pm-shop-grid">
                    {shopLinks.map((link: any) => {
                      const cfg = SHOP_CONFIG[link.platform] ?? { bg: '#555', fg: '#fff', label: link.platform }
                      return (
                        <a
                          key={link.platform}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="pm-shop-btn"
                          style={{ background: cfg.bg, color: cfg.fg }}
                          aria-label={`Buy on ${cfg.label}`}
                        >
                          {cfg.label}
                          <ExternalLink size={10} />
                        </a>
                      )
                    })}
                  </div>
                </div>
              )}

            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

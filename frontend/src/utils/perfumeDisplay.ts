/**
 * perfumeDisplay.ts — display helpers for perfume data.
 *
 * Pricing:
 * - Real USD prices (eBay dataset) are converted server-side with live FX.
 * - Brand-tier prices are realistic Indian market ranges.
 * - No fake discounts. No made-up numbers.
 */

// ── Brand tier table (client-side fallback only) ──────────────────────
// Used only when the API hasn't responded yet (instant first render).
// Server has the authoritative version with 200+ brands.
const BRAND_TIERS: Record<string, [number, number]> = {
  // Ultra-luxury
  creed: [25000, 80000], "tom ford": [15000, 55000],
  "maison margiela": [12000, 45000], byredo: [14000, 40000],
  diptyque: [10000, 30000], "jo malone": [8000, 25000],
  "parfums de marly": [14000, 45000], amouage: [18000, 60000],
  "roja parfums": [25000, 90000], "frederic malle": [18000, 55000],
  "maison francis kurkdjian": [15000, 50000], mfk: [15000, 50000],
  xerjoff: [20000, 70000], initio: [16000, 50000],
  nishane: [12000, 40000], "le labo": [10000, 35000],
  // Premium designer
  chanel: [8000, 22000], dior: [6000, 18000],
  "christian dior": [6000, 18000], "yves saint laurent": [5000, 15000],
  ysl: [5000, 15000], givenchy: [5000, 14000],
  guerlain: [6000, 20000], hermes: [8000, 25000],
  cartier: [6000, 18000], bvlgari: [5000, 15000],
  versace: [4000, 12000], prada: [6000, 18000],
  valentino: [5000, 15000], burberry: [4000, 12000],
  gucci: [5000, 15000], "dolce & gabbana": [4000, 12000],
  armani: [4000, 12000], "giorgio armani": [4000, 12000],
  "hugo boss": [3000, 9000], boss: [3000, 9000],
  "mont blanc": [3000, 9000], montblanc: [3000, 9000],
  "calvin klein": [2500, 8000], "ralph lauren": [3000, 9000],
  "michael kors": [3500, 10000], "jimmy choo": [4000, 12000],
  "jean paul gaultier": [4000, 12000], mugler: [4000, 12000],
  "issey miyake": [4000, 12000], lacoste: [3000, 9000],
  davidoff: [2500, 8000], azzaro: [3000, 9000],
  "carolina herrera": [4000, 12000], "narciso rodriguez": [5000, 15000],
  // Arabic / Oud
  lattafa: [1500, 6000], rasasi: [2000, 8000],
  ajmal: [1500, 8000], "al haramain": [2000, 10000],
  "swiss arabian": [2000, 10000], armaf: [1500, 6000],
  "maison alhambra": [1500, 6000], afnan: [1500, 6000],
  // Budget
  "elizabeth arden": [1500, 5000], adidas: [800, 2500],
  fogg: [200, 800], engage: [200, 800], denver: [300, 1200],
  wildstone: [200, 800], "park avenue": [300, 1200],
}

function _brandTier(brand: string): [number, number] {
  const key = brand.toLowerCase().trim()
  if (BRAND_TIERS[key]) return BRAND_TIERS[key]
  for (const [b, range] of Object.entries(BRAND_TIERS)) {
    if (key.includes(b) || b.includes(key)) return range
  }
  return [1200, 5000] // default standard
}

// ── Price formatting ──────────────────────────────────────────────────

export interface ClientPriceInfo {
  display: string          // "₹8,000 – ₹22,000" or "₹7,140"
  min: number
  max: number
  source: 'dataset_usd' | 'brand_tier' | 'local'
  note: string             // "Converted from $84.99 · Rate: ₹84.2" or "Estimated market price"
  isRange: boolean
}

/**
 * Build price info from the API response (ShoppingInfo).
 * Falls back to client-side brand tier if API hasn't responded.
 */
export function buildPriceFromApi(
  apiData: {
    price_inr_min?: number
    price_inr_max?: number
    price_display?: string
    price_source?: string
    usd_original?: number
    fx_rate?: number
    original_price_inr?: string
    discounted_price_inr?: string
  } | null,
  name: string,
  brand: string,
  datasetPriceUsd: number = 0,
): ClientPriceInfo {
  // Use new accurate fields if available
  if (apiData?.price_inr_min && apiData.price_inr_max) {
    const isRange = apiData.price_inr_min !== apiData.price_inr_max
    let note = ''
    if (apiData.price_source === 'dataset_usd' && apiData.usd_original && apiData.fx_rate) {
      note = `Converted from $${apiData.usd_original.toFixed(2)} · Rate: ₹${apiData.fx_rate.toFixed(1)}/USD`
    } else {
      note = 'Estimated Indian market price'
    }
    return {
      display: apiData.price_display ?? `₹${apiData.price_inr_min.toLocaleString('en-IN')}`,
      min: apiData.price_inr_min,
      max: apiData.price_inr_max,
      source: (apiData.price_source as ClientPriceInfo['source']) ?? 'brand_tier',
      note,
      isRange,
    }
  }

  // Client-side fallback
  return buildClientPrice(name, brand, datasetPriceUsd)
}

/**
 * Client-side price estimate — used before API responds.
 * Uses a fixed rate of 84 INR/USD for dataset prices,
 * or brand tier for no-price perfumes.
 */
export function buildClientPrice(
  _name: string,
  brand: string,
  datasetPriceUsd: number = 0,
): ClientPriceInfo {
  if (datasetPriceUsd > 0) {
    const FALLBACK_RATE = 84
    const inr = Math.round(datasetPriceUsd * FALLBACK_RATE * 1.18) // +18% tax
    return {
      display: `₹${inr.toLocaleString('en-IN')}`,
      min: inr, max: inr,
      source: 'dataset_usd',
      note: `Approx. from $${datasetPriceUsd.toFixed(2)} · Rate: ₹${FALLBACK_RATE}/USD`,
      isRange: false,
    }
  }

  const [lo, hi] = _brandTier(brand)
  return {
    display: `₹${lo.toLocaleString('en-IN')} – ₹${hi.toLocaleString('en-IN')}`,
    min: lo, max: hi,
    source: 'brand_tier',
    note: 'Estimated Indian market price',
    isRange: true,
  }
}

// ── Accord helpers ────────────────────────────────────────────────────

export function buildAccordPreview(accords?: string, family?: string): string {
  const raw = (accords || family || '').trim()
  if (!raw) return 'A beautiful signature scent for your collection.'
  const parts = raw.split(/[,\s]+/).map(p => p.trim()).filter(Boolean).slice(0, 4)
  return parts.length ? parts.join(', ') : 'A beautiful signature scent for your collection.'
}

export function buildAccordTags(accords?: string, family?: string, limit = 6): string[] {
  const raw = (accords || family || '').trim()
  if (!raw) return []
  const seen = new Set<string>()
  return raw
    .split(/[,\s]+/)
    .map(p => p.trim())
    .filter(Boolean)
    .filter(p => {
      const k = p.toLowerCase()
      if (seen.has(k) || k.length < 3) return false
      seen.add(k)
      return true
    })
    .slice(0, limit)
}

export function formatMatchPercent(score?: number | null): string {
  if (typeof score !== 'number' || !Number.isFinite(score)) return ''
  const normalized = score > 1 ? score / 100 : score
  const percent = Math.round(Math.max(0, Math.min(0.99, normalized)) * 100)
  return `${percent}%`
}

// Legacy export — kept for any remaining callers
export interface LocalPriceInfo {
  originalPriceInr: string
  discountedPriceInr: string
}
export function buildLocalPriceInfo(_name: string, brand: string, price = 0): LocalPriceInfo {
  const info = buildClientPrice(_name, brand, price)
  return {
    originalPriceInr: info.display,
    discountedPriceInr: info.display,
  }
}

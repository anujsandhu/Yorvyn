/**
 * Client-side image URL cache backed by localStorage.
 * Keeps image URLs across page reloads so repeat searches are instant.
 *
 * Key  : md5-like hash of "brand|name" (lowercased)
 * Value: { url: string | null, ts: number }
 * TTL  : 24 hours
 */

const LS_KEY = 'pf_img_cache'
const TTL_MS = 24 * 60 * 60 * 1000   // 24 hours
const MAX_ENTRIES = 500

interface CacheEntry { url: string | null; ts: number }
type CacheMap = Record<string, CacheEntry>

// Simple non-crypto hash — fast, good enough for cache keys
function hashKey(brand: string, name: string): string {
  const raw = `${brand.toLowerCase().trim()}|${name.toLowerCase().trim()}`
  let h = 0
  for (let i = 0; i < raw.length; i++) {
    h = (Math.imul(31, h) + raw.charCodeAt(i)) | 0
  }
  return (h >>> 0).toString(36)
}

function readCache(): CacheMap {
  try {
    const raw = localStorage.getItem(LS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function writeCache(map: CacheMap) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(map))
  } catch {
    // Storage full — clear and retry
    try { localStorage.removeItem(LS_KEY) } catch {}
  }
}

function evict(map: CacheMap): CacheMap {
  const now = Date.now()
  // Remove expired
  const fresh = Object.fromEntries(
    Object.entries(map).filter(([, v]) => now - v.ts < TTL_MS)
  )
  // If still too large, remove oldest 20%
  const keys = Object.keys(fresh)
  if (keys.length > MAX_ENTRIES) {
    const sorted = keys.sort((a, b) => fresh[a].ts - fresh[b].ts)
    sorted.slice(0, Math.floor(keys.length * 0.2)).forEach(k => delete fresh[k])
  }
  return fresh
}

export function getCachedImage(brand: string, name: string): string | null | undefined {
  const key = hashKey(brand, name)
  const map = readCache()
  const entry = map[key]
  if (!entry) return undefined                    // not in cache
  if (Date.now() - entry.ts > TTL_MS) return undefined  // expired
  return entry.url                                // null = known miss
}

export function setCachedImage(brand: string, name: string, url: string | null) {
  const key = hashKey(brand, name)
  let map = readCache()
  map[key] = { url, ts: Date.now() }
  map = evict(map)
  writeCache(map)
}

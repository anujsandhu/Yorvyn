/**
 * Lightweight localStorage-backed store for:
 *  - wishlist (saved perfumes)
 *  - recent searches
 *  - saved preferences (survey answers)
 *  - saved recommendation sessions
 *
 * SECURITY: All keys are scoped per-user (uid) to prevent cross-user data leakage.
 * Never use the unscoped helpers directly — always pass a uid.
 */

export interface WishlistItem {
  id: string
  name: string
  brand: string
  accords?: string
  rating: number
  image_url?: string | null
  savedAt: number
}

export interface RecentSearch {
  id: string
  query: string
  label: string          // human-readable summary
  survey: Record<string, string>
  ts: number
}

export interface SavedPreference {
  id: string
  label: string
  survey: Record<string, string>
  ts: number
}

// ── helpers ──────────────────────────────────────────────────────────
function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write<T>(key: string, value: T) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch {}
}

function remove(key: string) {
  try { localStorage.removeItem(key) } catch {}
}

// ── User-scoped key builders ──────────────────────────────────────────
// Keys include the uid so User A's data never bleeds into User B's session.
function keys(uid: string) {
  return {
    wishlist:   `pf_wishlist_${uid}`,
    recents:    `pf_recents_${uid}`,
    savedPrefs: `pf_saved_prefs_${uid}`,
  }
}

// ── Legacy unscoped keys (kept only for migration, never written) ─────
const LEGACY_KEYS = {
  wishlist:   'pf_wishlist',
  recents:    'pf_recents',
  savedPrefs: 'pf_saved_prefs',
}

/**
 * Clear all legacy unscoped localStorage keys.
 * Call once on app startup to remove any pre-isolation data.
 */
export function clearLegacyStorage() {
  remove(LEGACY_KEYS.wishlist)
  remove(LEGACY_KEYS.recents)
  remove(LEGACY_KEYS.savedPrefs)
}

/**
 * Clear ALL data for a specific user from localStorage.
 * Must be called on logout to prevent the next user from seeing stale data.
 */
export function clearUserStorage(uid: string) {
  const k = keys(uid)
  remove(k.wishlist)
  remove(k.recents)
  remove(k.savedPrefs)
}

// ── Bulk setters (used when syncing from Firestore) ───────────────────
export function setWishlistItems(uid: string, items: WishlistItem[]) {
  write(keys(uid).wishlist, items.slice(0, 50))
}

export function setRecentSearches(uid: string, items: RecentSearch[]) {
  write(keys(uid).recents, items.slice(0, 20))
}

export function setSavedPreferenceItems(uid: string, items: SavedPreference[]) {
  write(keys(uid).savedPrefs, items.slice(0, 10))
}

// ── Wishlist ──────────────────────────────────────────────────────────
export function getWishlist(uid: string): WishlistItem[] {
  return read<WishlistItem[]>(keys(uid).wishlist, [])
}

export function isWishlisted(uid: string, id: string): boolean {
  return getWishlist(uid).some(w => w.id === id)
}

export function toggleWishlist(uid: string, item: WishlistItem): boolean {
  const list = getWishlist(uid)
  const idx  = list.findIndex(w => w.id === item.id)
  if (idx >= 0) {
    list.splice(idx, 1)
    write(keys(uid).wishlist, list)
    return false
  }
  list.unshift({ ...item, savedAt: Date.now() })
  write(keys(uid).wishlist, list.slice(0, 50))
  return true
}

export function removeFromWishlist(uid: string, id: string) {
  write(keys(uid).wishlist, getWishlist(uid).filter(w => w.id !== id))
}

// ── Recent searches ───────────────────────────────────────────────────
export function getRecents(uid: string): RecentSearch[] {
  return read<RecentSearch[]>(keys(uid).recents, [])
}

export function addRecent(uid: string, item: Omit<RecentSearch, 'id' | 'ts'>): RecentSearch {
  const list = getRecents(uid).filter(r => r.query !== item.query)
  const recent = { ...item, id: Math.random().toString(36).slice(2), ts: Date.now() }
  list.unshift(recent)
  write(keys(uid).recents, list.slice(0, 20))
  return recent
}

export function clearRecents(uid: string) {
  write(keys(uid).recents, [])
}

// ── Saved preferences ─────────────────────────────────────────────────
export function getSavedPrefs(uid: string): SavedPreference[] {
  return read<SavedPreference[]>(keys(uid).savedPrefs, [])
}

export function savePreference(uid: string, item: Omit<SavedPreference, 'id' | 'ts'>): SavedPreference {
  const list = getSavedPrefs(uid)
  const pref = { ...item, id: Math.random().toString(36).slice(2), ts: Date.now() }
  list.unshift(pref)
  write(keys(uid).savedPrefs, list.slice(0, 10))
  return pref
}

export function removeSavedPref(uid: string, id: string) {
  write(keys(uid).savedPrefs, getSavedPrefs(uid).filter(p => p.id !== id))
}

/**
 * useFirestore — syncs wishlist, recents, chats, history, and preferences
 * to Firestore when the user is logged in.
 *
 * Data model:
 *   users/{uid}/wishlist/{perfumeId}   — WishlistItem
 *   users/{uid}/history/{docId}        — HistoryItem
 *   users/{uid}/preferences/{docId}    — SavedPreference
 *   users/{uid}/recents/{docId}        — RecentSearch
 *   users/{uid}/chats/{chatId}         — StoredChat
 *   users/{uid}/settings/personalization — PersonalizationPrefs
 */
import {
  collection, doc,
  setDoc, deleteDoc, getDocs, getDoc, writeBatch,
  orderBy, query, limit,
  serverTimestamp, Timestamp,
} from 'firebase/firestore'
import { db, isFirestoreConnectionIssue, markFirestoreUnavailable, firestoreUnavailable } from '../utils/firebase'
import { WishlistItem, SavedPreference, RecentSearch } from '../store'

export interface HistoryItem {
  id: string
  query: string
  topResults: Array<{ name: string; brand: string; rating: number }>
  ts: number
}

export interface StoredChat {
  id: string
  title: string
  messages: Array<Record<string, unknown>>
  survey: Record<string, string>
  resultQuery?: string
  createdAtMs: number
  updatedAt: number
}

export interface UserProfile {
  nickname: string
  dateOfBirth: string   // ISO date string e.g. "1998-05-14"
  gender: string        // 'male' | 'female' | 'non-binary' | 'prefer-not-to-say'
  updatedAt?: number
}

export interface FirestorePersonalization {
  preferredGender: string
  favoriteNotes: string[]
  preferredOccasion: string
  preferredSeason: string
  preferredIntensity: string
}

function cleanValue(value: unknown): unknown {
  if (value === undefined) return null
  if (Array.isArray(value)) return value.map(cleanValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .map(([key, entry]) => [key, cleanValue(entry)])
    )
  }
  return value
}

function tsToMillis(value: unknown, fallback = Date.now()) {
  return value instanceof Timestamp ? value.toMillis() : typeof value === 'number' ? value : fallback
}

function chatFromDoc(id: string, data: Record<string, any>): StoredChat {
  return {
    id,
    title: data.title || 'Untitled chat',
    messages: Array.isArray(data.messages) ? data.messages : [],
    survey: data.survey || {},
    resultQuery: data.resultQuery || '',
    createdAtMs: typeof data.createdAtMs === 'number' ? data.createdAtMs : Date.now(),
    updatedAt: tsToMillis(data.updatedAt),
  }
}

function isFallbackMode(error: unknown) {
  if (firestoreUnavailable) return true
  if (!error) return false
  if (isFirestoreConnectionIssue(error)) {
    markFirestoreUnavailable()
    return true
  }
  return false
}

// ── Wishlist ──────────────────────────────────────────────────────────

export async function fsAddToWishlist(uid: string, item: WishlistItem) {
  try {
    await setDoc(doc(db, 'users', uid, 'wishlist', item.id), {
      id: item.id,
      name: item.name,
      brand: item.brand,
      accords: item.accords ?? null,
      rating: item.rating,
      image_url: item.image_url ?? null,
      savedAt: serverTimestamp(),
    })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsRemoveFromWishlist(uid: string, itemId: string) {
  try {
    await deleteDoc(doc(db, 'users', uid, 'wishlist', itemId))
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetWishlist(uid: string): Promise<WishlistItem[]> {
  try {
    const snap = await getDocs(
      query(collection(db, 'users', uid, 'wishlist'), orderBy('savedAt', 'desc'), limit(50))
    )
    return snap.docs.map(d => {
      const data = d.data()
      return {
        ...data,
        id: d.id,
        savedAt: data.savedAt instanceof Timestamp ? data.savedAt.toMillis() : Date.now(),
      } as WishlistItem
    })
  } catch (error) {
    if (isFallbackMode(error)) return []
    throw error
  }
}

// ── History ───────────────────────────────────────────────────────────

export async function fsAddHistory(uid: string, item: Omit<HistoryItem, 'id'>) {
  try {
    const ref = doc(collection(db, 'users', uid, 'history'))
    await setDoc(ref, {
      query: item.query,
      topResults: cleanValue(item.topResults),
      ts: serverTimestamp(),
    })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetHistory(uid: string): Promise<HistoryItem[]> {
  try {
    const snap = await getDocs(
      query(collection(db, 'users', uid, 'history'), orderBy('ts', 'desc'), limit(20))
    )
    return snap.docs.map(d => {
      const data = d.data()
      return {
        ...data,
        id: d.id,
        ts: data.ts instanceof Timestamp ? data.ts.toMillis() : Date.now(),
      } as HistoryItem
    })
  } catch (error) {
    if (isFallbackMode(error)) return []
    throw error
  }
}

// ── Recents ───────────────────────────────────────────────────────────

export async function fsAddRecent(uid: string, item: RecentSearch) {
  try {
    await setDoc(doc(db, 'users', uid, 'recents', item.id), {
      id: item.id,
      query: item.query,
      label: item.label,
      survey: item.survey || {},
      tsMs: item.ts,
      ts: serverTimestamp(),
    })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetRecents(uid: string): Promise<RecentSearch[]> {
  try {
    const snap = await getDocs(
      query(collection(db, 'users', uid, 'recents'), orderBy('ts', 'desc'), limit(20))
    )
    return snap.docs.map(d => {
      const data = d.data()
      return {
        id: data.id || d.id,
        query: data.query || '',
        label: data.label || data.query || 'Recent search',
        survey: data.survey || {},
        ts: tsToMillis(data.ts, data.tsMs ?? Date.now()),
      }
    })
  } catch (error) {
    if (isFallbackMode(error)) return []
    throw error
  }
}

export async function fsClearRecents(uid: string) {
  try {
    const snap = await getDocs(collection(db, 'users', uid, 'recents'))
    const batch = writeBatch(db)
    snap.docs.forEach(d => batch.delete(d.ref))
    await batch.commit()
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

// ── Preferences ───────────────────────────────────────────────────────

export async function fsAddPreference(uid: string, item: SavedPreference) {
  try {
    await setDoc(doc(db, 'users', uid, 'preferences', item.id), {
      id: item.id,
      label: item.label,
      survey: item.survey || {},
      tsMs: item.ts,
      ts: serverTimestamp(),
    })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetPreferences(uid: string): Promise<SavedPreference[]> {
  try {
    const snap = await getDocs(
      query(collection(db, 'users', uid, 'preferences'), orderBy('ts', 'desc'), limit(10))
    )
    return snap.docs.map(d => {
      const data = d.data()
      return {
        ...data,
        id: d.id,
        ts: data.ts instanceof Timestamp ? data.ts.toMillis() : Date.now(),
      } as SavedPreference
    })
  } catch (error) {
    if (isFallbackMode(error)) return []
    throw error
  }
}

export async function fsRemovePreference(uid: string, prefId: string) {
  try {
    await deleteDoc(doc(db, 'users', uid, 'preferences', prefId))
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

// ── Personalization settings ──────────────────────────────────────────

export async function fsSavePersonalization(uid: string, prefs: FirestorePersonalization) {
  try {
    await setDoc(doc(db, 'users', uid, 'settings', 'personalization'), {
      preferredGender: prefs.preferredGender || '',
      favoriteNotes: prefs.favoriteNotes || [],
      preferredOccasion: prefs.preferredOccasion || '',
      preferredSeason: prefs.preferredSeason || '',
      preferredIntensity: prefs.preferredIntensity || '',
      updatedAt: serverTimestamp(),
    })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetPersonalization(uid: string): Promise<FirestorePersonalization | null> {
  try {
    const snap = await getDoc(doc(db, 'users', uid, 'settings', 'personalization'))
    if (!snap.exists()) return null
    const data = snap.data()
    return {
      preferredGender: data.preferredGender || '',
      favoriteNotes: Array.isArray(data.favoriteNotes) ? data.favoriteNotes : [],
      preferredOccasion: data.preferredOccasion || '',
      preferredSeason: data.preferredSeason || '',
      preferredIntensity: data.preferredIntensity || '',
    }
  } catch (error) {
    if (isFallbackMode(error)) return null
    throw error
  }
}

// ── Chat sessions ─────────────────────────────────────────────────────

export async function fsSaveChat(uid: string, chat: Omit<StoredChat, 'updatedAt'>) {
  try {
    await setDoc(doc(db, 'users', uid, 'chats', chat.id), {
      id: chat.id,
      title: chat.title || 'Untitled chat',
      messages: cleanValue(chat.messages.slice(-80)),
      survey: chat.survey || {},
      resultQuery: chat.resultQuery || '',
      createdAtMs: chat.createdAtMs,
      updatedAt: serverTimestamp(),
    }, { merge: true })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetChats(uid: string): Promise<StoredChat[]> {
  try {
    const snap = await getDocs(
      query(collection(db, 'users', uid, 'chats'), orderBy('updatedAt', 'desc'), limit(20))
    )
    return snap.docs.map(d => chatFromDoc(d.id, d.data()))
  } catch (error) {
    if (isFallbackMode(error)) return []
    throw error
  }
}

export async function fsGetLatestChat(uid: string): Promise<StoredChat | null> {
  const chats = await fsGetChats(uid)
  return chats[0] ?? null
}

export async function fsGetChat(uid: string, chatId: string): Promise<StoredChat | null> {
  try {
    const snap = await getDoc(doc(db, 'users', uid, 'chats', chatId))
    return snap.exists() ? chatFromDoc(snap.id, snap.data()) : null
  } catch (error) {
    if (isFallbackMode(error)) return null
    throw error
  }
}

export async function fsDeleteChat(uid: string, chatId: string) {
  try {
    await deleteDoc(doc(db, 'users', uid, 'chats', chatId))
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

// ── User profile (nickname, DOB, gender) ─────────────────────────────

export async function fsSaveUserProfile(uid: string, profile: UserProfile) {
  try {
    await setDoc(doc(db, 'users', uid, 'settings', 'profile'), {
      nickname: profile.nickname || '',
      dateOfBirth: profile.dateOfBirth || '',
      gender: profile.gender || '',
      updatedAt: serverTimestamp(),
    }, { merge: true })
  } catch (error) {
    if (!isFallbackMode(error)) throw error
  }
}

export async function fsGetUserProfile(uid: string): Promise<UserProfile | null> {
  try {
    const snap = await getDoc(doc(db, 'users', uid, 'settings', 'profile'))
    if (!snap.exists()) return null
    const data = snap.data()
    return {
      nickname: data.nickname || '',
      dateOfBirth: data.dateOfBirth || '',
      gender: data.gender || '',
      updatedAt: tsToMillis(data.updatedAt),
    }
  } catch (error) {
    if (isFallbackMode(error)) return null
    throw error
  }
}

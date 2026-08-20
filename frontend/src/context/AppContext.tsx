import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode, Dispatch, SetStateAction } from 'react'
import { Perfume, RecommendationScore } from '../types'
import {
  WishlistItem, RecentSearch, SavedPreference,
  getWishlist, toggleWishlist as storeToggle,
  getRecents, addRecent, clearRecents,
  getSavedPrefs, savePreference, removeSavedPref,
  setWishlistItems, setRecentSearches, setSavedPreferenceItems,
  clearLegacyStorage,
} from '../store/index'
import { useAuth } from './AuthContext'
import {
  fsAddToWishlist, fsRemoveFromWishlist, fsGetWishlist,
  fsAddHistory, fsGetHistory, HistoryItem,
  fsAddPreference, fsGetPreferences, fsRemovePreference,
  fsAddRecent, fsGetRecents, fsClearRecents,
  fsSavePersonalization, fsGetPersonalization,
  fsSaveChat, fsGetChats, fsGetChat, fsDeleteChat, StoredChat,
  fsSaveUserProfile, fsGetUserProfile, UserProfile,
} from '../hooks/useFirestore'

// ── Types ─────────────────────────────────────────────────────────────
export interface SurveyState {
  gender: string
  occasion: string
  season: string
  mood: string
}

export interface PersonalizationPrefs {
  preferredGender: string
  favoriteNotes: string[]
  preferredOccasion: string
  preferredSeason: string
  preferredIntensity: string
}

export type AppPhase = 'quiz' | 'results'

export interface ConvMsg {
  id: string
  role: 'user' | 'advisor'
  text: string
  cards?: RecommendationScore[]
  isSearching?: boolean
  timestamp: number
  // Context extracted from this message (for display)
  extractedContext?: {
    gender?: string
    occasion?: string
    season?: string
    mood?: string
    liked_notes?: string[]
  }
  followUpSuggestions?: string[]
}

interface AppContextValue {
  phase: AppPhase
  setPhase: (p: AppPhase) => void

  survey: SurveyState
  setSurvey: (s: SurveyState) => void
  surveyStep: number
  setSurveyStep: (n: number) => void

  results: RecommendationScore[]
  setResults: (r: RecommendationScore[]) => void
  resultQuery: string
  setResultQuery: (q: string) => void
  isLoading: boolean
  setIsLoading: (b: boolean) => void
  loadError: string
  setLoadError: (s: string) => void
  visibleCount: number
  setVisibleCount: (n: number) => void

  // Persisted conversation (survives phase changes)
  conversation: ConvMsg[]
  setConversation: Dispatch<SetStateAction<ConvMsg[]>>

  // Temporary mode (session not saved)
  tempMode: boolean
  setTempMode: (b: boolean) => void

  // Sidebar state (shared so TopNav can open it)
  sidebarOpen: boolean
  setSidebarOpen: (b: boolean | ((prev: boolean) => boolean)) => void
  sidebarTab: 'recents' | 'saved' | 'explore' | 'settings'
  setSidebarTab: (t: 'recents' | 'saved' | 'explore' | 'settings') => void

  modalPerfume: Perfume | null
  openModal: (p: Perfume) => void
  closeModal: () => void

  wishlist: WishlistItem[]
  wishSet: Set<string>
  toggleWishlist: (item: WishlistItem) => void

  recents: RecentSearch[]
  addRecentSearch: (item: Omit<RecentSearch, 'id' | 'ts'>) => void
  clearAllRecents: () => void

  savedPrefs: SavedPreference[]
  addSavedPref: (item: Omit<SavedPreference, 'id' | 'ts'>) => void
  removeSavedPrefById: (id: string) => void

  history: HistoryItem[]
  addHistoryItem: (item: Omit<HistoryItem, 'id'>) => void

  chatSummaries: StoredChat[]
  openChat: (chatId: string) => Promise<void>
  deleteChat: (chatId: string) => Promise<void>

  // Stop generation
  stopGeneration: boolean
  setStopGeneration: (b: boolean) => void

  // Personalization preferences
  personalization: PersonalizationPrefs
  setPersonalization: (p: PersonalizationPrefs) => void

  // User profile (nickname, DOB, gender)
  userProfile: UserProfile
  setUserProfile: (p: UserProfile) => void

  // Whether current conversation was loaded from history (no typewriter)
  isHistoryChat: boolean

  resetToQuiz: () => void
}

// ── Context ───────────────────────────────────────────────────────────
const Ctx = createContext<AppContextValue | null>(null)

const makeId = () => Math.random().toString(36).slice(2, 12)

function buildChatTitle(conversation: ConvMsg[], resultQuery: string) {
  const firstUserMessage = conversation.find(m => m.role === 'user' && m.text.trim())
  const fallbackMessage = conversation.find(m => m.text.trim())
  const title = firstUserMessage?.text || resultQuery || fallbackMessage?.text || 'Scent conversation'
  return title.replace(/\s+/g, ' ').trim().slice(0, 120)
}

function upsertChatSummary(list: StoredChat[], chat: StoredChat) {
  return [chat, ...list.filter(item => item.id !== chat.id)]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, 20)
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  const [phase, setPhase]               = useState<AppPhase>('quiz')
  const [survey, setSurvey]             = useState<SurveyState>({ gender: '', occasion: '', season: '', mood: '' })
  const [surveyStep, setSurveyStep]     = useState(0)
  const [results, setResults]           = useState<RecommendationScore[]>([])
  const [resultQuery, setResultQuery]   = useState('')
  const [isLoading, setIsLoading]       = useState(false)
  const [loadError, setLoadError]       = useState('')
  const [visibleCount, setVisibleCount] = useState(3)
  const [modalPerfume, setModalPerfume] = useState<Perfume | null>(null)
  const [conversation, setConversation] = useState<ConvMsg[]>([])
  const [sidebarOpen, setSidebarOpen]   = useState(false)
  const [sidebarTab, setSidebarTab]     = useState<'recents' | 'saved' | 'explore' | 'settings'>('recents')
  const [stopGeneration, setStopGeneration] = useState(false)
  const [tempMode, setTempMode]         = useState(false)
  const [personalization, setPersonalizationState] = useState<PersonalizationPrefs>({
    preferredGender: '', favoriteNotes: [], preferredOccasion: '',
    preferredSeason: '', preferredIntensity: '',
  })
  const [userProfile, setUserProfileState] = useState<UserProfile>({
    nickname: '', dateOfBirth: '', gender: '',
  })
  const [isHistoryChat, setIsHistoryChat] = useState(false)

  const [wishlist, setWishlist]     = useState<WishlistItem[]>([])
  const [wishSet, setWishSet]       = useState<Set<string>>(() => new Set<string>())
  const [recents, setRecents]       = useState<RecentSearch[]>([])
  const [savedPrefs, setSavedPrefs] = useState<SavedPreference[]>([])
  const [history, setHistory]       = useState<HistoryItem[]>([])
  const [chatSummaries, setChatSummaries] = useState<StoredChat[]>([])
  const [activeChatId, setActiveChatId] = useState(makeId)
  const saveChatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedChatRef = useRef('')

  // ── Clear legacy unscoped localStorage on mount (one-time migration) ─
  useEffect(() => { clearLegacyStorage() }, [])

  // ── Sync from Firestore when user logs in; wipe state on logout ───
  useEffect(() => {
    if (!user) {
      // User logged out — wipe ALL in-memory state immediately.
      // localStorage is already scoped per-uid so nothing leaks,
      // but we still clear React state so the next user starts fresh.
      setWishlist([])
      setWishSet(new Set())
      setRecents([])
      setSavedPrefs([])
      setHistory([])
      setChatSummaries([])
      setPersonalizationState({ preferredGender: '', favoriteNotes: [], preferredOccasion: '', preferredSeason: '', preferredIntensity: '' })
      setUserProfileState({ nickname: '', dateOfBirth: '', gender: '' })
      setConversation([])
      setPhase('quiz')
      setSurvey({ gender: '', occasion: '', season: '', mood: '' })
      setSurveyStep(0)
      setResults([])
      setResultQuery('')
      setActiveChatId(makeId())
      lastSavedChatRef.current = ''
      return
    }

    // User logged in — load their data from Firestore, then seed localStorage cache
    const uid = user.uid

    fsGetWishlist(uid).then(items => {
      setWishlist(items)
      setWishSet(new Set(items.map(w => w.id)))
      setWishlistItems(uid, items)
    }).catch(() => {})

    fsGetRecents(uid).then(items => {
      setRecents(items)
      setRecentSearches(uid, items)
    }).catch(() => {})

    fsGetHistory(uid).then(setHistory).catch(() => {})

    fsGetPreferences(uid).then(prefs => {
      if (prefs.length > 0) {
        setSavedPrefs(prefs)
        setSavedPreferenceItems(uid, prefs)
      }
    }).catch(() => {})

    fsGetPersonalization(uid).then(prefs => {
      if (prefs) setPersonalizationState(prefs)
    }).catch(() => {})

    fsGetUserProfile(uid).then(profile => {
      if (profile) setUserProfileState(profile)
    }).catch(() => {})

    fsGetChats(uid).then(chats => {
      setChatSummaries(chats)
    }).catch(() => {})
  }, [user])

  // ── Persist active chat session to Firestore ──────────────────────
  useEffect(() => {
    // Skip saving if temp mode is active
    if (tempMode) return
    if (!user || conversation.length === 0 || conversation.some(m => m.isSearching)) return

    const snapshot = JSON.stringify({ activeChatId, conversation, resultQuery, survey })
    if (snapshot === lastSavedChatRef.current) return

    if (saveChatTimerRef.current) clearTimeout(saveChatTimerRef.current)
    saveChatTimerRef.current = setTimeout(() => {
      const now = Date.now()
      const chat = {
        id: activeChatId,
        title: buildChatTitle(conversation, resultQuery),
        messages: conversation as unknown as Array<Record<string, unknown>>,
        survey: survey as unknown as Record<string, string>,
        resultQuery,
        createdAtMs: conversation[0]?.timestamp || now,
      }

      fsSaveChat(user.uid, chat)
        .then(() => {
          lastSavedChatRef.current = snapshot
          setChatSummaries(prev => upsertChatSummary(prev, { ...chat, updatedAt: now }))
        })
        .catch(() => {})
    }, 600)

    return () => {
      if (saveChatTimerRef.current) clearTimeout(saveChatTimerRef.current)
    }
  }, [user, activeChatId, conversation, resultQuery, survey, tempMode])

  const openModal  = useCallback((p: Perfume) => setModalPerfume(p), [])
  const closeModal = useCallback(() => setModalPerfume(null), [])

  const toggleWishlist = useCallback((item: WishlistItem) => {
    if (!user) return
    storeToggle(user.uid, item)
    const updated = getWishlist(user.uid)
    setWishlist(updated)
    setWishSet(new Set(updated.map(w => w.id)))
    const isNowSaved = updated.some(w => w.id === item.id)
    if (isNowSaved) fsAddToWishlist(user.uid, item).catch(() => {})
    else fsRemoveFromWishlist(user.uid, item.id).catch(() => {})
  }, [user])

  const addRecentSearch = useCallback((item: Omit<RecentSearch, 'id' | 'ts'>) => {
    if (!user) return
    const recent = addRecent(user.uid, item)
    setRecents(getRecents(user.uid))
    fsAddRecent(user.uid, recent).catch(() => {})
  }, [user])

  const clearAllRecents = useCallback(() => {
    if (!user) return
    clearRecents(user.uid)
    setRecents([])
    fsClearRecents(user.uid).catch(() => {})
  }, [user])

  const addSavedPref = useCallback((item: Omit<SavedPreference, 'id' | 'ts'>) => {
    if (!user) return
    const pref = savePreference(user.uid, item)
    setSavedPrefs(getSavedPrefs(user.uid))
    fsAddPreference(user.uid, pref).catch(() => {})
  }, [user])

  const removeSavedPrefById = useCallback((id: string) => {
    if (!user) return
    removeSavedPref(user.uid, id)
    setSavedPrefs(getSavedPrefs(user.uid))
    fsRemovePreference(user.uid, id).catch(() => {})
  }, [user])

  const addHistoryItem = useCallback((item: Omit<HistoryItem, 'id'>) => {
    setHistory(prev => [{ ...item, id: Math.random().toString(36).slice(2) }, ...prev].slice(0, 20))
    if (user) fsAddHistory(user.uid, item).catch(() => {})
  }, [user])

  const setPersonalization = useCallback((prefs: PersonalizationPrefs) => {
    setPersonalizationState(prefs)
    if (user) fsSavePersonalization(user.uid, prefs).catch(() => {})
  }, [user])

  const setUserProfile = useCallback((profile: UserProfile) => {
    setUserProfileState(profile)
    if (user) fsSaveUserProfile(user.uid, profile).catch(() => {})
  }, [user])

  const openChat = useCallback(async (chatId: string) => {
    if (!user) return
    const chat = await fsGetChat(user.uid, chatId)
    if (!chat) return
    setActiveChatId(chat.id)
    setSurvey({
      gender: chat.survey.gender || '',
      occasion: chat.survey.occasion || '',
      season: chat.survey.season || '',
      mood: chat.survey.mood || '',
    })
    setResultQuery(chat.resultQuery || '')
    setConversation(chat.messages as unknown as ConvMsg[])
    setIsHistoryChat(true)   // ← mark as history: no typewriter, no re-generation
    setPhase('results')
    setSidebarOpen(false)
  }, [user])

  const deleteChat = useCallback(async (chatId: string) => {
    setChatSummaries(prev => prev.filter(c => c.id !== chatId))
    if (user) {
      await fsDeleteChat(user.uid, chatId).catch(() => {})
    }
    // If the deleted chat is the active one, reset to quiz
    setActiveChatId(prev => {
      if (prev === chatId) {
        resetToQuiz()
        return makeId()
      }
      return prev
    })
  }, [user])

  const resetToQuiz = useCallback(() => {
    setActiveChatId(makeId())
    lastSavedChatRef.current = ''
    setIsHistoryChat(false)
    setTempMode(false)  // Reset temp mode on new search
    setPhase('quiz')
    setSurvey({ gender: '', occasion: '', season: '', mood: '' })
    setSurveyStep(0)
    setResults([])
    setResultQuery('')
    setLoadError('')
    setVisibleCount(3)
    setConversation([])
  }, [])

  return (
    <Ctx.Provider value={{
      phase, setPhase,
      survey, setSurvey, surveyStep, setSurveyStep,
      results, setResults, resultQuery, setResultQuery,
      isLoading, setIsLoading, loadError, setLoadError,
      visibleCount, setVisibleCount,
      conversation, setConversation,
      sidebarOpen, setSidebarOpen,
      sidebarTab, setSidebarTab,
      modalPerfume, openModal, closeModal,
      wishlist, wishSet, toggleWishlist,
      recents, addRecentSearch, clearAllRecents,
      savedPrefs, addSavedPref, removeSavedPrefById,
      history, addHistoryItem,
      chatSummaries, openChat, deleteChat,
      stopGeneration, setStopGeneration,
      tempMode, setTempMode,
      personalization, setPersonalization,
      userProfile, setUserProfile,
      isHistoryChat,
      resetToQuiz,
    }}>
      {children}
    </Ctx.Provider>
  )
}

export function useApp() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}

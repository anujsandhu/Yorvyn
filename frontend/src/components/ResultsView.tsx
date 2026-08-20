/**
 * ResultsView — ChatGPT-style conversational perfume advisor.
 *
 * Features:
 * - Full conversation history sent to backend on every turn
 * - Backend extracts & merges intent across turns (occasion, gender, mood, notes)
 * - Typewriter effect on advisor replies
 * - Follow-up suggestion chips generated per-turn
 * - Context pill strip shows what the advisor has understood
 * - Cards shown after text finishes typing
 * - "Show more" to expand card grid
 * - Smooth scroll to latest message
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import {
  Send, Plus, Sparkles, Square,
  Users, User, MapPin, Calendar, Smile, Music, Zap,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useApp, ConvMsg } from '../context/AppContext'
import { apiClient } from '../utils/api'
import { buildAccordTags } from '../utils/perfumeDisplay'
import { RecommendationScore } from '../types'
import { PerfumeCard } from './PerfumeCard'
import './ResultsView.css'

// ── Typewriter hook ───────────────────────────────────────────────────
function useTypewriter(text: string, speed = 18, active = true) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)
  useEffect(() => {
    if (!active || !text) { setDisplayed(text); setDone(true); return }
    setDisplayed('')
    setDone(false)
    let i = 0
    const id = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) { clearInterval(id); setDone(true) }
    }, speed)
    return () => clearInterval(id)
  }, [text, active])
  return { displayed, done }
}

// ── Searching status ──────────────────────────────────────────────────
const SEARCH_PHRASES = [
  'Scanning 73,000+ fragrances...',
  'Matching your scent profile...',
  'Ranking by notes and mood...',
  'Filtering by occasion...',
  'Almost there...',
]

function SearchingStatus() {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setIdx(i => (i + 1) % SEARCH_PHRASES.length), 1400)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="rv-searching">
      <div className="rv-searching-dots">
        <span /><span /><span />
      </div>
      <AnimatePresence mode="wait">
        <motion.span
          key={idx}
          className="rv-searching-text"
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.22 }}
        >
          {SEARCH_PHRASES[idx]}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

// ── Rich text renderer ────────────────────────────────────────────────
function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g)
  return (
    <p className="rv-conv-text">
      {parts.map((p, i) => {
        if (p.startsWith('**') && p.endsWith('**'))
          return <strong key={i}>{p.slice(2, -2)}</strong>
        if (p.startsWith('*') && p.endsWith('*'))
          return <em key={i} className="rv-italic">{p.slice(1, -1)}</em>
        if (p.startsWith('`') && p.endsWith('`'))
          return <code key={i} className="rv-code">{p.slice(1, -1)}</code>
        return <span key={i}>{p}</span>
      })}
    </p>
  )
}

// ── Context pill strip ────────────────────────────────────────────────
function ContextPills({ ctx }: { ctx: ConvMsg['extractedContext'] }) {
  if (!ctx) return null
  const pills: Array<{ key: string; label: string; icon: typeof User }> = []
  if (ctx.gender) {
    pills.push({
      key: `gender-${ctx.gender}`,
      label: ctx.gender === 'women' ? 'Women' : ctx.gender === 'men' ? 'Men' : 'Unisex',
      icon: ctx.gender === 'unisex' ? Users : User,
    })
  }
  if (ctx.occasion) {
    pills.push({
      key: `occasion-${ctx.occasion}`,
      label: ctx.occasion.charAt(0).toUpperCase() + ctx.occasion.slice(1),
      icon: MapPin,
    })
  }
  if (ctx.season) {
    pills.push({
      key: `season-${ctx.season}`,
      label: ctx.season.charAt(0).toUpperCase() + ctx.season.slice(1),
      icon: Calendar,
    })
  }
  if (ctx.mood) {
    const moodLabel = ctx.mood.split(' ').slice(0, 2).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    pills.push({ key: `mood-${ctx.mood}`, label: moodLabel, icon: Smile })
  }
  if (ctx.liked_notes?.length) {
    pills.push({ key: `notes-${ctx.liked_notes.join('-')}`, label: ctx.liked_notes.slice(0, 2).join(', '), icon: Music })
  }
  if (!pills.length) return null
  return (
    <div className="rv-ctx-pills">
      {pills.map(p => {
        const Icon = p.icon
        return (
          <span key={p.key} className="rv-ctx-pill">
            <Icon size={11} />
            {p.label}
          </span>
        )
      })}
    </div>
  )
}

// ── Advisor message ───────────────────────────────────────────────────
function AdvisorMessage({
  msg, isLatest, visibleCount, onShowMore, skipAnimation,
}: {
  msg: ConvMsg
  isLatest: boolean
  visibleCount: number
  onShowMore: () => void
  skipAnimation: boolean
}) {
  // Skip typewriter if: not the latest message, or history chat
  const { displayed, done } = useTypewriter(msg.text, 16, isLatest && !msg.isSearching && !skipAnimation)
  const { wishSet, toggleWishlist, openModal } = useApp()

  const handleOpen = (rec: RecommendationScore) => {
    openModal({
      id: rec.perfume_id, name: rec.name, brand: rec.brand,
      family: rec.family, rating: rec.rating, price: rec.price_usd ?? 0,
      description: rec.description, image_url: rec.image_url,
      gender: rec.gender, accords: rec.accords,
    })
  }

  const handleWish = (rec: RecommendationScore) => {
    toggleWishlist({
      id: rec.perfume_id, name: rec.name, brand: rec.brand,
      accords: rec.accords, rating: rec.rating,
      image_url: rec.image_url, savedAt: Date.now(),
    })
  }

  const showCards = msg.cards && msg.cards.length > 0 && (!isLatest || done)
  const visibleCards = msg.cards?.slice(0, visibleCount) ?? []
  const remaining = (msg.cards?.length ?? 0) - visibleCount

  return (
    <div className="rv-conv-advisor">
      <div className="rv-conv-avatar" aria-hidden="true">
        <Sparkles size={12} />
      </div>
      <div className="rv-conv-body">
        {/* Text */}
        {msg.isSearching ? (
          <SearchingStatus />
        ) : isLatest && !done ? (
          <p className="rv-conv-text">
            {displayed}<span className="rv-cursor" aria-hidden="true" />
          </p>
        ) : (
          <RichText text={msg.text} />
        )}

        {/* Context pills — shown after text done */}
        {!msg.isSearching && (!isLatest || done) && msg.extractedContext && (
          <ContextPills ctx={msg.extractedContext} />
        )}

        {/* Cards */}
        {showCards && (
          <div className="rv-conv-cards">
            {visibleCards.map((rec, i) => (
              <PerfumeCard
                key={rec.perfume_id}
                card={{
                  id: rec.perfume_id, name: rec.name, brand: rec.brand,
                  family: rec.family, rating: rec.rating, accords: rec.accords,
                  image_url: rec.image_url, gender: rec.gender, score: rec.final_score,
                }}
                rank={i + 1}
                wishlisted={wishSet.has(rec.perfume_id)}
                onOpen={() => handleOpen(rec)}
                onWishlist={() => handleWish(rec)}
                delay={i * 0.04}
                badge={i === 0 ? '🔥 Top Pick' : undefined}
              />
            ))}
          </div>
        )}

        {/* Show more */}
        {showCards && remaining > 0 && (
          <button className="rv-more-btn" onClick={onShowMore}>
            <Plus size={12} />
            Show {Math.min(3, remaining)} more
            <span className="rv-more-count">{remaining} remaining</span>
          </button>
        )}
      </div>
    </div>
  )
}

// ── Follow-up suggestion chips ────────────────────────────────────────
function FollowUpChips({
  chips, onSelect, disabled,
}: {
  chips: string[]
  onSelect: (text: string) => void
  disabled: boolean
}) {
  if (!chips.length) return null
  return (
    <motion.div
      className="rv-followup-row"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.22 }}
    >
      {chips.map(chip => (
        <button
          key={chip}
          className="rv-followup-chip"
          onClick={() => onSelect(chip)}
          disabled={disabled}
        >
          {chip}
        </button>
      ))}
    </motion.div>
  )
}

// ── uid ───────────────────────────────────────────────────────────────
const uid = () => Math.random().toString(36).slice(2, 10)

// ── Main ResultsView ──────────────────────────────────────────────────
export function ResultsView() {
  const {
    results: initialResults,
    setResults, setResultQuery,
    isLoading: initialLoading,
    loadError: initialError,
    survey, resetToQuiz,
    addRecentSearch,
    addHistoryItem,
    conversation, setConversation,
    stopGeneration, setStopGeneration,
    isHistoryChat,
    userProfile,
    personalization,
    wishlist,
    recents,
    chatSummaries,
    tempMode, setTempMode,
  } = useApp()

  // Derive display name — nickname > Google first name > fallback
  const displayName = userProfile.nickname || ''
  const isNewUser   = chatSummaries.length === 0 && recents.length === 0

  const [inputText, setInputText]     = useState('')
  const [searching, setSearching]     = useState(false)
  // Per-message visible card count
  const [visibleMap, setVisibleMap]   = useState<Record<string, number>>({})
  // Latest follow-up chips (from last advisor message)
  const [followUps, setFollowUps]     = useState<string[]>([])

  const inputRef  = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const initRef   = useRef(false)

  // Build summary chips from quiz survey
  const summaryChips = [
    survey.gender && (survey.gender === 'women' ? 'Women' : survey.gender === 'men' ? 'Men' : 'Unisex'),
    survey.occasion && survey.occasion.charAt(0).toUpperCase() + survey.occasion.slice(1),
    survey.season && survey.season.charAt(0).toUpperCase() + survey.season.slice(1),
  ].filter(Boolean) as string[]

  // ── Seed conversation from quiz results ──────────────────────────
  useEffect(() => {
    if (initRef.current) return
    // If this is a history chat loaded from sidebar, don't re-seed
    if (conversation.length > 0) { initRef.current = true; return }
    if (isHistoryChat) { initRef.current = true; return }
    initRef.current = true

    if (initialLoading) {
      setConversation([{
        id: uid(), role: 'advisor', text: '', isSearching: true, timestamp: Date.now(),
      }])
      return
    }

    if (initialResults.length > 0) {
      const top = initialResults[0]
      const notes = buildAccordTags(top.accords, top.family, 3).join(', ')
      const namePrefix = displayName ? `${displayName}, ` : ''
      const reply = `${namePrefix}I found **${initialResults.length} fragrances** that match your profile. Your top pick is **${top.name}** by ${top.brand}${notes ? ` — *${notes}*` : ''}. Tap any card to see full details and where to buy.`
      const msgId = uid()
      setConversation([{
        id: msgId, role: 'advisor', text: reply,
        cards: initialResults.slice(0, 6), timestamp: Date.now(),
        extractedContext: {
          gender: survey.gender || undefined,
          occasion: survey.occasion || undefined,
          season: survey.season || undefined,
        },
        followUpSuggestions: [
          'Show me something lighter',
          'More intense options',
          'Under ₹2000',
          'Show me similar brands',
          'For a date night',
          'For daily wear',
        ],
      }])
      setVisibleMap({ [msgId]: 3 })
      setFollowUps([
        'Show me something lighter',
        'More intense options',
        'Under ₹2000',
        'Show me similar brands',
        'For a date night',
        'For daily wear',
      ])
    } else if (initialError) {
      setConversation([{
        id: uid(), role: 'advisor',
        text: `I ran into an issue: **${initialError}**. Try typing what you're looking for below.`,
        timestamp: Date.now(),
        followUpSuggestions: ['Fresh citrus scent', 'Warm oud for winter', 'Floral for women', 'Woody for men'],
      }])
      setFollowUps(['Fresh citrus scent', 'Warm oud for winter', 'Floral for women', 'Woody for men'])
    } else {
      const msgId = uid()
      // Personalized greeting based on whether user is new or returning
      const greeting = isNewUser
        ? displayName
          ? `Hey ${displayName}, I'm your personal fragrance advisor. Tell me what kind of vibe you're going for — an *occasion*, a *mood*, a *note*, or a perfume you already love.`
          : "Hey — I'm your personal fragrance advisor. Tell me what kind of vibe you're going for — an *occasion*, a *mood*, a *note*, or a perfume you already love."
        : displayName
          ? `Welcome back, ${displayName}. What are we looking for today?`
          : "Welcome back. What are we looking for today?"

      // Personalized chips based on saved preferences
      const personalChips = personalization.favoriteNotes.length > 0
        ? [`More ${personalization.favoriteNotes[0]} fragrances`, 'Something different this time']
        : []
      const defaultChips = ['Floral and feminine', 'Woody and bold', 'Fresh and clean', 'Warm and sensual', 'Sweet and playful', 'Winter oud']
      const chips = [...personalChips, ...defaultChips].slice(0, 6)

      setConversation([{
        id: msgId, role: 'advisor',
        text: greeting,
        timestamp: Date.now(),
        followUpSuggestions: chips,
      }])
      setFollowUps(chips)
    }
  }, [])

  // When initial loading resolves, update the searching message
  useEffect(() => {
    if (!initialLoading && initRef.current) {
      setConversation(prev => {
        if (!prev.some(m => m.isSearching)) return prev
        const top = initialResults[0]
        const notes = top ? buildAccordTags(top.accords, top.family, 3).join(', ') : ''
        const reply = initialResults.length > 0
          ? `I found **${initialResults.length} fragrances** that match your profile. Your top pick is **${top.name}** by ${top.brand}${notes ? ` — *${notes}*` : ''}. Tap any card to see full details.`
          : initialError
            ? `I ran into an issue: **${initialError}**. Try typing what you're looking for below.`
            : "I couldn't find matches. Try describing a *mood*, *note*, or reference perfume."
        const chips = initialResults.length > 0
          ? ['Show me something lighter', 'More intense options', 'Under ₹2000', 'For a date night']
          : ['Fresh citrus scent', 'Warm oud for winter', 'Floral for women']
        return prev.map(m =>
          m.isSearching
            ? { ...m, text: reply, cards: initialResults.slice(0, 6), isSearching: false, followUpSuggestions: chips }
            : m
        )
      })
    }
  }, [initialLoading, initialResults, initialError])

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation])

  // ── Send message ──────────────────────────────────────────────────
  const handleSend = useCallback(async (e: React.FormEvent | null, overrideText?: string) => {
    if (e) e.preventDefault()
    const text = (overrideText ?? inputText).trim()
    if (!text || searching) return

    setInputText('')
    setFollowUps([])

    // Add user message
    const userMsg: ConvMsg = { id: uid(), role: 'user', text, timestamp: Date.now() }
    setConversation(prev => [...prev, userMsg])

    // Add searching placeholder
    const searchId = uid()
    setConversation(prev => [...prev, {
      id: searchId, role: 'advisor', text: '', isSearching: true, timestamp: Date.now(),
    }])
    setSearching(true)
    setStopGeneration(false)

    addRecentSearch({ query: text, label: text, survey: survey as unknown as Record<string, string> })

    try {
      // Check if user stopped before request
      if (stopGeneration) {
        setConversation(prev => prev.map(m =>
          m.id === searchId ? { ...m, text: '*(Generation stopped)*', isSearching: false } : m
        ))
        setStopGeneration(false)
        return
      }

      // Build full history for the backend
      // Include all messages up to this point (conversation already has previous advisor responses)
      const historyForApi = [...conversation, userMsg]
        .filter(m => {
          // Include user messages
          if (m.role === 'user') return true
          // Include advisor messages that have text and aren't currently searching
          if (m.role === 'advisor' && m.text && !m.isSearching) return true
          return false
        })
        .map(m => ({ role: m.role, text: m.text, timestamp: m.timestamp }))
      
      // Debug: Log conversation history being sent
      console.log('📤 Sending conversation history:', historyForApi.map(m => `${m.role}: ${m.text.substring(0, 50)}...`))

      // Build user context for personalization
      const userContext = {
        name: userProfile.nickname || '',
        nickname: userProfile.nickname || '',
        gender: userProfile.gender || '',
        dateOfBirth: userProfile.dateOfBirth || '',
        preferredGender: personalization.preferredGender || '',
        favoriteNotes: personalization.favoriteNotes || [],
        preferredOccasion: personalization.preferredOccasion || '',
        preferredSeason: personalization.preferredSeason || '',
        preferredIntensity: personalization.preferredIntensity || '',
        likedPerfumeNames: wishlist.slice(0, 5).map(w => w.name),
        recentSearches: recents.slice(0, 5).map(r => r.query),
        isNewUser,
        totalChats: chatSummaries.length,
      }

      const res = await apiClient.chatV2(historyForApi, 6, userContext)

      // Check if user stopped after response
      if (stopGeneration) {
        setConversation(prev => prev.map(m =>
          m.id === searchId ? { ...m, text: '*(Generation stopped)*', isSearching: false } : m
        ))
        setStopGeneration(false)
        return
      }

      const chips = res.follow_up_suggestions ?? []
      const msgId = searchId

      setConversation(prev => prev.map(m =>
        m.id === msgId ? {
          ...m,
          text: res.reply,
          cards: res.recommendations,
          isSearching: false,
          extractedContext: res.extracted_context,
          followUpSuggestions: chips,
        } : m
      ))
      setVisibleMap(prev => ({ ...prev, [msgId]: 3 }))
      setFollowUps(chips)
      setResults(res.recommendations)
      setResultQuery(text)
      addHistoryItem({
        query: text,
        topResults: (res.recommendations || []).slice(0, 6).map(rec => ({
          name: rec.name,
          brand: rec.brand,
          rating: rec.rating,
        })),
        ts: Date.now(),
      })
    } catch (err: any) {
      const errText = err?.isOffline
        ? 'You appear offline. Check your connection and try again.'
        : err?.isBackendUnavailable || !err?.response
          ? 'The backend is unavailable right now. Please try again in a moment.'
        : `Something went wrong: *${err?.response?.data?.detail ?? err?.message ?? 'unknown error'}*`
      setConversation(prev => prev.map(m =>
        m.id === searchId ? { ...m, text: errText, isSearching: false } : m
      ))
    } finally {
      setSearching(false)
      setTimeout(() => inputRef.current?.focus(), 80)
    }
  }, [inputText, searching, conversation, survey, addHistoryItem])

  const handleShowMore = (msgId: string) => {
    setVisibleMap(prev => ({ ...prev, [msgId]: (prev[msgId] ?? 3) + 3 }))
  }

  // Latest advisor message's follow-ups (for display below last message)
  // (used to seed followUps state on init — kept for future use)

  return (
    <div className="rv-root">

      {/* ── Top bar ── */}
      <div className="rv-summary-bar">
        <div className="rv-summary-chips">
          {summaryChips.map(chip => (
            <span key={chip} className="rv-chip">{chip}</span>
          ))}
        </div>
        <div className="rv-summary-right">
          {/* Temp toggle */}
          <button
            className={`rv-temp-toggle ${tempMode ? 'rv-temp-active' : ''}`}
            onClick={() => setTempMode(!tempMode)}
            aria-label={tempMode ? 'Temporary mode active' : 'Enable temporary mode'}
            title={tempMode ? 'Temporary session - not saved' : 'Enable temporary mode'}
          >
            <Zap size={14} strokeWidth={2.5} />
            <span>Temp</span>
          </button>

          {/* New Search button */}
          <button
            className="rv-new-search-btn"
            onClick={resetToQuiz}
            aria-label="New search"
          >
            <Plus size={16} strokeWidth={2.5} />
            <span>New Search</span>
          </button>
        </div>
      </div>

      {/* Temp mode badge */}
      {tempMode && (
        <div className="rv-temp-badge">
          <Zap size={12} />
          <span>Temporary session - not saved to history</span>
        </div>
      )}

      {/* ── Conversation scroll ── */}
      <div className="rv-scroll" role="log" aria-live="polite" aria-label="Conversation">
        <div className="rv-conv-inner">

          {conversation.map((msg, idx) => {
            const isLatest = idx === conversation.length - 1
            const msgVisible = visibleMap[msg.id] ?? 3

            if (msg.role === 'user') {
              return (
                <motion.div
                  key={msg.id}
                  className="rv-conv-user"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <p className="rv-conv-user-text">{msg.text}</p>
                </motion.div>
              )
            }

            return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22 }}
              >
                <AdvisorMessage
                  msg={msg}
                  isLatest={isLatest}
                  visibleCount={msgVisible}
                  onShowMore={() => handleShowMore(msg.id)}
                  skipAnimation={isHistoryChat}
                />
              </motion.div>
            )
          })}

          {/* Follow-up chips — shown below last advisor message */}
          {followUps.length > 0 && !searching && (
            <FollowUpChips
              chips={followUps}
              onSelect={text => handleSend(null, text)}
              disabled={searching}
            />
          )}

          <div ref={bottomRef} style={{ height: 1 }} />
        </div>
      </div>

      {/* ── Input bar ── */}
      <div className="rv-refine-bar">
        <form className="rv-refine-form" onSubmit={handleSend}>
          <div className="rv-refine-wrap">
            <input
              ref={inputRef}
              className="rv-refine-input"
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              placeholder="Describe your vibe — fresh, date night, winter oud..."
              disabled={searching}
              autoComplete="off"
              autoFocus
              aria-label="Chat input"
            />
            {searching ? (
              <button
                type="button"
                className="rv-refine-send rv-stop-btn"
                onClick={() => { setStopGeneration(true); setSearching(false) }}
                aria-label="Stop generation"
                title="Stop"
              >
                <Square size={13} fill="currentColor" />
              </button>
            ) : (
              <button
                type="submit"
                className="rv-refine-send"
                disabled={!inputText.trim()}
                aria-label="Send"
              >
                <Send size={15} />
              </button>
            )}
          </div>
        </form>
        <p className="rv-refine-hint">
          Try: "something like Dior Sauvage" · "rose floral for her" · "oud for winter evenings" · "under ₹2000"
        </p>
      </div>
    </div>
  )
}

import { useState, useCallback, useEffect, useRef } from 'react'
import {
  ChevronLeft, Check, Flower2, TreePine, Users, Sun, Briefcase, Moon,
  Gem, Snowflake, Leaf, CircleDot, Droplets, Flame, Heart, Waves,
  type LucideIcon,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useApp, SurveyState } from '../context/AppContext'
import { apiClient } from '../utils/api'
import { TopPicks } from './TopPicks'
import './QuizView.css'

// ── Survey steps ──────────────────────────────────────────────────────
interface StepOption { value: string; label: string; sub: string; icon: LucideIcon }
interface Step { key: keyof SurveyState; question: string; options: StepOption[] }

const STEPS: Step[] = [
  {
    key: 'gender',
    question: 'Who is this fragrance for?',
    options: [
      { value: 'women',  label: 'Women',        sub: 'Floral, soft, feminine',    icon: Flower2 },
      { value: 'men',    label: 'Men',           sub: 'Woody, fresh, bold',        icon: TreePine },
      { value: 'unisex', label: 'Unisex / Gift', sub: 'Versatile, modern, shared', icon: Users },
    ],
  },
  {
    key: 'occasion',
    question: "What's the occasion?",
    options: [
      { value: 'daily',   label: 'Daily Wear',  sub: 'Light, effortless, all-day',  icon: Sun },
      { value: 'office',  label: 'Office',       sub: 'Subtle, professional, clean', icon: Briefcase },
      { value: 'date',    label: 'Date Night',   sub: 'Sensual, memorable, warm',    icon: Moon },
      { value: 'party',   label: 'Party',        sub: 'Bold, vibrant, expressive',   icon: Flame },
      { value: 'wedding', label: 'Wedding',      sub: 'Elegant, timeless, special',  icon: Gem },
    ],
  },
  {
    key: 'season',
    question: 'Season or climate?',
    options: [
      { value: 'summer', label: 'Summer', sub: 'Fresh, citrus, aquatic', icon: Sun },
      { value: 'winter', label: 'Winter', sub: 'Warm, spicy, deep',      icon: Snowflake },
      { value: 'spring', label: 'Spring', sub: 'Floral, green, light',   icon: Leaf },
      { value: 'autumn', label: 'Autumn', sub: 'Earthy, woody, amber',   icon: TreePine },
      { value: '',       label: 'Any',    sub: 'No preference',          icon: CircleDot },
    ],
  },
  {
    key: 'mood',
    question: 'What vibe are you going for?',
    options: [
      { value: 'fresh citrus clean',       label: 'Fresh & Clean',     sub: 'Citrus, aquatic, crisp',  icon: Droplets },
      { value: 'warm amber vanilla musky', label: 'Warm & Sensual',    sub: 'Amber, vanilla, musk',    icon: Flame },
      { value: 'floral rose feminine',     label: 'Floral & Romantic', sub: 'Rose, jasmine, peony',    icon: Heart },
      { value: 'woody oud leather smoky',  label: 'Bold & Woody',      sub: 'Oud, cedar, leather',     icon: TreePine },
      { value: 'sweet fruity gourmand',    label: 'Sweet & Playful',   sub: 'Fruity, gourmand, fun',   icon: Flower2 },
      { value: 'aquatic marine light',     label: 'Aquatic & Light',   sub: 'Marine, ozonic, breezy',  icon: Waves },
    ],
  },
]

function buildQuery(s: SurveyState): string {
  const parts: string[] = []
  if (s.mood)     parts.push(s.mood)
  if (s.occasion) parts.push(`for ${s.occasion}`)
  if (s.season)   parts.push(`in ${s.season}`)
  return parts.join(', ')
}

// Build context strip message from current survey state
function buildContextMsg(survey: SurveyState, step: number): string {
  if (step === 0) return 'Building your scent profile...'
  const parts: string[] = []
  if (survey.gender) {
    const g = survey.gender === 'women' ? 'Women' : survey.gender === 'men' ? 'Men' : 'Unisex'
    parts.push(g)
  }
  if (survey.occasion) parts.push(survey.occasion.charAt(0).toUpperCase() + survey.occasion.slice(1))
  if (survey.season)   parts.push(survey.season.charAt(0).toUpperCase() + survey.season.slice(1))
  if (survey.mood) {
    const moodLabel = STEPS[3].options.find(o => o.value === survey.mood)?.label ?? ''
    if (moodLabel) parts.push(moodLabel)
  }
  if (parts.length === 0) return 'Building your scent profile...'
  return `Based on: ${parts.join(' · ')}`
}

// Build context bridge tags
function buildBridgeTags(survey: SurveyState): string[] {
  const tags: string[] = []
  if (survey.gender) {
    tags.push(survey.gender === 'women' ? 'Women' : survey.gender === 'men' ? 'Men' : 'Unisex')
  }
  if (survey.occasion) tags.push(survey.occasion.charAt(0).toUpperCase() + survey.occasion.slice(1))
  if (survey.season)   tags.push(survey.season.charAt(0).toUpperCase() + survey.season.slice(1))
  if (survey.mood) {
    const moodLabel = STEPS[3].options.find(o => o.value === survey.mood)?.label ?? ''
    if (moodLabel) tags.push(moodLabel)
  }
  return tags
}

// ── Component ─────────────────────────────────────────────────────────
export function QuizView() {
  const {
    survey, setSurvey, surveyStep, setSurveyStep,
    setPhase, setResults, setResultQuery,
    setIsLoading, setLoadError, setVisibleCount,
    addRecentSearch, addSavedPref, addHistoryItem, openModal,
  } = useApp()

  const [selected, setSelected]   = useState<string | null>(null)
  const [direction, setDirection] = useState(1)
  const [pending, setPending]     = useState(false)
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null)

  const step     = STEPS[surveyStep]
  const isLast   = surveyStep === STEPS.length - 1
  const progress = (surveyStep / STEPS.length) * 100
  const bridgeTags = buildBridgeTags(survey)
  const contextMsg = buildContextMsg(survey, surveyStep)

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  // ── Fire recommendation ───────────────────────────────────────────
  const fireRec = useCallback(async (updated: SurveyState) => {
    const query = buildQuery(updated)
    setResultQuery(query)
    setPhase('results')
    setIsLoading(true)
    setLoadError('')
    setVisibleCount(3)

    const gLabel = STEPS[0].options.find(o => o.value === updated.gender)?.label ?? updated.gender
    const oLabel = STEPS[1].options.find(o => o.value === updated.occasion)?.label ?? updated.occasion
    const mLabel = STEPS[3].options.find(o => o.value === updated.mood)?.label ?? ''
    const prefLabel = [gLabel, oLabel, mLabel].filter(Boolean).join(' · ')
    addSavedPref({ label: prefLabel, survey: updated as unknown as Record<string, string> })
    addRecentSearch({ query, label: prefLabel, survey: updated as unknown as Record<string, string> })

    try {
      const res = await apiClient.getRecommendations(query, 12, {
        preferred_gender: updated.gender || undefined,
        occasion: updated.occasion || undefined,
        season: updated.season || undefined,
      })
      setResults(res.recommendations || [])
      addHistoryItem({
        query,
        topResults: (res.recommendations || []).slice(0, 6).map(rec => ({
          name: rec.name,
          brand: rec.brand,
          rating: rec.rating,
        })),
        ts: Date.now(),
      })
    } catch (err: any) {
      setLoadError(
        err?.isOffline
          ? 'You appear offline. Check your connection and try again.'
          : err?.isBackendUnavailable || !err?.response
            ? 'The backend is unavailable right now. Please try again in a moment.'
          : err?.response?.data?.detail ?? err?.message ?? 'Something went wrong'
      )
    } finally {
      setIsLoading(false)
    }
  }, [survey, addHistoryItem])

  // ── Advance step ──────────────────────────────────────────────────
  const advance = useCallback(async (value: string) => {
    const updated = { ...survey, [step.key]: value }
    setSurvey(updated)
    setSelected(null)
    setPending(false)
    setDirection(1)
    if (!isLast) { setSurveyStep(surveyStep + 1); return }
    await fireRec(updated)
  }, [survey, step, isLast, surveyStep, fireRec])

  const handleSelect = useCallback((value: string) => {
    if (pending) return
    setSelected(value)
    setPending(true)
    timerRef.current = setTimeout(() => advance(value), 360)
  }, [pending, advance])

  const handleBack = useCallback(() => {
    if (surveyStep === 0) return
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    setSelected(null)
    setPending(false)
    setDirection(-1)
    setSurveyStep(surveyStep - 1)
  }, [surveyStep])

  const handleSkip = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setPhase('results')
    setResultQuery('')
    setResults([])
    setIsLoading(false)
  }, [])

  const slideVariants = {
    enter: (d: number) => ({ opacity: 0, x: d > 0 ? 36 : -36 }),
    center: { opacity: 1, x: 0 },
    exit:  (d: number) => ({ opacity: 0, x: d > 0 ? -36 : 36 }),
  }

  const colClass = step.options.length <= 3 ? 'qv-cols-3'
                 : step.options.length <= 4 ? 'qv-cols-4'
                 : 'qv-cols-3'

  return (
    <div className="qv-root">

      {/* ── Skip button - moved to top right ── */}
      <button className="qv-skip-top" onClick={handleSkip}>
        Skip →
      </button>

      {/* ── 1. Context strip ── */}
      <div className="qv-context-strip">
        <AnimatePresence mode="wait">
          <motion.span
            key={contextMsg}
            className="qv-context-text"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            {contextMsg}
          </motion.span>
        </AnimatePresence>
      </div>

      {/* ── 2. Progress bar ── */}
      <div className="qv-progress-track">
        <motion.div
          className="qv-progress-fill"
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>

      {/* ── 3. Survey panel ── */}
      <div className="qv-survey-panel">
        <div className="qv-inner">

          {/* Step meta */}
          <div className="qv-step-meta">
            {surveyStep > 0 && (
              <button className="qv-back-btn" onClick={handleBack} aria-label="Back">
                <ChevronLeft size={14} />
                Back
              </button>
            )}
            <span className="qv-step-pill">
              Step {surveyStep + 1} of {STEPS.length}
            </span>
          </div>

          {/* Question + cards */}
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={surveyStep}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="qv-question-block"
            >
              <div className="qv-question-head">
                <p className="qv-hero-heading">I'll help you find your perfect fragrance</p>
                <h1 className="qv-question">{step.question}</h1>
                <div className="qv-progress-dots">
                  {STEPS.map((_, i) => (
                    <span key={i} className={`qv-dot ${i <= surveyStep ? 'qv-dot-active' : ''}`} />
                  ))}
                </div>
              </div>

              <div className={`qv-options ${colClass}`}>
                {step.options.map(opt => {
                  const isSel = selected === opt.value
                  const OptionIcon = opt.icon
                  return (
                    <motion.button
                      key={opt.value}
                      className={`qv-card ${isSel ? 'qv-card-selected' : ''} ${pending && !isSel ? 'qv-card-dimmed' : ''}`}
                      onClick={() => handleSelect(opt.value)}
                      disabled={pending}
                      animate={isSel ? { scale: 1.03 } : { scale: 1 }}
                      whileHover={!pending ? { y: -3, scale: 1.03 } : {}}
                      whileTap={!pending ? { scale: 0.98 } : {}}
                      transition={{ duration: 0.16 }}
                    >
                      <span className="qv-card-icon">
                        <OptionIcon size={24} strokeWidth={1.8} />
                      </span>
                      {/* Text group — allows horizontal layout on mobile */}
                      <span className="qv-card-text-group">
                        <span className="qv-card-label">{opt.label}</span>
                        <span className="qv-card-sub">{opt.sub}</span>
                      </span>
                      <AnimatePresence>
                        {isSel && (
                          <motion.div
                            className="qv-card-check"
                            initial={{ scale: 0, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0, opacity: 0 }}
                            transition={{ type: 'spring', stiffness: 500, damping: 24 }}
                          >
                            <Check size={10} strokeWidth={2.4} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.button>
                  )
                })}
              </div>

              {/* Continue button */}
              <button 
                className="qv-continue-btn" 
                onClick={() => selected && advance(selected)}
                disabled={!selected || pending}
              >
                Continue →
              </button>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* ── 4. Context bridge ── */}
      <AnimatePresence>
        {bridgeTags.length > 0 && (
          <motion.div
            className="qv-bridge"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <span className="qv-bridge-label">Based on your selection</span>
            <div className="qv-bridge-tags">
              {bridgeTags.map(tag => (
                <span key={tag} className="qv-bridge-tag">{tag}</span>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── 5. Curated carousel ── */}
      <TopPicks onOpenModal={openModal} />

    </div>
  )
}

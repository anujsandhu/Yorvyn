import { useState } from 'react'
import { X, Sparkles, ArrowRight, ArrowLeft } from 'lucide-react'
import { Logo } from './Logo'
import '../styles/QuizModal.css'

interface QuizModalProps {
  onClose: () => void
  onSubmitPreferences: (payload: {
    prompt: string
    gender: string
    scent: string
    occasion: string
  }) => void
}

export function QuizModal({ onClose, onSubmitPreferences }: QuizModalProps) {
  const [step, setStep] = useState(1)
  const [answers, setAnswers] = useState({
    gender: '',
    scent: '',
    occasion: '',
  })

  const handleNext = (key: string, value: string) => {
    const newAnswers = { ...answers, [key]: value }
    setAnswers(newAnswers)
    
    if (step < 3) {
      setStep(step + 1)
    } else {
      const prompt = `I am looking for a ${newAnswers.gender} fragrance. I prefer ${newAnswers.scent} notes. It should be suitable for ${newAnswers.occasion}.`
      onSubmitPreferences({
        prompt,
        gender: newAnswers.gender,
        scent: newAnswers.scent,
        occasion: newAnswers.occasion,
      })
      onClose()
    }
  }

  return (
    <div className="quiz-overlay" onClick={onClose}>
      <div className="quiz-panel yb-mist-ui" onClick={e => e.stopPropagation()}>
        <button className="quiz-x" onClick={onClose}><X size={24} /></button>

        <div className="quiz-header">
          <Sparkles size={20} color="var(--yb-pink)" />
          <Logo size="sm" />
          <div className="quiz-progress">
            <div className={`q-dot ${step >= 1 ? 'active' : ''}`} />
            <div className={`q-dot ${step >= 2 ? 'active' : ''}`} />
            <div className={`q-dot ${step >= 3 ? 'active' : ''}`} />
          </div>
        </div>

        <div className="quiz-body">
          {step === 1 && (
            <div className="q-step fade-in">
              <h3>Who are you shopping for?</h3>
              <div className="q-options">
                {['Men', 'Women', 'Unisex'].map(opt => (
                  <button key={opt} className="q-opt-btn" onClick={() => handleNext('gender', opt)}>
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="q-step fade-in">
              <button className="q-back" onClick={() => setStep(1)}><ArrowLeft size={16}/> Back</button>
              <h3>What kind of scent do you love?</h3>
              <div className="q-options grid-2">
                {[
                  { label: 'Fresh & Citrus', desc: 'Ocean breeze, lemon, bergamot' },
                  { label: 'Floral & Sweet', desc: 'Rose, jasmine, vanilla' },
                  { label: 'Woody & Earthy', desc: 'Sandalwood, cedar, vetiver' },
                  { label: 'Oriental & Spicy', desc: 'Amber, musk, cinnamon' },
                ].map(opt => (
                  <button key={opt.label} className="q-opt-btn col" onClick={() => handleNext('scent', opt.label)}>
                    <span className="o-title">{opt.label}</span>
                    <span className="o-desc">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="q-step fade-in">
              <button className="q-back" onClick={() => setStep(2)}><ArrowLeft size={16}/> Back</button>
              <h3>When will you wear this?</h3>
              <div className="q-options">
                {['Daily Office Wear', 'Date Night', 'Casual Weekends', 'Special Events / Parties'].map(opt => (
                  <button key={opt} className="q-opt-btn" onClick={() => handleNext('occasion', opt)}>
                    {opt} <ArrowRight size={16} />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

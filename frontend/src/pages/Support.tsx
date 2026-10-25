import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mail, Github, Linkedin, Instagram, MessageSquare,
  Bug, Lightbulb, Heart, ChevronDown, ChevronUp,
  ExternalLink, Send, CheckCircle, Star,
} from 'lucide-react'
import { Logo } from '../components/Logo'
import './Support.css'

// ── Developer info ────────────────────────────────────────────────────
const DEV = {
  name: 'Anuj Sandhu',
  role: 'Full-Stack Developer & AI Engineer',
  bio: 'Building Yorvyn to make personal styling smarter, more accessible, and more intuitive. Passionate about AI, design, and personalized aesthetics.',
  email: 'anujsandhu.dev@gmail.com',
  github: 'https://github.com/anujsandhu',
  linkedin: 'https://linkedin.com/in/anujsandhu',
  instagram: 'https://instagram.com/anujsandhu.dev',
}

// ── FAQ ───────────────────────────────────────────────────────────────
const FAQS = [
  {
    q: 'How does Yorvyn\'s AI work?',
    a: 'Yorvyn uses a multi-objective fashion intelligence engine combining color harmony theory, thermal comfort matrices, silhouette geometry, and personal style aesthetics with conversational AI. Your wardrobe, lifestyle, and occasions are evaluated together to curate tailored ensembles.',
  },
  {
    q: 'Is my data private?',
    a: 'Yes. Your digital wardrobe, style preferences, and session history are stored securely under your account in Firebase Firestore. We never sell or share your data with third parties. You can manage or delete your data at any time from your profile.',
  },
  {
    q: 'How do I get better outfit recommendations?',
    a: 'Keep your Digital Wardrobe updated with your staple pieces, set your color season and body geometry in your Personal Profile, and mention details like destination, weather, or dress code in the AI Stylist chat.',
  },
  {
    q: 'Can I use Yorvyn offline?',
    a: 'Yorvyn is a Progressive Web App (PWA). You can install it on your phone or desktop for a native app experience. Basic wardrobe browsing works offline; AI styling recommendations require an active connection.',
  },
  {
    q: 'How do I install Yorvyn as an app?',
    a: 'On mobile: tap the Share button in your browser and select "Add to Home Screen". On desktop Chrome: click the install icon in the address bar. You\'ll get a full-screen app experience with no browser UI.',
  },
  {
    q: 'How does the 3D Digital Twin work?',
    a: 'The Avatar Studio lets you customize parametric body geometry, drape outfits in real-time, test silhouette proportions, and visualize layer interactions before wearing them in real life.',
  },
]

// ── Suggested features ────────────────────────────────────────────────
const SUGGESTIONS = [
  'Smart capsule wardrobe generator',
  'Seasonal wardrobe rotation assistant',
  'Weather-aware morning outfit alerts',
  'Virtual try-on photo upload',
  'Fabric texture & drape simulation',
  'Sustainable cost-per-wear tracker',
  'Occasion lookbook planner',
  'Color season undertone scanner',
]

type FormType = 'feedback' | 'bug' | 'feature' | null

function FeedbackForm({ type, onClose }: { type: FormType; onClose: () => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [rating, setRating] = useState(0)
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(false)

  const config = {
    feedback: { title: 'Share Feedback', icon: <MessageSquare size={18} />, placeholder: 'Tell us what you think about Yorvyn...', subject: 'Yorvyn Feedback' },
    bug: { title: 'Report a Bug', icon: <Bug size={18} />, placeholder: 'Describe the issue: what happened, what you expected, and steps to reproduce...', subject: 'Yorvyn Bug Report' },
    feature: { title: 'Suggest a Feature', icon: <Lightbulb size={18} />, placeholder: 'Describe the feature you\'d love to see in Yorvyn...', subject: 'Yorvyn Feature Request' },
  }[type!]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim()) return
    setSending(true)
    // Build mailto link as fallback (no backend needed)
    const body = encodeURIComponent(
      `Name: ${name || 'Anonymous'}\nEmail: ${email || 'Not provided'}\nRating: ${rating ? `${rating}/5` : 'Not rated'}\n\n${message}`
    )
    window.open(`mailto:${DEV.email}?subject=${encodeURIComponent(config!.subject)}&body=${body}`)
    await new Promise(r => setTimeout(r, 600))
    setSending(false)
    setSent(true)
  }

  if (sent) {
    return (
      <motion.div className="sp-form-success" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
        <CheckCircle size={36} className="sp-success-icon" />
        <h3>Thank you!</h3>
        <p>Your {type} has been sent. We read every message and will get back to you if needed.</p>
        <button className="sp-btn-primary" onClick={onClose}>Done</button>
      </motion.div>
    )
  }

  return (
    <motion.form
      className="sp-form"
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="sp-form-header">
        <span className="sp-form-icon">{config!.icon}</span>
        <h3>{config!.title}</h3>
        <button type="button" className="sp-form-close" onClick={onClose}>✕</button>
      </div>

      {type === 'feedback' && (
        <div className="sp-rating-row">
          <span className="sp-rating-label">Overall rating</span>
          <div className="sp-stars">
            {[1,2,3,4,5].map(n => (
              <button key={n} type="button" onClick={() => setRating(n)}>
                <Star size={20} fill={n <= rating ? 'currentColor' : 'none'} className={n <= rating ? 'sp-star-on' : 'sp-star-off'} />
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="sp-form-row">
        <input className="sp-input" type="text" placeholder="Your name (optional)" value={name} onChange={e => setName(e.target.value)} />
        <input className="sp-input" type="email" placeholder="Your email (optional)" value={email} onChange={e => setEmail(e.target.value)} />
      </div>
      <textarea
        className="sp-textarea"
        placeholder={config!.placeholder}
        value={message}
        onChange={e => setMessage(e.target.value)}
        rows={5}
        required
      />
      <button className="sp-btn-primary" type="submit" disabled={sending || !message.trim()}>
        <Send size={14} />
        {sending ? 'Opening email…' : 'Send'}
      </button>
      <p className="sp-form-note">This will open your email client pre-filled with your message.</p>
    </motion.form>
  )
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`sp-faq-item ${open ? 'sp-faq-open' : ''}`}>
      <button className="sp-faq-q" onClick={() => setOpen(v => !v)}>
        <span>{q}</span>
        {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="sp-faq-a"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <p>{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function SupportPage() {
  const [activeForm, setActiveForm] = useState<FormType>(null)

  return (
    <div className="sp-root">

      {/* ── Hero ── */}
      <div className="sp-hero">
        <Logo size="xl" />
        <h1 className="sp-hero-title">Support & About</h1>
        <p className="sp-hero-sub">Get help, share feedback, or learn more about Yorvyn and the team behind it.</p>
      </div>

      {/* ── Contact actions ── */}
      <section className="sp-section">
        <h2 className="sp-section-title">Get in Touch</h2>
        <div className="sp-action-grid">
          <button className="sp-action-card" onClick={() => setActiveForm('feedback')}>
            <span className="sp-action-icon sp-icon-purple"><MessageSquare size={18} /></span>
            <span className="sp-action-label">Share Feedback</span>
            <span className="sp-action-sub">Tell us what you love or what could be better</span>
          </button>
          <button className="sp-action-card" onClick={() => setActiveForm('bug')}>
            <span className="sp-action-icon sp-icon-red"><Bug size={18} /></span>
            <span className="sp-action-label">Report a Bug</span>
            <span className="sp-action-sub">Found a UI issue or something broken?</span>
          </button>
          <button className="sp-action-card" onClick={() => setActiveForm('feature')}>
            <span className="sp-action-icon sp-icon-amber"><Lightbulb size={18} /></span>
            <span className="sp-action-label">Suggest a Feature</span>
            <span className="sp-action-sub">What would make Yorvyn even better?</span>
          </button>
          <a className="sp-action-card" href={`mailto:${DEV.email}`}>
            <span className="sp-action-icon sp-icon-blue"><Mail size={18} /></span>
            <span className="sp-action-label">Email Directly</span>
            <span className="sp-action-sub">{DEV.email}</span>
          </a>
        </div>
      </section>

      {/* ── Form modal ── */}
      <AnimatePresence>
        {activeForm && (
          <>
            <motion.div className="sp-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setActiveForm(null)} />
            <motion.div className="sp-modal" initial={{ opacity: 0, y: 20, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 20, scale: 0.97 }} transition={{ duration: 0.2 }}>
              <FeedbackForm type={activeForm} onClose={() => setActiveForm(null)} />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Developer ── */}
      <section className="sp-section">
        <h2 className="sp-section-title">Meet the Developer</h2>
        <div className="sp-dev-card">
          <div className="sp-dev-avatar">AS</div>
          <div className="sp-dev-info">
            <h3 className="sp-dev-name">{DEV.name}</h3>
            <p className="sp-dev-role">{DEV.role}</p>
            <p className="sp-dev-bio">{DEV.bio}</p>
            <div className="sp-dev-links">
              <a href={DEV.github} target="_blank" rel="noopener noreferrer" className="sp-dev-link">
                <Github size={16} /> GitHub <ExternalLink size={11} />
              </a>
              <a href={DEV.linkedin} target="_blank" rel="noopener noreferrer" className="sp-dev-link">
                <Linkedin size={16} /> LinkedIn <ExternalLink size={11} />
              </a>
              <a href={DEV.instagram} target="_blank" rel="noopener noreferrer" className="sp-dev-link">
                <Instagram size={16} /> Instagram <ExternalLink size={11} />
              </a>
              <a href={`mailto:${DEV.email}`} className="sp-dev-link">
                <Mail size={16} /> Email <ExternalLink size={11} />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ── Suggested features ── */}
      <section className="sp-section">
        <h2 className="sp-section-title">Coming Soon — Vote for Features</h2>
        <p className="sp-section-desc">These are features we're considering. Send us a feature request to vote for your favourite!</p>
        <div className="sp-suggestions">
          {SUGGESTIONS.map((s, i) => (
            <motion.div
              key={s}
              className="sp-suggestion"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <Heart size={13} className="sp-suggestion-icon" />
              <span>{s}</span>
            </motion.div>
          ))}
        </div>
        <button className="sp-btn-outline" onClick={() => setActiveForm('feature')}>
          <Lightbulb size={14} /> Suggest your own feature
        </button>
      </section>

      {/* ── FAQ ── */}
      <section className="sp-section">
        <h2 className="sp-section-title">Frequently Asked Questions</h2>
        <div className="sp-faq-list">
          {FAQS.map(f => <FaqItem key={f.q} q={f.q} a={f.a} />)}
        </div>
      </section>

      {/* ── About ── */}
      <section className="sp-section">
        <h2 className="sp-section-title">About Yorvyn</h2>
        <div className="sp-about-card">
          <Logo size="lg" className="sp-about-logo" />
          <div>
            <p className="sp-about-text">
              Yorvyn is your personal AI stylist for discovering outfits, organizing your digital wardrobe, and exploring your individual style. Powered by multi-objective outfit scoring, color harmony algorithms, and a customizable fictional 3D avatar twin, Yorvyn helps you assemble cohesive ensembles for every occasion and climate.
            </p>
            <p className="sp-about-text">
              Built with React, FastAPI, Python, and Firebase. Powered by high-curation fashion intelligence and modern generative AI.
            </p>
            <div className="sp-about-badges">
              <span className="sp-badge">Personal AI Stylist</span>
              <span className="sp-badge">Digital Wardrobe</span>
              <span className="sp-badge">3D Digital Twin</span>
              <span className="sp-badge">Outfit Scoring</span>
              <span className="sp-badge">PWA</span>
            </div>
          </div>
        </div>
      </section>

      <p className="sp-footer">Made with <Heart size={12} className="sp-footer-heart" /> by {DEV.name} · © 2026 Yorvyn</p>
    </div>
  )
}

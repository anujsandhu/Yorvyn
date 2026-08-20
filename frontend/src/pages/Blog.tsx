import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Clock, Tag, ArrowLeft } from 'lucide-react'
import './Blog.css'

interface Post {
  slug: string
  title: string
  excerpt: string
  category: string
  readTime: number
  date: string
  tags: string[]
  body: string[]
}

const POSTS: Post[] = [
  {
    slug: 'how-to-choose-perfume',
    title: 'How to Choose the Perfect Perfume for Your Personality',
    excerpt: 'Finding a fragrance that truly represents you is an art. Learn how to match perfume notes to your personality, lifestyle, and occasions.',
    category: 'Fragrance Guide',
    readTime: 5,
    date: '2026-04-15',
    tags: ['perfume guide', 'fragrance tips', 'how to choose perfume'],
    body: [
      '## Understanding Fragrance Families',
      'Every perfume belongs to a fragrance family — a broad category that describes its dominant character.',
      '**Floral** — Rose, jasmine, peony. Romantic, feminine, timeless.',
      '**Woody** — Sandalwood, cedar, oud. Warm, grounding, sophisticated.',
      '**Fresh / Citrus** — Bergamot, lemon, grapefruit. Clean, energetic, uplifting.',
      '**Oriental / Amber** — Vanilla, musk, amber. Sensual, warm, mysterious.',
      '**Gourmand** — Caramel, chocolate, coffee. Sweet, playful, comforting.',
      '## Match Your Personality',
      'If you are bold and confident — reach for woody or oriental fragrances. Oud, leather, and smoky notes project strength.',
      'If you are romantic and creative — floral bouquets with rose, iris, or peony suit you perfectly.',
      'If you are minimalist and clean — fresh aquatic or citrus scents mirror your aesthetic.',
      '## Consider the Occasion',
      'A fragrance for daily office wear should be subtle — think light musks or soft florals. For a date night, reach for something warmer and more sensual.',
      '## The Sillage Factor',
      'Sillage is the trail a perfume leaves. Light sillage is polite for professional settings; heavy sillage makes a statement at parties.',
      '## Try Before You Buy',
      'Always test a fragrance on your skin — not paper. Your skin chemistry changes how a perfume smells. Let it dry down for 30 minutes before deciding.',
    ],
  },
  {
    slug: 'best-perfumes-india-2026',
    title: 'Best Perfumes Available in India 2026 — AI Ranked',
    excerpt: 'Our AI analysed 73,000+ fragrances to find the best perfumes available in India across every budget, from ₹500 to ₹50,000.',
    category: 'Top Lists',
    readTime: 7,
    date: '2026-04-20',
    tags: ['best perfume india', 'perfume 2026', 'top fragrances'],
    body: [
      '## How We Ranked These Perfumes',
      'Yorvyn\'s AI model analyses community ratings, fragrance notes, longevity, sillage, and value for money across 73,000+ perfumes.',
      '## Under ₹2,000',
      '**Fogg Scent Xpressio** — Fresh, clean, long-lasting. Perfect for daily office wear.',
      '**Engage Cologne Spray** — Light citrus with a woody dry-down. Great value.',
      '**Wild Stone Code Titanium** — Aquatic and fresh. Popular for gym and casual wear.',
      '## ₹2,000 – ₹8,000',
      '**Davidoff Cool Water** — The classic aquatic. Timeless and universally loved.',
      '**Versace Eros** — Mint, vanilla, and tonka bean. Bold and confident.',
      '**Dior Sauvage EDT** — Bergamot and ambroxan. The best-selling men\'s fragrance globally.',
      '## ₹8,000 – ₹20,000',
      '**Chanel Chance Eau Tendre** — Grapefruit, jasmine, white musk. Feminine and fresh.',
      '**Tom Ford Oud Wood** — Oud, rosewood, cardamom. Luxurious and distinctive.',
      '**YSL Black Opium** — Coffee, vanilla, white flowers. Addictive and modern.',
      '## Premium (₹20,000+)',
      '**Creed Aventus** — Pineapple, birch, musk. The ultimate power fragrance.',
      '**Maison Margiela Replica Jazz Club** — Rum, tobacco, vetiver. Unique and memorable.',
    ],
  },
  {
    slug: 'oud-perfume-guide',
    title: 'The Complete Guide to Oud Perfumes — History, Notes & Best Picks',
    excerpt: 'Oud is the most expensive raw material in perfumery. Discover its history, how it smells, and the best oud fragrances for every budget.',
    category: 'Ingredient Deep Dive',
    readTime: 6,
    date: '2026-04-25',
    tags: ['oud perfume', 'oud fragrance', 'best oud perfume', 'agarwood'],
    body: [
      '## What is Oud?',
      'Oud (also called agarwood or oudh) is a resinous heartwood that forms in Aquilaria trees when they become infected with a specific mould. It takes decades to produce quality oud, which is why it commands prices of up to $100,000 per kilogram.',
      '## How Does Oud Smell?',
      'Oud is complex and polarising. It can smell woody and earthy, smoky and leathery, sweet and balsamic, or even medicinal. The smell varies by origin: Indian oud is dark and smoky; Cambodian oud is sweet and fruity; Thai oud is clean and woody.',
      '## Best Oud Perfumes by Budget',
      '**Arabian Oud Kalemat** — Sweet, warm, accessible. Under ₹3,000.',
      '**Tom Ford Oud Wood** — The gateway oud for Western noses. ₹3,000–₹15,000.',
      '**Amouage Interlude Man** — Complex, smoky, unforgettable. Luxury tier.',
      '**Roja Dove Amber Aoud** — The pinnacle of oud perfumery.',
    ],
  },
  {
    slug: 'perfume-longevity-tips',
    title: '10 Tips to Make Your Perfume Last All Day',
    excerpt: 'Frustrated that your perfume fades within hours? These science-backed tips will dramatically improve your fragrance longevity.',
    category: 'Tips & Tricks',
    readTime: 4,
    date: '2026-05-01',
    tags: ['perfume longevity', 'make perfume last longer', 'fragrance tips'],
    body: [
      '## Why Perfume Fades',
      'Fragrance molecules evaporate at different rates. Top notes last 15–30 minutes. Heart notes last 2–4 hours. Base notes can last 6–12 hours or more.',
      '## 10 Proven Tips',
      '**1. Moisturise first** — Fragrance clings to hydrated skin. Apply unscented lotion before your perfume.',
      '**2. Target pulse points** — Wrists, neck, behind ears, inner elbows. These areas emit heat that amplifies the scent.',
      '**3. Do not rub** — Rubbing breaks down fragrance molecules. Spray and let it dry naturally.',
      '**4. Layer your fragrance** — Use matching shower gel and body lotion from the same fragrance line.',
      '**5. Spray on clothes** — Fabric holds fragrance longer than skin.',
      '**6. Store correctly** — Keep perfume away from heat, light, and humidity.',
      '**7. Choose the right concentration** — EDP lasts longer than EDT. Parfum lasts longest.',
      '**8. Apply after showering** — Open pores absorb fragrance better.',
      '**9. Spray from distance** — Hold the bottle 15–20cm away for even distribution.',
      '**10. Reapply strategically** — Carry a travel-size bottle for touch-ups.',
    ],
  },
]

function renderLine(line: string, i: number) {
  if (line.startsWith('## ')) return <h2 key={i} className="blog-body-h2">{line.slice(3)}</h2>
  const parts = line.split(/(\*\*[^*]+\*\*)/)
  return (
    <p key={i} className="blog-body-p">
      {parts.map((p, j) =>
        p.startsWith('**') && p.endsWith('**')
          ? <strong key={j}>{p.slice(2, -2)}</strong>
          : p
      )}
    </p>
  )
}

function PostCard({ post, onOpen }: { post: Post; onOpen: () => void }) {
  return (
    <motion.article
      className="blog-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onOpen()}
    >
      <span className="blog-card-cat">{post.category}</span>
      <h2 className="blog-card-title">{post.title}</h2>
      <p className="blog-card-excerpt">{post.excerpt}</p>
      <div className="blog-card-meta">
        <span>{new Date(post.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
        <span className="blog-card-dot">·</span>
        <Clock size={11} />
        <span>{post.readTime} min read</span>
      </div>
      <div className="blog-card-tags">
        {post.tags.slice(0, 3).map(t => (
          <span key={t} className="blog-tag"><Tag size={9} />{t}</span>
        ))}
      </div>
      <span className="blog-card-cta">Read article <ArrowRight size={13} /></span>
    </motion.article>
  )
}

function PostView({ post, onBack }: { post: Post; onBack: () => void }) {
  return (
    <motion.div
      className="blog-post"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <button className="blog-back-btn" onClick={onBack}>
        <ArrowLeft size={14} /> Back to Blog
      </button>
      <span className="blog-post-cat">{post.category}</span>
      <h1 className="blog-post-title">{post.title}</h1>
      <div className="blog-post-meta">
        <span>{new Date(post.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
        <span>·</span>
        <span><Clock size={12} /> {post.readTime} min read</span>
        <span>·</span>
        <span>By Anuj Sandhu</span>
      </div>
      <p className="blog-post-lead">{post.excerpt}</p>
      <div className="blog-post-body">
        {post.body.map((line, i) => renderLine(line, i))}
      </div>
      <div className="blog-post-tags">
        {post.tags.map(t => <span key={t} className="blog-tag"><Tag size={9} />{t}</span>)}
      </div>
    </motion.div>
  )
}

export function BlogPage() {
  const [open, setOpen] = useState<Post | null>(null)

  return (
    <div className="blog-root">
      {open ? (
        <PostView post={open} onBack={() => setOpen(null)} />
      ) : (
        <>
          <div className="blog-hero">
            <h1 className="blog-hero-title">Fragrance Journal</h1>
            <p className="blog-hero-sub">Guides, tips, and deep dives into the world of perfumery — curated by Yorvyn's AI.</p>
          </div>
          <div className="blog-grid">
            {POSTS.map(p => (
              <PostCard key={p.slug} post={p} onOpen={() => setOpen(p)} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

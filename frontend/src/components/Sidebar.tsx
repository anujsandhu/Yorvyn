import {
  Heart, Trash2, X, LogOut, Settings, Sliders,
  MoreHorizontal, User,
  HelpCircle, BookOpen,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useApp } from '../context/AppContext'
import { useAuth } from '../context/AuthContext'
import { WishlistItem } from '../store/index'
import toast from 'react-hot-toast'
import { Logo } from './Logo'
import './Sidebar.css'

// ── Account block (3-dot menu) ────────────────────────────────────────
// ── Account block (dropdown menu only) ───────────────────────────────
function AccountBlock() {
  const { user, signOut } = useAuth()
  const { userProfile, setSidebarOpen } = useApp()
  const [open, setOpen] = useState(false)

  const googleName = user?.displayName || 'Yorvyn user'
  const name    = userProfile.nickname || googleName
  const email   = user?.email || 'Signed in'
  const initial = (name || email || 'Y').charAt(0).toUpperCase()

  const handleSignOut = async () => {
    setOpen(false)
    setSidebarOpen(false)
    await signOut()
    toast.success('Signed out')
  }

  const handleMenuAction = (action: string) => {
    setOpen(false)
    // TODO: Implement navigation to these pages
    // For now, show a toast
    toast(`${action} - Coming soon`, { duration: 2000 })
  }

  return (
    <div className="sb-account-block">
      <AnimatePresence>
        {open && (
          <>
            {/* click-away */}
            <div className="sb-menu-backdrop" onClick={() => setOpen(false)} />
            <motion.div
              className="sb-account-menu"
              initial={{ opacity: 0, y: 8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.97 }}
              transition={{ duration: 0.14 }}
            >
              <button onClick={() => handleMenuAction('Profile')}>
                <User size={14} />
                <span>Profile</span>
              </button>
              <button onClick={() => handleMenuAction('Personalization')}>
                <Sliders size={14} />
                <span>Personalization</span>
              </button>
              <button onClick={() => handleMenuAction('Settings')}>
                <Settings size={14} />
                <span>Settings</span>
              </button>
              <div className="sb-menu-divider" />
              <button onClick={() => handleMenuAction('Fragrance Journal')}>
                <BookOpen size={14} />
                <span>Fragrance Journal</span>
              </button>
              <button onClick={() => handleMenuAction('Support & About')}>
                <HelpCircle size={14} />
                <span>Support & About</span>
              </button>
              <div className="sb-menu-divider" />
              <button className="sb-menu-danger" onClick={handleSignOut}>
                <LogOut size={14} />
                <span>Sign out</span>
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <button className="sb-account-btn" onClick={() => setOpen(v => !v)}>
        <span className="sb-account-avatar">
          {user?.photoURL
            ? <img src={user.photoURL} alt={name} referrerPolicy="no-referrer" onError={e => { (e.target as HTMLImageElement).style.display = 'none'; (e.target as HTMLImageElement).parentElement!.querySelector('.sb-avatar-fallback')?.classList.add('sb-avatar-fallback-visible'); }} />
            : null
          }
          <span className="sb-avatar-fallback" style={user?.photoURL ? { display: 'none' } : undefined}>{initial}</span>
        </span>
        <span className="sb-account-info">
          <span className="sb-account-name">{name}</span>
          <span className="sb-account-email">{email}</span>
        </span>
        <MoreHorizontal size={16} />
      </button>
    </div>
  )
}

// ── Shared inner content ──────────────────────────────────────────────
function SidebarContent({
  isDrawer,
}: {
  isDrawer: boolean
  collapsed: boolean
  onToggleCollapse: () => void
  uiScale: number
  onUiScaleChange: (v: number) => void
}) {
  const {
    wishlist, toggleWishlist, openModal,
    setSidebarOpen,
    chatSummaries, openChat, deleteChat,
  } = useApp()

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; title: string } | null>(null)

  const handleWishlistOpen = (item: WishlistItem) => {
    setSidebarOpen(false)
    openModal({
      id: item.id, name: item.name, brand: item.brand,
      family: '', rating: item.rating, price: 0,
      image_url: item.image_url, accords: item.accords,
    })
  }

  const handleDeleteChat = async (chatId: string) => {
    setConfirmDelete(null)
    setDeletingId(chatId)
    await deleteChat(chatId)
    setDeletingId(null)
    toast.success('Chat deleted', { duration: 1500 })
  }

  // Group chats by date
  const groupedChats = chatSummaries.reduce((acc, chat) => {
    const date = new Date(chat.updatedAt)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    let group = 'Earlier'
    if (date.toDateString() === today.toDateString()) {
      group = 'Today'
    } else if (date.toDateString() === yesterday.toDateString()) {
      group = 'Yesterday'
    }

    if (!acc[group]) acc[group] = []
    acc[group].push(chat)
    return acc
  }, {} as Record<string, typeof chatSummaries>)

  return (
    <div className="sb-content">
      {/* Top Area: Logo */}
      <div className="sb-top">
        <div className="sb-logo">
          <Logo size="sm" />
        </div>
        {isDrawer && (
          <button className="sb-close-btn" onClick={() => setSidebarOpen(false)} aria-label="Close">
            <X size={16} />
          </button>
        )}
      </div>

      {/* Main Section: Conversations */}
      <div className="sb-main">
        <div className="sb-section-label">Conversations</div>
        
        {chatSummaries.length === 0 ? (
          <div className="sb-empty-state">
            <p>No conversations yet</p>
            <span>Start a new search to begin</span>
          </div>
        ) : (
          <>
            {['Today', 'Yesterday', 'Earlier'].map(group => {
              const chats = groupedChats[group]
              if (!chats || chats.length === 0) return null
              
              return (
                <div key={group} className="sb-chat-group">
                  <div className="sb-group-label">{group}</div>
                  {chats.map(chat => (
                    <div key={chat.id} className={`sb-chat-item ${deletingId === chat.id ? 'sb-item-deleting' : ''}`}>
                      <button className="sb-chat-btn" onClick={() => openChat(chat.id)}>
                        <span className="sb-chat-title">{chat.title}</span>
                      </button>
                      <button
                        className="sb-chat-delete"
                        onClick={e => { e.stopPropagation(); setConfirmDelete({ id: chat.id, title: chat.title }) }}
                        aria-label="Delete chat"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )
            })}
          </>
        )}
      </div>

      {/* Favorites Section */}
      <div className="sb-favorites">
        <div className="sb-section-label">
          <Heart size={12} />
          <span>Favorites</span>
        </div>
        
        {wishlist.length === 0 ? (
          <div className="sb-empty-state sb-empty-compact">
            <span>No saved perfumes</span>
          </div>
        ) : (
          <div className="sb-fav-list">
            {wishlist.slice(0, 5).map(item => (
              <div key={item.id} className="sb-fav-item">
                <button className="sb-fav-btn" onClick={() => handleWishlistOpen(item)}>
                  <div className="sb-fav-img">
                    {item.image_url
                      ? <img src={item.image_url} alt={item.name} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      : <span>{item.brand.charAt(0)}</span>
                    }
                  </div>
                  <div className="sb-fav-info">
                    <span className="sb-fav-name">{item.name}</span>
                    <span className="sb-fav-brand">{item.brand}</span>
                  </div>
                </button>
                <button className="sb-fav-delete" onClick={() => toggleWishlist(item)} aria-label="Remove">
                  <X size={12} />
                </button>
              </div>
            ))}
            {wishlist.length > 5 && (
              <button className="sb-fav-more" onClick={() => toast('View all favorites - Coming soon', { duration: 2000 })}>
                View all {wishlist.length} favorites
              </button>
            )}
          </div>
        )}
      </div>

      {/* Bottom Area: User Profile */}
      <div className="sb-bottom">
        <AccountBlock />
      </div>

      {/* ── Delete confirm dialog ── */}
      <AnimatePresence>
        {confirmDelete && (
          <>
            <motion.div
              className="sb-confirm-backdrop"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setConfirmDelete(null)}
            />
            <motion.div
              className="sb-confirm-dialog"
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.16 }}
            >
              <div className="sb-confirm-icon">
                <Trash2 size={18} />
              </div>
              <p className="sb-confirm-title">Delete chat?</p>
              <p className="sb-confirm-sub">
                "<span>{confirmDelete.title.slice(0, 50)}{confirmDelete.title.length > 50 ? '…' : ''}</span>" will be permanently deleted.
              </p>
              <div className="sb-confirm-actions">
                <button className="sb-confirm-cancel" onClick={() => setConfirmDelete(null)}>
                  Cancel
                </button>
                <button className="sb-confirm-delete" onClick={() => handleDeleteChat(confirmDelete.id)}>
                  Delete
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Welcome toast ─────────────────────────────────────────────────────
function WelcomeToast() {
  const { user, isNewUser } = useAuth()
  const { userProfile } = useApp()
  const [hasShown, setHasShown] = useState(false)

  useEffect(() => {
    if (!user || hasShown) return
    setHasShown(true)
    const name = userProfile.nickname || user.displayName?.split(' ')[0] || 'there'
    if (isNewUser) {
      toast.success(`Welcome to Yorvyn, ${name}! 🌸 Let's find your perfect scent.`, { duration: 4000, icon: '✨' })
    } else {
      toast.success(`Welcome back, ${name}! 👋 Ready to explore more fragrances?`, { duration: 3500, icon: '🌸' })
    }
  }, [user, isNewUser, hasShown, userProfile.nickname])

  return null
}

// ── Main export ───────────────────────────────────────────────────────
export function Sidebar() {
  const { sidebarOpen, setSidebarOpen } = useApp()
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sb-collapsed') === '1' } catch { return false }
  })
  const [uiScale, setUiScale] = useState(() => {
    try { return parseFloat(localStorage.getItem('ui-scale') || '1') } catch { return 1 }
  })

  // Apply ui-scale to :root CSS variable
  useEffect(() => {
    document.documentElement.style.setProperty('--ui-scale', String(uiScale))
    try { localStorage.setItem('ui-scale', String(uiScale)) } catch {}
  }, [uiScale])

  const toggleCollapse = () => {
    setCollapsed(v => {
      const next = !v
      try { localStorage.setItem('sb-collapsed', next ? '1' : '0') } catch {}
      return next
    })
  }

  useEffect(() => {
    document.body.style.overflow = sidebarOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [sidebarOpen])

  return (
    <>
      <WelcomeToast />

      <aside className={`sb-static${collapsed ? ' sb-collapsed' : ''}`}>
        <SidebarContent
          isDrawer={false}
          collapsed={collapsed}
          onToggleCollapse={toggleCollapse}
          uiScale={uiScale}
          onUiScaleChange={setUiScale}
        />
      </aside>

      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              className="sb-backdrop"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setSidebarOpen(false)}
              aria-hidden="true"
            />
            <motion.aside
              className="sb-drawer"
              role="dialog" aria-modal="true" aria-label="Navigation menu"
              initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
              transition={{ type: 'tween', duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
            >
              <SidebarContent
                isDrawer={true}
                collapsed={false}
                onToggleCollapse={toggleCollapse}
                uiScale={uiScale}
                onUiScaleChange={setUiScale}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

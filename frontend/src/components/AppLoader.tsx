/**
 * AppLoader — full-screen loading state shown while Firebase auth initialises.
 * Uses the Logo component at xl size with a subtle pulse animation.
 */
import { motion } from 'framer-motion'
import { Logo } from './Logo'
import './AppLoader.css'

export function AppLoader() {
  return (
    <div className="al-root" role="status" aria-label="Loading Yorvyn">
      <motion.div
        className="al-logo-wrap"
        initial={{ opacity: 0, scale: 0.88 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Glow ring */}
        <motion.div
          className="al-glow"
          animate={{ scale: [1, 1.18, 1], opacity: [0.35, 0.6, 0.35] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />

        {/* Logo */}
        <Logo size="xl" className="al-logo" />
      </motion.div>

      {/* Dot loader */}
      <div className="al-dots" aria-hidden="true">
        {[0, 1, 2].map(i => (
          <motion.span
            key={i}
            className="al-dot"
            animate={{ opacity: [0.2, 1, 0.2], y: [0, -5, 0] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.18, ease: 'easeInOut' }}
          />
        ))}
      </div>
    </div>
  )
}

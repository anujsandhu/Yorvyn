import { AnimatePresence, motion } from 'framer-motion'
import { useApp } from '../context/AppContext'
import { QuizView } from './QuizView'
import { ResultsView } from './ResultsView'
import { ProductModal } from './ProductModal'
import './MainView.css'

export function MainView() {
  const { phase, modalPerfume, closeModal } = useApp()

  return (
    <div className="mv-root">
      <AnimatePresence mode="wait">
        {phase === 'quiz' && (
          <motion.div
            key="quiz"
            className="mv-pane"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <QuizView />
          </motion.div>
        )}

        {phase === 'results' && (
          <motion.div
            key="results"
            className="mv-pane"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <ResultsView />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {modalPerfume && (
          <ProductModal perfume={modalPerfume} onClose={closeModal} />
        )}
      </AnimatePresence>
    </div>
  )
}

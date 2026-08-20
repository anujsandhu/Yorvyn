import { useState, useEffect, useRef } from 'react'
import { Search, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../utils/api'
import { Perfume } from '../types'
import { ProductCard } from './ProductCard'
import { ProductModal } from './ProductModal'
import '../styles/SearchModal.css'

interface SearchModalProps {
  onClose: () => void
}

export function SearchModal({ onClose }: SearchModalProps) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Perfume[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selected, setSelected] = useState<Perfume | null>(null)

  useEffect(() => {
    // Focus the input when modal opens
    if (inputRef.current) inputRef.current.focus()
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim().length >= 2) {
        performSearch(query)
      } else {
        setResults([])
      }
    }, 400) // Debounce search
    return () => clearTimeout(timer)
  }, [query])

  const performSearch = async (searchQuery: string) => {
    setIsLoading(true)
    try {
      const res = await apiClient.searchPerfumes(searchQuery, 12)
      setResults(res.results || [])
    } catch (err) {
      console.error('Search failed', err)
      setResults([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      onClose()
      navigate(`/search?q=${encodeURIComponent(query)}`)
    }
  }

  return (
    <div className="search-overlay yb-mist-overlay" onClick={onClose}>
      <div className="search-panel yb-mist-ui" onClick={e => e.stopPropagation()}>
        
        {/* Header / Input Area */}
        <div className="sm-header">
           <form onSubmit={handleSubmit} className="sm-form">
             <Search size={24} className="sm-icon" />
             <input
               ref={inputRef}
               type="text"
               className="sm-input"
               placeholder="Search fragrances, occasions, or brands..."
               value={query}
               onChange={e => setQuery(e.target.value)}
             />
             {query && (
               <button type="button" className="sm-clear" onClick={() => setQuery('')}>
                 <X size={20} />
               </button>
             )}
           </form>
           <button className="sm-close-btn" onClick={onClose}><X size={28} /></button>
        </div>

        {/* Results Area */}
        <div className="sm-body">
          {isLoading ? (
            <div className="sm-loading">
               <SparklesLoader />
            </div>
          ) : results.length > 0 ? (
            <div className="yb-grid sm-grid">
              {results.map(p => (
                <ProductCard
                  key={p.id}
                  perfume={p}
                  onViewDetails={setSelected}
                />
              ))}
            </div>
          ) : query.length >= 2 ? (
            <div className="sm-empty">
              <p>No perfumes found. Try a different occasion or brand.</p>
            </div>
          ) : (
            <div className="sm-empty">
              <p>Start typing to discover scents...</p>
            </div>
          )}
        </div>
      </div>

      <ProductModal perfume={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

function SparklesLoader() {
  return <div className="spinner-border text-dark" role="status"><span className="visually-hidden">Loading...</span></div>
}

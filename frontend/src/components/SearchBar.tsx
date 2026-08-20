import { useState, useRef, useEffect } from 'react'
import { Search, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../utils/api'
import { Perfume } from '../types'
import '../styles/SearchBar.css'

interface SearchBarProps {
  onSelectPerfume?: (perfume: Perfume) => void
}

export function SearchBar({ onSelectPerfume }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Perfume[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      return
    }

    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await apiClient.searchPerfumes(query, 5)
        setResults(res.results || [])
        setOpen(true)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [query])

  // Click outside to close
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      setOpen(false)
      navigate(`/search?q=${encodeURIComponent(query)}`)
    }
  }

  const handleSelect = (perfume: Perfume) => {
    if (onSelectPerfume) {
      onSelectPerfume(perfume)
    } else {
      navigate(`/search?q=${encodeURIComponent(perfume.name)}`)
    }
    setOpen(false)
    setQuery('')
  }

  return (
    <div className="search-widget" ref={wrapperRef}>
      <form className="search-widget-form" onSubmit={handleSubmit}>
        <Search size={20} className="sm-icon" />
        <input
          type="text"
          value={query}
          onChange={e => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => {
            if (query.length >= 2) setOpen(true)
          }}
          placeholder="Search perfumes, brands, notes..."
        />
        {query && (
          <button type="button" className="sm-clear" onClick={() => setQuery('')}>
            <X size={18} />
          </button>
        )}
      </form>

      {open && query.length >= 2 && (
        <div className="search-dropdown">
          {loading && <div className="sm-loading">Searching...</div>}
          
          {!loading && results.length > 0 && (
            <div className="sm-list">
              {results.map(p => (
                <div key={p.id} className="sm-item" onClick={() => handleSelect(p)}>
                  <div className="sm-item-img">
                    {p.image_url ? (
                      <img src={p.image_url} alt="" />
                    ) : (
                      <span>{(p.brand || 'P').charAt(0)}</span>
                    )}
                  </div>
                  <div className="sm-item-info">
                    <div className="sm-item-name">{p.name}</div>
                    <div className="sm-item-brand">{p.brand}</div>
                  </div>
                </div>
              ))}
              <div 
                className="sm-see-all" 
                onClick={() => {
                  setOpen(false)
                  navigate(`/search?q=${encodeURIComponent(query)}`)
                }}
              >
                See all results for "{query}" ➔
              </div>
            </div>
          )}

          {!loading && results.length === 0 && (
             <div className="sm-empty">No results found</div>
          )}
        </div>
      )}
    </div>
  )
}

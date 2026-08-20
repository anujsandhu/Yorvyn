import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { apiClient } from '../utils/api'
import { Perfume } from '../types'
import { ProductCard } from '../components/ProductCard'
import { ProductModal } from '../components/ProductModal'
import { useLocation } from 'react-router-dom'
import './Search.css'

export function SearchPage() {
  const location = useLocation()
  const initialQuery = new URLSearchParams(location.search).get('q') || ''
  
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState<Perfume[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selected, setSelected] = useState<Perfume | null>(null)
  const [hasSearched, setHasSearched] = useState(false)

  useEffect(() => {
    if (initialQuery) {
      performSearch(initialQuery)
    }
  }, [initialQuery])

  const performSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return
    
    setIsLoading(true)
    setHasSearched(true)
    try {
      const res = await apiClient.searchPerfumes(searchQuery, 24)
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
    performSearch(query)
  }

  return (
    <div className="search-page">
      <div className="search-header">
        <div className="container">
          <h1>Find a <em>Fragrance</em></h1>
          <form onSubmit={handleSubmit} className="search-form-large">
            <Search size={24} className="search-icon" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search by name, brand, or notes (e.g. 'Dior', 'vanilla')..."
              autoFocus
            />
            <button type="submit" className="search-btn">Search</button>
          </form>
        </div>
      </div>

      <div className="container">
        {isLoading && (
          <div className="yb-grid mt-40">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="skeleton-card yb-card">
                <div className="yb-card-arch-container">
                  <div className="yb-card-arch skeleton" style={{ width: '100%', height: '300px', borderRadius: '200px 200px 0 0' }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {!isLoading && hasSearched && (
          <div className="search-results-container mt-40">
            <h2 className="results-count">
              Found {results.length} results for "{query}"
            </h2>
            
            {results.length > 0 ? (
              <div className="yb-grid">
                {results.map(p => (
                  <ProductCard
                    key={p.id}
                    perfume={p}
                    onViewDetails={setSelected}
                  />
                ))}
              </div>
            ) : (
              <div className="no-results-large">
                <p>No perfumes found matching your search.</p>
                <button onClick={() => setQuery('')} className="btn-clear">Clear Search</button>
              </div>
            )}
          </div>
        )}
      </div>

      <ProductModal perfume={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

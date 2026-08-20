import { Droplet, Wind, Feather } from 'lucide-react'
import { Perfume } from '../types'
import { buildAccordPreview, buildLocalPriceInfo } from '../utils/perfumeDisplay'
import '../styles/ProductCard.css'

interface ProductCardProps {
  perfume: Perfume
  onViewDetails: (perfume: Perfume) => void
  badge?: string
}

export function ProductCard({ perfume, onViewDetails, badge }: ProductCardProps) {
  const imgUrl = perfume.image_url
  const priceInfo = buildLocalPriceInfo(perfume.name, perfume.brand, perfume.price)

  return (
    <div className="yb-card">
      {/* Arch Background Container */}
      <div className="yb-card-arch-container">
        <div className="yb-card-arch">
          {/* Badge */}
          {badge && (
            <div className="yb-card-badge">
              {badge}
            </div>
          )}

          {/* Image */}
          <div className="yb-card-image">
            {imgUrl && imgUrl !== 'Unknown' ? (
              <img src={imgUrl} alt={perfume.name} loading="lazy" />
            ) : (
              <div className="yb-card-placeholder">
                <span>{(perfume.brand || 'A').charAt(0)}</span>
              </div>
            )}
          </div>

          {/* Mini overlay icons (like the yellow/purple/green in screenshot) */}
          <div className="yb-card-mini-icons">
            <div className="yb-mini-icon" style={{ background: '#ffd54f' }}><Droplet size={12} color="#fff" /></div>
            <div className="yb-mini-icon" style={{ background: '#ba68c8' }}><Wind size={12} color="#fff" /></div>
            <div className="yb-mini-icon" style={{ background: '#2e7d32' }}><Feather size={12} color="#fff" /></div>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="yb-card-body">
        <p className="yb-card-brand">{perfume.brand}</p>
        <h3 className="yb-card-title">{perfume.name}</h3>
        <p className="yb-card-desc">
          {buildAccordPreview(perfume.accords, perfume.family)}
        </p>

        {/* Pricing */}
        <div className="yb-card-pricing">
           <span className="yb-price-old">{priceInfo.originalPriceInr}</span>
           <span className="yb-price-new">From {priceInfo.discountedPriceInr}</span>
           <div className="yb-price-tax">Inclusive of All Taxes</div>
        </div>

        <button className="yb-card-btn" onClick={() => onViewDetails(perfume)}>
          View profile
        </button>
      </div>
    </div>
  )
}

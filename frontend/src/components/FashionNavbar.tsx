import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import { 
  Sparkles, 
  Layers, 
  Grid, 
  Box, 
  User
} from 'lucide-react';
import './FashionNavbar.css';

export const FashionNavbar: React.FC = () => {
  return (
    <header className="fashion-nav-root">
      {/* Brand Logo & Vision */}
      <Link to="/" className="fashion-nav-brand">
        <div className="fashion-logo-emblem">Y</div>
        <div>
          <span className="fashion-brand-name">YORVYN</span>
          <span className="fashion-brand-tagline">Personal AI Fashion Intelligence</span>
        </div>
      </Link>

      {/* Primary Studio Navigation */}
      <nav className="fashion-nav-links">
        <NavLink 
          to="/" 
          end
          className={({ isActive }) => `fashion-nav-item ${isActive ? 'active' : ''}`}
        >
          <Sparkles size={16} color="#d4af37" />
          <span>AI Stylist</span>
        </NavLink>

        <NavLink 
          to="/wardrobe" 
          className={({ isActive }) => `fashion-nav-item ${isActive ? 'active' : ''}`}
        >
          <Layers size={16} />
          <span>Digital Wardrobe</span>
        </NavLink>

        <NavLink 
          to="/outfits" 
          className={({ isActive }) => `fashion-nav-item ${isActive ? 'active' : ''}`}
        >
          <Grid size={16} />
          <span>Lookbook Studio</span>
        </NavLink>

        <NavLink 
          to="/avatar" 
          className={({ isActive }) => `fashion-nav-item ${isActive ? 'active' : ''}`}
        >
          <Box size={16} />
          <span>3D Digital Twin</span>
        </NavLink>

        <NavLink 
          to="/profile" 
          className={({ isActive }) => `fashion-nav-item ${isActive ? 'active' : ''}`}
        >
          <User size={16} />
          <span>Style Identity</span>
        </NavLink>
      </nav>

      {/* Right User State */}
      <div className="fashion-nav-right">
        <div className="user-quick-pill">
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
          <span>Autumn • Warm</span>
        </div>
      </div>
    </header>
  );
};

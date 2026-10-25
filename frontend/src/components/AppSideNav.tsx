import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  Sparkles, 
  User, 
  Settings as SettingsIcon, 
  Store, 
  Heart, 
  Layers, 
  Box 
} from 'lucide-react';
import './AppSideNav.css';

interface AppSideNavProps {
  onOpenSettings: () => void;
}

export const AppSideNav: React.FC<AppSideNavProps> = ({ onOpenSettings }) => {
  const navigate = useNavigate();

  return (
    <aside className="app-side-navbar" aria-label="Main Application Navigation">
      {/* Top: Yorvyn Luxury Monogram Emblem */}
      <div className="side-nav-brand">
        <button 
          className="brand-monogram" 
          onClick={() => navigate('/')}
          title="Return to Yorvyn Home"
          aria-label="Return to Yorvyn Home"
        >
          <span>Y</span>
        </button>
      </div>

      {/* Middle: Page Nav Links */}
      <nav className="side-nav-pages-list" aria-label="Pages">
        {/* 1. Fitting Room Studio */}
        <NavLink 
          to="/" 
          end
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          title="Fitting Room"
          aria-label="Fitting Room"
        >
          <Store size={20} />
          <span className="side-nav-tooltip">Fitting Room</span>
        </NavLink>

        {/* 2. AI Stylist (AI) */}
        <NavLink 
          to="/stylist" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          title="AI Stylist"
          aria-label="AI Stylist"
        >
          <Sparkles size={20} />
          <span className="side-nav-tooltip">AI Stylist</span>
        </NavLink>

        {/* 3. Digital Wardrobe */}
        <NavLink 
          to="/wardrobe" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          title="Digital Wardrobe"
          aria-label="Digital Wardrobe"
        >
          <Heart size={20} />
          <span className="side-nav-tooltip">Wardrobe</span>
        </NavLink>

        {/* 4. Lookbook Studio */}
        <NavLink 
          to="/outfits" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          title="Lookbook Studio"
          aria-label="Lookbook Studio"
        >
          <Layers size={20} />
          <span className="side-nav-tooltip">Lookbook</span>
        </NavLink>

        {/* 5. 3D Avatar Twin */}
        <NavLink 
          to="/avatar" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          title="3D Avatar Twin"
          aria-label="3D Avatar Twin"
        >
          <Box size={20} />
          <span className="side-nav-tooltip">3D Twin</span>
        </NavLink>

        {/* 6. Personal Profile */}
        <NavLink 
          to="/profile" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          title="Personal Profile"
          aria-label="Personal Profile"
        >
          <User size={20} />
          <span className="side-nav-tooltip">Profile</span>
        </NavLink>
      </nav>

      {/* Bottom: Settings */}
      <div className="side-nav-bottom">
        <button 
          className="side-nav-link-btn" 
          onClick={onOpenSettings}
          title="Studio Settings"
          aria-label="Studio Settings"
        >
          <SettingsIcon size={20} />
          <span className="side-nav-tooltip">Settings</span>
        </button>
      </div>
    </aside>
  );
};

import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  CoatHanger,
  Sparkle, 
  User,
  ShoppingBag,
  UserFocus
} from './icons';
import './AppSideNav.css';

interface AppSideNavProps {}

export const AppSideNav: React.FC<AppSideNavProps> = () => {
  return (
    <aside className="app-side-navbar" aria-label="Main Application Navigation">
      {/* 4 Core Unified Hubs (Matches Screenshot Order) */}
      <nav className="side-nav-pages-list" aria-label="Pages">
        {/* 1. Studio */}
        <NavLink 
          to="/" 
          end
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          aria-label="Studio"
        >
          {({ isActive }) => (
            <>
              <CoatHanger size={22} weight={isActive ? 'fill' : 'regular'} />
              <span className="side-nav-label">Studio</span>
              <span className="side-nav-tooltip">Studio</span>
            </>
          )}
        </NavLink>

        {/* 2. AI Stylist */}
        <NavLink 
          to="/stylist" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          aria-label="AI Stylist"
        >
          {({ isActive }) => (
            <>
              <Sparkle size={22} weight={isActive ? 'fill' : 'regular'} />
              <span className="side-nav-label">AI Stylist</span>
              <span className="side-nav-tooltip">AI Stylist</span>
            </>
          )}
        </NavLink>

        {/* 3. Personal Profile & Studio Settings (Single Tray) */}
        <NavLink 
          to="/profile" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          aria-label="Personal Profile"
        >
          {({ isActive }) => (
            <>
              <User size={22} weight={isActive ? 'fill' : 'regular'} />
              <span className="side-nav-label">Profile</span>
              <span className="side-nav-tooltip">Profile</span>
            </>
          )}
        </NavLink>

        {/* 4. Digital Wardrobe */}
        <NavLink 
          to="/wardrobe" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          aria-label="Wardrobe"
        >
          {({ isActive }) => (
            <>
              <ShoppingBag size={22} weight={isActive ? 'fill' : 'regular'} />
              <span className="side-nav-label">Wardrobe</span>
              <span className="side-nav-tooltip">Wardrobe</span>
            </>
          )}
        </NavLink>

        {/* 5. 3D Avatar Customization */}
        <NavLink 
          to="/avatar" 
          className={({ isActive }) => `side-nav-link-btn ${isActive ? 'active' : ''}`}
          aria-label="Avatar"
        >
          {({ isActive }) => (
            <>
              <UserFocus size={22} weight={isActive ? 'fill' : 'regular'} />
              <span className="side-nav-label">Avatar</span>
              <span className="side-nav-tooltip">Avatar</span>
            </>
          )}
        </NavLink>
      </nav>
    </aside>
  );
};

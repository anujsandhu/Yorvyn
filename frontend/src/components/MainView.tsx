import { AvatarStudio } from '../pages/AvatarStudio'
import './MainView.css'

/**
 * MainView renders the persistent single-screen Yorvyn experience.
 *
 * In adherence to the Single-Screen Liquid Glass UI architecture,
 * AvatarStudio remains permanently mounted across all hub routes
 * (Studio, AI Stylist, Digital Wardrobe, and Personal Profile).
 *
 * Route transitions update tray content inside the right-side drawer
 * without unmounting the Three.js WebGL avatar stage.
 */
export function MainView() {
  return (
    <div className="mv-root">
      <AvatarStudio />
    </div>
  )
}



import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
// @ts-ignore
import FOG from 'vanta/dist/vanta.fog.min';
import './VantaFogBackground.css';

interface VantaFogBackgroundProps {
  lowlightColor?: number;
  highlightColor?: number;
  midtoneColor?: number;
  baseColor?: number;
  blurFactor?: number;
  speed?: number;
  zoom?: number;
  className?: string;
}

export const VantaFogBackground: React.FC<VantaFogBackgroundProps> = ({
  lowlightColor = 0x87cefa,
  highlightColor = 0xffffff,
  midtoneColor = 0xbae6fd,
  baseColor = 0xe0f2fe,
  blurFactor = 0.45,
  speed = 0.65,
  zoom = 1.25,
  className = ''
}) => {
  const vantaRef = useRef<HTMLDivElement>(null);
  const vantaEffectRef = useRef<any>(null);

  useEffect(() => {
    // Ensure window.THREE is available for Vanta
    if (typeof window !== 'undefined' && !(window as any).THREE) {
      (window as any).THREE = THREE;
    }

    if (!vantaEffectRef.current && vantaRef.current) {
      try {
        const fogInit = (FOG as any)?.default || FOG;
        const config: Record<string, any> = {
          el: vantaRef.current,
          THREE,
          mouseControls: true,
          touchControls: true,
          gyroControls: false,
          minHeight: 200.0,
          minWidth: 200.0,
          lowlightColor,
          highlightColor,
          midtoneColor,
          baseColor,
          blurFactor,
          speed,
          zoom
        };

        vantaEffectRef.current = fogInit(config);
      } catch (err) {
        console.warn('[VantaFog] Initialization warning:', err);
      }
    }

    // Responsive resize observer to recompute viewport canvas bounds
    let resizeObserver: ResizeObserver | null = null;
    if (vantaRef.current && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        if (vantaEffectRef.current && typeof vantaEffectRef.current.resize === 'function') {
          vantaEffectRef.current.resize();
        }
      });
      resizeObserver.observe(vantaRef.current);
    }

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (vantaEffectRef.current) {
        try {
          vantaEffectRef.current.destroy();
        } catch (e) {
          // ignore cleanup errors
        }
        vantaEffectRef.current = null;
      }
    };
  }, [lowlightColor, highlightColor, midtoneColor, baseColor, blurFactor, speed, zoom]);

  return (
    <div 
      ref={vantaRef} 
      className={`vanta-fog-container ${className}`} 
      aria-hidden="true" 
    />
  );
};

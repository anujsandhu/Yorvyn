/**
 * YORVYN — 3D Garment Mannequin Preview Renderer
 * 
 * Generates photorealistic, catalog-grade visual thumbnails of reconstructed 3D garments:
 * 1. Drapes the actual 3D reconstructed garment mesh onto an elegant dress-form mannequin.
 * 2. Neutral fashion studio backdrop (#f8fafc) with subtle vignetting.
 * 3. Consistent 3-point studio lighting & ambient floor contact shadow.
 * 4. Standardized catalog camera framing (centered, 3/4 perspective).
 * 5. Completely replaces the original uploaded photograph: ONLY the 3D garment on a mannequin is shown.
 * 6. Headless WebGL offscreen rendering with high-speed 2D canvas fallback for headless testing.
 */

import * as THREE from 'three';
import { ReconstructedMeshGeometry } from './garmentReconstructionTypes';

export class GarmentMannequinPreviewRenderer {
  private static instance: GarmentMannequinPreviewRenderer | null = null;
  private cache: Map<string, string> = new Map();
  private renderer: THREE.WebGLRenderer | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private isWebGLAvailable: boolean = false;

  private constructor() {
    this.initWebGL();
  }

  public static getInstance(): GarmentMannequinPreviewRenderer {
    if (!GarmentMannequinPreviewRenderer.instance) {
      GarmentMannequinPreviewRenderer.instance = new GarmentMannequinPreviewRenderer();
    }
    return GarmentMannequinPreviewRenderer.instance;
  }

  /**
   * Initializes headless offscreen Three.js WebGL context
   */
  private initWebGL(): void {
    if (typeof document === 'undefined') return;

    try {
      this.canvas = document.createElement('canvas');
      this.canvas.width = 256;
      this.canvas.height = 256;

      this.renderer = new THREE.WebGLRenderer({
        canvas: this.canvas,
        alpha: true,
        antialias: true,
        preserveDrawingBuffer: true,
        powerPreference: 'low-power'
      });
      this.renderer.setPixelRatio(1);
      this.renderer.setSize(256, 256);
      this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
      this.renderer.toneMappingExposure = 1.05;

      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(32, 1, 0.1, 20);

      // Studio 3-Point Lighting
      const ambient = new THREE.AmbientLight(0xffffff, 0.85);
      this.scene.add(ambient);

      const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
      keyLight.position.set(1.5, 2.4, 2.0);
      this.scene.add(keyLight);

      const fillLight = new THREE.DirectionalLight(0xdbeafe, 0.65);
      fillLight.position.set(-1.8, 1.0, 1.5);
      this.scene.add(fillLight);

      const rimLight = new THREE.DirectionalLight(0xffffff, 1.1);
      rimLight.position.set(0, 2.8, -2.0);
      this.scene.add(rimLight);

      this.isWebGLAvailable = true;
    } catch {
      this.isWebGLAvailable = false;
    }
  }

  /**
   * Renders a 3D garment mesh draped on a mannequin dress-form stand.
   */
  public async renderGarmentThumbnail(
    geometry: ReconstructedMeshGeometry,
    diffuseAtlasUrl?: string,
    primaryColorHex: string = '#4a2e18',
    subcategory: string = 'hoodie'
  ): Promise<string> {
    const cacheKey = `${subcategory}_${primaryColorHex}_${geometry.vertexCount}_${diffuseAtlasUrl ? diffuseAtlasUrl.slice(0, 40) : 'plain'}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    if (!this.isWebGLAvailable || !this.renderer || !this.scene || !this.camera) {
      const fallbackUrl = this.renderProceduralCanvasMannequin(primaryColorHex, subcategory);
      this.cache.set(cacheKey, fallbackUrl);
      return fallbackUrl;
    }

    try {
      // Clear previous dynamic meshes (keep studio lights)
      const toRemove: THREE.Object3D[] = [];
      this.scene.traverse((obj) => {
        if (obj !== this.scene && !(obj instanceof THREE.Light)) {
          toRemove.push(obj);
        }
      });
      for (const obj of toRemove) {
        this.scene.remove(obj);
      }

      // 1. Construct Elegant Neutral Dress-Form Mannequin Stand
      const mannequinGroup = new THREE.Group();
      mannequinGroup.name = 'dress_form_mannequin';

      // Matte porcelain bisque material for inner torso
      const bustMaterial = new THREE.MeshStandardMaterial({
        color: 0xeeece8,
        roughness: 0.72,
        metalness: 0.05
      });

      // Turned wooden finial / neck cap material
      const woodMaterial = new THREE.MeshStandardMaterial({
        color: 0x8b5a2b, // Warm polished beechwood
        roughness: 0.45,
        metalness: 0.08
      });

      // Cast iron / gunmetal stand material
      const standMaterial = new THREE.MeshStandardMaterial({
        color: 0x334155,
        roughness: 0.35,
        metalness: 0.75
      });

      // A. Inner Torso Bust (forms the chest and neck structure inside garment)
      const bustGeom = new THREE.CylinderGeometry(0.085, 0.14, 0.58, 20);
      const bustMesh = new THREE.Mesh(bustGeom, bustMaterial);
      bustMesh.position.set(0, 1.20, 0);
      mannequinGroup.add(bustMesh);

      // B. Neck Column & Wooden Finial Cap
      const neckGeom = new THREE.CylinderGeometry(0.055, 0.065, 0.14, 16);
      const neckMesh = new THREE.Mesh(neckGeom, bustMaterial);
      neckMesh.position.set(0, 1.50, 0);
      mannequinGroup.add(neckMesh);

      const finialGeom = new THREE.CylinderGeometry(0.045, 0.055, 0.06, 16);
      const finialMesh = new THREE.Mesh(finialGeom, woodMaterial);
      finialMesh.position.set(0, 1.58, 0);
      mannequinGroup.add(finialMesh);

      const topBallGeom = new THREE.SphereGeometry(0.038, 16, 12);
      const topBallMesh = new THREE.Mesh(topBallGeom, woodMaterial);
      topBallMesh.position.set(0, 1.62, 0);
      mannequinGroup.add(topBallMesh);

      // C. Pedestal Pole extending below hem
      const poleGeom = new THREE.CylinderGeometry(0.016, 0.016, 0.90, 16);
      const poleMesh = new THREE.Mesh(poleGeom, standMaterial);
      poleMesh.position.set(0, 0.45, 0);
      mannequinGroup.add(poleMesh);

      // D. Circular Wooden / Metal Base Plate
      const baseGeom = new THREE.CylinderGeometry(0.18, 0.20, 0.035, 24);
      const baseMesh = new THREE.Mesh(baseGeom, woodMaterial);
      baseMesh.position.set(0, 0.02, 0);
      mannequinGroup.add(baseMesh);

      this.scene.add(mannequinGroup);

      // 2. Build 3D Garment Mesh from Reconstructed Geometry
      const garmentGeom = new THREE.BufferGeometry();
      garmentGeom.setAttribute('position', new THREE.BufferAttribute(geometry.positions, 3));
      garmentGeom.setAttribute('normal', new THREE.BufferAttribute(geometry.normals, 3));
      garmentGeom.setAttribute('uv', new THREE.BufferAttribute(geometry.uvs, 2));
      garmentGeom.setIndex(new THREE.BufferAttribute(geometry.indices, 1));

      let texture: THREE.Texture | null = null;
      if (diffuseAtlasUrl && typeof Image !== 'undefined') {
        try {
          const img = new Image();
          img.crossOrigin = 'anonymous';
          await new Promise<void>((resolve) => {
            img.onload = () => resolve();
            img.onerror = () => resolve();
            img.src = diffuseAtlasUrl;
          });
          texture = new THREE.CanvasTexture(img);
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.flipY = true;
        } catch {
          texture = null;
        }
      }

      const cleanHex = primaryColorHex.replace('#', '');
      const r = (parseInt(cleanHex.slice(0, 2), 16) || 74) / 255.0;
      const g = (parseInt(cleanHex.slice(2, 4), 16) || 46) / 255.0;
      const b = (parseInt(cleanHex.slice(4, 6), 16) || 24) / 255.0;

      const garmentMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(r, g, b),
        map: texture || undefined,
        roughness: 0.88,
        metalness: 0.02,
        side: THREE.DoubleSide
      });

      const garmentMesh = new THREE.Mesh(garmentGeom, garmentMat);
      garmentMesh.name = 'reconstructed_garment';
      this.scene.add(garmentMesh);

      // 3. Camera Framing (Subtle 3/4 Fashion Catalog Perspective)
      const bb = geometry.boundingBox;
      const centerY = (bb.min[1] + bb.max[1]) * 0.5;
      const heightSpan = Math.max(0.2, bb.max[1] - bb.min[1]);

      // Camera positioned at 12 degree yaw, framed on garment & dress-form
      const camY = centerY + 0.05;
      const camDist = Math.max(1.1, heightSpan * 1.85);
      const angle = THREE.MathUtils.degToRad(14);

      this.camera.position.set(Math.sin(angle) * camDist, camY, Math.cos(angle) * camDist);
      this.camera.lookAt(0, centerY, 0);

      // 4. Render and extract data URL
      this.renderer.render(this.scene, this.camera);
      if (!this.canvas) throw new Error('Canvas context not initialized');
      const thumbUrl = this.canvas.toDataURL('image/png');

      this.cache.set(cacheKey, thumbUrl);
      return thumbUrl;
    } catch {
      const fallbackUrl = this.renderProceduralCanvasMannequin(primaryColorHex, subcategory);
      this.cache.set(cacheKey, fallbackUrl);
      return fallbackUrl;
    }
  }

  /**
   * Deterministic 2D Canvas Fallback: renders high-fashion mannequin with garment draping
   * Guarantees zero-dependency execution in non-WebGL environments.
   */
  public renderProceduralCanvasMannequin(
    primaryColorHex: string,
    subcategory: string = 'hoodie',
    size = 256
  ): string {
    if (typeof document === 'undefined') {
      return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkWPjfDwAEeQHzj374ZAAAAABJRU5ErkJggg==';
    }

    try {
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (!ctx) return '';

      // 1. Neutral luxury studio vignette
      const grad = ctx.createRadialGradient(size / 2, size * 0.45, 10, size / 2, size / 2, size * 0.72);
      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.65, '#f8fafc');
      grad.addColorStop(1, '#e2e8f0');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, size, size);

      // 2. Ambient ground contact shadow
      ctx.fillStyle = 'rgba(15, 23, 42, 0.08)';
      ctx.beginPath();
      ctx.ellipse(size / 2, size * 0.92, size * 0.28, size * 0.04, 0, 0, Math.PI * 2);
      ctx.fill();

      // 3. Wooden / Metal Mannequin Pedestal Stand
      ctx.fillStyle = '#475569';
      ctx.fillRect(size / 2 - 3, size * 0.65, 6, size * 0.26);

      // Circular Base
      ctx.fillStyle = '#8b5a2b'; // Wood base
      ctx.beginPath();
      ctx.ellipse(size / 2, size * 0.90, size * 0.16, size * 0.035, 0, 0, Math.PI * 2);
      ctx.fill();

      // 4. Mannequin Torso Silhouette (Porcelain Bisque)
      ctx.fillStyle = '#e2e8f0';
      ctx.beginPath();
      ctx.moveTo(size * 0.35, size * 0.30);
      ctx.lineTo(size * 0.65, size * 0.30);
      ctx.lineTo(size * 0.60, size * 0.68);
      ctx.lineTo(size * 0.40, size * 0.68);
      ctx.closePath();
      ctx.fill();

      // Neck & Wooden Finial Cap
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(size / 2 - 12, size * 0.18, 24, size * 0.12);

      ctx.fillStyle = '#8b5a2b';
      ctx.beginPath();
      ctx.arc(size / 2, size * 0.17, 10, 0, Math.PI * 2);
      ctx.fill();

      // 5. 3D Reconstructed Garment Draped Over Mannequin
      const isHoodie = subcategory === 'hoodie';
      const isBottom = subcategory === 'trousers' || subcategory === 'jeans' || subcategory === 'shorts';

      ctx.fillStyle = primaryColorHex;
      ctx.shadowColor = 'rgba(0, 0, 0, 0.14)';
      ctx.shadowBlur = 10;
      ctx.shadowOffsetY = 4;

      if (isBottom) {
        // Trousers silhouette
        ctx.beginPath();
        ctx.moveTo(size * 0.36, size * 0.42);
        ctx.lineTo(size * 0.64, size * 0.42);
        ctx.lineTo(size * 0.62, size * 0.84);
        ctx.lineTo(size * 0.52, size * 0.84);
        ctx.lineTo(size * 0.50, size * 0.56); // Crotch apex
        ctx.lineTo(size * 0.48, size * 0.84);
        ctx.lineTo(size * 0.38, size * 0.84);
        ctx.closePath();
        ctx.fill();
      } else {
        // Upper garment silhouette (Torso & Sleeves)
        ctx.beginPath();
        // Neck opening
        ctx.moveTo(size * 0.40, size * 0.28);
        ctx.quadraticCurveTo(size / 2, size * 0.33, size * 0.60, size * 0.28);
        // Right shoulder & long sleeve
        ctx.lineTo(size * 0.74, size * 0.34);
        ctx.lineTo(size * 0.82, size * 0.62);
        ctx.lineTo(size * 0.74, size * 0.64);
        ctx.lineTo(size * 0.68, size * 0.44); // Right armpit
        // Right torso to waistband
        ctx.lineTo(size * 0.64, size * 0.70);
        // Waistband hem
        ctx.lineTo(size * 0.36, size * 0.70);
        // Left torso to armpit
        ctx.lineTo(size * 0.32, size * 0.44);
        // Left sleeve
        ctx.lineTo(size * 0.26, size * 0.64);
        ctx.lineTo(size * 0.18, size * 0.62);
        ctx.lineTo(size * 0.26, size * 0.34);
        ctx.closePath();
        ctx.fill();

        ctx.shadowColor = 'transparent';

        // 3D Volumetric Hood Cowl
        if (isHoodie) {
          ctx.fillStyle = primaryColorHex;
          ctx.beginPath();
          ctx.arc(size / 2, size * 0.24, 28, Math.PI * 0.8, Math.PI * 2.2);
          ctx.fill();

          // Kangaroo Pouch Pocket on Front Torso
          ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
          ctx.beginPath();
          ctx.moveTo(size * 0.42, size * 0.52);
          ctx.lineTo(size * 0.58, size * 0.52);
          ctx.lineTo(size * 0.61, size * 0.65);
          ctx.lineTo(size * 0.39, size * 0.65);
          ctx.closePath();
          ctx.fill();

          // Braided Drawstrings hanging from collar
          ctx.strokeStyle = '#c5a059'; // Metallic aglet tips
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(size * 0.46, size * 0.32);
          ctx.lineTo(size * 0.46, size * 0.46);
          ctx.moveTo(size * 0.54, size * 0.32);
          ctx.lineTo(size * 0.54, size * 0.46);
          ctx.stroke();
        }

        // Ribbed waistband hem line
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.20)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(size * 0.36, size * 0.67);
        ctx.lineTo(size * 0.64, size * 0.67);
        ctx.stroke();
      }

      return canvas.toDataURL('image/png');
    } catch {
      return '';
    }
  }
}

export const garmentMannequinPreviewRenderer = GarmentMannequinPreviewRenderer.getInstance();

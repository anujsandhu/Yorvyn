/**
 * Phase 16.3 Real-Time 3D Garment BufferGeometry & PBR Material Editor
 * Mutates BufferGeometry attributes in place from immutable rest buffers, highlights semantic
 * components, builds procedural normal/UV/stitch maps, measures bounding dimensions, and exports GLB/GLTF.
 */

import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import type {
  DesignMaterialState,
  GeometryDeformationParams,
  ViewportInspectionModes,
} from './DesignStateEngine';

interface RestMeshBuffers {
  positions: Float32Array;
  normals: Float32Array;
  minY: number;
  maxY: number;
  center: THREE.Vector3;
  semanticRole: 'torso' | 'sleeve' | 'cuff' | 'collar' | 'hem' | 'waistband' | 'leg' | 'pocket';
  baseMaterialSnapshot: THREE.MeshStandardMaterial | null;
  baseMap: THREE.Texture | null;
}

export interface LiveMeshMetrics {
  widthCm: number;
  heightCm: number;
  depthCm: number;
  vertexCount: number;
  triangleCount: number;
  meshCount: number;
  componentIds: string[];
  topologyHash: string;
}

export class RealtimeMeshEditor {
  private restBuffers = new WeakMap<THREE.Mesh, RestMeshBuffers>();
  private uvTestTexture: THREE.CanvasTexture | null = null;
  private weaveTextures = new Map<string, THREE.CanvasTexture>();
  private normalDebugMaterial: THREE.MeshNormalMaterial | null = null;
  private stitchOverlayGroup: THREE.Group | null = null;
  private measurementGroup: THREE.Group | null = null;

  public inferSemanticRole(mesh: THREE.Mesh): RestMeshBuffers['semanticRole'] {
    const extraType = String(mesh.userData?.semantic_type || mesh.userData?.component_id || '').toLowerCase();
    const label = `${mesh.name} ${extraType}`.toLowerCase();
    if (label.includes('cuff')) return 'cuff';
    if (label.includes('sleeve')) return 'sleeve';
    if (label.includes('collar') || label.includes('lapel') || label.includes('hood') || label.includes('neck')) return 'collar';
    if (label.includes('waistband') || label.includes('pelvis')) return 'waistband';
    if (label.includes('leg')) return 'leg';
    if (label.includes('hem')) return 'hem';
    if (label.includes('pocket')) return 'pocket';
    return 'torso';
  }

  public indexGarmentScene(root: THREE.Object3D): string[] {
    const components: string[] = [];
    root.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh;
        const geo = mesh.geometry;
        const posAttr = geo?.getAttribute('position') as THREE.BufferAttribute | undefined;
        if (!posAttr) return;

        if (!geo.getAttribute('normal')) {
          geo.computeVertexNormals();
        }
        const normAttr = geo.getAttribute('normal') as THREE.BufferAttribute;

        if (!this.restBuffers.has(mesh)) {
          geo.computeBoundingBox();
          const bb = geo.boundingBox || new THREE.Box3().setFromBufferAttribute(posAttr);
          const center = new THREE.Vector3();
          bb.getCenter(center);
          const stdMat = !Array.isArray(mesh.material) && (mesh.material as THREE.MeshStandardMaterial)?.isMeshStandardMaterial
            ? (mesh.material as THREE.MeshStandardMaterial)
            : null;
          this.restBuffers.set(mesh, {
            positions: new Float32Array(posAttr.array as Float32Array),
            normals: new Float32Array(normAttr.array as Float32Array),
            minY: bb.min.y,
            maxY: bb.max.y,
            center,
            semanticRole: this.inferSemanticRole(mesh),
            baseMaterialSnapshot: stdMat ? stdMat.clone() : null,
            baseMap: stdMat?.map ?? null,
          });
        }
        const compName = String(mesh.userData?.component_id || mesh.userData?.semantic_type || mesh.name || 'torso');
        if (!components.includes(compName)) components.push(compName);
      }
    });
    return components;
  }

  public applyGeometryParameters(root: THREE.Object3D, params: GeometryDeformationParams): LiveMeshMetrics {
    this.indexGarmentScene(root);
    const componentIds: string[] = [];
    let vertexCount = 0;
    let triangleCount = 0;
    let meshCount = 0;

    root.traverse((obj) => {
      if (!(obj as THREE.Mesh).isMesh) return;
      const mesh = obj as THREE.Mesh;
      if (mesh.userData?.isEditorHelper) return;
      const rest = this.restBuffers.get(mesh);
      if (!rest) return;

      meshCount++;
      const posAttr = mesh.geometry.getAttribute('position') as THREE.BufferAttribute;
      const normAttr = mesh.geometry.getAttribute('normal') as THREE.BufferAttribute;
      const dstPos = posAttr.array as Float32Array;
      const dstNorm = normAttr.array as Float32Array;
      const srcPos = rest.positions;
      const srcNorm = rest.normals;
      const count = posAttr.count;
      vertexCount += count;

      const spanY = Math.max(0.05, rest.maxY - rest.minY);
      const isMultiComponent = componentIds.length > 1 || rest.semanticRole !== 'torso';

      for (let i = 0; i < count; i++) {
        const i3 = i * 3;
        const px = srcPos[i3];
        const py = srcPos[i3 + 1];
        const pz = srcPos[i3 + 2];

        let sx = params.torsoWidthScale;
        let sy = params.torsoLengthScale;
        let sz = params.torsoWidthScale;
        let anchorY = rest.maxY;
        let dxShift = 0;
        let dyShift = 0;

        if (isMultiComponent && rest.semanticRole === 'cuff') {
          sx = params.cuffWidthScale;
          sy = 1.0;
          sz = params.cuffWidthScale;
        } else if (isMultiComponent && rest.semanticRole === 'sleeve') {
          sx = params.sleeveWidthScale;
          sy = params.sleeveLengthScale;
          sz = params.sleeveWidthScale;
          if (params.shoulderWidthScale !== 1.0) {
            dxShift = Math.sign(rest.center.x) * Math.abs(rest.center.x) * (params.shoulderWidthScale - 1.0) * 0.5;
          }
        } else if (isMultiComponent && rest.semanticRole === 'collar') {
          sx = params.collarWidthScale;
          sy = 1.0;
          sz = params.collarWidthScale;
        } else if (isMultiComponent && rest.semanticRole === 'waistband') {
          sx = params.waistbandWidthScale;
          sy = 1.0;
          sz = params.waistbandWidthScale;
        } else if (isMultiComponent && rest.semanticRole === 'leg') {
          sx = params.legWidthScale;
          sy = params.legLengthScale;
          sz = params.legWidthScale;
        } else if (isMultiComponent && rest.semanticRole === 'pocket') {
          sx = 1.0;
          sy = 1.0;
          sz = 1.0;
          dyShift = params.pocketOffsetYM;
        } else if (isMultiComponent && rest.semanticRole === 'hem') {
          sx = params.hemWidthScale;
          sy = 1.0;
          sz = params.hemWidthScale;
        } else {
          // Semantic torso region zoning (upper shoulder blend, collar apex, hem lower blend)
          const yNorm = (py - rest.minY) / spanY;
          if (yNorm > 0.84) {
            const blend = (yNorm - 0.84) / 0.16;
            sx = THREE.MathUtils.lerp(sx, params.collarWidthScale, blend);
            sz = THREE.MathUtils.lerp(sz, params.collarWidthScale, blend);
          } else if (yNorm > 0.65 && params.shoulderWidthScale !== 1.0) {
            const blend = (yNorm - 0.65) / 0.35;
            sx = sx * THREE.MathUtils.lerp(1.0, params.shoulderWidthScale, blend);
          } else if (yNorm < 0.22) {
            const blend = (0.22 - yNorm) / 0.22;
            sx = THREE.MathUtils.lerp(sx, params.hemWidthScale, blend);
            sz = THREE.MathUtils.lerp(sz, params.hemWidthScale, blend);
          }
          if (Math.abs(px - rest.center.x) > 0.18 && yNorm > 0.45) {
            sx = params.sleeveWidthScale;
            sz = params.sleeveWidthScale;
            anchorY = rest.center.y + spanY * 0.25;
            sy = params.sleeveLengthScale;
          }
        }

        dstPos[i3] = rest.center.x + (px - rest.center.x) * sx + dxShift;
        dstPos[i3 + 1] = anchorY + (py - anchorY) * sy + dyShift;
        dstPos[i3 + 2] = rest.center.z + (pz - rest.center.z) * sz;

        const nx = srcNorm[i3] / Math.max(1e-4, sx);
        const ny = srcNorm[i3 + 1] / Math.max(1e-4, sy);
        const nz = srcNorm[i3 + 2] / Math.max(1e-4, sz);
        const nLen = Math.hypot(nx, ny, nz) || 1;
        dstNorm[i3] = nx / nLen;
        dstNorm[i3 + 1] = ny / nLen;
        dstNorm[i3 + 2] = nz / nLen;
      }

      posAttr.needsUpdate = true;
      normAttr.needsUpdate = true;
      mesh.geometry.computeBoundingBox();
      mesh.geometry.computeBoundingSphere();

      const idx = mesh.geometry.getIndex();
      triangleCount += idx ? Math.floor(idx.count / 3) : Math.floor(count / 3);
      const cid = String(mesh.userData?.component_id || mesh.name || 'garment');
      if (!componentIds.includes(cid)) componentIds.push(cid);
    });

    const box = new THREE.Box3().setFromObject(root);
    const size = new THREE.Vector3();
    box.getSize(size);
    return {
      widthCm: Number((size.x * 100).toFixed(1)),
      heightCm: Number((size.y * 100).toFixed(1)),
      depthCm: Number((size.z * 100).toFixed(1)),
      vertexCount,
      triangleCount,
      meshCount,
      componentIds,
      topologyHash: `${meshCount}:${vertexCount}:${triangleCount}:${componentIds.slice().sort().join(',')}`,
    };
  }

  private getUvTestTexture(): THREE.CanvasTexture | null {
    if (this.uvTestTexture) return this.uvTestTexture;
    if (typeof document === 'undefined') return null;
    const c = document.createElement('canvas');
    c.width = 256;
    c.height = 256;
    const ctx = c.getContext('2d');
    if (!ctx) return null;
    for (let y = 0; y < 8; y++) {
      for (let x = 0; x < 8; x++) {
        ctx.fillStyle = (x + y) % 2 === 0 ? '#1d4ed8' : '#f8fafc';
        ctx.fillRect(x * 32, y * 32, 32, 32);
      }
    }
    ctx.strokeStyle = '#dc2626';
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 252, 252);
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.colorSpace = THREE.SRGBColorSpace;
    this.uvTestTexture = tex;
    return tex;
  }

  private getWeaveTexture(preset: string, stitchVisible: boolean, stitchColor: string): THREE.CanvasTexture | null {
    const key = `${preset}:${stitchVisible}:${stitchColor}`;
    const existing = this.weaveTextures.get(key);
    if (existing) return existing;
    if (typeof document === 'undefined') return null;
    const c = document.createElement('canvas');
    c.width = 128;
    c.height = 128;
    const ctx = c.getContext('2d');
    if (!ctx) return null;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, 128, 128);
    ctx.strokeStyle = preset === 'denim' ? 'rgba(15,23,42,0.18)' : 'rgba(100,116,139,0.10)';
    ctx.lineWidth = preset === 'denim' ? 2 : 1;
    for (let i = -128; i < 256; i += 8) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i + (preset === 'denim' ? 128 : 0), 128);
      ctx.stroke();
    }
    if (stitchVisible) {
      ctx.strokeStyle = stitchColor;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(6, 6, 116, 116);
    }
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.colorSpace = THREE.SRGBColorSpace;
    this.weaveTextures.set(key, tex);
    return tex;
  }

  public applyMaterialAndInspectionModes(
    root: THREE.Object3D,
    materialState: DesignMaterialState,
    viewModes: ViewportInspectionModes,
    selectedComponent: string | null,
    hoveredComponent: string | null
  ): void {
    this.indexGarmentScene(root);
    const panelPalette = ['#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4'];
    let panelIdx = 0;

    root.traverse((obj) => {
      if (!(obj as THREE.Mesh).isMesh) return;
      const mesh = obj as THREE.Mesh;
      if (mesh.userData?.isEditorHelper) return;
      const rest = this.restBuffers.get(mesh);
      if (!rest) return;

      if (viewModes.showNormals) {
        if (!this.normalDebugMaterial) {
          this.normalDebugMaterial = new THREE.MeshNormalMaterial({ wireframe: viewModes.wireframe });
        }
        this.normalDebugMaterial.wireframe = viewModes.wireframe;
        mesh.material = this.normalDebugMaterial;
        return;
      }

      if (!mesh.userData.__studioStdMat) {
        mesh.userData.__studioStdMat = rest.baseMaterialSnapshot
          ? rest.baseMaterialSnapshot.clone()
          : new THREE.MeshStandardMaterial({ color: '#ffffff', side: THREE.DoubleSide });
      }
      const mat = mesh.userData.__studioStdMat as THREE.MeshStandardMaterial;
      mesh.material = mat;

      const compName = String(mesh.userData?.component_id || mesh.name || 'torso');
      const isSelected = Boolean(selectedComponent && compName === selectedComponent);
      const isHovered = Boolean(hoveredComponent && compName === hoveredComponent);

      if (viewModes.showUVs) {
        mat.map = this.getUvTestTexture();
        mat.color.set('#ffffff');
      } else if (viewModes.showPanels) {
        mat.map = rest.baseMap;
        mat.color.set(panelPalette[panelIdx % panelPalette.length]);
        panelIdx++;
      } else {
        const tex = rest.baseMap || this.getWeaveTexture(materialState.preset, materialState.stitchVisible, materialState.stitchColor);
        if (tex) {
          tex.repeat.set(materialState.repeatX * materialState.printScale, materialState.repeatY * materialState.printScale);
          tex.offset.set(materialState.offsetX, materialState.offsetY);
          tex.rotation = (materialState.rotationDeg * Math.PI) / 180;
          tex.needsUpdate = true;
        }
        mat.map = tex;
        mat.color.set(materialState.baseColor || '#ffffff');
      }

      mat.roughness = materialState.roughness;
      mat.metalness = materialState.metalness;
      mat.wireframe = viewModes.wireframe;
      mat.side = THREE.DoubleSide;
      mat.emissive.set(isSelected ? '#1d4ed8' : isHovered ? '#0284c7' : '#000000');
      mat.emissiveIntensity = isSelected ? 0.35 : isHovered ? 0.18 : 0.0;
      mat.needsUpdate = true;
    });

    this.updateOverlays(root, viewModes, materialState);
  }

  private updateOverlays(
    root: THREE.Object3D,
    viewModes: ViewportInspectionModes,
    materialState: DesignMaterialState
  ): void {
    if (this.stitchOverlayGroup) {
      root.remove(this.stitchOverlayGroup);
      this.stitchOverlayGroup.traverse((o) => {
        if ((o as THREE.LineSegments).geometry) (o as THREE.LineSegments).geometry.dispose();
      });
      this.stitchOverlayGroup = null;
    }
    if (viewModes.showSeams || materialState.stitchVisible) {
      const grp = new THREE.Group();
      grp.userData.isEditorHelper = true;
      const lineMat = new THREE.LineBasicMaterial({
        color: viewModes.showSeams ? '#2563eb' : materialState.stitchColor,
      });
      root.traverse((obj) => {
        if ((obj as THREE.Mesh).isMesh && !obj.userData?.isEditorHelper) {
          const edges = new THREE.EdgesGeometry((obj as THREE.Mesh).geometry, 28);
          const segs = new THREE.LineSegments(edges, lineMat);
          segs.userData.isEditorHelper = true;
          grp.add(segs);
        }
      });
      root.add(grp);
      this.stitchOverlayGroup = grp;
    }

    if (this.measurementGroup) {
      root.remove(this.measurementGroup);
      this.measurementGroup.traverse((o) => {
        if ((o as THREE.Box3Helper).geometry) (o as THREE.Box3Helper).geometry.dispose();
      });
      this.measurementGroup = null;
    }
    if (viewModes.showMeasurements) {
      const box = new THREE.Box3().setFromObject(root);
      if (!box.isEmpty()) {
        const helper = new THREE.Box3Helper(box, 0x0284c7);
        helper.userData.isEditorHelper = true;
        const mGrp = new THREE.Group();
        mGrp.userData.isEditorHelper = true;
        mGrp.add(helper);
        root.add(mGrp);
        this.measurementGroup = mGrp;
      }
    }
  }

  public async exportToBinaryGLB(root: THREE.Object3D): Promise<Blob> {
    const exporter = new GLTFExporter();
    const cleanClone = root.clone(true);
    const toRemove: THREE.Object3D[] = [];
    cleanClone.traverse((o) => {
      if (o.userData?.isEditorHelper) toRemove.push(o);
    });
    toRemove.forEach((o) => o.parent?.remove(o));

    return new Promise<Blob>((resolve, reject) => {
      exporter.parse(
        cleanClone,
        (result) => {
          if (result instanceof ArrayBuffer) {
            resolve(new Blob([result], { type: 'model/gltf-binary' }));
          } else {
            resolve(new Blob([JSON.stringify(result)], { type: 'model/gltf+json' }));
          }
        },
        (err) => reject(err),
        { binary: true }
      );
    });
  }

  public async exportToGLTFJson(root: THREE.Object3D): Promise<string> {
    const exporter = new GLTFExporter();
    const cleanClone = root.clone(true);
    const toRemove: THREE.Object3D[] = [];
    cleanClone.traverse((o) => {
      if (o.userData?.isEditorHelper) toRemove.push(o);
    });
    toRemove.forEach((o) => o.parent?.remove(o));

    return new Promise<string>((resolve, reject) => {
      exporter.parse(
        cleanClone,
        (result) => resolve(JSON.stringify(result, null, 2)),
        (err) => reject(err),
        { binary: false }
      );
    });
  }

  public dispose(): void {
    this.uvTestTexture?.dispose();
    this.uvTestTexture = null;
    this.weaveTextures.forEach((t) => t.dispose());
    this.weaveTextures.clear();
    this.normalDebugMaterial?.dispose();
    this.normalDebugMaterial = null;
  }
}

/**
 * YORVYN — Garment Resource Manager (Phase 5)
 * Manages allocation, tracking, and clean disposal of 3D meshes, geometries, and textures.
 * Prevents visual duplicates, z-fighting surfaces, and memory leaks on 8GB Apple Silicon M2.
 */

import * as THREE from 'three';

export interface GarmentResourceBinding {
  garmentId: string;
  category: string;
  object3D: THREE.Object3D;
  geometries: THREE.BufferGeometry[];
  materials: THREE.Material[];
  textures: THREE.Texture[];
}

export class GarmentResourceManager {
  private activeResources = new Map<string, GarmentResourceBinding>();

  /**
   * Registers a 3D garment object in the manager and tracks all underlying GPU resources.
   */
  public register(
    garmentId: string,
    category: string,
    object3D: THREE.Object3D
  ): GarmentResourceBinding {
    // If a resource already exists in this category, dispose of it first (prevents duplicates)
    this.disposeCategory(category);

    const geometries: THREE.BufferGeometry[] = [];
    const materials: THREE.Material[] = [];
    const textures: THREE.Texture[] = [];

    object3D.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        if (mesh.geometry && !geometries.includes(mesh.geometry)) {
          geometries.push(mesh.geometry);
        }

        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        mats.forEach((mat) => {
          if (mat && !materials.includes(mat)) {
            materials.push(mat);
            // Track textures on material
            const std = mat as THREE.MeshStandardMaterial;
            if (std.map && !textures.includes(std.map)) textures.push(std.map);
            if (std.normalMap && !textures.includes(std.normalMap)) textures.push(std.normalMap);
            if (std.roughnessMap && !textures.includes(std.roughnessMap)) textures.push(std.roughnessMap);
            if (std.metalnessMap && !textures.includes(std.metalnessMap)) textures.push(std.metalnessMap);
          }
        });
      }
    });

    const binding: GarmentResourceBinding = {
      garmentId,
      category,
      object3D,
      geometries,
      materials,
      textures
    };

    this.activeResources.set(category, binding);
    return binding;
  }

  /**
   * Disposes of all GPU resources associated with a garment category.
   * Cleans geometries, materials, and textures from memory, and unlinks from parent scene graph.
   */
  public disposeCategory(category: string): boolean {
    const binding = this.activeResources.get(category);
    if (!binding) return false;

    // 1. Remove from scene graph
    if (binding.object3D.parent) {
      binding.object3D.parent.remove(binding.object3D);
    }

    // 2. Dispose of geometries
    binding.geometries.forEach((geo) => geo.dispose());

    // 3. Dispose of materials and textures
    binding.materials.forEach((mat) => mat.dispose());
    binding.textures.forEach((tex) => tex.dispose());

    this.activeResources.delete(category);
    return true;
  }

  /**
   * Completely purges all active garments and releases all resources.
   */
  public disposeAll(): void {
    const categories = Array.from(this.activeResources.keys());
    categories.forEach((cat) => this.disposeCategory(cat));
  }

  public dispose(): void {
    this.disposeAll();
  }

  public getAllocatedCount(): number {
    return this.activeResources.size;
  }

  /**
   * Checks whether a category currently has an active 3D mesh.
   */
  public hasActiveCategory(category: string): boolean {
    return this.activeResources.has(category);
  }

  /**
   * Gets the active binding for a category.
   */
  public getBinding(category: string): GarmentResourceBinding | undefined {
    return this.activeResources.get(category);
  }
}


/**
 * YORVYN — Three.js Runtime GLB Loadability Verifier (Phase 14.13 Workstream I.6)
 * Uses the project's actual Three.js GLTFLoader to test whether a GLB is parseable by Three.js.
 * Usage: node scripts/verify_glb_threejs.mjs <path-to-glb>
 */

globalThis.self = globalThis;
import fs from 'fs';
import path from 'path';
import * as THREE from '../frontend/node_modules/three/build/three.module.js';
import { GLTFLoader } from '../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';

const targetGlbPath = process.argv[2];

if (!targetGlbPath) {
  console.log(JSON.stringify({ success: false, error: "No GLB file path provided" }));
  process.exit(1);
}

try {
  const resolvedPath = path.resolve(targetGlbPath);
  if (!fs.existsSync(resolvedPath)) {
    console.log(JSON.stringify({ success: false, error: `File not found: ${resolvedPath}` }));
    process.exit(1);
  }

  const fileBuf = fs.readFileSync(resolvedPath);
  const arrayBuffer = fileBuf.buffer.slice(fileBuf.byteOffset, fileBuf.byteOffset + fileBuf.byteLength);

  const loader = new GLTFLoader();
  loader.parse(
    arrayBuffer,
    '',
    (gltf) => {
      let totalGeometries = 0;
      let totalMaterials = 0;
      let totalVertices = 0;

      if (gltf.scene) {
        gltf.scene.traverse((child) => {
          if (child.isMesh) {
            totalGeometries++;
            if (child.material) totalMaterials++;
            if (child.geometry && child.geometry.attributes && child.geometry.attributes.position) {
              totalVertices += child.geometry.attributes.position.count;
            }
          }
        });
      }

      console.log(JSON.stringify({
        success: true,
        glb_path: resolvedPath,
        file_size_bytes: fileBuf.byteLength,
        scenes_count: gltf.scenes ? gltf.scenes.length : 0,
        scene_children_count: gltf.scene ? gltf.scene.children.length : 0,
        mesh_count: totalGeometries,
        material_count: totalMaterials,
        vertex_count: totalVertices,
        three_js_revision: THREE.REVISION
      }));
    },
    (err) => {
      console.log(JSON.stringify({
        success: false,
        glb_path: resolvedPath,
        error: String(err)
      }));
      process.exit(1);
    }
  );
} catch (e) {
  console.log(JSON.stringify({
    success: false,
    error: e.message || String(e)
  }));
  process.exit(1);
}

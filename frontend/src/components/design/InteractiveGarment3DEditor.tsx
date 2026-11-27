/**
 * Phase 16.3 Interactive Real-Time 3D Garment Editor
 * Upgraded Three.js viewport featuring OrbitControls, Raycaster component hover/selection,
 * in-place BufferGeometry updates, PBR/UV/Normal/Panel/Seam inspection, lighting & camera presets,
 * context-loss protection, WebGPU capability telemetry badge, and live FPS/triangle readout.
 */

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type {
  CameraPreset,
  DesignStateEngine,
  GarmentDesignState,
  LightingPreset,
} from '../../engine/designStudio/DesignStateEngine';
import {
  detectGraphicsCapabilities,
  type GraphicsCapabilitiesReport,
} from '../../engine/designStudio/GraphicsCapabilityService';
import {
  RealtimeMeshEditor,
  type LiveMeshMetrics,
} from '../../engine/designStudio/RealtimeMeshEditor';

export interface RenderTelemetry {
  fps: number;
  frameTimeMs: number;
  drawCalls: number;
  triangles: number;
  backend: string;
}

interface Props {
  glbUrl: string;
  designEngine: DesignStateEngine;
  designState: GarmentDesignState;
  meshEditorRef: React.MutableRefObject<RealtimeMeshEditor | null>;
  garmentGroupRef: React.MutableRefObject<THREE.Object3D | null>;
  onTelemetry?: (telemetry: RenderTelemetry, capabilities: GraphicsCapabilitiesReport | null) => void;
  onMeshMetrics?: (metrics: LiveMeshMetrics) => void;
}

const CAMERA_ANGLES: Record<CameraPreset, [number, number, number]> = {
  front: [0, 0.15, 2.0],
  three_quarter: [1.35, 0.35, 1.55],
  side: [2.0, 0.15, 0.0],
  back: [0, 0.15, -2.0],
  detail: [0.35, 0.52, 1.05],
};

function applyLightingPreset(
  preset: LightingPreset,
  exposure: number,
  renderer: THREE.WebGLRenderer,
  hemi: THREE.HemisphereLight,
  keyLight: THREE.DirectionalLight,
  rimLight: THREE.DirectionalLight
): void {
  renderer.toneMappingExposure = exposure;
  if (preset === 'runway_spotlight') {
    hemi.intensity = 0.55;
    keyLight.color.set('#ffffff');
    keyLight.intensity = 2.6;
    keyLight.position.set(1.2, 4.2, 1.6);
    rimLight.color.set('#93c5fd');
    rimLight.intensity = 1.8;
  } else if (preset === 'warm_atelier') {
    hemi.intensity = 0.95;
    keyLight.color.set('#fff3e0');
    keyLight.intensity = 1.9;
    keyLight.position.set(2.0, 2.8, 2.2);
    rimLight.color.set('#fde68a');
    rimLight.intensity = 1.1;
  } else {
    hemi.intensity = 1.1;
    keyLight.color.set('#ffffff');
    keyLight.intensity = 1.75;
    keyLight.position.set(1.5, 3.0, 2.4);
    rimLight.color.set('#bae6fd');
    rimLight.intensity = 1.0;
  }
}

export function InteractiveGarment3DEditor({
  glbUrl,
  designEngine,
  designState,
  meshEditorRef,
  garmentGroupRef,
  onTelemetry,
  onMeshMetrics,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [initError, setInitError] = useState<string | null>(null);
  const [contextLost, setContextLost] = useState(false);
  const [caps, setCaps] = useState<GraphicsCapabilitiesReport | null>(null);
  const [telemetry, setTelemetry] = useState<RenderTelemetry>({
    fps: 0,
    frameTimeMs: 0,
    drawCalls: 0,
    triangles: 0,
    backend: 'webgl2',
  });
  const [componentList, setComponentList] = useState<string[]>([]);

  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const lightsRef = useRef<{
    hemi: THREE.HemisphereLight;
    key: THREE.DirectionalLight;
    rim: THREE.DirectionalLight;
  } | null>(null);
  const modelCenterRef = useRef(new THREE.Vector3());
  const modelDistRef = useRef(1.8);
  const stateRef = useRef(designState);
  stateRef.current = designState;

  // Probe WebGL2 + WebGPU capabilities once on mount
  useEffect(() => {
    let alive = true;
    detectGraphicsCapabilities({ probeWebGPUAdapter: true }).then((report) => {
      if (alive) setCaps(report);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Initialize Three.js WebGL2 Renderer + Controls + Raycaster + ResizeObserver
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const width = container.clientWidth || 520;
    const height = container.clientHeight || 420;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: true,
        preserveDrawingBuffer: true,
        powerPreference: 'high-performance',
      });
    } catch (err: any) {
      try {
        renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true });
      } catch {
        setInitError('Interactive 3D editor requires WebGL2.');
        return;
      }
    }

    renderer.setSize(width, height, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#f1f5f9');
    sceneRef.current = scene;

    const grid = new THREE.GridHelper(2.4, 24, 0xcbd5e1, 0xe2e8f0);
    grid.position.y = -0.65;
    scene.add(grid);

    const camera = new THREE.PerspectiveCamera(35, width / height, 0.02, 40);
    camera.position.set(0, 0.15, 2.0);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 0.45;
    controls.maxDistance = 5.0;
    controlsRef.current = controls;

    const hemi = new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 1.1);
    const key = new THREE.DirectionalLight(0xffffff, 1.75);
    key.position.set(1.5, 3.0, 2.4);
    const rim = new THREE.DirectionalLight(0xbae6fd, 1.0);
    rim.position.set(-1.5, 2.2, -2.0);
    scene.add(hemi, key, rim);
    lightsRef.current = { hemi, key, rim };

    if (!meshEditorRef.current) {
      meshEditorRef.current = new RealtimeMeshEditor();
    }

    const onContextLost = (e: Event) => {
      e.preventDefault();
      setContextLost(true);
    };
    const onContextRestored = () => {
      setContextLost(false);
      if (container && rendererRef.current && cameraRef.current) {
        rendererRef.current.setSize(container.clientWidth || 520, container.clientHeight || 420, false);
      }
    };
    canvas.addEventListener('webglcontextlost', onContextLost, false);
    canvas.addEventListener('webglcontextrestored', onContextRestored, false);

    // Raycaster hover + click component selection
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const pickComponent = (clientX: number, clientY: number): string | null => {
      if (!garmentGroupRef.current) return null;
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObject(garmentGroupRef.current, true);
      for (const hit of hits) {
        const mesh = hit.object as THREE.Mesh;
        if (mesh.isMesh && !mesh.userData?.isEditorHelper) {
          return String(mesh.userData?.component_id || mesh.userData?.semantic_type || mesh.name || 'torso');
        }
      }
      return null;
    };

    const onPointerMove = (e: PointerEvent) => {
      const cid = pickComponent(e.clientX, e.clientY);
      if (cid !== stateRef.current.hoveredComponent) {
        designEngine.setViewState({ hoveredComponent: cid });
      }
    };
    const onPointerClick = (e: MouseEvent) => {
      const cid = pickComponent(e.clientX, e.clientY);
      if (cid !== null) {
        designEngine.setViewState({ selectedComponent: cid });
      }
    };
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('click', onPointerClick);

    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      const h = entry.contentRect.height;
      if (w > 0 && h > 0) {
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      }
    });
    ro.observe(container);

    // Performance-metered animation loop
    let animId = 0;
    let frameCount = 0;
    let lastReportAt = performance.now();
    let prevFrameAt = lastReportAt;
    let simPhase = 0;

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const now = performance.now();
      const dt = Math.min(0.1, (now - prevFrameAt) / 1000);
      prevFrameAt = now;

      // Lightweight interactive cloth sway preview when enabled
      if (garmentGroupRef.current) {
        if (stateRef.current.simulationMode === 'cloth_sim' || stateRef.current.simulationMode === 'interactive_deform') {
          simPhase += dt * 2.4;
          garmentGroupRef.current.rotation.y = Math.sin(simPhase) * 0.045;
        } else {
          garmentGroupRef.current.rotation.y = 0;
        }
      }

      controls.update();
      renderer.render(scene, camera);

      frameCount++;
      if (now - lastReportAt >= 500) {
        const elapsed = now - lastReportAt;
        const fps = Number(((frameCount * 1000) / Math.max(1, elapsed)).toFixed(1));
        const frameTimeMs = Number((elapsed / Math.max(1, frameCount)).toFixed(2));
        const info = {
          fps,
          frameTimeMs,
          drawCalls: renderer.info.render.calls,
          triangles: renderer.info.render.triangles,
          backend: 'webgl2',
        };
        setTelemetry(info);
        onTelemetry?.(info, caps);
        frameCount = 0;
        lastReportAt = now;
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('click', onPointerClick);
      canvas.removeEventListener('webglcontextlost', onContextLost);
      canvas.removeEventListener('webglcontextrestored', onContextRestored);
      controls.dispose();
      grid.geometry.dispose();
      (grid.material as THREE.Material).dispose();
      meshEditorRef.current?.dispose();
      renderer.dispose();
    };
  }, []);

  // Load candidate GLB model and keep current preview visible cleanly until loaded
  useEffect(() => {
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!scene || !camera || !controls || !glbUrl) return;

    let alive = true;
    new GLTFLoader().load(
      glbUrl,
      (gltf) => {
        if (!alive) return;
        if (garmentGroupRef.current) {
          scene.remove(garmentGroupRef.current);
        }
        const model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        model.position.sub(center);
        scene.add(model);
        garmentGroupRef.current = model;
        modelCenterRef.current.set(0, 0, 0);
        modelDistRef.current = Math.max(0.8, size.length() * 1.45);
        controls.target.set(0, 0, 0);
        camera.position.set(0, 0.12, modelDistRef.current);
        controls.update();

        const editor = meshEditorRef.current;
        if (editor) {
          const cids = editor.indexGarmentScene(model);
          setComponentList(cids);
          const metrics = editor.applyGeometryParameters(model, stateRef.current.geometryParams);
          editor.applyMaterialAndInspectionModes(
            model,
            stateRef.current.material,
            stateRef.current.viewModes,
            stateRef.current.selectedComponent,
            stateRef.current.hoveredComponent
          );
          onMeshMetrics?.(metrics);
        }
        if (canvasRef.current) {
          canvasRef.current.dataset.studioLoaded = 'true';
        }
      },
      undefined,
      () => {
        if (alive) setInitError('Could not load candidate GLB for interactive design.');
      }
    );
    return () => {
      alive = false;
    };
  }, [glbUrl]);

  // Apply real-time geometry mutations whenever geometryVersion changes
  useEffect(() => {
    const model = garmentGroupRef.current;
    const editor = meshEditorRef.current;
    if (!model || !editor) return;
    const metrics = editor.applyGeometryParameters(model, designState.geometryParams);
    onMeshMetrics?.(metrics);
  }, [designState.geometryVersion]);

  // Apply real-time material, selection, and inspection mode updates
  useEffect(() => {
    const model = garmentGroupRef.current;
    const editor = meshEditorRef.current;
    if (!model || !editor) return;
    editor.applyMaterialAndInspectionModes(
      model,
      designState.material,
      designState.viewModes,
      designState.selectedComponent,
      designState.hoveredComponent
    );
  }, [
    designState.materialVersion,
    designState.textureVersion,
    designState.viewModes,
    designState.selectedComponent,
    designState.hoveredComponent,
  ]);

  // Apply lighting & camera presets cleanly
  useEffect(() => {
    if (!rendererRef.current || !lightsRef.current) return;
    applyLightingPreset(
      designState.viewModes.lightingPreset,
      designState.viewModes.exposure,
      rendererRef.current,
      lightsRef.current.hemi,
      lightsRef.current.key,
      lightsRef.current.rim
    );
  }, [designState.viewModes.lightingPreset, designState.viewModes.exposure]);

  useEffect(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const [dx, dy, dz] = CAMERA_ANGLES[designState.cameraPreset] || CAMERA_ANGLES.front;
    const scale = modelDistRef.current / 2.0;
    cameraRef.current.position.set(dx * scale, dy * scale, dz * scale);
    controlsRef.current.target.copy(modelCenterRef.current);
    controlsRef.current.update();
  }, [designState.cameraPreset]);

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: 420, background: '#f1f5f9', borderRadius: 10, overflow: 'hidden', border: '1px solid #cbd5e1' }}>
      {initError ? (
        <div role="alert" style={{ padding: 20, color: '#b91c1c' }}>{initError}</div>
      ) : (
        <canvas
          ref={canvasRef}
          data-testid="interactive-3d-canvas"
          aria-label="Interactive 3D Garment Design Canvas"
          style={{ width: '100%', height: '100%', display: 'block' }}
        />
      )}

      {contextLost && (
        <div role="status" style={{ position: 'absolute', top: 10, left: 10, background: '#fef2f2', color: '#991b1b', padding: '4px 10px', borderRadius: 6, fontSize: 12 }}>
          WebGL context lost — waiting for restore…
        </div>
      )}

      {/* Telemetry & Selected Component Overlay */}
      <div
        data-testid="render-telemetry-hud"
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          background: 'rgba(15, 23, 42, 0.78)',
          color: '#f8fafc',
          padding: '6px 10px',
          borderRadius: 8,
          fontSize: 11,
          fontFamily: 'monospace',
          pointerEvents: 'none',
        }}
      >
        <div>
          Backend: {caps?.preferredBackend || telemetry.backend} ({caps?.tier || 'balanced'}) | WebGPU:{' '}
          {caps?.webgpuAdapterAvailable ? 'adapter' : 'fallback->WebGL2'}
        </div>
        <div>
          FPS: {telemetry.fps} ({telemetry.frameTimeMs}ms) | Calls: {telemetry.drawCalls} | Tris: {telemetry.triangles}
        </div>
        {designState.selectedComponent && (
          <div style={{ color: '#93c5fd' }}>Selected: {designState.selectedComponent}</div>
        )}
      </div>

      {/* Quick Component Chips */}
      {componentList.length > 0 && (
        <div style={{ position: 'absolute', bottom: 8, left: 8, right: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {componentList.map((cid) => (
            <button
              key={cid}
              type="button"
              onClick={() => designEngine.setViewState({ selectedComponent: cid === designState.selectedComponent ? null : cid })}
              style={{
                fontSize: 11,
                padding: '2px 7px',
                borderRadius: 6,
                border: '1px solid #94a3b8',
                background: cid === designState.selectedComponent ? '#1d4ed8' : 'rgba(255,255,255,0.9)',
                color: cid === designState.selectedComponent ? '#fff' : '#0f172a',
                cursor: 'pointer',
              }}
            >
              {cid}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

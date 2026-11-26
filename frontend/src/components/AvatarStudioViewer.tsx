import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import toast from 'react-hot-toast';
import { Character } from '../engine/ara/core/human';
import { AssetLibrary } from '../engine/ara/core/assets';
import { HumanParams } from '../engine/ara/core/params';
import { araEngine } from '../engine/ara/AraService';
import { araAnim } from '../engine/ara/avatarAnimationController';
import { faceExpressionController } from '../engine/ara/faceExpressionController';
import { avatarPerformanceController } from '../engine/humanAvatar';
import { LiveMannequinEngine, FashionPosePreset } from '../engine/mannequin';
import { studio3DAssetManager } from '../engine/ara/Studio3DAssetManager';
import {
  ClothSimulationController,
  SimulationQualityMode,
  FabricProfileId,
  ClothDiagnosticMetrics
} from '../engine/clothPhysics';
import {
  MotionCoreOrchestrator,
  type MotionState,
  type MotionPerformanceTelemetry,
  validateAnimatedGLBExport,
} from '../engine/motionCore';
import { calculateCameraFraming } from '../../../packages/three-renderer/index';
import { AvatarSkeletonLoader } from './SkeletonLoader';
import { GarmentAvatarFittingEngine, UniversalGarmentFittingOrchestrator } from '../engine/garments';
import { GarmentGeometryProcessor } from '../engine/garmentReconstruction/GarmentGeometryProcessor';
import './AvatarStudioViewer.css';

export interface AvatarStudioViewerHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  resetCamera: () => void;
  toggleWireframe: () => void;
  toggleViewMode: () => void;
  playReaction: (reactionName: string) => boolean;
  setPose?: (pose: FashionPosePreset) => void;
  onGarmentEquipped?: (category: string) => void;
  viewFront: () => void;
  viewSide: () => void;
  viewBack: () => void;
  setExpression: (expr: string) => void;
  focusHead?: () => void;
  focusTorso?: () => void;
  focusFullBody?: () => void;
  focusFeet?: () => void;
  syncOutfit?: (params: HumanParams) => void;
  setClothQualityMode?: (mode: SimulationQualityMode) => void;
  setClothFabricProfile?: (profile: FabricProfileId) => void;
  resetClothSimulation?: () => void;
  getClothDiagnostics?: () => ClothDiagnosticMetrics | null;
  playPerformanceIntent?: (intent: any, duration: number) => void;
  setPerformanceState?: (state: 'idle' | 'listening' | 'thinking' | 'speaking') => void;
  interruptPerformance?: () => void;
  getCustomGarmentStats?: () => { fitted: boolean; triangles: number } | null;
  setCustomGarmentAppearance?: (opts: { color?: string; roughness?: number; metalness?: number; wireframe?: boolean }) => boolean;
  setMotionState?: (state: MotionState, customClipName?: string) => boolean;
  getMotionState?: () => MotionState;
  pauseMotion?: () => void;
  resumeMotion?: () => void;
  resetMotionPose?: () => void;
  getMotionTelemetry?: () => MotionPerformanceTelemetry | null;
}

export interface AvatarStudioViewerProps {
  character: Character | null;
  lib: AssetLibrary | null;
  loading?: boolean;
  loadingLabel?: string;
  error?: string | null;
  onRetry?: () => void;
  showSunglasses?: boolean;
  viewMode?: 'full' | 'portrait';
  onViewModeChange?: (mode: 'full' | 'portrait') => void;
  activeAnimation?: string;
  onAnimationTriggered?: (animName: string) => void;
  customGarmentGlbUrl?: string | null;
  customGarmentCategory?: string | null;
  customGarmentSubcategory?: string | null;
  onCustomGarmentFitResult?: (result: {
    url: string;
    fitted: boolean;
    error?: string;
    attachmentType?: 'skinned' | 'bone_parented';
    penetrationCount?: number;
    maxPenetrationMm?: number;
    majorPenetrationDetected?: boolean;
  }) => void;
  heightCm?: number;
  bodySilhouetteId?: string;
  isOnboarding?: boolean;
  clothSimulationEnabled?: boolean;
  fabricProfileId?: FabricProfileId;
  clothQualityMode?: SimulationQualityMode;
}

export const AvatarStudioViewer = forwardRef<AvatarStudioViewerHandle, AvatarStudioViewerProps>(({
  character,
  lib,
  loading = false,
  loadingLabel = 'Building 3D Character...',
  error = null,
  onRetry,
  showSunglasses = false,
  viewMode: controlledViewMode,
  onViewModeChange,
  activeAnimation,
  onAnimationTriggered,
  customGarmentGlbUrl = null,
  customGarmentCategory = null,
  customGarmentSubcategory = null,
  onCustomGarmentFitResult,
  heightCm,
  bodySilhouetteId,
  isOnboarding = false,
  clothSimulationEnabled = true,
  fabricProfileId = 'cotton',
  clothQualityMode = 'balanced'
}, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Three.js instances
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const currentModelRef = useRef<THREE.Object3D | null>(null);
  const [avatarModel, setAvatarModel] = useState<THREE.Object3D | null>(null);
  const lastEquippedUrlRef = useRef<string | null>(null);
  const sunglassesMeshRef = useRef<THREE.Group | null>(null);
  const [garmentFit, setGarmentFit] = useState<{url: string; fitted: boolean} | null>(null);
  const customGarmentRef = useRef<THREE.Object3D | null>(null);
  const textureCacheRef = useRef<Map<string, THREE.Texture>>(new Map());
  const textureLoaderRef = useRef<THREE.TextureLoader>(new THREE.TextureLoader());
  const isFirstLoadRef = useRef(true);
  const groundingFramesRef = useRef(15);
  const mannequinEngineRef = useRef<LiveMannequinEngine | null>(null);
  if (!mannequinEngineRef.current) {
    mannequinEngineRef.current = new LiveMannequinEngine();
  }

  // Phase 10 / 16.9: Unified MotionCore Orchestrator (Animation + IK + XPBD Cloth + Collision + Secondary Motion)
  const clothSimRef = useRef<ClothSimulationController | null>(null);
  if (!clothSimRef.current) {
    clothSimRef.current = new ClothSimulationController(clothQualityMode);
  }
  const motionCoreRef = useRef<MotionCoreOrchestrator | null>(null);
  if (!motionCoreRef.current) {
    motionCoreRef.current = new MotionCoreOrchestrator();
  }

  const [wireframe, setWireframe] = useState(false);
  const [internalViewMode, setInternalViewMode] = useState<'full' | 'portrait'>('full');
  const [internalError, setInternalError] = useState<string | null>(null);
  const viewMode = controlledViewMode ?? internalViewMode;

  const cameraTransitionRef = useRef<{
    isTransitioning: boolean;
    startPos: THREE.Vector3;
    targetPos: THREE.Vector3;
    startTarget: THREE.Vector3;
    endTarget: THREE.Vector3;
    startTime: number;
    duration: number;
  } | null>(null);

  const smoothAnimateCamera = useCallback((targetPos: THREE.Vector3, targetLook: THREE.Vector3, durationMs: number = 550) => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraTransitionRef.current = {
      isTransitioning: true,
      startPos: cameraRef.current.position.clone(),
      targetPos,
      startTarget: controlsRef.current.target.clone(),
      endTarget: targetLook,
      startTime: performance.now(),
      duration: durationMs
    };
  }, []);

  // Initialize Three.js Scene once
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 700;

    // 1. Renderer Initialization (Fault-Tolerant with WebGL Context Detection)
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: true,
        preserveDrawingBuffer: true,
        powerPreference: 'high-performance',
        failIfMajorPerformanceCaveat: false
      });
    } catch (err: any) {
      console.warn('[AvatarStudioViewer] High-performance WebGL init failed, attempting standard fallback:', err);
      try {
        renderer = new THREE.WebGLRenderer({
          canvas,
          antialias: false,
          alpha: true,
          powerPreference: 'default'
        });
      } catch (fatalErr: any) {
        console.error('[AvatarStudioViewer] Fatal WebGL context creation error:', fatalErr);
        setInternalError('WebGL 3D graphics hardware acceleration could not be initialized in this browser environment.');
        return;
      }
    }

    renderer.setClearColor(0x000000, 0); // Explicit transparent clear to show sky-blue gradient
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.localClippingEnabled = true;
    rendererRef.current = renderer;

    // WebGL Context Preservation
    const handleContextLost = (e: Event) => {
      e.preventDefault();
      console.warn('[AvatarStudioViewer] WebGL context lost. Preventing default to allow restoration.');
    };
    const handleContextRestored = () => {
      console.log('[AvatarStudioViewer] WebGL context restored. Rebinding viewport renderer...');
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.setSize(container.clientWidth, container.clientHeight);
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
    };
    canvas.addEventListener('webglcontextlost', handleContextLost, false);
    canvas.addEventListener('webglcontextrestored', handleContextRestored, false);

    // 2. Scene
    const scene = new THREE.Scene();
    scene.background = null; // Always transparent so studio background is purely visible
    sceneRef.current = scene;

    // Studio Environment lighting
    try {
      const pmrem = new THREE.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environmentIntensity = 0.55;
    } catch {
      // Fallback ambient
      const amb = new THREE.AmbientLight(0xffffff, 0.7);
      scene.add(amb);
    }

    const h = heightCm ? heightCm / 100 : 1.78;
    const isPortrait = viewMode === 'portrait';
    const initFraming = isOnboarding
      ? isPortrait
        ? {
            position: [0, h * 0.77, 2.15] as [number, number, number],
            target: [0, h * 0.75, 0] as [number, number, number],
            fov: 28,
            minDistance: 1.60,
            maxDistance: 2.80
          }
        : {
            position: [0, h * 0.44, 3.75] as [number, number, number],
            target: [0, h * 0.44, 0] as [number, number, number],
            fov: 28,
            minDistance: 3.20,
            maxDistance: 4.80
          }
      : calculateCameraFraming(isPortrait ? 'portrait' : 'full', h);
    const camera = new THREE.PerspectiveCamera(initFraming.fov, width / height, 0.05, 50);

    camera.position.set(initFraming.position[0], initFraming.position[1], initFraming.position[2]);
    cameraRef.current = camera;

    // 4. Orbit Controls (centered, fitted orbit range with Apple-grade damping)
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.065;
    controls.enablePan = false; // Always lock pan to keep avatar dead-center in the box

    if (isOnboarding) {
      controls.maxPolarAngle = Math.PI / 2.05;
      controls.minPolarAngle = Math.PI / 3.6; // Keep model upright & centered
      controls.minDistance = isPortrait ? 1.60 : 3.20; // Half-body hair zoom or full-body fitted
      controls.maxDistance = isPortrait ? 2.80 : 4.80;
    } else {
      controls.maxPolarAngle = Math.PI / 2.02; // keeps camera above floor plane
      controls.minPolarAngle = Math.PI / 9;    // ~20 degrees, allows comfortable high-angle view
      controls.minDistance = 2.40;            // calibrated minimum distance prevents camera clipping inside avatar
      controls.maxDistance = 8.00;            // generous zoom out for full perspective
    }

    controls.target.set(initFraming.target[0], initFraming.target[1], initFraming.target[2]);
    controlsRef.current = controls;
    (window as any).__studio = {
      getCamera: () => camera,
      getControls: () => controls,
      getScene: () => scene,
      getModel: () => currentModelRef.current,
      getCustomGarment: () => customGarmentRef.current,
      getFittingEngine: () => GarmentAvatarFittingEngine,
      getGeometryProcessor: () => GarmentGeometryProcessor,
      getMotionCore: () => motionCoreRef.current,
      validateGLBExport: (bytes: Uint8Array) => validateAnimatedGLBExport(bytes),
    };

    // ── Trackpad & Precision Gesture Physics ──
    const orbitVelocity = { x: 0, y: 0 };
    let zoomVelocity = 0;

    const handleCanvasWheel = (e: WheelEvent) => {
      // Prevent browser default back/forward history swipe on horizontal trackpad gesture
      e.preventDefault();
      e.stopImmediatePropagation();

      if (e.ctrlKey) {
        // Trackpad pinch-to-zoom (macOS & Windows Precision Touchpads emit wheel + ctrlKey)
        zoomVelocity += e.deltaY * 0.0035;
      } else {
        // Trackpad two-finger swipe or discrete mouse wheel
        const isTrackpadScroll = Math.abs(e.deltaX) > 0 || Math.abs(e.deltaY) < 40;
        if (isTrackpadScroll) {
          // Horizontal swipe orbits azimuth, vertical swipe tilts elevation smoothly
          orbitVelocity.x += e.deltaX * 0.0022;
          orbitVelocity.y += e.deltaY * 0.0016;
        } else {
          // Discrete mouse scroll wheel zoom
          zoomVelocity += (e.deltaY > 0 ? 1 : -1) * 0.065;
        }
      }
    };

    // Safari native gesture events (macOS / iPadOS)
    let lastGestureScale = 1.0;
    const handleGestureStart = (e: any) => {
      e.preventDefault();
      lastGestureScale = 1.0;
    };
    const handleGestureChange = (e: any) => {
      e.preventDefault();
      const diff = e.scale - lastGestureScale;
      lastGestureScale = e.scale;
      zoomVelocity -= diff * 0.65;
    };
    const handleGestureEnd = (e: any) => {
      e.preventDefault();
    };

    // Double-tap on touch screens to smoothly fit/center frame
    let lastTapTime = 0;
    const handleCanvasTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        const now = performance.now();
        if (now - lastTapTime < 300) {
          e.preventDefault();
          handleResetCamera();
          lastTapTime = 0;
          return;
        }
        lastTapTime = now;
      }
    };

    canvas.addEventListener('wheel', handleCanvasWheel, { passive: false });
    canvas.addEventListener('gesturestart', handleGestureStart, { passive: false });
    canvas.addEventListener('gesturechange', handleGestureChange, { passive: false });
    canvas.addEventListener('gestureend', handleGestureEnd, { passive: false });
    canvas.addEventListener('touchstart', handleCanvasTouchStart, { passive: true });

    // 5. Cloud Ambiance & Studio Three-Point Lighting Setup
    // Soft sky-blue & cloud-white ambient hemisphere light
    const hemiLight = new THREE.HemisphereLight(0xdcf8fe, 0xffffff, 0.9);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight('#ffffff', 1.45);
    keyLight.position.set(1.0, 3.8, 2.4);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.bias = -0.0004;
    keyLight.shadow.normalBias = 0.02;
    keyLight.shadow.radius = 4;
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 10;
    keyLight.shadow.camera.left = -2.5;
    keyLight.shadow.camera.right = 2.5;
    keyLight.shadow.camera.top = 2.8;
    keyLight.shadow.camera.bottom = -0.8;
    scene.add(keyLight);

    // Soft Champagne & Warm Rim / Backlight for natural silhouette separation
    const rimLight = new THREE.DirectionalLight('#fffaf0', 0.95);
    rimLight.position.set(-1.8, 2.6, -2.5);
    scene.add(rimLight);

    const rimLight2 = new THREE.DirectionalLight('#f8fafc', 0.75);
    rimLight2.position.set(1.8, 2.2, -2.2);
    scene.add(rimLight2);

    // Soft Warm Fill Light
    const fillLight = new THREE.DirectionalLight('#ffffff', 0.65);
    fillLight.position.set(-2.0, 1.2, 2.0);
    scene.add(fillLight);

    // Seamless infinite contact shadow floor
    const floorGeo = new THREE.PlaneGeometry(30, 30).rotateX(-Math.PI / 2);
    const floorMat = new THREE.ShadowMaterial({
      opacity: 0.16
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.receiveShadow = true;
    floor.position.y = 0;
    scene.add(floor);

    // Responsive Resize Observer
    const resizeObserver = new ResizeObserver(() => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w === 0 || h === 0) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    resizeObserver.observe(container);

    // Render loop with high-precision timestamp delta calculation
    let animId: number;
    let lastTime = performance.now();
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (typeof document !== 'undefined' && document.hidden) return;
      const now = performance.now();
      const delta = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;
      motionCoreRef.current?.step(delta);

      if (groundingFramesRef.current > 0 && currentModelRef.current) {
        alignFeetToGround(currentModelRef.current);
        groundingFramesRef.current--;
      }

      if (cameraTransitionRef.current?.isTransitioning) {
        const trans = cameraTransitionRef.current;
        const now = performance.now();
        const elapsed = now - trans.startTime;
        const p = Math.min(1, elapsed / trans.duration);
        const ease = 1 - Math.pow(1 - p, 3);
        camera.position.lerpVectors(trans.startPos, trans.targetPos, ease);
        controls.target.lerpVectors(trans.startTarget, trans.endTarget, ease);
        if (p >= 1) {
          cameraTransitionRef.current = null;
        }
      }

      // Advanced smooth trackpad orbit damping (glides with exponential friction)
      if (Math.abs(orbitVelocity.x) > 0.00002 || Math.abs(orbitVelocity.y) > 0.00002) {
        controls.rotateLeft(orbitVelocity.x);
        controls.rotateUp(orbitVelocity.y);
        orbitVelocity.x *= 0.88;
        orbitVelocity.y *= 0.88;
      }

      // Advanced smooth trackpad pinch zoom damping
      if (Math.abs(zoomVelocity) > 0.00002) {
        const currentDist = camera.position.distanceTo(controls.target);
        const targetDist = THREE.MathUtils.clamp(
          currentDist * (1 + zoomVelocity),
          controls.minDistance,
          controls.maxDistance
        );
        const dir = camera.position.clone().sub(controls.target).normalize();
        camera.position.copy(controls.target).addScaledVector(dir, targetDist);
        zoomVelocity *= 0.84;
      }

      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      resizeObserver.disconnect();
      canvas.removeEventListener('webglcontextlost', handleContextLost);
      canvas.removeEventListener('webglcontextrestored', handleContextRestored);
      canvas.removeEventListener('wheel', handleCanvasWheel);
      canvas.removeEventListener('gesturestart', handleGestureStart);
      canvas.removeEventListener('gesturechange', handleGestureChange);
      canvas.removeEventListener('gestureend', handleGestureEnd);
      canvas.removeEventListener('touchstart', handleCanvasTouchStart);
      renderer.dispose();
      studio3DAssetManager.disposeObject3D(currentModelRef.current);
      studio3DAssetManager.disposeObject3D(customGarmentRef.current);
      araAnim.dispose();
      clothSimRef.current?.dispose();
      motionCoreRef.current?.dispose();
    };
  }, []);

  // Texture loader helper
  const loadTexture = useCallback((fileName: string, isColor: boolean): THREE.Texture => {
    const key = `${fileName}_${isColor}`;
    let tex = textureCacheRef.current.get(key);
    if (!tex && lib) {
      const url = lib.textureUrl(fileName);
      tex = textureLoaderRef.current.load(url);
      tex.flipY = false; // CRUCIAL: glTF uses top-left UV coordinates origin
      tex.colorSpace = isColor ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      tex.anisotropy = 8;
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      textureCacheRef.current.set(key, tex);
    }
    return tex!;
  }, [lib]);

  // Build Sleek Fashion Sunglasses accessory group
  const createSunglassesMesh = useCallback((characterHeight: number) => {
    const glasses = new THREE.Group();
    const hScale = characterHeight / 1.70;

    const frameMat = new THREE.MeshStandardMaterial({
      color: 0x18181b,
      metalness: 0.95,
      roughness: 0.15,
      wireframe
    });

    const lensMat = new THREE.MeshPhysicalMaterial({
      color: 0x1f2937,
      roughness: 0.06,
      metalness: 0.20,
      clearcoat: 1.0,
      clearcoatRoughness: 0.03,
      transmission: 0.40,
      thickness: 0.003,
      transparent: true,
      opacity: 0.75
    });

    // Sleek, refined curved luxury designer lenses
    const lensGeo = new THREE.CylinderGeometry(0.022 * hScale, 0.022 * hScale, 0.0015 * hScale, 32);
    lensGeo.rotateX(Math.PI / 2);
    const leftLens = new THREE.Mesh(lensGeo, lensMat);
    leftLens.position.set(-0.031 * hScale, 0, 0);
    leftLens.scale.set(1.22, 0.82, 1);

    const rightLens = new THREE.Mesh(lensGeo, lensMat);
    rightLens.position.set(0.031 * hScale, 0, 0);
    rightLens.scale.set(1.22, 0.82, 1);

    // Slim wireframe bridge
    const bridgeGeo = new THREE.CylinderGeometry(0.0008 * hScale, 0.0008 * hScale, 0.014 * hScale, 12);
    bridgeGeo.rotateZ(Math.PI / 2);
    const bridge = new THREE.Mesh(bridgeGeo, frameMat);
    bridge.position.set(0, 0.005 * hScale, 0.001 * hScale);

    // Slim subtle arms
    const armGeo = new THREE.CylinderGeometry(0.0008 * hScale, 0.0008 * hScale, 0.095 * hScale, 8);
    armGeo.rotateX(Math.PI / 2);
    const leftArm = new THREE.Mesh(armGeo, frameMat);
    leftArm.position.set(-0.049 * hScale, 0.003 * hScale, -0.046 * hScale);
    const rightArm = new THREE.Mesh(armGeo, frameMat);
    rightArm.position.set(0.049 * hScale, 0.003 * hScale, -0.046 * hScale);

    glasses.add(leftLens);
    glasses.add(rightLens);
    glasses.add(bridge);
    glasses.add(leftArm);
    glasses.add(rightArm);

    return glasses;
  }, [wireframe]);

  // Helper to compute live stature and silhouette scale
  const computeStatureScale = useCallback((cm?: number, silhouetteId?: string) => {
    // The unscaled MakeHuman / Ara rigged GLTF in Three.js has raw mesh height character?.height (~1.414m)
    const rawMeshHeightM = character?.height || 1.414;
    // Target height in cm (default adult avatar standard: 178cm)
    const targetCm = cm || 178;
    const targetHeightM = targetCm / 100;
    const statureScale = targetHeightM / rawMeshHeightM;
    const scaleY = statureScale;

    let widthMul = 1.0;
    let depthMul = 1.0;

    switch (silhouetteId) {
      case 'slender':
        widthMul = 0.92;
        depthMul = 0.92;
        break;
      case 'athletic':
        widthMul = 1.05;
        depthMul = 1.01;
        break;
      case 'curvy':
        widthMul = 1.05;
        depthMul = 1.08;
        break;
      case 'broad':
        widthMul = 1.11;
        depthMul = 1.08;
        break;
      case 'fuller':
        widthMul = 1.15;
        depthMul = 1.14;
        break;
      case 'regular':
      default:
        widthMul = 1.0;
        depthMul = 1.0;
        break;
    }

    const scaleX = scaleY * widthMul;
    const scaleZ = scaleY * depthMul;
    return { scaleX, scaleY, scaleZ, targetCm };
  }, [character?.height]);

  // Helper to ground rigged character model cleanly on the floor plane (Y = 0)
  const computeGroundOffset = useCallback((_root?: THREE.Object3D, scaleY: number = 1.0) => {
    // In MakeHuman / Ara standard humanoid armature, the hips are at local (0, 0, 0),
    // and the feet extend down by 0.725m in the rest/idle pose.
    // Offsetting the root by 0.725 * scaleY places the soles of the shoes cleanly on the ground floor plane.
    return 0.725 * scaleY;
  }, []);

  const alignFeetToGround = useCallback((root: THREE.Object3D | null) => {
    if (!root) return;
    root.updateMatrixWorld(true);
    const leftFoot = root.getObjectByName('LeftFoot') || root.getObjectByName('leftfoot');
    const rightFoot = root.getObjectByName('RightFoot') || root.getObjectByName('rightfoot');
    let footY = Infinity;
    if (leftFoot) {
      const wp = new THREE.Vector3().setFromMatrixPosition(leftFoot.matrixWorld);
      footY = Math.min(footY, wp.y);
    }
    if (rightFoot) {
      const wp = new THREE.Vector3().setFromMatrixPosition(rightFoot.matrixWorld);
      footY = Math.min(footY, wp.y);
    }
    if (footY < -0.05 || (footY > 0.15 && footY !== Infinity)) {
      root.position.y += (0.02 - footY);
      root.updateMatrixWorld(true);
    }
  }, []);

  // Update Character 3D Mesh whenever character changes
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !character || !lib) return;

    let isCancelled = false;

    const loadSkinnedModel = async () => {
      try {
        // 1. Export character with real Ara 3D Gen clips baked (Idle, Wave, Cheer, Turn)
        const glbBytes = await araEngine.exportCharacterGlb(character, true);
        if (isCancelled) return;

        // 2. Parse using centralized Studio3DAssetManager
        const gltf = await studio3DAssetManager.parseGLB(glbBytes.buffer as ArrayBuffer, '');
        if (isCancelled) return;

        // 3. Remove previous character model from scene
        if (currentModelRef.current) {
          if (customGarmentRef.current && customGarmentRef.current.parent) {
            customGarmentRef.current.parent.remove(customGarmentRef.current);
          }
          scene.remove(currentModelRef.current);
          studio3DAssetManager.disposeObject3D(currentModelRef.current);
          currentModelRef.current = null;
          customGarmentRef.current = null;
        }

        const modelRoot = gltf.scene;

        // If custom 3D AI garment is currently equipped, immediately hide base avatar clothing
        // so default uniform shirt or trousers never flash or display during character load
        if (customGarmentGlbUrl) {
          GarmentAvatarFittingEngine.updateAvatarClothingVisibility(
            modelRoot,
            customGarmentCategory || 'top',
            true
          );
        }

        // 4. Traverse meshes and attach shadow/textures with Cloud white & skyblue aesthetic
        modelRoot.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const m = child as THREE.Mesh;
            // Strictly protect custom AI fitted garments (including multi-component children) from base avatar material traversal
            if (
              m.name === 'custom_ai_garment_fitted' ||
              m.name === 'custom_ai_garment' ||
              m.userData?.isCustomAiGarment ||
              m.parent?.name === 'custom_ai_garment_fitted'
            ) {
              return;
            }
            m.castShadow = true;
            m.receiveShadow = true;
            m.frustumCulled = false; // Prevent clipping during full turns or gestural poses

            const mats = Array.isArray(m.material) ? m.material : [m.material];
            mats.forEach((mat) => {
              const stdMat = mat as THREE.MeshStandardMaterial;
              const matName = (stdMat.name || m.name || '').toLowerCase();
              
              // Find matching material from Ara character definition by name
              const origMat = character.mesh.materials.find(
                x => x.name && (matName.includes(x.name.toLowerCase()) || x.name.toLowerCase().includes(matName))
              );

              stdMat.wireframe = wireframe;

              // Distinguish body parts and garments
              const isSkin = matName.includes('skin') || matName.includes('body') || matName.includes('head') || matName.includes('face') || matName.includes('arm') || matName.includes('hand') || matName.includes('leg') || matName.includes('caucasian') || matName.includes('african') || matName.includes('asian');
              const isHair = matName.includes('hair') || matName.includes('eyebrow') || matName.includes('lash') || matName.includes('beard') || matName.includes('mhair');
              const isEyes = matName.includes('eye');

              if (origMat) {
                if (origMat.map) {
                  if (!stdMat.map) {
                    stdMat.map = loadTexture(origMat.map, true);
                  } else {
                    stdMat.map.flipY = false;
                    stdMat.map.colorSpace = THREE.SRGBColorSpace;
                    stdMat.map.needsUpdate = true;
                  }
                }
                if (origMat.normalMap) {
                  if (!stdMat.normalMap) {
                    stdMat.normalMap = loadTexture(origMat.normalMap, false);
                  } else {
                    stdMat.normalMap.flipY = false;
                    stdMat.normalMap.colorSpace = THREE.NoColorSpace;
                    stdMat.normalMap.needsUpdate = true;
                  }
                }
                stdMat.roughness = origMat.roughness ?? 0.65;
                stdMat.metalness = origMat.metalness ?? 0.05;

                if (origMat.doubleSided) {
                  stdMat.side = THREE.DoubleSide;
                  stdMat.shadowSide = THREE.FrontSide;
                }
                if (origMat.alpha === 'mask') {
                  stdMat.alphaTest = 0.35;
                  stdMat.alphaToCoverage = true;
                } else if (origMat.alpha === 'blend') {
                  stdMat.transparent = true;
                  stdMat.opacity = origMat.opacity ?? 1;
                  stdMat.depthWrite = true;
                  if (origMat.map) stdMat.alphaTest = 0.05;
                }
              }

              // Real Garment Materials & User Personalization
              if (isSkin) {
                // Natural realistic skin: diffuse map is high-fidelity color photography
                // Preserve map purity with neutral white base to prevent yellow jaundice discoloration
                stdMat.color = new THREE.Color('#ffffff');
                stdMat.roughness = 0.62;
                stdMat.metalness = 0.0;
                stdMat.envMapIntensity = 0.38;
              } else if (isHair) {
                // Hair color matching user's selected swatch with natural fiber scattering
                stdMat.color = new THREE.Color(character.params?.hairColor || character.params?.hairTint || '#1e293b');
                stdMat.roughness = 0.58;
                stdMat.metalness = 0.04;
                stdMat.side = THREE.DoubleSide;
                stdMat.shadowSide = THREE.DoubleSide;
                stdMat.transparent = false;
                // Low threshold (0.05) preserves fine hair strands and wisps without creating see-through holes in back view
                stdMat.alphaTest = 0.05;
                stdMat.depthWrite = true;
                stdMat.depthTest = true;
                stdMat.polygonOffset = true;
                stdMat.polygonOffsetFactor = -2.0;
                stdMat.polygonOffsetUnits = -4.0;
                m.renderOrder = 2;
                stdMat.envMapIntensity = 0.50;
              } else if (isEyes) {
                // Keep authentic iris diffuse map, neutral white tint, cornea clearcoat catchlight
                stdMat.color = new THREE.Color('#ffffff');
                stdMat.roughness = 0.05;
                stdMat.metalness = 0.02;
                (stdMat as any).clearcoat = 1.0;
                (stdMat as any).clearcoatRoughness = 0.04;
                stdMat.envMapIntensity = 1.60;
              } else {
                // Genuine Garment Material: Honor the real texture and color generated by the 3D pipeline
                if (origMat?.map) {
                  // For mapped textures without color override, white preserves the map's diffuse fidelity
                  stdMat.color = new THREE.Color(
                    origMat.color && origMat.color.toLowerCase() !== '#000000' && origMat.color.toLowerCase() !== '#808080'
                      ? origMat.color
                      : '#ffffff'
                  );
                } else if (origMat?.color) {
                  stdMat.color = new THREE.Color(origMat.color);
                } else {
                  stdMat.color = new THREE.Color(stdMat.color || '#f1f5f9');
                }
                stdMat.roughness = origMat?.roughness ?? 0.65;
                stdMat.metalness = origMat?.metalness ?? 0.05;
                stdMat.envMapIntensity = 0.70;
              }

              stdMat.needsUpdate = true;
            });
          }
        });

        scene.add(modelRoot);
        currentModelRef.current = modelRoot;
        setAvatarModel(modelRoot);
        const initialScale = computeStatureScale(heightCm, bodySilhouetteId);
        modelRoot.scale.set(initialScale.scaleX, initialScale.scaleY, initialScale.scaleZ);
        modelRoot.position.y = computeGroundOffset(modelRoot, initialScale.scaleY);
        modelRoot.updateMatrixWorld(true);

        // 5. Initialize Unified MotionCore Orchestrator (Single mixer, skeleton retargeting, cloth sync, facial & gestures)
        console.log('[AraAvatarViewer] Real animation clips detected:', gltf.animations.map(a => a.name));
        mannequinEngineRef.current?.syncFromHumanParams(character.params, modelRoot);
        faceExpressionController.init(modelRoot);
        faceExpressionController.setExpression((character.params?.expression as any) || 'neutral');
        avatarPerformanceController.init(modelRoot, gltf.animations);
        await motionCoreRef.current?.initAvatar(modelRoot, gltf.animations, {
          onExternalFacialAndGestureTick: (dt) => {
            faceExpressionController.update(dt);
            avatarPerformanceController.update(dt);
          },
        });
        alignFeetToGround(modelRoot);
        groundingFramesRef.current = 15;
        clothSimRef.current?.init(modelRoot);

        // 6. Ensure idle breathing cycle remains active without abrupt initial body contortions
        if (isFirstLoadRef.current) {
          isFirstLoadRef.current = false;
          if (controlsRef.current && cameraRef.current) {
            const effectiveH = initialScale.targetCm / 100;
            const isPortrait = (controlledViewMode ?? internalViewMode) === 'portrait';
            const framing = calculateCameraFraming(isPortrait ? 'portrait' : 'full', effectiveH);
            controlsRef.current.target.set(0, framing.target[1], 0);
            cameraRef.current.position.set(0, framing.position[1], framing.position[2]);
            controlsRef.current.update();
          }
        }

        // 7. Attach Sunglasses to Head bone if present, so sunglasses track animation gestures
        if (sunglassesMeshRef.current) {
          scene.remove(sunglassesMeshRef.current);
          sunglassesMeshRef.current = null;
        }

        if (showSunglasses) {
          const glasses = createSunglassesMesh(character.height);
          const headBone = modelRoot.getObjectByName('Head') || modelRoot.getObjectByName('head');
          if (headBone) {
            headBone.add(glasses);
            const hScale = character.height / 1.70;
            glasses.position.set(0, 0.070 * hScale, 0.125 * hScale);
            glasses.rotation.set(0, 0, 0);
          } else {
            const hScale = character.height / 1.70;
            glasses.position.set(0, character.height * 0.925, 0.128 * hScale);
            modelRoot.add(glasses);
          }
          sunglassesMeshRef.current = glasses;
          motionCoreRef.current?.registerSecondaryNode('sunglasses_accessory', glasses, 'accessory');
        }
      } catch (err) {
        console.warn('[AraAvatarViewer] Rigged GLTF loading fallback:', err);
        fallbackStaticMesh();
      }
    };

    // Fallback static mesh generator if GLTF parse encounters any unexpected environment error
    const fallbackStaticMesh = () => {
      const { mesh: m } = character;
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(m.positions, 3));
      geo.setAttribute('normal', new THREE.BufferAttribute(m.normals, 3));
      if (m.uvs) {
        const uvs = new Float32Array(m.uvs.length);
        for (let i = 0; i < m.uvs.length; i += 2) {
          uvs[i] = m.uvs[i];
          uvs[i + 1] = 1 - m.uvs[i + 1];
        }
        geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
      }

      const total = m.groups.reduce((n, g) => n + g.indices.length, 0);
      const index = new Uint32Array(total);
      let o = 0;
      for (const g of m.groups) {
        index.set(g.indices, o);
        geo.addGroup(o, g.indices.length, g.material);
        o += g.indices.length;
      }
      geo.setIndex(new THREE.BufferAttribute(index, 1));

      const materials: THREE.Material[] = m.materials.map(mt => {
        return new THREE.MeshStandardMaterial({
          name: mt.name,
          color: new THREE.Color(mt.color || '#ffffff'),
          roughness: mt.roughness ?? 0.65,
          metalness: mt.metalness ?? 0.05,
          map: mt.map ? loadTexture(mt.map, true) : null,
          normalMap: mt.normalMap ? loadTexture(mt.normalMap, false) : null,
          side: mt.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
          wireframe
        });
      });

      const mesh = new THREE.Mesh(geo, materials);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
      currentModelRef.current = mesh;
      setAvatarModel(mesh);
      const initialScale = computeStatureScale(heightCm, bodySilhouetteId);
      mesh.scale.set(initialScale.scaleX, initialScale.scaleY, initialScale.scaleZ);

      if (showSunglasses) {
        const glasses = createSunglassesMesh(character.height);
        glasses.position.set(0, character.height * 0.925, 0.12 * (character.height / 1.70));
        scene.add(glasses);
        sunglassesMeshRef.current = glasses;
      }
    };

    loadSkinnedModel();

    return () => {
      isCancelled = true;
    };
  }, [character, lib, loadTexture, showSunglasses, wireframe, createSunglassesMesh, computeStatureScale, computeGroundOffset, heightCm, bodySilhouetteId]);

  // Real-time material color live updates on the active 3D model
  useEffect(() => {
    if (!currentModelRef.current || !character?.params) return;
    const hairColor = character.params.hairColor || character.params.hairTint;

    currentModelRef.current.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const m = child as THREE.Mesh;
        const mats = Array.isArray(m.material) ? m.material : [m.material];
        mats.forEach((mat) => {
          const stdMat = mat as THREE.MeshStandardMaterial;
          const matName = (stdMat.name || m.name || '').toLowerCase();
          const isSkin = matName.includes('skin') || matName.includes('body') || matName.includes('head') || matName.includes('face') || matName.includes('arm') || matName.includes('hand') || matName.includes('leg') || matName.includes('caucasian') || matName.includes('african') || matName.includes('asian');
          const isHair = matName.includes('hair') || matName.includes('eyebrow') || matName.includes('lash') || matName.includes('beard') || matName.includes('mhair');

          if (isSkin) {
            stdMat.color = new THREE.Color('#ffffff');
            stdMat.needsUpdate = true;
          } else if (isHair && hairColor) {
            stdMat.color = new THREE.Color(hairColor);
            stdMat.needsUpdate = true;
          }
        });
      }
    });
  }, [character?.params?.skinTint, character?.params?.hairColor, character?.params?.hairTint]);

  // Live Instant Stature & Body Silhouette Scaling without reloading GLTF
  useEffect(() => {
    const model = currentModelRef.current;
    if (!model) return;

    const { scaleX, scaleY, scaleZ, targetCm } = computeStatureScale(heightCm, bodySilhouetteId);
    model.scale.set(scaleX, scaleY, scaleZ);
    model.position.y = computeGroundOffset(model, scaleY);
    model.updateWorldMatrix(true, true);
    alignFeetToGround(model);
    groundingFramesRef.current = 15;

    if (controlsRef.current && cameraRef.current) {
      const effectiveH = targetCm / 100;
      const isPortrait = (controlledViewMode ?? internalViewMode) === 'portrait';
      const framing = calculateCameraFraming(isPortrait ? 'portrait' : 'full', effectiveH);
      controlsRef.current.target.set(0, framing.target[1], 0);
      cameraRef.current.position.set(0, framing.position[1], framing.position[2]);
      controlsRef.current.update();
    }
  }, [heightCm, bodySilhouetteId, computeStatureScale, computeGroundOffset, controlledViewMode, internalViewMode]);

  // Synchronize facial expression changes directly into faceExpressionController
  useEffect(() => {
    if (character?.params?.expression) {
      faceExpressionController.setExpression(character.params.expression as any);
    }
  }, [character?.params?.expression]);

  // Handle activeAnimation prop change via single MotionCore mixer
  useEffect(() => {
    if (!activeAnimation || !motionCoreRef.current) return;
    const upper = activeAnimation.toUpperCase().trim();
    if (upper === 'IDLE') {
      motionCoreRef.current.transitionTo('IDLE');
      onAnimationTriggered?.(activeAnimation);
    } else if (['WALK', 'RUN', 'TURN', 'RAISE_ARMS', 'BEND', 'SIT', 'STAND'].includes(upper)) {
      motionCoreRef.current.transitionTo(upper as MotionState);
      onAnimationTriggered?.(activeAnimation);
    } else {
      motionCoreRef.current.transitionTo('CUSTOM', { customClipName: activeAnimation });
      onAnimationTriggered?.(activeAnimation);
    }
  }, [activeAnimation, onAnimationTriggered]);

  // ── 3D Custom AI Garment Fitting & Occlusion Masking ──
  useEffect(() => {
    const scene = sceneRef.current;
    const modelRoot = avatarModel || currentModelRef.current;
    setGarmentFit(null);
    if (!scene || !modelRoot) return;

    // 1. Cleanup previous custom garment & detach physics
    if (customGarmentRef.current) {
      GarmentAvatarFittingEngine.detachGarment(modelRoot);
      if (customGarmentRef.current.parent) {
        customGarmentRef.current.parent.remove(customGarmentRef.current);
      } else {
        scene.remove(customGarmentRef.current);
      }
      clothSimRef.current?.detachGarment('custom_ai_garment');
      motionCoreRef.current?.detachGarment();
      customGarmentRef.current = null;
    }

    if (!customGarmentGlbUrl) {
      lastEquippedUrlRef.current = null;
      // Without custom AI overlay, restore default clothing visibility
      GarmentAvatarFittingEngine.updateAvatarClothingVisibility(modelRoot, null, false);
      if (character?.params && mannequinEngineRef.current) {
        mannequinEngineRef.current.syncFromHumanParams(character.params, modelRoot);
      }
      return;
    }

    let isCancelled = false;
    const normCategory = (customGarmentCategory || 'top').toLowerCase();

    // Immediately hide conflicting base avatar clothing so it never flashes or pokes through
    GarmentAvatarFittingEngine.updateAvatarClothingVisibility(modelRoot, normCategory, true);

    const { promise: loadPromise, abort } = studio3DAssetManager.loadGLB(
      customGarmentGlbUrl,
      'high'
    );

    loadPromise.then(
      (gltf) => {
        if (isCancelled || currentModelRef.current !== modelRoot) return;
        const garmentGroup = gltf.scene;
        garmentGroup.name = 'custom_ai_garment';

        try {
          // Atomic detach before attaching to prevent duplicate garments on rapid switches
          GarmentAvatarFittingEngine.detachGarment(modelRoot);

          // Unified Phase 17.5 Universal Garment & Accessory Fitting Pipeline
          const orchResult = UniversalGarmentFittingOrchestrator.fitAndAttach(
            garmentGroup,
            modelRoot,
            {
              category: normCategory,
              subcategory: customGarmentSubcategory || undefined,
              wireframe,
              attachmentMode: 'auto',
              minClearanceMeters: 0.0030,
              preserveOtherLayers: true,
            }
          );

          if (!orchResult.success || !orchResult.attachedObject) {
            throw new Error(orchResult.error || 'The fitted mesh was not attached to the avatar.');
          }
          customGarmentRef.current = orchResult.attachedObject;
          setGarmentFit({url: customGarmentGlbUrl, fitted: true});

          // Double check base clothing visibility after attachment
          GarmentAvatarFittingEngine.updateAvatarClothingVisibility(modelRoot, normCategory, true);

          // Attach fitted single-mesh OR multi-component garment cleanly to MotionCore dynamics
          if (orchResult.attachmentType === 'skinned' || orchResult.attachmentType === 'bone_parented') {
            motionCoreRef.current?.attachGarment(orchResult.attachedObject, normCategory, {
              fabricHint: fabricProfileId || undefined,
              hasConstructionSeams: true,
            });
          }

          onCustomGarmentFitResult?.({
            url: customGarmentGlbUrl,
            fitted: true,
            attachmentType: orchResult.attachmentType === 'skinned' ? 'skinned' : 'bone_parented',
            penetrationCount: orchResult.diagnostics.penetrationCount,
            maxPenetrationMm: orchResult.diagnostics.maxPenetrationMm,
            majorPenetrationDetected: orchResult.diagnostics.majorPenetrationDetected,
          });

          // Only celebrate if this is a newly equipped garment (not a character reload)
          const isFreshEquip = lastEquippedUrlRef.current !== customGarmentGlbUrl;
          lastEquippedUrlRef.current = customGarmentGlbUrl;
          if (isFreshEquip) {
            motionCoreRef.current?.transitionTo('TURN');
          }
        } catch (fitErr) {
          const errMsg = fitErr instanceof Error ? fitErr.message : 'Could not fit garment onto avatar.';
          console.error('[AraAvatarViewer] GarmentAvatarFittingEngine failed:', fitErr);
          GarmentAvatarFittingEngine.detachGarment(modelRoot);
          GarmentAvatarFittingEngine.updateAvatarClothingVisibility(modelRoot, null, false);
          setGarmentFit({url: customGarmentGlbUrl, fitted: false});
          onCustomGarmentFitResult?.({ url: customGarmentGlbUrl, fitted: false, error: errMsg });
        }
      },
      (err) => {
        if (!isCancelled) {
          const errMsg = err instanceof Error ? err.message : 'Failed to load custom garment GLB.';
          console.error('[AraAvatarViewer] Failed to load custom garment GLB:', err);
          GarmentAvatarFittingEngine.detachGarment(modelRoot);
          GarmentAvatarFittingEngine.updateAvatarClothingVisibility(modelRoot, null, false);
          setGarmentFit({url: customGarmentGlbUrl, fitted: false});
          onCustomGarmentFitResult?.({ url: customGarmentGlbUrl, fitted: false, error: errMsg });
        }
      }
    );

    return () => {
      isCancelled = true;
      abort();
    };
  }, [customGarmentGlbUrl, customGarmentCategory, customGarmentSubcategory, avatarModel, wireframe, fabricProfileId]);

  // Update Camera based on viewMode and character height
  useEffect(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = heightCm ? heightCm / 100 : 1.78;
    const isPortrait = viewMode === 'portrait';

    if (isOnboarding) {
      const targetPos = isPortrait
        ? new THREE.Vector3(0, h * 0.77, 2.15)
        : new THREE.Vector3(0, h * 0.50, 4.05);
      const targetLook = isPortrait
        ? new THREE.Vector3(0, h * 0.75, 0)
        : new THREE.Vector3(0, h * 0.50, 0);

      controlsRef.current.minDistance = isPortrait ? 1.60 : 3.20;
      controlsRef.current.maxDistance = isPortrait ? 2.80 : 4.80;
      controlsRef.current.enablePan = false;

      smoothAnimateCamera(targetPos, targetLook, 500);
      return;
    }
    const framing = calculateCameraFraming(viewMode, h);
    const targetPos = new THREE.Vector3(framing.position[0], framing.position[1], framing.position[2]);
    const targetLook = new THREE.Vector3(framing.target[0], framing.target[1], framing.target[2]);
    smoothAnimateCamera(targetPos, targetLook, 520);
  }, [viewMode, heightCm, isOnboarding, smoothAnimateCamera]);

  // Reset view to default (always restores full-body hero view)
  const handleResetCamera = () => {
    if (!cameraRef.current || !controlsRef.current) return;
    if (viewMode !== 'full') {
      if (onViewModeChange) onViewModeChange('full');
      else setInternalViewMode('full');
    }
    const h = heightCm ? heightCm / 100 : 1.78;
    const framing = calculateCameraFraming('full', h);
    const targetPos = new THREE.Vector3(framing.position[0], framing.position[1], framing.position[2]);
    const targetLook = new THREE.Vector3(framing.target[0], framing.target[1], framing.target[2]);
    smoothAnimateCamera(targetPos, targetLook, 400);
  };

  const toggleViewMode = () => {
    const next = viewMode === 'portrait' ? 'full' : 'portrait';
    if (onViewModeChange) {
      onViewModeChange(next);
    } else {
      setInternalViewMode(next);
    }
  };

  const handleZoom = (inwards: boolean) => {
    if (!cameraRef.current || !controlsRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const h = heightCm ? heightCm / 100 : 1.78;
    const isPortrait = viewMode === 'portrait';
    const framing = calculateCameraFraming(viewMode, h);

    // Current horizontal azimuth angle (preserves whatever angle the user rotated to)
    const currentAngle = Math.atan2(camera.position.x, camera.position.z);

    // Current distance to current target
    const currentDist = camera.position.distanceTo(controls.target);

    const MIN_DISTANCE = isOnboarding ? (isPortrait ? 1.60 : 3.20) : framing.minDistance;
    const MAX_DISTANCE = isOnboarding ? (isPortrait ? 2.80 : 4.80) : framing.maxDistance;

    let nextDist: number;
    if (inwards) {
      if (currentDist <= MIN_DISTANCE + 0.05) {
        toast('Maximum zoom reached', { duration: 900 });
        return;
      }
      nextDist = Math.max(currentDist * 0.85, MIN_DISTANCE);
    } else {
      if (currentDist >= MAX_DISTANCE - 0.05) {
        toast('Minimum zoom reached', { duration: 900 });
        return;
      }
      nextDist = Math.min(currentDist * 1.15, MAX_DISTANCE);
    }

    // Smoothly glide camera with cubic ease-out
    const targetPos = new THREE.Vector3(
      Math.sin(currentAngle) * nextDist,
      framing.position[1],
      Math.cos(currentAngle) * nextDist
    );
    const targetLook = new THREE.Vector3(0, framing.target[1], 0);
    smoothAnimateCamera(targetPos, targetLook, 340);
  };

  const inspectAngle = (azimuthRad: number) => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = heightCm ? heightCm / 100 : 1.78;
    const framing = calculateCameraFraming(viewMode, h);
    const dist = framing.position[2]; // Use calibrated framing distance for standard angles
    const targetLook = new THREE.Vector3(framing.target[0], framing.target[1], framing.target[2]);
    const targetPos = new THREE.Vector3(
      targetLook.x + Math.sin(azimuthRad) * dist,
      framing.position[1],
      targetLook.z + Math.cos(azimuthRad) * dist
    );
    smoothAnimateCamera(targetPos, targetLook, 380);
  };

  const focusHead = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = heightCm ? heightCm / 100 : 1.78;
    const targetPos = new THREE.Vector3(0, h * 0.82, 4.00);
    const targetLook = new THREE.Vector3(0, h * 0.75, 0);
    smoothAnimateCamera(targetPos, targetLook, 450);
  }, [heightCm, smoothAnimateCamera]);

  const focusTorso = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = heightCm ? heightCm / 100 : 1.78;
    const targetPos = new THREE.Vector3(0, h * 0.68, 4.40);
    const targetLook = new THREE.Vector3(0, h * 0.58, 0);
    smoothAnimateCamera(targetPos, targetLook, 450);
  }, [heightCm, smoothAnimateCamera]);

  const focusFullBody = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    if (viewMode !== 'full') {
      if (onViewModeChange) onViewModeChange('full');
      else setInternalViewMode('full');
    }
    const h = heightCm ? heightCm / 100 : 1.78;
    const framing = calculateCameraFraming('full', h);
    const targetPos = new THREE.Vector3(framing.position[0], framing.position[1], framing.position[2]);
    const targetLook = new THREE.Vector3(framing.target[0], framing.target[1], framing.target[2]);
    smoothAnimateCamera(targetPos, targetLook, 400);
  }, [heightCm, smoothAnimateCamera, viewMode, onViewModeChange]);

  const focusFeet = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = heightCm ? heightCm / 100 : 1.78;
    const targetPos = new THREE.Vector3(0, h * 0.40, 4.20);
    const targetLook = new THREE.Vector3(0, h * 0.20, 0);
    smoothAnimateCamera(targetPos, targetLook, 450);
  }, [heightCm, smoothAnimateCamera]);

  // Synchronize cloth simulation props
  useEffect(() => {
    if (clothSimulationEnabled !== undefined) {
      clothSimRef.current?.setEnabled(clothSimulationEnabled);
    }
  }, [clothSimulationEnabled]);

  useEffect(() => {
    if (fabricProfileId && motionCoreRef.current) {
      motionCoreRef.current.setFabric(customGarmentCategory || 'top', fabricProfileId);
    }
  }, [fabricProfileId, customGarmentCategory]);

  useEffect(() => {
    if (clothQualityMode) {
      clothSimRef.current?.setQualityMode(clothQualityMode);
    }
  }, [clothQualityMode]);

  useImperativeHandle(ref, () => ({
    zoomIn: () => handleZoom(true),
    zoomOut: () => handleZoom(false),
    resetCamera: handleResetCamera,
    toggleWireframe: () => setWireframe(v => !v),
    toggleViewMode,
    playReaction: (reactionName: string) => {
      if (motionCoreRef.current) {
        return motionCoreRef.current.transitionTo('CUSTOM', { customClipName: reactionName }).accepted;
      }
      return mannequinEngineRef.current ? mannequinEngineRef.current.playReaction(reactionName, 0.35) : false;
    },
    setPose: (pose: FashionPosePreset) => {
      mannequinEngineRef.current?.setPose(pose);
    },
    onGarmentEquipped: (category: string) => {
      mannequinEngineRef.current?.onGarmentEquipped(category);
    },
    viewFront: () => inspectAngle(0),
    viewSide: () => inspectAngle(Math.PI / 2),
    viewBack: () => inspectAngle(Math.PI),
    setExpression: (expr: string) => {
      faceExpressionController.setExpression(expr as any);
    },
    focusHead,
    focusTorso,
    focusFullBody,
    focusFeet,
    syncOutfit: (params: HumanParams) => {
      if (currentModelRef.current && mannequinEngineRef.current) {
        mannequinEngineRef.current.syncFromHumanParams(params, currentModelRef.current);
      }
    },
    setClothQualityMode: (mode: SimulationQualityMode) => {
      clothSimRef.current?.setQualityMode(mode);
    },
    setClothFabricProfile: (profile: FabricProfileId) => {
      clothSimRef.current?.setFabricProfile('custom_ai_garment', profile);
    },
    resetClothSimulation: () => {
      clothSimRef.current?.resetSimulation();
    },
    getClothDiagnostics: () => {
      return clothSimRef.current?.getDiagnostics().getMetrics() ?? null;
    },
    playPerformanceIntent: (intent: any, duration: number) => {
      avatarPerformanceController.playIntent(intent, duration);
    },
    setPerformanceState: (state: 'idle' | 'listening' | 'thinking' | 'speaking') => {
      avatarPerformanceController.setState(state);
    },
    interruptPerformance: () => {
      avatarPerformanceController.interrupt();
    },
    getCustomGarmentStats: () => {
      if (!customGarmentRef.current) return null;
      let triangles = 0;
      customGarmentRef.current.traverse((o) => {
        if ((o as THREE.Mesh).isMesh) {
          const g = (o as THREE.Mesh).geometry;
          triangles += g.index ? Math.floor(g.index.count / 3) : Math.floor((g.getAttribute('position')?.count || 0) / 3);
        }
      });
      return { fitted: Boolean(garmentFit?.fitted), triangles };
    },
    setCustomGarmentAppearance: (opts) => {
      if (!customGarmentRef.current) return false;
      customGarmentRef.current.traverse((o) => {
        if ((o as THREE.Mesh).isMesh) {
          const mats = Array.isArray((o as THREE.Mesh).material) ? (o as THREE.Mesh).material : [(o as THREE.Mesh).material];
          (mats as THREE.MeshStandardMaterial[]).forEach((m) => {
            if (opts.color) m.color?.set(opts.color);
            if (opts.roughness !== undefined && 'roughness' in m) m.roughness = opts.roughness;
            if (opts.metalness !== undefined && 'metalness' in m) m.metalness = opts.metalness;
            if (opts.wireframe !== undefined) m.wireframe = opts.wireframe;
            m.needsUpdate = true;
          });
        }
      });
      return true;
    },
    setMotionState: (state: MotionState, customClipName?: string) => {
      if (!motionCoreRef.current) return false;
      return motionCoreRef.current.transitionTo(state, { customClipName }).accepted;
    },
    getMotionState: () => {
      return motionCoreRef.current?.stateManager.getState() ?? 'IDLE';
    },
    pauseMotion: () => {
      motionCoreRef.current?.pause();
    },
    resumeMotion: () => {
      motionCoreRef.current?.resume();
    },
    resetMotionPose: () => {
      motionCoreRef.current?.stateManager.reset();
      motionCoreRef.current?.resetAll();
      motionCoreRef.current?.transitionTo('IDLE');
    },
    getMotionTelemetry: () => {
      return motionCoreRef.current?.getTelemetry() ?? null;
    },
  }));

  return (
    <div className="ara-viewer-container" ref={containerRef}>
      <canvas ref={canvasRef} className="ara-canvas" />

      {/* 3D Wireframe Avatar Skeleton Loader */}
      {loading && (
        <AvatarSkeletonLoader
          loadingLabel={loadingLabel}
          theme="light"
          title="Yorvyn 3D Studio"
        />
      )}

      {/* Active Custom Garment Pill (Phase 8 Provenance) */}
      {customGarmentGlbUrl && garmentFit?.url === customGarmentGlbUrl && !loading && (
        <div style={{
          position: 'absolute',
          bottom: '1rem',
          left: '1rem',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(8px)',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          borderRadius: '20px',
          padding: '0.35rem 0.75rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.75rem',
          color: '#f8fafc',
          zIndex: 10,
          pointerEvents: 'none'
        }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#34d399' }} />
          <span role="status">{garmentFit.fitted
            ? `Fitted custom 3D ${customGarmentCategory || 'garment'}`
            : 'Could not fit this garment to the avatar.'}</span>
        </div>
      )}

      {/* Error Overlay */}
      {(error || internalError) && !loading && (
        <div className="viewer-error-overlay">
          <p className="error-title">Avatar Engine Offline</p>
          <p className="error-desc">{error || internalError}</p>
          {onRetry && (
            <button className="viewer-retry-btn" onClick={() => {
              setInternalError(null);
              onRetry();
            }}>
              Retry Initialization
            </button>
          )}
        </div>
      )}
    </div>
  );
});

AvatarStudioViewer.displayName = 'AvatarStudioViewer';

// Backward-compatible aliases
export const AraAvatarViewer = AvatarStudioViewer;
export type AraAvatarViewerHandle = AvatarStudioViewerHandle;
export type AraAvatarViewerProps = AvatarStudioViewerProps;

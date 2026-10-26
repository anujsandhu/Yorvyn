import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import toast from 'react-hot-toast';
import { Character } from '../engine/ara/core/human';
import { AssetLibrary } from '../engine/ara/core/assets';
import { araEngine } from '../engine/ara/AraService';
import { araAnim } from '../engine/ara/avatarAnimationController';
import { calculateCameraFraming } from '@yorvyn/three-renderer/index.ts';
import './AvatarStudioViewer.css';

export interface AvatarStudioViewerHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  resetCamera: () => void;
  toggleWireframe: () => void;
  toggleViewMode: () => void;
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
}

export const AvatarStudioViewer = forwardRef<AvatarStudioViewerHandle, AvatarStudioViewerProps>(({
  character,
  lib,
  loading = false,
  loadingLabel = 'Building 3D Character...',
  error = null,
  onRetry,
  showSunglasses = true,
  viewMode: controlledViewMode,
  onViewModeChange,
  activeAnimation,
  onAnimationTriggered,
  customGarmentGlbUrl = null,
  customGarmentCategory = null
}, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Three.js instances
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const currentModelRef = useRef<THREE.Object3D | null>(null);
  const sunglassesMeshRef = useRef<THREE.Group | null>(null);
  const customGarmentRef = useRef<THREE.Group | null>(null);
  const textureCacheRef = useRef<Map<string, THREE.Texture>>(new Map());
  const textureLoaderRef = useRef<THREE.TextureLoader>(new THREE.TextureLoader());
  const isFirstLoadRef = useRef(true);

  // View state
  const [wireframe, setWireframe] = useState(false);
  const [internalViewMode, setInternalViewMode] = useState<'full' | 'portrait'>('full');
  const viewMode = controlledViewMode ?? internalViewMode;

  // Initialize Three.js Scene once
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 700;

    // 1. Renderer
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
      powerPreference: 'high-performance'
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    rendererRef.current = renderer;

    // 2. Scene
    const scene = new THREE.Scene();
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

    const h = character?.height || 1.78;
    const isPortrait = (controlledViewMode ?? 'full') === 'portrait';
    const initFraming = calculateCameraFraming(isPortrait ? 'portrait' : 'full', h);
    const camera = new THREE.PerspectiveCamera(initFraming.fov, width / height, 0.05, 50);

    camera.position.set(initFraming.position[0], initFraming.position[1], initFraming.position[2]);
    cameraRef.current = camera;

    // 4. Orbit Controls (natural orbit range without restrictive limits)
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2.02; // keeps camera above floor plane
    controls.minPolarAngle = Math.PI / 9;    // ~20 degrees, allows comfortable high-angle view
    controls.minDistance = 0.90;            // zoom in to inspect details
    controls.maxDistance = 6.00;            // generous zoom out for full perspective
    controls.target.set(initFraming.target[0], initFraming.target[1], initFraming.target[2]);
    controlsRef.current = controls;

    // 5. Cloud Ambiance & Studio Three-Point Lighting Setup
    // Soft sky-blue & cloud-white ambient hemisphere light
    const hemiLight = new THREE.HemisphereLight(0xdcf8fe, 0xffffff, 0.9);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight('#ffffff', 2.0);
    keyLight.position.set(2.2, 3.2, 2.8);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.bias = -0.0005;
    keyLight.shadow.normalBias = 0.02;
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 10;
    keyLight.shadow.camera.left = -1.5;
    keyLight.shadow.camera.right = 1.5;
    keyLight.shadow.camera.top = 2.2;
    keyLight.shadow.camera.bottom = -0.2;
    scene.add(keyLight);

    // Ethereal Sky-Blue Rim / Backlight for cloud silhouette glow
    const rimLight = new THREE.DirectionalLight('#7dd3fc', 1.8);
    rimLight.position.set(-1.8, 2.6, -2.5);
    scene.add(rimLight);

    const rimLight2 = new THREE.DirectionalLight('#bae6fd', 1.2);
    rimLight2.position.set(1.8, 2.2, -2.2);
    scene.add(rimLight2);

    // Soft Warm Fill Light
    const fillLight = new THREE.DirectionalLight('#ffffff', 0.85);
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

    // Render loop with AnimationMixer clock update
    let animId: number;
    const clock = new THREE.Clock();
    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      araAnim.update(delta);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      resizeObserver.disconnect();
      renderer.dispose();
      araAnim.dispose();
    };
  }, []);

  // Texture loader helper
  const loadTexture = useCallback((fileName: string, isColor: boolean): THREE.Texture => {
    const key = `${fileName}_${isColor}`;
    let tex = textureCacheRef.current.get(key);
    if (!tex && lib) {
      const url = lib.textureUrl(fileName);
      tex = textureLoaderRef.current.load(url);
      tex.colorSpace = isColor ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      tex.anisotropy = 8;
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      textureCacheRef.current.set(key, tex);
    }
    return tex!;
  }, [lib]);

  // Build Sunglasses accessory group
  const createSunglassesMesh = useCallback((characterHeight: number) => {
    const glasses = new THREE.Group();
    const hScale = characterHeight / 1.70;

    const frameMat = new THREE.MeshStandardMaterial({
      color: 0x050505,
      metalness: 0.85,
      roughness: 0.2,
      wireframe
    });

    const lensMat = new THREE.MeshPhysicalMaterial({
      color: 0x0a0a0a,
      roughness: 0.1,
      metalness: 0.1,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1,
      transmission: 0.35,
      thickness: 0.015
    });

    // Left and right dark rectangular lenses
    const lensGeo = new THREE.BoxGeometry(0.044 * hScale, 0.026 * hScale, 0.005 * hScale);
    const leftLens = new THREE.Mesh(lensGeo, lensMat);
    leftLens.position.set(-0.032 * hScale, 0, 0);
    const rightLens = new THREE.Mesh(lensGeo, lensMat);
    rightLens.position.set(0.032 * hScale, 0, 0);

    // Nose bridge
    const bridgeGeo = new THREE.BoxGeometry(0.022 * hScale, 0.004 * hScale, 0.005 * hScale);
    const bridge = new THREE.Mesh(bridgeGeo, frameMat);
    bridge.position.set(0, 0.006 * hScale, 0);

    // Left and right temple arms
    const armGeo = new THREE.BoxGeometry(0.003 * hScale, 0.003 * hScale, 0.11 * hScale);
    const leftArm = new THREE.Mesh(armGeo, frameMat);
    leftArm.position.set(-0.056 * hScale, 0.005 * hScale, -0.055 * hScale);
    const rightArm = new THREE.Mesh(armGeo, frameMat);
    rightArm.position.set(0.056 * hScale, 0.005 * hScale, -0.055 * hScale);

    glasses.add(leftLens);
    glasses.add(rightLens);
    glasses.add(bridge);
    glasses.add(leftArm);
    glasses.add(rightArm);
    glasses.castShadow = true;

    return glasses;
  }, [wireframe]);

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

        // 2. Parse using Three.js GLTFLoader
        const loader = new GLTFLoader();
        const gltf = await loader.parseAsync(glbBytes.buffer as ArrayBuffer, '');
        if (isCancelled) return;

        // 3. Remove previous character model from scene
        if (currentModelRef.current) {
          scene.remove(currentModelRef.current);
          currentModelRef.current.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const m = child as THREE.Mesh;
              m.geometry?.dispose();
              if (Array.isArray(m.material)) {
                m.material.forEach(mat => mat.dispose());
              } else {
                m.material?.dispose();
              }
            }
          });
          currentModelRef.current = null;
        }

        const modelRoot = gltf.scene;

        // 4. Traverse meshes and attach shadow/textures with Cloud white & skyblue aesthetic
        modelRoot.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const m = child as THREE.Mesh;
            m.castShadow = true;
            m.receiveShadow = true;
            m.frustumCulled = false; // Prevent clipping during full turns or gestural poses

            const mats = Array.isArray(m.material) ? m.material : [m.material];
            mats.forEach((mat) => {
              const stdMat = mat as THREE.MeshStandardMaterial;
              const matName = (stdMat.name || m.name || '').toLowerCase();
              
              // Find matching material from Ara character definition by name
              const origMat = character.mesh.materials.find(
                x => x.name && matName.includes(x.name.toLowerCase())
              );

              stdMat.wireframe = wireframe;

              // Distinguish body parts and garments
              const isSkin = matName.includes('skin') || matName.includes('body') || matName.includes('head') || matName.includes('face') || matName.includes('arm') || matName.includes('hand') || matName.includes('leg');
              const isHair = matName.includes('hair') || matName.includes('eyebrow') || matName.includes('lash') || matName.includes('beard');
              const isEyes = matName.includes('eye');
              const isShoes = matName.includes('shoe') || matName.includes('footwear');
              const isBottom = matName.includes('bottom') || matName.includes('pant') || matName.includes('jean') || matName.includes('trouser');

              if (origMat) {
                if (origMat.map) stdMat.map = loadTexture(origMat.map, true);
                if (origMat.normalMap) stdMat.normalMap = loadTexture(origMat.normalMap, false);
                stdMat.roughness = origMat.roughness ?? 0.65;
                stdMat.metalness = origMat.metalness ?? 0.05;

                if (origMat.doubleSided) {
                  stdMat.side = THREE.DoubleSide;
                  stdMat.shadowSide = THREE.FrontSide;
                }
                if (origMat.alpha === 'mask') {
                  stdMat.alphaTest = 0.5;
                  stdMat.alphaToCoverage = true;
                } else if (origMat.alpha === 'blend') {
                  stdMat.transparent = true;
                  stdMat.opacity = origMat.opacity ?? 1;
                  stdMat.depthWrite = false;
                  if (origMat.map) stdMat.alphaTest = 0.01;
                }
              }

              // Realistic Cloud Styling: Crisp white and skyblue
              if (isSkin) {
                // Natural realistic porcelain / warm skin (never orange!)
                stdMat.color = new THREE.Color('#ffffff');
                stdMat.roughness = 0.60;
                stdMat.metalness = 0.02;
              } else if (isHair) {
                // Sleek obsidian / charcoal hair
                stdMat.color = new THREE.Color('#1e293b');
                stdMat.roughness = 0.45;
                stdMat.metalness = 0.06;
              } else if (isEyes) {
                // Vibrant azure / skyblue eyes
                stdMat.color = new THREE.Color('#0284c7');
                stdMat.roughness = 0.15;
                stdMat.metalness = 0.08;
              } else if (isBottom) {
                // Serene tailored sky-blue trousers
                stdMat.color = new THREE.Color('#7dd3fc');
                stdMat.roughness = 0.65;
                stdMat.metalness = 0.04;
              } else if (isShoes) {
                // Cloud white luxury sneakers
                stdMat.color = new THREE.Color('#ffffff');
                stdMat.roughness = 0.35;
                stdMat.metalness = 0.06;
              } else {
                // Cloud pure white top / blazer / blouse
                stdMat.color = new THREE.Color('#f8fafc');
                stdMat.roughness = 0.55;
                stdMat.metalness = 0.03;
              }

              stdMat.needsUpdate = true;
            });
          }
        });

        scene.add(modelRoot);
        currentModelRef.current = modelRoot;

        // 5. Initialize Animation Controller with real AnimationClips from the exported character
        console.log('[AraAvatarViewer] Real animation clips detected:', gltf.animations.map(a => a.name));
        araAnim.init(modelRoot, gltf.animations);

        // 6. Animation sequencing:
        // "Play Wave once when the user first opens the fashion studio, then smoothly return to Idle."
        // "Keep Idle playing while the user browses the wardrobe."
        if (isFirstLoadRef.current) {
          isFirstLoadRef.current = false;
          araAnim.playOneShot('Wave', 'Idle', 0.4);
        } else {
          araAnim.play('Idle', { loop: true, crossfadeDuration: 0.35 });
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
            glasses.position.set(0, 0.075 * hScale, 0.115 * hScale);
            glasses.rotation.set(0, 0, 0);
          } else {
            const hScale = character.height / 1.70;
            glasses.position.set(0, character.height * 0.925, 0.12 * hScale);
            modelRoot.add(glasses);
          }
          sunglassesMeshRef.current = glasses;
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
      if (m.uvs) geo.setAttribute('uv', new THREE.BufferAttribute(m.uvs, 2));

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
  }, [character, lib, loadTexture, showSunglasses, wireframe, createSunglassesMesh]);

  // Handle activeAnimation prop change
  useEffect(() => {
    if (activeAnimation && araAnim.hasClip(activeAnimation)) {
      if (activeAnimation.toLowerCase() === 'idle') {
        araAnim.returnToIdle(0.35);
      } else {
        araAnim.playOneShot(activeAnimation, 'Idle', 0.35);
      }
      onAnimationTriggered?.(activeAnimation);
    }
  }, [activeAnimation, onAnimationTriggered]);

  // ── 3D Custom AI Garment Fitting & Occlusion Masking ──
  useEffect(() => {
    const scene = sceneRef.current;
    const modelRoot = currentModelRef.current;
    if (!scene) return;

    // 1. Cleanup previous custom garment
    if (customGarmentRef.current) {
      if (customGarmentRef.current.parent) {
        customGarmentRef.current.parent.remove(customGarmentRef.current);
      } else {
        scene.remove(customGarmentRef.current);
      }
      customGarmentRef.current.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const m = child as THREE.Mesh;
          m.geometry?.dispose();
          if (Array.isArray(m.material)) {
            m.material.forEach((mat) => mat.dispose());
          } else {
            m.material?.dispose();
          }
        }
      });
      customGarmentRef.current = null;
    }

    // 2. Body Occlusion Masking: hide default avatar clothes that would clip with the custom piece
    if (modelRoot) {
      modelRoot.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const m = child as THREE.Mesh;
          const mat = Array.isArray(m.material) ? m.material[0] : m.material;
          const matName = (mat?.name || m.name || '').toLowerCase();
          const isSkin = matName.includes('skin') || matName.includes('body') || matName.includes('head') || matName.includes('face') || matName.includes('arm') || matName.includes('hand') || matName.includes('leg');
          const isHair = matName.includes('hair') || matName.includes('eyebrow') || matName.includes('lash') || matName.includes('beard');
          const isEyes = matName.includes('eye');
          const isShoes = matName.includes('shoe') || matName.includes('footwear');
          const isBottom = matName.includes('bottom') || matName.includes('pant') || matName.includes('jean') || matName.includes('trouser');
          const isTop = !isSkin && !isHair && !isEyes && !isShoes && !isBottom;

          if (customGarmentGlbUrl) {
            const cat = (customGarmentCategory || 'top').toLowerCase();
            if ((cat === 'top' || cat === 'outerwear' || cat === 'jacket' || cat === 'dress') && isTop) {
              m.visible = false;
            } else if ((cat === 'bottom' || cat === 'pants' || cat === 'trousers' || cat === 'skirt') && isBottom) {
              m.visible = false;
            }
          } else {
            m.visible = true;
          }
        }
      });
    }

    if (!customGarmentGlbUrl) return;

    let isCancelled = false;
    const loader = new GLTFLoader();
    loader.load(
      customGarmentGlbUrl,
      (gltf) => {
        if (isCancelled) return;
        const garmentGroup = gltf.scene;
        garmentGroup.name = 'custom_ai_garment';

        // Fit body-relative scale
        const hScale = (character?.height || 1.78) / 1.70;
        garmentGroup.scale.set(hScale, hScale, hScale);

        garmentGroup.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const m = child as THREE.Mesh;
            m.castShadow = true;
            m.receiveShadow = true;
            m.frustumCulled = false;
            if (m.material) {
              const mat = m.material as THREE.MeshStandardMaterial;
              mat.side = THREE.DoubleSide;
              mat.wireframe = wireframe;
              mat.needsUpdate = true;
            }
          }
        });

        // Attach to modelRoot (or scene if modelRoot is not yet ready)
        if (modelRoot) {
          modelRoot.add(garmentGroup);
        } else {
          scene.add(garmentGroup);
        }
        customGarmentRef.current = garmentGroup;

        // Celebrate wearing the new garment!
        araAnim.playOneShot('Turn', 'Idle', 0.4);
      },
      undefined,
      (err) => {
        console.error('[AraAvatarViewer] Failed to load custom garment GLB:', err);
      }
    );

    return () => {
      isCancelled = true;
    };
  }, [customGarmentGlbUrl, customGarmentCategory, character?.height, wireframe, character]);

  // Update Camera based on viewMode and character height
  useEffect(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = character?.height || 1.78;
    const framing = calculateCameraFraming(viewMode, h);
    cameraRef.current.position.set(framing.position[0], framing.position[1], framing.position[2]);
    controlsRef.current.target.set(framing.target[0], framing.target[1], framing.target[2]);
    controlsRef.current.update();
  }, [viewMode, character?.height]);

  // Reset view to default
  const handleResetCamera = () => {
    if (!cameraRef.current || !controlsRef.current) return;
    const h = character?.height || 1.78;
    const framing = calculateCameraFraming(viewMode, h);
    cameraRef.current.position.set(framing.position[0], framing.position[1], framing.position[2]);
    controlsRef.current.target.set(framing.target[0], framing.target[1], framing.target[2]);
    controlsRef.current.update();
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
    const h = character?.height || 1.78;

    // Current horizontal azimuth angle (preserves whatever angle the user rotated to)
    const currentAngle = Math.atan2(camera.position.x, camera.position.z);

    // Current distance to current target
    const currentDist = camera.position.distanceTo(controls.target);

    const MIN_DISTANCE = 0.95; // Zoomed-in close-up limit (face and chest)
    const MAX_DISTANCE = 5.80; // Zoomed-out wide limit

    let nextDist: number;
    if (inwards) {
      if (currentDist <= MIN_DISTANCE + 0.05) {
        toast('Maximum zoom reached', { icon: '🔍', duration: 800 });
        return;
      }
      nextDist = Math.max(currentDist * 0.82, MIN_DISTANCE);
    } else {
      if (currentDist >= MAX_DISTANCE - 0.05) {
        toast('Minimum zoom reached', { icon: '🔎', duration: 800 });
        return;
      }
      nextDist = Math.min(currentDist * 1.20, MAX_DISTANCE);
    }

    // Blend target and camera height cleanly between Half Body / Portrait (inwards) and Full Body (outwards)
    // t = 0 when fully zoomed in, t = 1 when fully zoomed out
    const t = THREE.MathUtils.clamp((nextDist - MIN_DISTANCE) / (MAX_DISTANCE - MIN_DISTANCE), 0, 1);
    
    // In Full Body (t = 1): targetY = h * 0.48, cameraY = h * 0.50
    // In Half Body (t = 0): targetY = h * 0.65, cameraY = h * 0.67
    const targetY = THREE.MathUtils.lerp(h * 0.65, h * 0.48, t);
    const cameraY = THREE.MathUtils.lerp(h * 0.67, h * 0.50, t);

    controls.target.set(0, targetY, 0);
    camera.position.set(
      Math.sin(currentAngle) * nextDist,
      cameraY,
      Math.cos(currentAngle) * nextDist
    );
    controls.update();
  };

  useImperativeHandle(ref, () => ({
    zoomIn: () => handleZoom(true),
    zoomOut: () => handleZoom(false),
    resetCamera: handleResetCamera,
    toggleWireframe: () => setWireframe(v => !v),
    toggleViewMode
  }));

  return (
    <div className="ara-viewer-container" ref={containerRef}>
      <canvas ref={canvasRef} className="ara-canvas" />

      {/* Loading Overlay */}
      {loading && (
        <div className="viewer-loading-overlay">
          <div className="viewer-spinner" />
          <p className="loading-title">Yorvyn 3D Studio</p>
          <p className="loading-desc">{loadingLabel}</p>
        </div>
      )}

      {/* Error Overlay */}
      {error && !loading && (
        <div className="viewer-error-overlay">
          <p className="error-title">Avatar Engine Offline</p>
          <p className="error-desc">{error}</p>
          {onRetry && (
            <button className="viewer-retry-btn" onClick={onRetry}>
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

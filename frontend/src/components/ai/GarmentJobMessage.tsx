import { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { aiSessionService, type GarmentArtifact } from '../../services/aiSessionService';
import { fashionApi } from '../../services/fashionApi';
import { GarmentDesignWorkspace } from '../design/GarmentDesignWorkspace';

function Model({url}: {url: string}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!canvas.current) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({canvas: canvas.current, antialias: true, alpha: true}); }
    catch { setError('3D preview requires WebGL.'); return; }
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.001, 100);
    const controls = new OrbitControls(camera, canvas.current);
    const draw = () => renderer.render(scene, camera);
    controls.addEventListener('change', draw);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 2));
    const light = new THREE.DirectionalLight(0xffffff, 2);
    light.position.set(2,3,4);
    scene.add(light);
    let alive = true;
    const dispose = (root: THREE.Object3D) => root.traverse(obj => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        for (const material of [obj.material].flat()) {
          for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose();
          material.dispose();
        }
      }
    });
    new GLTFLoader().load(url, ({scene: model}) => {
      if (!alive) { dispose(model); return; }
      scene.add(model);
      const box = new THREE.Box3().setFromObject(model);
      box.getCenter(controls.target);
      camera.position.copy(controls.target);
      camera.position.z += box.getSize(new THREE.Vector3()).length() * 1.8;
      controls.update();
      draw();
      if (canvas.current) canvas.current.dataset.garmentLoaded = "true";
    }, undefined, () => { if (alive) setError('Could not open the exported model.'); });
    const resize = new ResizeObserver(([entry]) => {
      const {width, height} = entry.contentRect;
      if (width && height) { renderer.setSize(width,height,false); camera.aspect = width/height; camera.updateProjectionMatrix(); draw(); }
    });
    resize.observe(canvas.current);
    return () => { alive=false; resize.disconnect(); controls.dispose(); dispose(scene); renderer.dispose(); };
  }, [url]);
  return error ? <p>{error}</p> : <canvas ref={canvas} aria-label="Rotate garment preview" style={{width:'100%',height:230}} />;
}

export function GarmentJobMessage({session, garment, wear}: {
  session: string; garment: GarmentArtifact; wear: (blob: Blob) => void
}) {
  const job = garment.job_id;
  const [state,setState] = useState('');
  const [stage,setStage] = useState('');
  const wearBlob = useRef<Blob | null>(null);
  const [url,setUrl] = useState('');
  const [attempt,refresh] = useState(0);
  const [error,setError] = useState('');
  const [studioOpen, setStudioOpen] = useState(false);
  useEffect(() => {
    if (!job) return;
    let active = true, candidate = '';
    let timer: ReturnType<typeof setTimeout>;
    setError(''); setUrl('');
    async function poll() {
      try {
        const data = await fashionApi.getGarment3DJobStatus(job!);
        if (!active) return;
        setState(data.status); setStage(data.error || data.current_stage);
        if (data.status === 'completed') {
          const blob = await aiSessionService.candidateBlob(session,garment.turn_id);
          if (active) {wearBlob.current = blob; candidate = URL.createObjectURL(blob); setUrl(candidate);}
        } else if (!['cancelled','failed','timed_out'].includes(data.status)) timer = setTimeout(poll,2000);
      } catch (err: any) {
        const detail = err.response?.data;
        let message = err.message;
        if (detail instanceof Blob) { try { message = JSON.parse(await detail.text()).detail || message; } catch { /* non-JSON */ } }
        if (active) setError(message);
      }
    }
    poll();
    return () => {active=false; wearBlob.current=null; clearTimeout(timer); if (candidate) URL.revokeObjectURL(candidate);};
  },[session,job,garment.turn_id,attempt]);
  async function control(retry: boolean) {
    if (!job) return;
    try {
      if (retry) await fashionApi.retryGarmentGenJob(job); else await fashionApi.cancelGarment3DJob(job);
      refresh(n=>n+1);
    } catch(err: any) {setError(err.response?.data?.detail || err.message);}
  }
  const safeParts = garment.recognition?.component_handoff?.safe_components || [];
  const clarifyNote = garment.recognition?.component_handoff?.clarification_prompts?.[0];
  if (!job) {
    if (!safeParts.length && !clarifyNote) return null;
    return <div aria-live="polite">
      {safeParts.length > 0 && <p>Visible garment parts: {safeParts.map(p => p.replace(/_/g, ' ')).join(', ')}.</p>}
      {clarifyNote && <p>{clarifyNote}</p>}
    </div>;
  }
  return <div aria-live="polite"><p>{stage || 'Checking reconstruction progress…'}</p>
    {safeParts.length > 0 && <p>Visible garment parts: {safeParts.map(p => p.replace(/_/g, ' ')).join(', ')}.</p>}
    {error && <p role="alert">{error} <button onClick={()=>refresh(n=>n+1)}>Check again</button></p>}
    {state && !['completed','cancelled','failed','timed_out'].includes(state) && <button onClick={()=>control(false)}>Cancel reconstruction</button>}
    {['failed','timed_out'].includes(state) && <button onClick={()=>control(true)}>Retry reconstruction</button>}
    {url && <><Model url={url}/><p>Mesh inspection passed. Photo fidelity is unmeasured.</p>
      {garment.previous_mesh_report && garment.mesh_report &&
        <details><summary>Compare dimensions</summary>
          <table><thead><tr><th>Dimension</th><th>Previous</th><th>Current</th></tr></thead>
            <tbody>{['Width', 'Height', 'Depth'].map((axis, index) =>
              <tr key={axis}><th>{axis}</th>{[garment.previous_mesh_report!, garment.mesh_report!].map((report, i) =>
                <td key={i}>{(report.extents[index] * 100).toFixed(1)} cm</td>)}</tr>)}</tbody></table>
        </details>}
      <a href={url} download="garment.glb">Download GLB</a> <button onClick={()=>wearBlob.current && wear(wearBlob.current)}>Try on</button> <button type="button" onClick={() => setStudioOpen(true)}>Open Design Studio</button></>}
    {studioOpen && url && (
      <GarmentDesignWorkspace
        garmentId={garment.job_id || garment.turn_id}
        candidateId={garment.turn_id}
        glbUrl={url}
        category={garment.category || 'jacket'}
        subcategory={garment.recognition?.garment?.subcategory || ''}
        initialDesignCommand={(garment as any).design_command}
        onApplyToAvatar={(editedBlob) => {
          wearBlob.current = editedBlob;
          wear(editedBlob);
          setStudioOpen(false);
        }}
        onClose={() => setStudioOpen(false)}
      />
    )}
  </div>;
}


export function GarmentPhotoStrip({files,remove,disabled}: {files:File[];remove:(index:number)=>void;disabled:boolean}) {
  const [photos,setPhotos] = useState<string[]>([]);
  useEffect(()=>{
    const urls = files.map(file=>URL.createObjectURL(file));
    setPhotos(urls);
    return ()=>urls.forEach(url=>URL.revokeObjectURL(url));
  },[files]);
  if (!photos.length) return null;
  return <div style={{display:'flex',maxWidth:'30%',overflowX:'auto',gap:3}}>
    {photos.map((url,i)=><button key={url} type="button" aria-label={`Remove photo ${i+1}`} disabled={disabled} onClick={()=>remove(i)}>
      <img src={url} width="30" height="36" alt={files[i]?.name || 'Garment photo'} style={{objectFit:'cover'}}/>
    </button>)}
  </div>;
}

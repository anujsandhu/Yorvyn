/**
 * Phase 16.3 Interactive 2D Pattern CAD Editor
 * High-DPI Canvas2D pattern designer separated cleanly from independent PatternPiece2D data.
 * Supports panel selection, vertex control-point dragging with polygon validation, grid snapping,
 * zoom & pan, seam allowances, seam highlights, darts, notches, grainlines, and layer visibility.
 */

import { useEffect, useRef, useState } from 'react';
import type {
  DesignPatternPiece,
  DesignStateEngine,
  GarmentDesignState,
  PatternLayerVisibility,
} from '../../engine/designStudio/DesignStateEngine';

interface Props {
  designEngine: DesignStateEngine;
  designState: GarmentDesignState;
}

const GRID_STEP_M = 0.01; // 1 cm snap grid when grid snapping is enabled

export function Pattern2DEditor({ designEngine, designState }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(320); // px per meter
  const [pan, setPan] = useState({ x: 80, y: 340 });
  const [snapToGrid, setSnapToGrid] = useState(true);
  const dragRef = useRef<
    | { kind: 'vertex'; pieceId: string; vertexIdx: number }
    | { kind: 'pan'; startX: number; startY: number; origPanX: number; origPanY: number }
    | null
  >(null);

  const pieces = Object.values(designState.patternPieces);
  const activePiece: DesignPatternPiece | undefined =
    (designState.selectedPieceId && designState.patternPieces[designState.selectedPieceId]) || pieces[0];

  const toCanvas = (pt: { x: number; y: number }) => ({
    cx: pan.x + pt.x * zoom,
    cy: pan.y - pt.y * zoom,
  });

  const toWorld = (cx: number, cy: number) => {
    let wx = (cx - pan.x) / zoom;
    let wy = (pan.y - cy) / zoom;
    if (snapToGrid) {
      wx = Math.round(wx / GRID_STEP_M) * GRID_STEP_M;
      wy = Math.round(wy / GRID_STEP_M) * GRID_STEP_M;
    }
    return { x: Number(wx.toFixed(4)), y: Number(wy.toFixed(4)) };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);

    // 1. Optional 5cm CAD Grid
    if (designState.patternLayers.grid) {
      const stepPx = 0.05 * zoom;
      ctx.strokeStyle = '#f1f5f9';
      ctx.lineWidth = 1;
      for (let x = ((pan.x % stepPx) + stepPx) % stepPx; x < w; x += stepPx) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = ((pan.y % stepPx) + stepPx) % stepPx; y < h; y += stepPx) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
    }

    if (!activePiece) return;

    const poly = activePiece.boundary_polygon;
    if (poly.length < 3) return;

    // 2. Seam allowance outline
    if (designState.patternLayers.seamAllowance) {
      const sa = activePiece.seam_allowance_m || 0.01;
      const cxMean = poly.reduce((s, p) => s + p.x, 0) / poly.length;
      const cyMean = poly.reduce((s, p) => s + p.y, 0) / poly.length;
      ctx.save();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      poly.forEach((p, idx) => {
        const dx = p.x - cxMean;
        const dy = p.y - cyMean;
        const dist = Math.hypot(dx, dy) || 1;
        const pt = toCanvas({ x: p.x + (dx / dist) * sa, y: p.y + (dy / dist) * sa });
        if (idx === 0) ctx.moveTo(pt.cx, pt.cy);
        else ctx.lineTo(pt.cx, pt.cy);
      });
      ctx.closePath();
      ctx.stroke();
      ctx.restore();
    }

    // 3. Cut line fill & stroke
    if (designState.patternLayers.cutLine) {
      ctx.fillStyle = activePiece.verification_state === 'OBSERVED' ? 'rgba(59,130,246,0.08)' : 'rgba(245,158,11,0.08)';
      ctx.strokeStyle = activePiece.verification_state === 'OBSERVED' ? '#1e3a8a' : '#b45309';
      ctx.lineWidth = 2;
      ctx.beginPath();
      poly.forEach((p, idx) => {
        const pt = toCanvas(p);
        if (idx === 0) ctx.moveTo(pt.cx, pt.cy);
        else ctx.lineTo(pt.cx, pt.cy);
      });
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }

    // 4. Seam edge markers
    if (designState.patternLayers.seams) {
      ctx.strokeStyle = '#0284c7';
      ctx.lineWidth = 2.5;
      activePiece.edges.forEach((edge) => {
        if (edge.role === 'SEWN' || edge.role === 'SLEEVE_ATTACHMENT') {
          ctx.beginPath();
          edge.vertices.forEach((p, idx) => {
            const pt = toCanvas(p);
            if (idx === 0) ctx.moveTo(pt.cx, pt.cy);
            else ctx.lineTo(pt.cx, pt.cy);
          });
          ctx.stroke();
        }
      });
    }

    // 5. Darts & Notches
    if (designState.patternLayers.dartsAndNotches) {
      ctx.strokeStyle = '#dc2626';
      ctx.lineWidth = 1.6;
      activePiece.darts.forEach((d) => {
        const bl = toCanvas(d.base_left);
        const ap = toCanvas(d.apex);
        const br = toCanvas(d.base_right);
        ctx.beginPath();
        ctx.moveTo(bl.cx, bl.cy);
        ctx.lineTo(ap.cx, ap.cy);
        ctx.lineTo(br.cx, br.cy);
        ctx.stroke();
      });
    }

    // 6. Grainline & Measurements
    if (designState.patternLayers.grainlineAndMeasurements && activePiece.grainline) {
      const g1 = toCanvas(activePiece.grainline.start);
      const g2 = toCanvas(activePiece.grainline.end);
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(g1.cx, g1.cy);
      ctx.lineTo(g2.cx, g2.cy);
      ctx.stroke();
      ctx.fillStyle = '#0f172a';
      ctx.font = '11px monospace';
      ctx.fillText(
        `${activePiece.piece_id} | ${(activePiece.area_m2 * 10000).toFixed(0)} cm2 | perim ${(activePiece.perimeter_m * 100).toFixed(1)} cm`,
        12,
        20
      );
    }

    // 7. Interactive draggable control points
    poly.forEach((p, idx) => {
      const pt = toCanvas(p);
      ctx.fillStyle = idx === 0 ? '#1d4ed8' : '#0f172a';
      ctx.beginPath();
      ctx.arc(pt.cx, pt.cy, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }, [activePiece, zoom, pan, designState.patternLayers, designState.patternVersion]);

  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !activePiece) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const cx = ((e.clientX - rect.left) / rect.width) * canvasRef.current.width;
    const cy = ((e.clientY - rect.top) / rect.height) * canvasRef.current.height;

    const hitIdx = activePiece.boundary_polygon.findIndex((p) => {
      const pt = toCanvas(p);
      return Math.hypot(pt.cx - cx, pt.cy - cy) <= 10;
    });
    if (hitIdx >= 0) {
      dragRef.current = { kind: 'vertex', pieceId: activePiece.piece_id, vertexIdx: hitIdx };
    } else {
      dragRef.current = { kind: 'pan', startX: e.clientX, startY: e.clientY, origPanX: pan.x, origPanY: pan.y };
    }
    canvasRef.current.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!dragRef.current || !canvasRef.current) return;
    if (dragRef.current.kind === 'pan') {
      setPan({
        x: dragRef.current.origPanX + (e.clientX - dragRef.current.startX),
        y: dragRef.current.origPanY + (e.clientY - dragRef.current.startY),
      });
      return;
    }
    const rect = canvasRef.current.getBoundingClientRect();
    const cx = ((e.clientX - rect.left) / rect.width) * canvasRef.current.width;
    const cy = ((e.clientY - rect.top) / rect.height) * canvasRef.current.height;
    const worldPt = toWorld(cx, cy);
    designEngine.applyPatternVertexEdit(dragRef.current.pieceId, dragRef.current.vertexIdx, worldPt);
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    dragRef.current = null;
    canvasRef.current?.releasePointerCapture?.(e.pointerId);
  };

  const toggleLayer = (key: keyof PatternLayerVisibility) => {
    designEngine.setViewState({
      patternLayers: { [key]: !designState.patternLayers[key] },
    });
  };

  return (
    <div data-testid="pattern-2d-editor" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Piece Tabs + Zoom & Snap Controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        {pieces.map((p) => (
          <button
            key={p.piece_id}
            type="button"
            onClick={() => designEngine.setViewState({ selectedPieceId: p.piece_id })}
            style={{
              padding: '3px 8px',
              fontSize: 11,
              borderRadius: 6,
              border: '1px solid #cbd5e1',
              background: activePiece?.piece_id === p.piece_id ? '#0f172a' : '#f8fafc',
              color: activePiece?.piece_id === p.piece_id ? '#fff' : '#0f172a',
              cursor: 'pointer',
            }}
          >
            {p.name}
          </button>
        ))}
        <button type="button" onClick={() => setZoom((z) => Math.min(700, z + 40))} aria-label="Pattern zoom in">
          +
        </button>
        <button type="button" onClick={() => setZoom((z) => Math.max(140, z - 40))} aria-label="Pattern zoom out">
          -
        </button>
        <label style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
          <input type="checkbox" checked={snapToGrid} onChange={(e) => setSnapToGrid(e.target.checked)} />
          Snap 1cm
        </label>
      </div>

      {/* Layer Toggles */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, fontSize: 11 }}>
        {(
          [
            ['cutLine', 'Cut'],
            ['seamAllowance', 'Seam Allow.'],
            ['seams', 'Seams'],
            ['dartsAndNotches', 'Darts/Notches'],
            ['grainlineAndMeasurements', 'Grain/Dims'],
            ['grid', 'Grid'],
          ] as [keyof PatternLayerVisibility, string][]
        ).map(([k, label]) => (
          <label key={k} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <input type="checkbox" checked={designState.patternLayers[k]} onChange={() => toggleLayer(k)} />
            {label}
          </label>
        ))}
      </div>

      <canvas
        ref={canvasRef}
        width={480}
        height={380}
        data-testid="pattern-2d-canvas"
        aria-label="Interactive 2D Pattern CAD Canvas"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={{
          width: '100%',
          height: 360,
          borderRadius: 8,
          border: '1px solid #cbd5e1',
          cursor: 'crosshair',
          touchAction: 'none',
        }}
      />

      {/* Scoped panel ease nudge + correspondence badge */}
      {activePiece && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', fontSize: 12 }}>
          <span>
            Piece: <strong>{activePiece.verification_state}</strong>
            {designState.correspondence?.pieceMappings[activePiece.piece_id]?.meshRegionIds?.length ? (
              <> ({designState.correspondence.pieceMappings[activePiece.piece_id].meshRegionIds.join(', ')})</>
            ) : null}
          </span>
          <button
            type="button"
            onClick={() => designEngine.applyPanelEase(activePiece.piece_id, 0.03, true)}
          >
            +3 cm Panel Ease
          </button>
          {designState.patternValidationErrors.length > 0 && (
            <span role="alert" style={{ color: '#b91c1c' }}>
              {designState.patternValidationErrors[0]}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

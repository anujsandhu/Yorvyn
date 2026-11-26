/**
 * YORVYN Phase 17.5 — Lightweight Client-Side Live Camera Frame Analyzer.
 *
 * Runs throttled (~3 FPS) on downscaled HTMLCanvasElement frames locally in the browser
 * without running expensive neural inference on every video frame or streaming frames to server.
 * Computes genuine luminance, sharpness, center-vs-border foreground visibility, and framing checks,
 * returning one prioritized plain-English corrective instruction at a time.
 */

export interface LiveFrameQualityMetrics {
  sharpness: number;
  exposure: number;
  garmentVisibility: number;
  framing: number;
  backgroundContrast: number;
  usable: boolean;
  primaryIssue: string | null;
  instruction: string;
}

export function analyzeLivePreviewImageData(
  data: Uint8ClampedArray,
  width: number,
  height: number
): LiveFrameQualityMetrics {
  if (!data || width < 16 || height < 16 || data.length < width * height * 4) {
    return {
      sharpness: 0,
      exposure: 0,
      garmentVisibility: 0,
      framing: 0,
      backgroundContrast: 0,
      usable: false,
      primaryIssue: 'no_frame',
      instruction: 'Waiting for camera preview frame...',
    };
  }

  const totalPixels = width * height;
  const gray = new Float32Array(totalPixels);
  let sumLuma = 0;
  let darkCount = 0;
  let brightCount = 0;

  for (let i = 0; i < totalPixels; i++) {
    const p = i * 4;
    const y = 0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2];
    gray[i] = y;
    sumLuma += y;
    if (y < 28) darkCount++;
    if (y > 240) brightCount++;
  }

  const meanLuma = sumLuma / totalPixels;
  const underFrac = darkCount / totalPixels;
  const overFrac = brightCount / totalPixels;

  let expPenalty = 0;
  if (meanLuma < 55) expPenalty += (55 - meanLuma) / 55;
  else if (meanLuma > 215) expPenalty += (meanLuma - 215) / 40;
  if (underFrac > 0.45) expPenalty += 0.35;
  if (overFrac > 0.35) expPenalty += 0.35;
  const exposure = Math.max(0, Math.min(1, 1 - expPenalty));

  // Gradient / sharpness approximation (fast 4-neighbor difference)
  let gradSum = 0;
  let gradCount = 0;
  for (let y = 1; y < height - 1; y += 2) {
    for (let x = 1; x < width - 1; x += 2) {
      const idx = y * width + x;
      const g =
        Math.abs(gray[idx] - gray[idx - 1]) +
        Math.abs(gray[idx] - gray[idx + 1]) +
        Math.abs(gray[idx] - gray[idx - width]) +
        Math.abs(gray[idx] - gray[idx + width]);
      gradSum += g * 0.25;
      gradCount++;
    }
  }
  const meanGrad = gradCount > 0 ? gradSum / gradCount : 0;
  const sharpness = Math.max(0, Math.min(1, meanGrad / 14.0));

  // Border background median-like mean RGB vs foreground separation & edge clipping
  const borderMargin = Math.max(2, Math.floor(Math.min(width, height) / 14));
  let bR = 0, bG = 0, bB = 0, bN = 0;
  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      if (y < borderMargin || y >= height - borderMargin || x < borderMargin || x >= width - borderMargin) {
        const p = (y * width + x) * 4;
        bR += data[p];
        bG += data[p + 1];
        bB += data[p + 2];
        bN++;
      }
    }
  }
  const bgR = bN > 0 ? bR / bN : 128;
  const bgG = bN > 0 ? bG / bN : 128;
  const bgB = bN > 0 ? bB / bN : 128;

  let fgCount = 0;
  let fgDistSum = 0;
  let botTouch = 0, botTotal = 0;
  let topTouch = 0, topTotal = 0;
  const edgeBand = Math.max(2, Math.floor(height / 24));

  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      const p = (y * width + x) * 4;
      const dist = Math.hypot(data[p] - bgR, data[p + 1] - bgG, data[p + 2] - bgB);
      const isFg = dist > 28;
      if (isFg) {
        fgCount++;
        fgDistSum += dist;
      }
      if (y < edgeBand) {
        topTotal++;
        if (isFg) topTouch++;
      } else if (y >= height - edgeBand) {
        botTotal++;
        if (isFg) botTouch++;
      }
    }
  }

  const sampledTotal = Math.ceil(height / 2) * Math.ceil(width / 2);
  const fgRatio = sampledTotal > 0 ? fgCount / sampledTotal : 0;
  const botRatio = botTotal > 0 ? botTouch / botTotal : 0;
  const topRatio = topTotal > 0 ? topTouch / topTotal : 0;

  const garmentVisibility =
    fgRatio < 0.06
      ? (fgRatio / 0.06) * 0.4
      : fgRatio > 0.88
        ? Math.max(0.25, 1 - (fgRatio - 0.88) * 4)
        : Math.min(1, 0.55 + Math.min(fgRatio, 0.65) * 0.7);

  let framingPenalty = 0;
  if (botRatio > 0.36 || topRatio > 0.42) framingPenalty += 0.45;
  if (fgRatio < 0.08) framingPenalty += 0.4;
  const framing = Math.max(0, Math.min(1, 1 - framingPenalty));

  const meanFgDist = fgCount > 0 ? fgDistSum / fgCount : 0;
  const backgroundContrast = Math.max(0, Math.min(1, meanFgDist / 90));

  let primaryIssue: string | null = null;
  let instruction = 'Frame looks clear and steady. Tap Capture when ready.';

  if (exposure < 0.42) {
    primaryIssue = 'poor_lighting';
    instruction =
      meanLuma > 215 || overFrac > 0.35
        ? 'Reduce direct glare or bright light. Overexposed areas hide garment details.'
        : 'Increase the lighting or move closer to a well-lit area. Dark regions are hiding garment details.';
  } else if (sharpness < 0.22) {
    primaryIssue = 'blur_detected';
    instruction = 'Hold your camera steady and wait for focus before capturing.';
  } else if (botRatio > 0.36) {
    primaryIssue = 'bottom_cut_off';
    instruction = 'Move the camera slightly farther away. The bottom of your garment is outside the frame.';
  } else if (topRatio > 0.42) {
    primaryIssue = 'top_cut_off';
    instruction = 'Center the garment and step back slightly so the top fits inside the guide.';
  } else if (fgRatio < 0.06) {
    primaryIssue = 'garment_not_visible';
    instruction = 'Move closer to the garment or use a plain contrasting background.';
  }

  return {
    sharpness: Number(sharpness.toFixed(3)),
    exposure: Number(exposure.toFixed(3)),
    garmentVisibility: Number(garmentVisibility.toFixed(3)),
    framing: Number(framing.toFixed(3)),
    backgroundContrast: Number(backgroundContrast.toFixed(3)),
    usable: primaryIssue === null,
    primaryIssue,
    instruction,
  };
}

"""Fast in-canvas keeper bbox detection via getImageData."""

from __future__ import annotations

KEEPER_BBOX_JS = """
(canvas, args) => {
  const {
    goalLeft, goalTop, goalRight, goalBottom,
    scanTopFrac, scanBottomFrac, bboxWidth,
    canvasWidth, canvasHeight,
    hintX, searchHalfWidth,
  } = args;

  if (!canvas) return null;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;

  const w = canvas.width;
  const h = canvas.height;
  const sx = w / canvasWidth;
  const sy = h / canvasHeight;

  let gl = Math.floor(goalLeft * sx);
  let gr = Math.ceil(goalRight * sx);
  const gt = Math.floor(goalTop * sy);
  const gb = Math.ceil(goalBottom * sy);
  const band = gb - gt;
  const y0 = gt + Math.floor(band * scanTopFrac);
  const y1 = gt + Math.floor(band * scanBottomFrac);

  if (hintX != null) {
    const hx = Math.floor(hintX * sx);
    const half = Math.floor(searchHalfWidth * sx);
    gl = Math.max(gl, hx - half);
    gr = Math.min(gr, hx + half);
  }

  const regionW = gr - gl;
  const regionH = y1 - y0;
  if (regionW <= 8 || regionH <= 4) return null;

  const data = ctx.getImageData(gl, y0, regionW, regionH).data;
  const window = Math.max(8, Math.floor(bboxWidth * sx));

  function isKeeper(r, g, b) {
    if (g > r + 15 && g > b + 10 && g > 80) return false;
    const mx = Math.max(r, g, b);
    const mn = Math.min(r, g, b);
    if (mx - mn < 35) return false;
    return true;
  }

  const counts = new Array(regionW).fill(0);
  for (let y = 0; y < regionH; y += 2) {
    for (let x = 0; x < regionW; x++) {
      const i = (y * regionW + x) * 4;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      if (isKeeper(r, g, b)) counts[x]++;
    }
  }

  if (regionW <= window) return null;

  const margin = Math.max(4, Math.floor(40 * sx));
  const peaks = [];
  for (let i = margin; i < regionW - margin; i++) {
    const c = counts[i];
    if (c < 4) continue;
    if (c >= counts[i - 1] && c > counts[i + 1]) peaks.push({ count: c, i });
  }
  if (peaks.length === 0) {
    let bestI = margin;
    let bestC = 0;
    for (let i = margin; i < regionW - margin; i++) {
      if (counts[i] > bestC) { bestC = counts[i]; bestI = i; }
    }
    if (bestC < 4) return null;
    peaks.push({ count: bestC, i: bestI });
  }

  let maxCount = 0;
  for (const p of peaks) if (p.count > maxCount) maxCount = p.count;
  const strong = peaks.filter((p) => p.count >= maxCount * 0.55);

  let chosen = strong[0];
  if (hintX != null && strong.length > 1) {
    const toX = canvasWidth / w;
    let bestDist = Infinity;
    for (const p of strong) {
      const cxCfg = goalLeft + p.i * (goalRight - goalLeft) / regionW;
      const dist = Math.abs(cxCfg - hintX);
      if (dist < bestDist) { bestDist = dist; chosen = p; }
    }
  } else {
    let bestScore = -1;
    for (const p of strong) {
      const left = Math.max(0, p.i - Math.floor(window / 2));
      const right = p.i + Math.floor(window / 2);
      let top = y1, bottom = y0, mass = 0;
      for (let y = 0; y < regionH; y++) {
        const py = y0 + y;
        for (let x = left; x < right; x += 2) {
          if (x < 0 || x >= regionW) continue;
          const i = (y * regionW + x) * 4;
          const r = data[i], g = data[i + 1], b = data[i + 2];
          if (isKeeper(r, g, b)) {
            mass++;
            if (py < top) top = py;
            if (py > bottom) bottom = py;
          }
        }
      }
      const score = Math.max(0, bottom - top) * mass;
      if (score > bestScore) { bestScore = score; chosen = p; }
    }
  }

  const centerPx = gl + chosen.i;
  const leftPx = Math.floor(centerPx - window / 2);
  const rightPx = leftPx + window;
  let topPx = y1;
  let bottomPx = y0;

  for (let y = 0; y < regionH; y++) {
    const py = y0 + y;
    for (let x = chosen.i - Math.floor(window / 2); x < chosen.i + Math.floor(window / 2); x += 2) {
      if (x < 0 || x >= regionW) continue;
      const i = (y * regionW + x) * 4;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      if (isKeeper(r, g, b)) {
        if (py < topPx) topPx = py;
        if (py > bottomPx) bottomPx = py;
      }
    }
  }
  if (topPx >= bottomPx) return null;

  const toX = canvasWidth / w;
  const toY = canvasHeight / h;
  const left = leftPx * toX;
  const right = rightPx * toX;
  const top = topPx * toY;
  const bottom = bottomPx * toY;
  return {
    cx: (left + right) / 2,
    cy: (top + bottom) / 2,
    left,
    right,
    top,
    bottom,
  };
}
"""

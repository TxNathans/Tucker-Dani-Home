/* Video deck: one or two videos with switchable layers (body lines, hand path, racket tracer, racket plane, feet, angles...),
   drawing tools (line, angle, circle, freehand) and one set of playback controls. */
(function () {
  const TT = window.TT = window.TT || {};
  const svg = (d, extra = '') => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${d}</svg>`;
  const ICON = TT.ICON = {
    line: svg('<path d="M6 18 18 6"/><circle cx="5" cy="19" r="1.7"/><circle cx="19" cy="5" r="1.7"/>'),
    angle: svg('<path d="M4.5 19h15.5M4.5 19 15 5"/><path d="M12 19a7.4 7.4 0 0 0-3-6"/>'),
    circle: svg('<circle cx="12" cy="12" r="7.6"/>'),
    pen: svg('<path d="M3.5 16.5c3-7 5.2 2.6 8.4-2.8S15.6 6 20.5 7.6"/>'),
    undo: svg('<path d="M8.5 5 4.5 9l4 4"/><path d="M4.5 9H14a5 5 0 0 1 0 10h-4"/>'),
    clear: svg('<path d="M5 7h14M10 7V4.8h4V7M7 7l.9 12.2h8.2L17 7"/>'),
    save: svg('<path d="M12 4v10.5M7.8 10.6l4.2 4.2 4.2-4.2M5 19.5h14"/>'),
    play: svg('<path d="M8.2 5.4v13.2l11-6.6z" fill="currentColor" stroke="none"/>'),
    pause: svg('<path d="M8.5 5.5v13M15.5 5.5v13" stroke-width="3.2"/>'),
    back: svg('<path d="M17.5 6.2 9.8 12l7.7 5.8z" fill="currentColor"/><path d="M6.8 6v12"/>'),
    fwd: svg('<path d="M6.5 6.2 14.2 12l-7.7 5.8z" fill="currentColor"/><path d="M17.2 6v12"/>'),
    left: svg('<path d="M14.5 6 8.5 12l6 6"/>'), right: svg('<path d="M9.5 6l6 6-6 6"/>'),
    close: svg('<path d="M6 6l12 12M18 6 6 18"/>'), check: svg('<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7L16 9.6"/>'),
    arrow: svg('<path d="M4 12h15M13.5 6.5 19 12l-5.500 5.500"/>'),
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2.8v2.4M12 18.800v2.400M2.800 12h2.400M18.800 12h2.400M5.500 5.500l1.700 1.700M16.800 16.800l1.700 1.700M5.500 18.500l1.700-1.700M16.800 7.200l1.700-1.700"/>'),
    moon: svg('<path d="M19.500 14.200A8 8 0 0 1 9.800 4.500a8 8 0 1 0 9.700 9.700z"/>'),
  };
  const LAYERS = [
    ['skeleton', 'Body lines', true], ['hand', 'Hand path', true], ['tracer', 'Racket tracer', true], ['plane', 'Racket plane', false],
    ['feet', 'Feet', true], ['angles', 'Angles', false], ['contact', 'Contact', true], ['box', 'Racket box', false], ['labels', 'Labels', true],
  ];
  const TOOLS = [['line', 'Line'], ['angle', 'Angle'], ['circle', 'Circle'], ['pen', 'Freehand']];
  const COLORS = [['#ffd60a', 'Yellow'], ['#ffffff', 'White'], ['#ff453a', 'Red']];
  const HINTS = {
    line: 'Line: drag across the video. It shows its angle from level.',
    angle: 'Angle: drag the first side out from the corner, then drag or tap the second side.',
    circle: 'Circle: drag out from the centre.', pen: 'Freehand: draw on the video.',
  };
  const GRADE_COLOR = {strength: '#4ade80', on_target: '#60a5fa', building: '#fbbf24', priority: '#f87171'};
  const BONES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28], [15, 19], [16, 20]];
  const JOINTS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];
  const ARM = {right: [12, 14, 16, 20], left: [11, 13, 15, 19]};
  const BLUE = '#3d86ff', EDGE = 'rgba(12, 18, 24, .85)';
  const store = {
    get(key, fallback) { try { const v = JSON.parse(localStorage.getItem(key)); return v ?? fallback; } catch (e) { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {} },
  };
  TT.store = store;

  // ---------- one video with its canvas ----------
  class Stage {
    constructor(spec) {
      Object.assign(this, {fps: 30, tracks: null, swings: [], series: null, tag: '', zeroFrame: 0}, spec);
      this.drawings = []; this.pending = null; this.exact = null; this.head = null;
      if (this.tracks && this.tracks.racket_head) {          // light smoothing so the tracer is a clean line, not detector jitter
        const H = this.tracks.racket_head, n = Math.max(1, Math.round(this.fps * 0.035));
        this.head = H.map((p, k) => {
          if (!p) return null;
          let x = 0, y = 0, c = 0;
          for (let j = k - n; j <= k + n; j++) if (H[j]) { x += H[j][0]; y += H[j][1]; c++; }
          return [x / c, y / c];
        });
      }
      this.el = document.createElement('div');
      this.el.className = 'screen';
      this.el.innerHTML = `<video playsinline muted preload="auto" src="${spec.src}"></video><canvas></canvas>${this.tag ? `<span class="tag">${this.tag}</span>` : ''}`;
      this.video = this.el.firstChild; this.canvas = this.el.children[1];
      const shape = () => {
        const a = this.video.videoWidth / this.video.videoHeight || (this.tracks && this.tracks.aspect) || 0.75;
        this.aspect = a; this.el.style.aspectRatio = String(a); this.el.style.maxWidth = `calc(${this.tall || 64}vh * ${a})`;
      };
      this.el.style.margin = '0 auto'; this.el.style.width = '100%';
      this.video.style.height = '100%';
      shape();
      this.video.addEventListener('loadedmetadata', shape);
      this.video.addEventListener('seeking', () => { this.exact = null; });
      if (this.video.requestVideoFrameCallback) {
        const tick = (now, meta) => { this.exact = meta.mediaTime; if (this.onPaint) this.onPaint(); this.video.requestVideoFrameCallback(tick); };
        this.video.requestVideoFrameCallback(tick);
      }
    }
    get zero() { return (this.zeroFrame + 0.5) / this.fps; }      // the moment both videos line up on: the middle of the contact frame
    get frames() { return this.tracks ? this.tracks.frames : Math.max(1, Math.round((this.video.duration || 0) * this.fps)); }
    get frame() {
      const k = this.exact !== null ? Math.round(this.exact * this.fps) : Math.floor(this.video.currentTime * this.fps + 1e-3);
      return Math.max(0, Math.min(this.frames - 1, k));
    }
    timeOf(frame) { return (Math.max(0, Math.min(this.frames - 1, frame)) + 0.5) / this.fps; }
    seek(time) { const d = this.video.duration || 1e9; this.video.currentTime = Math.max(0, Math.min(d - 0.001, time)); }
    swingAt(frame) {
      let found = null;
      for (const s of this.swings) if (frame >= s.frames.takeback - 2) found = s;
      return found;
    }
    fit() {
      const r = this.el.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      const w = Math.round(r.width * dpr), h = Math.round(r.height * dpr);
      if (w && h && (this.canvas.width !== w || this.canvas.height !== h)) { this.canvas.width = w; this.canvas.height = h; }
      return [r.width, r.height, dpr];
    }
    paint(layers) {
      const [w, h, dpr] = this.fit();
      if (!w || !h) return;
      const ctx = this.canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      this.render(ctx, w, h, layers);
    }
    render(ctx, w, h, layers) {
      if (this.tracks && layers) drawLayers(ctx, w, h, this, layers);
      drawMarks(ctx, w, h, this.pending ? [...this.drawings, this.pending] : this.drawings);
    }
  }

  // ---------- layers ----------
  function drawLayers(ctx, w, h, st, on) {
    const T = st.tracks, i = st.frame, pose = T.pose[i];
    if (!pose) return;
    const u = Math.max(1.4, h / 420), hidden = new Set(T.hidden[i] || []);
    const P = (j, row = pose) => [row[2 * j] * w / 1000, row[2 * j + 1] * h / 1000];
    const head = k => { const p = st.head && st.head[k]; return p ? [p[0] * w / 1000, p[1] * h / 1000] : null; };
    const wr = T.hand === 'left' ? 15 : 16, wrist = k => P(wr, T.pose[k]);
    const s = st.swingAt(i);
    const line = (a, b, color, width) => {
      ctx.lineCap = 'round';
      ctx.strokeStyle = EDGE; ctx.lineWidth = width + 2.4; ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
    };
    const path = (pts, color, width, alpha = 1) => {
      if (pts.length < 2) return;
      ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
      for (let k = 1; k < pts.length - 1; k++) ctx.quadraticCurveTo(pts[k][0], pts[k][1], (pts[k][0] + pts[k + 1][0]) / 2, (pts[k][1] + pts[k + 1][1]) / 2);
      ctx.lineTo(pts[pts.length - 1][0], pts[pts.length - 1][1]); ctx.stroke(); ctx.restore();
    };
    const pill = (text, x, y, bg = 'rgba(12, 18, 24, .78)', fg = '#fff', align = 'left') => {
      const size = Math.max(11, Math.min(15, h / 44));
      ctx.font = `600 ${size}px "DM Sans", system-ui, sans-serif`;
      const tw = ctx.measureText(text).width, bw = tw + size * 1.1, bh = size * 1.75;
      let bx = align === 'center' ? x - bw / 2 : align === 'right' ? x - bw : x;
      bx = Math.max(4, Math.min(w - bw - 4, bx)); const by = Math.max(4, Math.min(h - bh - 4, y - bh / 2));
      ctx.fillStyle = bg; ctx.beginPath(); ctx.roundRect ? ctx.roundRect(bx, by, bw, bh, bh / 2) : ctx.rect(bx, by, bw, bh); ctx.fill();
      ctx.fillStyle = fg; ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.fillText(text, bx + size * 0.55, by + bh / 2 + 0.5);
    };

    // racket plane: the surface the racket sweeps from the start of the forward swing, with the tilt of the path at contact
    if (on.plane && s && T.racket_head) {
      const a = s.frames.racket_drop ?? s.frames.forward_swing, b = Math.min(i, s.frames.finish);
      const rows = [];
      for (let k = a; k <= b; k++) { const p = head(k); if (p) rows.push([k, wrist(k), p]); }
      if (rows.length > 1) {
        ctx.save();
        ctx.beginPath(); rows.forEach((r, n) => n ? ctx.lineTo(r[2][0], r[2][1]) : ctx.moveTo(r[2][0], r[2][1]));
        for (let n = rows.length - 1; n >= 0; n--) ctx.lineTo(rows[n][1][0], rows[n][1][1]);
        ctx.closePath(); ctx.fillStyle = 'rgba(61, 134, 255, .24)'; ctx.fill();
        ctx.strokeStyle = 'rgba(255, 255, 255, .55)'; ctx.lineWidth = Math.max(1, u * 0.55);
        const every = Math.max(1, Math.round(st.fps / 40));
        rows.forEach((r, n) => { if (n % every === 0 || n === rows.length - 1) { ctx.beginPath(); ctx.moveTo(r[1][0], r[1][1]); ctx.lineTo(r[2][0], r[2][1]); ctx.stroke(); } });
        ctx.restore();
      }
      const c = s.frames.contact, span = Math.max(2, Math.round(st.fps * 0.05));
      if (i >= c - span) {
        const near = []; for (let k = c - span; k <= Math.min(c + span, i); k++) { const p = head(k); if (p) near.push(p); }
        if (near.length >= 3) {
          const mx = near.reduce((t, p) => t + p[0], 0) / near.length, my = near.reduce((t, p) => t + p[1], 0) / near.length;
          let sxx = 0, sxy = 0, syy = 0; near.forEach(p => { sxx += (p[0] - mx) ** 2; sxy += (p[0] - mx) * (p[1] - my); syy += (p[1] - my) ** 2; });
          const ang = 0.5 * Math.atan2(2 * sxy, sxx - syy), dx = Math.cos(ang), dy = Math.sin(ang), len = h * 0.3;
          ctx.save(); ctx.setLineDash([u * 4, u * 3.2]); ctx.strokeStyle = '#fff'; ctx.lineWidth = u * 1.1;
          ctx.beginPath(); ctx.moveTo(mx - dx * len, my - dy * len); ctx.lineTo(mx + dx * len, my + dy * len); ctx.stroke(); ctx.restore();
          const m = (s.metrics || []).find(q => q.key === 'swing_plane' || q.key === 'serve_swing_up');
          const deg = m && typeof m.value === 'number' ? m.value : Math.round(Math.abs(Math.atan2(dy, dx) * 180 / Math.PI) > 90 ? 180 - Math.abs(Math.atan2(dy, dx) * 180 / Math.PI) : Math.abs(Math.atan2(dy, dx) * 180 / Math.PI));
          const hips = (P(23)[0] + P(24)[0]) / 2, side = mx >= hips ? 1 : -1, sx = Math.sign(dx) || 1;       // label at the end of the line away from the body
          const end = [mx + side * sx * dx * len, my + side * sx * dy * len];
          pill(`Racket plane ${deg}° up from level`, end[0], end[1] - h * 0.035, 'rgba(255, 255, 255, .92)', '#1d2536', side > 0 ? 'right' : 'left');
        }
      }
    }

    // racket tracer: the whole path of the racket head through the swing (the hand when the racket was not tracked)
    if (on.tracer && s) {
      const source = T.racket_head ? head : wrist, end = Math.min(i, s.frames.finish + Math.round(st.fps * 0.2));
      const runs = [[]];
      let gap = 0;
      for (let k = s.frames.takeback; k <= end; k++) {
        const p = source(k);
        if (!p) { if (++gap > 4 && runs[runs.length - 1].length) runs.push([]); continue; }
        gap = 0; runs[runs.length - 1].push([k, p]);
      }
      const part = (from, to) => runs.map(r => r.filter(q => q[0] >= from && q[0] <= to).map(q => q[1])).filter(r => r.length > 1);
      const fs = s.frames.forward_swing, c = s.frames.contact;
      part(-1, fs).forEach(r => path(r, '#ffffff', u * 1.5, 0.55));
      part(fs, 1e9).forEach(r => path(r, BLUE, u * 6.5, 0.28));
      part(fs, c).forEach(r => { path(r, BLUE, u * 3.1); path(r, '#ffffff', u * 1.05, 0.95); });
      part(c, 1e9).forEach(r => { path(r, '#9cc0ff', u * 2.6); path(r, '#ffffff', u * 0.9, 0.8); });
      const hit = i >= c ? source(c) : null;
      if (hit) { ctx.fillStyle = '#fff'; ctx.strokeStyle = BLUE; ctx.lineWidth = u * 1.4; ctx.beginPath(); ctx.arc(hit[0], hit[1], u * 3.2, 0, 7); ctx.fill(); ctx.stroke(); }
    }

    // hand path: a short fading trail behind the hitting hand
    if (on.hand) {
      const n = Math.max(3, Math.round(st.fps * 0.5)), lo = Math.max(0, i - n);
      ctx.save(); ctx.lineCap = 'round';
      for (let k = lo + 1; k <= i; k++) {
        const f = (k - lo) / (i - lo || 1), a = wrist(k - 1), b = wrist(k);
        ctx.strokeStyle = BLUE; ctx.globalAlpha = 0.92 * f ** 1.5; ctx.lineWidth = u * 2 * (0.5 + f);
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      }
      ctx.restore();
    }

    if (on.box && T.racket_box && T.racket_box[i]) {
      const b = T.racket_box[i], x = b[0] * w / 1000, y = b[1] * h / 1000;
      ctx.strokeStyle = '#fff'; ctx.lineWidth = Math.max(1, u * 0.7); ctx.setLineDash([u * 3, u * 2]);
      ctx.strokeRect(x, y, b[2] * w / 1000 - x, b[3] * h / 1000 - y); ctx.setLineDash([]);
      pill('Racket', x, y - h * 0.022);
    }

    if (on.skeleton) {
      const arm = new Set(ARM[T.hand] || []), later = [];
      for (const [a, b] of BONES) {
        if (hidden.has(a) || hidden.has(b)) continue;
        if (arm.has(a) && arm.has(b)) { later.push([a, b]); continue; }
        line(P(a), P(b), '#f5f5f5', u * 1.9);
      }
      later.forEach(([a, b]) => line(P(a), P(b), BLUE, u * 2.5));
      for (const j of JOINTS) {
        if (hidden.has(j)) continue;
        const p = P(j);
        ctx.fillStyle = EDGE; ctx.beginPath(); ctx.arc(p[0], p[1], u * 2.9, 0, 7); ctx.fill();
        ctx.fillStyle = arm.has(j) ? BLUE : '#f5f5f5'; ctx.beginPath(); ctx.arc(p[0], p[1], u * 1.9, 0, 7); ctx.fill();
      }
      const e1 = P(7), e2 = P(8), n0 = P(0), cx = (e1[0] + e2[0] + n0[0]) / 3, cy = (e1[1] + e2[1] + n0[1]) / 3;
      const rad = Math.max(u * 4, Math.hypot(e1[0] - e2[0], e1[1] - e2[1]) * 0.9);
      ctx.strokeStyle = EDGE; ctx.lineWidth = u * 3.6; ctx.beginPath(); ctx.arc(cx, cy, rad, 0, 7); ctx.stroke();
      ctx.strokeStyle = '#f5f5f5'; ctx.lineWidth = u * 1.5; ctx.beginPath(); ctx.arc(cx, cy, rad, 0, 7); ctx.stroke();
    }

    // feet: an arrow along each foot, coloured by how that foot graded at this point of the swing
    if (on.feet) {
      const grade = {left: null, right: null};
      if (s && s.topdown && i <= s.frames.finish + 6) {
        const g = (s.coaching && s.coaching.grades) || {}, front = s.topdown.front, rear = front === 'right' ? 'left' : 'right';
        if (i < s.frames.forward_swing) grade[rear] = g.back_foot_angle; else { grade[front] = g.front_foot_angle; grade[rear] = g.back_foot_pivot; }
      }
      for (const [side, heel, toe] of [['left', 29, 31], ['right', 30, 32]]) {
        if (hidden.has(heel) || hidden.has(toe)) continue;
        const a = P(heel), b = P(toe), tip = [b[0] + (b[0] - a[0]) * 0.55, b[1] + (b[1] - a[1]) * 0.55];
        const color = GRADE_COLOR[grade[side]] || '#f5f5f5', ang = Math.atan2(tip[1] - a[1], tip[0] - a[0]), hl = u * 6;
        line(a, tip, color, u * 2.4);
        ctx.fillStyle = color; ctx.strokeStyle = EDGE; ctx.lineWidth = 1.2; ctx.beginPath();
        ctx.moveTo(tip[0] + Math.cos(ang) * hl * 0.6, tip[1] + Math.sin(ang) * hl * 0.6);
        ctx.lineTo(tip[0] + Math.cos(ang + 2.5) * hl, tip[1] + Math.sin(ang + 2.5) * hl);
        ctx.lineTo(tip[0] + Math.cos(ang - 2.5) * hl, tip[1] + Math.sin(ang - 2.5) * hl); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
    }

    // angles: knees and the hitting elbow, from the 3D body estimate
    if (on.angles && st.series) {
      const S = st.series, dom = T.hand === 'left' ? 'left' : 'right', lead = s && ((s.topdown && s.topdown.front) || (s.serve && s.serve.lead));
      const rows = [];
      const kneeName = side => lead ? (side === lead ? 'Lead knee' : 'Trail knee') : (side === 'left' ? 'Left knee' : 'Right knee');
      for (const [side, hip, knee, ankle] of [['left', 23, 25, 27], ['right', 24, 26, 28]]) {
        const v = side === dom ? S.knee : S.knee_off;
        if (v && v[i] !== undefined && !hidden.has(knee)) rows.push([kneeName(side), v[i], P(hip), P(knee), P(ankle)]);
      }
      const [sh, el, wj] = dom === 'left' ? [11, 13, 15] : [12, 14, 16];
      if (S.elbow && !hidden.has(el)) rows.push(['Elbow', S.elbow[i], P(sh), P(el), P(wj)]);
      const mid = P(23)[0] / 2 + P(24)[0] / 2;
      for (const [name, value, a, v, c] of rows) {
        const a1 = Math.atan2(a[1] - v[1], a[0] - v[0]), a2 = Math.atan2(c[1] - v[1], c[0] - v[0]);
        let d = a2 - a1; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
        ctx.strokeStyle = '#ffd60a'; ctx.lineWidth = u * 1.3; ctx.beginPath(); ctx.arc(v[0], v[1], u * 9, a1, a1 + d, d < 0); ctx.stroke();
        const outward = v[0] >= mid;
        pill(`${name} ${Math.round(value)}°`, v[0] + (outward ? u * 12 : -u * 12), v[1], 'rgba(12, 18, 24, .8)', '#ffd60a', outward ? 'left' : 'right');
      }
    }

    if (on.contact) for (const q of st.swings) {
      if (Math.abs(i - q.frames.contact) <= Math.max(1, Math.round(st.fps * 0.035))) {
        const p = wrist(i);
        ctx.strokeStyle = EDGE; ctx.lineWidth = u * 4; ctx.beginPath(); ctx.arc(p[0], p[1], u * 13, 0, 7); ctx.stroke();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = u * 2; ctx.beginPath(); ctx.arc(p[0], p[1], u * 13, 0, 7); ctx.stroke();
      }
    }

    if (on.labels && s && i <= s.frames.finish + 6) {
      let label = '';
      for (const [key, name] of (s.phases || [])) if (s.frames[key] !== undefined && i >= s.frames[key]) label = name;
      if (label) pill((st.swings.length > 1 ? s.index + '. ' : '') + label, 10, 10 + h / 50, i === s.frames.contact ? BLUE : 'rgba(12, 18, 24, .78)');
    }
  }

  // ---------- drawings ----------
  function drawMarks(ctx, w, h, marks) {
    const px = p => [p[0] * w, p[1] * h], lw = Math.max(2, h / 260);
    const label = (text, x, y, color) => {
      const size = Math.max(12, Math.min(16, h / 40));
      ctx.font = `650 ${size}px "DM Sans", system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const tw = ctx.measureText(text).width + size * 0.9, bh = size * 1.6;
      ctx.fillStyle = 'rgba(12, 18, 24, .82)'; ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x - tw / 2, y - bh / 2, tw, bh, bh / 2) : ctx.rect(x - tw / 2, y - bh / 2, tw, bh); ctx.fill();
      ctx.fillStyle = color; ctx.fillText(text, x, y + 0.5);
    };
    const stroke = (build, color) => {
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.strokeStyle = 'rgba(12, 18, 24, .55)'; ctx.lineWidth = lw + 2.2; ctx.beginPath(); build(); ctx.stroke();
      ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.beginPath(); build(); ctx.stroke();
    };
    const knob = (p, color) => { ctx.fillStyle = color; ctx.strokeStyle = 'rgba(12, 18, 24, .6)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(p[0], p[1], lw * 1.5, 0, 7); ctx.fill(); ctx.stroke(); };
    for (const m of marks) {
      const pts = m.pts.map(px);
      if (m.tool === 'pen') { if (pts.length > 1) stroke(() => pts.forEach((p, n) => n ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])), m.color); continue; }
      if (pts.length < 2) continue;
      const [a, b] = pts;
      if (m.tool === 'line') {
        stroke(() => { ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); }, m.color); knob(a, m.color); knob(b, m.color);
        let deg = Math.abs(Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI); if (deg > 90) deg = 180 - deg;
        if (Math.hypot(b[0] - a[0], b[1] - a[1]) > 40) label(`${Math.round(deg)}°`, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - lw * 7, m.color);
      } else if (m.tool === 'circle') {
        stroke(() => ctx.arc(a[0], a[1], Math.hypot(b[0] - a[0], b[1] - a[1]), 0, 7), m.color);
      } else if (m.tool === 'angle') {            // a = corner, b = end of the first side, c = end of the second side
        stroke(() => { ctx.moveTo(b[0], b[1]); ctx.lineTo(a[0], a[1]); if (pts[2]) ctx.lineTo(pts[2][0], pts[2][1]); }, m.color);
        knob(a, m.color); knob(b, m.color);
        if (pts[2]) {
          const c = pts[2], a1 = Math.atan2(b[1] - a[1], b[0] - a[0]), a2 = Math.atan2(c[1] - a[1], c[0] - a[0]);
          let d = a2 - a1; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
          const r = Math.min(lw * 12, Math.hypot(b[0] - a[0], b[1] - a[1]) * 0.5, Math.hypot(c[0] - a[0], c[1] - a[1]) * 0.5);
          stroke(() => ctx.arc(a[0], a[1], r, a1, a1 + d, d < 0), m.color); knob(c, m.color);
          const midA = a1 + d / 2;
          label(`${Math.round(Math.abs(d) * 180 / Math.PI)}°`, a[0] + Math.cos(midA) * (r + lw * 9), a[1] + Math.sin(midA) * (r + lw * 9), m.color);
        }
      }
    }
  }

  // ---------- deck ----------
  TT.deck = function (mount, opts) {
    const stages = opts.stages.map(spec => new Stage(spec));
    const master = stages[0], dual = stages.length > 1, hasLayers = stages.some(s => s.tracks);
    const layers = Object.assign(Object.fromEntries(LAYERS.map(([k, , d]) => [k, d])), store.get('tt-layers', {}));
    let allOn = store.get('tt-layers-on', true), tool = null, color = COLORS[0][0], playing = false, raf = 0, alive = true, rateKey = opts.contact === false ? 'tt-rate-full' : 'tt-rate', rate = store.get(rateKey, opts.contact === false ? 1 : 0.25);
    const hasRacket = stages.some(s => s.tracks && s.tracks.racket_head);

    mount.innerHTML = `<div class="deck">
      ${hasLayers ? `<div class="layerbar" role="group" aria-label="What to show on the video">
        <button class="switch master ${allOn ? 'on' : ''}" data-layer="*"><i></i>Overlays</button>
        ${LAYERS.map(([k, name]) => `<button class="switch ${layers[k] ? 'on' : ''}" data-layer="${k}" ${(k === 'plane' || k === 'box') && !hasRacket ? 'disabled title="The racket was not tracked in this clip"' : ''}><i></i>${name}</button>`).join('')}
      </div>` : ''}
      <div class="stagewrap"><div class="screens"></div>
        <div class="toolcol" role="toolbar" aria-label="Drawing tools">
          ${TOOLS.map(([k, name]) => `<button class="ibtn" data-tool="${k}" title="${name}" aria-label="${name}" aria-pressed="false">${ICON[k]}</button>`).join('')}
          <hr>${COLORS.map(([c, name], n) => `<button class="swatch ${n ? '' : 'on'}" data-color="${c}" style="background:${c}" title="${name}" aria-label="${name}"></button>`).join('')}
          <hr><button class="ibtn" data-act="undo" title="Undo" aria-label="Undo">${ICON.undo}</button>
          <button class="ibtn" data-act="clear" title="Clear drawings" aria-label="Clear drawings">${ICON.clear}</button>
          <button class="ibtn" data-act="save" title="Save picture" aria-label="Save picture">${ICON.save}</button>
        </div></div>
      <div class="transport">
        <button class="ibtn" data-act="back" title="Back one frame" aria-label="Back one frame">${ICON.back}</button>
        <button class="play" data-act="play" title="Play" aria-label="Play">${ICON.play}</button>
        <button class="ibtn" data-act="fwd" title="Forward one frame" aria-label="Forward one frame">${ICON.fwd}</button>
        ${opts.contact !== false ? '<button class="btn sm" data-act="contact">Contact</button>' : ''}
        <input type="range" min="0" max="1000" value="0" step="1" aria-label="Scrub through the video">
        <div class="clock num"><span>0</span><small>${opts.contact !== false ? 'ms from contact' : 'seconds'}</small></div>
        <select aria-label="Playback speed">${[[0.1, '1/10 speed'], [0.25, '1/4 speed'], [0.5, '1/2 speed'], [1, 'Full speed']].map(([v, n]) => `<option value="${v}" ${v === rate ? 'selected' : ''}>${n}</option>`).join('')}</select>
      </div>
      <div class="hint" aria-live="polite"></div></div>`;
    const root = mount.firstChild, screens = root.querySelector('.screens'), scrub = root.querySelector('input[type=range]');
    const clock = root.querySelector('.clock span'), hint = root.querySelector('.hint'), playBtn = root.querySelector('[data-act=play]');
    stages.forEach(s => screens.appendChild(s.el));

    // time is counted from contact ("rel"), so two videos line up on their contact points
    const range = () => {
      const lo = Math.max(...stages.map(s => -s.zero)), hi = Math.min(...stages.map(s => (s.video.duration || s.frames / s.fps) - s.zero));
      return [lo, Math.max(lo + 0.01, hi - 0.5 / master.fps)];
    };
    const rel = () => master.video.currentTime - master.zero;
    const active = () => layers && allOn ? layers : null;
    const paint = () => {
      stages.forEach(s => s.paint(active()));
      const [lo, hi] = range(), r = rel();
      if (document.activeElement !== scrub || playing) scrub.value = String(Math.round((r - lo) / (hi - lo) * 1000));
      const fromContact = (master.frame - master.zeroFrame) / master.fps;
      clock.textContent = opts.contact !== false ? `${fromContact > 0 ? '+' : ''}${Math.round(fromContact * 1000)}` : master.video.currentTime.toFixed(2);
      if (opts.onFrame) opts.onFrame(master.frame, master);
    };
    stages.forEach(s => { s.onPaint = () => { if (!playing) paint(); }; });
    const seekRel = r => { const [lo, hi] = range(); r = Math.max(lo, Math.min(hi, r)); stages.forEach(s => s.seek(s.zero + r)); requestAnimationFrame(paint); };
    const setPlaying = on => {
      playing = on; playBtn.innerHTML = on ? ICON.pause : ICON.play; playBtn.title = on ? 'Pause' : 'Play'; playBtn.setAttribute('aria-label', playBtn.title);
      cancelAnimationFrame(raf);
      if (!on) { stages.forEach(s => s.video.pause()); return paint(); }
      const [lo, hi] = range();
      if (rel() >= hi - 0.02) stages.forEach(s => s.seek(s.zero + lo));
      stages.forEach(s => { s.video.playbackRate = rate; s.video.play().catch(() => {}); });
      const loop = () => {
        if (!alive || !playing) return;
        const r = rel();
        for (const s of stages.slice(1)) if (Math.abs(s.video.currentTime - s.zero - r) > 0.09) s.seek(s.zero + r);
        paint();
        if (r >= range()[1] || master.video.ended) return setPlaying(false);
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    };
    const step = d => { setPlaying(false); const k = master.frame + d; const r = master.timeOf(k) - master.zero; seekRel(r); };
    const freeze = frame => { setPlaying(false); seekRel(master.timeOf(frame) - master.zero); };

    stages.forEach(s => {
      ['seeked', 'loadeddata', 'timeupdate'].forEach(ev => s.video.addEventListener(ev, () => { if (!playing) paint(); }));
      s.video.addEventListener('loadedmetadata', () => { if (s === master && opts.startFrame !== undefined) s.seek(s.timeOf(opts.startFrame)); else s.seek(Math.max(0, s.zero + range()[0])); });
      new ResizeObserver(() => { if (!playing) paint(); }).observe(s.el);
    });
    scrub.addEventListener('input', () => { setPlaying(false); const [lo, hi] = range(); seekRel(lo + (hi - lo) * scrub.value / 1000); });
    root.querySelector('select').addEventListener('change', ev => { rate = +ev.target.value; store.set(rateKey, rate); stages.forEach(s => { s.video.playbackRate = rate; }); });

    // drawing
    const setTool = name => {
      tool = tool === name ? null : name;
      stages.forEach(s => { s.pending = null; s.el.classList.toggle('drawing', !!tool); });
      root.querySelectorAll('[data-tool]').forEach(b => { const on = b.dataset.tool === tool; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); });
      hint.textContent = tool ? HINTS[tool] : '';
      if (tool) setPlaying(false); else paint();
    };
    stages.forEach(s => {
      const at = ev => { const r = s.canvas.getBoundingClientRect(); return [(ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height]; };
      const far = (a, b) => Math.hypot((a[0] - b[0]) * s.canvas.clientWidth, (a[1] - b[1]) * s.canvas.clientHeight) > 6;
      let down = false;
      s.canvas.addEventListener('pointerdown', ev => {
        if (!tool) return;
        ev.preventDefault(); s.canvas.setPointerCapture(ev.pointerId); down = true;
        const p = at(ev);
        if (tool === 'angle' && s.pending && s.pending.tool === 'angle' && s.pending.pts.length >= 2) s.pending.pts[2] = p;
        else s.pending = {tool, color, pts: tool === 'pen' ? [p] : [p, p]};
        paint();
      });
      s.canvas.addEventListener('pointermove', ev => {
        if (!down || !s.pending) return;
        const p = at(ev), m = s.pending;
        if (m.tool === 'pen') { if (far(m.pts[m.pts.length - 1], p)) m.pts.push(p); }
        else m.pts[m.pts.length - 1] = p;
        paint();
      });
      const up = () => {
        if (!down) return; down = false;
        const m = s.pending; if (!m) return;
        if (m.tool === 'angle' && m.pts.length === 2) {
          if (!far(m.pts[0], m.pts[1])) s.pending = null; else hint.textContent = 'Now drag or tap where the second side should end.';
          return paint();
        }
        if (m.tool === 'pen' ? m.pts.length > 2 : far(m.pts[0], m.pts[1])) s.drawings.push(m);
        s.pending = null; if (m.tool === 'angle') hint.textContent = HINTS.angle;
        paint();
      };
      s.canvas.addEventListener('pointerup', up); s.canvas.addEventListener('pointercancel', up);
    });
    const savePicture = () => {
      const tiles = stages.map(s => {
        const c = document.createElement('canvas'); c.width = s.video.videoWidth || 720; c.height = s.video.videoHeight || 960;
        const ctx = c.getContext('2d'); ctx.drawImage(s.video, 0, 0, c.width, c.height); s.render(ctx, c.width, c.height, active()); return c;
      });
      const hh = Math.max(...tiles.map(c => c.height)), out = document.createElement('canvas');
      out.height = hh; out.width = tiles.reduce((t, c) => t + Math.round(c.width * hh / c.height), 0);
      const ctx = out.getContext('2d'); let x = 0;
      tiles.forEach(c => { const ww = Math.round(c.width * hh / c.height); ctx.drawImage(c, x, 0, ww, hh); x += ww; });
      out.toBlob(blob => {
        if (!blob) return;
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `tracer-tennis-frame-${master.frame}.png`;
        document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
        hint.textContent = 'Picture saved.';
      }, 'image/png');
    };

    root.addEventListener('click', ev => {
      const b = ev.target.closest('button'); if (!b) return;
      if (b.dataset.layer) {
        if (b.dataset.layer === '*') { allOn = !allOn; store.set('tt-layers-on', allOn); b.classList.toggle('on', allOn); }
        else { const k = b.dataset.layer; layers[k] = !layers[k]; store.set('tt-layers', layers); b.classList.toggle('on', layers[k]); if (layers[k] && !allOn) { allOn = true; store.set('tt-layers-on', true); root.querySelector('.master').classList.add('on'); } }
        return paint();
      }
      if (b.dataset.tool) return setTool(b.dataset.tool);
      if (b.dataset.color) { color = b.dataset.color; root.querySelectorAll('.swatch').forEach(x => x.classList.toggle('on', x === b)); return; }
      const act = b.dataset.act;
      if (act === 'play') setPlaying(!playing);
      else if (act === 'back') step(-1);
      else if (act === 'fwd') step(1);
      else if (act === 'contact') { setPlaying(false); seekRel(0); }
      else if (act === 'undo') { const s = [...stages].reverse().find(x => x.pending || x.drawings.length); if (s) { if (s.pending) s.pending = null; else s.drawings.pop(); } paint(); }
      else if (act === 'clear') { stages.forEach(s => { s.drawings = []; s.pending = null; }); paint(); }
      else if (act === 'save') savePicture();
    });

    const api = {
      el: root, stages, master,
      get playing() { return playing; },
      toggle: () => setPlaying(!playing), step, freeze,
      showAt(frame) { freeze(frame - Math.round(master.fps * 0.3)); rate = Math.min(rate, 0.25); root.querySelector('select').value = String(rate); setTimeout(() => setPlaying(true), 120); root.scrollIntoView({behavior: 'smooth', block: 'nearest'}); },
      setZero(frame) { master.zeroFrame = frame; paint(); },
      repaint: paint,
      destroy() { alive = false; cancelAnimationFrame(raf); stages.forEach(s => { s.video.pause(); s.video.removeAttribute('src'); s.video.load(); }); if (TT.activeDeck === api) TT.activeDeck = null; },
    };
    TT.activeDeck = api;
    return api;
  };

  document.addEventListener('keydown', ev => {
    const d = TT.activeDeck;
    if (!d || !document.body.contains(d.el) || /INPUT|SELECT|TEXTAREA/.test(ev.target.tagName) || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ev.key === ' ') { ev.preventDefault(); d.toggle(); }
    else if (ev.key === 'ArrowLeft') { ev.preventDefault(); d.step(-1); }
    else if (ev.key === 'ArrowRight') { ev.preventDefault(); d.step(1); }
  });
})();

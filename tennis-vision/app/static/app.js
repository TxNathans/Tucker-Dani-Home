/* Tracer Tennis pages: home, upload, swing and serve reads, compare, lesson and match. */
(function () {
  const TT = window.TT, ICON = TT.ICON, store = TT.store;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const view = $('#view'), drawer = $('#drawer'), scrim = $('#scrim');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const fmt = (v, d = 1) => v === null || v === undefined ? '–' : (typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(d)) : esc(v));
  const pctTxt = v => v === null || v === undefined ? '–' : v + '%';
  const nice = s => esc(String(s).replace(/_/g, ' '));
  const cap = s => s ? s[0].toUpperCase() + s.slice(1) : '';
  const MPH = 2.237;
  let pollTimer = null, pickedCorners = null, deck = null, saveCtx = null;

  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(m); }
    return r.json();
  }

  // ---------- grades, chips, meters ----------
  const GRADES = {strength: 'Strength', on_target: 'On target', building: 'Building', priority: 'Priority', not_graded: 'Not graded'};
  const SHAPES = {
    priority: '<path d="M5 0 10 5 5 10 0 5z"/>', building: '<path d="M5 .7 10 9.500H0z"/>', on_target: '<circle cx="5" cy="5" r="4.600"/>',
    strength: '<path d="M5 0l1.500 3.300 3.500.400-2.600 2.400.700 3.600L5 7.900 1.900 9.700l.700-3.600L0 3.700l3.500-.400z"/>',
    not_graded: '<circle cx="5" cy="5" r="3.600" fill="none" stroke="var(--g-not_graded)" stroke-width="1.800"/>',
  };
  const mark = g => `<svg class="mark" viewBox="0 0 10 10" fill="var(--g-${g in SHAPES ? g : 'not_graded'})" aria-hidden="true">${SHAPES[g] || SHAPES.not_graded}</svg>`;
  const gradeChip = g => `<span class="chip">${mark(g)}${GRADES[g] || GRADES.not_graded}</span>`;
  const LIGHT = {red: 'priority', yellow: 'building', green: 'on_target'};
  const unitTxt = u => u === 'deg' ? '°' : u ? ' ' + esc(u) : '';
  const valTxt = (v, u) => typeof v === 'number' ? `${fmt(v, Math.abs(v) < 10 ? 2 : 1)}<small>${u === 'deg' ? '°' : esc(u || '')}</small>` : `<span class="small">${esc(v)}</span>`;
  function meter(m, value) {
    if (!m || typeof value !== 'number') return '<div class="meter" aria-hidden="true"></div>';
    const pos = v => Math.max(0, Math.min(100, (v - m.min) / (m.max - m.min) * 100));
    return `<div class="meter" aria-hidden="true"><span class="zone" style="left:${pos(m.lo).toFixed(1)}%;width:${(pos(m.hi) - pos(m.lo)).toFixed(1)}%"></span><span class="here" style="left:${pos(value).toFixed(1)}%"></span></div>`;
  }
  function dial(hit, total) {
    const n = 41, R = 78, cx = 84, cy = 84, lit = total ? Math.round(hit / total * n) : 0;
    let ticks = '';
    for (let k = 0; k < n; k++) {
      const a = Math.PI - k / (n - 1) * Math.PI, c = Math.cos(a), s = Math.sin(a);
      ticks += `<line x1="${(cx + c * (R - 12)).toFixed(1)}" y1="${(cy - s * (R - 12)).toFixed(1)}" x2="${(cx + c * R).toFixed(1)}" y2="${(cy - s * R).toFixed(1)}" stroke="${k < lit ? 'var(--g-on_target)' : 'var(--tick)'}" stroke-width="2.600" stroke-linecap="round"/>`;
    }
    return `<div class="dial"><svg viewBox="0 0 168 90" role="img" aria-label="${hit} of ${total} on target">${ticks}</svg><div class="mid"><b class="num">${hit}/${total}</b><span>on target</span></div></div>`;
  }
  function countsBlock(c) {
    const n = {priority: c.priority || 0, building: c.building || 0, on_target: (c.on_target || 0) - (c.strength || 0), strength: c.strength || 0};      // strengths are counted inside on target
    return `<div class="counts">${['priority', 'building', 'on_target', 'strength'].map(g => `<div>${mark(g)}${GRADES[g]}<b class="num">${n[g]}</b></div>`).join('')}</div>`;
  }

  // ---------- small helpers: toast, extra icons ----------
  const svgi = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.900" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  Object.assign(ICON, {
    star: svgi('<path d="M12 3.600l2.600 5.300 5.800.800-4.200 4.100 1 5.800-5.200-2.700-5.200 2.700 1-5.800-4.200-4.100 5.800-.800z"/>'),
    help: svgi('<circle cx="12" cy="12" r="9"/><path d="M9.600 9.300a2.500 2.500 0 1 1 3.600 2.300c-.800.500-1.200 1-1.200 1.900"/><path d="M12 16.800v.100"/>'),
    doc: svgi('<path d="M7 3.500h7l4 4V20.500H7z"/><path d="M14 3.500v4h4M9.500 12.500h5M9.500 16h5"/>'),
    film: svgi('<rect x="3.500" y="5.500" width="17" height="13" rx="2"/><path d="M10 9.500v5l4.500-2.500z" fill="currentColor"/>'),
    image: svgi('<rect x="3.500" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.600"/><path d="M4.500 17l5-4.500 3.500 3 2.500-2 4 3.500"/>'),
    table: svgi('<rect x="3.500" y="5" width="17" height="14" rx="2"/><path d="M3.500 10h17M3.500 14.500h17M9.500 5v14"/>'),
  });
  let toastTimer = null;
  TT.toast = text => {
    let el = $('#toast');
    if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
    el.textContent = text; el.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
  };
  const patchJob = (id, body) => api('/api/jobs/' + id, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});

  // ---------- drawer ----------
  function openDrawer(html, label = 'Details') {
    drawer.scrollTop = 0;
    drawer.innerHTML = `<div class="rowline spread dhead"><span class="eyebrow">${label}</span><button class="ibtn" data-close aria-label="Close">${ICON.close}</button></div>${html}`;
    drawer.classList.add('open'); scrim.classList.add('open'); drawer.setAttribute('aria-hidden', 'false');
  }
  function closeDrawer() { drawer.classList.remove('open'); scrim.classList.remove('open'); drawer.setAttribute('aria-hidden', 'true'); }
  scrim.addEventListener('click', closeDrawer);
  drawer.addEventListener('click', ev => { if (ev.target.closest('[data-close]')) closeDrawer(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') closeDrawer(); });

  // ---------- save and share ----------
  let marksTimer = null, marksWaiting = null, notesTimer = null, toldMarks = false;
  function sendMarks() {
    clearTimeout(marksTimer);
    if (!marksWaiting) return;
    const [id, marks] = marksWaiting;
    marksWaiting = null;
    // keepalive lets the request finish even if the page is being closed or reloaded
    fetch(`/api/jobs/${id}/marks`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(marks), keepalive: true})
      .then(r => { if (!r.ok) throw new Error(); if (!toldMarks) { toldMarks = true; TT.toast('Drawings are saved with this video'); } })
      .catch(() => TT.toast('Could not save the drawing'));
  }
  function saveMarks(job, marks) {
    job.marks = marks.map(stage => stage.map(m => ({tool: m.tool, color: m.color, pts: m.pts})));
    marksWaiting = [job.id, job.marks];
    clearTimeout(marksTimer);
    marksTimer = setTimeout(sendMarks, 350);
  }
  window.addEventListener('pagehide', sendMarks);
  function openSave(job, opts = {}) {
    saveCtx = {job, opts};
    const id = job.id, isSwing = job.kind === 'swing' || job.kind === 'serve', q = opts.swing ? `?swing=${opts.swing}` : '';
    const link = (icon, title, sub, href) => `<a class="saverow" href="${href}" download><span class="ibtn">${icon}</span><span class="grow"><b>${title}</b><span class="tiny muted">${sub}</span></span></a>`;
    const act = (icon, title, sub, name) => `<button class="saverow" data-save="${name}"><span class="ibtn">${icon}</span><span class="grow"><b>${title}</b><span class="tiny muted">${sub}</span></span></button>`;
    openDrawer(`<h3>Save and share</h3>
      <p class="small ink2">This video and its read are saved on this computer automatically. Find them any time under Home.</p>
      <div class="lbl">Name</div><div class="rowline"><input type="text" id="svName" maxlength="80" value="${esc(job.title)}" aria-label="Name of this video"><button class="btn sm" data-save="name">Rename</button></div>
      <div style="margin-top:10px"><button class="switch ${job.starred ? 'on' : ''}" data-save="star" aria-pressed="${!!job.starred}"><i></i>Keep in favourites</button></div>
      <div class="lbl">Notes</div><textarea id="svNotes" rows="4" maxlength="4000" placeholder="What you worked on, what to try next" aria-label="Notes">${esc(job.notes || '')}</textarea>
      <div class="tiny muted" id="svState">Notes save as you type${isSwing ? ' and print on the report' : ''}.</div>
      <div class="lbl">Take it with you</div>
      ${isSwing ? link(ICON.doc, 'Report', 'A PDF with the read, the cue, the drill and every number', `/api/jobs/${id}/report.pdf${q}`) : ''}
      ${link(ICON.film, 'Marked-up video', 'The video with the tracking drawn on it', `/files/${id}/overlay.mp4?download=1`)}
      ${act(ICON.image, 'Picture of this frame', 'What is on the video right now, drawings included', 'picture')}
      ${isSwing ? link(ICON.table, 'Numbers', 'Every number as a spreadsheet file', `/api/jobs/${id}/numbers.csv${q}`) : link(ICON.table, 'Shots', 'Every shot as a spreadsheet file', `/api/jobs/${id}/shots.csv`)}
      <div class="lbl">Remove</div><button class="btn danger" data-save="delete">Delete this video</button>`, 'Save');
  }
  drawer.addEventListener('click', async ev => {
    if (ev.target.closest('a.saverow')) { TT.toast('Saving to your downloads'); return; }
    const b = ev.target.closest('[data-save]');
    if (!b || !saveCtx) return;
    const {job, opts} = saveCtx, what = b.dataset.save;
    try {
      if (what === 'name') {
        const out = await patchJob(job.id, {title: $('#svName').value});
        job.title = out.title; $('#svName').value = out.title; if (opts.onTitle) opts.onTitle(out.title); TT.toast('Renamed');
      } else if (what === 'star') {
        const out = await patchJob(job.id, {starred: !job.starred});
        job.starred = out.starred; b.classList.toggle('on', out.starred); b.setAttribute('aria-pressed', out.starred); TT.toast(out.starred ? 'Added to favourites' : 'Removed from favourites');
      } else if (what === 'picture') { closeDrawer(); if (deck) deck.savePicture(); }
      else if (what === 'delete') {
        if (!b.classList.contains('sure')) { b.classList.add('sure'); b.textContent = 'Tap again to delete it for good'; return; }
        await api('/api/jobs/' + job.id, {method: 'DELETE'}); closeDrawer(); TT.toast('Deleted'); location.hash = '#/';
      }
    } catch (e) { TT.toast(e.message); }
  });
  drawer.addEventListener('input', ev => {
    if (ev.target.id !== 'svNotes' || !saveCtx) return;
    const job = saveCtx.job, text = ev.target.value;
    if ($('#svState')) $('#svState').textContent = 'Saving...';
    clearTimeout(notesTimer);
    notesTimer = setTimeout(() => patchJob(job.id, {notes: text}).then(() => { job.notes = text; if ($('#svState')) $('#svState').textContent = 'Notes saved.'; })
      .catch(() => { if ($('#svState')) $('#svState').textContent = 'Could not save the notes. Check the computer is still running the app.'; }), 600);
  });

  function openHelp() {
    const part = (title, body) => `<div class="lbl">${title}</div><p class="small">${body}</p>`;
    openDrawer(`<h3>How to use Tracer Tennis</h3>
      ${part('1. Film', 'Whole body in the picture, phone held still, from the side or from behind. 60 fps or Slo-mo gives the sharpest read. Sound on, so contact can be heard.')}
      ${part('2. Upload', 'Pick Swing, Serve, Lesson or Match at the top, choose the video and tap Analyze. You can leave the page while it works.')}
      ${part('3. Read it', 'The headline is the one thing to work on first. The blue box is the cue to think about. "Show me" plays that moment in slow motion and rings the body part on the video.')}
      ${part('The grades', `${mark('strength')} <b>Strength</b> well past the target. ${mark('on_target')} <b>On target</b> inside the range. ${mark('building')} <b>Building</b> a little outside. ${mark('priority')} <b>Priority</b> clearly outside and seen directly. ${mark('not_graded')} <b>Not graded</b> depends on the shot, or could not be seen clearly.`)}
      ${part('Estimates', 'A number marked "est." is worked out in 3D from one camera, read from the racket\'s outline, or timed between frames. It is a good guide for comparing your own swings, and it is never the reason something is marked Priority.')}
      ${part('The video', 'The switches above the video turn each overlay on and off: body lines, hand path, racket tracer, racket plane, feet, angles. Use the buttons under the video to step one frame at a time or jump to contact. Pick a speed on the right.')}
      ${part('Drawing', 'Pick Line, Angle, Circle or Draw beside the video, then drag on the picture. Line shows its angle from level. Angle: drag the first side out from the corner, then the second. Tap the tool again to stop drawing. Drawings are saved with the video.')}
      ${part('Compare', 'Pick a baseline and a retest. Both play together, lined up on contact, and the page shows what moved the right way.')}
      ${part('Saving', 'Everything is saved on this computer automatically and listed under Home. The Save button gives you a PDF report, the marked-up video, a picture of the current frame and the numbers as a spreadsheet. Star a video to keep it in favourites.')}`, 'Help');
  }
  $('#help').addEventListener('click', openHelp);

  // ---------- theme ----------
  const themeBtn = $('#theme');
  function paintTheme() {
    const dark = document.documentElement.dataset.theme === 'dark';
    themeBtn.innerHTML = dark ? ICON.sun : ICON.moon;
    $('meta[name=theme-color]').setAttribute('content', dark ? '#141517' : '#e7eaf0');
  }
  themeBtn.addEventListener('click', () => {
    const dark = document.documentElement.dataset.theme !== 'dark';
    if (dark) document.documentElement.dataset.theme = 'dark'; else delete document.documentElement.dataset.theme;
    try { localStorage.setItem('tt-theme', dark ? 'dark' : 'light'); } catch (e) {}
    paintTheme(); if (deck) deck.repaint();
  });
  paintTheme();

  // ---------- routing ----------
  function route() {
    clearTimeout(pollTimer); closeDrawer(); sendMarks();
    if (deck) { deck.destroy(); deck = null; }
    view.onclick = view.onkeydown = drawer.onclick = null; saveCtx = null;
    const h = location.hash || '#/', parts = h.slice(2).split('/');
    const nav = parts[0] === 'new' ? parts[1] : parts[0] === 'compare' ? 'compare' : parts[0] === '' ? 'home' : '';
    $$('.topbar nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === nav));
    window.scrollTo(0, 0);
    if (parts[0] === 'new') return newJob(parts[1]);
    if (parts[0] === 'job') return showJob(parts[1], parts[2]);
    if (parts[0] === 'compare') return parts[1] && parts[2] ? compareView(decodeURIComponent(parts[1]), decodeURIComponent(parts[2])) : comparePick(parts[1] ? decodeURIComponent(parts[1]) : null);
    return home();
  }
  window.addEventListener('hashchange', route);

  // ---------- home ----------
  const MODE_ICON = {
    swing: '<ellipse cx="14.500" cy="8.500" rx="5" ry="6.200" transform="rotate(35 14.500 8.500)"/><path d="M10.600 13.600 4 21"/><circle cx="19.500" cy="18.500" r="1.800"/>',
    serve: '<circle cx="17.500" cy="4.500" r="1.800"/><path d="M12 21v-7l-2.500-4 4-3.500 3 4.500"/><path d="M9.500 10 6 7.500M12 14l-3 7"/>',
    compare: '<rect x="3.500" y="5" width="7" height="14" rx="1.800"/><rect x="13.500" y="5" width="7" height="14" rx="1.800"/>',
    lesson: '<rect x="5" y="4" width="14" height="17" rx="2.500"/><path d="M9 4.500h6M8.500 11l2 2 4-4.500M8.500 17h7"/>',
    match: '<rect x="4.500" y="3" width="15" height="18" rx="1.500"/><path d="M4.500 12h15M8 3v18M16 3v18M8 7.500h8M8 16.500h8M12 7.500v9"/>',
  };
  const modeIcon = k => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.800" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${MODE_ICON[k]}</svg>`;
  const KIND_NAME = {swing: 'Swing', serve: 'Serve', lesson: 'Lesson', match: 'Match'};
  const when = t => new Date(t * 1000).toLocaleString([], {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});

  let libFilter = 'all';
  async function home() {
    const mode = (kind, href, title, text, lead) => `<a class="panel mode ${lead ? 'lead' : ''}" href="${href}"><span class="ico">${modeIcon(kind)}</span><h3>${title}</h3><span class="small ink2">${text}</span></a>`;
    view.innerHTML = `
      <div class="homehead"><span class="eyebrow">Video coaching</span><h1>See your game the way a coach does</h1>
        <p class="ink2">Film on your iPhone. Get motion capture, one clear thing to fix, and the numbers behind it.</p></div>
      <div class="modes">
        ${mode('swing', '#/new/swing', 'Swing', 'Forehand, backhand or volley: feet, legs, turn, racket path and contact.', true)}
        ${mode('serve', '#/new/serve', 'Serve', 'Every part of the serve from toss to landing, for flat, slice and kick.')}
        ${mode('compare', '#/compare', 'Compare', 'Two swings side by side, lined up on contact. See what changed.')}
        ${mode('lesson', '#/new/lesson', 'Lesson', 'Every shot from a lesson: type, where it was hit, where it landed, in or out.')}
        ${mode('match', '#/new/match', 'Match', 'Singles or doubles: every player and shot, stats, positioning and strategy.')}
      </div>
      <div class="homegrid" style="margin-top:14px"><section class="panel"><h2>Saved videos<span class="tiny muted" style="font-weight:500">Kept on this computer</span></h2>
        <div class="tabs" id="libTabs" style="margin-bottom:6px">${[['all', 'All'], ['starred', 'Favourites'], ['swing', 'Swings'], ['serve', 'Serves'], ['lesson', 'Lessons'], ['match', 'Matches']].map(([k, n]) => `<button class="${k === libFilter ? 'on' : ''}" data-lib="${k}">${n}</button>`).join('')}</div>
        <div id="recent" class="muted">Loading...</div></section><div id="phone"></div></div>`;
    phoneCard();
    let jobs = [];
    const paint = () => {
      const box = $('#recent'); if (!box) return;
      const rows = jobs.filter(j => libFilter === 'all' || (libFilter === 'starred' ? j.starred : j.kind === libFilter));
      box.innerHTML = rows.length ? rows.map(j => `<div class="lrow"><button class="ibtn star ${j.starred ? 'on' : ''}" data-star="${j.id}" aria-pressed="${!!j.starred}" aria-label="${j.starred ? 'Remove from favourites' : 'Add to favourites'}" title="Favourite">${ICON.star}</button>
          <a class="grow" href="#/job/${j.id}"><b class="cut">${esc(j.title)}</b><span class="tiny muted">${when(j.created)} · ${j.status === 'done' ? 'ready' : j.status === 'error' ? 'could not be analysed' : j.status === 'queued' ? 'waiting in line' : 'analyzing'}</span></a>
          <span class="chip flat">${KIND_NAME[j.kind] || esc(j.kind)}</span>
          <button class="ibtn" data-del="${j.id}" aria-label="Delete ${esc(j.title)}" title="Delete" ${j.status === 'queued' || j.status === 'running' ? 'disabled' : ''}>${ICON.clear}</button></div>`).join('')
        : `<p class="small" style="padding:10px 0">${jobs.length ? 'Nothing here yet.' : 'Nothing yet. Pick Swing or Serve above and upload a video to start.'}</p>`;
    };
    view.onclick = async ev => {
      const tab = ev.target.closest('[data-lib]'), star = ev.target.closest('[data-star]'), del = ev.target.closest('[data-del]');
      try {
        if (tab) { libFilter = tab.dataset.lib; $$('#libTabs button').forEach(b => b.classList.toggle('on', b === tab)); paint(); }
        else if (star) { const j = jobs.find(x => x.id === star.dataset.star); j.starred = (await patchJob(j.id, {starred: !j.starred})).starred; paint(); TT.toast(j.starred ? 'Added to favourites' : 'Removed from favourites'); }
        else if (del) {
          if (!del.classList.contains('sure')) { del.classList.add('sure'); TT.toast('Tap the bin again to delete it for good'); setTimeout(() => del.classList.remove('sure'), 4000); return; }
          await api('/api/jobs/' + del.dataset.del, {method: 'DELETE'}); jobs = jobs.filter(x => x.id !== del.dataset.del); paint(); TT.toast('Deleted');
        }
      } catch (e) { TT.toast(e.message); }
    };
    try { jobs = await api('/api/jobs'); paint(); }
    catch (e) { if ($('#recent')) $('#recent').innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  }

  // On the computer: how to open the app on the phone. On the phone: how to add it to the home screen.
  async function phoneCard() {
    const onComputer = ['localhost', '127.0.0.1'].includes(location.hostname);
    const standalone = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;
    const box = $('#phone');
    if (!box) return;
    if (onComputer) {
      let info;
      try { info = await api('/api/info'); } catch (e) { return; }
      if (!$('#phone')) return;
      box.innerHTML = info.urls.length ? `<section class="panel"><h2>Use it on your iPhone</h2><div class="rowline" style="align-items:flex-start;flex-wrap:wrap">
          <img src="/api/qr" alt="QR code for ${esc(info.urls[0])}" width="132" height="132" style="border-radius:12px;background:#fff">
          <div class="grow small" style="min-width:170px"><p>1. Put the iPhone on the same Wi-Fi as this computer.</p><p>2. Point the camera at the code and open the link.</p>
            <p>3. In Safari tap Share, then <b>Add to Home Screen</b>.</p><p class="muted" style="margin-top:6px">${info.urls.map(esc).join(' or ')}</p></div></div>
          <p class="tiny muted" style="margin-top:10px">Videos are processed on this computer, so it has to be on with this app running.</p></section>`
        : `<section class="panel small muted">This computer is not on a network, so a phone cannot reach it yet.</section>`;
    } else if (!standalone && /iPhone|iPad/.test(navigator.userAgent)) {
      box.innerHTML = `<section class="panel small">Install it: tap <b>Share</b>, then <b>Add to Home Screen</b>. It then opens full screen like any other app.</section>`;
    }
  }

  // ---------- new job ----------
  function heightSelects() {
    const saved = store.get('tt-height', [5, 7]);
    const ft = [4, 5, 6].map(f => `<option ${f === saved[0] ? 'selected' : ''}>${f}</option>`).join('');
    const inch = [...Array(12).keys()].map(i => `<option ${i === saved[1] ? 'selected' : ''}>${i}</option>`).join('');
    return `<div class="rowline"><select class="field" id="ft" aria-label="feet">${ft}</select><span>ft</span><select class="field" id="in" aria-label="inches">${inch}</select><span>in</span></div>`;
  }
  const heightCm = () => { store.set('tt-height', [+$('#ft').value, +$('#in').value]); return Math.round((+$('#ft').value * 12 + +$('#in').value) * 2.54); };
  const FORM = {
    swing: ['Swing', 'Best results: whole body in view, side-on or from behind, 60 fps or slow-motion. Short clips process fastest.'],
    serve: ['Serve', 'Film from the side or from behind with the whole body and the full reach of the racket in view. One serve per clip reads best.'],
    lesson: ['Lesson', 'Prop the phone high behind the baseline with the whole court in view and leave it still. Mark the court below: in and out calls depend on it.'],
    match: ['Match or session', 'Best results: phone on a tripod or fence mount, high behind the baseline, whole court in view, not moving.'],
  };

  function newJob(kind) {
    if (!FORM[kind]) kind = 'swing';
    pickedCorners = null;
    const isMatch = kind === 'match' || kind === 'lesson', isLesson = kind === 'lesson';
    view.innerHTML = `<div class="narrow"><div class="titlebar"><div><span class="eyebrow">New video</span><h1>${FORM[kind][0]}</h1></div></div>
      <form id="f" class="panel"><p class="ink2">${FORM[kind][1]}</p>
        <label for="video">Video</label><input id="video" type="file" accept="video/*" required>
        ${isMatch ? `
          <label>Format</label>
          <div class="tabs fill" id="fmt"><button type="button" class="on" data-v="singles">Singles</button><button type="button" data-v="doubles">Doubles</button></div>
          <label>Players <span class="muted">(near side first, left to right, then far side)</span></label>
          <div id="names" class="grid2"></div>
          <div id="courtStep" class="hide">
            <label>Mark the court <span class="muted">(${isLesson ? 'needed for where shots land and in or out' : 'optional: unlocks placement, speeds, positioning, strategy'})</span></label>
            <p class="small muted" id="pickHint"></p><canvas class="pick" id="pick"></canvas>
            <div class="rowline" style="margin-top:8px"><button type="button" class="btn sm" id="redo">Start over</button><span class="small muted" id="pickState"></span></div>
          </div>` : `
          <label for="hand">Hitting hand</label>
          <select class="field" id="hand"><option value="auto">Detect automatically</option><option value="right">Right</option><option value="left">Left</option></select>
          ${kind === 'serve' ? `<label for="stype">Serve type</label>
            <select class="field" id="stype"><option value="auto">Read it from the swing</option><option value="flat">Flat</option><option value="slice">Slice</option><option value="kick">Kick</option></select>
            <p class="tiny muted" style="margin-top:6px">Pick the serve you were going for and it is graded against that serve's toss and swing. Leave it on the first choice and the app makes its best read.</p>` : ''}`}
        <label>Player height <span class="muted">(sets the scale for speeds and distances)</span></label>
        ${heightSelects()}
        <p id="msg" class="err" style="margin-top:10px"></p>
        <button id="go" class="btn primary wide" style="margin-top:8px">Analyze</button>
      </form></div>`;
    if (isMatch) {
      setupMatchForm(isLesson);
      api('/api/info').then(info => { if (info.ball_tracking === false && $('#msg')) $('#msg').textContent = 'Lesson and Match need PyTorch, which is not installed on this computer. Close Tracer Tennis and start it again to retry the install.'; }).catch(() => {});
    }
    $('#f').addEventListener('submit', async ev => {
      ev.preventDefault();
      const file = $('#video').files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('video', file); fd.append('kind', kind); fd.append('height_cm', heightCm()); fd.append('title', file.name);
      if (isMatch) {
        fd.append('format', $('#fmt .on').dataset.v);
        fd.append('names', $$('#names input').map(i => i.value.replace(/,/g, ' ')).join(','));
        if (pickedCorners && pickedCorners.length === 4) fd.append('corners', JSON.stringify(pickedCorners));
      } else { fd.append('hand', $('#hand').value); if (kind === 'serve') fd.append('serve_type', $('#stype').value); }
      $('#go').disabled = true; $('#go').textContent = 'Uploading…'; $('#msg').textContent = '';
      try {
        const r = await new Promise((resolve, reject) => {
          const x = new XMLHttpRequest();
          x.open('POST', '/api/jobs');
          x.upload.onprogress = e => { if (e.lengthComputable) $('#go').textContent = e.loaded < e.total ? `Uploading ${Math.round(100 * e.loaded / e.total)}%` : 'Starting the analysis...'; };
          x.onload = () => { let body = {}; try { body = JSON.parse(x.responseText); } catch (e) {} x.status < 300 ? resolve(body) : reject(new Error(body.detail || 'The upload did not go through. Try again.')); };
          x.onerror = () => reject(new Error('Could not reach the computer running Tracer Tennis. Check it is on and on the same Wi-Fi.'));
          x.send(fd);
        });
        location.hash = '#/job/' + r.id;
      } catch (e) { $('#msg').textContent = e.message; $('#go').disabled = false; $('#go').textContent = 'Analyze'; }
    });
  }

  function setupMatchForm(isLesson) {
    const drawNames = () => {
      const doubles = $('#fmt .on').dataset.v === 'doubles';
      const labels = doubles ? ['Near left', 'Near right', 'Far left', 'Far right'] : isLesson ? ['Near side (e.g. student)', 'Far side (e.g. coach)'] : ['Near player', 'Far player'];
      $('#names').innerHTML = labels.map(l => `<input type="text" placeholder="${l}" aria-label="${l}" maxlength="40">`).join('');
    };
    $('#fmt').addEventListener('click', ev => {
      if (!ev.target.dataset.v) return;
      $$('#fmt button').forEach(b => b.classList.toggle('on', b === ev.target));
      drawNames();
    });
    drawNames();
    const steps = ['far-left', 'far-right', 'near-right', 'near-left'];
    const canvas = $('#pick'), ctx = canvas.getContext('2d');
    let frame = null, pts = [];
    const redraw = () => {
      if (!frame) return;
      ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
      ctx.lineWidth = Math.max(2, canvas.width / 300); ctx.strokeStyle = '#ffd60a'; ctx.fillStyle = '#ffd60a';
      if (pts.length > 1) { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0] * canvas.width, p[1] * canvas.height) : ctx.moveTo(p[0] * canvas.width, p[1] * canvas.height)); if (pts.length === 4) ctx.closePath(); ctx.stroke(); }
      pts.forEach(p => { ctx.beginPath(); ctx.arc(p[0] * canvas.width, p[1] * canvas.height, canvas.width / 90, 0, 7); ctx.fill(); });
      $('#pickHint').textContent = pts.length < 4 ? `Tap the ${steps[pts.length]} corner of the doubles court (outer lines).` : 'Court marked. It will be snapped to the painted lines.';
      $('#pickState').textContent = `${pts.length}/4`;
      pickedCorners = pts.length === 4 ? pts : null;
    };
    canvas.addEventListener('click', ev => {
      if (pts.length >= 4 || !frame) return;
      const r = canvas.getBoundingClientRect();
      pts.push([(ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height]);
      redraw();
    });
    $('#redo').addEventListener('click', () => { pts = []; redraw(); });
    $('#video').addEventListener('change', () => {
      const file = $('#video').files[0];
      pts = []; frame = null; pickedCorners = null;
      if (!file) return;
      const v = document.createElement('video');
      v.muted = true; v.playsInline = true; v.preload = 'auto'; v.src = URL.createObjectURL(file);
      const grab = () => {
        if (!v.videoWidth) return;
        canvas.width = Math.min(v.videoWidth, 1280); canvas.height = Math.round(canvas.width * v.videoHeight / v.videoWidth);
        const off = document.createElement('canvas'); off.width = canvas.width; off.height = canvas.height;
        off.getContext('2d').drawImage(v, 0, 0, off.width, off.height);
        frame = off; $('#courtStep').classList.remove('hide'); redraw(); URL.revokeObjectURL(v.src);
      };
      v.addEventListener('loadeddata', () => { v.currentTime = Math.min(0.5, (v.duration || 1) / 2); });
      v.addEventListener('seeked', grab, {once: true});
      v.addEventListener('error', () => { $('#courtStep').classList.add('hide'); });
      v.play().then(() => v.pause()).catch(() => {});
    });
  }

  // ---------- job page ----------
  async function showJob(id, pick) {
    view.innerHTML = '<p class="muted">Loading…</p>';
    const tick = async () => {
      let job;
      try { job = await api('/api/jobs/' + id); } catch (e) { finished = true; if (location.hash.includes(id)) view.innerHTML = `<div class="narrow"><section class="panel"><p class="err">${esc(e.message)}</p><p style="margin-top:10px"><a class="btn" href="#/">Back to Home</a></p></section></div>`; return; }
      if (!location.hash.includes(id)) { finished = true; return; }        // the user moved to another page while this was loading
      if (job.status === 'done') { finished = true; return job.kind === 'swing' || job.kind === 'serve' ? swingReport(job, pick) : matchReport(job); }
      if (job.status === 'error') { finished = true; view.innerHTML = `<div class="narrow"><div class="titlebar"><h1>${esc(job.title)}</h1></div><section class="panel"><p class="err">${esc(job.error)}</p><p style="margin-top:10px"><a class="btn" href="#/new/${job.kind}">Try another video</a></p></section></div>`; return; }
      const p = Math.round((job.progress || 0) * 100), solo = job.kind === 'swing' || job.kind === 'serve';
      const body = !solo ? 'players, ball and shots' : p < 60 ? 'the body in every frame (step 1 of 3)' : p < 80 ? 'the racket (step 2 of 3)' : 'the last details and drawing the video (step 3 of 3)';
      view.innerHTML = `<div class="narrow"><div class="titlebar"><div><span class="eyebrow">${job.status === 'queued' ? 'Waiting in line' : 'Analyzing'}</span><h1>${esc(job.title)}</h1></div></div>
        <section class="panel"><div class="rowline spread" style="margin-bottom:8px"><b>${job.status === 'queued' ? 'Waiting for the video ahead of it' : 'Tracking ' + body}</b><span class="num ink2">${p}%</span></div>
        <div class="progress"><i style="width:${p}%"></i></div><p class="small muted" style="margin-top:10px">You can leave this page and come back.</p></section></div>`;
    };
    let finished = false;                       // keep asking only while the video is still being analysed
    const loop = async () => { await tick(); if (!finished && location.hash.includes(id)) pollTimer = setTimeout(loop, 1500); };
    await loop();
  }

  function lineChart(series, marks, opts = {}) {
    // series: [{name, color, t:[], y:[], dash}], marks: [{t, label}]
    const W = 340, H = (opts.height || 150) + 20, pad = 26;
    const all = series.flatMap(s => s.t), t0 = opts.t0 ?? Math.min(...all), t1 = opts.t1 ?? Math.max(...all);
    const inside = (s, i) => s.t[i] >= t0 - 1e-6 && s.t[i] <= t1 + 1e-6 && s.y[i] !== null;
    const ymax = Math.max(1, ...series.flatMap(s => s.y.filter((v, i) => inside(s, i)))) * 1.08;
    const X = t => pad + (t - t0) / Math.max(t1 - t0, 1e-6) * (W - pad - 8), Y = v => H - 18 - v / ymax * (H - 36);
    const paths = series.map(s => {
      let d = '', pen = false;
      s.y.forEach((v, i) => { if (!inside(s, i)) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(s.t[i]).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; });
      return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.200" stroke-linejoin="round" stroke-linecap="round" ${s.dash ? 'stroke-dasharray="5 4" opacity=".75"' : ''}/>`;
    }).join('');
    const lines = marks.map(m => `<line x1="${X(m.t)}" x2="${X(m.t)}" y1="24" y2="${H - 18}" stroke="currentColor" stroke-opacity=".28" stroke-dasharray="3 3"/>
      <text x="${X(m.t)}" y="${H - 4}" font-size="11" text-anchor="middle" fill="currentColor" opacity=".65">${esc(m.label)}</text>`).join('');
    let lx = pad;
    const legend = series.map(s => { const x = lx; lx += 22 + s.name.length * 6.200; return `<line x1="${x}" x2="${x + 12}" y1="9" y2="9" stroke="${s.color}" stroke-width="2.600" stroke-linecap="round" ${s.dash ? 'stroke-dasharray="4 3"' : ''}/><text x="${x + 16}" y="13" font-size="11" fill="currentColor" opacity=".8">${esc(s.name)}</text>`; }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.label || 'speed over time')}" style="width:100%;height:auto"><text x="2" y="${Y(ymax / 1.08) + 4}" font-size="11" fill="currentColor" opacity=".65">${(ymax / 1.08).toFixed(0)}</text>${lines}${paths}${legend}</svg>`;
  }

  // ---------- swing and serve read ----------
  const SHOW_AT = {shoulder_turn: 'backswing_end', separation: 'backswing_end', back_foot_angle: 'backswing_end', knee_bend_dom: 'backswing_end',
    prep_time: 'backswing_end', racket_drop: 'forward_swing', follow_length: 'finish', finish_height: 'finish', back_foot_pivot: 'finish',
    lead_knee_back: 'backswing_end', trail_knee_back: 'backswing_end', racket_angle_back: 'backswing_end', racket_angle_low: 'forward_swing', racket_lag: 'forward_swing'};
  const SERVE_AT = {toss: 'toss', trophy: 'trophy', drive: 'racket_drop', contact: 'contact', finish: 'finish'};
  const PHASE_ORDER = ['Preparation', 'Loading', 'Feet', 'Legs', 'Forward swing', 'Racket', 'Contact', 'Through the ball', 'Follow-through'];
  const PHASES = [['takeback', 'Ready'], ['backswing_end', 'Racket back'], ['forward_swing', 'Swing'], ['contact', 'Contact'], ['finish', 'Finish']];
  function momentOf(s, key) {
    if (SHOW_AT[key]) return SHOW_AT[key];
    const cat = ((s.coaching || {}).categories || []).find(c => c.keys.includes(key));
    return s.serve && cat && SERVE_AT[cat.id] ? SERVE_AT[cat.id] : 'contact';
  }
  const swingName = s => s.serve && ['flat', 'slice', 'kick'].includes(s.serve.type) ? cap(s.serve.type) + ' serve' : cap(s.stroke) + (s.two_handed ? ', two-handed' : '');
  const heightTxt = m => { const inches = Math.round(m * 100 / 2.540); return `${Math.floor(inches / 12)} ft ${inches % 12} in`; };

  function birdsEye(td, which, grades, byKey) {
    // Schematic seen from straight above. Up the page is toward the target; the chest side is to the right.
    const f = td[which], S = 160, W = 300, H = 290;
    const mid = [(f.feet[0].pos[0] + f.feet[1].pos[0]) / 2, (f.feet[0].pos[1] + f.feet[1].pos[1]) / 2];
    const gap = Math.hypot(f.feet[0].pos[0] - f.feet[1].pos[0], f.feet[0].pos[1] - f.feet[1].pos[1]);
    const spread = gap < 0.42 ? 0.42 / Math.max(gap, 0.05) : 1;      // keep the two shoes from overlapping when the feet are close
    const feet = f.feet.map(ft => ({...ft, pos: [mid[0] + (ft.pos[0] - mid[0]) * spread, mid[1] + (ft.pos[1] - mid[1]) * spread]}));
    const X = x => W / 2 + 8 + (x - mid[0]) * S, Y = y => H / 2 + 18 - (y - mid[1]) * S;
    const col = k => grades[k] && grades[k] !== 'not_graded' ? `var(--g-${grades[k]})` : 'var(--ink2)';
    const num = k => byKey[k] && typeof byKey[k].value === 'number' ? byKey[k].value : null;
    const shoe = ft => {
      const key = ft.front ? 'front_foot_angle' : (which === 'set' ? 'back_foot_angle' : 'back_foot_pivot');
      const deg = Math.atan2(ft.dir[0], ft.dir[1]) * 180 / Math.PI, cx = X(ft.pos[0]), cy = Y(ft.pos[1]);
      const off = Math.round(Math.acos(Math.max(-1, Math.min(1, ft.dir[1]))) * 180 / Math.PI);
      const left = ft.pos[0] < mid[0] || (ft.pos[0] === mid[0] && !ft.front);
      return `<g transform="translate(${cx.toFixed(1)} ${cy.toFixed(1)}) rotate(${deg.toFixed(1)}) scale(.74)">
          <path d="M-12 26 Q-14 -6 -9 -24 Q0 -40 9 -24 Q14 -6 12 26 Q0 33 -12 26 Z" fill="${col(key)}"/>
          <path d="M-7 -22 Q0 -33 7 -22" fill="none" stroke="#fff" stroke-opacity=".85" stroke-width="2.500" stroke-linecap="round"/></g>
        <text x="${(cx + (left ? -30 : 30)).toFixed(1)}" y="${(cy + 3).toFixed(1)}" font-size="11.500" font-weight="650" text-anchor="${left ? 'end' : 'start'}" fill="currentColor">${ft.front ? 'Front foot' : 'Back foot'}</text>
        <text x="${(cx + (left ? -30 : 30)).toFixed(1)}" y="${(cy + 17).toFixed(1)}" font-size="10.500" text-anchor="${left ? 'end' : 'start'}" fill="currentColor" opacity=".65">${off}° off target</text>`;
    };
    const turn = num(which === 'set' ? 'shoulder_turn' : 'shoulders_at_contact');
    let chest = '';
    if (turn !== null) {
      const a = turn * Math.PI / 180, nx = Math.sin(a), ny = Math.cos(a), cx = X(mid[0]), cy = Y(mid[1] + 0.03), half = 33;
      chest = `<line x1="${cx - ny * half}" y1="${cy - nx * half}" x2="${cx + ny * half}" y2="${cy + nx * half}" stroke="currentColor" stroke-opacity=".8" stroke-width="6.500" stroke-linecap="round"/>
        <line x1="${cx}" y1="${cy}" x2="${cx + nx * 24}" y2="${cy - ny * 24}" stroke="currentColor" stroke-opacity=".8" stroke-width="3" stroke-linecap="round"/>
        <text x="${cx + nx * 32 + (nx >= 0 ? 2 : -2)}" y="${cy - ny * 32 + 4}" font-size="10.500" font-weight="600" text-anchor="${nx >= 0.300 ? 'start' : nx <= -0.300 ? 'end' : 'middle'}" fill="currentColor" opacity=".7">chest</text>`;
    }
    let ball = '';
    const ahead = num('contact_in_front'), spacing = num('contact_spacing');
    if (which === 'contact' && ahead !== null && spacing !== null) {
      const front = feet.find(x => x.front), bx = X(Math.max(mid[0] + spacing / 100, front.pos[0] + 0.240)), by = Y(mid[1] + (front.pos[1] - mid[1]) * 0.500 + ahead / 100);
      ball = `<circle cx="${bx}" cy="${by}" r="8.500" fill="#d8ee3a" stroke="#7d8f00" stroke-width="1.200"/>
        <text x="${bx}" y="${by - 14}" font-size="11" font-weight="650" text-anchor="middle" fill="currentColor">Contact</text>`;
    }
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="feet, chest and contact point seen from above" style="width:100%;max-width:320px;height:auto;margin:0 auto">
      <line x1="22" y1="${H - 16}" x2="22" y2="34" stroke="var(--blue)" stroke-width="2.200" stroke-dasharray="5 5"/><path d="M22 16 L29.500 33 H14.500 Z" fill="var(--blue)"/>
      <text x="35" y="29" font-size="11" font-weight="650" fill="var(--blue)">To target</text>${chest}${feet.map(shoe).join('')}${ball}</svg>`;
  }

  const SURE = {estimate: 'Estimate', low: 'Not seen clearly'};
  const sureChip = level => SURE[level] ? `<span class="chip flat" title="${level === 'estimate' ? 'A guide, not an exact number' : 'Left ungraded'}">${SURE[level]}</span>` : '';
  // what to ring on the video for each number
  const SPOT_RULES = [
    [/^(contact_|extension|speed_carried|swing_path|follow_length|finish_height|hand_speed|serve_contact_|serve_swing_up|serve_follow|serve_hand)/, ['hand']],
    [/elbow/, ['elbow']], [/^serve_toss/, ['toss_hand']], [/^(separation|serve_coil)/, ['shoulders', 'hips']],
    [/shoulder/, ['shoulders']], [/^(trunk_lean|chest_lead|serve_trunk)/, ['spine']], [/^head_/, ['head']],
    [/^(weight_|balance|hip_|serve_rise|serve_into)/, ['hips']], [/^(lead_|serve_knee_lead|serve_leg_drive_lead)/, ['lead_knee']],
    [/^(trail_|serve_knee_trail|serve_leg_drive_trail)/, ['trail_knee']], [/^(knee_bend|leg_drive)/, ['dom_knee']],
    [/^(front_foot|step_in)/, ['front_foot']], [/^back_foot/, ['back_foot']], [/^(stance|serve_stance|serve_feet)/, ['feet']],
    [/^(racket_|approach_angle|swing_plane|serve_racket)/, ['racket']],
  ];
  const spotFor = m => ({parts: (SPOT_RULES.find(([re]) => re.test(m.key)) || [0, ['hand']])[1],
    label: `${m.label.split(' (')[0].split(':')[0]}${typeof m.value === 'number' ? ' ' + fmt(m.value) + (m.unit === 'deg' ? '°' : m.unit ? ' ' + m.unit : '') : ''}`});
  const cueBlock = f => `<div class="focus"><div class="lbl">The focus</div><b>${esc(f.cue)}</b></div>
    ${f.alts && f.alts.length ? `<div class="alts"><span class="tiny muted">Or say it this way</span>${f.alts.map(a => `<span class="chip">${esc(a)}</span>`).join('')}</div>` : ''}
    ${f.check ? `<p class="check"><span class="ck">${ICON.check}</span><span><b>You got it when:</b> ${esc(f.check)}</span></p>` : ''}`;

  function numberDrawer(s, m, c) {
    const g = (c && c.grades[m.key]) || 'not_graded', fix = c && c.fixes.find(f => f.key === m.key), win = c && c.strengths.find(w => w.key === m.key);
    const [name, ...rest] = m.label.split(' (');
    return `<div style="margin-top:14px" class="rowline wrapline">${gradeChip(g)}<span class="chip flat">${esc(m.phase)}</span>${sureChip(m.confidence)}</div>
      <h3>${esc(name)}</h3>${rest.length ? `<p class="small muted">${esc(rest.join(' (').replace(/\)$/, ''))}</p>` : ''}
      <div class="valrow"><div class="val num">${valTxt(m.value, m.unit)}</div>${m.typical ? `<div class="target">Target<b>${esc(m.typical)}${m.unit === 'deg' ? '°' : ''}</b></div>` : ''}</div>
      ${meter(c && c.meters[m.key], m.value)}
      ${fix ? `<div class="lbl">What we saw</div><p>${esc(fix.saw)}</p><div class="lbl">Why it matters</div><p>${esc(fix.why)}</p>
          ${cueBlock(fix)}<div class="lbl">Try this</div><p>${esc(fix.drill)}</p>`
        : `${win ? `<div class="lbl">What we saw</div><p>${esc(win.text)}</p>` : ''}${m.note ? `<div class="lbl">What it means</div><p>${esc(m.note)}</p>` : ''}`}
      ${m.seen ? `<div class="lbl">How sure is this</div><p class="small">${esc(m.seen)}</p>` : ''}
      ${g === 'not_graded' && m.confidence !== 'low' ? '<p class="small muted" style="margin-top:14px">This number is shown for reference. It is not graded because the right value depends on the ball and the shot you were hitting.</p>' : ''}
      <p style="margin-top:18px"><button class="btn primary" data-show="${m.key}">Show me in slow motion</button></p>`;
  }

  async function swingReport(job, pick) {
    const r = job.report, id = job.id, isServe = job.kind === 'serve';
    let tracks = null, others = [];
    if (r.files && r.files.tracks) try { tracks = await api(`/files/${id}/${r.files.tracks}`); } catch (e) {}
    try { others = await api('/api/swings'); } catch (e) {}
    const src = `/files/${id}/${tracks ? r.files.clean : 'overlay.mp4'}`, fps = tracks ? tracks.fps : r.video.fps;
    if (!r.swings.length) {
      view.innerHTML = `<div class="titlebar"><h1>${esc(job.title)}</h1></div><section class="panel"><p>No swing was found in this clip. The player was tracked, but the hand never moved fast enough to count as a stroke.</p><div id="deck" style="margin-top:14px"></div></section>`;
      deck = TT.deck($('#deck'), {stages: [{src, fps, tracks, series: r.series}], contact: false});
      return;
    }
    let current = Math.max(0, r.swings.findIndex(x => String(x.index) === String(pick))), fixAt = 0, eye = 'contact', filter = 'All';

    const draw = () => {
      if (deck) { deck.destroy(); deck = null; }
      const s = r.swings[current], c = s.coaching || null, byKey = Object.fromEntries(s.metrics.map(m => [m.key, m]));
      const grades = (c && c.grades) || {}, phases = s.phases || PHASES, ref = `${id}:${s.index}`;
      const top = c && c.fixes[0], hit = c ? c.counts.on_target : 0, sure = (c && c.confidence) || {};
      const racket = r.series.racket_head_speed;
      const chartSeries = [{name: 'Hand, mph', color: 'var(--ink2)', t: r.series.t, y: r.series.hand_speed.map(v => v * MPH)}];
      if (racket) chartSeries.push({name: 'Racket head, mph', color: 'var(--blue)', t: r.series.t, y: racket.map(v => v === null ? null : v * MPH)});
      const marks = (isServe ? [['trophy', 'trophy'], ['contact', 'contact']] : [['backswing_end', 'racket back'], ['contact', 'contact']]).map(([k, label]) => ({t: s.times[k], label})).filter(m => m.t !== undefined);
      const seqMax = Math.max(...(s.sequence || []).map(q => Math.abs(q.ms_before_contact)), 1);
      const kf = phases.slice(1).map(([k, label]) => [k, label, r.keyframes[`${s.index}:${k}`]]).filter(x => x[2]);
      const phaseNames = [...new Set(s.metrics.map(m => m.phase))].sort((a, b) => (PHASE_ORDER.indexOf(a) + 1 || 99) - (PHASE_ORDER.indexOf(b) + 1 || 99));
      const ordered = [...s.metrics].sort((a, b) => phaseNames.indexOf(a.phase) - phaseNames.indexOf(b.phase));
      const stance = byKey.stance_type, step = byKey.step_in;
      const audio = (s.contact_source || '').includes('audio');

      view.innerHTML = `
        <div class="titlebar"><div><span class="eyebrow">${isServe ? 'Serve read' : 'Swing read'}</span><h1>${esc(swingName(s))}<span class="when"><span data-title>${esc(job.title)}</span> · ${when(job.created)}</span></h1></div>
          <div class="acts"><button class="btn" data-open-save>${ICON.save}Save</button><a class="btn" href="#/new/${job.kind}">New video</a><a class="btn primary" href="#/compare/${ref}">Compare</a></div></div>
        ${r.swings.length > 1 ? `<div class="tabs" style="margin-bottom:14px">${r.swings.map((x, i) => `<button class="${i === current ? 'on' : ''}" data-swing="${i}">${i + 1}. ${esc(swingName(x))}</button>`).join('')}</div>` : ''}
        <div class="cols">
          <div class="stack left">
            ${c ? `<section class="panel"><h2>${isServe ? 'Serve read' : 'Swing read'}</h2><p class="tiny muted" style="margin:-4px 0 10px">Graded against coaching target ranges for ${isServe && s.serve ? 'a ' + esc(s.serve.type) + ' serve' : 'a ' + esc(s.stroke)}.</p>
              <div class="dialrow">${dial(hit, c.counts.graded)}${countsBlock(c.counts)}</div>
              ${c.counts.estimates || c.counts.unclear ? `<p class="tiny muted" style="margin-top:10px">${c.counts.estimates ? `${c.counts.estimates} of these are estimates: good guides, but never the reason something is marked Priority. ` : ''}${c.counts.unclear ? `${c.counts.unclear} could not be seen clearly and ${c.counts.unclear === 1 ? 'is' : 'are'} left ungraded.` : ''}</p>` : ''}</section>
              <section class="panel first" id="first"></section>
              <section class="panel"><h2>${isServe ? 'Parts of the serve' : 'Parts of the swing'}</h2>${c.categories.map(cat => `<div class="part"><b style="font-weight:600">${esc(cat.name)}</b><span class="small ink2 num">${cat.keys.filter(k => ['on_target', 'strength'].includes(grades[k])).length} of ${cat.checks} on target</span>
                <div class="pips">${cat.keys.map(k => `<i style="background:var(--g-${grades[k] || 'not_graded'})" title="${esc((byKey[k] || {}).label || k)}"></i>`).join('')}</div></div>`).join('')}</section>` : `<section class="panel"><p>This report was made with an older version. Upload the video again to get the full read.</p></section>`}
            ${isServe && s.serve ? serveTypeCard(s, byKey) : ''}
            <section class="panel"><h2>Speed through the ${isServe ? 'serve' : 'swing'}</h2>${lineChart(chartSeries, marks)}<p class="tiny muted" style="margin-top:6px">A good swing is still gaining speed at the contact line and holds it just after.</p></section>
            ${s.sequence && s.sequence.length ? `<section class="panel chain"><h2>Order of the swing</h2><p class="tiny muted" style="margin:-4px 0 8px">When each part reached top speed before contact. It should run hips, shoulders, arm, hand.</p>
              ${s.sequence.map(q => `<div class="rowline"><span style="width:76px">${esc(q.segment)}</span><div class="meter"><span class="zone" style="width:${Math.max(3, Math.abs(q.ms_before_contact) / seqMax * 100).toFixed(0)}%"></span></div><span class="num ink2" style="width:58px;text-align:right">${q.ms_before_contact} ms</span></div>`).join('')}</section>` : ''}
          </div>

          <div class="stack mid">
            <section class="panel hero">
              <div class="say">${c ? gradeChip(LIGHT[c.light] || 'not_graded') : ''} <span class="chip flat">${esc(cap(s.hand))}-handed</span>${stance && !isServe ? ` <span class="chip flat">${esc(cap(String(stance.value)))} stance</span>` : ''}
                <h1>${esc(top ? top.problem || top.title : c ? 'Nothing to fix on this one.' : swingName(s))}</h1>
                <p class="cost">${esc(top ? top.why : c ? 'Every checkpoint we grade came out on target. Film another to see if it holds.' : '')}</p>
                ${c && c.context ? `<p class="small muted" style="margin-top:8px">${esc(c.context)}</p>` : ''}
                ${c && c.strengths.length ? `<div class="working"><h2 style="margin-bottom:6px">Already working</h2>${c.strengths.slice(0, 3).map(w => `<div class="w"><span class="ck">${ICON.check}</span><span>${esc(w.text)}</span><span class="v num">${typeof w.value === 'number' ? fmt(w.value) + unitTxt(w.unit) : ''}</span></div>`).join('')}</div>` : ''}
                <div class="statusline"><i class="${audio ? '' : 'est'}"></i>${audio ? 'Contact confirmed from the sound of the ball' : 'Contact estimated from the swing. No clear ball sound was found.'}</div>
              </div>
              ${kf.length ? `<div class="moments"><h2 style="margin-bottom:8px">Key moments</h2><div class="strip">${kf.map(([k, label, f]) => `<figure data-freeze="${s.frames[k]}"><img loading="lazy" src="/files/${id}/${esc(f)}" alt="${esc(label)}"><figcaption>${esc(label)}</figcaption></figure>`).join('')}</div></div>` : ''}
              <div class="vid"><div id="deck"></div>
                <div class="phasebar">${phases.map(([k, label]) => `<button class="btn sm" data-freeze="${s.frames[k]}">${esc(label)}</button>`).join('')}</div>
                <div class="hud"><div class="raised"><span class="eyebrow">Moment</span><b id="hudPhase">Ready</b></div><div class="raised"><span class="eyebrow">Hand</span><b class="num" id="hudHand">0 mph</b></div><div class="raised"><span class="eyebrow">Racket</span><b class="num" id="hudRacket">–</b></div></div>
                ${tracks ? '' : '<p class="tiny muted" style="margin-top:8px">This clip was analysed with an older version, so its overlays are part of the video. Upload it again to switch them on and off.</p>'}
              </div>
            </section>
            <section class="panel"><h2>All numbers<span class="tiny muted" style="font-weight:500">Tap a row for what it means</span></h2>
              <div class="tabs" id="filter" style="margin-bottom:8px">${['All', ...phaseNames].map(p => `<button class="${p === filter ? 'on' : ''}" data-filter="${esc(p)}">${esc(p)}</button>`).join('')}</div>
              <div class="scroll"><table class="numbers"><thead><tr><th></th><th>Number</th><th>Grade</th><th>This ${isServe ? 'serve' : 'swing'}</th><th class="t">Target</th><th class="m"></th></tr></thead><tbody id="rows"></tbody></table></div></section>
          </div>

          <div class="stack right">
            <section class="panel"><h2>Swings<a class="btn sm" href="#/new/${job.kind}">New</a></h2><div class="list">${others.slice(0, 7).map(o => `<a href="#/job/${o.job}/${o.index}" class="${o.ref === ref ? 'on' : ''}">
              ${o.keyframe ? `<img class="thumb" loading="lazy" src="/files/${o.job}/${esc(o.keyframe)}" alt="">` : '<span class="thumb"></span>'}
              <span class="grow"><b class="cut" style="display:block;font-weight:600">${esc(o.name)}</b><span class="tiny muted cut" style="display:block">${esc(o.title)}</span></span><span class="dot light-${o.light}"></span></a>`).join('') || '<p class="small muted">Analysed swings show up here.</p>'}</div></section>
            ${s.topdown && s.topdown.contact ? `<section class="panel"><h2>Feet from above</h2><div class="tabs fill" id="eye"><button data-eye="set">Racket back</button><button data-eye="contact">Contact</button></div>
              <div id="eyeSvg" style="margin-top:6px"></div><p class="small">${stance ? `<b>${esc(cap(String(stance.value)))} stance.</b> ${esc(stance.note)}` : ''}${step && typeof step.value === 'number' && step.value >= 8 ? ` You stepped ${Math.round(step.value / 2.540)} inches toward the target.` : ''}</p></section>` : ''}
            ${r.checks && r.checks.length ? `<section class="panel"><h2>Video check</h2><div class="checks">${r.checks.map(k => `<div class="chk"><span>${mark({good: 'strength', warn: 'building', bad: 'priority'}[k.status])}</span><div><b>${esc(k.label)}</b><p class="small ink2">${esc(k.text)}</p>${k.tip && k.status !== 'good' ? `<p class="small"><b>Next time:</b> ${esc(k.tip)}</p>` : ''}</div></div>`).join('')}</div></section>` : ''}
            <section class="panel"><div class="rowline"><span class="avatar">${s.hand === 'left' ? 'L' : 'R'}</span><div class="grow"><b>${esc(cap(s.hand))}-handed</b><div class="tiny muted">${heightTxt(r.player.height_m)}, as entered</div></div></div>
              <div class="facts"><div class="groove"><span class="eyebrow">Camera</span><b class="num">${Math.round(r.player.camera_distance_m * 3.281)} ft away</b></div><div class="groove"><span class="eyebrow">Video</span><b class="num">${Math.round(r.video.fps)} fps</b></div>
                <div class="groove"><span class="eyebrow">Racket seen</span><b class="num">${r.player.racket_seen_pct === null || r.player.racket_seen_pct === undefined ? 'no' : r.player.racket_seen_pct + '%'}</b></div><div class="groove"><span class="eyebrow">Body tracked</span><b class="num">${Math.round(100 * r.video.pose_frames_detected / r.video.frames)}%</b></div></div>
              <details style="margin-top:12px"><summary class="small" style="cursor:pointer;font-weight:600">How accurate is this?</summary><div class="tiny muted" style="margin-top:6px;display:grid;gap:6px">${r.caveats.map(x => `<p>${esc(x)}</p>`).join('')}</div></details></section>
          </div>
        </div>`;

      deck = TT.deck($('#deck'), {
        stages: [{src, fps, tracks, swings: r.swings, series: r.series, zeroFrame: s.frames.contact, marks: (job.marks || [])[0]}], startFrame: s.frames.takeback,
        name: job.title.replace(/\.[a-z0-9]{2,4}$/i, ''), onMarks: marks => saveMarks(job, marks),
        onFrame(i) {
          const hp = $('#hudPhase'); if (!hp) return;
          let phase = phases[0][1];
          for (const [k, label] of phases) if (i >= s.frames[k]) phase = label;
          hp.textContent = phase;
          $('#hudHand').textContent = Math.round((r.series.hand_speed[i] || 0) * MPH) + ' mph';
          $('#hudRacket').textContent = racket && racket[i] !== null && racket[i] !== undefined ? Math.round(racket[i] * MPH) + ' mph' : '–';
        },
      });
      const show = key => { closeDrawer(); if (tracks && byKey[key]) deck.spot(spotFor(byKey[key])); deck.showAt(s.frames[momentOf(s, key)] ?? s.frames.contact); };

      const paintFirst = () => {
        const box = $('#first'); if (!box) return;
        if (!c.fixes.length) { box.innerHTML = `<h2>Work on first</h2><p>Nothing needs fixing on this one. Every graded number is on target.</p>`; return; }
        const f = c.fixes[fixAt], m = byKey[f.key] || f;
        box.innerHTML = `<div class="head"><h2 style="margin:0">Work on first</h2><div class="pager"><button class="ibtn" data-fix="-1" aria-label="Previous" ${fixAt === 0 ? 'disabled' : ''}>${ICON.left}</button><span class="num">${fixAt + 1} of ${c.fixes.length}</span><button class="ibtn" data-fix="1" aria-label="Next" ${fixAt === c.fixes.length - 1 ? 'disabled' : ''}>${ICON.right}</button></div></div>
          <div class="rowline" style="flex-wrap:wrap;gap:6px"><span class="chip flat">${esc(f.category)}</span>${gradeChip(f.grade)}${f.situational ? '<span class="chip flat">Partly the ball you got</span>' : ''}${sureChip(f.confidence)}</div>
          <h3 style="margin-top:10px">${esc(f.label.split(' (')[0])}</h3>
          <div class="valrow"><div class="val num">${valTxt(f.value, f.unit)}</div>${f.typical ? `<div class="target">Target<b>${esc(f.typical)}${f.unit === 'deg' ? '°' : ''}</b></div>` : ''}</div>
          ${meter(c.meters[f.key], f.value)}
          <p style="margin-top:10px">${esc(f.saw)}</p>
          ${cueBlock(f)}
          <div class="two"><button class="btn" data-show="${f.key}">Show me</button><button class="btn" data-drill="${f.key}">Drill</button></div>`;
      };
      const paintRows = () => {
        $('#rows').innerHTML = ordered.filter(m => filter === 'All' || m.phase === filter).map(m => {
          const [name, ...rest] = m.label.split(' (');
          return `<tr class="rowbtn" data-key="${m.key}" tabindex="0"><td class="phc"><span class="ph num">${phaseNames.indexOf(m.phase) + 1}</span></td>
            <td class="name"><b>${esc(name)}</b><span>${m.confidence === 'low' ? esc((m.seen || '').replace(/^Not graded: /, 'Not seen clearly: ')) : esc(m.phase) + (rest.length ? ' · ' + esc(rest.join(' (').replace(/\)$/, '')) : '')}</span></td>
            <td>${gradeChip(grades[m.key] || 'not_graded')}</td><td class="v num ${m.confidence === 'low' ? 'dim' : ''}">${valTxt(m.value, m.unit)}${m.confidence === 'estimate' ? '<span class="est" title="An estimate: a guide, not an exact number">est.</span>' : ''}</td><td class="t">${esc(m.typical || '')}</td><td class="m">${meter(c && c.meters[m.key], m.value)}</td></tr>`;
        }).join('');
      };
      const paintEye = () => { if (!$('#eyeSvg')) return; $('#eyeSvg').innerHTML = birdsEye(s.topdown, eye, grades, byKey); $$('#eye button').forEach(b => b.classList.toggle('on', b.dataset.eye === eye)); };
      if (c) paintFirst();
      paintRows(); paintEye();

      view.onclick = ev => {
        const el = ev.target.closest('[data-swing],[data-fix],[data-show],[data-drill],[data-freeze],[data-filter],[data-eye],[data-key],[data-open-save]');
        if (!el) return;
        if (el.dataset.swing) { current = +el.dataset.swing; fixAt = 0; filter = 'All'; draw(); }
        else if (el.dataset.fix) { fixAt = Math.max(0, Math.min(c.fixes.length - 1, fixAt + +el.dataset.fix)); paintFirst(); }
        else if (el.dataset.show) show(el.dataset.show);
        else if (el.dataset.drill) { const f = c.fixes.find(x => x.key === el.dataset.drill); openDrawer(`<div style="margin-top:14px">${gradeChip(f.grade)} <span class="chip flat">${esc(f.category)}</span></div><h3>${esc(f.title)}</h3>
          <div class="lbl">What we saw</div><p>${esc(f.saw)}</p><div class="lbl">Why it matters</div><p>${esc(f.why)}</p>${cueBlock(f)}${f.cue_more ? `<div class="lbl">In more words</div><p>${esc(f.cue_more)}</p>` : ''}<div class="lbl">The drill</div><p>${esc(f.drill)}</p>
          <p style="margin-top:18px"><button class="btn primary" data-show="${f.key}">Show me in slow motion</button></p>`, 'Drill'); }
        else if (el.dataset.openSave !== undefined) openSave(job, {swing: s.index, onTitle: t => { job.title = t; $$('[data-title]').forEach(x => { x.textContent = t; }); }});
        else if (el.dataset.freeze) { deck.spot(null); deck.freeze(+el.dataset.freeze); if (el.tagName === 'FIGURE') deck.el.scrollIntoView({behavior: 'smooth', block: 'nearest'}); }
        else if (el.dataset.filter) { filter = el.dataset.filter; $$('#filter button').forEach(b => b.classList.toggle('on', b === el)); paintRows(); }
        else if (el.dataset.eye) { eye = el.dataset.eye; paintEye(); }
        else if (el.dataset.key) openDrawer(numberDrawer(s, byKey[el.dataset.key], c));
      };
      view.onkeydown = ev => { if (ev.key === 'Enter' && ev.target.dataset && ev.target.dataset.key) openDrawer(numberDrawer(s, byKey[ev.target.dataset.key], c)); };
      drawer.onclick = ev => { const b = ev.target.closest('[data-show]'); if (b) show(b.dataset.show); };
    };
    draw();
  }

  function serveTypeCard(s, byKey) {
    const sv = s.serve, T = sv.targets || {}, types = ['flat', 'slice', 'kick'].filter(t => T[t]);
    const rows = [['front', 'Contact into the court', 'serve_contact_front', 'cm'], ['side', 'Contact out to the side', 'serve_contact_side', 'cm'], ['up', 'Swing up into the ball', 'serve_swing_up', '°']];
    const range = (v, u) => v ? `${v[0]} to ${v[1]}${u === '°' ? '°' : ''}` : '–';
    return `<section class="panel"><h2>Serve type</h2>
      <div class="rowline" style="flex-wrap:wrap;gap:6px"><h3>${esc(cap(sv.type))} serve</h3><span class="chip flat">${sv.declared && sv.declared !== 'auto' ? 'You picked it' : `Read from the swing, ${esc(sv.confidence || 'low')} confidence`}</span></div>
      <p class="small ink2" style="margin-top:6px">${esc(sv.basis || '')}</p>
      <p class="tiny muted" style="margin-top:4px">${esc(cap(sv.stance || ''))} stance · filmed from ${esc(sv.view || 'the side')}</p>
      <div class="scroll" style="margin-top:8px"><table class="plain"><tr><th>What each serve asks for</th><th class="num">You</th>${types.map(t => `<th class="num" ${t === sv.type ? 'style="color:var(--ink)"' : ''}>${cap(t)}</th>`).join('')}</tr>
        ${rows.map(([k, name, key, u]) => `<tr><td>${name}</td><td class="num"><b>${byKey[key] && typeof byKey[key].value === 'number' ? byKey[key].value + (u === '°' ? '°' : '') : '–'}</b></td>${types.map(t => `<td class="num" ${t === sv.type ? 'style="font-weight:650"' : ''}>${range(T[t][k], u)}</td>`).join('')}</tr>`).join('')}</table></div>
      <p class="tiny muted" style="margin-top:6px">Distances in cm. A dash means that number cannot be seen from this camera angle.</p></section>`;
  }

  // ---------- compare ----------
  async function comparePick(preset) {
    view.innerHTML = '<p class="muted">Loading…</p>';
    let rows;
    try { rows = await api('/api/swings'); } catch (e) { view.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
    let a = preset && rows.find(x => x.ref === preset) ? preset : null, b = null;
    if (rows.length < 2) {
      view.innerHTML = `<div class="narrow"><div class="titlebar"><div><span class="eyebrow">Compare</span><h1>Two swings, side by side</h1></div></div>
        <section class="panel"><p>Compare needs two analysed swings or serves. ${rows.length ? 'You have one so far.' : 'You have none yet.'}</p><p style="margin-top:12px"><a class="btn primary" href="#/new/swing">Analyze a swing</a> <a class="btn" href="#/new/serve">Analyze a serve</a></p></section></div>`;
      return;
    }
    const list = (side, chosen, other) => rows.map(o => { const kindOf = other && rows.find(x => x.ref === other).kind, off = o.ref === other || (kindOf && kindOf !== o.kind);
      return `<button class="pick-row ${o.ref === chosen ? 'on' : ''}" data-side="${side}" data-ref="${o.ref}" ${off ? 'disabled style="opacity:.4"' : ''}>
        ${o.keyframe ? `<img class="thumb" loading="lazy" src="/files/${o.job}/${esc(o.keyframe)}" alt="" style="width:38px;height:50px;border-radius:8px;object-fit:cover">` : ''}
        <span class="grow"><b class="cut" style="display:block;font-weight:600">${esc(o.name)}</b><span class="tiny muted cut" style="display:block">${esc(o.title)} · ${when(o.created)}</span></span>
        <span class="dot light-${o.light}" style="width:9px;height:9px;border-radius:50%;flex:0 0 9px"></span></button>`; }).join('');
    const paint = () => {
      view.innerHTML = `<div class="titlebar"><div><span class="eyebrow">Compare</span><h1>Pick two swings</h1></div>
          <div class="acts"><button class="btn primary" id="goCompare" ${a && b ? '' : 'disabled'}>Compare</button></div></div>
        <p class="ink2" style="margin:-6px 0 14px;max-width:70ch">The baseline is the swing you start from. The retest is the one you want to check against it. Both videos play together, lined up on contact.</p>
        <div class="grid2" style="gap:14px"><section class="panel"><h2>Baseline</h2>${list('a', a, b)}</section><section class="panel"><h2>Retest</h2>${list('b', b, a)}</section></div>`;
      $('#goCompare').onclick = () => { location.hash = `#/compare/${encodeURIComponent(a)}/${encodeURIComponent(b)}`; };
    };
    view.onclick = ev => { const el = ev.target.closest('.pick-row'); if (!el || el.disabled) return; if (el.dataset.side === 'a') a = el.dataset.ref; else b = el.dataset.ref; paint(); };
    paint();
  }

  const VERDICT = {better: ['strength', 'Better'], worse: ['priority', 'Worse'], no_change: ['not_graded', 'No change'], b_better: ['strength', 'Better'], a_better: ['priority', 'Worse'], different: ['not_graded', 'Different']};
  const verdictChip = v => `<span class="chip">${mark(VERDICT[v][0])}${VERDICT[v][1]}</span>`;

  async function compareView(refA, refB) {
    view.innerHTML = '<p class="muted">Loading…</p>';
    let c, jobs, tracks;
    try {
      c = await api(`/api/compare?a=${encodeURIComponent(refA)}&b=${encodeURIComponent(refB)}`);
      jobs = await Promise.all([c.a, c.b].map(x => api('/api/jobs/' + x.job)));
      tracks = await Promise.all([c.a, c.b].map(x => x.files && x.files.tracks ? api(`/files/${x.job}/${x.files.tracks}`).catch(() => null) : null));
    } catch (e) { view.innerHTML = `<div class="narrow"><section class="panel"><p class="err">${esc(e.message)}</p><p style="margin-top:10px"><a class="btn" href="#/compare">Pick two swings</a></p></section></div>`; return; }
    const sides = [c.a, c.b], names = ['Baseline', 'Retest'];
    const stageOf = n => { const x = sides[n], t = tracks[n], rep = jobs[n].report;
      return {src: `/files/${x.job}/${t ? x.files.clean : 'overlay.mp4'}`, fps: t ? t.fps : x.fps, tracks: t, swings: [x.swing], series: rep.series, zeroFrame: x.contact_frame, tag: names[n]}; };
    const speed = n => { const rep = jobs[n].report, t0 = sides[n].swing.times.contact; return {name: names[n] + ', hand mph', color: n ? 'var(--blue)' : 'var(--ink2)', dash: !n, t: rep.series.t.map(t => t - t0), y: rep.series.hand_speed.map(v => v * MPH)}; };
    const cnt = k => k ? `<span class="rowline small" style="gap:10px;flex-wrap:wrap">${['priority', 'building', 'on_target', 'strength'].map(g => `<span class="rowline" style="gap:5px" title="${GRADES[g]}">${mark(g)}<b class="num">${g === 'on_target' ? k.on_target - (k.strength || 0) : k[g]}</b></span>`).join('')}</span>` : '';
    const phases = c.b.swing.phases || PHASES;
    const worked = c.worked_on || [];
    view.innerHTML = `
      <div class="titlebar"><div><span class="eyebrow">Compare</span><h1>${esc(c.b.name)} against ${esc(c.a.name.toLowerCase())}<span class="when">${esc(c.b.title)} against ${esc(c.a.title)}</span></h1></div>
        <div class="acts"><a class="btn" href="#/compare/${encodeURIComponent(refB)}/${encodeURIComponent(refA)}">Swap</a><a class="btn" href="#/compare">Pick other swings</a><button class="btn" data-pic>${ICON.save}Save picture</button><a class="btn primary" href="#/new/${c.b.kind}">Retest again</a></div></div>
      <div class="cols">
        <div class="stack left">
          <section class="panel"><h2>Result</h2>
            <h3 style="font-size:22px">${worked.length ? `${c.moved_right} of ${worked.length} moved the right way` : esc(c.headline)}</h3>
            <div class="sep"></div>
            <div class="rowline spread" style="margin:6px 0"><span class="small ink2">Baseline</span>${cnt(c.counts.a)}</div>
            <div class="rowline spread" style="margin:6px 0"><span class="small ink2">Retest</span>${cnt(c.counts.b)}</div>
            ${c.notes.map(n => `<p class="small muted" style="margin-top:8px">${esc(n)}</p>`).join('')}</section>
          ${worked.length ? `<section class="panel"><h2>What was worked on</h2>${worked.map(x => `<div class="worked"><div class="rowline spread"><b style="font-weight:600">${esc(x.label.split(' (')[0])}</b>${verdictChip(x.verdict)}</div>
            <div class="beforeafter num"><span class="from">${fmt(x.a)}${x.unit === 'deg' ? '°' : ''}</span>${ICON.arrow}<span>${fmt(x.b)}${x.unit === 'deg' ? '°' : ''}</span><small>${x.unit === 'deg' ? '' : esc(x.unit)}</small></div>${x.typical ? `<div class="tiny muted">Target ${esc(x.typical)}</div>` : ''}</div>`).join('')}</section>` : ''}
          ${c.also_better.length || c.slipped.length ? `<section class="panel">${c.also_better.length ? `<h2>Also better</h2><ul class="bullets">${c.also_better.slice(0, 5).map(t => `<li>${mark('strength')}<span>${esc(t)}</span></li>`).join('')}</ul>` : ''}
            ${c.slipped.length ? `<h2 style="margin-top:${c.also_better.length ? 14 : 0}px">Slipped</h2><ul class="bullets">${c.slipped.slice(0, 5).map(t => `<li>${mark('priority')}<span>${esc(t)}</span></li>`).join('')}</ul>` : ''}</section>` : ''}
          ${c.keep_working ? `<div class="focus" style="margin:0"><div class="lbl">${esc(c.keep_working.lead)}: ${esc(c.keep_working.title.toLowerCase())}</div><b>${esc(c.keep_working.cue)}</b></div>` : ''}
          <section class="panel"><h2>Hand speed, lined up on contact</h2>${lineChart([speed(0), speed(1)], [{t: 0, label: 'contact'}], {t0: -0.900, t1: 0.400, label: 'hand speed of both swings'})}<p class="tiny muted" style="margin-top:6px">The baseline is the dashed line.</p></section>
        </div>
        <div class="stack mid">
          <section class="panel"><div id="deck"></div>
            <div class="phasebar">${phases.map(([k, label]) => c.b.swing.frames[k] !== undefined && c.a.swing.frames[k] !== undefined ? `<button class="btn sm" data-rel="${((c.b.swing.frames[k] - c.b.contact_frame) / c.b.fps).toFixed(4)}">${esc(label)}</button>` : '').join('')}</div>
            <p class="tiny muted">Both videos share the controls, the overlays and the drawing tools. The phase buttons jump to that moment in the retest.</p></section>
          <section class="panel"><h2>Every difference<span class="tiny muted" style="font-weight:500">${c.unchanged} numbers did not change</span></h2>
            <div class="scroll"><table class="numbers"><thead><tr><th>Number</th><th>Baseline</th><th>Retest</th><th class="t">Target</th><th></th></tr></thead><tbody>
            ${c.differences.map(d => `<tr><td class="name"><b>${esc(d.label.split(' (')[0])}</b><span>${esc(d.sentence)}</span></td><td class="v num ink2">${valTxt(d.a, d.unit)}</td><td class="v num">${valTxt(d.b, d.unit)}</td><td class="t">${esc(d.typical || '')}</td><td>${verdictChip(d.verdict)}</td></tr>`).join('') || '<tr><td colspan="5" class="muted">Nothing changed by enough to matter.</td></tr>'}
            </tbody></table></div></section>
        </div>
        <div class="stack right">${sides.map((x, n) => `<section class="panel"><h2>${names[n]}<a class="btn sm" href="#/job/${x.job}/${x.index}">Open</a></h2>
          <div class="rowline">${jobs[n].report.keyframes[`${x.index}:contact`] ? `<img loading="lazy" src="/files/${x.job}/${esc(jobs[n].report.keyframes[`${x.index}:contact`])}" alt="" style="width:54px;height:72px;border-radius:10px;object-fit:cover">` : ''}
            <div class="grow"><b class="cut" style="display:block">${esc(x.name)}</b><span class="tiny muted cut" style="display:block">${esc(x.title)}</span><span class="tiny muted">${when(x.created)}</span></div></div>
          ${c.overall.a !== null ? `<div class="sep"></div>${cnt(c.counts[n ? 'b' : 'a'])}` : ''}</section>`).join('')}</div>
      </div>`;
    deck = TT.deck($('#deck'), {stages: [stageOf(0), stageOf(1)], name: 'compare'});
    view.onclick = ev => {
      const el = ev.target.closest('[data-rel]');
      if (el) deck.freeze(deck.master.zeroFrame + Math.round(+el.dataset.rel * deck.master.fps));
      if (ev.target.closest('[data-pic]')) deck.savePicture();
    };
  }

  // ---------- match and lesson ----------
  function courtSvg(report, layer) {
    const DW = 5.485, SW = 4.115, L = 11.885, S = 6.400, pad = 2.600, k = 20;
    const W = (2 * DW + 2 * pad) * k, H = (2 * L + 2 * pad) * k;
    const X = x => (x + DW + pad) * k, Y = y => (L + pad - y) * k;
    const ln = (a, b) => `<line x1="${X(a[0])}" y1="${Y(a[1])}" x2="${X(b[0])}" y2="${Y(b[1])}" stroke="var(--court-line)" stroke-width="2"/>`;
    const lines = [[[-DW, L], [DW, L]], [[-DW, -L], [DW, -L]], [[-DW, -L], [-DW, L]], [[DW, -L], [DW, L]], [[-SW, -L], [-SW, L]], [[SW, -L], [SW, L]],
      [[-SW, S], [SW, S]], [[-SW, -S], [SW, -S]], [[0, -S], [0, S]]].map(([a, b]) => ln(a, b)).join('');
    const color = Object.fromEntries(report.players.map(p => [p.id, p.color]));
    let marks = '';
    for (const p of report.players) {
      const sum = report.shot_summary[p.id];
      if (layer === 'landings') marks += sum.landings.map(m => `<circle cx="${X(m.x)}" cy="${Y(m.y)}" r="6" fill="${color[p.id]}" stroke="#000" stroke-opacity=".4"${m.result !== 'in' && m.result !== 'unknown' ? ' fill-opacity=".25"' : ''}/>`).join('');
      if (layer === 'contacts') marks += sum.hit_positions.map(m => `<rect x="${X(m.x) - 5}" y="${Y(m.y) - 5}" width="10" height="10" fill="${color[p.id]}" stroke="#000" stroke-opacity=".4"/>`).join('');
      if (layer === 'movement' && report.movement) marks += report.movement[p.id].positions.map(q => `<circle cx="${X(q[0])}" cy="${Y(q[1])}" r="4" fill="${color[p.id]}" fill-opacity=".28"/>`).join('');
    }
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:300px;height:auto;margin:0 auto" role="img" aria-label="court map"><rect width="${W}" height="${H}" rx="12" fill="var(--court)"/>${lines}
      <line x1="${X(-DW - .9)}" y1="${Y(0)}" x2="${X(DW + .9)}" y2="${Y(0)}" stroke="#111" stroke-width="3"/>${marks}
      <text x="${W / 2}" y="${H - 8}" font-size="13" text-anchor="middle" fill="var(--court-line)">camera end</text></svg>`;
  }
  function shotLabel(s) {
    if (s.contact === 'serve' || s.contact === 'overhead') return nice(s.contact);
    const stroke = s.stroke === 'unknown' ? '' : nice(s.stroke);
    return `${stroke} ${s.contact === 'groundstroke' ? '' : nice(s.contact)}`.trim() || 'shot';
  }
  function mocapLine(metrics) {
    const short = {hand_speed_peak: 'hand speed', contact_height: 'contact height', swing_path: 'swing path', elbow_contact: 'elbow'};
    return Object.keys(short).filter(k => metrics[k] && metrics[k].value !== null).map(k => `${short[k]} ${fmt(metrics[k].value)} ${esc(metrics[k].unit)}`).join(' · ');
  }
  function tallyTable(title, groups, first) {
    const rows = Object.entries(groups);
    if (!rows.length) return '';
    return `<h2 style="margin:14px 0 4px">${title}</h2><div class="scroll"><table class="plain">
      <tr><th>${first}</th><th class="num">Shots</th><th class="num">In</th><th class="num">Net</th><th class="num">Long</th><th class="num">Wide</th><th class="num">In %</th></tr>
      ${rows.map(([k, v]) => `<tr><td>${nice(k)}</td><td class="num">${v.shots}</td><td class="num">${v.made}</td><td class="num">${v.net}</td><td class="num">${v.long}</td><td class="num">${v.wide}</td><td class="num">${pctTxt(v.in_pct)}</td></tr>`).join('')}</table></div>`;
  }
  function lessonSection(r) {
    const calibrated = r.mode === 'calibrated';
    return `${calibrated ? '' : '<section class="panel small muted">The court was not marked (or the camera moved), so shots are counted and classified but landing spots and in or out are not available.</section>'}
      ${r.players.map(p => { const L = r.lesson[p.id], t = L.total;
        if (!t.shots) return `<section class="panel"><h3><span class="pdot" style="background:${p.color}"></span>${esc(p.name)}</h3><p class="muted">No shots seen.</p></section>`;
        return `<section class="panel"><h3><span class="pdot" style="background:${p.color}"></span>${esc(p.name)}</h3>
          <div class="valrow"><div class="val num">${t.shots}<small>shots</small></div>${t.judged ? `<div class="target">In<b class="num">${t.made} of ${t.judged} (${pctTxt(t.in_pct)})</b></div>` : ''}</div>
          ${t.not_seen ? `<p class="small muted">${t.not_seen} landing${t.not_seen === 1 ? '' : 's'} not seen.</p>` : ''}${L.most_common_miss ? `<p class="small muted">Most common miss: ${nice(L.most_common_miss)}.</p>` : ''}
          ${tallyTable('By shot type', L.by_kind, 'Shot')}${tallyTable('By where it was hit from', L.by_hit_zone, 'Position')}${tallyTable('By landing depth (balls that went in)', L.by_depth, 'Depth')}</section>`; }).join('')}
      <p class="tiny muted">In and out are estimates from one camera. A ball within about 12 cm of a line counts as in. "Not seen" means the bounce was not detected, usually because it was hidden or too close to the next hit.</p>`;
  }
  function statRows(stats, rows) {
    const t = stats.teams;
    return rows.map(([label, f]) => `<tr><td>${label}</td><td class="num">${f(t['0'])}</td><td class="num">${f(t['1'])}</td></tr>`).join('');
  }

  function matchReport(job) {
    const r = job.report, id = job.id;
    const color = Object.fromEntries(r.players.map(p => [p.id, p.color]));
    const calibrated = r.mode === 'calibrated';
    let layer = 'landings';
    const shots = r.rallies.flatMap(x => x.shots), recs = r.recommendations || [], st = r.stats;
    const teamName = t => r.players.filter(p => p.team === t).map(p => esc(p.name)).join(' / ');
    const posAll = r.positioning_all_rallies;
    view.innerHTML = `
      <div class="titlebar"><div><span class="eyebrow">${r.lesson ? 'Lesson' : 'Match'}</span><h1><span data-title>${esc(job.title)}</span><span class="when">${when(job.created)}</span></h1></div>
        <div class="acts"><button class="btn" data-open-save>${ICON.save}Save</button><span class="chip flat">${esc(cap(r.format))}</span><span class="chip flat">${calibrated ? 'Court marked' : 'Court not marked'}</span><span class="chip flat">Ball seen ${r.tracking.ball_seen_pct}% of frames</span></div></div>
      <div class="cols">
        <div class="stack left">
          ${r.warnings.map(w => `<section class="panel small">${esc(w)}</section>`).join('')}
          ${r.lesson ? lessonSection(r) : `
            ${recs.length ? recs.map(x => `<section class="panel rec p${x.priority}"><h3>${esc(x.title)}</h3><p class="small muted" style="margin:4px 0">${esc(x.evidence)}</p><p>${esc(x.advice)}</p></section>`).join('')
              : `<section class="panel"><h2>Where to stand and what to play</h2><p class="small muted">${calibrated
                ? 'Not enough scored points in this video for evidence-based advice. Positioning measured so far is shown; a full set gives far more to work with.'
                : 'Positioning and strategy advice needs positions in metres. Film from a fixed spot behind the baseline with the whole court in view and mark the four corners when you upload.'}</p></section>`}
            ${posAll ? `<section class="panel"><h2>Positioning when the opponent hits</h2><div class="scroll"><table class="plain">
              <tr><th>Player</th><th class="num">Net</th><th class="num">Mid</th><th class="num">Base</th><th class="num">Deep</th><th class="num">Off spot</th></tr>
              ${r.players.map(p => { const z = posAll.players[p.id].zones, rc = posAll.players[p.id].recovery, g = n => pctTxt(z[n] ? z[n].share_pct : 0);
                return `<tr><td>${esc(p.name)}</td><td class="num">${g('net')}</td><td class="num">${g('no_mans_land')}</td><td class="num">${g('baseline')}</td><td class="num">${g('deep_behind')}</td><td class="num">${rc.avg_error_m === null ? '–' : rc.avg_error_m + ' m'}</td></tr>`; }).join('')}
              </table></div><p class="tiny muted" style="margin-top:6px">"Off spot" is the average sideways distance from the best recovery position when the opponent makes contact (singles, baseline rallies).</p></section>` : ''}`}
        </div>
        <div class="stack mid">
          <section class="panel"><div id="deck"></div><p class="small muted">${r.players.map(p => `<span class="pdot" style="background:${p.color}"></span>${esc(p.name)}`).join(' &nbsp; ')}</p></section>
          <section class="panel"><h2>Shots<span class="tiny muted" style="font-weight:500">Tap a shot to jump the video to it</span></h2>${shots.length ? r.rallies.map(ra => `<div class="tiny muted" style="margin-top:8px">${r.lesson ? 'Sequence' : 'Rally'} ${ra.n} · ${ra.shots.length} shot${ra.shots.length === 1 ? '' : 's'}</div>
            ${ra.shots.map(s => `<div class="shot" data-seek="${Math.max(0, s.t - 1).toFixed(2)}"><span class="t num">${s.t.toFixed(1)}s</span><span class="pdot" style="background:${color[s.player]}"></span>
              <div class="grow"><b>${esc(s.name)}</b> ${shotLabel(s)} ${s.unsure_player ? '<span class="chip flat">check player</span>' : ''}
                ${s.mocap ? `<div class="small muted">${mocapLine(s.mocap.metrics)}</div>${s.mocap.tip ? `<div class="small"><b>Fix:</b> ${esc(s.mocap.tip.title)}. <span class="muted">${esc(s.mocap.tip.cue)}</span></div>` : ''}` : ''}</div>
              <span class="small num">${r.lesson ? (s.result === 'unknown' ? '' : `<b>${s.result === 'in' ? 'in' : nice(s.result)}</b>`) : (s.result === 'in' || s.result === 'unknown' ? '' : nice(s.result))} ${s.speed_kmh ? Math.round(s.speed_kmh * 0.621) + ' mph' : ''}</span></div>`).join('')}`).join('')
            : '<p class="muted">No shots were detected.</p>'}</section>
          ${st ? `<section class="panel"><h2>Match stats</h2><h3>${esc(st.overview.score || 'In progress')}</h3>
            <p class="small muted">${st.overview.points} points · average rally ${fmt(st.overview.avg_rally)} shots · longest ${st.overview.longest_rally}</p>
            <div class="scroll"><table class="plain"><tr><th></th><th class="num">${teamName(0)}</th><th class="num">${teamName(1)}</th></tr>
            ${statRows(st, [
              ['Points won', t => `${t.points.won} (${pctTxt(t.points.won_pct)})`], ['Winners', t => t.points.winners], ['Unforced errors', t => t.points.unforced_errors],
              ['Forced errors', t => t.points.forced_errors], ['1st serve in', t => pctTxt(t.serve.first_serve_in_pct)], ['Won on 1st serve', t => pctTxt(t.serve.first_serve_won_pct)],
              ['Won on 2nd serve', t => pctTxt(t.serve.second_serve_won_pct)], ['Aces', t => t.serve.aces], ['Double faults', t => t.serve.double_faults],
              ['Return points won', t => pctTxt(t.ret.points_won_pct)], ['Break points won', t => `${t.ret.break_points_converted}/${t.ret.break_points_chances}`],
              ['Net points won', t => `${pctTxt(t.net.won_pct)} of ${t.net.points}`], ['Short rallies (0-4) won', t => pctTxt(t.rally['0-4'].won_pct)],
              ['Long rallies (9+) won', t => pctTxt(t.rally['9+'].won_pct)], ['Distance run', t => t.movement.distance_m + ' m']])}
            </table></div>${st.insights.length ? `<div class="sep"></div><h2>What decided it</h2>${st.insights.map(x => `<p style="margin-top:6px">${esc(x)}</p>`).join('')}` : ''}</section>` : ''}
          ${r.review && r.review.length ? `<section class="panel small"><h2>Rallies not scored</h2>${r.review.map(x => `<p><b>${x.t_start}s</b>: ${esc(x.reason)} (${x.shots} shots)</p>`).join('')}
            <p class="muted" style="margin-top:6px">A point is scored automatically only when the serve is seen and the ending is clear.</p></section>` : ''}
        </div>
        <div class="stack right">
          ${r.players.map(p => { const s = r.shot_summary[p.id], mv = r.movement && r.movement[p.id], se = r.session[p.id];
            return `<section class="panel"><h3><span class="pdot" style="background:${p.color}"></span>${esc(p.name)}</h3>
              <p style="margin-top:6px"><b class="num">${s.shots}</b> shots ${Object.entries(s.by_stroke).filter(([k]) => k !== 'unknown').map(([k, v]) => `<span class="chip flat">${v} ${nice(k)}</span>`).join(' ')}
                ${Object.entries(s.by_contact).filter(([k]) => !['groundstroke', 'serve'].includes(k)).map(([k, v]) => `<span class="chip flat">${v} ${nice(k)}</span>`).join(' ')}</p>
              ${s.avg_speed_kmh ? `<p class="small">Average shot ${Math.round(s.avg_speed_kmh * 0.621)} mph, top ${Math.round(s.max_speed_kmh * 0.621)} mph</p>` : ''}
              ${mv ? `<p class="small">Ran ${mv.distance_m} m${mv.max_speed_kmh ? `, top speed ${Math.round(mv.max_speed_kmh * 0.621)} mph` : ''}</p>` : ''}
              ${se.swings_measured ? `<p class="tiny muted" style="margin-top:4px">Motion capture on ${se.swings_measured} swing${se.swings_measured === 1 ? '' : 's'}: ${['hand_speed_peak', 'contact_height', 'swing_path', 'elbow_contact', 'knee_bend_dom'].filter(k => se.metrics[k]).map(k => `${esc(se.metrics[k].label.split(/[,(:]/)[0].toLowerCase())} ${fmt(se.metrics[k].mean)} ${esc(se.metrics[k].unit)}`).join(' · ')}</p>` : ''}</section>`; }).join('')}
          ${calibrated ? `<section class="panel"><h2>Court map</h2><div class="tabs fill" id="layers"><button class="on" data-l="landings">Landings</button><button data-l="contacts">Contact</button><button data-l="movement">Movement</button></div>
            <div id="court" style="margin-top:10px"></div><p class="tiny muted" style="margin-top:6px">Faded landing marks were out or in the net.</p></section>` : ''}
        </div>
      </div>`;
    deck = TT.deck($('#deck'), {stages: [{src: `/files/${id}/overlay.mp4`, fps: r.tracking.analysis_fps, marks: (job.marks || [])[0]}], contact: false,
      name: job.title.replace(/\.[a-z0-9]{2,4}$/i, ''), onMarks: marks => saveMarks(job, marks)});
    const paint = () => { if ($('#court')) $('#court').innerHTML = courtSvg(r, layer); };
    view.onclick = ev => {
      const seek = ev.target.closest('[data-seek]'), l = ev.target.closest('[data-l]');
      if (ev.target.closest('[data-open-save]')) openSave(job, {onTitle: t => { job.title = t; $$('[data-title]').forEach(x => { x.textContent = t; }); }});
      if (seek) { deck.freeze(Math.round(+seek.dataset.seek * deck.master.fps)); setTimeout(() => { if (!deck.playing) deck.toggle(); }, 150); deck.el.scrollIntoView({behavior: 'smooth', block: 'nearest'}); }
      if (l) { layer = l.dataset.l; $$('#layers button').forEach(b => b.classList.toggle('on', b === l)); paint(); }
    };
    paint();
  }

  route();
})();

"""
pitch_component.py - the interactive pitch used by dashboard.py.

One Streamlit v2 component holding the metric tiles, the pitch and the target
list.  Design behaviours, and where each one lives:

  Optimistic update     A click presses the player in the browser straight away
                        (node, links, list row, and an estimated efficiency
                        marked with "≈"), then Python confirms with exact numbers.
  Origin-aware motion   The cut spreads outward from the pressed player: a ripple
                        starts at the node and each link fades after a delay
                        proportional to its distance from that node.  The hover
                        card grows out of the player it describes.
  Interruptible motion  Every state change is a CSS transition or a tween that
                        restarts from the value currently on screen, so a second
                        click mid-animation redirects it instead of queueing.
  Tabular numbers       All figures use tabular-nums so digits do not shift.
  Progressive disclosure  Tiles and map first; hover for a player's summary;
                        the list shows five targets, each row opens a breakdown,
                        and "Show all" reveals the rest.
"""

import streamlit as st

HTML = """
<div class="pp">
  <div class="tiles" role="status" aria-live="polite"></div>
  <div class="stage">
    <svg class="pitch" viewBox="-3 -3 126 86" role="group" aria-label="Passing network on a pitch"></svg>
    <div class="card" hidden></div>
  </div>
  <div class="listhead"><span class="lh-title">Recommended pressing targets</span>
    <button class="reset" type="button" hidden>Clear pressed players</button></div>
  <div class="list"></div>
  <button class="more" type="button"></button>
</div>
"""

CSS = """
.pp { --ink: var(--st-text-color, #14261f); --bg: var(--st-background-color, #fff);
      --panel: var(--st-secondary-background-color, #f0f2f6); --line: var(--st-border-color, rgba(128,128,128,.35));
      --accent: var(--st-primary-color, #1f5fb0); --cut: #e34948; --muted: color-mix(in srgb, var(--ink) 62%, transparent);
      --ease: cubic-bezier(.2,.8,.2,1);
      color: var(--ink); font-family: var(--st-font, system-ui, sans-serif); font-size: 14px;
      display: flex; flex-direction: column; gap: 14px; }
.pp .num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }

.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.tile { background: var(--panel); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 2px;
        transition: opacity .25s var(--ease); }
.tile.pending { opacity: .55; }
.tile .k { font-size: 12.5px; color: var(--muted); }
.tile .v { font-size: 26px; font-weight: 600; line-height: 1.15; }
.tile .d { font-size: 12.5px; min-height: 17px; color: var(--muted); transition: color .25s var(--ease); }
.tile .d.bad { color: var(--cut); }

.stage { position: relative; width: 100%; max-width: 880px; margin: 0 auto; }
.pitch { width: 100%; height: auto; display: block; overflow: visible; }
.pitch .mark { fill: none; stroke: var(--line); stroke-width: .35; }
.edge { stroke: var(--ink); stroke-linecap: round;
        transition: opacity .38s var(--ease), stroke .38s var(--ease), stroke-dashoffset .38s var(--ease); }
.edge.cut { stroke: var(--cut); stroke-dasharray: .9 1.4; }
.node { cursor: pointer; outline: none; }
.node .dot { stroke: var(--bg); stroke-width: .7;
             transition: fill .35s var(--ease), fill-opacity .3s var(--ease), stroke .2s var(--ease),
                         stroke-width .2s var(--ease), transform .3s var(--ease); transform-box: fill-box; transform-origin: center; }
.node:hover .dot, .node.hl .dot, .node:focus-visible .dot { stroke: var(--accent); stroke-width: 1; }
.node:active .dot { transform: scale(.94); }
.node.out .dot { fill-opacity: .08; stroke: var(--cut); stroke-width: .7; stroke-dasharray: 1.1 .9; }
.node .x { stroke: var(--cut); stroke-width: .8; stroke-linecap: round; opacity: 0; transform: scale(.4);
           transform-box: fill-box; transform-origin: center; transition: opacity .25s var(--ease), transform .3s var(--ease); }
.node.out .x { opacity: 1; transform: scale(1); }
.node text { font-size: 2.3px; fill: var(--ink); text-anchor: middle; pointer-events: none;
             paint-order: stroke; stroke: var(--bg); stroke-width: .6; transition: opacity .3s var(--ease); }
.node.out text { opacity: .55; }
.ripple { fill: none; stroke: var(--cut); stroke-width: .5; pointer-events: none; }
.ripple.back { stroke: var(--accent); }

.card { position: absolute; z-index: 2; width: 216px; background: var(--bg); border: 1px solid var(--line);
        border-radius: 10px; padding: 10px 12px; box-shadow: 0 6px 22px rgba(0,0,0,.16); pointer-events: none;
        opacity: 0; transform: scale(.86); transition: opacity .14s var(--ease), transform .16s var(--ease); }
.card.on { opacity: 1; transform: scale(1); }
.card[hidden] { display: block; visibility: hidden; }
.card h4 { margin: 0 0 6px; font-size: 14px; font-weight: 600; }
.card dl { margin: 0; display: grid; grid-template-columns: 1fr auto; gap: 3px 12px; font-size: 12.5px; }
.card dt { color: var(--muted); } .card dd { margin: 0; text-align: right; }
.card .hint { margin-top: 7px; font-size: 12px; color: var(--muted); }

.listhead { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-height: 30px; }
.lh-title { font-weight: 600; }
.pp button { font: inherit; color: inherit; background: none; border: 1px solid var(--line); border-radius: 8px;
             padding: 5px 11px; cursor: pointer; transition: background .15s var(--ease), border-color .15s var(--ease), color .15s var(--ease); }
.pp button:hover { border-color: var(--accent); }
.pp button:focus-visible, .node:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.list { display: flex; flex-direction: column; }
.row { border-top: 1px solid var(--line); transition: background .15s var(--ease); }
.row.hl { background: var(--panel); }
.row.extra { display: grid; grid-template-rows: 0fr; border-top-color: transparent;
             transition: grid-template-rows .32s var(--ease), border-color .32s var(--ease); }
.list.all .row.extra { grid-template-rows: 1fr; border-top-color: var(--line); }
.row.extra > .inner { overflow: hidden; min-height: 0; }
.main { display: grid; grid-template-columns: 22px minmax(90px, 1.5fr) minmax(110px, 1.3fr) 76px 76px auto 30px;
        align-items: center; gap: 10px; padding: 8px 4px; }
.rank { color: var(--muted); text-align: right; }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: opacity .25s var(--ease); }
.row.out .name { opacity: .5; text-decoration: line-through; }
.bar { display: flex; align-items: center; gap: 8px; }
.track { flex: 1; height: 6px; border-radius: 3px; background: var(--panel); overflow: hidden; }
.fill { height: 100%; border-radius: 3px; background: var(--accent); transform-origin: left center;
        transition: transform .4s var(--ease); }
.cell { text-align: right; } .cell small { display: block; color: var(--muted); font-size: 11px; }
.press.on { background: var(--cut); border-color: var(--cut); color: #fff; }
.chev { border: none !important; padding: 4px !important; width: 28px; height: 28px; display: grid; place-items: center; }
.chev svg { transition: transform .25s var(--ease); } .chev[aria-expanded="true"] svg { transform: rotate(180deg); }
.detail { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .3s var(--ease); }
.detail.open { grid-template-rows: 1fr; }
.detail > div { overflow: hidden; min-height: 0; }
.dgrid { display: grid; grid-template-columns: 110px 1fr 44px 150px; gap: 6px 12px; align-items: center;
         padding: 4px 4px 14px 36px; font-size: 13px; }
.dgrid .why { grid-column: 1 / -1; color: var(--muted); padding-bottom: 2px; }
.dgrid .w { color: var(--muted); font-size: 12px; }
.more { align-self: flex-start; }
@media (max-width: 640px) {
  .main { grid-template-columns: 18px 1fr 64px auto 28px; } .main .bar, .main .cell.pm { display: none; }
  .dgrid { grid-template-columns: 90px 1fr 40px; padding-left: 8px; } .dgrid .w { display: none; }
}
@media (prefers-reduced-motion: reduce) { .pp *, .pp { transition-duration: .01ms !important; } }
"""

JS = r"""
const NS = 'http://www.w3.org/2000/svg';
const TOP = 5;
const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const sv = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
const pct = (v, d = 0) => (v * 100).toFixed(d) + '%';
const LABELS = { degree: 'Degree', betweenness: 'Betweenness', closeness: 'Closeness', eigenvector: 'Eigenvector' };
const TILES = [
  { k: 'efficiency', name: 'Global efficiency', fmt: v => v.toFixed(2), worse: -1 },
  { k: 'path_length', name: 'Avg path length (passes)', fmt: v => v.toFixed(2), worse: 1 },
  { k: 'clustering', name: 'Clustering', fmt: v => v.toFixed(2), worse: -1 },
  { k: 'connectivity', name: 'Connected core', fmt: v => pct(v), worse: -1 },
];

function ramp(root, t) {            // one hue, light to dark; flipped on a dark page so "more" always stands out
  const bg = getComputedStyle(root).getPropertyValue('--st-background-color').trim();
  const m = bg.match(/^#?([0-9a-f]{6})$/i);
  let dark = false;
  if (m) { const n = parseInt(m[1], 16); dark = (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) < 110; }
  const a = dark ? [38, 62, 96] : [208, 226, 247], b = dark ? [150, 200, 255] : [13, 59, 122];
  return 'rgb(' + a.map((c, i) => Math.round(c + (b[i] - c) * t)).join(',') + ')';
}

function tween(S, key, node, to, fmt, prefix) {    // restarts from the value on screen: interruptible
  cancelAnimationFrame(S.raf[key]); clearTimeout(S.tid[key]);
  const from = S.shown[key] ?? to, t0 = performance.now(), dur = (reduced() || document.hidden) ? 0 : 420;
  const land = () => { cancelAnimationFrame(S.raf[key]); S.shown[key] = to; node.textContent = (prefix || '') + fmt(to); };
  if (!dur || from === to) return land();
  const step = now => {
    const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3), v = from + (to - from) * e;
    S.shown[key] = v; node.textContent = (prefix || '') + fmt(v);
    if (k < 1) S.raf[key] = requestAnimationFrame(step);
  };
  node.textContent = (prefix || '') + fmt(from);
  S.raf[key] = requestAnimationFrame(step);
  S.tid[key] = setTimeout(land, dur + 150);         // frames can stall in a background tab; always land on the true value
}

function build(root, S) {
  const d = S.data, svg = root.querySelector('.pitch'), list = root.querySelector('.list'), tiles = root.querySelector('.tiles');
  svg.replaceChildren(); list.replaceChildren(); tiles.replaceChildren();
  S.shown = {}; S.open = new Set(); S.all = false; S.nodes = {}; S.rows = {}; S.edges = []; S.rip = {};
  S.by = Object.fromEntries(d.players.map(p => [p.name, p]));

  for (const t of TILES) {
    const box = el('div', 'tile'); box.dataset.k = t.k;
    box.append(el('span', 'k', t.name), el('span', 'v num'), el('span', 'd num'));
    tiles.append(box);
  }

  const marks = [['rect', { x: 0, y: 0, width: 120, height: 80 }], ['line', { x1: 60, y1: 0, x2: 60, y2: 80 }],
    ['circle', { cx: 60, cy: 40, r: 10 }], ['rect', { x: 0, y: 18, width: 18, height: 44 }], ['rect', { x: 102, y: 18, width: 18, height: 44 }],
    ['rect', { x: 0, y: 30, width: 6, height: 20 }], ['rect', { x: 114, y: 30, width: 6, height: 20 }]];
  for (const [tag, a] of marks) { const m = sv(tag, a); m.setAttribute('class', 'mark'); svg.append(m); }

  const gE = sv('g', {}), gR = sv('g', {}), gN = sv('g', {}); svg.append(gE, gR, gN); S.gR = gR;
  const wmax = Math.max(1, ...d.edges.map(e => e.w)), imax = Math.max(1, ...d.players.map(p => p.inv));
  for (const e of d.edges) {
    const a = S.by[e.u], b = S.by[e.v]; if (!a || !b) continue;
    const line = sv('line', { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'edge', 'stroke-width': (0.15 + 1.5 * e.w / wmax).toFixed(2) });
    gE.append(line); S.edges.push({ e, line, base: 0.10 + 0.42 * e.w / wmax });
  }
  for (const p of d.players) {
    p.r = 1.9 + 2.1 * p.inv / imax;
    const g = sv('g', { class: 'node', transform: `translate(${p.x},${p.y})`, tabindex: 0, role: 'button' });
    const k = p.r * 0.45;
    g.append(sv('circle', { class: 'dot', r: p.r.toFixed(2) }),
      sv('path', { class: 'x', d: `M${-k},${-k}L${k},${k}M${k},${-k}L${-k},${k}` }));
    const t = sv('text', { y: (p.r + 2.7).toFixed(2) }); t.textContent = p.label; g.append(t);
    g.addEventListener('click', () => toggle(root, S, p.name));
    g.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggle(root, S, p.name); } });
    for (const on of ['pointerenter', 'focus']) g.addEventListener(on, () => hover(root, S, p.name, true));
    for (const off of ['pointerleave', 'blur']) g.addEventListener(off, () => hover(root, S, p.name, false));
    gN.append(g); S.nodes[p.name] = g;
  }

  d.players.forEach((p, i) => {
    const row = el('div', 'row' + (i >= TOP ? ' extra' : '')), inner = el('div', 'inner'), main = el('div', 'main');
    const bar = el('div', 'bar'), track = el('div', 'track'), fill = el('div', 'fill'); track.append(fill);
    bar.append(track, el('span', 'num score'));
    const loss = el('div', 'cell num'); loss.append(document.createTextNode('−' + pct(p.loss, 1)), el('small', '', 'efficiency'));
    const pm = el('div', 'cell num pm'); pm.append(document.createTextNode(p.pressed.toFixed(1)), el('small', '', 'pressed / match'));
    const press = el('button', 'press'); press.type = 'button';
    press.addEventListener('click', () => toggle(root, S, p.name));
    const chev = el('button', 'chev'); chev.type = 'button'; chev.setAttribute('aria-label', 'Show score breakdown for ' + p.name);
    chev.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 5l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const nm = el('span', 'name', p.name); nm.title = p.name;
    main.append(el('span', 'rank num', String(i + 1)), nm, bar, loss, pm, press, chev);

    const detail = el('div', 'detail'), dwrap = el('div'), grid = el('div', 'dgrid');
    grid.append(el('div', 'why', 'How this score is built (each centrality scaled 0 to 1 within the team)'));
    for (const c of Object.keys(LABELS)) {
      const tr = el('div', 'track'), fl = el('div', 'fill'); fl.style.transform = `scaleX(${p.parts[c]})`; tr.append(fl);
      grid.append(el('span', '', LABELS[c]), tr, el('span', 'num cell', p.parts[c].toFixed(2)),
        el('span', 'w num', 'weight ' + d.weights[c].toFixed(2) + ' → ' + (p.parts[c] * d.weights[c]).toFixed(2)));
    }
    grid.append(el('div', 'why num', `${p.inv.toLocaleString('en-US')} pass involvements · vulnerability score ${p.pvs.toFixed(2)} · removing this player alone costs ${pct(p.loss, 1)} of efficiency`));
    dwrap.append(grid); detail.append(dwrap);
    chev.addEventListener('click', () => { S.open.has(p.name) ? S.open.delete(p.name) : S.open.add(p.name); render(root, S); });
    row.addEventListener('pointerenter', () => S.nodes[p.name].classList.add('hl'));
    row.addEventListener('pointerleave', () => S.nodes[p.name].classList.remove('hl'));
    if (i >= TOP) { inner.append(main, detail); row.append(inner); } else row.append(main, detail);
    list.append(row); S.rows[p.name] = { row, fill, score: bar.querySelector('.score'), press, chev, detail, focusables: [press, chev] };
  });

  root.querySelector('.more').onclick = () => { S.all = !S.all; render(root, S); };
  root.querySelector('.reset').onclick = () => {
    const was = [...S.removed]; S.removed = new Set(); push(S); was.forEach(n => ripple(S, n, false)); render(root, S, was);
  };
}

function push(S) {                      // tell Python; it answers with exact numbers and the same sequence number
  S.seq = Math.max(S.seq, S.data.ack) + 1;
  S.send('removed', { players: [...S.removed], seq: S.seq });
}

function ripple(S, name, out) {
  if (reduced()) return;
  const p = S.by[name]; if (!p) return;
  if (S.rip[name]) S.rip[name].cancel();          // a second click cancels the first ripple
  const c = sv('circle', { cx: p.x, cy: p.y, r: p.r, class: 'ripple' + (out ? '' : ' back') }); S.gR.append(c);
  const a = c.animate([{ r: p.r + 'px', opacity: .75 }, { r: (p.r + 11) + 'px', opacity: 0 }], { duration: 620, easing: 'cubic-bezier(.2,.8,.2,1)' });
  S.rip[name] = a; a.onfinish = a.oncancel = () => c.remove();
}

function toggle(root, S, name) {
  const out = !S.removed.has(name);
  out ? S.removed.add(name) : S.removed.delete(name);
  ripple(S, name, out);
  render(root, S, [name]);              // optimistic: drawn before Python has answered
  push(S);
}

function hover(root, S, name, on) {
  const card = root.querySelector('.card'), row = S.rows[name]; if (row) row.row.classList.toggle('hl', on);
  if (!on) { card.classList.remove('on'); return; }
  const p = S.by[name], stage = root.querySelector('.stage').getBoundingClientRect(), g = S.nodes[name].querySelector('.dot').getBoundingClientRect();
  const out = S.removed.has(name);
  card.innerHTML = '';
  const dl = el('dl');
  const add = (k, v) => { dl.append(el('dt', '', k), el('dd', 'num', v)); };
  add('Criticality (TCS)', p.tcs.toFixed(2)); add('Vulnerability (PVS)', p.pvs.toFixed(2));
  add('Efficiency lost if pressed', '−' + pct(p.loss, 1)); add('Pressed per match', p.pressed.toFixed(1));
  card.append(el('h4', '', p.name), dl, el('div', 'hint', out ? 'Click to bring back' : 'Click to press out of the game'));
  card.hidden = false;
  const cx = g.left + g.width / 2 - stage.left, cy = g.top + g.height / 2 - stage.top, w = 216, h = card.offsetHeight, gap = g.width / 2 + 10;
  const right = cx + gap + w < stage.width;             // the card grows out of the player it belongs to
  const top = Math.max(0, Math.min(stage.height - h, cy - h / 2));
  card.style.left = (right ? cx + gap : cx - gap - w) + 'px'; card.style.top = top + 'px';
  card.style.transformOrigin = (right ? '0%' : '100%') + ' ' + (cy - top) + 'px';
  requestAnimationFrame(() => card.classList.add('on'));
}

function render(root, S, origins) {
  const d = S.data, rm = S.removed;
  const exact = rm.size === d.removed.length && d.removed.every(n => rm.has(n));
  const src = (origins || []).map(n => S.by[n]).filter(Boolean);
  const far = Math.hypot(120, 80) / 2;

  for (const p of d.players) {
    const g = S.nodes[p.name], out = rm.has(p.name);
    g.classList.toggle('out', out); g.setAttribute('aria-pressed', out);
    g.setAttribute('aria-label', `${p.name}, criticality ${p.tcs.toFixed(2)}${out ? ', pressed out' : ''}`);
    g.querySelector('.dot').style.fill = ramp(root, d.colour === 'pvs' ? p.pvs : p.tcs);
    const r = S.rows[p.name];
    r.row.classList.toggle('out', out);
    r.press.classList.toggle('on', out); r.press.textContent = out ? 'Pressed' : 'Press'; r.press.setAttribute('aria-pressed', out);
    r.fill.style.transform = `scaleX(${d.colour === 'pvs' ? p.pvs : p.tcs})`;
    r.score.textContent = (d.colour === 'pvs' ? p.pvs : p.tcs).toFixed(2);
    const open = S.open.has(p.name); r.detail.classList.toggle('open', open); r.chev.setAttribute('aria-expanded', open);
  }
  for (const { e, line, base } of S.edges) {
    const cut = rm.has(e.u) || rm.has(e.v);
    let delay = 0;                                       // links fall away in order of distance from the click
    for (const o of src) if (o.name === e.u || o.name === e.v) {
      const q = S.by[o.name === e.u ? e.v : e.u]; delay = Math.hypot(q.x - o.x, q.y - o.y) / far * 260;
    }
    line.style.transitionDelay = reduced() ? '0ms' : delay.toFixed(0) + 'ms';
    line.classList.toggle('cut', cut); line.style.opacity = cut ? 0.28 : base;
  }

  const est = d.base.efficiency * Math.max(0, 1 - [...rm].reduce((s, n) => s + (S.by[n] ? S.by[n].loss : 0), 0));
  for (const t of TILES) {
    const box = root.querySelector(`.tile[data-k="${t.k}"]`), v = box.querySelector('.v'), dd = box.querySelector('.d');
    const base = d.base[t.k], guess = t.k === 'efficiency' && !exact;
    const val = exact ? d.after[t.k] : (guess ? est : null);
    box.classList.toggle('pending', !exact && !guess);
    if (val == null) { if (exact) { v.textContent = 'n/a'; dd.textContent = ''; } continue; }
    tween(S, t.k, v, val, t.fmt, guess ? '≈ ' : '');
    const ch = base ? (val - base) / base : 0;
    if (!rm.size || Math.abs(ch) < 0.0005) { dd.textContent = rm.size ? 'no change' : 'intact network'; dd.classList.remove('bad'); }
    else { dd.textContent = (ch > 0 ? '+' : '−') + pct(Math.abs(ch)) + ' vs intact' + (guess ? ' (estimate)' : ''); dd.classList.toggle('bad', ch * t.worse > 0); }
  }

  const list = root.querySelector('.list'), more = root.querySelector('.more'), extra = d.players.length - TOP;
  list.classList.toggle('all', S.all);
  more.hidden = extra <= 0; more.textContent = S.all ? 'Show top ' + TOP + ' only' : `Show all ${d.players.length} players`;
  more.setAttribute('aria-expanded', S.all);
  d.players.forEach((p, i) => { if (i >= TOP) S.rows[p.name].focusables.forEach(b => b.tabIndex = S.all ? 0 : -1); });
  root.querySelector('.reset').hidden = rm.size === 0;
}

export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement.querySelector('.pp');
  if (!root || !data) return;
  let S = root.__pp;
  if (!S) S = root.__pp = { removed: new Set(), seq: 0, raf: {}, tid: {}, shown: {} };
  S.send = setStateValue;
  const fresh = S.built !== data.id;
  const before = new Set(S.removed);
  S.data = data;
  if (fresh || data.ack >= S.seq) S.removed = new Set(data.removed);   // keep newer local clicks that Python has not seen yet
  if (fresh) { build(root, S); S.built = data.id; S.seq = data.ack; }
  const changed = fresh ? [] : [...new Set([...before, ...S.removed])].filter(n => before.has(n) !== S.removed.has(n));
  changed.forEach(n => ripple(S, n, S.removed.has(n)));               // combo-box changes animate from their player too
  render(root, S, changed);
}
"""

_component = st.components.v2.component("press_pitch", html=HTML, css=CSS, js=JS)


def press_pitch(*, data: dict, key: str, on_removed_change):
    """Mount the pitch. `data` is built by dashboard.payload; the component reports
    {"players": [...], "seq": n} as its `removed` state whenever the user clicks."""
    return _component(data=data, key=key, on_removed_change=on_removed_change)

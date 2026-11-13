/* Materials explorer: scatter of data sheet values, state in ?x=&y=&o=&p=&u=&c=. The table below is the full data and the no-JS view. */
(() => {
  const D = JSON.parse(document.getElementById("mat-data").textContent);
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
  const AX = Object.fromEntries(D.axes.map(([k, l, u, log, f]) => [k, { k, l, u, log, f }]));
  const CLASSES = D.classes.map(c => c[0]), CLASS_LABEL = Object.fromEntries(D.classes), USE_LABEL = Object.fromEntries(D.uses);
  const ST = { x: "elong", y: "uts", o: "xy", p: "", u: "", c: new Set(CLASSES) };

  const q = new URLSearchParams(location.search);
  if (AX[q.get("x")]) ST.x = q.get("x");
  if (AX[q.get("y")]) ST.y = q.get("y");
  if (q.get("o") === "z") ST.o = "z";
  if (D.processes.some(p => p[0] === q.get("p"))) ST.p = q.get("p");
  if (USE_LABEL[q.get("u")]) ST.u = q.get("u");
  if (q.has("c")) ST.c = new Set(q.get("c").split(",").filter(c => CLASSES.includes(c)));

  const axOpts = D.axes.map(([k, l, u]) => `<option value="${k}">${esc(l)} (${esc(u)})</option>`).join("");
  $("#m-x").innerHTML = axOpts; $("#m-y").innerHTML = axOpts;
  $("#m-x").value = ST.x; $("#m-y").value = ST.y;
  $("#m-p").innerHTML = `<option value="">All processes</option>` + D.processes.map(([i, n]) => `<option value="${i}">${esc(n)}</option>`).join("");
  $("#m-p").value = ST.p;
  $("#m-u").innerHTML = `<option value="">All uses</option>` + D.uses.map(([i, n]) => `<option value="${i}">${esc(n)}</option>`).join("");
  $("#m-u").value = ST.u;
  const syncChips = () => {
    $("#m-o").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.v === ST.o));
    $("#m-c").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", ST.c.has(b.dataset.v)));
  };
  syncChips();
  $("#m-o").querySelectorAll("button").forEach(b => b.onclick = () => { ST.o = b.dataset.v; update(); });
  $("#m-c").querySelectorAll("button").forEach(b => b.onclick = () => { const c = b.dataset.v; ST.c.has(c) ? ST.c.delete(c) : ST.c.add(c); update(); });
  [["#m-x", "x"], ["#m-y", "y"], ["#m-p", "p"], ["#m-u", "u"]].forEach(([s, k]) => $(s).addEventListener("change", e => { ST[k] = e.target.value; update(); }));

  // Value of one axis for one grade in the chosen direction, scaled to display units. HDT has no direction.
  const key = (stem, o) => stem === "hdt" ? "hdt_045" : `${stem}_${o}`;
  function val(r, stem, o) {
    const v = r.v[key(stem, o)], f = AX[stem].f;
    return v ? { lo: v.lo * f, hi: v.hi * f, mid: v.mid * f, range: v.lo !== v.hi } : null;
  }
  const fmt = x => x >= 1000 ? Math.round(x).toLocaleString("en-US") : String(+x.toPrecision(3));
  const show = v => v ? (v.range ? `${fmt(v.lo)}–${fmt(v.hi)}` : fmt(v.lo)) : "not published";

  function ticksFor(ax, lo, hi) {
    if (ax.log) {
      const r = Math.log10(hi / lo), a = Math.floor(Math.log10(lo)), b = Math.ceil(Math.log10(hi));
      const mult = r < .8 ? [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8] : r <= 2.3 ? [1, 2, 5] : [1];
      const t = [];
      for (let k = a; k <= b; k++) mult.forEach(m => { const v = m * 10 ** k; if (v >= lo && v <= hi) t.push(+v.toPrecision(3)); });
      return t;
    }
    const step = [10, 20, 25, 50, 100].find(s => (hi - lo) / s <= 7) || 200;
    const t = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) t.push(v);
    return t;
  }
  function domain(ax, vals) {
    let lo = Math.min(...vals.map(v => v.lo)), hi = Math.max(...vals.map(v => v.hi));
    if (ax.log) { const pad = 10 ** (Math.max(.15, Math.log10(hi / lo) * .06)); return [lo / pad, hi * pad]; }
    const pad = Math.max(8, (hi - lo) * .06); return [lo - pad, hi + pad];
  }

  function update() {
    syncChips();
    const u = new URLSearchParams();
    if (ST.x !== "elong") u.set("x", ST.x);
    if (ST.y !== "uts") u.set("y", ST.y);
    if (ST.o !== "xy") u.set("o", ST.o);
    if (ST.p) u.set("p", ST.p);
    if (ST.u) u.set("u", ST.u);
    if (ST.c.size !== CLASSES.length) u.set("c", [...ST.c].join(","));
    const s = u.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
    const inFilter = r => (!ST.p || r.process === ST.p) && (!ST.u || r.use === ST.u) && ST.c.has(r.cls);
    document.querySelectorAll(".mtbl tbody").forEach(tb => {
      const on = !ST.u || tb.dataset.u === ST.u;
      let n = 0;
      tb.querySelectorAll("tr[id]").forEach(tr => { tr.hidden = !(on && (!ST.p || tr.dataset.p === ST.p) && ST.c.has(tr.dataset.c)); n += !tr.hidden; });
      tb.hidden = !n;
    });
    draw(inFilter);
  }

  function draw(inFilter) {
    const svg = $("#m-svg"), box = $("#m-box"), tip = $("#m-tip");
    const W = Math.max(300, box.clientWidth - 12), H = Math.round(Math.min(560, Math.max(360, W * .58)));
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const ax = AX[ST.x], ay = AX[ST.y];
    const sel = D.rows.filter(inFilter);
    const pts = sel.map(r => ({ r, x: val(r, ST.x, ST.o), y: val(r, ST.y, ST.o) })).filter(p => p.x && p.y);
    const missing = sel.length - pts.length;
    const dir = ST.o === "z" && (ST.x !== "hdt" || ST.y !== "hdt") ? " in the build direction (Z)" : "";
    const lc = l => /^[A-Z]{2}/.test(l) ? l : l[0].toLowerCase() + l.slice(1);
    const what = ax.l === ay.l ? lc(ax.l) : `${lc(ax.l)} or ${lc(ay.l)}`;
    $("#m-count").textContent = `${pts.length} of ${D.rows.length} grades plotted.` + (missing ? ` ${missing} of the selected grades have no published value for ${what}${dir}; they stay in the table.` : "");
    const defs = svg.querySelector("defs").outerHTML;
    if (!pts.length) { svg.innerHTML = defs + `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" font-size="13" fill="var(--ink-3)">No grades match these filters.</text>`; return; }

    const M = { l: W < 520 ? 64 : 74, r: 16, t: 14, b: 46 };
    const [x0, x1] = domain(ax, pts.map(p => p.x)), [y0, y1] = domain(ay, pts.map(p => p.y));
    const lin = (v, a, b, p, q2) => p + (v - a) / (b - a) * (q2 - p);
    const sx = v => ax.log ? lin(Math.log10(v), Math.log10(x0), Math.log10(x1), M.l, W - M.r) : lin(v, x0, x1, M.l, W - M.r);
    const sy = v => ay.log ? lin(Math.log10(v), Math.log10(y0), Math.log10(y1), H - M.b, M.t) : lin(v, y0, y1, H - M.b, M.t);

    let g = "";
    ticksFor(ax, x0, x1).forEach(t => { const X = sx(t); g += `<line x1="${X}" x2="${X}" y1="${M.t}" y2="${H - M.b}" stroke="var(--line)"/><text x="${X}" y="${H - M.b + 16}" text-anchor="middle" font-size="11" fill="var(--ink-3)">${fmt(t)}</text>`; });
    ticksFor(ay, y0, y1).forEach(t => { const Y = sy(t); g += `<line x1="${M.l}" x2="${W - M.r}" y1="${Y}" y2="${Y}" stroke="var(--line)"/><text x="${M.l - 8}" y="${Y + 4}" text-anchor="end" font-size="11" fill="var(--ink-3)">${fmt(t)}</text>`; });
    const scale = a => a.log ? ", log scale" : "";
    g += `<text x="${(M.l + W - M.r) / 2}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--ink-2)">${esc(ax.l)} (${esc(ax.u)}${scale(ax)})</text>`;
    g += `<text transform="translate(13 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle" font-size="12" fill="var(--ink-2)">${esc(ay.l)} (${esc(ay.u)}${scale(ay)})</text>`;

    let marks = "", labels = "";
    const cand = [];
    pts.forEach(p => {
      const cx = sx(p.x.mid), cy = sy(p.y.mid), c = `var(--c-${p.r.cls})`;
      let wh = "";
      if (p.x.range) wh += `<line x1="${sx(p.x.lo)}" x2="${sx(p.x.hi)}" y1="${cy}" y2="${cy}" stroke="${c}" stroke-width="1.5"/>`;
      if (p.y.range) wh += `<line x1="${cx}" x2="${cx}" y1="${sy(p.y.lo)}" y2="${sy(p.y.hi)}" stroke="${c}" stroke-width="1.5"/>`;
      marks += `<a href="#g-${p.r.id}" class="pt" data-id="${p.r.id}" data-x="${cx}" data-y="${cy}" aria-label="${esc(p.r.grade)}">${wh}<circle cx="${cx}" cy="${cy}" r="12" fill="transparent"/><use href="#sh-${p.r.cls}" x="${cx}" y="${cy}" fill="${c}" stroke="var(--surface)" stroke-width="2"/></a>`;
      if (ST.p || ST.u) cand.push({ cx, cy, t: p.r.grade });
    });
    // Direct labels when filtered: try right of the point, then left; skip a label that would cover a point or a placed label (the tooltip still names it).
    const placed = cand.map(c => ({ x0: c.cx - 7, x1: c.cx + 7, y0: c.cy - 7, y1: c.cy + 7 })), hit = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
    cand.sort((a, b) => a.cy - b.cy).forEach(c => {
      const w = c.t.length * 7 + 4;
      for (const right of [true, false]) {
        const x0 = right ? c.cx + 9 : c.cx - 9 - w, box = { x0, x1: x0 + w, y0: c.cy - 8, y1: c.cy + 8 };
        if (x0 < M.l || box.x1 > W - M.r || placed.some(b => hit(b, box))) continue;
        placed.push(box);
        labels += `<text x="${right ? c.cx + 10 : c.cx - 10}" y="${c.cy + 4}" text-anchor="${right ? "start" : "end"}" font-size="11.5" fill="var(--ink)" stroke="var(--surface)" stroke-width="3" style="paint-order:stroke;pointer-events:none">${esc(c.t)}</text>`;
        break;
      }
    });
    svg.innerHTML = defs + g + marks + labels;

    const byId = Object.fromEntries(pts.map(p => [p.r.id, p]));
    const other = ST.o === "xy" ? "z" : "xy", oName = { xy: "in-plane", z: "Z" };
    const line = (a, v, r) => {
      const alt = a.k === "hdt" ? null : val(r, a.k, other);
      return `${esc(a.l)}: ${show(v)} ${esc(a.u)}${a.k === "hdt" ? "" : ` ${oName[ST.o]}`}${alt ? ` (${show(alt)} ${oName[other]})` : ""}`;
    };
    svg.querySelectorAll(".pt").forEach(el => {
      const p = byId[el.dataset.id], r = p.r;
      const on = () => {
        tip.hidden = false;
        tip.innerHTML = `<b>${esc(r.grade)}</b><br>${esc(r.vendor)} · ${esc(r.processName)} · ${esc(CLASS_LABEL[r.cls])}${r.use !== "general" ? ` · ${esc(USE_LABEL[r.use])}` : ""}<br>${line(ax, p.x, r)}<br>${ST.y !== ST.x ? line(ay, p.y, r) + "<br>" : ""}<span class="tsub">${esc(r.standard)}; ${esc(r.orientation)}; ${esc(r.condition)}</span>`;
        const sc = box.clientWidth / W, px = +el.dataset.x * sc + 6, py = +el.dataset.y * sc + 10;
        tip.style.left = Math.max(4, Math.min(px + 12, box.clientWidth - 290)) + "px";
        tip.style.top = (py > box.clientHeight * .6 ? py - tip.offsetHeight - 12 : py + 12) + "px";
      };
      el.addEventListener("mouseenter", on); el.addEventListener("focus", on);
      el.addEventListener("mouseleave", () => tip.hidden = true); el.addEventListener("blur", () => tip.hidden = true);
    });
  }

  let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(update, 120); });
  update();
})();

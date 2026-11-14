/* AM Process Atlas: picker, matrix, and map on the home page. Data comes from the JSON block the build embeds. */
(function () {
  const D = JSON.parse(document.getElementById("atlas-data").textContent);
  const P = D.processes, DIMS = D.dims, FAM = Object.fromEntries(D.families.map(f => [f.id, f]));
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const bandIdx = (axis, id) => D.bands[axis].bands.findIndex(b => b.id === id);
  const bandLabel = (axis, id) => (D.bands[axis].bands.find(b => b.id === id) || {}).label || id;
  const famTag = f => `<span class="fam" title="${esc(FAM[f].name)}">${FAM[f].code}</span>`;
  const matTag = p => `<span class="mat ${p.group}">${D.maturityLabels[p.maturity]}</span>`;
  const href = p => `${p.id}.html`;

  /* ---------- tabs ---------- */
  const VIEWS = ["pick", "matrix", "map"];
  function show(v) {
    if (!VIEWS.includes(v)) v = "pick";
    document.querySelectorAll("nav.tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.v === v));
    VIEWS.forEach(x => { $("#v-" + x).hidden = x !== v; });
    if (v === "map") drawMap();
  }
  document.querySelectorAll("nav.tabs button").forEach(b => b.addEventListener("click", () => {
    show(b.dataset.v); history.replaceState(null, "", location.pathname + location.search + "#" + b.dataset.v);
  }));

  /* ---------- picker ---------- */
  const DEFAULT_W = { detail: 1, surface: 1, strength: 3, throughput: 1, size: 1, materials: 1, cost_per_part: 2, system_cost: 1, workflow: 1, freedom: 2 };
  const ST = { mat: "polymer", qty: "bridge", feat: "", part: "", bud: "", caps: new Set(), w: { ...DEFAULT_W } };
  const QTY = [["proto", "Prototype (1–10)"], ["bridge", "Bridge (10–1K)"], ["prod", "Production (1K+)"]];

  // restore shared state from the query string
  const q = new URLSearchParams(location.search);
  if (q.has("m")) ST.mat = q.get("m");
  if (q.has("q")) ST.qty = q.get("q");
  if (q.has("f")) ST.feat = q.get("f");
  if (q.has("s")) ST.part = q.get("s");
  if (q.has("b")) ST.bud = q.get("b");
  if (q.get("c")) q.get("c").split(",").forEach(c => D.capabilities[c] && ST.caps.add(c));
  if (q.get("w")) q.get("w").split("").forEach((n, i) => { if (DIMS[i] && /[0-3]/.test(n)) ST.w[DIMS[i][0]] = +n; });

  $("#p-mat").innerHTML = `<option value="any">Any</option>` + Object.entries(D.materialClasses).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join("");
  $("#p-mat").value = ST.mat;
  $("#p-feat").innerHTML = `<option value="">Any</option>` + D.bands.min_feature.bands.map((b, i) => `<option value="${i}">${esc(b.label)} or finer</option>`).slice(0, 4).join("");
  $("#p-part").innerHTML = `<option value="">Any</option>` + D.bands.max_part.bands.map((b, i) => `<option value="${i}">${esc(b.label)} or larger</option>`).slice(1).join("");
  $("#p-bud").innerHTML = `<option value="">No limit</option>` + D.bands.system_price.bands.filter(b => !b.unranked).slice(0, 4).map((b, i) => `<option value="${i}">${esc(b.label)} or less</option>`).join("");
  $("#p-feat").value = ST.feat; $("#p-part").value = ST.part; $("#p-bud").value = ST.bud;

  $("#p-qty").innerHTML = QTY.map(([v, l]) => `<button class="chip" data-v="${v}" aria-pressed="${ST.qty === v}">${l}</button>`).join("");
  $("#p-qty").querySelectorAll("button").forEach(b => b.onclick = () => {
    ST.qty = b.dataset.v; $("#p-qty").querySelectorAll("button").forEach(z => z.setAttribute("aria-pressed", z === b)); rank();
  });
  $("#p-caps").innerHTML = Object.entries(D.capabilities).map(([k, l]) => `<button class="chip" data-k="${k}" aria-pressed="${ST.caps.has(k)}">${esc(l)}</button>`).join("");
  $("#p-caps").querySelectorAll("button").forEach(b => b.onclick = () => {
    const k = b.dataset.k; ST.caps.has(k) ? ST.caps.delete(k) : ST.caps.add(k); b.setAttribute("aria-pressed", ST.caps.has(k)); rank();
  });
  $("#p-w").innerHTML = DIMS.map(([k, l]) => `<label class="wt" for="w-${k}"><span>${esc(l)}</span><input type="range" id="w-${k}" min="0" max="3" step="1" value="${ST.w[k]}"><output id="o-${k}">${ST.w[k]}</output></label>`).join("");
  DIMS.forEach(([k]) => $("#w-" + k).addEventListener("input", e => { ST.w[k] = +e.target.value; $("#o-" + k).textContent = ST.w[k]; rank(); }));
  [["#p-mat", "mat"], ["#p-feat", "feat"], ["#p-part", "part"], ["#p-bud", "bud"]].forEach(([s, k]) => $(s).addEventListener("change", e => { ST[k] = e.target.value; rank(); }));
  $("#p-reset").onclick = () => { ST.w = { ...DEFAULT_W }; DIMS.forEach(([k]) => { $("#w-" + k).value = ST.w[k]; $("#o-" + k).textContent = ST.w[k]; }); rank(); };

  function shareUrl() {
    const u = new URLSearchParams();
    if (ST.mat !== "polymer") u.set("m", ST.mat);
    if (ST.qty !== "bridge") u.set("q", ST.qty);
    if (ST.feat) u.set("f", ST.feat);
    if (ST.part) u.set("s", ST.part);
    if (ST.bud) u.set("b", ST.bud);
    if (ST.caps.size) u.set("c", [...ST.caps].join(","));
    const w = DIMS.map(([k]) => ST.w[k]).join("");
    if (w !== DIMS.map(([k]) => DEFAULT_W[k]).join("")) u.set("w", w);
    const s = u.toString();
    return location.origin + location.pathname + (s ? "?" + s : "") + "#pick";
  }
  $("#p-share").onclick = () => {
    const url = shareUrl(), b = $("#p-share");
    history.replaceState(null, "", url);
    const done = () => { b.textContent = "Link copied"; setTimeout(() => b.textContent = "Copy link to these settings", 1600); };
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, () => { b.textContent = "Link is in the address bar"; });
    else b.textContent = "Link is in the address bar";
  };

  function weights() {
    const w = {};
    DIMS.forEach(([k]) => w[k] = ST.w[k]);
    if (ST.qty === "proto") { w.system_cost += 1.5; w.workflow += 1.5; w.detail += .5; }
    if (ST.qty === "bridge") { w.cost_per_part += 1.5; w.throughput += 1; w.strength += .5; }
    if (ST.qty === "prod") { w.throughput += 3; w.cost_per_part += 3; w.system_cost *= .2; }
    return w;
  }
  const MMULT = { mature: 1, industrial: 1, niche: .97, emerging: .92, research: .85 };
  function rank() {
    const w = weights(), rows = [];
    let excl = 0;
    P.forEach(p => {
      if (ST.mat !== "any" && !p.materials.includes(ST.mat)) return;
      const out = (ST.feat !== "" && bandIdx("min_feature", p.bands.min_feature) > +ST.feat)
        || (ST.part !== "" && bandIdx("max_part", p.bands.max_part) < +ST.part + 1)
        || (ST.bud !== "" && (p.bands.system_price === "service" || bandIdx("system_price", p.bands.system_price) > +ST.bud))
        || [...ST.caps].some(c => !p.capabilities.includes(c));
      if (out) { excl++; return; }
      let s = 0, ws = 0;
      const contrib = DIMS.map(([k, l]) => { s += w[k] * p.ratings[k]; ws += w[k]; return { l, v: p.ratings[k], w: w[k] }; });
      const sc = ws ? (s / ws - 1) / 4 * 100 * MMULT[p.maturity] : 0;
      const why = contrib.filter(c => c.v >= 4 && c.w >= 1).sort((a, b) => b.w * b.v - a.w * a.v).slice(0, 3).map(c => c.l.toLowerCase());
      const watch = contrib.filter(c => c.w >= 2 && c.v <= 2).map(c => c.l.toLowerCase());
      rows.push({ p, sc, why, watch });
    });
    rows.sort((a, b) => b.sc - a.sc);
    $("#p-count").textContent = `${rows.length} match${rows.length === 1 ? "" : "es"}${excl ? ` · ${excl} ruled out by requirements` : ""}`;
    $("#p-res").innerHTML = rows.length ? rows.slice(0, 10).map((r, i) => `
      <a class="res" href="${href(r.p)}">
        <span class="rk">${i + 1}</span>
        <span style="min-width:0"><span class="nm">${esc(r.p.name)}</span>
          <div class="why">${r.why.length ? "Strong on " + r.why.join(", ") : "No standout strength for these priorities"}</div>
          ${r.watch.length ? `<div class="watch">Weak on ${r.watch.join(", ")}</div>` : ""}
          <div class="tags">${famTag(r.p.family)}<span class="fam">${esc(bandLabel("system_price", r.p.bands.system_price))}</span>${matTag(r.p)}</div></span>
        <span class="sc"><div class="score">${Math.round(r.sc)}</div><div class="bar"><i style="width:${Math.max(2, r.sc)}%"></i></div></span>
      </a>`).join("") : `<div class="panel sub">No process meets every requirement. Loosen a requirement or change the material.</div>`;
  }

  /* ---------- matrix ---------- */
  const COLS = [
    { k: "name", l: "Process", get: p => p.name },
    { k: "family", l: "Family", get: p => FAM[p.family].code },
    { k: "maturity", l: "Maturity", get: p => D.maturityOrder.indexOf(p.maturity) },
    { k: "system_price", l: "Entry system", get: p => p.bands.system_price === "service" ? 99 : bandIdx("system_price", p.bands.system_price), band: 1 },
    { k: "min_feature", l: "Smallest feature", get: p => bandIdx("min_feature", p.bands.min_feature), band: 1 },
    { k: "max_part", l: "Largest part", get: p => bandIdx("max_part", p.bands.max_part), band: 1 },
    ...DIMS.map(([k, l]) => ({ k, l, get: p => p.ratings[k], heat: 1 }))
  ];
  const MS = { key: "family", dir: 1 };
  $("#m-fam").innerHTML = `<option value="">All</option>` + D.families.map(f => `<option value="${f.id}">${f.code} · ${esc(f.name)}</option>`).join("");
  $("#m-mat").innerHTML = `<option value="">All</option>` + D.maturityOrder.map(m => `<option value="${m}">${D.maturityLabels[m]}</option>`).join("");
  ["#m-q", "#m-fam", "#m-mat"].forEach(s => $(s).addEventListener("input", drawMatrix));
  function drawMatrix() {
    const qs = $("#m-q").value.trim().toLowerCase(), f = $("#m-fam").value, mm = $("#m-mat").value;
    const rows = P.filter(p => (!f || p.family === f) && (!mm || p.maturity === mm) && (!qs || p.search.includes(qs)));
    const col = COLS.find(c => c.k === MS.key);
    rows.sort((a, b) => { const A = col.get(a), B = col.get(b); return (A < B ? -1 : A > B ? 1 : 0) * MS.dir || a.name.localeCompare(b.name); });
    $("#m-count").textContent = `${rows.length} of ${P.length} processes`;
    $("#m-tbl").innerHTML = "<thead><tr>" + COLS.map(c => `<th class="sortable" data-k="${c.k}" aria-sort="${MS.key === c.k ? (MS.dir > 0 ? "ascending" : "descending") : "none"}">${esc(c.l)} ${MS.key === c.k ? (MS.dir > 0 ? "↑" : "↓") : ""}</th>`).join("") + "</tr></thead><tbody>" +
      rows.map(p => `<tr><td class="nm"><a href="${href(p)}">${esc(p.name)}</a></td><td>${famTag(p.family)}</td><td>${matTag(p)}</td>
        <td class="band">${esc(bandLabel("system_price", p.bands.system_price))}</td><td class="band">${esc(bandLabel("min_feature", p.bands.min_feature))}</td><td class="band">${esc(bandLabel("max_part", p.bands.max_part))}</td>
        ${DIMS.map(([k]) => `<td class="h"><span class="h${p.ratings[k]}">${p.ratings[k]}</span></td>`).join("")}</tr>`).join("") + "</tbody>";
    $("#m-tbl").querySelectorAll("th.sortable").forEach(th => th.onclick = () => {
      const k = th.dataset.k; if (MS.key === k) MS.dir *= -1; else { MS.key = k; MS.dir = COLS.find(c => c.k === k).heat ? -1 : 1; } drawMatrix();
    });
  }

  /* ---------- map ---------- */
  const AX = [
    ...["system_price", "min_feature", "max_part"].map(a => ({ k: a, l: D.bands[a].label, ticks: D.bands[a].bands.filter(b => !b.unranked).map(b => b.label), get: p => p.bands[a] === "service" ? null : bandIdx(a, p.bands[a]) })),
    ...DIMS.map(([k, l]) => ({ k, l: l + " (rating)", ticks: ["1", "2", "3", "4", "5"], get: p => p.ratings[k] - 1 }))
  ];
  ["#x-ax", "#y-ax"].forEach(s => $(s).innerHTML = AX.map(a => `<option value="${a.k}">${esc(a.l)}</option>`).join(""));
  $("#x-ax").value = "system_price"; $("#y-ax").value = "detail";
  $("#g-fam").innerHTML = `<option value="">All families</option>` + D.families.map(f => `<option value="${f.id}">${f.code} · ${esc(f.name)}</option>`).join("");
  ["#x-ax", "#y-ax", "#g-fam"].forEach(s => $(s).addEventListener("change", drawMap));
  const hash = s => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); };
  // monospace width estimate (IBM Plex Mono is 0.6em a character)
  const textW = (s, fs) => s.length * fs * 0.6;
  // split a tick label into at most two lines when it is wider than maxW, breaking after an en dash or at a space
  const wrapTick = (s, fs, maxW) => {
    if (textW(s, fs) <= maxW) return [s];
    let best = null;
    for (let i = 1; i < s.length; i++) {
      const a = s[i - 1] === "–" ? s.slice(0, i) : s[i] === " " ? s.slice(0, i) : null;
      if (a === null) continue;
      const b = s.slice(i).trim(), m = Math.max(a.length, b.length);
      if (!best || m < best[2]) best = [a, b, m];
    }
    return best ? [best[0], best[1]] : [s];
  };
  const overlap = (a, b) => Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  function drawMap() {
    const svg = $("#map-svg"), box = $("#mapbox"), key = $("#mapkey");
    const W = Math.max(300, box.clientWidth - 12), narrow = W < 560;
    const H = Math.round(Math.min(600, Math.max(narrow ? 420 : 380, W * .6)));
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const ax = AX.find(a => a.k === $("#x-ax").value), ay = AX.find(a => a.k === $("#y-ax").value), hf = $("#g-fam").value;
    const pts = P.filter(p => ax.get(p) != null && ay.get(p) != null);
    const fs = narrow ? 10 : 11;
    // left margin sized to the widest y tick (two lines allowed on phones), plus the rotated axis title
    const yLines = ay.ticks.map(t => wrapTick(t, fs, narrow ? 62 : 96));
    const yTickW = Math.max(...yLines.flat().map(s => textW(s, fs)));
    const M = { l: Math.round(Math.max(44, 30 + yTickW + 10)), r: narrow ? 8 : 18, t: 14, b: 46 };
    const cw = (W - M.r - M.l) / ax.ticks.length;
    const xLines = ax.ticks.map(t => wrapTick(t, fs, cw - 6));
    if (xLines.some(l => l.length > 1)) M.b += 12;
    const ch = (H - M.b - M.t) / ay.ticks.length;
    const sx = v => M.l + (v + .5) * cw, sy = v => (H - M.b) - (v + .5) * ch;
    const tspans = (lines, x, lh) => lines.map((s, i) => `<tspan x="${x}" dy="${i ? lh : 0}">${esc(s)}</tspan>`).join("");
    let g = "";
    ax.ticks.forEach((t, i) => { const X = sx(i); g += `<line x1="${X - cw / 2}" x2="${X - cw / 2}" y1="${M.t}" y2="${H - M.b}" stroke="var(--line)"/><text x="${X}" y="${H - M.b + 16}" text-anchor="middle" font-size="${fs}" fill="var(--ink-3)">${tspans(xLines[i], X, fs + 2)}</text>`; });
    ay.ticks.forEach((t, i) => { const Y = sy(i), n = yLines[i].length; g += `<line x1="${M.l}" x2="${W - M.r}" y1="${Y + ch / 2}" y2="${Y + ch / 2}" stroke="var(--line)"/><text x="${M.l - 8}" y="${Y + 4 - (n - 1) * (fs + 2) / 2}" text-anchor="end" font-size="${fs}" fill="var(--ink-3)">${tspans(yLines[i], M.l - 8, fs + 2)}</text>`; });
    g += `<text x="${(M.l + W - M.r) / 2}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--ink-2)">${esc(ax.l)}</text>`;
    g += `<text transform="translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle" font-size="12" fill="var(--ink-2)">${esc(ay.l)}</text>`;
    // spread points that share a cell on a small deterministic grid so none hide another
    const cells = {};
    pts.forEach(p => { const k = ax.get(p) + "," + ay.get(p); (cells[k] = cells[k] || []).push(p); });
    const R = narrow && hf ? 8 : 6, pos = [];
    Object.values(cells).forEach(list => {
      list.sort((a, b) => hash(a.id) - hash(b.id));
      const n = list.length, cols = Math.ceil(Math.sqrt(n)), rowsN = Math.ceil(n / cols);
      const step = Math.min(narrow && hf ? 19 : 18, (cw - 8) / cols, (ch - 8) / rowsN);
      list.forEach((p, i) => pos.push({ p, cx: sx(ax.get(p)) + ((i % cols) - (cols - 1) / 2) * step, cy: sy(ay.get(p)) + (Math.floor(i / cols) - (rowsN - 1) / 2) * step, dim: hf && p.family !== hf }));
    });
    const fill = p => `var(--${p.group === "mature" ? "m1" : p.group === "industrial" ? "m2" : "m3"})`;
    const lit = pos.filter(d => !d.dim).sort((a, b) => a.cx - b.cx || a.cy - b.cy);
    let dots = "", labels = "";
    pos.filter(d => d.dim).concat(lit).forEach(d => {
      const r = d.dim ? 5 : R, num = hf && narrow && !d.dim ? lit.indexOf(d) + 1 : 0;
      dots += `<a href="${href(d.p)}" class="pt" data-id="${d.p.id}" data-x="${d.cx}" data-y="${d.cy}" style="opacity:${d.dim ? .15 : 1}" aria-label="${esc(d.p.name)}"><circle cx="${d.cx}" cy="${d.cy}" r="12" fill="transparent"/><circle cx="${d.cx}" cy="${d.cy}" r="${r}" fill="${fill(d.p)}" stroke="var(--surface)" stroke-width="${num ? 1.5 : 2}"/>`
        + (num ? `<text x="${d.cx}" y="${d.cy + 3.3}" text-anchor="middle" font-size="9.5" font-weight="600" fill="#fff" style="pointer-events:none">${num}</text>` : "") + `</a>`;
    });
    if (hf && narrow) {
      // phones: numbered dots and a key, since full names do not fit in cells this small
      key.innerHTML = lit.map((d, i) => `<li><span class="kn" style="background:${fill(d.p)}">${i + 1}</span><a href="${href(d.p)}">${esc(d.p.name)}</a></li>`).join("");
      key.hidden = !lit.length;
    } else {
      key.hidden = true; key.innerHTML = "";
      if (hf) {
        // wider screens: name every highlighted dot, taking the first of ten spots that overlaps no dot or label
        const lf = 11.5, lh = 13, placed = lit.map(d => [d.cx - R - 2, d.cy - R - 2, d.cx + R + 2, d.cy + R + 2]);
        const faint = pos.filter(d => d.dim).map(d => [d.cx - 5, d.cy - 5, d.cx + 5, d.cy + 5]);
        lit.forEach((d, i) => {
          const tw = textW(d.p.name, lf), { cx, cy } = d, o = R + 4;
          const cands = [[cx + o, cy + 4, "start"], [cx - o, cy + 4, "end"], [cx, cy - o - 3, "middle"], [cx, cy + o + 10, "middle"],
            [cx + o - 2, cy - o, "start"], [cx + o - 2, cy + o + 8, "start"], [cx - o + 2, cy - o, "end"], [cx - o + 2, cy + o + 8, "end"],
            [cx, cy - o - 17, "middle", 1], [cx, cy + o + 24, "middle", 1]];
          const score = c => {
            const x0 = c[2] === "start" ? c[0] : c[2] === "end" ? c[0] - tw : c[0] - tw / 2, b = [x0, c[1] - lh + 3, x0 + tw, c[1] + 3];
            const out = b[0] < M.l - 4 || b[2] > W - 2 || b[1] < 0 || b[3] > H - M.b + 2;
            const hit = placed.reduce((s, q, j) => s + (j === i ? 0 : overlap(b, q)), 0) + .2 * faint.reduce((s, q) => s + overlap(b, q), 0);
            return [out ? 1 : 0, hit, b];
          };
          let best = null;
          for (const c of cands) { const s = score(c); if (!best || s[0] < best.s[0] || (s[0] === best.s[0] && s[1] < best.s[1] - .5)) best = { c, s }; if (!s[0] && !s[1]) break; }
          const [tx, ty, anchor, far] = best.c;
          placed.push(best.s[2]);
          if (far) labels += `<line x1="${cx}" y1="${cy + (ty < cy ? -R : R)}" x2="${tx}" y2="${ty < cy ? ty + 3 : ty - lh + 3}" stroke="var(--ink-3)" stroke-width="1"/>`;
          labels += `<text x="${tx}" y="${ty}" text-anchor="${anchor}" font-size="${lf}" fill="var(--ink)" stroke="var(--surface)" stroke-width="3" style="paint-order:stroke;pointer-events:none">${esc(d.p.name)}</text>`;
        });
      }
    }
    svg.innerHTML = g + dots + labels;
    const tip = $("#tip"), byId = Object.fromEntries(P.map(p => [p.id, p]));
    svg.querySelectorAll(".pt").forEach(el => {
      const p = byId[el.dataset.id];
      const on = () => {
        tip.hidden = false;
        tip.innerHTML = `<b>${esc(p.name)}</b><br>${FAM[p.family].code} · ${D.maturityLabels[p.maturity]}<br>${esc(ax.l)}: ${esc(ax.ticks[ax.get(p)])}<br>${esc(ay.l)}: ${esc(ay.ticks[ay.get(p)])}`;
        const sc = box.clientWidth / W, px = +el.dataset.x * sc + 6, py = +el.dataset.y * sc + 10;
        tip.style.left = Math.max(4, Math.min(px + 12, box.clientWidth - 270)) + "px"; tip.style.top = (py + 12) + "px";
      };
      el.addEventListener("mouseenter", on); el.addEventListener("focus", on);
      el.addEventListener("mouseleave", () => tip.hidden = true); el.addEventListener("blur", () => tip.hidden = true);
    });
  }
  let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (!$("#v-map").hidden) drawMap(); }, 120); });

  rank(); drawMatrix();
  show((location.hash || "").slice(1));
})();

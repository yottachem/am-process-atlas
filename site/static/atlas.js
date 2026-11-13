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
  function drawMap() {
    const svg = $("#map-svg"), box = $("#mapbox");
    const W = Math.max(320, box.clientWidth - 12), H = Math.round(Math.min(600, Math.max(380, W * .6)));
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const ax = AX.find(a => a.k === $("#x-ax").value), ay = AX.find(a => a.k === $("#y-ax").value), hf = $("#g-fam").value;
    const pts = P.filter(p => ax.get(p) != null && ay.get(p) != null);
    const M = { l: W < 520 ? 92 : 112, r: 18, t: 14, b: 46 };
    const sx = v => M.l + (v + .5) / ax.ticks.length * (W - M.r - M.l), sy = v => (H - M.b) - (v + .5) / ay.ticks.length * (H - M.b - M.t);
    const cw = (W - M.r - M.l) / ax.ticks.length, ch = (H - M.b - M.t) / ay.ticks.length;
    // spread points that share a cell on a small deterministic grid so none hide another
    const cells = {};
    pts.forEach(p => { const key = ax.get(p) + "," + ay.get(p); (cells[key] = cells[key] || []).push(p); });
    let g = "";
    ax.ticks.forEach((t, i) => { const X = sx(i); g += `<line x1="${X - cw / 2}" x2="${X - cw / 2}" y1="${M.t}" y2="${H - M.b}" stroke="var(--line)"/><text x="${X}" y="${H - M.b + 16}" text-anchor="middle" font-size="11" fill="var(--ink-3)">${esc(t)}</text>`; });
    ay.ticks.forEach((t, i) => { const Y = sy(i); g += `<line x1="${M.l}" x2="${W - M.r}" y1="${Y + ch / 2}" y2="${Y + ch / 2}" stroke="var(--line)"/><text x="${M.l - 8}" y="${Y + 4}" text-anchor="end" font-size="11" fill="var(--ink-3)">${esc(t)}</text>`; });
    g += `<text x="${(M.l + W - M.r) / 2}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--ink-2)">${esc(ax.l)}</text>`;
    g += `<text transform="translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle" font-size="12" fill="var(--ink-2)">${esc(ay.l)}</text>`;
    let dots = "", labels = "";
    Object.values(cells).forEach(list => {
      list.sort((a, b) => hash(a.id) - hash(b.id));
      const n = list.length, cols = Math.ceil(Math.sqrt(n)), rowsN = Math.ceil(n / cols), step = Math.min(18, (cw - 16) / cols, (ch - 16) / rowsN);
      list.forEach((p, i) => {
        const cx = sx(ax.get(p)) + ((i % cols) - (cols - 1) / 2) * step, cy = sy(ay.get(p)) + (Math.floor(i / cols) - (rowsN - 1) / 2) * step;
        const dim = hf && p.family !== hf;
        dots += `<a href="${href(p)}" class="pt" data-id="${p.id}" data-x="${cx}" data-y="${cy}" style="opacity:${dim ? .15 : 1}" aria-label="${esc(p.name)}"><circle cx="${cx}" cy="${cy}" r="12" fill="transparent"/><circle cx="${cx}" cy="${cy}" r="6" fill="var(--${p.group === "mature" ? "m1" : p.group === "industrial" ? "m2" : "m3"})" stroke="var(--surface)" stroke-width="2"/></a>`;
        if (hf && !dim) { const right = cx < W - 160; labels += `<text x="${cx + (right ? 10 : -10)}" y="${cy + 4}" text-anchor="${right ? "start" : "end"}" font-size="11.5" fill="var(--ink)" stroke="var(--surface)" stroke-width="3" style="paint-order:stroke;pointer-events:none">${esc(p.name)}</text>`; }
      });
    });
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

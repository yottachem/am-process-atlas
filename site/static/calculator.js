/* Buy vs outsource calculator. compute() mirrors atlas/calc.py (tests run both); inputs live in the query string. */
const HOURS_PER_YEAR = 8760;

function compute(x) {
  const perL = x.unit === "L" ? x.matPrice / 1000 : x.matPrice * x.density / 1000;  // $ per cm³
  const mat = x.partVol * perL * (1 + x.waste / 100);
  const s = x.success / 100, good = x.perBuild * s;
  const labor = x.laborMin / 60 * x.rate;
  const buildCost = mat * x.perBuild + x.consum + labor;
  const v = buildCost / good;
  const fixed = x.price / x.years + x.price * x.svc / 100;
  const builds = Math.floor(HOURS_PER_YEAR * x.util / 100 / x.buildHrs);
  const cap = builds * good;
  const margin = x.quote - v;
  const be = margin > 0 ? fixed / margin : null;
  const d = x.demand;
  const machines = cap ? Math.max(1, Math.ceil(d / cap)) : null;
  const annualIn = machines ? machines * fixed + d * v : null;
  return { mat, var: v, fixed, builds, cap, breakeven: be, reachable: be !== null && be <= cap, machines,
           perPart: annualIn && d ? annualIn / d : null, annualIn, annualOut: d * x.quote,
           parts: { material: mat * x.perBuild / good, consum: x.consum / good, labor: labor / good } };
}
// In-house cost per part at volume n, adding printers as volume outgrows capacity.
const costAt = (r, n) => r.var + Math.max(1, Math.ceil(n / r.cap)) * r.fixed / n;

if (typeof module !== "undefined") module.exports = { compute, costAt };

if (typeof document !== "undefined") (() => {
  const D = JSON.parse(document.getElementById("calc-data").textContent);
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
  const KEYS = D.inputs.map(i => i[0]);
  const ST = { ...D.defaults, preset: "", name: "" };
  const presetBy = Object.fromEntries(D.presets.map(p => [p.id, p]));

  // My printers: named input sets kept in this browser only. preset is "" (custom), a sourced id, or "my:<name>".
  const STORE = "atlas-calc-printers";
  const loadMine = () => { try { const a = JSON.parse(localStorage.getItem(STORE) || "[]"); return Array.isArray(a) ? a : []; } catch { return []; } };
  const saveMine = a => { try { localStorage.setItem(STORE, JSON.stringify(a)); return true; } catch { return false; } };
  let mine = loadMine();
  const myId = n => "my:" + n, isMine = id => id.startsWith("my:");

  const q = new URLSearchParams(location.search);
  KEYS.forEach(k => { const n = parseFloat(q.get(k)); if (q.has(k) && isFinite(n) && n >= 0) ST[k] = n; });
  if (q.get("unit") === "L") ST.unit = "L";
  ST.name = (q.get("name") || "").slice(0, 60);
  if (presetBy[q.get("preset")]) { ST.preset = q.get("preset"); if (!q.has("price")) ST.price = presetBy[ST.preset].price; }

  const money = n => n == null ? "–" : "$" + (Math.abs(n) >= 1000 ? Math.round(n).toLocaleString("en-US") : n.toFixed(2));
  const int = n => Math.round(n).toLocaleString("en-US");
  const fmtN = n => n >= 1000 ? int(n) : String(+n.toPrecision(3));

  function fillMine() {
    const g = $("#k-mine");
    g.innerHTML = mine.map(m => `<option value="${esc(myId(m.name))}">${esc(m.name)}</option>`).join("");
    g.hidden = !mine.length;
  }

  function syncForm() {
    KEYS.forEach(k => { const el = $(`#k-${k}`); if (+el.value !== ST[k] || el.value === "") el.value = ST[k]; });
    $("#k-unit").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.v === ST.unit));
    $("#f-density").hidden = ST.unit === "L";
    $("#k-preset").value = ST.preset;
    if ($("#k-name") !== document.activeElement) $("#k-name").value = ST.name;
    const p = presetBy[ST.preset];
    $("#f-name").hidden = !!p;
    $("#k-del").hidden = !isMine(ST.preset);
    $("#k-preset-note").innerHTML = p
      ? `Example: ${esc(p.label)}, ${esc(p.text)} (${p.basis === "list" ? "list price" : "reported"}, <a href="${esc(p.source)}" rel="noopener">${esc(p.publisher)}</a>, ${esc(p.as_of)}).${/–|to |from/i.test(p.text) ? " The lower figure is used." : ""} Printer only; edit any field to make it your own.`
      : isMine(ST.preset) ? "Saved in this browser. Changes are not kept until you save again."
      : `Enter your own figures, or pick a sourced price from the <a href="landscape.html">landscape</a> page (printer only; post-processing equipment is extra).`;
  }

  // Editing any input on a sourced example turns it into a custom printer; on a saved printer it stays selected until saved.
  KEYS.forEach(k => $(`#k-${k}`).addEventListener("input", e => {
    const n = parseFloat(e.target.value);
    ST[k] = isFinite(n) ? n : NaN;
    if (presetBy[ST.preset]) { ST.preset = ""; syncForm(); }
    update(false);
  }));
  $("#k-name").addEventListener("input", e => {
    ST.name = e.target.value.slice(0, 60);
    if (isMine(ST.preset) && ST.preset !== myId(ST.name.trim())) { ST.preset = ""; syncForm(); }
    update(false);
  });
  $("#k-unit").querySelectorAll("button").forEach(b => b.onclick = () => { ST.unit = b.dataset.v; if (presetBy[ST.preset]) ST.preset = ""; update(); });
  $("#k-preset").addEventListener("change", e => {
    const id = e.target.value;
    ST.preset = id;
    if (presetBy[id]) { ST.price = presetBy[id].price; ST.name = ""; }
    else if (isMine(id)) { const m = mine.find(x => myId(x.name) === id); if (m) Object.assign(ST, m.v, { name: m.name }); }
    update();
  });
  $("#k-save").onclick = () => {
    const name = ST.name.trim(), note = $("#k-save-note");
    if (!name) { note.textContent = "Enter a printer name first."; $("#k-name").focus(); return; }
    const v = Object.fromEntries([...KEYS, "unit"].map(k => [k, ST[k]]));
    mine = [...mine.filter(m => m.name !== name), { name, v }].sort((a, b) => a.name.localeCompare(b.name));
    note.textContent = saveMine(mine) ? `Saved "${name}" in this browser.` : "This browser is blocking storage, so it can't be saved. The page link still keeps your values.";
    ST.name = name; ST.preset = myId(name); fillMine(); update();
  };
  $("#k-del").onclick = () => {
    const name = ST.preset.slice(3);
    mine = mine.filter(m => m.name !== name); saveMine(mine);
    $("#k-save-note").textContent = `Removed "${name}".`;
    ST.preset = ""; fillMine(); update();
  };
  $("#k-reset").onclick = () => { Object.assign(ST, D.defaults, { preset: "", name: "" }); update(); };
  fillMine();
  const printerName = () => presetBy[ST.preset] ? presetBy[ST.preset].label : ST.name.trim();

  function update(sync = true) {
    if (sync) syncForm();
    else $("#f-density").hidden = ST.unit === "L";
    const u = new URLSearchParams();
    // Share link: sourced examples by id (their price is implied); custom and saved printers carry every changed value and the name.
    const sourced = !!presetBy[ST.preset];
    KEYS.forEach(k => { if (isFinite(ST[k]) && ST[k] !== D.defaults[k] && !(k === "price" && sourced)) u.set(k, ST[k]); });
    if (ST.unit !== "kg") u.set("unit", ST.unit);
    if (sourced) u.set("preset", ST.preset);
    if (!sourced && ST.name.trim()) u.set("name", ST.name.trim());
    const s = u.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));

    const label = Object.fromEntries(D.inputs.map(i => [i[0], i[1]]));
    const bad = KEYS.filter(k => !isFinite(ST[k]) || ST[k] < 0);
    const zero = ["years", "perBuild", "buildHrs", "success", "util", "demand"].filter(k => !bad.includes(k) && ST[k] <= 0);
    const err = $("#k-err");
    if (bad.length || zero.length || ST.success > 100 || ST.util > 100) {
      err.hidden = false;
      err.textContent = bad.length ? `Enter a number of zero or more for: ${bad.map(k => label[k].toLowerCase()).join(", ")}.`
        : zero.length ? `These need to be above zero: ${zero.map(k => label[k].toLowerCase()).join(", ")}.`
        : "Build success rate and utilization can't exceed 100%.";
      return;
    }
    const r = compute(ST);
    if (!r.cap) { err.hidden = false; err.textContent = "At this utilization the printer finishes no builds in a year. Raise utilization or shorten the build time."; return; }
    err.hidden = true;
    tiles(r); breakdown(r); volumes(r); draw(r);
  }

  function tiles(r) {
    let be;
    if (r.breakeven === null) be = ["None", `The quote is at or below the in-house cost of materials, consumables, and labor (${money(r.var)} a part), so owning never pays back.`];
    else if (!r.reachable) be = ["Out of reach", `Break-even would be ${int(Math.ceil(r.breakeven))} parts a year, but one printer makes at most ${int(r.cap)} good parts a year at this utilization, and each added printer adds the same fixed cost.`];
    else be = [`${int(Math.ceil(r.breakeven))} parts a year`, `Above this volume, owning costs less per part than the ${money(ST.quote)} quote.`];
    const diff = r.annualOut - r.annualIn, cheaper = diff > 0 ? "in-house" : "outsourcing";
    $("#k-tiles").innerHTML = [
      ["Break-even volume", be[0], be[1]],
      ["In-house cost per part", money(r.perPart), `${printerName() ? esc(printerName()) + ", at" : "At"} ${int(ST.demand)} parts a year, against a ${money(ST.quote)} quote.`],
      ["Annual cost", `${money(r.annualIn)} vs ${money(r.annualOut)}`, Math.abs(diff) < 0.5 ? "In-house and outsourcing cost the same." : `In-house vs outsourced. ${cheaper[0].toUpperCase() + cheaper.slice(1)} saves ${money(Math.abs(diff))} a year.`],
      ["Capacity per printer", `${int(r.cap)} parts a year`, `${int(r.builds)} builds a year. Your volume needs ${r.machines} printer${r.machines > 1 ? "s" : ""}.`],
    ].map(([k, v, s]) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="sub">${s}</div></div>`).join("");
  }

  function breakdown(r) {
    const fixedShare = r.machines * r.fixed / ST.demand;
    const rows = [["Material, including waste and failed builds", r.parts.material], ["Consumables and energy", r.parts.consum],
                  ["Labor", r.parts.labor], [`Depreciation and service (${money(r.fixed * r.machines)} a year over ${int(ST.demand)} parts)`, fixedShare]];
    $("#k-break").innerHTML = `<thead><tr><th>Per good part</th><th style="text-align:right">Cost</th><th style="text-align:right">Share</th></tr></thead><tbody>`
      + rows.map(([l, v]) => `<tr><td>${esc(l)}</td><td class="band" style="text-align:right">${money(v)}</td><td class="band" style="text-align:right">${Math.round(v / r.perPart * 100)}%</td></tr>`).join("")
      + `<tr class="tot"><td>In-house total</td><td class="band" style="text-align:right">${money(r.perPart)}</td><td></td></tr></tbody>`;
  }

  function volumes(r) {
    const set = new Set([100, 300, 1000, 3000, 10000, 30000, 100000, Math.round(ST.demand)]);
    if (r.breakeven && r.reachable) set.add(Math.ceil(r.breakeven));
    const vs = [...set].filter(n => n > 0).sort((a, b) => a - b);
    $("#k-vol").innerHTML = `<thead><tr><th>Parts a year</th><th style="text-align:right">Printers</th><th style="text-align:right">In-house per part</th><th style="text-align:right">Service quote</th><th>Cheaper</th></tr></thead><tbody>`
      + vs.map(n => { const c = costAt(r, n), m = Math.max(1, Math.ceil(n / r.cap));
        const tag = n === Math.round(ST.demand) ? " (your volume)" : r.breakeven && n === Math.ceil(r.breakeven) && r.reachable ? " (break-even)" : "";
        return `<tr${tag ? ' class="tot"' : ""}><td class="band">${int(n)}${tag}</td><td class="band" style="text-align:right">${m}</td><td class="band" style="text-align:right">${money(c)}</td><td class="band" style="text-align:right">${money(ST.quote)}</td><td>${Math.abs(c - ST.quote) < 0.005 ? "Equal" : c < ST.quote ? "In-house" : "Outsource"}</td></tr>`; }).join("")
      + "</tbody>";
  }

  // Log ticks at 1-2-5 when each gets at least 60 px, else at powers of ten.
  function ticks(lo, hi, px) {
    const t = [], a = Math.floor(Math.log10(lo)), b = Math.ceil(Math.log10(hi)), mult = px / (Math.log10(hi / lo) * 3) >= 60 ? [1, 2, 5] : [1];
    for (let k = a; k <= b; k++) mult.forEach(m => { const v = m * 10 ** k; if (v >= lo * 0.999 && v <= hi * 1.001) t.push(v); });
    return t;
  }

  function draw(r) {
    const svg = $("#k-svg"), box = $("#k-box"), tip = $("#k-tip");
    const W = Math.max(300, box.clientWidth - 12), H = Math.round(Math.min(420, Math.max(300, W * .5)));
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const M = { l: W < 520 ? 58 : 66, r: 16, t: 14, b: 44 };
    const anchor = [ST.demand, r.breakeven && r.reachable ? r.breakeven : ST.demand];
    const x0 = 10 ** Math.floor(Math.log10(Math.max(1, Math.min(...anchor) / 8)));
    const x1 = 10 ** Math.ceil(Math.log10(Math.max(...anchor) * 8));
    const N = 240, xs = [];
    for (let i = 0; i <= N; i++) xs.push(x0 * (x1 / x0) ** (i / N));
    for (let k = 1; k * r.cap < x1; k++) if (k * r.cap > x0) xs.push(k * r.cap, k * r.cap * 1.0001);  // crisp steps at each added printer
    xs.sort((a, b) => a - b);
    const ys = xs.map(n => costAt(r, n));
    // y spans the variable-cost floor to a few times the quote; the steep low-volume end of the curve is clipped.
    const y0 = Math.max(0.01, Math.min(r.var, ST.quote) * 0.7), y1 = Math.max(ST.quote, costAt(r, ST.demand)) * 3;
    const lx = v => M.l + (Math.log10(v) - Math.log10(x0)) / (Math.log10(x1) - Math.log10(x0)) * (W - M.l - M.r);
    const ly = v => H - M.b - (Math.log10(Math.max(v, y0 / 10)) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0)) * (H - M.t - M.b);
    let g = "";
    let right = -Infinity;  // skip a tick label that would overlap the previous one
    ticks(x0, x1, W - M.l - M.r).forEach(t => {
      const X = lx(t), s = fmtN(t), w = s.length * 6.8, cx = Math.min(X, W - M.r - w / 2);
      g += `<line x1="${X}" x2="${X}" y1="${M.t}" y2="${H - M.b}" stroke="var(--line)"/>`;
      if (cx - w / 2 < right + 8) return;
      right = cx + w / 2;
      g += `<text x="${cx}" y="${H - M.b + 16}" text-anchor="middle" font-size="11" fill="var(--ink-3)">${s}</text>`;
    });
    ticks(y0, y1, H - M.t - M.b).forEach(t => { const Y = ly(t); g += `<line x1="${M.l}" x2="${W - M.r}" y1="${Y}" y2="${Y}" stroke="var(--line)"/><text x="${M.l - 8}" y="${Y + 4}" text-anchor="end" font-size="11" fill="var(--ink-3)">${money(t).replace(".00", "")}</text>`; });
    g += `<text x="${(M.l + W - M.r) / 2}" y="${H - 6}" text-anchor="middle" font-size="12" fill="var(--ink-2)">Parts a year</text>`;
    g += `<text transform="translate(13 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle" font-size="12" fill="var(--ink-2)">Cost per part ($)</text>`;
    g += `<clipPath id="k-clip"><rect x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}"/></clipPath>`;
    const path = xs.map((n, i) => `${i ? "L" : "M"}${lx(n).toFixed(1)} ${ly(ys[i]).toFixed(1)}`).join("");
    const qY = ly(ST.quote);
    g += `<g clip-path="url(#k-clip)"><line x1="${M.l}" x2="${W - M.r}" y1="${qY}" y2="${qY}" stroke="var(--c-out)" stroke-width="2"/><path d="${path}" fill="none" stroke="var(--c-in)" stroke-width="2" stroke-linejoin="round"/></g>`;
    const lab = (x, y, t, anchor = "start") => `<text x="${x}" y="${y}" text-anchor="${anchor}" font-size="11.5" fill="var(--ink)" stroke="var(--surface)" stroke-width="3" style="paint-order:stroke">${esc(t)}</text>`;
    // Series labels at the right end: whichever line is higher gets its label above, the other below.
    const inY = ly(ys[ys.length - 1]), inAbove = inY < qY;
    g += lab(W - M.r - 4, inAbove ? qY + 16 : qY - 7, `Service quote ${money(ST.quote)}`, "end");
    g += lab(W - M.r - 4, Math.min(H - M.b - 4, Math.max(M.t + 12, inAbove ? inY - 7 : inY + 16)), printerName() ? `In-house, ${printerName()}` : "In-house", "end");
    if (r.breakeven && r.reachable) {
      const X = lx(r.breakeven);
      g += `<line x1="${X}" x2="${X}" y1="${M.t}" y2="${H - M.b}" stroke="var(--ink-3)" stroke-dasharray="4 3"/>` + lab(X + 5, M.t + 12, `Break-even ${int(Math.ceil(r.breakeven))}`);
    }
    const dX = lx(ST.demand), dY = ly(costAt(r, ST.demand));
    g += `<circle cx="${dX}" cy="${dY}" r="5" fill="var(--c-in)" stroke="var(--surface)" stroke-width="2"/>` + lab(dX + 8, dY + 16, `You: ${money(costAt(r, ST.demand))}`);
    g += `<line id="k-x" x1="0" x2="0" y1="${M.t}" y2="${H - M.b}" stroke="var(--ink-3)" visibility="hidden"/><rect id="k-hit" x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}" fill="transparent"/>`;
    svg.innerHTML = g;
    const hit = svg.querySelector("#k-hit"), cross = svg.querySelector("#k-x");
    const move = e => {
      const rect = svg.getBoundingClientRect(), sc = W / rect.width, px = (e.clientX - rect.left) * sc;
      const n = 10 ** (Math.log10(x0) + (px - M.l) / (W - M.l - M.r) * (Math.log10(x1) - Math.log10(x0)));
      const c = costAt(r, n), m = Math.max(1, Math.ceil(n / r.cap));
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
      tip.hidden = false;
      tip.innerHTML = `<b>${int(n)} parts a year</b><br>In-house: ${money(c)} a part (${m} printer${m > 1 ? "s" : ""})<br>Service quote: ${money(ST.quote)}<br><span class="tsub">${c < ST.quote ? "In-house" : "Outsourcing"} is cheaper</span>`;
      const bx = px / sc;
      tip.style.left = Math.max(4, Math.min(bx + 14, box.clientWidth - 250)) + "px";
      tip.style.top = (M.t / sc + 8) + "px";
    };
    hit.addEventListener("mousemove", move);
    hit.addEventListener("mouseleave", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); });
  }

  let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => update(false), 120); });
  update();
})();

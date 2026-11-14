/* Compare page: 2–4 process columns, state in ?p=a,b,c. Renders the same markup as templates/_side.html.j2. */
(() => {
  const D = JSON.parse(document.getElementById("cmp-data").textContent);
  const byId = Object.fromEntries(D.processes.map(p => [p.id, p]));
  const sel = [0, 1, 2, 3].map(i => document.getElementById(`c-${i}`));
  const out = document.getElementById("c-out");
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

  const opts = D.families.map(f => {
    const ps = D.processes.filter(p => p.family === f.id);
    return ps.length ? `<optgroup label="${esc(f.name)}">${ps.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</optgroup>` : "";
  }).join("");
  sel.forEach((s, i) => { s.innerHTML = (i > 1 ? '<option value="">None</option>' : "") + opts; });

  function render(ids) {
    const ps = ids.map(id => byId[id]);
    const row = (label, cell) => `<tr><th scope="row">${esc(label)}</th>${ps.map(cell).join("")}</tr>`;
    let h = `<div class="tframe"><table class="side stack" style="--n:${ps.length}"><thead><tr><th scope="col"><span class="vh">Attribute</span></th>`
      + ps.map(p => `<th scope="col"><a href="${p.id}.html">${esc(p.name)}</a></th>`).join("") + "</tr></thead><tbody>";
    h += row("Family", p => `<td data-label="${esc(p.name)}">${esc(p.familyName)}</td>`);
    h += row("Maturity", p => `<td data-label="${esc(p.name)}">${esc(p.maturityLabel)}</td>`);
    for (const [axis, label] of D.bandAxes)
      h += row(label, p => `<td class="band" data-label="${esc(p.name)}">${esc(p.bands[axis])}${p.estimated.includes(axis) ? ' <span class="sub">(estimate)</span>' : ""}</td>`);
    for (const [k, label, levels] of D.dims) {
      const vals = ps.map(p => p.ratings[k]), hi = Math.max(...vals), lo = Math.min(...vals);
      h += `<tr class="rr"><th scope="row">${esc(label)}</th>` + ps.map(p => {
        const v = p.ratings[k];
        return `<td data-label="${esc(p.name)}"${v === hi && hi !== lo ? ' class="lead"' : ""}><div class="sb"><div class="bar"><i style="width:${v * 20}%"></i></div><span class="n">${v}</span></div><small>${esc(levels[v])}</small></td>`;
      }).join("") + "</tr>";
    }
    h += row("Materials", p => `<td data-label="${esc(p.name)}">${esc(p.material_text)}</td>`);
    h += row("Capabilities", p => `<td data-label="${esc(p.name)}">${p.capabilities.length ? esc(p.capabilities.join(", ")) : '<span class="sub">None tagged</span>'}</td>`);
    h += row("Choose it when", p => `<td data-label="${esc(p.name)}">${esc(p.choose)}</td>`);
    h += row("Avoid it when", p => `<td data-label="${esc(p.name)}">${esc(p.avoid)}</td>`);
    h += row("Vendors", p => `<td data-label="${esc(p.name)}">${esc(p.vendors_text)}</td>`);
    out.innerHTML = h + "</tbody></table></div>";
  }

  function current() {
    const ids = sel.map(s => s.value).filter(Boolean);
    return ids.filter((id, i) => ids.indexOf(id) === i);
  }

  function update() {
    const ids = current();
    render(ids);
    try { history.replaceState(null, "", `?p=${ids.join(",")}`); } catch (e) { /* file:// or sandboxed */ }
  }

  const fromUrl = (new URLSearchParams(location.search).get("p") || "").split(",").filter(id => byId[id]).slice(0, 4);
  const start = fromUrl.length >= 2 ? fromUrl : D.default;
  sel.forEach((s, i) => { s.value = start[i] || ""; s.addEventListener("change", update); });
  render(current());
})();

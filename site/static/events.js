/* Events page filters: type chips, process and company selects; state in the query string (?t=launch,funding&p=sls&c=hp). */
(() => {
  const chips = [...document.querySelectorAll("#e-t .chip")];
  const selP = document.getElementById("e-p"), selC = document.getElementById("e-c");
  const items = [...document.querySelectorAll(".evl li")];
  const n = document.getElementById("e-n"), none = document.getElementById("e-none");
  const all = chips.map(c => c.dataset.v);

  const qs = new URLSearchParams(location.search);
  const t = (qs.get("t") || "").split(",").filter(v => all.includes(v));
  if (t.length) chips.forEach(c => c.setAttribute("aria-pressed", t.includes(c.dataset.v)));
  if (qs.get("p") && [...selP.options].some(o => o.value === qs.get("p"))) selP.value = qs.get("p");
  if (qs.get("c") && [...selC.options].some(o => o.value === qs.get("c"))) selC.value = qs.get("c");

  function apply() {
    const on = chips.filter(c => c.getAttribute("aria-pressed") === "true").map(c => c.dataset.v);
    const p = selP.value, c = selC.value;
    let shown = 0;
    items.forEach(li => {
      const ok = on.includes(li.dataset.t) && (!p || li.dataset.p.split(" ").includes(p)) && (!c || li.dataset.c === c);
      li.hidden = !ok;
      shown += ok;
    });
    document.querySelectorAll(".evy").forEach(s => { s.hidden = !s.querySelector("li:not([hidden])"); });
    if (n) n.textContent = `${shown} event${shown === 1 ? "" : "s"}`;
    if (none) none.hidden = shown > 0 || !items.length;
    const q = new URLSearchParams();
    if (on.length < all.length) q.set("t", on.join(","));
    if (p) q.set("p", p);
    if (c) q.set("c", c);
    history.replaceState(null, "", q.toString() ? `?${q}` : location.pathname);
  }

  chips.forEach(ch => ch.addEventListener("click", () => {
    ch.setAttribute("aria-pressed", ch.getAttribute("aria-pressed") !== "true");
    apply();
  }));
  selP.addEventListener("change", apply);
  selC.addEventListener("change", apply);
  apply();
})();

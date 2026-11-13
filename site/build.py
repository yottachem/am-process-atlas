"""Build the site into site/dist from the reference YAML (atlas.load).
Pages: home (picker, matrix, map), one page per process, compare, X-vs-Y pairs, materials explorer, calculator, landscape,
events (with events.xml RSS), methods, status. Downloads: atlas.json, processes.csv, vendors.csv, materials.csv, events.csv.

Usage: uv run python site/build.py [--preview]
--preview marks every page as an internal preview (banner, noindex, no analytics) and shows sections still
waiting on sourcing or on Josh (references, practitioner notes) as placeholders instead of leaving them out.
"""
import csv
import json
import shutil
import sys
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from analysis.claims import evaluate  # noqa: E402
from atlas import calc  # noqa: E402
from ingest.common import RUNS, TYPE_LABELS, domain_of, load_companies, load_ledger  # noqa: E402
from ingest.filings import read_queue  # noqa: E402
from atlas.load import CAPABILITIES, GRADE_CLASSES, GRADE_USES, MATERIAL_CLASSES, MATERIAL_FIELDS, MATURITY, MATURITY_GROUP, load  # noqa: E402

DIST = HERE / "dist"
LINKCHECK = ROOT / "data" / "linkcheck.json"
REPO = "https://github.com/yottachem/am-process-atlas"
SITE_URL = "https://yottachem.github.io/am-process-atlas/"
# Cloudflare Web Analytics site token for yottachem.github.io (public; it ships in the page). Empty = no beacon.
ANALYTICS_TOKEN = "ee99837aed054d67b79a567044baec28"
REVIEWED = "2026-11-10"  # last full editorial review of ratings and bands
MATURITY_LABELS = {"mature": "Mature", "industrial": "Industrial", "niche": "Niche", "emerging": "Emerging",
                   "research": "Research"}
# Processes that get a practitioner note at launch; preview shows a placeholder until the note exists.
NOTE_TARGETS = ["msla", "sla", "dlp", "clip", "sls", "mjf", "hss", "fff", "ifdm", "polyjet", "lpbf", "diw"]
BAND_AXES = ["system_price", "min_feature", "max_part"]
N_ALTERNATIVES = 3
COMPARE_DEFAULT = ["sls", "mjf"]
MIN_RATING_GAP = 2  # pair pages list rating differences of at least this much


def band_index(bands, axis, bid):
    b = bands[axis]["bands"]
    i = next(i for i, x in enumerate(b) if x["id"] == bid)
    return None if b[i].get("unranked") else i


def alternatives(p, procs, bands, rubric):
    """Nearest processes by rating and band distance, with a short note on the biggest rating differences."""
    def dist(q):
        d = sum(abs(p["ratings"][k] - q["ratings"][k]) for k in rubric)
        for axis in BAND_AXES:
            a, b = band_index(bands, axis, p["bands"][axis]), band_index(bands, axis, q["bands"][axis])
            d += 2 if a is None or b is None else abs(a - b)
        d += 0 if set(p["materials"]) & set(q["materials"]) else 4
        d += 0 if p["family"] == q["family"] else 2
        return d

    out = []
    for q in sorted((q for q in procs if q["id"] != p["id"]), key=lambda q: (dist(q), q["name"]))[:N_ALTERNATIVES]:
        diffs = sorted(((q["ratings"][k] - p["ratings"][k], k) for k in rubric), key=lambda x: (-abs(x[0]), x[1]))
        better = [rubric[k]["label"].lower() for d, k in diffs if d > 0][:2]
        worse = [rubric[k]["label"].lower() for d, k in diffs if d < 0][:2]
        parts = ([f"higher on {' and '.join(better)}"] if better else []) + ([f"lower on {' and '.join(worse)}"] if worse else [])
        diff = "Rates " + "; ".join(parts) + "." if parts else "Same ratings; differs in bands or materials."
        out.append({"id": q["id"], "name": q["name"], "diff": diff})
    return out


def differences(ps, ref, labels):
    """Plain statements of where 2–3 processes differ: ratings that differ by MIN_RATING_GAP or more, and bands."""
    out = []
    for axis in BAND_AXES:
        vals = [p["bands"][axis] for p in ps]
        if len(set(vals)) > 1:
            out.append(f"{ref['bands'][axis]['label']}: " + "; ".join(f"{p['name']} {labels[axis][p['bands'][axis]]}" for p in ps) + ".")
    for k, d in ref["rubric"].items():
        vals = [p["ratings"][k] for p in ps]
        hi, lo = max(vals), min(vals)
        if hi - lo < MIN_RATING_GAP:
            continue
        top = [p["name"] for p in ps if p["ratings"][k] == hi]
        low = [p["name"] for p in ps if p["ratings"][k] == lo]
        out.append(f"{d['label']}: {' and '.join(top)} {hi} of 5 ({d['levels'][hi].lower()}), {' and '.join(low)} {lo} "
                   f"({d['levels'][lo].lower()}).")
    return out


def compare_payload(ref, labels):
    fams = ref["family_by_id"]
    return {
        "processes": [{"id": p["id"], "name": p["name"], "family": p["family"], "familyName": fams[p["family"]]["name"],
                       "maturityLabel": MATURITY_LABELS[p["maturity"]],
                       "bands": {a: labels[a][p["bands"][a]] for a in BAND_AXES}, "estimated": p.get("estimated", []),
                       "ratings": p["ratings"], "material_text": p["material_text"],
                       "capabilities": [CAPABILITIES[c] for c in p["capabilities"]],
                       "choose": p["choose"], "avoid": p["avoid"], "vendors_text": p["vendors_text"]} for p in ref["processes"]],
        "families": [{"id": f["id"], "name": f["name"]} for f in ref["families"]],
        "bandAxes": [[a, ref["bands"][a]["label"]] for a in BAND_AXES],
        "dims": [[k, d["label"], d["levels"]] for k, d in ref["rubric"].items()],
        "default": COMPARE_DEFAULT,
    }


def payload(ref):
    procs = []
    for p in ref["processes"]:
        search = " ".join([p["name"], p["aka"], p["material_text"], p["vendors_text"], p["applications"], p["choose"]])
        procs.append({k: p[k] for k in ("id", "name", "aka", "family", "maturity", "materials", "capabilities", "bands", "ratings")}
                     | {"estimated": p.get("estimated", [])}
                     | {"group": MATURITY_GROUP[p["maturity"]], "search": search.lower()})
    return {
        "processes": procs,
        "families": [{k: f[k] for k in ("id", "code", "name")} for f in ref["families"]],
        "bands": ref["bands"],
        "dims": [[k, d["label"]] for k, d in ref["rubric"].items()],
        "materialClasses": MATERIAL_CLASSES,
        "capabilities": CAPABILITIES,
        "maturityLabels": MATURITY_LABELS,
        "maturityOrder": MATURITY,
    }


def export_json(ref):
    """Public download: the reference data without editorial working fields."""
    keep = ("id", "name", "aka", "family", "maturity", "materials", "capabilities", "material_text", "bands", "estimated", "band_notes", "ratings",
            "choose", "avoid", "applications", "vendors_text", "refs")
    return {"reviewed": REVIEWED, "license": "CC-BY-4.0", "source": REPO, "families": ref["families"],
            "bands": ref["bands"], "rubric": ref["rubric"], "processes": [{k: p.get(k) for k in keep} for p in ref["processes"]],
            "vendors": ref["vendors"]}


def write_csv(path, ref):
    rubric, bands = ref["rubric"], ref["bands"]
    label = {axis: {b["id"]: b["label"] for b in bands[axis]["bands"]} for axis in BAND_AXES}
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "process", "family", "maturity", "materials", *[bands[a]["label"] for a in BAND_AXES],
                    *[d["label"] for d in rubric.values()], "url"])
        for p in ref["processes"]:
            w.writerow([p["id"], p["name"], ref["family_by_id"][p["family"]]["name"], p["maturity"], ";".join(p["materials"]),
                        *[label[a][p["bands"][a]] for a in BAND_AXES], *[p["ratings"][k] for k in rubric], f"{SITE_URL}{p['id']}.html"])


def write_vendors_csv(path, ref):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vendor", "process", "product", "price", "basis", "source", "as_of"])
        for v in ref["vendors"]:
            for pid in v["processes"]:
                prods = [pr for pr in v["products"] if pr["process"] == pid] or [None]
                for pr in prods:
                    price = pr["price"] if pr else "quote"
                    priced = price != "quote"
                    w.writerow([v["name"], pid, pr["name"] if pr else "", price["value"] if priced else "quote",
                                price["basis"] if priced else "", price["source"] if priced else "", price["as_of"] if priced else ""])


GRADE_CLASS_LABELS = {"polymer": "Polymer", "elastomer": "Elastomer", "composite": "Fiber composite", "metal": "Metal"}
# Explorer axes: key stem, label, unit, log scale. Each stem has _xy and _z columns except HDT.
# Modulus is stored in MPa like the data sheets and shown in GPa (factor).
MATERIAL_AXES = [("uts", "Tensile strength", "MPa", True, 1), ("mod", "Tensile modulus", "GPa", True, 0.001),
                 ("elong", "Elongation at break", "%", True, 1), ("hdt", "HDT at 0.45 MPa", "°C", False, 1)]


def fmt_num(x):
    return f"{x:,.3g}" if x < 1000 else f"{x:,.0f}"


def grade_cell(m, stem):
    """Table text for one property: 'in-plane / Z', with published ranges kept as ranges."""
    factor = next(a[4] for a in MATERIAL_AXES if a[0] == stem)
    keys = ["hdt_045"] if stem == "hdt" else [f"{stem}_xy", f"{stem}_z"]
    out = []
    for k in keys:
        v = m["values"][k]
        if v is None:
            out.append("–")
        elif v["lo"] == v["hi"]:
            out.append(fmt_num(v["lo"] * factor))
        else:
            out.append(f"{fmt_num(v['lo'] * factor)}–{fmt_num(v['hi'] * factor)}")
    return " / ".join(out) if any(o != "–" for o in out) else "–"


def materials_payload(ref):
    names = {p["id"]: p["name"] for p in ref["processes"]}
    rows = [{"id": m["id"], "grade": m["grade"], "vendor": m["vendor"], "process": m["process"], "processName": names[m["process"]],
             "cls": m["class"], "use": m["use"], "base": m["base"], "v": {k: m["values"][k] for k in MATERIAL_FIELDS if m["values"][k]},
             "standard": m["standard"], "orientation": m["orientation"], "condition": m["condition"], "url": m["tds_url"],
             "doc": m["doc"]} for m in ref["materials"] if m["available"]]
    procs = sorted({r["process"] for r in rows}, key=lambda i: names[i])
    return {"rows": rows, "processes": [[i, names[i]] for i in procs], "classes": [[c, GRADE_CLASS_LABELS[c]] for c in GRADE_CLASSES],
            "uses": [list(u) for u in GRADE_USES.items()], "axes": [list(a) for a in MATERIAL_AXES]}


def landscape_rows(ref, labels):
    """One row per process: entry band, vendor text, and every product with a sourced price."""
    prices = {}
    for v in ref["vendors"]:
        for pr in v["products"]:
            if pr["price"] != "quote":
                prices.setdefault(pr["process"], []).append(
                    {"vendor": v["name"], "product": pr["name"], **pr["price"], "status": pr.get("status", {}).get("text")})
    rows = []
    for p in ref["processes"]:
        ps = sorted(prices.get(p["id"], []), key=lambda x: x["vendor"].lower())
        search = " ".join([p["name"], p["aka"], p["vendors_text"]] + [f"{x['vendor']} {x['product']}" for x in ps]).lower()
        rows.append({"id": p["id"], "name": p["name"], "family": p["family"], "band": labels["system_price"][p["bands"]["system_price"]],
                     "estimated": "system_price" in p.get("estimated", []), "vendors_text": p["vendors_text"], "prices": ps,
                     "price_note": p.get("band_notes", {}).get("system_price") if not ps else None,
                     "search": search})
    return rows


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RSS_ITEMS = 50
# Status-page rows for the events feed, in pipeline order.
RUN_SOURCES = [("sec", "SEC filings"), ("news:bing", "News: Bing"), ("news:gnews", "News: Google News"),
               ("news:gdelt", "News: GDELT"), ("news:newsroom", "News: company newsrooms"), ("accept", "Acceptance rules")]


def date_label(d):
    """'2024-04-17' -> '17 Apr 2024'; '2025-03' -> 'Mar 2025'; '2026' -> '2026'."""
    parts = d.split("-")
    if len(parts) == 3:
        return f"{int(parts[2])} {MONTHS[int(parts[1]) - 1]} {parts[0]}"
    if len(parts) == 2:
        return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}"
    return d


def event_rows(ref):
    """Accepted ledger rows, newest first, with names, processes (the row's own, else the company's) and source domains."""
    companies = load_companies()
    names = {p["id"]: p["name"] for p in ref["processes"]}
    rows = []
    for e in load_ledger():
        c = companies[e["company"]]
        procs = e["processes"].split() or c["processes"]
        rows.append(e | {"company_name": c["name"], "processes": procs, "process_names": [names[p] for p in e["processes"].split()],
                         "year": e["date"][:4], "date_label": date_label(e["date"]),
                         "sources": [{"url": u, "domain": domain_of(u)} for u in e["sources"].split()]})
    return sorted(rows, key=lambda r: (r["date"], r["id"]), reverse=True)


def write_rss(path, events):
    def pub(d):
        y, m, dd = (d.split("-") + ["01", "01"])[:3]
        return format_datetime(datetime(int(y), int(m), int(dd), 12, tzinfo=timezone.utc))
    items = "".join(
        f"<item><title>{escape(e['detail'])}</title><link>{escape(e['sources'][0]['url'])}</link>"
        f"<guid isPermaLink=\"false\">am-process-atlas-{e['id']}</guid><pubDate>{pub(e['date'])}</pubDate>"
        f"<category>{TYPE_LABELS[e['type']]}</category><description>{escape(TYPE_LABELS[e['type']] + ' · ' + e['company_name'])}"
        f"</description></item>\n" for e in events[:RSS_ITEMS])
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>\n'
                    f"<title>AM Process Atlas: industry events</title><link>{SITE_URL}events.html</link>\n"
                    "<description>Additive manufacturing launches, acquisitions, mergers, funding, wind-downs and market exits, "
                    "each with its source.</description><language>en-us</language>\n" + items + "</channel></rss>\n")


def write_events_csv(path, events):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "date", "company", "type", "status", "detail", "amount_usd", "qualifier", "processes", "sources", "accept"])
        for e in events:
            w.writerow([e["id"], e["date"], e["company_name"], e["type"], e["status"], e["detail"], e["amount_usd"], e["qualifier"],
                        " ".join(e["processes"]), " ".join(s["url"] for s in e["sources"]), e["accept"]])


def feed_status():
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else {}
    queue = read_queue()
    return {"runs": [{"label": label, **runs[k]} if k in runs else {"label": label} for k, label in RUN_SOURCES],
            "open": sum(q["status"] == "open" for q in queue), "watched": len(load_companies())}


def coverage(ref):
    procs = ref["processes"]
    est = sum(len(p.get("estimated", [])) for p in procs)
    priced = sum(pr["price"] != "quote" for v in ref["vendors"] for pr in v["products"])
    return [("Processes", len(procs)), ("References", sum(len(p["refs"]) for p in procs)),
            ("Bands marked estimate", f"{est} of {3 * len(procs)}"), ("Vendors", len(ref["vendors"])),
            ("Products with a public price", priced), ("Material grades", sum(m["available"] for m in ref["materials"])),
            ("Practitioner notes", len(ref["notes"])), ("Accepted events", len(load_ledger()))]


def build(preview=False):
    ref = load()
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    bands = ref["bands"]
    labels = {axis: {b["id"]: b["label"] for b in bands[axis]["bands"]} for axis in BAND_AXES}
    procs = [p | {"group": MATURITY_GROUP[p["maturity"]]} for p in ref["processes"]]
    claims = evaluate(ref)
    common = {"preview": preview, "site_url": SITE_URL, "repo": REPO, "reviewed": REVIEWED, "built": date.today().isoformat(),
              "analytics_token": ANALYTICS_TOKEN, "processes": procs, "families": ref["family_by_id"],
              "family_list": ref["families"], "bands": bands, "rubric": ref["rubric"], "capabilities": CAPABILITIES,
              "maturity_labels": MATURITY_LABELS, "band_label": lambda axis, bid: labels[axis][bid], "claims": claims}

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    for f in (HERE / "static").iterdir():
        shutil.copy(f, DIST / f.name)

    def render(tpl, out, page, **ctx):
        (DIST / out).write_text(env.get_template(tpl).render(**common, page=page, page_file="" if page == "index" else out, **ctx))

    # "</" would end the script block early; JSON allows the escaped form.
    data = json.dumps(payload(ref), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    render("index.html.j2", "index.html", "index", payload=data)
    render("methods.html.j2", "methods.html", "methods", n_watched=len(load_companies()))
    by_id = {p["id"]: p for p in procs}
    pairs = ref["pairs"]
    cdata = json.dumps(compare_payload(ref, labels), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    render("compare.html.j2", "compare.html", "compare", payload=cdata, pairs=pairs, default=[by_id[i] for i in COMPARE_DEFAULT])
    for pair in pairs:
        ps = [by_id[i] for i in pair["processes"]]
        related = [r for r in pairs if r is not pair and set(r["processes"]) & set(pair["processes"])]
        render("pair.html.j2", f"{pair['id']}.html", pair["id"], pair=pair, ps=ps, diffs=differences(ps, ref, labels),
               related=related)
    render("landscape.html.j2", "landscape.html", "landscape", rows=landscape_rows(ref, labels))
    mdata = json.dumps(materials_payload(ref), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    grades = [m for m in ref["materials"] if m["available"]]
    render("materials.html.j2", "materials.html", "materials", payload=mdata, grades=grades,
           unavailable=[m for m in ref["materials"] if not m["available"]],
           class_labels=GRADE_CLASS_LABELS, use_labels=GRADE_USES, process_names={p["id"]: p["name"] for p in procs}, cell=grade_cell,
           payload_procs=len({m["process"] for m in grades}))
    groups = {}
    for k, label, unit, d, step, help_, group in calc.INPUTS:
        groups.setdefault(group, []).append((k, label, unit, d, step, help_))
    presets = calc.presets(ref["vendors"], {p["id"]: p["name"] for p in procs})
    kdata = json.dumps({"inputs": [list(i) for i in calc.INPUTS], "defaults": calc.DEFAULTS, "presets": presets},
                       ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    render("calculator.html.j2", "calculator.html", "calculator", payload=kdata, presets=presets,
           groups=[{"name": g, "inputs": i} for g, i in groups.items()])
    grades_by_process = {}
    for m in grades:
        grades_by_process.setdefault(m["process"], []).append(m)
    linkcheck = json.loads(LINKCHECK.read_text()) if LINKCHECK.exists() else None
    events = event_rows(ref)
    fs = feed_status()
    used = {p for e in events for p in e["processes"]}
    render("events.html.j2", "events.html", "events", events=events, type_labels=TYPE_LABELS, n_watched=fs["watched"],
           n_open=fs["open"], event_processes=[p for p in procs if p["id"] in used],
           event_companies=[{"id": i, "name": n} for i, n in sorted({(e["company"], e["company_name"]) for e in events}, key=lambda c: c[1].lower())])
    write_rss(DIST / "events.xml", events)
    write_events_csv(DIST / "events.csv", events)
    render("status.html.j2", "status.html", "status", coverage=coverage(ref), linkcheck=linkcheck, feed=fs)
    for p in procs:
        render("process.html.j2", f"{p['id']}.html", p["id"], p=p, note=ref["notes"].get(p["id"]), note_targets=NOTE_TARGETS,
               pairs=[r for r in pairs if p["id"] in r["processes"]], grades=grades_by_process.get(p["id"], []),
               alternatives=alternatives(p, procs, bands, ref["rubric"]))

    (DIST / "atlas.json").write_text(json.dumps(export_json(ref), ensure_ascii=False, indent=1))
    write_csv(DIST / "processes.csv", ref)
    write_vendors_csv(DIST / "vendors.csv", ref)
    shutil.copy(ROOT / "reference" / "materials.csv", DIST / "materials.csv")
    pages = ["", "compare.html", "materials.html", "calculator.html", "landscape.html", "events.html", "methods.html", "status.html"] + [f"{r['id']}.html" for r in pairs] + [f"{p['id']}.html" for p in procs]
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"<url><loc>{SITE_URL}{u}</loc></url>\n" for u in pages) + "</urlset>\n")
    (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if preview else f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
    print(f"Built {len(pages)} pages into {DIST}{' (preview)' if preview else ''}")


if __name__ == "__main__":
    build(preview="--preview" in sys.argv)

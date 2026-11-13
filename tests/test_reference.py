import os
from pathlib import Path

import pytest

from atlas.load import CAPABILITIES, GRADE_CLASSES, GRADE_USES, MATERIAL_CLASSES, MATERIAL_FIELDS, MATURITY, load

D = load()
GATE = os.environ.get("LAUNCH_GATE") == "1"
PROCS = D["processes"]


def test_ids_unique():
    ids = [p["id"] for p in PROCS]
    assert len(ids) == len(set(ids))
    fams = [f["id"] for f in D["families"]]
    assert len(fams) == len(set(fams))


@pytest.mark.parametrize("p", PROCS, ids=lambda p: p["id"])
def test_process_schema(p):
    for k in ("name", "aka", "family", "maturity", "materials", "material_text", "bands", "ratings",
              "choose", "avoid", "applications", "refs"):
        assert p.get(k) not in (None, ""), k
    assert p["family"] in D["family_by_id"]
    assert p["maturity"] in MATURITY
    assert set(p["materials"]) <= set(MATERIAL_CLASSES) and p["materials"]
    assert set(p.get("capabilities", [])) <= set(CAPABILITIES)
    assert set(p["ratings"]) == set(D["rubric"])
    assert all(v in (1, 2, 3, 4, 5) for v in p["ratings"].values())
    for axis, band in p["bands"].items():
        assert band in {b["id"] for b in D["bands"][axis]["bands"]}, (axis, band)
    assert set(p["bands"]) == {"system_price", "min_feature", "max_part"}


@pytest.mark.parametrize("p", PROCS, ids=lambda p: p["id"])
def test_neutral(p):
    # the public atlas never singles out a vendor
    assert not {"highlight", "featured", "fl", "vendor_status"} & set(p)


def test_derived_ratings_not_stored():
    import yaml
    raw = yaml.safe_load((Path(__file__).resolve().parent.parent / "reference/processes.yaml").read_text())["processes"]
    derived = {k for k, d in D["rubric"].items() if d.get("derived_from")}
    assert derived == {"detail", "size", "system_cost"}
    for p in raw:
        assert not derived & set(p["ratings"]), p["id"]


BAND_AXES = ["system_price", "min_feature", "max_part"]


def test_rubric_levels():
    for k, d in D["rubric"].items():
        assert set(d["levels"]) == {1, 2, 3, 4, 5}, k


@pytest.mark.parametrize("p", PROCS, ids=lambda p: p["id"])
def test_refs(p):
    for r in p["refs"]:
        assert r.get("title") and str(r.get("url", "")).startswith("http"), r
        assert r.get("supports") and set(r["supports"]) <= {"process", "capabilities", *BAND_AXES}, r
    # Every band is backed by a reference or carries an open verify flag that names it.
    backed = {a for r in p["refs"] for a in r["supports"]}
    flagged = {v.split(":")[0] for v in p.get("verify", [])}
    estimated = set(p.get("estimated", []))
    service = {"system_price"} if p["bands"]["system_price"] == "service" and "system_price" in p.get("band_notes", {}) else set()
    for axis in BAND_AXES:
        assert axis in backed | flagged | estimated | service, f"{axis} has no reference, estimate mark, or verify flag"
    for axis in estimated:
        assert axis in p.get("band_notes", {}) or axis not in backed, f"{axis} is cited and estimated; add a band note saying why"
    if GATE:
        assert p["refs"], "no references"
        assert not p.get("verify"), f"verify pending: {p.get('verify')}"


def test_notes():
    for pid, n in D["notes"].items():
        assert pid in D["process_by_id"]
        assert n.get("author") and n.get("date")
        words = len(n["body"].split())
        assert 60 <= words <= 200, (pid, words)


def test_build_smoke(tmp_path, monkeypatch):
    """The site builds, every process gets a page, and the embedded data parses."""
    import json
    import re
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "site"))
    import build
    monkeypatch.setattr(build, "DIST", tmp_path)
    build.build(preview=False)
    ref = load()
    for p in ref["processes"]:
        assert (tmp_path / f"{p['id']}.html").exists()
    html = (tmp_path / "index.html").read_text()
    data = json.loads(re.search(r'id="atlas-data">(.*?)</script>', html, re.S).group(1))
    assert len(data["processes"]) == len(ref["processes"])
    assert "noindex" not in html and "Internal preview" not in html
    for r in ref["pairs"]:
        assert (tmp_path / f"{r['id']}.html").exists(), r["id"]
    cmp = (tmp_path / "compare.html").read_text()
    assert len(json.loads(re.search(r'id="cmp-data">(.*?)</script>', cmp, re.S).group(1))["processes"]) == len(ref["processes"])
    mat = (tmp_path / "materials.html").read_text()
    mdata = json.loads(re.search(r'id="mat-data">(.*?)</script>', mat, re.S).group(1))
    avail = [m for m in ref["materials"] if m["available"]]
    assert len(mdata["rows"]) == len(avail)
    assert all(f'id="g-{m["id"]}"' in mat for m in avail)
    calc_html = (tmp_path / "calculator.html").read_text()
    kdata = json.loads(re.search(r'id="calc-data">(.*?)</script>', calc_html, re.S).group(1))
    assert all(f'id="k-{i[0]}"' in calc_html for i in kdata["inputs"])
    for f in ("compare.js", "materials.js", "calculator.js", "events.js", "events.html", "events.csv", "materials.csv", "landscape.html", "methods.html", "status.html", "vendors.csv", "processes.csv", "atlas.json", "sitemap.xml"):
        assert (tmp_path / f).exists(), f
    import xml.etree.ElementTree as ET
    assert ET.parse(tmp_path / "events.xml").getroot().find("channel/title") is not None
    land = (tmp_path / "landscape.html").read_text()
    assert all(f'href="{p["id"]}.html"' in land for p in ref["processes"])
    assert "Open review flags" not in (tmp_path / "sla.html").read_text()


@pytest.mark.parametrize("p", PROCS, ids=lambda p: p["id"])
def test_estimated(p):
    assert set(p.get("estimated", [])) <= set(BAND_AXES)
    assert set(p.get("band_notes", {})) <= set(BAND_AXES)


@pytest.mark.parametrize("v", D["vendors"], ids=lambda v: v["id"])
def test_vendor(v):
    assert v["processes"] and set(v["processes"]) <= set(D["process_by_id"]), v["processes"]
    for pid in v["processes"]:
        assert v["name"] in D["process_by_id"][pid]["vendors_text"], (v["name"], pid)
    for pr in v["products"]:
        assert pr["process"] in v["processes"], pr
        price = pr["price"]
        if price != "quote":
            assert price["value"] and price["source"].startswith("http") and price["as_of"], pr
            assert price["basis"] in ("list", "reported"), pr
        if "status" in pr:
            assert pr["status"]["source"].startswith("http"), pr


def test_vendor_ids_unique():
    ids = [v["id"] for v in D["vendors"]]
    assert len(ids) == len(set(ids))


def test_claims():
    from analysis.claims import evaluate
    cs = [c for page in evaluate(D).values() for c in page]
    assert len({c["id"] for c in cs}) == len(cs)
    if GATE:
        assert all(c["holds"] for c in cs), [c["id"] for c in cs if not c["holds"]]


@pytest.mark.parametrize("pair", D["pairs"], ids=lambda r: r["id"])
def test_pair(pair):
    assert 2 <= len(pair["processes"]) <= 3
    assert set(pair["processes"]) <= set(D["process_by_id"])
    assert pair["id"] == "-vs-".join(pair["processes"]), "id must be the process ids joined by -vs-"
    assert pair["title"] and 20 <= len(pair["intro"].split()) <= 70


def test_pair_ids_unique():
    ids = [r["id"] for r in D["pairs"]]
    assert len(ids) == len(set(ids)) and not set(ids) & set(D["process_by_id"])


# Plausible bounds per property (display units as stored: MPa, %, degrees C), to catch unit slips such as GPa typed as MPa.
THIRD_PARTY = ("sculpteo", "seas.harvard.edu", "cdn.shopify.com", "ulprospector", "protolabs", "goengineer", "matterhackers")
BOUNDS = {"uts": (1, 2000), "mod": (1, 250000), "elong": (0.3, 1000), "hdt": (30, 350)}


@pytest.mark.parametrize("m", D["materials"], ids=lambda m: m["id"])
def test_material(m):
    import datetime
    assert m["process"] in D["process_by_id"], m["process"]
    assert m["class"] in GRADE_CLASSES
    assert m["status"] in ("", "unavailable")
    assert m["use"] in GRADE_USES, m["use"]
    datetime.date.fromisoformat(m["as_of"])
    if not m["available"]:
        assert m["grade"] and m["vendor"] and m["condition"], "unavailable rows say why"
        assert not any(m["values"].values()) and not m["tds_url"], "unavailable rows carry no values or third-party source"
        return
    assert m["grade"] and m["vendor"] and m["base"] and m["orientation"] and m["condition"] and m["doc"]
    assert m["standard"], "standard may be 'Not stated' but not blank"
    assert m["tds_url"].startswith("https://")
    assert not any(h in m["tds_url"] for h in THIRD_PARTY), "vendor-hosted sheets only"
    vals = {k: v for k, v in m["values"].items() if v}
    assert vals, "at least one property"
    for k, v in vals.items():
        lo, hi = BOUNDS[k.split("_")[0]]
        assert v["lo"] <= v["hi"] and lo <= v["lo"] and v["hi"] <= hi, (k, v)
    if m["class"] == "metal" and m["values"]["mod_xy"]:
        assert m["values"]["mod_xy"]["lo"] >= 40000, "metal modulus is stored in MPa"


def test_material_ids_unique():
    ids = [m["id"] for m in D["materials"]]
    assert len(ids) == len(set(ids))
    assert len(D["materials"][0]) - 2 == len(MATERIAL_FIELDS) + 14, "materials.csv columns changed; update the loader and tests (minus values, available)"

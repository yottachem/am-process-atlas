"""Load and join the hand-curated reference files."""
import csv
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference"

MATERIAL_CLASSES = {
    "polymer": "Rigid polymer", "elastomer": "Elastomer / flexible", "metal": "Metal", "ceramic": "Technical ceramic",
    "composite": "Fiber composite", "casting": "Casting pattern or mold", "bio": "Living cells / hydrogel",
    "other": "Other (concrete, gypsum, inks)",
}
CAPABILITIES = {
    "biocompatible": "Biocompatible grades", "transparent": "Transparent parts", "high_temp_polymer": "High-temp polymer",
    "flame_retardant": "Flame-retardant grades", "multi_material": "Multi-material", "full_color": "Full color",
    "support_free": "No supports",
}
MATURITY = ["mature", "industrial", "niche", "emerging", "research"]
# Three maturity groups for color: the map caps categorical color at three series.
MATURITY_GROUP = {"mature": "mature", "industrial": "industrial", "niche": "industrial", "emerging": "emerging", "research": "emerging"}


def _yaml(name):
    return yaml.safe_load((REF / name).read_text())


def notes():
    out = {}
    for p in sorted((REF / "notes").glob("*.md")):
        if p.name == "README.md":
            continue
        text = p.read_text()
        _, fm, body = text.split("---", 2)
        meta = yaml.safe_load(fm)
        out[meta["process"]] = {**meta, "body": body.strip()}
    return out


# Material grades from vendor-hosted data sheets. Numeric cells hold one value or a published range "lo-hi".
# status "unavailable": the vendor no longer serves a data sheet; the grade is listed but not plotted.
# use: the application group the vendor sells the grade for; the explorer sections and filters by it.
MATERIAL_FIELDS = ["uts_xy", "uts_z", "mod_xy", "mod_z", "elong_xy", "elong_z", "hdt_045"]
GRADE_CLASSES = ["polymer", "elastomer", "composite", "metal"]
GRADE_USES = {"general": "Engineering and general purpose", "dental": "Dental", "biomedical": "Biomedical", "castable": "Castable"}


def parse_value(s):
    """'' -> None; '50' -> {lo: 50, hi: 50}; '55-60' -> {lo: 55, hi: 60}. mid is what the chart plots."""
    s = s.strip()
    if not s:
        return None
    lo, _, hi = s.partition("-")
    lo, hi = float(lo), float(hi or lo)
    return {"lo": lo, "hi": hi, "mid": (lo + hi) / 2, "text": s}


def materials():
    with (REF / "materials.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["values"] = {k: parse_value(r[k]) for k in MATERIAL_FIELDS}
        r["available"] = r["status"] != "unavailable"
    return rows


def derive_ratings(procs, bands, rubric):
    """Ratings with derived_from come from the band position: smallest feature, largest part, lowest price score 5."""
    for k, d in rubric.items():
        axis = d.get("derived_from")
        if not axis:
            continue
        ranked = [b["id"] for b in bands[axis]["bands"] if not b.get("unranked")]
        for p in procs:
            band = p["bands"][axis]
            i = ranked.index(band) if band in ranked else None
            if axis == "min_feature":  # bands run fine to coarse
                score = 5 - i
            elif axis == "max_part":  # bands run small to large
                score = i + 1
            else:  # system_price runs cheap to expensive; unranked (service only) scores 1
                score = 1 if i is None else 5 - i
            p["ratings"][k] = score


def load():
    fams = _yaml("families.yaml")["families"]
    procs = _yaml("processes.yaml")["processes"]
    bands, rubric = _yaml("bands.yaml"), _yaml("rubric.yaml")["dimensions"]
    vendors = _yaml("vendors.yaml")["vendors"]
    pairs = _yaml("pairs.yaml")["pairs"]
    derive_ratings(procs, bands, rubric)
    return {
        "families": fams,
        "family_by_id": {f["id"]: f for f in fams},
        "processes": procs,
        "process_by_id": {p["id"]: p for p in procs},
        "bands": bands,
        "rubric": rubric,
        "vendors": vendors,
        "pairs": pairs,
        "notes": notes(),
        "materials": materials(),
    }

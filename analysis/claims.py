"""Checked statements: every summary sentence on the site is a claim in analysis/claims.yaml, stored with the
condition it rests on. Each build re-checks every claim against the reference data:

- condition holds: the text is shown with numbers filled in from the data
- condition fails: the neutral fallback is shown, and LAUNCH_GATE=1 pytest fails until the claim is rewritten

Rewriting a claim is a reviewed, manual step: change `text` and `holds` together so the condition states exactly
what the text asserts. Never loosen `holds` just to clear a failure.

Usage: uv run python -m analysis.claims            # print every claim and whether it holds
       uv run python -m analysis.claims --values   # also print every value claims can use
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "analysis" / "claims.yaml"
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")
SAFE = {"abs": abs, "min": min, "max": max, "all": all, "any": any, "len": len, "True": True, "False": False}


def values(ref):
    """Every value a claim can use, computed from the reference data."""
    procs = ref["processes"]

    def count(axis, ids):
        return sum(p["bands"][axis] in ids for p in procs)

    fine = [p for p in procs if p["bands"]["min_feature"] in ("lt10um", "10-50um")]
    return {
        "n": len(procs),
        "n_families": len({p["family"] for p in procs}),
        "n_desktop": count("system_price", ("lt1k", "1k-10k")),
        "n_over_500k": count("system_price", ("gt500k",)),
        "n_service": count("system_price", ("service",)),
        "n_price_estimated": sum("system_price" in p.get("estimated", []) for p in procs),
        "n_fine": len(fine),
        "fine_all_small": all(p["bands"]["max_part"] in ("lt100mm", "100-300mm") for p in fine),
        "n_over_1m": count("max_part", ("1-3m", "gt3m")),
        "n_metal": sum("metal" in p["materials"] for p in procs),
        "n_vendors": len(ref["vendors"]),
        "n_vendors_priced": sum(any(pr["price"] != "quote" for pr in v["products"]) for v in ref["vendors"]),
        "n_refs": sum(len(p["refs"]) for p in procs),
    }


def fill(text, vals):
    return PLACEHOLDER.sub(lambda m: f"{vals[m.group(1)]:,}" if isinstance(vals[m.group(1)], int) else str(vals[m.group(1)]), text)


def evaluate(ref):
    """{page: [{id, text, holds}]} with numbers filled in; a failing claim shows its fallback."""
    vals = values(ref)
    out = {}
    for c in yaml.safe_load(SPEC.read_text())["claims"]:
        ok = bool(eval(c["holds"], {"__builtins__": {}}, SAFE | vals))  # noqa: S307 (expressions are repo-authored)
        out.setdefault(c["page"], []).append({"id": c["id"], "holds": ok, "text": fill(c["text"] if ok else c["fallback"], vals)})
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from atlas.load import load
    ref = load()
    if "--values" in sys.argv:
        for k, v in values(ref).items():
            print(f"{k:20} {v}")
    for page, cs in evaluate(ref).items():
        for c in cs:
            print(f"{'ok  ' if c['holds'] else 'FAIL'} {page:9} {c['id']:16} {c['text']}")

"""Buy-vs-outsource breakeven model. site/static/calculator.js mirrors compute(); tests check the two agree."""
import math
import re

HOURS_PER_YEAR = 8760

# (key, label, unit, placeholder default, step, help, group). Defaults are placeholders for the reader to replace, not sourced figures.
INPUTS = [
    ("price", "System price", "$", 50000, 500, "Printer plus required post-processing equipment and installation", "Printer"),
    ("years", "Depreciation period", "years", 5, 1, "Straight line, no residual value", "Printer"),
    ("svc", "Service and maintenance", "% of price per year", 10, 1, "Service contract, spare parts, software", "Printer"),
    ("util", "Utilization", "% of the year printing", 40, 5, "Share of 8,760 hours a year the printer is building", "Printer"),
    ("perBuild", "Parts per build", "parts", 40, 1, "How many of this part fit one build", "Each build"),
    ("buildHrs", "Build time", "hours", 12, 0.5, "Print time per build, including cooldown that blocks the printer", "Each build"),
    ("success", "Build success rate", "%", 95, 1, "Share of parts that pass inspection", "Each build"),
    ("consum", "Consumables and energy", "$ per build", 20, 1, "Tanks, plates, filters, gas, electricity", "Each build"),
    ("matPrice", "Material price", "$ per kg or L", 100, 1, "Price of the material as bought", "Material"),
    ("density", "Material density", "g/cm³", 1.0, 0.01, "Used only when material is priced per kg", "Material"),
    ("partVol", "Material per part", "cm³", 20, 1, "Part plus supports", "Material"),
    ("waste", "Waste and refresh loss", "%", 30, 5, "Unrecovered powder, resin left in tanks, purge", "Material"),
    ("laborMin", "Labor per build", "minutes", 60, 5, "Setup, unloading, cleaning, finishing", "Labor"),
    ("rate", "Labor rate", "$ per hour", 60, 5, "Loaded hourly cost", "Labor"),
    ("quote", "Service quote", "$ per part", 25, 0.5, "Outsourced price per part, including shipping", "Outsourcing"),
    ("demand", "Your volume", "parts per year", 2000, 100, "Parts you need a year", "Outsourcing"),
]
DEFAULTS = {k: d for k, _, _, d, *_ in INPUTS} | {"unit": "kg"}


def compute(x):
    """Costs for one part design. Returns per-part and annual figures, capacity, and the breakeven volume (None if never)."""
    per_l = x["matPrice"] / 1000 if x["unit"] == "L" else x["matPrice"] * x["density"] / 1000  # $ per cm³
    mat = x["partVol"] * per_l * (1 + x["waste"] / 100)
    s = x["success"] / 100
    good = x["perBuild"] * s
    build_cost = mat * x["perBuild"] + x["consum"] + x["laborMin"] / 60 * x["rate"]
    var = build_cost / good
    fixed = x["price"] / x["years"] + x["price"] * x["svc"] / 100
    builds = math.floor(HOURS_PER_YEAR * x["util"] / 100 / x["buildHrs"])
    cap = builds * good
    margin = x["quote"] - var
    be = fixed / margin if margin > 0 else None
    reachable = be is not None and be <= cap
    d = x["demand"]
    machines = max(1, math.ceil(d / cap)) if cap else None
    annual_in = machines * fixed + d * var if machines else None
    return {"mat": mat, "var": var, "fixed": fixed, "builds": builds, "cap": cap, "breakeven": be, "reachable": reachable,
            "machines": machines, "perPart": annual_in / d if annual_in and d else None, "annualIn": annual_in,
            "annualOut": d * x["quote"]}


def presets(vendors, process_names):
    """System prices with a sourced figure. Ranges use the lower figure; subscriptions are skipped."""
    out = []
    for v in vendors:
        for p in v["products"]:
            pr = p["price"]
            if pr == "quote" or "year" in pr["value"]:
                continue
            m = re.search(r"\$([\d,]+(?:\.\d+)?)\s*(million)?", pr["value"])
            if not m:
                continue
            n = float(m.group(1).replace(",", "")) * (1e6 if m.group(2) else 1)
            out.append({"id": f"{v['id']}-{p['name']}".lower().replace(" ", "-"), "label": f"{v['name']} {p['name']}",
                        "process": process_names[p["process"]], "price": round(n), "text": pr["value"], "basis": pr["basis"],
                        "publisher": pr["publisher"], "source": pr["source"], "as_of": pr["as_of"]})
    return sorted(out, key=lambda r: r["price"])

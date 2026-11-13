"""Breakeven model: a hand-worked example, and the browser copy (calculator.js) agrees with atlas/calc.py."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from atlas.calc import DEFAULTS, INPUTS, compute, presets
from atlas.load import load

JS = Path(__file__).resolve().parent.parent / "site" / "static" / "calculator.js"


def test_worked_example():
    """The example on the methods page, by hand: $2.60 material, $184 a build over 38 good parts, $15,000 a year fixed."""
    r = compute(DEFAULTS)
    assert r["mat"] == pytest.approx(2.60)
    assert r["var"] == pytest.approx(184 / 38)
    assert r["fixed"] == pytest.approx(15000)
    assert r["builds"] == 292 and r["cap"] == pytest.approx(292 * 38)
    assert r["breakeven"] == pytest.approx(15000 / (25 - 184 / 38))
    assert round(r["breakeven"], 1) == 744.1
    assert r["perPart"] == pytest.approx(184 / 38 + 15000 / 2000)
    assert round(r["perPart"], 2) == 12.34


def test_edge_cases():
    assert compute(DEFAULTS | {"quote": 4})["breakeven"] is None  # quote below variable cost: owning never pays back
    r = compute(DEFAULTS | {"util": 1, "quote": 5})  # break-even beyond one printer's capacity
    assert r["breakeven"] > r["cap"] and not r["reachable"]
    r = compute(DEFAULTS | {"demand": 30000})  # volume beyond one printer adds printers
    assert r["machines"] == 3
    assert compute(DEFAULTS | {"unit": "L", "matPrice": 100})["mat"] == pytest.approx(2.60)  # density only applies per kg


CASES = [DEFAULTS, DEFAULTS | {"unit": "L", "matPrice": 180, "quote": 9, "demand": 300},
         DEFAULTS | {"price": 250000, "util": 70, "perBuild": 300, "buildHrs": 20, "demand": 60000, "quote": 6.5},
         DEFAULTS | {"quote": 3}, DEFAULTS | {"util": 2, "quote": 6}]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_matches_python():
    script = f"const c = require({json.dumps(str(JS))}); console.log(JSON.stringify({json.dumps(CASES)}.map(x => c.compute(x))));"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for x, js in zip(CASES, out):
        py = compute(x)
        for k, v in py.items():
            if v is None or isinstance(v, bool):
                assert js[k] == v, (k, x)
            else:
                assert js[k] == pytest.approx(v), (k, x)


def test_inputs_and_presets():
    assert len({i[0] for i in INPUTS}) == len(INPUTS)
    ref = load()
    ps = presets(ref["vendors"], {p["id"]: p["name"] for p in ref["processes"]})
    assert ps, "no sourced system prices"
    for p in ps:
        assert p["price"] > 0 and p["source"].startswith("https://") and p["publisher"]

"""Render the social preview card (site/static/social.png, 1200x630): title, counts, and a heatmap of every rating.

Run locally after the data changes; CI doesn't have Chrome, so the PNG is committed.
Run: uv run python site/social.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import build  # noqa: E402
from analysis.claims import values  # noqa: E402
from atlas.load import load  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RAMP = ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#104281"]  # light-mode --h1..--h5 from atlas.css


def main():
    ref = load()
    dims = list(ref["rubric"])
    fam_order = [f["id"] for f in ref["families"]]
    procs = sorted(ref["processes"], key=lambda p: fam_order.index(p["family"]))
    vals = values(ref)
    html = Environment(loader=FileSystemLoader(HERE / "templates")).get_template("social.html.j2").render(
        dims=dims, rows=[[p["ratings"][k] for k in dims] for p in procs], ramp=RAMP, site_url=build.SITE_URL, **vals)
    out = HERE / "static" / "social.png"
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "social.html"
        page.write_text(html)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--window-size=1200,630", "--virtual-time-budget=4000", f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True)
    print(out)


if __name__ == "__main__":
    main()

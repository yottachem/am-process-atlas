"""Check every cited URL (process refs, vendor price and status sources, material data sheets) and write data/linkcheck.json.

Sites that refuse automated requests (401, 403, 429) are reported as blocked, not failed; check those by hand.
The weekly Actions run opens an issue when anything fails.
Usage: uv run python -m tools.linkcheck            # run the check, write data/linkcheck.json
       uv run python -m tools.linkcheck --report   # print failures from the last run as an issue body
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from atlas.load import load  # noqa: E402

OUT = ROOT / "data" / "linkcheck.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
BLOCKED = {401, 403, 429, 454, 999}  # 454: nonstandard bot block seen on cobod.com


def urls(ref):
    out = {}
    for p in ref["processes"]:
        for r in p["refs"]:
            out.setdefault(r["url"], set()).add(p["id"])
    for v in ref["vendors"]:
        for pr in v["products"]:
            for src in ([pr["price"]["source"]] if pr["price"] != "quote" else []) + ([pr["status"]["source"]] if "status" in pr else []):
                out.setdefault(src, set()).add(v["id"])
    for pid, n in ref["notes"].items():
        for r in n.get("refs", []):
            out.setdefault(r["url"], set()).add(f"note:{pid}")
    for m in ref["materials"]:
        if m["tds_url"]:
            out.setdefault(m["tds_url"], set()).add(m["id"])
    return out


def check(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=(15, 90), allow_redirects=True, stream=True)
        r.close()
        return r.status_code
    except requests.RequestException as e:
        return type(e).__name__


def run():
    used = urls(load())
    with ThreadPoolExecutor(8) as ex:
        status = dict(zip(used, ex.map(check, used)))
    rows = [{"url": u, "status": s, "used_by": sorted(used[u])} for u, s in sorted(status.items())]
    ok = [r for r in rows if isinstance(r["status"], int) and r["status"] < 400]
    blocked = [r for r in rows if r["status"] in BLOCKED]
    failed = [r for r in rows if r not in ok and r not in blocked]
    result = {"checked": date.today().isoformat(), "n_ok": len(ok), "n_blocked": len(blocked), "n_failed": len(failed),
              "failed": failed, "blocked": blocked}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    return result


if __name__ == "__main__":
    if "--report" in sys.argv:
        res = json.loads(OUT.read_text())
        if res["failed"]:
            print("\n".join(f"- {r['url']} ({r['status']}): {', '.join(r['used_by'])}" for r in res["failed"]))
    else:
        res = run()
        print(f"{res['n_ok']} ok, {res['n_blocked']} blocked, {res['n_failed']} failed")
        for r in res["failed"] + res["blocked"]:
            print(f"  {r['status']!s:24} {r['url']}")

"""Shared helpers for the events feed: watch registry, ledger, source tiers, secrets, run log, raw snapshots.
Ported from physical-ai-tracker (ingest/common.py), trimmed to what the AM feed uses."""
import csv
import json
import os
import subprocess
from datetime import date, datetime, timezone
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
RAW = ROOT / "data" / "raw"
RUNS = ROOT / "data" / "runs.json"
COMPANIES = REF / "companies.yaml"
LEDGER = REF / "ledger.csv"
LEDGER_COLUMNS = ["id", "company", "date", "type", "detail", "amount_usd", "qualifier", "status", "processes", "sources",
                  "accept", "added"]
# Event types the ledger holds. Order is detection priority (classify/events.py) and the site's filter order.
TYPES = ["launch", "acquisition", "merger", "funding", "wind_down", "exit"]
TYPE_LABELS = {"launch": "Launch", "acquisition": "Acquisition", "merger": "Merger", "funding": "Funding",
               "wind_down": "Wind-down", "exit": "Market exit"}
STATUSES = ["closed", "announced", "reported"]


def load_companies():
    """Registry entries with name and processes filled from vendors.yaml for vendor ids."""
    vendors = {v["id"]: v for v in yaml.safe_load((REF / "vendors.yaml").read_text())["vendors"]}
    out = {}
    for cid, c in yaml.safe_load(COMPANIES.read_text())["companies"].items():
        v = vendors.get(cid)
        out[cid] = {"name": v["name"] if v else c["name"], "processes": v["processes"] if v else c["processes"],
                    "vendor": bool(v)} | {k: x for k, x in c.items() if k not in ("name", "processes")}
    return out


def load_ledger():
    with LEDGER.open(newline="") as f:
        return list(csv.DictReader(f))


def domain_of(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def _matches(host, domain):
    return host == domain or host.endswith("." + domain)


@cache
def _tiers():
    t = yaml.safe_load((REF / "source_tiers.yaml").read_text())
    tier1 = [d for group in t["tier1"].values() for d in group]
    company = [d for c in load_companies().values() for d in [c["domain"], *c["other_domains"]] if d]
    return {"company": company, "wire": t["tier1"]["wires"], "tier1": tier1, "tier2": t["tier2"],
            "secondary": t["secondary"]}


def tier_of(url):
    """'tier1' (company domain or tier-1 list), 'tier2', 'secondary', or None for an unclassified domain."""
    host = domain_of(url)
    t = _tiers()
    if any(_matches(host, d) for d in t["company"] + t["tier1"]):
        return "tier1"
    for name in ("tier2", "secondary"):
        if any(_matches(host, d) for d in t[name]):
            return name
    return None


def primary(url, company):
    """True for the company's own domains and press wires: the sources a launch can be auto-accepted from."""
    host = domain_of(url)
    return any(_matches(host, d) for d in [company["domain"], *company["other_domains"], *_tiers()["wire"]] if d)


@cache
def secret(name, keychain_service):
    """Env var first, then macOS Keychain. Never log the return value."""
    if v := os.environ.get(name):
        return v
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", keychain_service, "-w"],
                           capture_output=True, text=True)
    except FileNotFoundError:  # not macOS (CI uses env vars)
        return None
    return r.stdout.strip() or None


def contact():
    """Contact email for SEC: CONTACT_EMAIL, else Keychain item am-process-atlas-contact (falls back to the
    lifesci-tracker-contact item on Josh's machine). Kept out of the repo."""
    return secret("CONTACT_EMAIL", "am-process-atlas-contact") or secret("LIFESCI_CONTACT_EMAIL", "lifesci-tracker-contact")


def user_agent():
    """SEC wants "name email"; URLs in the UA get 403."""
    if not (email := contact()):
        raise RuntimeError("SEC needs a contact email: set CONTACT_EMAIL or Keychain item am-process-atlas-contact")
    return f"am-process-atlas {email}"


def write_snapshot(source, payload):
    """Raw snapshot per run: data/raw/<source>/<YYYY-MM-DD>.json (gitignored)."""
    d = RAW / source
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{date.today().isoformat()}.json"
    path.write_text(json.dumps(payload, indent=1, sort_keys=True))
    return path


def record_run(source, **stats):
    """Last run per source for the status page: data/runs.json (committed, unlike raw snapshots)."""
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else {}
    runs[source] = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} | stats
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    RUNS.write_text(json.dumps(runs, indent=1, sort_keys=True) + "\n")

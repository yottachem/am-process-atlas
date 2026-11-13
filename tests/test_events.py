"""Events feed: registry, tiers, ledger and queue validity, headline rules, and acceptance decisions."""
import json
import re

import pytest
import yaml

from atlas.load import load
from classify.accept import candidate, decide
from classify.events import events, money, product_launch
from ingest.common import LEDGER_COLUMNS, REF, STATUSES, TYPES, load_companies, load_ledger, tier_of
from ingest.filings import QUEUE_COLUMNS, read_queue

D = load()
COMPANIES = load_companies()
LEDGER = load_ledger()
PROC_IDS = set(D["process_by_id"])
VENDOR_IDS = {v["id"] for v in D["vendors"]}


@pytest.mark.parametrize("cid", COMPANIES)
def test_registry_entry(cid):
    raw = yaml.safe_load((REF / "companies.yaml").read_text())["companies"][cid]
    c = COMPANIES[cid]
    if cid not in VENDOR_IDS:
        assert raw.get("name") and raw.get("processes"), "non-vendor entries need name and processes"
    else:
        assert "name" not in raw and "processes" not in raw, "vendor entries take name and processes from vendors.yaml"
    assert set(c["processes"]) <= PROC_IDS
    assert c["ownership"] in ("public", "private", "subsidiary", "defunct")
    assert c["news"]["terms"] and all(t.startswith('"') and t.endswith('"') for t in c["news"]["terms"])
    assert c["cik"] is None or isinstance(c["cik"], int)
    for d in [c["domain"], *c["other_domains"]]:
        assert d is None or re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", d), d
    assert c["newsroom_feed"] is None or c["newsroom_feed"].startswith("https://")


def test_tiers_disjoint():
    t = yaml.safe_load((REF / "source_tiers.yaml").read_text())
    tier1 = [d for g in t["tier1"].values() for d in g]
    lists = [tier1, t["tier2"], t["secondary"]]
    flat = [d for lst in lists for d in lst]
    assert len(flat) == len(set(flat))


def test_ledger_rows():
    ids = [e["id"] for e in LEDGER]
    assert len(ids) == len(set(ids))
    with (REF / "ledger.csv").open() as f:
        assert f.readline().strip().split(",") == LEDGER_COLUMNS
    for e in LEDGER:
        assert re.fullmatch(r"E\d{4}", e["id"])
        assert e["company"] in COMPANIES
        assert re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", e["date"])
        assert e["type"] in TYPES and e["status"] in STATUSES and e["accept"] in ("auto", "reviewed")
        assert e["detail"] and e["sources"]
        assert set(e["processes"].split()) <= PROC_IDS
        assert e["amount_usd"] == "" or e["type"] == "funding"
        for u in e["sources"].split():
            assert tier_of(u) is not None, f"{e['id']}: add {u} to source_tiers.yaml"


def test_queue_rows():
    for q in read_queue():
        assert list(q) == QUEUE_COLUMNS
        assert q["status"] in ("open", "accepted", "rejected", "dup", "auto")
        assert q["company"] in COMPANIES
        json.loads(q["parsed"] or "{}")


def test_seed_file():
    for path in (REF / "seed").glob("*.yaml"):
        for e in yaml.safe_load(path.read_text())["events"]:
            assert e["company"] in COMPANIES and e["type"] in TYPES
            assert set(e.get("processes", [])) <= PROC_IDS
            assert e["url"].startswith("https://")


@pytest.mark.parametrize("title,want", [
    ("Desktop Metal files for Chapter 11 bankruptcy protection", "wind_down"),
    ("Sintratec ceases operations after bankruptcy", "wind_down"),
    ("Stratasys to acquire Markforged for $42.5 million", "acquisition"),
    ("Nano Dimension completes acquisition of Desktop Metal", "acquisition"),
    ("Stratasys and Desktop Metal agree to merge", "merger"),
    ("3D Systems divests Geomagic software business", "exit"),
    ("Inkbit raises $30M Series B to scale vision-controlled jetting", "funding"),
    ("ICON lands $56 million", "funding"),
    ("Inkbit secures $10M loan", "funding"),
    ("Formlabs launches Fuse X1 large-format SLS printer", "launch"),
    ("FDA administration guidance on 3D printed devices", None),
    ("Pinnacle Associates Ltd. Buys 1,916,783 Shares of 3D Systems Corporation", None),
    ("Evology Manufacturing acquires 10th EOS 3D printer", None),
    ("Eplus3D and Hofmann CNC Partner to Combine Metal Additive Manufacturing with Precision CNC Machining", None),
])
def test_event_types(title, want):
    got = events(title)
    assert (got[0] if got else None) == want


def test_money_and_product():
    assert money("Inkbit raises $30M Series B") == [30_000_000]
    assert money("ICON lands $56 million") == [56_000_000]
    assert product_launch("  unveils Fuse X1 large-format SLS printer") == "product"
    assert product_launch("  unveils connected platform") == "loose"
    assert product_launch("  releases third-quarter results") is None
    assert product_launch("  launches new webinar series") is None


def art(title, url, cid="formlabs", tier=None, d="2026-11-01"):
    return {"title": title, "url": url, "company": cid, "date": d, "tier": tier or (tier_of(url) or "")}


def test_auto_launch_from_company_site():
    a = art("Formlabs unveils Fuse X1 large-format SLS printer", "https://formlabs.com/company/press/fuse-x1/")
    decision, row = decide(a, COMPANIES, [])
    assert decision == "auto" and row["type"] == "launch" and row["status"] == "closed"


def test_launch_from_trade_press_is_a_feed_item():
    a = art("Formlabs unveils Fuse X1 large-format SLS printer", "https://3dprintingindustry.com/news/x/")
    assert decide(a, COMPANIES, []) == (None, None)


def test_loose_launch_is_queued():
    a = art("SprintRay unveils connected digital workflow platform", "https://www.prnewswire.com/news/x", cid="sprintray")
    decision, p = decide(a, COMPANIES, [])
    assert decision == "queue" and any("platform" in r for r in p["reasons"])


def test_before_feed_start_is_a_feed_item():
    a = art("Inkbit secures $30M in Series B funding", "https://www.prnewswire.com/x", cid="inkbit", d="2021-07-20")
    assert decide(a, COMPANIES, []) == (None, None)


def test_company_name_does_not_make_a_product():
    a = art("3D Systems releases third-quarter results", "https://www.businesswire.com/news/x", cid="3d-systems")
    assert candidate(COMPANIES["3d-systems"], a) is None


def test_auto_funding_and_duplicate():
    a = art("Inkbit raises $30M Series B", "https://www.businesswire.com/news/inkbit", cid="inkbit")
    decision, row = decide(a, COMPANIES, [])
    assert decision == "auto" and row["amount_usd"] == "30000000"
    row["id"] = "E0001"
    again = art("Inkbit closes $31 million round", "https://techcrunch.com/x", cid="inkbit")
    assert decide(again, COMPANIES, [row]) == ("dup", "E0001")


@pytest.mark.parametrize("title", [
    "Stratasys to acquire Markforged for $42.5 million",
    "Desktop Metal files for Chapter 11",
    "Formlabs plans to launch a new SLS printer",
    "Inkbit secures $10M loan",
])
def test_always_reviewed(title):
    cid = next(k for k, c in COMPANIES.items() if any(t.strip('"').lower() in title.lower() for t in c["news"]["terms"]))
    decision, _ = decide(art(title, "https://www.businesswire.com/news/x", cid=cid), COMPANIES, [])
    assert decision == "queue"

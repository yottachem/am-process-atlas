"""SEC filings watcher: new filings for every registry company with a CIK go to the review queue.

Source: data.sec.gov submissions JSON (public domain; User-Agent with contact email; <= 10 requests/second).
Watched forms mark the six event types: Form D (funding), S-4/F-4 and merger proxies (merger), tender offers
(acquisition), and 8-K items 1.03 bankruptcy (wind-down), 2.01 completed acquisition or disposal, 2.05 exit costs
and 1.01 material agreements (type left to review). Foreign issuers report events on 6-K, which is queued as a
routine filing for review. Form D reports amount sold to date for an offering, not a round size, so it is evidence
for review, never auto-accepted. Ported from physical-ai-tracker.

Usage: uv run python -m ingest.filings [--since YYYY-MM-DD] [company-id ...]
"""
import argparse
import csv
import json
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

from ingest.common import ROOT, load_companies, load_ledger, record_run, user_agent, write_snapshot

QUEUE = ROOT / "data" / "review" / "queue.csv"
QUEUE_COLUMNS = ["qid", "found", "source", "company", "date", "kind", "suggested_type", "title", "url", "parsed",
                 "status"]

# form -> suggested type ("filing" = type left to review; None = decided by 8-K items)
FORMS = {"D": "funding", "S-4": "merger", "F-4": "merger", "DEFM14A": "merger", "PREM14A": "merger",
         "SC TO-T": "acquisition", "SC 14D9": "acquisition", "8-K": None, "6-K": "filing"}
ITEMS = {"1.01": "filing", "1.03": "wind_down", "2.01": "acquisition", "2.05": "exit"}


def sec_get(url, **kw):
    r = requests.get(url, headers={"User-Agent": user_agent()}, timeout=60, **kw)
    r.raise_for_status()
    time.sleep(0.15)
    return r


def filings(cik, since):
    d = sec_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json").json()
    r = d["filings"]["recent"]
    for form, fdate, acc, doc, items, desc in zip(r["form"], r["filingDate"], r["accessionNumber"],
                                                  r["primaryDocument"], r["items"], r["primaryDocDescription"]):
        if fdate < since:
            break
        if form not in FORMS:
            continue
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
        yield {"form": form, "date": fdate, "accession": acc, "items": items, "description": desc,
               "url": f"{base}/{doc}", "base": base}


def suggested_type(f):
    if FORMS[f["form"]]:
        return FORMS[f["form"]]
    # 1.03 and 2.01 outrank a 1.01 filed alongside them
    types = sorted((ITEMS[i] for i in f["items"].split(",") if i in ITEMS), key=lambda t: t == "filing")
    return types[0] if types else None


def form_d(f):
    """Offering amounts from a Form D primary_doc.xml."""
    x = ET.fromstring(sec_get(f"{f['base']}/primary_doc.xml").content)
    od = x.find(".//offeringData")

    def num(path):
        v = od.findtext(path) if od is not None else None
        return int(float(v)) if v and v.replace(".", "").isdigit() else v

    return {"total_offering": num("offeringSalesAmounts/totalOfferingAmount"),
            "amount_sold": num("offeringSalesAmounts/totalAmountSold"),
            "first_sale": od.findtext("typeOfFiling/dateOfFirstSale/value") if od is not None else None}


def read_queue():
    if not QUEUE.exists():
        return []
    with QUEUE.open() as fh:
        return list(csv.DictReader(fh))


def write_queue(rows):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, QUEUE_COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda q: (q["status"] != "open", q["date"], q["company"])))


def main(ids, since):
    companies = load_companies()
    queue = read_queue()
    known = {q["qid"] for q in queue}
    cited = " ".join(e["sources"] for e in load_ledger())
    snapshot, errors, added, seen = {}, {}, 0, 0
    for cid in ids or companies:
        c = companies[cid]
        if not c.get("cik"):
            continue
        try:
            found = list(filings(c["cik"], since))
        except (requests.RequestException, KeyError, ValueError) as e:
            errors[cid] = f"{type(e).__name__}: {e}"[:200]
            print(f"{cid}: ERROR {errors[cid]}", flush=True)
            continue
        snapshot[cid] = found
        seen += len(found)
        new = 0
        for f in found:
            qid = f"sec:{f['accession']}"
            kind = suggested_type(f)
            if qid in known or kind is None or f["accession"].replace("-", "") in cited:
                continue
            parsed = {"items": f["items"]} if f["items"] and f["form"] != "D" else {}
            if f["form"] == "D":
                try:
                    parsed |= form_d(f)
                except (requests.RequestException, ET.ParseError) as e:
                    parsed["parse_error"] = type(e).__name__
            queue.append({"qid": qid, "found": date.today().isoformat(), "source": "sec", "company": cid,
                          "date": f["date"], "kind": f["form"], "suggested_type": kind,
                          "title": f"{c['name']}: {f['form']} {f['description']}".strip(), "url": f["url"],
                          "parsed": json.dumps(parsed, sort_keys=True), "status": "open"})
            known.add(qid)
            new += 1
        added += new
        print(f"{cid}: {len(found)} watched filings since {since}, {new} queued", flush=True)
    write_snapshot("filings", {"since": since, "companies": snapshot, "errors": errors})
    record_run("sec", fetched=seen, kept=added, companies=len(snapshot), errors=len(errors),
               error_sample=[f"{k}: {v}"[:160] for k, v in list(errors.items())[:3]])
    write_queue(queue)
    print(f"{added} queued; {sum(q['status'] == 'open' for q in queue)} open in {QUEUE.relative_to(ROOT)}; "
          f"{len(errors)} errors")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=(date.today() - timedelta(days=14)).isoformat())
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    main(a.ids, a.since)

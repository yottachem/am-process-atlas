"""Acceptance rules: news headlines -> ledger (auto), review queue (open) or closed as a duplicate.

A headline is a candidate when it is dated on or after FEED_START and matches one of the six event types
(classify.events). Funding headlines also need a dollar figure. Launches count only from the company's own site or a
press wire (trade-press launch stories echo those releases) and only when they name hardware, a material, or at least
a platform; otherwise they stay feed items and are not queued. Events before FEED_START come from the reviewed seed.

Auto-accept (accept = auto) covers only two cases, both from tier-1 sources with a publisher link, naming the
company in the title and no other watched company:
  - funding: exactly one US-dollar amount, a closing verb or named round (raises, closes, Series B), no debt, grant,
    offering or "X invests in" wording, no talks or plans, and no conflict with a ledger row for the same round
  - launch: a product noun (printer, system, material, resin, powder ...) and no plans wording ("will launch");
    a launch naming only a platform or "3D printing" goes to review
Acquisitions, mergers, wind-downs and market exits always go to review, as does everything from tier 2 and below.
A funding figure within 10% of an existing row for the company, or a headline that repeats an accepted event
(same company and type, within 30 days, titles overlapping), closes as a duplicate naming the ledger id.

Usage: uv run python -m classify.accept      (processes every stored article not yet decided)
"""
import csv
import json
import re
from datetime import date

from classify.events import clean_round, events, money, non_usd, product_launch, qualifier, reported, round_of
from ingest.common import LEDGER as LEDGER_PATH
from ingest.common import LEDGER_COLUMNS, load_companies, load_ledger, primary, record_run, tier_of
from ingest.filings import read_queue, write_queue
from ingest.news import _has, norm_title, phrases, read_articles, write_articles

FEED_START = "2026-10-01"  # first daily run was 2026-11-11; it looked back 30+ days
STOP = {"a", "an", "the", "to", "of", "in", "on", "for", "and", "with", "as", "at", "its", "by", "from", "is", "it",
        "s", "new", "says", "after"}


def named(c, title):
    """True when one of the company's news terms appears in the title itself (context not required)."""
    return any(all(_has(title, p) for p in phrases(t)) for t in c["news"]["terms"])


def without_name(c, title):
    for t in c["news"]["terms"]:
        for p in phrases(t):
            title = re.sub(rf"(?<![\w-]){re.escape(p)}(?![\w-])", " ", title, flags=re.I)
    return title


def tokens(title):
    return {t for t in norm_title(title).split() if t not in STOP and not t.replace(".", "").isdigit()}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def close(a, b, tol=0.10):
    return a and b and abs(a - b) <= tol * max(a, b)


def num(v):
    return int(float(v)) if v not in ("", None) else None


def days_apart(a, b):
    """Days between two ledger dates; partial dates (YYYY-MM, YYYY) compare from their first day, empty = far."""
    if not a or not b:
        return 10**6
    pad = lambda d: date.fromisoformat((d + "-01-01")[:10] if len(d) == 4 else (d + "-01")[:10])  # noqa: E731
    return abs((pad(a) - pad(b)).days)


def candidate(c, article):
    """The event type a headline is queued under, or None when it stays a feed item."""
    title = article["title"]
    if article["date"] < FEED_START:
        return None
    found = events(title)
    if not found:
        return None
    kind = found[0]
    if kind == "launch" and not (product_launch(without_name(c, title)) and article["url"] and primary(article["url"], c)):
        return None
    if kind == "funding" and not money(title):
        return None
    return kind


def decide(article, companies, ledger):
    """Return (decision, payload): ("auto", ledger_row) | ("dup", ledger_id) | ("queue", parsed) | (None, None)."""
    title, cid = article["title"], article["company"]
    c = companies[cid]
    kind = candidate(c, article)
    if kind is None:
        return None, None
    amounts, rnd, rep = money(title), round_of(title), reported(title)
    parsed = {"type": kind, "events": events(title), "amounts": amounts, "round": rnd, "reported": rep}
    rows = [e for e in ledger if e["company"] == cid]
    for e in rows:
        if kind == "funding" and e["type"] == "funding" and any(close(a, num(e["amount_usd"])) for a in amounts):
            return "dup", e["id"]
        if e["type"] == kind and days_apart(e["date"], article["date"]) <= 30 \
                and jaccard(tokens(title), tokens(e["detail"])) >= 0.4:
            return "dup", e["id"]
    others = [k for k, o in companies.items() if k != cid and named(o, title)]
    reasons = []
    if article["tier"] != "tier1":
        reasons.append(f"tier {article['tier'] or 'unclassified'}")
    if not article["url"]:
        reasons.append("no publisher link")
    if kind not in ("funding", "launch"):
        reasons.append(f"{kind.replace('_', '-')} news is always reviewed")
    if not named(c, title):
        reasons.append("company not named in title")
    if others:
        reasons.append("also names " + ", ".join(others))
    if rep:
        reasons.append("talks or plans, not a completed event")
    if kind == "funding":
        if len(amounts) > 1:
            reasons.append("several amounts")
        if non_usd(title):
            reasons.append("amount not in US dollars")
        if not clean_round(title):
            reasons.append("not clearly a closed equity round (debt, grant, offering, third-party investment or no closing verb)")
        for e in rows:
            if rnd and e["type"] == "funding" and rnd.lower() in e["detail"].lower():
                reasons.append(f"same round as {e['id']} with a different amount")
    if kind == "launch" and product_launch(without_name(c, title)) == "loose":
        reasons.append("launch names a platform or 3D printing, not a specific printer or material")
    if reasons:
        return "queue", dict(parsed, reasons=reasons)
    row = {k: "" for k in LEDGER_COLUMNS}
    row.update(company=cid, date=article["date"], type=kind, detail=title,
               amount_usd=str(amounts[0]) if kind == "funding" else "", qualifier=qualifier(title) if kind == "funding" else "",
               status="closed", sources=article["url"], accept="auto", added=date.today().isoformat())
    return "auto", row


def next_id(ledger):
    return max((int(e["id"][1:]) for e in ledger), default=0) + 1


def main():
    companies = load_companies()
    ledger = load_ledger()
    queue = read_queue()
    done = {q["qid"] for q in queue}
    cited = " ".join(e["sources"] for e in ledger)
    today = date.today().isoformat()
    nid = next_id(ledger)
    counts = {"auto": 0, "dup": 0, "queue": 0}
    new_rows = []
    articles = read_articles()
    for a in articles:  # this stage owns the events and tier columns, so pattern or tier changes re-tag stored rows
        a["events"] = "|".join(events(a["title"]))
        if a["url"] or a["domain"]:
            a["tier"] = tier_of(a["url"] or "https://" + a["domain"]) or ""
    write_articles(articles)
    for a in sorted(articles, key=lambda a: a["date"]):
        qid = f"news:{a['aid']}"
        if qid in done or a["company"] not in companies or (a["url"] and a["url"] in cited):
            continue
        decision, payload = decide(a, companies, ledger + new_rows)
        if decision is None:
            continue
        counts[decision] += 1
        base = {"qid": qid, "found": today, "source": "news", "company": a["company"], "date": a["date"],
                "kind": a["tier"] or "unclassified", "title": a["title"], "url": a["url"]}
        if decision == "auto":
            payload["id"] = f"E{nid:04d}"
            nid += 1
            new_rows.append(payload)
            queue.append(dict(base, suggested_type=payload["type"], parsed=json.dumps({"ledger": payload["id"]}),
                              status="auto"))
        elif decision == "dup":
            queue.append(dict(base, suggested_type="", parsed=json.dumps({"duplicate_of": payload}), status="dup"))
        else:
            queue.append(dict(base, suggested_type=payload["type"], parsed=json.dumps(payload, sort_keys=True),
                              status="open"))
        done.add(qid)
    if new_rows:
        with open(LEDGER_PATH, "a", newline="") as fh:
            csv.DictWriter(fh, LEDGER_COLUMNS).writerows(new_rows)
    write_queue(queue)
    n_open = sum(q["status"] == "open" for q in queue)
    record_run("accept", auto=counts["auto"], dup=counts["dup"], queued=counts["queue"], open=n_open)
    print(f"auto-accepted {counts['auto']} (ledger {new_rows[0]['id'] + '..' + new_rows[-1]['id'] if new_rows else '-'}),"
          f" {counts['dup']} duplicates, {counts['queue']} queued; {n_open} open")


if __name__ == "__main__":
    main()

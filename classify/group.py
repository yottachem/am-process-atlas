"""Group open review-queue items that describe the same event, so one decision covers them all.

News items (same company and event type) link when they share a dollar figure (within 10%) dated within 45 days,
or, when either has no figure, when their titles overlap (token Jaccard >= 0.4) within 14 days. Links are
transitive. SEC filings group only when routine (6-K, or 8-Ks with only a 1.01 agreement item): same company, form
and items. Seed items never group. Groups are computed from the open items each time, never stored; the group id is
its lead item's qid. Ported from physical-ai-tracker.
"""
import json

from classify.accept import close, days_apart, jaccard, tokens

RANK = {"tier1": 0, "tier2": 1, "secondary": 2, "unclassified": 3}


def figures(q):
    return [f for f in json.loads(q["parsed"] or "{}").get("amounts") or [] if f]


def linked(a, b):
    if a["company"] != b["company"] or a["source"] != "news" or b["source"] != "news":
        return False
    if a["suggested_type"] != b["suggested_type"]:
        return False
    fa, fb = figures(a), figures(b)
    gap = days_apart(a["date"], b["date"])
    if fa and fb:
        return gap <= 45 and any(close(x, y) for x in fa for y in fb)
    return gap <= 14 and jaccard(tokens(a["title"]), tokens(b["title"])) >= 0.4


def sec_key(q):
    if q["source"] != "sec":
        return None
    items = json.loads(q["parsed"] or "{}").get("items", "")
    if q["kind"] == "6-K" or (q["kind"] == "8-K" and items and set(items.split(",")) <= {"1.01", "7.01", "8.01", "9.01"}):
        return (q["company"], q["kind"], items)
    return None


def lead_key(q):
    return (RANK.get(q["kind"], 2) if q["source"] == "news" else 0, not figures(q), not q["url"], q["date"], q["qid"])


def groups(rows):
    """Open rows -> list of groups (lists of rows), each sorted lead first; groups ordered by company then date."""
    rows = [r for r in rows if r["status"] == "open"]
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_key = {}
    for i, r in enumerate(rows):
        k = sec_key(r)
        if k:
            parent[find(i)] = find(by_key.setdefault(k, i))
    news = [i for i, r in enumerate(rows) if r["source"] == "news"]
    for x, i in enumerate(news):
        for j in news[x + 1:]:
            if linked(rows[i], rows[j]):
                parent[find(i)] = find(j)
    out = {}
    for i, r in enumerate(rows):
        out.setdefault(find(i), []).append(r)
    gs = [sorted(g, key=lead_key) for g in out.values()]
    return sorted(gs, key=lambda g: (g[0]["company"], min(r["date"] for r in g)))


def group_of(rows, qid):
    for g in groups(rows):
        if any(r["qid"] == qid for r in g):
            return g
    return None

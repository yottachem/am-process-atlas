"""Queue the seed timeline (reference/seed/*.yaml) for review. Idempotent: each item is queued once as seed:<id>.

The suggested type, status, processes and any extra sources ride in the queue row's parsed field, so the reviewer
can accept with the same values or change them.

Usage: uv run python -m classify.seed
"""
import json
from datetime import date

import yaml

from ingest.common import REF, TYPES, load_companies
from ingest.filings import read_queue, write_queue


def main():
    companies = load_companies()
    queue = read_queue()
    known = {q["qid"] for q in queue}
    added = 0
    for path in sorted((REF / "seed").glob("*.yaml")):
        for e in yaml.safe_load(path.read_text())["events"]:
            qid = f"seed:{e['id']}"
            if qid in known:
                continue
            assert e["company"] in companies and e["type"] in TYPES, e
            parsed = {k: e[k] for k in ("status", "processes", "sources", "note") if e.get(k)} | {"file": path.name}
            queue.append({"qid": qid, "found": date.today().isoformat(), "source": "seed", "company": e["company"],
                          "date": e["date"], "kind": "seed", "suggested_type": e["type"], "title": e["title"],
                          "url": e["url"], "parsed": json.dumps(parsed, sort_keys=True), "status": "open"})
            added += 1
    write_queue(queue)
    print(f"{added} seed items queued; {sum(q['status'] == 'open' for q in queue)} open")


if __name__ == "__main__":
    main()

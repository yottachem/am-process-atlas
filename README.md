# AM Process Atlas

When to use each additive manufacturing process: 39 processes rated on a published rubric, with sourced price,
feature, and size bands, a process picker, a vendor landscape, per-process reference pages, a materials explorer, a
buy-vs-outsource calculator, and a sourced industry events feed.

## Data

| File | Holds |
|---|---|
| `reference/processes.yaml` | Processes: bands, editorial ratings, text, refs (each says which band it supports), estimates, band notes |
| `reference/bands.yaml` | Band definitions and the rule for placing a process in a band |
| `reference/rubric.yaml` | Rating definitions; detail, size, and system cost are derived from bands |
| `reference/vendors.yaml` | Vendors, products, entry prices (sourced or "quote") |
| `reference/families.yaml` | ISO/ASTM 52900 families |
| `reference/pairs.yaml` | X-vs-Y pages: process ids and a mechanism-only intro |
| `analysis/claims.yaml` | Summary sentences with the condition each rests on |
| `reference/companies.yaml` | Events-feed watch registry (vendor ids plus companies that left the market): news terms, domains, CIK, newsroom feed |
| `reference/source_tiers.yaml` | Which source domains can be auto-accepted (tier 1) and which always go to review |
| `reference/ledger.csv` | Accepted events: launch, acquisition, merger, funding, wind_down, exit |
| `reference/seed/` | Pre-feed timeline, queued for review by `classify.seed` |
| `data/review/queue.csv` | Review queue (open, accepted, rejected, dup, auto), written only by `classify.review` and `classify.accept` |
| `data/news/articles.csv` | Stored headlines (titles, links, dates, publishers; no article text) |
| `data/runs.json` | Last run per events source, shown on the status page |

## Commands

```
uv run pytest                        # data and build checks
LAUNCH_GATE=1 uv run pytest          # also fails on open verify flags, missing refs, failing claims
uv run python site/build.py --preview  # build site/dist with preview banner and review flags
uv run python -m analysis.claims     # print every claim and whether it holds
uv run python -m tools.linkcheck     # check every cited URL, write data/linkcheck.json
uv run python site/social.py         # re-render site/static/social.png (needs local Chrome)

# events feed (daily in Actions behind SCHEDULE_ON)
uv run python -m ingest.filings --since YYYY-MM-DD   # SEC filings -> review queue (needs CONTACT_EMAIL or Keychain)
uv run python -m ingest.news --days 3                 # Bing, Google News, GDELT, newsroom feeds -> articles.csv
uv run python -m classify.accept                      # acceptance rules: auto, duplicate, or queue
uv run python -m classify.review list                 # open items grouped by event
uv run python -m classify.review accept QID --type launch --process sls [--status announced] [--group]
uv run python -m classify.review reject QID --reason "..." [--group]
```

Code MIT, data CC-BY-4.0.

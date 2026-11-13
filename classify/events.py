"""Headline event detection and figure parsing (regex; no model calls).

events(title) returns every event type the headline matches, in detection priority: a headline that matches both
"acquires" and "launches" is an acquisition. money() and round_of() pull figures; reported() spots talks and plans,
which never become closed events. Ported from physical-ai-tracker and trimmed to the six AM event types.
"""
import re

from ingest.common import TYPES

PATTERNS = {
    "wind_down": r"\b(shut(?:s|ting)? down|bankrupt\w*|Chapter (?:7|11)|winds? down|wind-down|ceases? operations|"
                 r"insolven\w*|liquidat\w*|receivership|(?:enters?|into) administration|StaRUG|"
                 r"assignment for the benefit of creditors|closes? (?:its )?doors)\b",
    "merger": r"\b(merg(?:e|er|es|ing)|business combination|combine[sd]?|combination with)\b",
    "acquisition": r"\b(acquires?|acquired|acquisition|to buy|buys|takeover|tender offer|"
                   r"assets? (?:sold|sale) to)\b",
    "exit": r"\b(exits?|exiting|discontinu\w+|withdraw(?:s|ing)? from|sunsets?|divest\w*|"
            r"sells? (?:its|the) [\w\s-]{0,40}?(?:business|unit|division|line|portfolio)|"
            r"ends? (?:production|sales|support) of)\b",
    "funding": r"\b(rais(?:e|es|ed|ing)|funding|financing|Series [A-H]\b|seed round|pre-seed|investment|"
               r"backed by|round|loan|credit facility|grant|(?:secur|land|clos|bag|nab|snag)\w* (?:a |an )?(?:US)?[$€£])",
    "launch": r"\b(launch\w*|unveil\w*|introduc\w+|debuts?|releases?|announces? (?:the )?new|reveals?|"
              r"rolls? out|now shipping|begins? shipping|now available)\b",
}
assert list(PATTERNS) == ["wind_down", "merger", "acquisition", "exit", "funding", "launch"] and set(PATTERNS) == set(TYPES)
RX = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
# Deal words that are not corporate deals: share trades, shopping, customers buying printers, partnerships.
NOT_DEAL = re.compile(r"\b(shares|stake in|share-count|Black Friday|Cyber Monday|to buy:|picked \w+ \w+ to buy|partner\w*|"
                      r"(?:acquires?|buys|purchases?) (?:[\w-]+ ){0,4}(?:printers?|systems?|machines?))\b", re.I)

# A launch is auto-accepted only when it names hardware or a material (PRODUCT); a launch that only says "platform",
# "solution" or "3D printing" (LOOSE) is queued, since it may be software or a service.
PRODUCT = re.compile(r"\b(printers?|systems?|machines?|materials?|resins?|powders?|filaments?|alloys?|photopolymers?)\b",
                     re.I)
LOOSE = re.compile(r"\b(platforms?|solutions?|series|lines?|cells?|3D print\w*|additive)\b", re.I)
NOT_PRODUCT = re.compile(r"\b(software|app|webinar|podcast|event|conference|course|training|award|report|results|"
                         r"earnings|quarter|guidance|dividend|shareholders|white ?paper|case study|partnership|partners|"
                         r"ecosystem|digital dentistry)\b", re.I)

MONEY = re.compile(r"(?:US)?[$€£]\s?(\d+(?:\.\d+)?)\s?(billion|bn|b|million|mn|m)\b", re.I)
SCALE = {"b": 1e9, "bn": 1e9, "billion": 1e9, "m": 1e6, "mn": 1e6, "million": 1e6}
ROUND = re.compile(r"\b(pre-seed|seed|Series [A-H](?:[- ]?\d|\+)?(?: extension)?|bridge round|growth round)\b", re.I)
REPORTED = re.compile(r"\b(in talks|talks|seeks?|seeking|reportedly|report(?:s|ed)? that|eyes|eyeing|nears?|"
                      r"considering|plan(?:s|ning|ned)?|looking to|could|said to|sources say|explores?|exploring|"
                      r"weighs?|in discussions|aims? to|set to|expected to|would|may|will|to (?:launch|buy|acquire|merge))\b",
                      re.I)
CLOSED = re.compile(r"\b(rais(?:es|ed)|clos(?:es|ed)|secur(?:es|ed)|lands?|landed|completes?|completed|"
                    r"announces? \$|Series [A-H]|seed round|pre-seed)\b", re.I)
NOT_EQUITY = re.compile(r"\b(debt|loan|credit facility|grant|award\w*|contract|government|program|invests? (?:in|into)|"
                        r"investment (?:in|into)|offering|convertible|notes)\b", re.I)


def events(title):
    deal_noise = NOT_DEAL.search(title)
    return [k for k in PATTERNS if RX[k].search(title) and not (deal_noise and k in ("acquisition", "merger"))]


def _usd(num, unit):
    return int(round(float(num) * SCALE[unit.lower()]))


def money(title):
    """Amounts in the headline. Euro and pound figures are kept at face value and flagged for review by accept."""
    return [_usd(n, u) for n, u in MONEY.findall(title)]


def non_usd(title):
    return bool(re.search(r"[€£]\s?\d", title))


def round_of(title):
    m = ROUND.search(title)
    return m.group(1).title().replace("Pre-Seed", "Pre-seed") if m else ""


def reported(title):
    return bool(REPORTED.search(title))


def clean_round(title):
    """A headline that states a closed equity round: closing verb, and no debt, grant, offering or third-party investment."""
    return bool(CLOSED.search(title)) and not NOT_EQUITY.search(title)


def product_launch(title):
    """"product" for a launch headline that names hardware or a material, "loose" when it only names a platform or
    3D printing generally, None otherwise (software, results, events, partnerships, or no launch verb).
    Pass the title with the company name removed (3D Systems would otherwise match "systems")."""
    if not RX["launch"].search(title) or NOT_PRODUCT.search(title):
        return None
    if PRODUCT.search(title):
        return "product"
    return "loose" if LOOSE.search(title) else None


def qualifier(title):
    """Ledger qualifier for the headline's figure: at_least, up_to, approx or ''."""
    t = title.lower()
    if re.search(r"\b(at least|more than|over|north of|upwards of)\s+(?:us)?\$", t):
        return "at_least"
    if re.search(r"\b(up to|as much as)\s+(?:us)?\$", t):
        return "up_to"
    if re.search(r"\b(about|around|nearly|roughly|almost|some|approximately)\s+(?:us)?\$|~\$", t):
        return "approx"
    return ""

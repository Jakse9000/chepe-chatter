"""
events.py — collect upcoming cultural events automatically.

Source: GAM Cultural (gamcultural.com), the main agenda for the Central
Valley. Its pages embed schema.org "Event" data as JSON-LD, so we read
that structured data directly — much more robust than scraping HTML.

Returns a list of events in the same shape the rest of the program uses
(day / month / title / desc / where / link). Titles come in Spanish and
are translated on the build step, exactly like the news.

If the source is unreachable or changes, this returns an empty list and
build.py falls back to the manual `events:` list in feeds.yaml — so the
site never ends up with an empty calendar.
"""

import re
import json
import datetime as dt
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

GAM_URL = "https://www.gamcultural.com/cr"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Chepe Chatter events)"})
    with urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "ignore")


def _find_events(obj, out):
    """Recursively collect any schema.org node whose @type ends in 'Event'."""
    if isinstance(obj, dict):
        if str(obj.get("@type", "")).endswith("Event"):
            out.append(obj)
        for v in obj.values():
            _find_events(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _find_events(v, out)


def collect_events(limit=8):
    try:
        html = _fetch(GAM_URL)
    except Exception as e:
        print(f"   ⚠ event source unreachable, using fallback list: {e}")
        return []

    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    nodes = []
    for b in blocks:
        try:
            _find_events(json.loads(b), nodes)
        except Exception:
            continue

    # GitHub's servers run on UTC — up to 6 hours ahead of Costa Rica — so
    # "today" must be computed in local time or events would vanish at 6 pm.
    today = dt.datetime.now(ZoneInfo("America/Costa_Rica")).date()
    out, seen = [], set()
    for e in nodes:
        try:
            date = dt.datetime.fromisoformat(e.get("startDate", "")).date()
        except Exception:
            continue
        if date < today:                      # only upcoming
            continue
        url = (e.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)

        loc = e.get("location", {})
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        where = loc.get("name", "") if isinstance(loc, dict) else ""

        desc = re.sub(r"\s+", " ", (e.get("description") or "")).strip()

        out.append({
            "_date": date,
            "day": f"{date.day:02d}",
            "month": MONTHS[date.month - 1],
            "title": (e.get("name") or "").strip(),
            "desc": desc[:200],
            "where": where,
            "link": url,
        })

    out.sort(key=lambda x: x["_date"])
    for o in out:
        o.pop("_date", None)
    return out[:limit]


if __name__ == "__main__":          # quick manual test: python events.py
    for ev in collect_events():
        print(f"{ev['day']} {ev['month']}  {ev['title'][:55]}  @ {ev['where']}")

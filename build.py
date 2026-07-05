#!/usr/bin/env python3
"""
build.py — the heart of Chepe Chatter.

Run it with:   python build.py

What it does, in order:
  1. Read feeds.yaml (your sources + events).
  2. Fetch every RSS feed (skipping any that are down).
  3. Sort each story into a stream and judge foreigner-relevance.
  4. Translate Spanish<->English (cached, free engine by default).
  5. Write a finished bilingual website to the  site/  folder.

You normally never edit this file. To change sources, edit feeds.yaml.
"""

import io
import re
import csv
import sys
import json
import time
import html
import urllib.request
import datetime as dt
from pathlib import Path

import yaml
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

import classify
import classify_ai as CL_AI
import translate as T
import events as EV
import weather as WX

ROOT = Path(__file__).parent
OUT = ROOT / "site"
NOW = dt.datetime.now(dt.timezone.utc)

STREAM_DEFS = [
    ("world",  "🌎", "Costa Rica in the world", "Costa Rica en el mundo",
     "International coverage about Costa Rica", "Cobertura internacional sobre Costa Rica"),
    ("living", "🏡", "Living here", "Vivir aquí",
     "Local news that matters if you're a foreigner", "Noticias locales que importan si eres extranjero"),
    ("business", "💼", "Business", "Negocios",
     "Economy, companies & money in Costa Rica", "Economía, empresas y dinero en Costa Rica"),
    ("sports", "⚽", "Sports", "Deportes",
     "Because the game brings everyone together", "Porque el deporte nos une a todos"),
]


def clean(text):
    """Strip HTML tags and tidy whitespace from a feed summary."""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def age_from_dt(ts):
    """Turn a datetime into a short '2h' / '3d' badge."""
    secs = max((NOW - ts).total_seconds(), 0)
    if secs > 30 * 86400:            # ancient / unknown date — show nothing
        return ""
    if secs < 3600:
        return f"{int(secs // 60)}m"
    if secs < 86400:
        return f"{int(secs // 3600)}h"
    return f"{int(secs // 86400)}d"


def age_label(published):
    """Turn a struct_time into a short '2h' / '3d' badge."""
    if not published:
        return ""
    try:
        ts = dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
    except Exception:
        return ""
    return age_from_dt(ts)


def sort_key(published):
    try:
        return dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
    except Exception:
        return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _fetch_url(url, timeout=20):
    """Download a feed with a hard timeout — feedparser has none by default,
    so one hanging server could otherwise stall the whole hourly build."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Chepe Chatter)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_all(feeds):
    raw = []
    for feed in feeds:
        print(f" → {feed['name']}")
        try:
            parsed = feedparser.parse(_fetch_url(feed["url"]))
            if parsed.bozo and not parsed.entries:
                print(f"   ⚠ could not read feed, skipping")
                continue
            for e in parsed.entries[:20]:
                raw.append((feed, e))
        except Exception as ex:
            print(f"   ⚠ error, skipping: {ex}")
    return raw


def parse_item(feed, entry):
    """Parse a feed entry into an item dict. Classification happens later."""
    title = clean(entry.get("title", ""))
    summary = clean(entry.get("summary", entry.get("description", "")))
    if len(summary) > 320:
        summary = summary[:317].rsplit(" ", 1)[0] + "…"

    published = entry.get("published_parsed") or entry.get("updated_parsed")
    return {
        "source": feed["name"],
        "age": age_label(published),
        "url": entry.get("link", "#"),
        "title": title, "summary": summary,
        "origin": feed["lang"],
        "_feed": feed,
        "_sort": sort_key(published),
    }


# A road-closure item is only kept if it's about Costa Rica. The news search
# occasionally returns closures in other countries (Mexico, Bogotá, …).
_CR_PLACES = ("costa rica", "san josé", "san jose", "cartago", "heredia",
              "alajuela", "limón", "limon", "puntarenas", "guanacaste",
              "circunvalación", "circunvalacion", " ruta ", "ccss", "mopt")
_FOREIGN = ("méxico", "mexico", "bogotá", "bogota", "colombia", "madrid",
            "perú ", "peru ", "argentina", "chile", "guatemala", "honduras",
            "el salvador", "ecuador", "venezuela", "brasil", "brazil")


def _cr_traffic_ok(item):
    t = (item.get("title", "") + " " + item.get("summary", "")).lower()
    if any(p in t for p in _CR_PLACES):
        return True
    if any(f in t for f in _FOREIGN):
        return False
    return True            # the feed already targets Costa Rica — default keep


def _norm_title(title):
    """Normalise a title for cross-source duplicate detection: drop a trailing
    ' - Source' suffix (Google News adds one), punctuation and case."""
    t = (title or "").strip()
    if " - " in t:
        t = t.rpartition(" - ")[0]
    t = re.sub(r"[^\w\s]", "", t.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()[:60]


def _junk_title(title):
    """Drop empty Google-News entries like 'The Costa Rica News - The Costa Rica News'."""
    t = (title or "").strip()
    if len(t) < 12:
        return True
    if " - " in t:
        head, _, src = t.rpartition(" - ")
        if head.strip().lower() == src.strip().lower():
            return True
    return False


def classify_items(items):
    """
    Assign each item a 'stream' and 'relevant' flag.
    Uses the Claude AI classifier when ANTHROPIC_API_KEY is set, otherwise
    falls back to the keyword rules in classify.py. Returns the engine name.
    """
    # Traffic (road closures) is always shown. Everything else — local AND
    # international — is judged by the AI for relevance, so lifestyle/travel
    # fluff from the news search gets filtered out too.
    judged = [it for it in items if it["_feed"].get("stream") != "traffic"]
    ai_results = CL_AI.classify_batch(judged) if CL_AI.available() else None

    ji = 0
    for it in items:
        feed = it["_feed"]
        fs = feed.get("stream")
        if fs == "traffic":
            it["stream"] = "traffic"
            it["relevant"] = _cr_traffic_ok(it)   # drop foreign road closures
            continue
        if fs == "world":
            # International coverage stays in world, but anything the AI sees
            # as sport or business moves to its own section, and the AI also
            # judges relevance (keyword fallback can't, so it shows them).
            if ai_results is not None:
                ai_stream, ai_rel = ai_results[ji]
                ji += 1
                if ai_stream == "sports":
                    it["stream"], it["relevant"] = "sports", True
                elif ai_stream == "business":
                    it["stream"], it["relevant"] = "business", ai_rel
                else:
                    it["stream"], it["relevant"] = "world", ai_rel
            else:
                it["stream"], it["relevant"] = "world", True
                ji += 1
            continue
        # Local feeds: AI picks stream + relevance; trusted expat sources kept.
        if ai_results is not None:
            stream, relevant = ai_results[ji]
            if feed.get("trust"):
                relevant = True
            it["stream"], it["relevant"] = stream, relevant
        else:
            it["stream"], it["relevant"] = classify.classify(it, feed)
        ji += 1

    return "Claude AI" if ai_results is not None else "keyword rules"


# ---- Rolling archive ---------------------------------------------------
# Stories stay on the site for up to ARCHIVE_HOURS after their feed drops
# them (feeds only hold ~20 items), and they rescue the site if every feed
# is briefly unreachable. Persisted between builds via the workflow cache.
ARCHIVE_FILE = ROOT / ".archive.json"
ARCHIVE_HOURS = 48


def load_archive():
    """Load archived items, dropping anything not seen for ARCHIVE_HOURS."""
    try:
        data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cutoff = NOW - dt.timedelta(hours=ARCHIVE_HOURS)
    out = {}
    for url, rec in data.items():
        try:
            if dt.datetime.fromisoformat(rec["archived"]) >= cutoff:
                out[url] = rec
        except Exception:
            continue
    return out


def merge_archive(buckets, caps):
    """Archive everything currently shown, bring back recently-seen items
    that vanished from their feeds, then re-sort and re-cap each bucket."""
    archive = load_archive()

    current = set()
    for k in buckets:
        for it in buckets[k]:
            current.add(it["url"])
            rec = {kk: vv for kk, vv in it.items() if kk != "_sort"}
            rec["_sort"] = it["_sort"].isoformat()
            rec["archived"] = NOW.isoformat()      # last seen in a feed
            archive[it["url"]] = rec

    restored = 0
    for url, rec in archive.items():
        if url in current:
            continue
        it = dict(rec)
        it.pop("archived", None)
        try:
            it["_sort"] = dt.datetime.fromisoformat(it["_sort"])
        except Exception:
            it["_sort"] = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        it["age"] = age_from_dt(it["_sort"])
        bucket = buckets.get(it.get("stream"))
        if bucket is not None:
            bucket.append(it)
            restored += 1

    for k in buckets:
        buckets[k].sort(key=lambda x: x["_sort"], reverse=True)
        buckets[k] = buckets[k][:caps[k]]

    if restored:
        print(f"  + {restored} recent stor{'y' if restored == 1 else 'ies'} kept from the 48h archive")
    try:
        ARCHIVE_FILE.write_text(json.dumps(archive, ensure_ascii=False, default=str),
                                encoding="utf-8")
    except Exception:
        pass


def translate_item(it, cfg):
    """Fill in both languages for an item we've decided to keep."""
    do = it["relevant"] or cfg["site"].get("translate_hidden", False)
    title, summary = it["title"], it["summary"]
    if it["origin"] == "es":
        it["title_es"], it["summary_es"] = title, summary
        it["title_en"] = T.translate(title, "es", "en") if do else title
        it["summary_en"] = T.translate(summary, "es", "en") if do else summary
    else:
        it["title_en"], it["summary_en"] = title, summary
        it["title_es"] = T.translate(title, "en", "es") if do else title
        it["summary_es"] = T.translate(summary, "en", "es") if do else summary
    return it


def fetch_sheet_sponsors(csv_url):
    """
    Read self-service sponsors from the published Google Sheet (CSV).
    Only rows whose `approved` cell is truthy are included — that's the
    owner's one-click publish control.
    """
    if not csv_url:
        return []
    # Cache-buster: Google serves a cached copy of the same CSV URL for a long
    # time, which delayed newly-approved sponsors. A unique param + no-cache
    # headers force a fresh read on every build.
    sep = "&" if "?" in csv_url else "?"
    fetch_url = f"{csv_url}{sep}_cb={int(time.time())}"
    try:
        req = urllib.request.Request(fetch_url, headers={
            "User-Agent": "Chepe Chatter",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"   ⚠ sponsor sheet unreachable, skipping: {e}")
        return []

    # Read by fixed column position (not header name): Google's CSV export can
    # merge the header row with the first data row, so position is more robust.
    # Columns: 0 timestamp, 1 company, 2 tagline_en, 3 tagline_es, 4 link,
    #          5 logo, 6 section, 7 email, 8 approved
    rows = list(csv.reader(io.StringIO(text)))
    out = []
    for cols in rows[1:]:                       # skip the header row
        if len(cols) < 9:
            continue
        cols = [(c or "").strip() for c in cols]
        if cols[8].lower() not in ("true", "yes", "1", "y", "x", "✓"):
            continue
        if not cols[1]:
            continue
        secs = [s.strip() for s in cols[6].replace(";", ",").split(",") if s.strip()]
        out.append({
            "name": cols[1],
            "tagline_en": cols[2],
            "tagline_es": cols[3],
            "logo": cols[5],
            "link": cols[4] or "#",
            "sections": secs or ["living"],
        })
    if out:
        print(f"  + {len(out)} approved sponsor(s) from the sheet")
    return out


def _clean_link(url):
    """Normalise a website link — people type 'www.x.com' without a scheme,
    which would otherwise act as a broken relative link. Default to '#'."""
    url = (url or "").strip()
    if not url:
        return "#"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# Image hosts whose links are signed and expire (or block other websites
# from embedding them). A logo from these WILL break within days/weeks, so
# we reject it up front — better no logo than a broken one.
_BAD_LOGO_HOSTS = ("fbcdn.net", "fbsbx.com", "cdninstagram.com", "licdn.com")


def _clean_logo(url):
    """Only accept a logo that is really an image file URL — a stray or broken
    link (e.g. a page or folder) would otherwise wreck the card layout."""
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = url.split("/")[2].lower() if url.count("/") >= 2 else ""
    if any(bad in host for bad in _BAD_LOGO_HOSTS):
        return ""                    # e.g. Facebook photo links — they expire
    path = url.split("?")[0].split("#")[0].lower()
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return url if ext in ("png", "jpg", "jpeg", "gif", "webp", "svg") else ""


def build_sponsors(cfg):
    """
    Pick one sponsor per section (rotating hourly when several are assigned),
    filling in any missing translated tagline. Returns {section_id: sponsor|None}.
    Sponsors come from feeds.yaml AND the self-service Google Sheet.
    """
    sponsors = list(cfg.get("sponsors") or [])
    sponsors += fetch_sheet_sponsors(cfg["site"].get("sponsor_sheet_csv", ""))
    for sp in sponsors:
        sp["logo"] = _clean_logo(sp.get("logo", ""))
        sp["link"] = _clean_link(sp.get("link", ""))
    for sp in sponsors:
        en, es = sp.get("tagline_en", ""), sp.get("tagline_es", "")
        if en and not es:
            sp["tagline_es"] = T.translate(en, "en", "es")
        elif es and not en:
            sp["tagline_en"] = T.translate(es, "es", "en")
        sp.setdefault("tagline_en", "")
        sp.setdefault("tagline_es", "")
        sp.setdefault("logo", "")
        sp.setdefault("link", "#")

    rot = int(NOW.timestamp() // 3600)          # advances once per hour
    by_section = {}
    for sec in ("world", "living", "business", "sports", "traffic", "events"):
        matches = [sp for sp in sponsors
                   if sec in sp.get("sections", []) or "all" in sp.get("sections", [])]
        # Real (paying) sponsors take priority — a placeholder "spot available"
        # card only shows when the section has NO real sponsor.
        real = [sp for sp in matches if not sp.get("placeholder")]
        pool = real if real else matches
        by_section[sec] = pool[rot % len(pool)] if pool else None
    return by_section


def build_events(events, fallback_link):
    out = []
    for ev in events or []:
        title_es = ev.get("title", "")
        desc_es = ev.get("desc", "")
        out.append({
            "day": ev.get("day", ""), "month": ev.get("month", ""),
            "where": ev.get("where", ""),
            "link": ev.get("link") or fallback_link,
            "title_es": title_es, "desc_es": desc_es,
            "title_en": T.translate(title_es, "es", "en"),
            "desc_en": T.translate(desc_es, "es", "en"),
        })
    return out


def main():
    cfg = yaml.safe_load((ROOT / "feeds.yaml").read_text(encoding="utf-8"))
    feeds = cfg["feeds"]
    limit = cfg["site"].get("max_items_per_stream", 9)

    print("Fetching feeds…")
    raw = fetch_all(feeds)
    print(f"Got {len(raw)} stories. Parsing…")

    parsed = []
    seen = set()
    seen_titles = set()
    for feed, entry in raw:
        link = entry.get("link", "")
        if link and link in seen:
            continue
        seen.add(link)
        it = parse_item(feed, entry)
        if _junk_title(it["title"]):
            continue
        # Same story picked up by two sources? Keep only the first copy.
        nt = _norm_title(it["title"])
        if nt and nt in seen_titles:
            continue
        seen_titles.add(nt)
        parsed.append(it)

    print("Classifying…")
    engine = classify_items(parsed)
    print(f"  sorted {len(parsed)} stories via {engine}")

    buckets = {"world": [], "living": [], "business": [], "sports": [], "traffic": []}
    for it in parsed:
        if it["stream"] == "traffic" and not it["relevant"]:
            continue                       # foreign road closure — drop it
        buckets[it["stream"]].append(it)

    # newest first, cap per stream, THEN translate only what we keep
    max_traffic = cfg["site"].get("max_traffic", 6)
    caps = {k: (max_traffic if k == "traffic" else limit + 4) for k in buckets}
    for k in buckets:
        buckets[k].sort(key=lambda x: x["_sort"], reverse=True)
        # keep a few extra hidden items so "show everything" has content
        buckets[k] = buckets[k][:caps[k]]
        for it in buckets[k]:
            it.pop("_feed", None)
            translate_item(it, cfg)

    # Bring back recently-seen stories whose feed dropped them (48h archive).
    merge_archive(buckets, caps)

    # Safety net: never deploy an EMPTY site. If every feed failed and the
    # archive is empty too, abort — GitHub keeps the previous version live.
    if not any(buckets.values()):
        print("✖ No stories at all (all feeds down?) — aborting so the "
              "previous site stays up.")
        sys.exit(1)

    streams = []
    for sid, icon, t_en, t_es, s_en, s_es in STREAM_DEFS:
        streams.append({
            "id": sid, "icon": icon,
            "title_en": t_en, "title_es": t_es,
            "subtitle_en": s_en, "subtitle_es": s_es,
            "cards": buckets[sid],
        })

    # Try to collect live cultural events; fall back to the manual list.
    print("Collecting cultural events…")
    collected = EV.collect_events(cfg["site"].get("max_events", 8))
    if collected:
        print(f"  got {len(collected)} live events from GAM Cultural")
        raw_events = collected
    else:
        print("  using manual events from feeds.yaml")
        raw_events = cfg.get("events", [])
    events = build_events(raw_events, cfg.get("events_fallback_link", "#"))
    sponsors = build_sponsors(cfg)
    print("Fetching weather…")
    wx = WX.get_weather(cfg["site"].get("weather_lat", 9.9281),
                        cfg["site"].get("weather_lon", -84.0907))
    T.flush()

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("index.html")
    htmlout = tpl.render(
        site=cfg["site"],
        streams=streams,
        traffic=buckets["traffic"],
        events=events,
        sponsors=sponsors,
        weather=wx,
        sources=[f["name"] for f in feeds],
        generated=NOW.strftime("%d %b %Y, %H:%M UTC"),
    )

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(htmlout, encoding="utf-8")

    # SEO helpers: robots.txt + sitemap.xml (uses site.url from feeds.yaml).
    site_url = (cfg["site"].get("url") or "").rstrip("/")
    if site_url:
        (OUT / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n",
            encoding="utf-8")
        (OUT / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{site_url}/</loc>"
            f"<lastmod>{NOW.strftime('%Y-%m-%d')}</lastmod>"
            "<changefreq>hourly</changefreq></url>\n"
            "</urlset>\n",
            encoding="utf-8")

    counts = ", ".join(f"{k}:{len(v)}" for k, v in buckets.items())
    print(f"✅ Built site/index.html  ({counts}, events:{len(events)})")


if __name__ == "__main__":
    main()

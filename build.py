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

import sys
import time
import html
import datetime as dt
from pathlib import Path

import yaml
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

import classify
import classify_ai as CL_AI
import translate as T
import events as EV

ROOT = Path(__file__).parent
OUT = ROOT / "site"
NOW = dt.datetime.now(dt.timezone.utc)

STREAM_DEFS = [
    ("world",  "🌎", "Costa Rica in the world", "Costa Rica en el mundo",
     "International coverage about Costa Rica", "Cobertura internacional sobre Costa Rica"),
    ("living", "🏡", "Living here", "Vivir aquí",
     "Local news that matters if you're a foreigner", "Noticias locales que importan si eres extranjero"),
    ("sports", "⚽", "Sports", "Deportes",
     "Because the game brings everyone together", "Porque el deporte nos une a todos"),
]


def clean(text):
    """Strip HTML tags and tidy whitespace from a feed summary."""
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def age_label(published):
    """Turn a struct_time into a short '2h' / '3d' badge."""
    if not published:
        return ""
    try:
        ts = dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
    except Exception:
        return ""
    delta = NOW - ts
    secs = delta.total_seconds()
    if secs < 3600:
        return f"{int(secs // 60)}m"
    if secs < 86400:
        return f"{int(secs // 3600)}h"
    return f"{int(secs // 86400)}d"


def sort_key(published):
    try:
        return dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
    except Exception:
        return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def fetch_all(feeds):
    raw = []
    for feed in feeds:
        print(f" → {feed['name']}")
        try:
            parsed = feedparser.parse(feed["url"])
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


def classify_items(items):
    """
    Assign each item a 'stream' and 'relevant' flag.
    Uses the Claude AI classifier when ANTHROPIC_API_KEY is set, otherwise
    falls back to the keyword rules in classify.py. Returns the engine name.
    """
    # International-feed items are always world + relevant — no judgement needed.
    local = [it for it in items if it["_feed"].get("stream") != "world"]
    ai_results = CL_AI.classify_batch(local) if CL_AI.available() else None

    li = 0
    for it in items:
        feed = it["_feed"]
        if feed.get("stream") == "world":
            it["stream"], it["relevant"] = "world", True
            continue
        if ai_results is not None:
            it["stream"], it["relevant"] = ai_results[li]
        else:
            it["stream"], it["relevant"] = classify.classify(it, feed)
        li += 1

    return "Claude AI" if ai_results is not None else "keyword rules"


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
    for feed, entry in raw:
        link = entry.get("link", "")
        if link and link in seen:
            continue
        seen.add(link)
        parsed.append(parse_item(feed, entry))

    print("Classifying…")
    engine = classify_items(parsed)
    print(f"  sorted {len(parsed)} stories via {engine}")

    buckets = {"world": [], "living": [], "sports": []}
    for it in parsed:
        buckets[it["stream"]].append(it)

    # newest first, cap per stream, THEN translate only what we keep
    for k in buckets:
        buckets[k].sort(key=lambda x: x["_sort"], reverse=True)
        # keep a few extra hidden items so "show everything" has content
        buckets[k] = buckets[k][:limit + 4]
        for it in buckets[k]:
            it.pop("_feed", None)
            translate_item(it, cfg)

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
    T.flush()

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("index.html")
    htmlout = tpl.render(
        site=cfg["site"],
        streams=streams,
        events=events,
        sources=[f["name"] for f in feeds],
        generated=NOW.strftime("%d %b %Y, %H:%M UTC"),
    )

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(htmlout, encoding="utf-8")
    counts = ", ".join(f"{k}:{len(v)}" for k, v in buckets.items())
    print(f"✅ Built site/index.html  ({counts}, events:{len(events)})")


if __name__ == "__main__":
    main()

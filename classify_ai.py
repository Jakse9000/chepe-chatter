"""
classify_ai.py — smarter news sorting using Claude (Anthropic).

For each LOCAL news item it judges two things:
  • stream:   "sports" or "living"
  • relevant: would this matter to a foreigner LIVING in Costa Rica?

It reads articles in batches (cheap, fast) and caches every verdict on
disk, so the same article is never judged twice.

NO API KEY? Then `available()` returns False and build.py automatically
falls back to the keyword rules in classify.py — the site still works.

TO TURN THIS ON:
  1. Get an API key at https://console.anthropic.com  (Settings → API keys).
  2. Add it to your repo as a secret named ANTHROPIC_API_KEY
     (Settings → Secrets and variables → Actions → New repository secret).
  That's it — the workflow already passes it in.

Model can be overridden with the CLASSIFIER_MODEL environment variable.
"""

import os
import json
import time
import hashlib
import datetime as dt
import urllib.request
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")
# 15 per call keeps the JSON reply comfortably inside max_tokens.
BATCH = 15
MAX_TOKENS = 2000
# Bump this whenever the prompt changes — it invalidates old cached verdicts.
PROMPT_VERSION = "v3"
# Cached verdicts unused for this many days are pruned (headlines rarely return).
CACHE_MAX_AGE_DAYS = 30

CACHE_FILE = Path(__file__).parent / ".classify_cache.json"
_TODAY = dt.date.today().isoformat()


def _load_cache():
    """Load the cache, migrating old [stream, relevant] entries to the new
    [stream, relevant, last_used] format so pruning can work."""
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for k, v in raw.items():
        if isinstance(v, list) and len(v) == 2:
            v = [v[0], v[1], _TODAY]
        if isinstance(v, list) and len(v) == 3:
            out[k] = v
    return out


_cache = _load_cache()

INSTRUCTIONS = (
    "You sort Costa Rican news for an audience of FOREIGNERS LIVING IN "
    "Costa Rica (expats, residents, newcomers) who read in English.\n"
    "For each article decide two things:\n"
    '  "stream": "sports" if it is primarily about sport, athletes, teams or '
    'competitions; "business" if it is primarily about the economy, companies, '
    "investment, real estate, employment, banking, markets, trade or the "
    'tourism industry; otherwise "living".\n'
    '  "relevant": true if a foreigner living in Costa Rica would plausibly '
    "want to read it. Be reasonably INCLUSIVE. This covers:\n"
    "    - practical life: immigration/residency, cost of living, healthcare and "
    "the Caja, banking, taxes, driving/licences, safety, weather or disasters, "
    "utilities, housing, transport/airports;\n"
    "    - AND general national interest: national politics and the economy, "
    "major public events, business, the environment, and notable human-interest "
    "or cultural stories about Costa Rica.\n"
    "  Set relevant FALSE ONLY for clear noise: celebrity/farándula gossip, "
    "horoscopes, generic lifestyle or self-help filler, clickbait, hyper-local "
    "notices with no wider interest, and routine minor crime blotter.\n"
    "Return ONLY a JSON array, one object per article, no markdown, no prose:\n"
    '[{"i": <index>, "stream": "living|business|sports", "relevant": true|false}, ...]'
)


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _save_cache():
    """Persist the cache, dropping entries not used for CACHE_MAX_AGE_DAYS."""
    cutoff = (dt.date.today() - dt.timedelta(days=CACHE_MAX_AGE_DAYS)).isoformat()
    pruned = {k: v for k, v in _cache.items() if v[2] >= cutoff}
    try:
        CACHE_FILE.write_text(json.dumps(pruned, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _key(it):
    raw = (PROMPT_VERSION + "|" + it.get("title", "") + "|" + it.get("summary", "")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _call(api_key, articles):
    """articles: list of (index, title, summary). Returns parsed JSON array."""
    blocks = []
    for idx, title, summary in articles:
        blocks.append(f"{idx}. TITLE: {title}\nSUMMARY: {summary}")
    prompt = INSTRUCTIONS + "\n\nArticles:\n" + "\n\n".join(blocks)

    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    text = resp["content"][0]["text"]
    # Be forgiving: slice the JSON array out of the response.
    arr = json.loads(text[text.index("["): text.rindex("]") + 1])
    return arr


def classify_batch(items):
    """
    items: list of dicts with 'title' and 'summary' (LOCAL items only).
    Returns a list of (stream, relevant) aligned with items, or None if the
    AI path fails (signals build.py to use the keyword fallback instead).
    """
    if not items:
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    results = [None] * len(items)
    todo = []
    for i, it in enumerate(items):
        ck = _key(it)
        if ck in _cache:
            _cache[ck][2] = _TODAY            # mark as recently used
            results[i] = (_cache[ck][0], _cache[ck][1])
        else:
            todo.append(i)

    try:
        for b in range(0, len(todo), BATCH):
            chunk = todo[b:b + BATCH]
            articles = [(j, items[j]["title"][:200], items[j]["summary"][:300]) for j in chunk]
            # One transient API hiccup shouldn't sink the whole AI run:
            # retry each batch once before giving up.
            for attempt in range(2):
                try:
                    arr = _call(api_key, articles)
                    break
                except Exception:
                    if attempt == 1:
                        raise
                    time.sleep(2)
            by_i = {int(o.get("i", -1)): o for o in arr}
            for j in chunk:
                o = by_i.get(j, {})
                stream = o.get("stream", "living")
                if stream not in ("living", "business", "sports"):
                    stream = "living"
                relevant = bool(o.get("relevant", False))
                if stream == "sports":
                    relevant = True            # sports has its own home
                results[j] = (stream, relevant)
                _cache[_key(items[j])] = [stream, relevant, _TODAY]
        _save_cache()
    except Exception as e:
        print(f"   ⚠ AI classifier failed, using keyword fallback: {e}")
        return None

    for i in range(len(results)):
        if results[i] is None:
            results[i] = ("living", False)
    return results

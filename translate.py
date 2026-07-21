"""
translate.py — turn Spanish into English (and English into Spanish).

Default engine: deep-translator's Google backend. It is FREE and needs
NO API key. Translations are cached on disk so we never translate the
same headline twice (faster builds, gentler on the free service).

UPGRADING TO DEEPL LATER (better quality):
    1. pip install deep-translator already includes DeepL support.
    2. Get a DeepL API key (free tier available).
    3. Set an environment variable DEEPL_API_KEY=your-key
    4. That's it — the code below auto-detects the key and uses DeepL.
"""

import os
import json
import time
import hashlib
import datetime as dt
import urllib.request
import urllib.error
from pathlib import Path

CACHE_FILE = Path(__file__).parent / ".translation_cache.json"
# Cached translations unused for this many days are pruned, so the cache
# file can't grow forever (headlines rarely come back after a month).
CACHE_MAX_AGE_DAYS = 30
_TODAY = dt.date.today().isoformat()

# Which engine is active this run. Included in the cache key so that switching
# from Google to DeepL (or back) re-translates instead of reusing old results.
ENGINE = "deepl" if os.environ.get("DEEPL_API_KEY") else "google"

# Bump to discard old cached translations (e.g. after fixing a bug that cached
# failed translations as the untranslated original).
CACHE_VERSION = "v3"

def _load_cache():
    """Load the cache, migrating old plain-string entries to the new
    [text, last_used] format so pruning can work."""
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for k, v in raw.items():
        if isinstance(v, str):
            v = [v, _TODAY]
        if isinstance(v, list) and len(v) == 2:
            out[k] = v
    return out


_cache = _load_cache()


def _save_cache():
    """Persist the cache, dropping entries not used for CACHE_MAX_AGE_DAYS."""
    cutoff = (dt.date.today() - dt.timedelta(days=CACHE_MAX_AGE_DAYS)).isoformat()
    pruned = {k: v for k, v in _cache.items() if v[1] >= cutoff}
    try:
        CACHE_FILE.write_text(json.dumps(pruned, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _key(text, src, tgt):
    h = hashlib.md5(f"{CACHE_VERSION}:{ENGINE}:{src}->{tgt}:{text}".encode("utf-8")).hexdigest()
    return h


# DeepL wants regional codes for some targets (EN -> EN-US, PT -> PT-PT).
_DEEPL_SOURCE = {"es": "ES", "en": "EN", "pt": "PT"}
_DEEPL_TARGET = {"es": "ES", "en": "EN-US", "pt": "PT-PT"}


def _deepl(text, src, tgt):
    """Call DeepL's REST API directly (more reliable than the wrapper lib)."""
    key = os.environ["DEEPL_API_KEY"].strip()
    base = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
    body = json.dumps({
        "text": [text],
        "source_lang": _DEEPL_SOURCE.get(src, src.upper()),
        "target_lang": _DEEPL_TARGET.get(tgt, tgt.upper()),
    }).encode("utf-8")
    req = urllib.request.Request(
        base + "/v2/translate", data=body,
        headers={"Authorization": "DeepL-Auth-Key " + key,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode("utf-8", "ignore")
        raise RuntimeError(f"DeepL HTTP {e.code}: {detail}")
    return data["translations"][0]["text"]


def _engines(src, tgt):
    """
    Ordered list of (name, translate_callable) backends to try in turn.

    DeepL goes first when a key is present (best quality). The FREE Google and
    MyMemory backends always follow as fallbacks, so a broken, expired or
    quota-exhausted DeepL key — or an engine that is temporarily blocked from
    the build server's IP — no longer leaves every headline in Spanish.
    """
    engines = []
    if os.environ.get("DEEPL_API_KEY"):
        engines.append(("deepl", lambda text: _deepl(text, src, tgt)))
    try:
        from deep_translator import GoogleTranslator
        engines.append(("google", GoogleTranslator(source=src, target=tgt).translate))
    except Exception:
        pass
    try:
        # MyMemory runs on different infrastructure, so it often still works
        # when Google is rate-limited/blocked from a data-centre IP.
        from deep_translator import MyMemoryTranslator
        _MM = {"es": "es-ES", "en": "en-US", "pt": "pt-PT"}
        mm = MyMemoryTranslator(source=_MM.get(src, src), target=_MM.get(tgt, tgt))
        engines.append(("mymemory", mm.translate))
    except Exception:
        pass
    return engines


def translate(text, src, tgt):
    """
    Translate `text` from `src` to `tgt` ('es'/'en').
    Returns the translated string, or the ORIGINAL text if translation
    fails for any reason (so the site always builds).
    """
    return translate_flagged(text, src, tgt)[0]


# How many items fell back to the untranslated original this run. build.py
# reads this at the end so a broken engine shows up loudly in the CI log.
fail_count = 0


def translate_flagged(text, src, tgt):
    """
    Like translate(), but returns a (text, ok) tuple.

    `ok` is True when the returned text is genuinely in the target language
    (a real translation, a cache hit, or nothing-to-do), and False when every
    engine failed and we fell back to the ORIGINAL untranslated text. Callers
    use this to label a card honestly instead of always claiming "Translated".
    """
    global fail_count
    text = (text or "").strip()
    if not text or src == tgt:
        return text, True

    ck = _key(text, src, tgt)
    if ck in _cache:
        _cache[ck][1] = _TODAY               # mark as recently used
        return _cache[ck][0], True

    # Try up to 3 times — DeepL's free tier rate-limits bursts with a 429,
    # which a short backoff usually clears. Each attempt walks the whole
    # engine fallback chain, so DeepL failing hands off to Google/MyMemory.
    last_err = None
    for attempt in range(3):
        try:
            out = _do_translate(text, src, tgt)
            if out:
                _cache[ck] = [out, _TODAY]   # cache ONLY successful translations
                if len(_cache) % 10 == 0:
                    _save_cache()
                return out, True
        except Exception as e:
            last_err = e
        time.sleep(1.0 * (attempt + 1))   # 1s, 2s backoff

    # IMPORTANT: on failure we return the original but DO NOT cache it, so the
    # next build retries instead of permanently storing untranslated text.
    fail_count += 1
    print(f"   ⚠ translation failed ({src}->{tgt}), keeping original this run: {last_err}")
    return text, False


def _do_translate(text, src, tgt):
    """One translation pass. Walks the engine fallback chain until one returns
    a result; long text is chunked on sentence breaks. Raises only if EVERY
    engine failed, so the caller can retry/back off."""
    engines = _engines(src, tgt)
    if not engines:
        raise RuntimeError("no translation engine available")
    last_err = None
    for name, fn in engines:
        try:
            out = _translate_with(fn, text)
            if out:
                return out
        except Exception as e:
            last_err = e            # try the next engine in the chain
    if last_err:
        raise last_err
    return ""


def _translate_with(fn, text):
    """Run one engine callable, chunking text longer than the API limit."""
    if len(text) <= 4500:
        out = fn(text)
    else:
        parts, buf = [], ""
        for sentence in text.replace("。", ". ").split(". "):
            if len(buf) + len(sentence) > 4500:
                parts.append(fn(buf)); buf = ""
            buf += sentence + ". "
        if buf:
            parts.append(fn(buf))
        out = " ".join(parts)
    return (out or "").strip()


def flush():
    """Call once at the end of a build to persist the cache."""
    _save_cache()

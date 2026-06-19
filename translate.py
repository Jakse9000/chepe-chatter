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
import urllib.request
import urllib.error
from pathlib import Path

CACHE_FILE = Path(__file__).parent / ".translation_cache.json"

# Which engine is active this run. Included in the cache key so that switching
# from Google to DeepL (or back) re-translates instead of reusing old results.
ENGINE = "deepl" if os.environ.get("DEEPL_API_KEY") else "google"

# Bump to discard old cached translations (e.g. after fixing a bug that cached
# failed translations as the untranslated original).
CACHE_VERSION = "v3"

try:
    _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
except Exception:
    _cache = {}


def _save_cache():
    try:
        CACHE_FILE.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
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


def _engine(src, tgt):
    """Return a translate(text)->text callable for the best available engine."""
    if os.environ.get("DEEPL_API_KEY"):
        return lambda text: _deepl(text, src, tgt)
    from deep_translator import GoogleTranslator
    tr = GoogleTranslator(source=src, target=tgt)
    return tr.translate


def translate(text, src, tgt):
    """
    Translate `text` from `src` to `tgt` ('es'/'en').
    Returns the translated string, or the ORIGINAL text if translation
    fails for any reason (so the site always builds).
    """
    text = (text or "").strip()
    if not text or src == tgt:
        return text

    ck = _key(text, src, tgt)
    if ck in _cache:
        return _cache[ck]

    # Try up to 3 times — DeepL's free tier rate-limits bursts with a 429,
    # which a short backoff usually clears.
    last_err = None
    for attempt in range(3):
        try:
            out = _do_translate(text, src, tgt)
            if out:
                _cache[ck] = out          # cache ONLY successful translations
                if len(_cache) % 10 == 0:
                    _save_cache()
                return out
        except Exception as e:
            last_err = e
        time.sleep(1.0 * (attempt + 1))   # 1s, 2s backoff

    # IMPORTANT: on failure we return the original but DO NOT cache it, so the
    # next build retries instead of permanently storing untranslated text.
    print(f"   ⚠ translation failed ({src}->{tgt}), keeping original this run: {last_err}")
    return text


def _do_translate(text, src, tgt):
    """One translation attempt. Long text is chunked on sentence breaks."""
    fn = _engine(src, tgt)
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

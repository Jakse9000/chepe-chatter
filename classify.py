"""
classify.py — decide which stream a story belongs in, and whether
it's relevant to a foreigner living in Costa Rica.

Matching is done on WHOLE WORDS (not substrings), so short keywords like
"gol" no longer match inside unrelated words like "golpe", and "juegos"
no longer matches inside "videojuegos". This needs no API key and runs
instantly. Later you can replace `classify()` with an AI call; the rest
of the program won't change.
"""

import re

# Words that signal a story matters to a foreigner living here.
# Lowercase; Spanish + English. Add your own over time.
RELEVANT_KEYWORDS = [
    # immigration / residency
    "migración", "migracion", "residencia", "residente", "residentes",
    "extranjero", "extranjera", "extranjeros", "visa", "visas",
    "dimex", "cédula", "cedula", "pasaporte", "naturalización",
    "immigration", "residency", "foreigner", "foreigners", "expat", "expats", "nomad",
    # money / cost of living
    "caja", "ccss", "seguro", "impuesto", "impuestos", "tributario", "hacienda",
    "banco", "bancos", "colón", "colones", "dólar", "dolar", "alquiler",
    "tarifa", "tarifas", "aresep", "electricidad", "gasolina", "combustible",
    "tax", "taxes", "rent", "utilities",
    # health / safety / daily life
    "salud", "hospital", "clínica", "clinica", "covid", "dengue", "seguridad",
    "estafa", "estafas", "licencia", "cosevi", "riteve", "marchamo",
    "healthcare", "safety", "scam", "driving",
    # weather / environment that affects everyone
    "lluvia", "lluvias", "tormenta", "huracán", "huracan", "inundación",
    "inundacion", "inundaciones", "sismo", "temblor", "terremoto",
    "volcán", "volcan", "weather", "storm", "flood", "earthquake", "hurricane",
    # travel / airports
    "aeropuerto", "vuelo", "vuelos", "aerolínea", "aerolinea", "turismo",
    "frontera", "airport", "flight", "flights", "tourism", "border",
]

# Words that route a local story into the BUSINESS stream (headline only).
BUSINESS_KEYWORDS = [
    "economía", "economia", "económico", "economico", "económica", "economica",
    "empresa", "empresas", "empresario", "empresarios", "negocio", "negocios",
    "inversión", "inversion", "inversiones", "inversionista", "inversionistas",
    "exportación", "exportacion", "exportaciones", "importación", "importacion",
    "empleo", "empleos", "desempleo", "pib", "inflación", "inflacion",
    "banco central", "bccr", "tipo de cambio", "mercado", "mercados",
    "bolsa", "comercio", "industria", "zona franca", "zonas francas",
    "economy", "economic", "business", "businesses", "company", "companies",
    "investment", "investors", "exports", "imports", "jobs", "employment",
    "unemployment", "inflation", "gdp", "market", "markets", "trade",
    "startup", "startups", "real estate", "free trade zone",
]

# Words that route a local story into the SPORTS stream.
# Curated to avoid ambiguous tokens (dropped: "liga", "partido", "juegos",
# "gol" kept only as exact word, etc.).
SPORTS_KEYWORDS = [
    "fútbol", "futbol", "football", "soccer",
    "saprissa", "alajuelense", "herediano", "cartaginés", "cartagines",
    "liga deportiva", "la sele", "selección nacional", "seleccion nacional",
    "eliminatoria", "eliminatorias",
    # "mundial" alone is ambiguous (also means "world/global"), so require
    # a football context instead:
    "mundial 2026", "copa mundial", "copa del mundo", "world cup", "fifa",
    "gol", "goles", "goleador", "torneo", "torneos",
    "deporte", "deportes", "deportivo", "deportiva", "deportivos", "deportivas",
    "surf", "surfing", "surfista", "maratón", "maraton", "marathon",
    "atletismo", "atleta", "atletas", "ciclismo", "ciclista", "cycling",
    "tenis", "tennis", "baloncesto", "basketball",
    "olímpico", "olímpicos", "olimpico", "olympics", "olympic",
    "boxeo", "boxing", "natación", "natacion", "swimming",
    "voleibol", "volleyball", "sport", "sports",
]


def _has(text, words):
    """True if any keyword appears as a WHOLE WORD in text (accent-aware)."""
    t = (text or "").lower()
    for w in words:
        # \b word boundaries; works around accented letters under Unicode.
        if re.search(r"\b" + re.escape(w) + r"\b", t):
            return True
    return False


def classify(item, feed):
    """
    Returns (stream, relevant) where stream is one of:
        'world', 'living', 'business', 'sports'
    and relevant is True/False (False = hidden by the default filter).
    """
    title = item.get("title", "")
    text = f"{title} {item.get('summary','')}"

    # International coverage feeds go straight to the world stream.
    if feed.get("stream") == "world":
        return "world", True

    # Sports and business are judged on the HEADLINE only — precise, avoids
    # false positives from a stray word buried in an unrelated summary.
    if _has(title, SPORTS_KEYWORDS):
        return "sports", True   # sports has its own home, always shown
    if _has(title, BUSINESS_KEYWORDS):
        return "business", True

    # Relevance uses the fuller title+summary text for better recall.
    relevant = feed.get("trust", False) or _has(text, RELEVANT_KEYWORDS)
    return "living", relevant

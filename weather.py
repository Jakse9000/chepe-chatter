"""
weather.py — current weather for San José, fetched at build time.

Source: Open-Meteo (open-meteo.com) — completely free, no API key needed.
Because the site rebuilds hourly, the weather chip updates hourly too.

Returns a small dict (temp, emoji, bilingual description) or None if the
service can't be reached — in which case the chip is simply hidden.
"""

import json
import urllib.request

API = ("https://api.open-meteo.com/v1/forecast"
       "?latitude={lat}&longitude={lon}"
       "&current=temperature_2m,weather_code"
       "&timezone=America/Costa_Rica")

# WMO weather codes -> emoji + English / Spanish label.
CODES = {
    0:  ("☀️", "Clear", "Despejado"),
    1:  ("🌤️", "Mainly clear", "Mayormente despejado"),
    2:  ("⛅", "Partly cloudy", "Parcialmente nublado"),
    3:  ("☁️", "Overcast", "Nublado"),
    45: ("🌫️", "Fog", "Niebla"),
    48: ("🌫️", "Fog", "Niebla"),
    51: ("🌦️", "Light drizzle", "Llovizna ligera"),
    53: ("🌦️", "Drizzle", "Llovizna"),
    55: ("🌦️", "Heavy drizzle", "Llovizna intensa"),
    61: ("🌧️", "Light rain", "Lluvia ligera"),
    63: ("🌧️", "Rain", "Lluvia"),
    65: ("🌧️", "Heavy rain", "Lluvia intensa"),
    66: ("🌧️", "Freezing rain", "Lluvia helada"),
    67: ("🌧️", "Freezing rain", "Lluvia helada"),
    71: ("🌨️", "Light snow", "Nieve ligera"),
    73: ("🌨️", "Snow", "Nieve"),
    75: ("🌨️", "Heavy snow", "Nieve intensa"),
    77: ("🌨️", "Snow grains", "Granos de nieve"),
    80: ("🌦️", "Light showers", "Aguaceros ligeros"),
    81: ("🌦️", "Showers", "Aguaceros"),
    82: ("⛈️", "Heavy showers", "Aguaceros fuertes"),
    85: ("🌨️", "Snow showers", "Aguaceros de nieve"),
    86: ("🌨️", "Snow showers", "Aguaceros de nieve"),
    95: ("⛈️", "Thunderstorm", "Tormenta"),
    96: ("⛈️", "Thunderstorm, hail", "Tormenta con granizo"),
    99: ("⛈️", "Thunderstorm, hail", "Tormenta con granizo"),
}


def get_weather(lat=9.9281, lon=-84.0907):
    try:
        url = API.format(lat=lat, lon=lon)
        req = urllib.request.Request(url, headers={"User-Agent": "Chepe Chatter"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        cur = data["current"]
        temp = round(cur["temperature_2m"])
        emoji, en, es = CODES.get(int(cur["weather_code"]), ("🌡️", "—", "—"))
        return {"temp": temp, "emoji": emoji, "desc_en": en, "desc_es": es}
    except Exception as e:
        print(f"   ⚠ weather unavailable, hiding chip: {e}")
        return None


if __name__ == "__main__":
    print(get_weather())

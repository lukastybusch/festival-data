#!/usr/bin/env python3
"""
Baut aus den Einzel-Datenbanken die fertige festivals.json für die App.

Quellen (alle optional, rückwärtskompatibel):
  series/<id>.json        – Festival-Marke: Name, Ort, Farben, Website, Ticket-Anbieter, Infos
  artists/<slug>.json     – Künstler: Name, Genre, Bild-URL, Spotify-URL
  affiliate/providers.json– Ticket-Anbieter: deine Affiliate-ID + Basis-URL
  genres.json             – Genre-Vokabular mit Farben
  festivals/<edition>.json– Edition: Datum + Line-up (referenziert Serie & Künstler)

Ergebnis: festivals.json (self-contained), die die App wie bisher lädt.

Aufruf (im Repo-Wurzelverzeichnis):  python3 build_festivals.py
"""

import json, glob, os


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm(name: str) -> str:
    return (name or "").strip().lower()


# --- Datenbanken laden -------------------------------------------------------

series = {}
for p in glob.glob("series/*.json"):
    s = load(p)
    series[s["id"]] = s

artists = {}
for p in glob.glob("artists/*.json"):
    a = load(p)
    artists[norm(a["name"])] = a

providers = {}
if os.path.exists("affiliate/providers.json"):
    providers = load("affiliate/providers.json").get("providers", {})

genres = {}
if os.path.exists("genres.json"):
    for g in load("genres.json").get("genres", []):
        genres[norm(g["name"])] = g


# --- Helfer ------------------------------------------------------------------

def pick(edition, ser, key, default=None):
    """Editions-Wert hat Vorrang, sonst Serie, sonst Default."""
    return edition.get(key) if edition.get(key) is not None else ser.get(key, default)


def ticket_url(edition):
    t = edition.get("ticket")
    if not t:
        return None
    if t.get("url"):                      # direkte URL überschreibt alles
        return t["url"]
    prov = providers.get(t.get("provider", ""))
    if prov and t.get("eventId") is not None:
        return f'{prov["base"]}{t["eventId"]}{prov.get("suffix", "")}'
    return None


# --- Festivals zusammenbauen -------------------------------------------------

out = []
for p in sorted(glob.glob("festivals/*.json")):
    fest = load(p)
    ser = series.get(fest.get("seriesId"), {})

    merged = {
        "id": fest["id"],
        "name": pick(fest, ser, "name", ""),
        "location": pick(fest, ser, "location", ""),
        "genre": pick(fest, ser, "genre", ""),
        "startDate": fest["startDate"],
        "endDate": fest["endDate"],
        "color": pick(fest, ser, "color", "#111827"),
        "accent": pick(fest, ser, "accent", "#7C3AED"),
    }

    if pick(fest, ser, "website"):
        merged["website"] = pick(fest, ser, "website")
    if pick(fest, ser, "info"):
        merged["info"] = pick(fest, ser, "info")
    url = ticket_url(fest)
    if url:
        merged["ticketURL"] = url

    # Line-up anreichern (Künstler-Join)
    schedule = []
    for item in fest.get("schedule", []):
        name = item.get("artist") or item.get("title")
        entry = {"title": name, "date": item["date"]}
        if item.get("stage"):
            entry["stage"] = item["stage"]

        a = artists.get(norm(name)) if name else None
        if a:
            if a.get("genre"):   entry["genre"] = a["genre"]
            if a.get("image"):   entry["image"] = a["image"]
            if a.get("spotify"): entry["spotify"] = a["spotify"]

        g = genres.get(norm(entry.get("genre", "")))
        if g and g.get("color"):
            entry["genreColor"] = g["color"]

        schedule.append(entry)

    if schedule:
        merged["schedule"] = schedule

    out.append(merged)

with open("festivals.json", "w", encoding="utf-8") as f:
    json.dump({"version": 1, "festivals": out}, f, ensure_ascii=False, indent=2)

print(f"{len(out)} Festivals gebaut → festivals.json")

#!/usr/bin/env python3
"""
Reichert artists/ automatisch mit Spotify-Daten an: Bild-URL, Spotify-Link,
Genre-Vorschlag. Sammelt alle Künstlernamen aus festivals/*.json, sucht sie auf
Spotify und schreibt/aktualisiert artists/<slug>.json.
MANUELL gesetzte Felder bleiben erhalten (das Skript füllt nur Leeres auf).

Voraussetzung: kostenlose Spotify-Developer-App → Client ID + Secret.
Als Umgebungsvariablen setzen (NICHT im Code speichern!):

    export SPOTIFY_CLIENT_ID=deine_id
    export SPOTIFY_CLIENT_SECRET=dein_secret
    python3 enrich_artists.py

Spotify-Terms beachten: Bild-URLs nur referenzieren (nicht selbst re-hosten),
Bilder nicht verändern, in der App "In Spotify öffnen" + Attribution zeigen.
"""

import os, re, glob, json, time, base64, sys
import urllib.parse, urllib.request, urllib.error

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit("Bitte SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET als Umgebungsvariablen setzen.")


def get_token():
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=data,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["access_token"]


def search_artist(name, token):
    q = urllib.parse.urlencode({"q": name, "type": "artist", "limit": 1})
    req = urllib.request.Request(
        f"https://api.spotify.com/v1/search?{q}",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            items = json.load(r).get("artists", {}).get("items", [])
            return items[0] if items else None
    except urllib.error.HTTPError as e:
        if e.code == 429:                     # Rate-Limit → warten und erneut
            time.sleep(int(e.headers.get("Retry-After", "2")) + 1)
            return search_artist(name, token)
        raise


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "artist"


# --- Künstlernamen aus allen Festivals sammeln ------------------------------
names = set()
for p in glob.glob("festivals/*.json"):
    fest = json.load(open(p, encoding="utf-8"))
    for it in fest.get("schedule", []):
        n = it.get("artist") or it.get("title")
        if n:
            names.add(n.strip())

os.makedirs("artists", exist_ok=True)
token = get_token()
created = updated = skipped = 0

for name in sorted(names):
    path = f"artists/{slug(name)}.json"
    existing = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

    # Schon angereichert ODER schon erfolglos gesucht → API-Call sparen.
    # Das macht Re-Runs schnell: nur der erste Lauf sucht wirklich alles.
    if existing.get("image") and existing.get("spotify"):
        skipped += 1
        continue
    if existing.get("spotifyChecked") and not existing.get("image"):
        skipped += 1
        continue

    art = search_artist(name, token)
    time.sleep(0.25)                           # sanft mit der Rate umgehen

    data = dict(existing)
    data.setdefault("name", name)
    data["spotifyChecked"] = True              # markieren → beim nächsten Lauf überspringen
    if art:
        imgs = art.get("images", [])
        if imgs and not data.get("image"):
            data["image"] = imgs[0]["url"]     # größtes Bild
        sp = art.get("external_urls", {}).get("spotify")
        if sp and not data.get("spotify"):
            data["spotify"] = sp
        genres = art.get("genres", [])
        if genres:
            data.setdefault("spotifyGenres", genres)
            if not data.get("genre"):
                data["genre"] = genres[0].title()   # Vorschlag – manuell überschreibbar

    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(("~ aktualisiert " if existing else "+ neu          ") + f"{name} → {path}")
    updated += 1 if existing else 0
    created += 0 if existing else 1

print(f"\nFertig: {created} neu, {updated} aktualisiert, {skipped} übersprungen.")
print("Tipp: Genre-Vorschläge in artists/*.json ggf. auf deine Kategorien anpassen.")

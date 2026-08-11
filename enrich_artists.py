#!/usr/bin/env python3
"""
Reichert artists/ mit Spotify-Daten an: Bild-URL, Spotify-Link, Genre-Vorschlag.
Sammelt Künstlernamen aus festivals/*.json, sucht sie auf Spotify und schreibt/
aktualisiert artists/<slug>.json. Manuelle Felder bleiben erhalten; schon geprüfte
Namen werden übersprungen (Re-Runs sind schnell).

Env-Variablen setzen (nicht im Code speichern):
    export SPOTIFY_CLIENT_ID=...
    export SPOTIFY_CLIENT_SECRET=...
    python3 -u enrich_artists.py
"""

import os, re, glob, json, time, base64, sys
import urllib.parse, urllib.request, urllib.error

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit("Bitte SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET setzen.")


def log(*a):
    print(*a, flush=True)          # sofort ausgeben, nicht puffern


def get_token():
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=data,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def search_artist(name, token, tries=3):
    """Gibt (artist_dict_or_None, fehler_or_None) zurück – hängt NIE endlos."""
    q = urllib.parse.urlencode({"q": name, "type": "artist", "limit": 1})
    req = urllib.request.Request(
        f"https://api.spotify.com/v1/search?{q}",
        headers={"Authorization": f"Bearer {token}"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                items = json.load(r).get("artists", {}).get("items", [])
                return (items[0] if items else None), None
        except urllib.error.HTTPError as e:
            if e.code == 429:                       # Rate-Limit → begrenzt warten
                raw = e.headers.get("Retry-After", "?")   # echte Sperrdauer laut Spotify
                wait = min(int(raw) if str(raw).isdigit() else 5, 30)
                log(f"   429 Rate-Limit (Spotify will {raw}s), warte {wait}s "
                    f"(Versuch {attempt+1}/{tries})")
                time.sleep(wait + 1)
                continue
            return None, f"HTTP {e.code}"           # 401/403/… → nicht crashen
        except Exception as e:
            return None, str(e)
    return None, "429 (aufgegeben)"


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "artist"


# --- Namen sammeln ----------------------------------------------------------
# Nur AKTUELLE/kommende Festivals anreichern. Vergangene blendet die App eh aus,
# also sparen wir uns die Spotify-Anfragen dafür. Ein Festival gilt als vorbei,
# wenn sein endDate mehr als 3 Tage zurückliegt (kleiner Puffer).
from datetime import date, datetime, timedelta
CUTOFF = date.today() - timedelta(days=3)

def ended(fest):
    end = fest.get("endDate") or fest.get("startDate")
    try:
        return datetime.strptime(end[:10], "%Y-%m-%d").date() < CUTOFF
    except Exception:
        return False   # kein/kaputtes Datum -> lieber anreichern

names = set()
skipped_fests = 0
for p in sorted(glob.glob("festivals/*.json")):
    fest = json.load(open(p, encoding="utf-8"))
    if ended(fest):
        skipped_fests += 1
        continue
    for it in fest.get("schedule", []):
        n = it.get("artist") or it.get("title")
        if n:
            names.add(n.strip())
names = sorted(names)
log(f"{len(names)} eindeutige Namen aus aktuellen Festivals "
    f"({skipped_fests} vergangene Festivals übersprungen).")

# --- Login + Selbsttest -----------------------------------------------------
try:
    token = get_token()
    log("Spotify-Login OK.")
except Exception as e:
    sys.exit(f"Spotify-Login fehlgeschlagen: {e}")

test, err = search_artist("Coldplay", token)
if err:
    sys.exit(f"ABBRUCH: Selbsttest fehlgeschlagen ({err}). Spotify drosselt/blockt "
             f"gerade - in ein paar Stunden erneut versuchen.")
if not (test and test.get("images")):
    sys.exit("ABBRUCH: Selbsttest lieferte kein Bild - Zugriff eingeschraenkt.")
log("Selbsttest OK - Spotify liefert Kuenstlerbilder.")

# --- Anreichern -------------------------------------------------------------
os.makedirs("artists", exist_ok=True)
created = updated = skipped = with_image = 0

def load_existing(path):
    """Liest artists/<slug>.json. Leere oder kaputte Dateien (z.B. Platzhalter
    zum Ordner-Anlegen) werden als 'noch nicht angereichert' behandelt, nicht
    als Absturz."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read().strip()
        return json.loads(txt) if txt else {}
    except (json.JSONDecodeError, ValueError):
        log(f"   (leere/kaputte Datei ignoriert: {path})")
        return {}

for i, name in enumerate(names, 1):
    path = f"artists/{slug(name)}.json"
    existing = load_existing(path)

    if existing.get("image") and existing.get("spotify"):
        skipped += 1
        continue
    if existing.get("spotifyChecked") and not existing.get("image"):
        skipped += 1
        continue

    art, err = search_artist(name, token)
    time.sleep(0.2)

    data = dict(existing)
    data.setdefault("name", name)
    if err is None:                    # nur bei gueltiger Antwort als geprueft markieren
        data["spotifyChecked"] = True  # (bei 429/Fehler NICHT -> naechster Lauf versucht erneut)
    if art:
        imgs = art.get("images", [])
        if imgs and not data.get("image"):
            data["image"] = imgs[0]["url"]
            with_image += 1
        sp = art.get("external_urls", {}).get("spotify")
        if sp and not data.get("spotify"):
            data["spotify"] = sp
        genres = art.get("genres", [])
        if genres:
            data.setdefault("spotifyGenres", genres)
            if not data.get("genre"):
                data["genre"] = genres[0].title()

    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    mark = "img" if data.get("image") else " - "
    log(f"[{i}/{len(names)}] {mark}  {name}")
    if existing:
        updated += 1
    else:
        created += 1

log(f"\nFertig: {created} neu, {updated} aktualisiert, {skipped} uebersprungen, {with_image} mit Bild.")

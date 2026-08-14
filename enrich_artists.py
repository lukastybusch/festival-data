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

import os, re, glob, json, time, base64, sys, unicodedata
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


def norm_name(s):
    """Vergleichbare Form eines Künstlernamens: klein, ohne Akzente, ohne Zusätze
    wie „(DJ Set)"/„(party set)", nur Buchstaben/Ziffern. Damit prüfen wir, ob ein
    Spotify-Treffer WIRKLICH derselbe Act ist – „Marsh" != „Marshmello"."""
    s = (s or "").lower().strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)          # abschließende Klammer weg
    s = "".join(c for c in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(c))     # Akzente weg
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()        # Rest normalisieren
    return s


def search_artist(name, token, tries=3):
    """Gibt (artist_dict_or_None, fehler_or_None) zurück – hängt NIE endlos.
    Holt mehrere Kandidaten und akzeptiert NUR einen, dessen Name exakt passt
    (normalisiert). Kein exakter Treffer -> (None, None): lieber Platzhalter als
    falsches Bild."""
    q = urllib.parse.urlencode({"q": name, "type": "artist", "limit": 8})
    req = urllib.request.Request(
        f"https://api.spotify.com/v1/search?{q}",
        headers={"Authorization": f"Bearer {token}"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                items = json.load(r).get("artists", {}).get("items", [])
                target = norm_name(name)
                # exakter Namens-Treffer; bei mehreren der mit den meisten Followern
                exact = [a for a in items if norm_name(a.get("name", "")) == target]
                if exact:
                    exact.sort(key=lambda a: a.get("followers", {}).get("total", 0),
                               reverse=True)
                    return exact[0], None
                return None, None                    # kein sicherer Treffer
        except urllib.error.HTTPError as e:
            if e.code == 429:                       # Rate-Limit
                raw = e.headers.get("Retry-After", "")     # Sperrdauer laut Spotify
                secs = int(raw) if str(raw).isdigit() else None
                if secs is not None and secs > 120:  # LANGE Sperre -> nicht warten
                    return None, f"RATELIMIT:{secs}" # oben sauber abbrechen & sichern
                wait = min(secs or 5, 30)            # kurze Drosselung -> begrenzt warten
                log(f"   429 Rate-Limit, warte {wait}s (Versuch {attempt+1}/{tries})")
                time.sleep(wait + 1)
                continue
            return None, f"HTTP {e.code}"           # 401/403/… → nicht crashen
        except Exception as e:
            return None, str(e)
    return None, "RATELIMIT:0"                       # 3x kurz gedrosselt -> auch stoppen


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

    # Manuell gepflegte Einträge nie anfassen.
    if existing.get("manual"):
        skipped += 1
        continue
    # Schon mit der EXAKTEN Prüfung verifiziert -> überspringen (schnelle Re-Runs).
    # Alte Einträge ohne "verified" werden erneut geprüft, damit falsche Treffer
    # (z.B. Marsh -> Marshmello) einmalig korrigiert werden.
    if existing.get("verified"):
        skipped += 1
        continue

    art, err = search_artist(name, token)

    # Bei (langer) Rate-Limit-Sperre: NICHT weiterrennen, sondern sauber stoppen.
    # So bleibt das Script im Zeitlimit, endet mit exit 0, und der Workflow committet
    # den bisherigen Fortschritt. Der nächste Lauf macht genau hier weiter.
    if err and err.startswith("RATELIMIT"):
        secs = err.split(":")[1]
        dauer = f"~{int(secs)//3600}h" if secs.isdigit() and int(secs) > 3600 else f"{secs}s"
        log(f"\n== Spotify-Rate-Limit erreicht (Sperre {dauer}). Stoppe hier und "
            f"sichere den Fortschritt. Naechster Lauf macht ab '{name}' weiter. ==")
        break

    time.sleep(0.2)

    data = dict(existing)
    data.setdefault("name", name)

    if err is None:
        # Gültige Antwort ausgewertet -> als exakt geprüft markieren.
        data["spotifyChecked"] = True
        data["verified"] = True
        if art:
            # Exakter Treffer: Bild/Spotify/Genre setzen (überschreibt evtl. alte
            # FALSCHE Werte, denn diese Prüfung ist zuverlässiger als die erste).
            imgs = art.get("images", [])
            if imgs:
                data["image"] = imgs[0]["url"]
                with_image += 1
            elif not existing.get("manual"):
                data.pop("image", None)
            sp = art.get("external_urls", {}).get("spotify")
            if sp:
                data["spotify"] = sp
            genres = art.get("genres", [])
            if genres:
                data["spotifyGenres"] = genres
                data.setdefault("genre", genres[0].title())
            data.pop("spotifyMatch", None)
        else:
            # Kein sicherer Namens-Treffer: evtl. früher gesetztes FALSCHES Bild
            # entfernen (außer manuell) und als "kein Treffer" markieren.
            if not existing.get("manual"):
                data.pop("image", None)
                data.pop("spotify", None)
            data["spotifyMatch"] = "none"
    # bei 429/Netzfehler: nichts markieren -> nächster Lauf versucht erneut

    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    mark = "img" if data.get("image") else ("—" if data.get("spotifyMatch") == "none" else " ? ")
    log(f"[{i}/{len(names)}] {mark}  {name}")
    if existing:
        updated += 1
    else:
        created += 1

log(f"\nFertig: {created} neu, {updated} aktualisiert, {skipped} uebersprungen, {with_image} mit Bild.")

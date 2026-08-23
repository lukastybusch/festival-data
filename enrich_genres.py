#!/usr/bin/env python3
"""
Reichert artists/*.json um ein Genre an – aus WIKIDATA (CC0, frei nutzbar,
auch kommerziell). Kein Spotify, keine Credentials.

Für jeden Artist ohne Genre wird in Wikidata ein Musik-Act mit passendem Namen
gesucht (gefiltert über die Beschreibung, damit „Marsh" nicht „Marshmello" wird)
und dessen Genre (Property P136) übernommen. Manuell gesetzte Genres bleiben.
Schon geprüfte Einträge (genreChecked) werden übersprungen → schnelle Re-Runs.

Aufruf (im Repo-Wurzelverzeichnis):  python3 enrich_genres.py
"""

import os, re, glob, json, time
import urllib.parse, urllib.request, urllib.error

API = "https://www.wikidata.org/w/api.php"
# Wikidata verlangt einen aussagekräftigen User-Agent mit Kontakt.
UA = "FestdaysGenreBot/1.0 (https://lukastybusch.github.io/festival-data; support@forgehub.eu)"

# Beschreibungen, die auf einen Musik-Act hindeuten (en + etwas de).
MUSIC_RE = re.compile(
    r"\b(music|musician|singer|songwriter|rapper|band|group|duo|trio|dj|"
    r"disc jockey|producer|composer|guitarist|drummer|bassist|vocalist|"
    r"orchestra| sänger|musiker|gruppe|kapelle|rapperin|sängerin)\b", re.I)


def log(*a):
    print(*a, flush=True)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def api_get(params, tries=3):
    params = dict(params)
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:                 # zu schnell -> kurz warten
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(2)
            continue
    return None


def find_genre(name):
    """Gibt das erste Genre eines gleichnamigen Musik-Acts zurück – oder None."""
    data = api_get({"action": "wbsearchentities", "search": name,
                    "language": "en", "uselang": "en", "type": "item", "limit": 6})
    if not data:
        return None
    target = norm(name)

    def score(c):
        exact = norm(c.get("label", "")) == target
        musical = bool(MUSIC_RE.search(c.get("description", "") or ""))
        return (exact and musical, exact, musical)

    for c in sorted(data.get("search", []), key=score, reverse=True):
        if not MUSIC_RE.search(c.get("description", "") or ""):
            continue                          # kein Musik-Act -> überspringen
        qid = c.get("id")
        if not qid:
            continue
        ent = api_get({"action": "wbgetentities", "ids": qid, "props": "claims"})
        if not ent:
            continue
        claims = ent.get("entities", {}).get(qid, {}).get("claims", {})
        gids = []
        for cl in claims.get("P136", []):     # P136 = genre
            try:
                gids.append(cl["mainsnak"]["datavalue"]["value"]["id"])
            except (KeyError, TypeError):
                pass
        if not gids:
            return None                       # Act gefunden, aber ohne Genre
        lab = api_get({"action": "wbgetentities", "ids": gids[0],
                       "props": "labels", "languages": "en"})
        if not lab:
            return None
        label = (lab.get("entities", {}).get(gids[0], {})
                 .get("labels", {}).get("en", {}).get("value"))
        return label.strip().title() if label else None
    return None


# --- Durchlauf ---------------------------------------------------------------
files = sorted(glob.glob("artists/*.json"))
checked = found = 0
for i, path in enumerate(files, 1):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read().strip()
        data = json.loads(txt) if txt else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        continue
    name = (data.get("name") or "").strip()
    if not name or data.get("genre") or data.get("genreChecked"):
        continue                              # kein Name / schon vorhanden / geprüft

    genre = None
    try:
        genre = find_genre(name)
    except Exception as e:
        log(f"   Fehler bei {name}: {e}")

    data["genreChecked"] = True               # nicht erneut abfragen
    if genre:
        data["genre"] = genre
        found += 1
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    checked += 1
    log(f"[{i}/{len(files)}] {name} -> {genre or '—'}")
    time.sleep(0.3)                           # freundlich zu Wikidata

log(f"\nFertig: {checked} geprüft, {found} mit Genre.")

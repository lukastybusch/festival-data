#!/usr/bin/env python3
"""
Hält artists/ synchron mit den Festival-Line-ups – OHNE Spotify.

Zwei Aufgaben in einem Lauf:
  1) Entfernt aus ALLEN artists/*.json die Spotify-Reste
     (image, spotify, spotifyGenres, spotifyChecked, verified).
     Manuell gepflegte Felder wie name/genre bleiben erhalten.
  2) Sammelt alle Künstlernamen aus festivals/*.json und legt für jeden
     fehlenden einen Eintrag artists/<slug>.json an ({"name": ...}),
     damit die "Datenbank" vollständig mitwächst.

Kein Netzwerk, keine API, keine Credentials nötig.
Aufruf (im Repo-Wurzelverzeichnis):  python3 sync_artists.py
"""

import os, re, glob, json

# Felder, die aus Spotify stammen und raus sollen.
SPOTIFY_FIELDS = {"image", "spotify", "spotifyGenres", "spotifyChecked", "verified"}


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "artist"


def load(path):
    """Liest JSON; leere/kaputte Dateien werden zu {} statt Absturz."""
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read().strip()
        return json.loads(txt) if txt else {}
    except (json.JSONDecodeError, ValueError, OSError):
        return {}


def save(path, data):
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


os.makedirs("artists", exist_ok=True)

# --- 1) Bestehende Dateien von Spotify-Resten befreien -----------------------
cleaned = 0
for p in glob.glob("artists/*.json"):
    data = load(p)
    if not isinstance(data, dict):
        continue
    to_remove = SPOTIFY_FIELDS & set(data.keys())
    if to_remove:
        for k in to_remove:
            data.pop(k, None)
        save(p, data)
        cleaned += 1

# --- 2) Namen aus den Festivals sammeln -------------------------------------
names = set()
for p in sorted(glob.glob("festivals/*.json")):
    fest = load(p)
    if not isinstance(fest, dict):
        continue
    for it in fest.get("schedule", []):
        n = (it.get("artist") or it.get("title") or "").strip()
        if n:
            names.add(n)

# --- 3) Fehlende Artist-Einträge anlegen, Namen sicherstellen ---------------
created = 0
for name in sorted(names):
    path = f"artists/{slug(name)}.json"
    if os.path.exists(path):
        data = load(path)
        if not isinstance(data, dict):
            data = {}
        if not data.get("name"):          # Name nachtragen, falls leer
            data["name"] = name
            save(path, data)
        continue
    save(path, {"name": name})
    created += 1

print(f"{cleaned} Dateien bereinigt, {created} neue Artists angelegt, "
      f"{len(names)} Namen aus Festivals gesamt.")

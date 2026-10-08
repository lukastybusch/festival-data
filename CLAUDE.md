# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A data repo (served via GitHub Pages, Jekyll Cayman theme) for the "Festdays" festival countdown app. Hand-maintained source JSON files are joined by a Python script into a single self-contained `festivals.json` that the app downloads. Docs and comments are in German; `DATENMODELL.md` is the authoritative description of each file's schema.

Die Daten speisen die App **Festday** (iOS SwiftUI + WidgetKit; Android Kotlin/Compose). Die App lädt die fertige `festivals.json`, die hier aus Einzel-Dateien gebaut wird.

## ⚠️ EISERNE REGEL: Keine erfundenen Daten (verbindlich)

Das ist eine Countdown- und Line-up-App. Falsche Daten = Vertrauensverlust. Niemals raten.

- **Datum (Tag):** Nur eintragen, wenn offiziell bekannt. Kein Schätzen.
- **Uhrzeit (`date` mit Zeit):** NUR wenn der Veranstalter die Running Order offiziell veröffentlicht hat.
- **Bühne (`stage`):** NUR wenn offiziell genannt. Sonst Feld weglassen.
- **Act bestätigt, aber Tag/Zeit noch offen?** → gehört in `confirmed` (Namen-Teaser), NICHT in `schedule`.
- Quelle im Zweifel immer die **offizielle Festival-Website oder der offizielle Ticket-/Social-Kanal**. Sekundärquellen (Blogs, Wikipedia) nur als Hinweis, nie als Beleg für Uhrzeiten/Bühnen.
- Wenn eine Info nicht sicher belegbar ist: **weglassen und im PR vermerken**, nicht füllen.

## ⚠️ Rechtliche Tabus (verbindlich)

- **Kein Spotify**: keine Spotify-Bilder, -Links oder -Daten in die JSON schreiben (Terms/Urheberrecht). Genre darf rein (ein Wort). Artist-Bild bleibt leer → App zeigt Platzhalter, baut Spotify-Such-Link selbst aus dem Namen.
- Keine Festival-Logos, keine geschützten Bilder, keine fremde Trade Dress.

## Commands

No dependencies beyond Python 3 stdlib; there are no tests or linters. Run from the repo root:

```
python3 sync_artists.py     # strip Spotify fields from artists/, create stub artists/<slug>.json for every lineup name
python3 enrich_genres.py    # fill missing artist genres from Wikidata (network, slow, rate-limited; skips genreChecked entries)
python3 build_festivals.py  # join everything -> festivals.json
```

## Architecture

Pipeline: `series/` + `artists/` + `affiliate/providers.json` + `genres.json` + `festivals/` → `build_festivals.py` → `festivals.json`.

- **festivals/** – one file per edition (`<series>-<year>.json`): dates, lineup (`schedule`), optional `confirmed` (names-only teaser list passed through when no timetable exists), ticket info. Links to a brand via `seriesId` and to artists by *name* (matched case-insensitively via `norm()`, not by slug).
- **series/** – the brand (colors, website, info); editions inherit via `pick()` (edition value wins, then series, then default). Only some festivals have a series file; others are self-contained.
- **artists/** – shared artist DB, one file per slug. Only `name` and `genre` are meaningful; **Spotify image/links are deliberately not stored** (terms/copyright) and `sync_artists.py` actively deletes those fields. The app builds Spotify links at runtime from the name.
- **affiliate/providers.json** – ticket providers; `ticket_url()` builds links via `wrap` (tracking URL with `{url}`), `base`+`eventId`+`suffix`, or falls back to a direct `ticket.url`.
- **genres.json** – genre → color vocabulary, currently an empty placeholder (1 byte); `genreColor` is only emitted when a genre matches.

Key behaviors to know:
- Edition files may use either the simple schema (`startDate`, `location` string, `ticket`) or the richer one (`start_date`, `location` object, `genres[]`, `tickets`); `normalize_edition()` reconciles them. Some files (e.g. `festivals/primavera-sound-2027`) have no `.json` extension and are therefore ignored by the glob; editions missing `id` or a start date are skipped with a log line.
- `load()` in both scripts tolerates empty/broken JSON (returns None/{}), so a bad file is skipped rather than aborting the build.
- Lineup `date` is either `YYYY-MM-DD` or a full timestamp; never guess times. `stage` only if officially known.

## Automation (GitHub Actions)

- `merge-festivals.yml` – on push to `main` touching data/scripts: runs `sync_artists.py` + `build_festivals.py`, commits `artists/` and `festivals.json` as a bot (`Auto: ...` commits).
- `enrich-genres.yml` – weekly (Mon 04:00 UTC) + manual: sync → Wikidata enrich → build → commit.

Because bots commit `artists/` and `festivals.json`, `git pull` before pushing; don't hand-edit `festivals.json` (it's regenerated). Static pages `impressum.html`, `privacy.html`, `support.html` are legal/support pages for the app.

## Schema: festivals/<edition>.json (bevorzugt)

Zwei Schreibweisen werden akzeptiert (siehe `normalize_edition` in build_festivals.py). Bevorzugt das einfache Schema:

```json
{
  "id": "rock-am-ring-2027",
  "seriesId": "rock-am-ring",
  "startDate": "2027-06-04",
  "endDate": "2027-06-06",
  "confirmed": ["Blink-182"],
  "schedule": [
    { "artist": "Beispiel Act", "date": "2027-06-04T20:00:00", "stage": "Mainstage" }
  ]
}
```

- `id`: eindeutig, Kleinbuchstaben, mit Jahr. Test-Festival-IDs beginnen mit `test-` (nur im Debug-Build sichtbar).
- `date`: nur Tag `"2027-06-04"` ODER mit Zeit `"2027-06-04T20:00:00"` – Zeit nur wenn offiziell.
- `confirmed`: reine Namensliste für bestätigte Acts ohne Tag/Zeit (Teaser).
- `name/location/color/accent/website/info/ticket` werden aus der `series` gezogen, können pro Edition überschrieben werden.
- `ticket`: `{ "url": "https://offizieller-ticketlink" }` → Direktlink. `affiliate/providers.json` ist aktuell nicht genutzt (Direktlinks).

## Workflow: Festival anlegen/aktualisieren

1. Prüfen, ob `series/<id>.json` existiert; wenn nicht, anlegen.
2. `festivals/<edition>.json` nach Schema anlegen/ergänzen – **nur belegbare Daten** (siehe eiserne Regel).
3. `python3 build_festivals.py` → `festivals.json` neu bauen, Output prüfen (Anzahl Festivals, keine „übersprungen"-Warnungen).
4. Als **Branch + Pull Request** committen, NICHT direkt auf main pushen.
5. Im PR knapp vermerken: Quelle je Line-up + was bewusst weggelassen wurde (fehlende Zeiten/Bühnen).
6. Lukas reviewt und merged. GitHub Actions baut dann automatisch.

> GITHUB_TOKEN-Commits der Actions lösen keine weiteren Workflows aus (bewusst).

`festivals.json` ist **generiert** – niemals von Hand editieren. Immer die Quelldateien ändern und `python3 build_festivals.py` laufen lassen.

## Lokalisierung

- Sprachen: Deutsch + Englisch. Keine In-App-Sprachauswahl (iOS/Android regeln das über System-Einstellungen).
- Quelle der Wahrheit: eine Master-Liste DE/EN. iOS = `.xcstrings`, Android = `strings.xml` – gleicher Text, anderes Format.
- Catalog-Keys = **deutscher Quelltext**. Nur String-Literale im Code lokalisieren; Enum-rawValues und Variablen-Strings NICHT.

## Commits / PRs

- Kleine, thematische Commits. Aussagekräftige Messages (DE ok).
- Niemals direkt auf `main` für Datenänderungen – immer PR, damit die Daten-Regel geprüft werden kann.

# Festdays – Datenmodell & Build

So sind die Daten organisiert. Du pflegst die **Quell-Dateien** (Einzel-Datenbanken),
die GitHub-Action baut daraus automatisch die fertige `festivals.json`, die die App lädt.

```
series/    (Marke: Name, Ort, Farben, Website, Ticket-Anbieter)   ┐
artists/   (Künstler: Genre, Bild, Spotify)                        │
affiliate/ (deine Affiliate-IDs + Basis-URLs)                      ├─► build_festivals.py ─► festivals.json ─► App
genres.json(Genre-Vokabular + Farben)                              │
festivals/<edition>  (Datum + Line-up, referenziert Serie/Künstler)┘
```

**Prinzip:** Was sich unabhängig ändert oder mehrfach genutzt wird → eigene Datei.
Alles ist **optional & rückwärtskompatibel** – bestehende self-contained Festival-Dateien laufen weiter.

Ordner im Repo: `.github/workflows/merge-festivals.yml`, `build_festivals.py` (Wurzel),
sowie die Ordner `series/`, `artists/`, `affiliate/`, `festivals/` und `genres.json`.

---

## series/&lt;id&gt;.json — Festival-Marke (stabil)

```json
{
  "id": "pangea",
  "name": "Pangea Festival",
  "location": "Pütnitz, DE",
  "genre": "Festival",
  "website": "https://pangea-festival.com",
  "color": "#2E1065",
  "accent": "#C084FC",
  "info": {
    "openingHours": "Do 12:00 – So 18:00",
    "emergency": "+49 151 …",
    "faq": "https://pangea-festival.com/faq"
  }
}
```
Farben, Website, Infos einmal pro Marke – jede Jahres-Edition erbt sie.

## festivals/&lt;edition&gt;.json — Jahres-Edition (ändert sich jährlich)

```json
{
  "id": "pangea-2026",
  "seriesId": "pangea",
  "startDate": "2026-08-06",
  "endDate": "2026-08-09",
  "ticket": { "provider": "eventim", "eventId": "12345" },
  "schedule": [
    { "artist": "Giant Rooks", "date": "2026-08-07T22:40:00", "stage": "New Havn" }
  ]
}
```
- Verweist per `seriesId` auf die Marke und per **Künstlername** auf `artists/`.
- `date`: nur Tag `"2026-08-07"` oder mit echter Uhrzeit `"2026-08-07T22:40:00"` (nie schätzen).
- `stage` nur, wenn offiziell bekannt.
- Optionaler Override: `color`/`accent`/`name` in der Edition überschreiben die Serie.

## artists/&lt;slug&gt;.json — Künstler (stabil, über Festivals geteilt)

```json
{
  "name": "Giant Rooks",
  "genre": "Indie/Pop",
  "image": "https://i.scdn.co/image/…",
  "spotify": "https://open.spotify.com/artist/…"
}
```
`image` + `spotify` füllt später das Spotify-Skript automatisch. Fehlt ein Künstler → Platzhalter in der App.

## affiliate/providers.json — Ticket-Anbieter (stabil)

```json
{
  "providers": {
    "eventim": { "base": "https://www.eventim.de/event/", "suffix": "?affiliate=DEINE_ID" }
  }
}
```
Der Build baut den Link: `base` + `eventId` (aus der Edition) + `suffix`.
Ändert sich deine Affiliate-ID → nur hier anpassen. Alternativ direkt `"ticket": { "url": "…" }` in der Edition.

## genres.json — Genre-Vokabular (Farben für die Filter-Chips)

```json
{
  "genres": [
    { "name": "Indie/Pop", "color": "#38BDF8" },
    { "name": "Rap/Hip-Hop", "color": "#F472B6" }
  ]
}
```

---

## Ergebnis (was die App bekommt)

`festivals.json` ist self-contained – jedes Festival hat `color`/`accent`/`website`/`ticketURL`,
jeder Line-up-Eintrag `title`/`date`/`stage` plus (wenn vorhanden) `genre`/`image`/`spotify`/`genreColor`.
Die App decodiert nur, was sie kennt; unbekannte Felder werden ignoriert.

## Einrichtung im Repo

1. `build_festivals.py` ins Wurzelverzeichnis legen.
2. `merge-festivals.yml` nach `.github/workflows/` (ersetzt die alte jq-Version).
3. Ordner `series/`, `artists/`, `affiliate/` und `genres.json` anlegen und befüllen.
4. Push → die Action baut `festivals.json` automatisch.

Lokal testen: `python3 build_festivals.py` im Repo-Ordner.

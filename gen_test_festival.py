#!/usr/bin/env python3
"""Erzeugt die DEBUG-Test-Festivals mit Terminen relativ zu HEUTE.

Aufruf:  python3 gen_test_festival.py && python3 build_festivals.py

Die IDs beginnen mit 'test-' -> sichtbar nur in Debug-Builds, nie in der
veröffentlichten App. Alle Daten sind frei erfunden und dienen nur zum Testen
(echte Künstlernamen, damit Spotify-Suche und Genre real testbar sind).
Die Dateien nach jedem Testtag neu erzeugen, damit "Jetzt live" greift.

Abgedeckte Fälle:
  test-festival         läuft gerade: Live-Set, Nachtsets nach Mitternacht (Festival-Tag
                        endet 07:00), Überschneidung auf zwei Bühnen, gleiche Bühne
                        hintereinander, Eintrag nur mit Tag, Eintrag ohne Bühne.
  test-festival-teaser  in 30 Tagen: nur 'confirmed' (Namen-Teaser), kein schedule.
"""
import json
from datetime import datetime, timedelta

now = datetime.now().replace(second=0, microsecond=0)
today = now.replace(hour=0, minute=0)

def ts(day_offset, hour, minute=0):
    d = today + timedelta(days=day_offset, hours=hour, minutes=minute)
    return d.strftime("%Y-%m-%dT%H:%M:00")

def day(offset):
    return (today + timedelta(days=offset)).strftime("%Y-%m-%d")

def rel(minutes):
    t = (now + timedelta(minutes=minutes))
    t = t.replace(minute=(t.minute // 5) * 5)
    return t.strftime("%Y-%m-%dT%H:%M:00")

def s(artist, date, stage=None, genre=None):
    e = {"artist": artist, "date": date}
    if stage: e["stage"] = stage
    if genre: e["genre"] = genre
    return e

common = {
    "location": "Teststadt, XX", "genre": "Test / Mixed",
    "color": "#1E293B", "accent": "#F43F5E",
    "website": "https://example.com",
    "ticket": {"url": "https://example.com/tickets"},
    "info": {"openingHours": "Alle Tage 12:00–06:00", "emergency": "+49 000 0000000",
             "faq": "https://example.com/faq", "map": "https://example.com/map",
             "instagram": "https://instagram.com"},
}

live = {
    "_comment": "GENERIERT von gen_test_festival.py (nicht von Hand editieren). Nur DEBUG.",
    "id": "test-festival", "name": "Test-Festival (Debug)",
    "startDate": day(-1), "endDate": day(2), **common,
    "schedule": [
        # Gestern (vorbei) inkl. Nachtset nach Mitternacht -> gehört zum Festival-Tag "gestern"
        s("Wolf Alice", ts(-1, 18), "Main Stage", "Indie Rock"),
        s("Bonobo", ts(-1, 20), "Main Stage", "Electronic"),
        s("Twenty One Pilots", ts(-1, 22), "Main Stage", "Alternative"),
        s("Four Tet", ts(0, 1, 30), "Club", "Electronic"),
        # Heute: Live-Set + Überschneidung (Royal Blood / Jungle auf verschiedenen Bühnen)
        s("Zara Larsson", ts(0, 14), "Main Stage", "Pop"),
        s("Royal Blood", rel(-25), "Main Stage", "Rock"),
        s("Jungle", rel(-10), "Second Stage", "Funk"),
        s("Glass Animals", rel(120), "Main Stage", "Indie"),
        s("Peggy Gou", ts(0, 22), "Main Stage", "House"),
        s("Skrillex", ts(0, 23), "Main Stage", "Dubstep"),
        s("Fred again..", ts(1, 1), "Main Stage", "Electronic"),
        s("Ben Böhmer", ts(1, 3), "Second Stage", "Melodic House"),
        # Morgen: Überschneidung Arctic Monkeys / Fontaines D.C.
        s("Florence + the Machine", ts(1, 20), "Main Stage", "Art Pop"),
        s("Arctic Monkeys", ts(1, 22), "Main Stage", "Indie Rock"),
        s("Fontaines D.C.", ts(1, 22, 30), "Second Stage", "Post-Punk"),
        # Übermorgen: nur Tag bekannt (keine Uhrzeit), eine ohne Bühne
        s("Tame Impala", day(2), "Main Stage", "Psychedelic Rock"),
        s("Jungle", day(2), None, "Funk"),
    ],
}

teaser = {
    "_comment": "GENERIERT von gen_test_festival.py (nicht von Hand editieren). Nur DEBUG.",
    "id": "test-festival-teaser", "name": "Test-Teaser (Debug)",
    "startDate": day(30), "endDate": day(32), **common,
    "confirmed": ["Wolf Alice", "Bonobo", "Royal Blood", "Glass Animals", "Peggy Gou", "Tame Impala"],
}

for name, obj in (("test-festival", live), ("test-festival-teaser", teaser)):
    with open(f"festivals/{name}.json", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("geschrieben:", name, obj["startDate"], "–", obj["endDate"])

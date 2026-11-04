# Nullstart allgemein machen - Ziel: Historisches Kaufhaus Freiburg von 0 (Nutzer 2026-11-03)

Massstab: Ein neues Objekt braucht nur `objekt.json` (Ort, Fotoquellen, Seiten) + Daten; kein neuer Code, keine Handzahlen.
Stand Martinstor-Nullstart: laeuft ohne Eingriff (Lauf 56, 66/75), aber an vielen Stellen mit Martinstor-Wissen.

## A. Was schon allgemein ist (weiterverwenden)
- Bauteile `tools/bauteile.py`: baender_rundkoerper (Erker/Tuermchen aus Wolkenbaendern), oeffnungsreihe_aus_profil / segmentbogen_reihe (Arkaden aus Wolke + Foto-Zaehlung),
  mauerwerk_aus_protokollen (Quader aus Foto-Protokollen, Register CI), tuermchen_achse_je_quadrant (Register CH), seite_achsen.
- Pruefstand + Quellenmatrix, CB-Lint, Regression, foto_diff/fehlteile_finden, hardcode_finden.py, job_start.sh, testdruck_dachziegel/mauerwerk.
- SfM-Kette (sfm_netz/ausrichten/dicht/entzerren), wolke_profile/wolke_baender (Koerper aus objekt.json['koerper']).

## B. Martinstor-Wissen in der Pipeline (Luecken, nach Schwere)
| # | Stelle | Was ist speziell | Allgemein |
|---|---|---|---|
| 1 | Generator `martinstor_v4_gen.py` | ganzes Bauwerk als Code (248 feste Zahlen, hardcode_finden.py) | **Baukasten-Generator**: liest `objekt.json['bauteile']` (Rumpf aus LoD2, Dach aus DOM1/LoD2/Profil, Fassadenoeffnungen aus fassade.json, Arkaden, Erker, Quader) und ruft nur bauteile.py |
| 2 | `nullstart.py` Z. 89/129/166/171/192 | Seiten fest "nord"/"sued" | Seiten aus `objekt.json['sfm']` (Schluessel = Seiten), Hauptseite dort |
| 3 | `nullstart.py` Z. 138-139 | Fotos 060/061, `--hoehe 44 8` | Registrier-Fotos + Hoehenfenster aus objekt.json (`sfm.registrieren`), Hoehe aus LoD2-Traufe/First |
| 4 | `nullstart.py` Z. 77/81 | Generatorpfad martinstor_v4_gen.py | `objekt.json['generator']` (ist schon da) durchreichen |
| 5 | `nullstart.py` Z. 199 Vergleich | Dateien silhouette_061, baender_tuermchen/zentral | Vergleichsliste aus `objekt.json['regression']['dateien']` |
| 6 | Kette in objekt.json | `--zentral-z 40.5 56`, Foto 061, Gold z 20-32 | Hoehen aus LoD2/DOM1 ableiten; Silhouettenfoto = bestes Seitenfoto aus fotoliste (automatisch) |
| 7 | K/Z/M-Protokolle | werden aus der Referenz KOPIERT; fuer ein neues Objekt gibt es keine | (a) Kamera: Anker-Picks automatisch (LoD2-Ecken in Foto-Kanten), (b) Zaehlungen/Masse: halbautomatisch mit Vorschlag + Bild zur Abnahme (Regel 9 bleibt: Foto ist Quelle) |
| 8 | masse.json "Stufe C" (14 Handwerte) | DACHHOEHE, GX/GY, GZ0/GZ1, OR ... | aus Profilen ableiten (masse_aus_profilen.py), Rest als ANNAHME |

## C. Reihenfolge (Vorschlag)
1. nullstart.py: Seiten, Registrierfotos, Generator, Vergleichsliste aus objekt.json (B2-B5) - Martinstor-Ergebnis muss identisch bleiben (Regression + Nullstart-Vergleich).
2. Kaufhaus anlegen (`objekt_anlegen.py kaufhaus`), Daten holen (LoD2/DOM1/Fotos/Mapillary), Nullstart bis zur Wolke laufen lassen -> zeigt, was als Naechstes bricht.
3. Baukasten-Generator (B1) zuerst fuer das Kaufhaus (einfacher Rumpf + steiles Dach + Arkaden + Eckerker), dann Martinstor darauf umziehen.
4. Anker-Picks/Zaehlungen automatisieren (B7).

## D. Stand 2026-11-03 abends - Kaufhaus Kaltstart (was brach, was jetzt allgemein ist)
| Bruch | Ursache | Allgemeine Loesung |
|---|---|---|
| Rahmen +x zeigte nach Westen, Notiz "Sueden" | Vorzeichenregel nur fuer N-S-Langachsen; zweite Spiegelung konnte linkshaendig machen | `objekt_daten.py`: N-S-Achse -> +x Sued, O-W -> +x Ost, +y immer links (rechtshaendig); `seiten_konvention` aus dem Kompass, wenn Platzhalter |
| bilder_holen: IndexError | Schwellen werden an vorhandenen Fotos kalibriert - neues Objekt hat keine | KALTSTART: Saat = groesste sich geometrisch bestaetigende Gruppe der Kategorie-Bilder (Kaufhaus 110 von 132; Innen/Fremd faellt heraus) |
| Wikimedia HTTP 429 (24 Bilder) | kein Warten | `lade_bild`: Retry-After / 5-80 s Backoff |
| einsortieren: Saat faellt durchs Inlier-Gate, Fotos ohne Seite in keinem Netz | Martinstor-Seitentrennung | Saat passiert; `sfm.netz_ohne_seite` = gemeinsames Netz (nicht symmetrische Objekte) |
| nullstart: masse.json/fassade.json fehlen | Referenz setzte Handwerte voraus | leeres Geruest, keine erfundenen Werte |
| Ausrichtung braucht LoD2-Eckpicks (B7) | Handpicks | **`sfm_lod2_ausrichten.py`**: Lot aus Kameraebene, Grobsuche an Wandlinien ALLER LoD2-Gebaeude (Nachbarfassaden machen es eindeutig), Fein Punkt-zu-Flaeche LoD2+DGM1 in SfM-Einheiten (massstabsneutral; in Metern kollabiert der Massstab), Guete = Inlier x Abdeckung der eigenen Objektwand, Wolkenmitte <= 20 m vom Objekt, Kamerahoehe 1,6 +- 1 m robust (ANNAHME). Kaufhaus: Abdeckung 40 % (naechste Loesung 3 %), Kameras Median 1,59 m, Fassade/Erker auf LoD2 (Sichtprobe Front + Quer). nullstart waehlt das Werkzeug automatisch (Picks vorhanden -> alt). |
Martinstor-Regression nach allen Aenderungen: identisch.

# Maßprüfung Martinstor – Nachweis gegen amtliche Laserdaten

Stand 31.10.2026, Modell `modelle/stl/martinstor_v4_1-87.stl` (Generator `modelle/martinstor_v4_gen.py`).

## Was bewiesen ist (und womit)

**Referenz:** Digitales Oberflächenmodell DOM1 + Geländemodell DGM1 des Landesamts für Geoinformation BW (LiDAR, Aufnahme 2017,
Raster 1 m, Höhengenauigkeit 0,15 m, Datenlizenz Deutschland – Namensnennung 2.0, `opengeodata.lgl-bw.de`).
Reproduzierbar mit `python tools/masspruefung_daten.py` (lädt beide Kacheln, schreibt das 60×60-m-Fenster).

**Gegenprobe der Methode:** Dieselben Daten ergeben für das Freiburger Münster 116,6 m über Gelände, amtlich sind 116 m.
Dünne Turmspitzen gehen also nicht verloren.

| Größe | Laser | Modell | Befund |
|---|---|---|---|
| Turmhöhe (Spitze über Gelände) | 332,77 − 277,97 = **54,80 m** | **54,80 m** (STL 629,9 mm × 87 / 1000) | stimmt auf 1 cm |
| Fläche über 20 / 24 / 28 m (Schaft) | 129 / 126 / 121 m² | 138 / 138 / 138 m² | +7 / +10 / +14 % |
| Fläche über 32 m (Zinnenkranz, Erker) | 97 m² | 114 m² | +18 % |
| Fläche über 35 m | 77 m² | 104 m² | **+35 %, nicht gelöst** |
| Fläche über 38 / 40 / 42 / 44 m (Glockenstock, Dach) | 62 / 43 / 28 / 20 m² | 62 / 44 / 26 / 20 m² | 0 / +2 / −7 / 0 % |
| Fläche über 46 / 48 / 50 m (Dachreiter) | 16 / 8 / 6 m² | 18 / 8 / 6 m² | +12 / 0 / 0 % |
| Nadel über 52 m | 4 m² | 2 m² | Nadel dünner als 1 Zelle, nicht auflösbar |

Vollständige Tabelle (Gesamtfläche je Höhenschwelle im 9-m-Umkreis, gleiches 1-m-Raster): `python tools/masspruefung_tabelle.py`.
Mittlere Flächenabweichung über alle 13 Höhenstufen: **12 %**, Median **7 %**.

## Was damit **widerlegt** ist
Mehrere Textquellen nennen **60–66 m** (Bauforschung BW „65 m“, Schwarzwaldportal „66 m“, ein Absatz derselben PDF „60 m“).
Der Laser misst **54,8 m**. Die 65–66 m stimmen nicht für die heutige Spitze. Die Grundfläche „10 × 11 m“ der Quellen stimmt dagegen:
der Schaft misst im Laser (Mindestrechteck, 24–28 m) 12,1/11,7 × 10,7 m einschließlich Randzellen.
Auch OSM (Spitze 53 m) liegt näher als die Texte.

## Grenzen (ehrlich)
1. Das Raster ist 1 m. Jede Breite ist daher nur auf etwa ±1 m bewiesen, jede Fläche auf etwa ±15 % (Drehung/Phase der Zellen ändern die Zählung).
2. Die Draufsicht sieht nur die **höchste Fläche je Zelle**. Torbogen, Uhr (Ø, Höhe), Fenster, Sockelaufweitung und alles unter Vordächern bleiben
   damit **unbewiesen**; dort gilt nur der Fotovergleich (±10 %, Annahme Torbogenbreite 6,6 m).
3. Bei 35 m liegt das Modell +35 % über dem Laser (3 Randzellen). Vermutlich ist Kragdach-/Dachtraufe etwas anders geformt; mit 1-m-Daten nicht zu klären.
4. Nicht geprüft ist ein Probedruck.

## Gefundener Hauptfehler und Korrektur
Das frühere Modell (54,0 m) hatte die richtige Höhe, aber falsche **Binnenhöhen**: Zinnenkrone 34–35 m (Laser ≈ 31,5 m), Glockenstock-Oberkante 39,8 m (≈ 35,5 m),
Dachfirst 49 m (≈ 46 m), Erkerkörper 37 m (≈ 32,7 m), Erkerkegel-Spitze 47 m (≈ 39,7 m), Dachreiter zu kurz (5 m statt ≈ 9 m), Schaft 1–2 m zu breit.
Korrigiert in v4 (Eintrag 12 im Lernjournal).

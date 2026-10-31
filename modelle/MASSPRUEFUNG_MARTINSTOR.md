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
| Turmhöhe (Spitze über Gelände) | 332,77 − 277,97 = **54,80 m** | **54,80 m** (STL 629,9 mm ÷ 87 × 1000/1000) | stimmt auf 1 cm |
| Schaft-Querschnitt 20–28 m (Raster-Fläche) | 121–129 m² | 138 m² | +7 … +14 % |
| Glockenstock + Dach 38–50 m | 62 / 43 / 28 / 20 / 16 / 8 / 6 m² (bei 38/40/42/44/46/48/50 m) | 64 / 46 / 26 / 18 / 18 / 8 / 6 m² | −10 … +12 % |
| Dachreiter-Nadel (>52 m) | 4 m² | 2 m² | Nadel dünner als 1 Zelle, nicht auflösbar |
| Zone 32–35 m (Zinnen, Kragdach, Erker) | 97 / 77 m² | 136 / 102 m² | **+32 … +40 %, nicht gelöst** |

Vollständige Tabelle (Gesamtfläche je Höhenschwelle im 9-m-Umkreis, gleiches 1-m-Raster): `python tools/masspruefung_tabelle.py`.
Mittlere Flächenabweichung über alle 13 Höhenstufen: **15 %**, Median **10 %**.

## Was damit **widerlegt** ist
Mehrere Textquellen nennen **60–66 m** (Bauforschung BW „65 m“, Schwarzwaldportal „66 m“, ein Absatz derselben PDF „60 m“).
Der Laser misst **54,8 m**. Die 65–66 m stimmen nicht für die heutige Spitze. Die Grundfläche „10 × 11 m“ der Quellen stimmt dagegen:
der Schaft misst im Laser (Mindestrechteck, 24–28 m) 12,1/11,7 × 10,7 m einschließlich Randzellen.
Auch OSM (Spitze 53 m) liegt näher als die Texte.

## Grenzen (ehrlich)
1. Das Raster ist 1 m. Jede Breite ist daher nur auf etwa ±1 m bewiesen, jede Fläche auf etwa ±15 % (Drehung/Phase der Zellen ändern die Zählung).
2. Die Draufsicht sieht nur die **höchste Fläche je Zelle**. Torbogen, Uhr (Ø, Höhe), Fenster, Sockelaufweitung und alles unter Vordächern bleiben
   damit **unbewiesen**; dort gilt nur der Fotovergleich (±10 %, Annahme Torbogenbreite 6,6 m).
3. Zone 32–35 m weicht um bis zu 40 % ab. Vermutlich ist die Zinnen-/Wehrgang-Geometrie anders (Wehrgang, Kragdachform); mit 1-m-Daten nicht zu klären.
4. Nicht geprüft ist ein Probedruck.

## Gefundener Hauptfehler und Korrektur
Das frühere Modell (54,0 m) hatte die richtige Höhe, aber falsche **Binnenhöhen**: Glockenstock-Oberkante 39,8 m (Laser ≈ 36–37 m),
Dachfirst 49 m (≈ 46 m), Erkerkörper 37 m (≈ 33–34 m), Dachreiter zu kurz (5 m statt ≈ 9 m), Schaft 1–2 m zu breit.
Korrigiert in v4 (Eintrag 12 im Lernjournal).

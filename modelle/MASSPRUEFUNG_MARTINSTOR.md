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


## Teil 2: von oben unsichtbare Maße – Foto-Verhältnismessung gegen die laservermessene Fassade
Was der Laser nicht sieht (Torbogen, Uhr, Wappenschild), wird als **Verhältnis zur Fassadenbreite auf gleicher Höhe** an zwei unabhängigen Fotos
(`daten/martinstor/fotos/030…7999`, `042…Martinstor_1`) gemessen, mit Gitter in Originalpixeln abgelesen. Verhältnisse in einer Ebene auf gleicher
Bildhöhe sind gegen Kamerakippung robust; die Fassadenbreite (≈ 11,5 m) stammt aus dem Laser (Schaft 11,7 m inkl. Randzelle).

| Merkmal | Foto 030 | Foto 042 | Mittel | Meter (×11,5 m) | im Modell |
|---|---|---|---|---|---|
| Zifferblatt-Ø / Fassade | 204/587 = 0,35 | 142/365 = 0,39 | 0,37 | **4,2 m** | 4,2 m (r 2,1) |
| Durchfahrt (Öffnung) / Fassade am Fuß | 347/833 = 0,42 | 185/475 = 0,39 | 0,405 | **4,7 m** | 4,7 m |
| Wappenschild-Breite / Fassade | – | 65/440 = 0,15 | 0,15 | **1,7 m** (Höhe ≈ 2,3 m) | 1,7 × 2,3 m |

Unsicherheit je Messung ≈ ±8 % (Ablesefehler ±5 px, leichte Schrägsicht ≈ ±5 %), beide Fotos weichen bis 10 % voneinander ab.
**Korrektur:** Frühere Werte (Torbogen 6,0 → 6,6 m, Adler 2,8 × 3,2 m, Uhr Ø 4,6 m) beruhten auf einem Augenvergleich und auf einer Annahme (Bogen ↔ Uhr), also
zirkulär; sie waren 20–60 % zu groß. Das ist der eigentliche Fund dieses Teils.

## Teil 3: Höhenlage der Uhr (lokaler Maßstab über das kreisrunde Zifferblatt)
Foto 042 (Originalpixel, Gitter 20 px): Zifferblatt 158 px breit × 139 px hoch → senkrechte Stauchung 0,88 (Kamera blickt nach oben).
Fassadenbreite auf Uhrhöhe 406 px = 11,5 m → waagrecht 35,3 px/m, senkrecht 35,3 × 0,88 = 31,1 px/m.
Uhrmitte (950 px) bis Gesimsunterkante (≈ 840 px) = 110 px → **3,5 m**; Uhrmitte bis Rahmenunterkante (1033 px) = 83 px → **2,7 m**.
Modell: Uhrmitte 26,9 m, Gesimsunterkante 30,05 m → **3,15 m**; Rahmenunterkante 26,9 − 3,0 = 23,9 → **3,0 m**. Abweichung ≤ 0,4 m (≈ 12 %).
Die Höhe des Gesimses selbst stützt der Laser (Zinnenkrone ≈ 31–32 m). Damit ist die Uhrlage **relativ zum Laser-Gesims** auf ±0,5 m belegt.

Verworfen: Kamerabestimmung (PnP) aus Spitze, Dachbällchen und Erkerspitzen mit EXIF-Brennweite (Pentax Optio 50L, 5,4 mm → 1559 px).
Alle Anker liegen über 39 m, nach unten ist die Lösung schlecht bestimmt (freie Kamerahöhe 13,8 m, bei realer Augenhöhe 31 px Restfehler, Uhr 256 px daneben).

## Teil 4: Gegenprobe mit dem amtlichen 3D-Gebäudemodell (LoD2, Gebäude DEBW_001000hPLcn)
Quelle: LGL BW `LoD2_32_413_5316_2_bw.zip` (Stand ALKIS 2025). Geometrie, nicht Raster: 68-Punkt-Grundriss, 68 Wand- und 4 Dachflächen.

| Größe | LoD2 | Modell | Befund |
|---|---|---|---|
| Grundrissfläche | 115,1 m² (Mindestrechteck 11,9 × 11,5 m, 15,6° gedreht) | ≈ 111 m² (Fuß 9,8 × 11,3 m) | −4 % |
| Wandoberkante | 36,5–37,2 m über Gelände | Glockenstock-Oberkante 35,5 m | LoD2 verallgemeinert (Traufe der Dachfläche) |
| Dachfirst | 45,0 m, Flächen 57–60° | 46,2 m | **+1,2 m, ungeklärt** |

Versuch, den First auf 45,0 m zu senken: Laser-Abweichung steigt (Median 7 → 10 %, Stufen 40–48 m bis −40 %). Der Laser ist eine Messung, das LoD2 eine Modellierung aus Dachebenen, die den Dachreiter und das Dachreiter-Podest ausspart. Die Änderung wurde **verworfen**.
Offener Widerspruch: LoD2 45,0 m gegen Laser-Fit 46,2 m am Dachfirst (1,2 m).

## Was damit **widerlegt** ist
Mehrere Textquellen nennen **60–66 m** (Bauforschung BW „65 m“, Schwarzwaldportal „66 m“, ein Absatz derselben PDF „60 m“).
Der Laser misst **54,8 m**. Die 65–66 m stimmen nicht für die heutige Spitze. Die Grundfläche „10 × 11 m“ der Quellen stimmt dagegen:
der Schaft misst im Laser (Mindestrechteck, 24–28 m) 12,1/11,7 × 10,7 m einschließlich Randzellen.
Auch OSM (Spitze 53 m) liegt näher als die Texte.

## Grenzen (ehrlich)
1. Das Raster ist 1 m. Jede Breite ist daher nur auf etwa ±1 m bewiesen, jede Fläche auf etwa ±15 % (Drehung/Phase der Zellen ändern die Zählung).
2. Die Draufsicht sieht nur die **höchste Fläche je Zelle**. Torbogen, Uhr und Schild sind deshalb nur über Teil 2 (Fotoverhältnis, ±10 %) belegt.
   Die Uhrlage ist relativ zum Gesims belegt (Teil 3, ±0,5 m). **Torbogenscheitel (6,55 m), Schild, Fenster und Sockelaufweitung** sind **nicht belegt** (nur Fotovergleich ±10 %).
3. Bei 35 m liegt das Modell +22 … +35 % über dem Laser (1–2 Randzellen). Eine Parametersuche über Glockenstock-, Erkerkörper- und Traufmaß (8 Varianten) fand keine bessere Lage; der Sprung zwischen 22 und 35 % liegt im Rauschen der Methode (±15 % durch Rasterphase/Drehung). Kein belegter Fehler.
4. Nicht geprüft ist ein Probedruck.

## Gefundener Hauptfehler und Korrektur
Das frühere Modell (54,0 m) hatte die richtige Höhe, aber falsche **Binnenhöhen**: Zinnenkrone 34–35 m (Laser ≈ 31,5 m), Glockenstock-Oberkante 39,8 m (≈ 35,5 m),
Dachfirst 49 m (≈ 46 m), Erkerkörper 37 m (≈ 32,7 m), Erkerkegel-Spitze 47 m (≈ 39,7 m), Dachreiter zu kurz (5 m statt ≈ 9 m), Schaft 1–2 m zu breit.
Korrigiert in v4 (Eintrag 12 im Lernjournal).

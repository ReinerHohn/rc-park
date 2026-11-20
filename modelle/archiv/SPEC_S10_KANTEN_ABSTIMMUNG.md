# SPEC S10 - Vier Kanten-Pipelines + Abstimmung (Nutzer 6.11. ~07:20)

Nutzer: "verschiedene Ansaetze durchgehen, mehrere Pipelines, Ergebnisse vergleichen; 4 Pipelines mit 4 Ansaetzen, dann abstimmen, was eine Kante ist". Dazu: Wolke besser filtern, mit Farben experimentieren ("was ich als Mensch kann, musst du auch koennen").
Objekt: kaufhaus_null5. Generisch, keine Objektnamen/Festwerte im Code. Start NACH S9 (ein GPU-Job, 15 GB RAM).

## Teil A - Vier Kanten-Pipelines je Foto (gleiche Ausgabe: Kantenwahrscheinlichkeit 0..1 je Pixel, Bild unverzerrt)
P1 Helligkeit: mehrstufiges Canny (wie foto_diff mehrstufig).
P2 Farbe: Gradienten in Lab und HSV (Farbton gewichtet nach Saettigung), Non-Maximum-Suppression; trennt rot/gold bei gleicher Helligkeit.
P3 Gelernt: DexiNed oder TEED oder PiDiNet (Lizenz pruefen, permissiv bevorzugt; GPU), unterdrueckt Textur (Ziegel, Fugen).
P4 Segmentgrenzen: Grenzen von Bildsegmenten (SAM/SAM2 automatisch oder Mask2Former-Fassade; Lizenz pruefen) = Objekt-/Materialgrenzen.

## Teil B - Abstimmung
- Je Foto: Kante, wenn >= k von 4 Pipelines zustimmen (k = 2,3,4 vergleichen); Gewichte NICHT am Pruefbild tunen.
- Ueber Fotos: 3D-Kante (tools/kanten_3d.py) nur, wenn in >= 3 Fotos bei unterschiedlichem Licht/Blickwinkel bestaetigt (Schatten wandern, echte Kanten bleiben).
- Bewertung ohne Handarbeit: (1) Synth-Szene mit bekannten Kanten (gerendert, mit Textur, Schatten, Farbgrenzen gleicher Helligkeit): Praezision/Vollstaendigkeit je Pipeline und je Abstimmung. (2) Kreuz-Ansicht: Kanten aus Trainingsfotos triangulieren, in die 6 Holdout-Fotos projizieren, Anteil bestaetigt (Praezision) und Anteil Holdout-Kanten erklaert (Vollstaendigkeit); Tabelle je Pipeline und k.

## Teil B2 - Entscheidung starkes Modell 6.11. ~07:40 nach Recherche: "quer rueber" statt getrennt abstimmen
Recherche: NEF (CVPR 2023, Kantendichtefeld aus 2D-Kantenkarten, Bezier-Kurven) und EMAP (CVPR 2024 "3D Neural Edge Reconstruction", vorzeichenloses Abstandsfeld aus Mehransichts-Kantenkarten, extrahiert Geraden UND Kurven, verbessert auch Flaechenrekonstruktion). Beide brauchen keine Kantenzuordnung zwischen Fotos.
Entscheidung: HAUPTWEG = alle vier Pipelines liefern weiche Kantenkarten je Foto (gemittelt, nicht hart abgestimmt) -> gemeinsames 3D-Kantenfeld ueber ALLE kalibrierten Fotos (EMAP-Prinzip; Code/Lizenz pruefen: neural-edge-map.github.io; sonst eigene Umsetzung als Voxel-/Hash-Feld mit Rendering-Verlust auf der GPU) -> parametrische Kurven/Geraden (Boegen als Kurven!) -> Zwangslinien fuer S9/S8.
Die harte Abstimmung je Foto (Teil B) bleibt nur als Vergleichsbasis.
Lehren eingearbeitet: (1) LSD findet nur Geraden -> Boegen fehlten (S8); (2) harte Einzelentscheidungen kippen (Ebenen-Zellen S8) -> weiche Evidenz bis zuletzt; (3) Bewertung nur mit fairem Mass kosten_lr auf Holdout, nicht rot+gelb; (4) Schwellen nie am Pruefbild tunen, zweite Synth-Szene als Gegenprobe.

## Teil C - Wolke filtern (je Variante gleiche Kennzahlen)
F0 heutige Wolke. F1 strengere COLMAP-Fusion (min_num_pixels hoeher, max_reproj_error/max_depth_error/max_normal_error enger). F2 Masken vor Fusion (Himmel, Personen, Fahrzeuge, Vegetation, Stände, Nachbarhaeuser; vorhandene himmelsmaske/video_masken.py nutzen). F3 Joint-Bilateral (Lage+Farbe) bzw. kantenerhaltendes Glaetten auf F1/F2.
Kennzahlen: Rauschen auf Wandebenen (RANSAC-Rest p50/p90), Kantenschaerfe (Punktdichte-Abfall quer zu 3D-Kanten), Abdeckung je Fassade, Ausreisser vor der Fassade; danach Carving mit bester Variante -> kosten_lr Holdout gegen carv_kh3.

## Betrieb
tools/job_start.sh, nur ein GPU-Job, Platztor; Ausgabe /media/oem/scan/rc-park_null/s10/; Lizenzen in modelle/LIZENZ_WERKZEUGE.md; keine Commits; Bericht als Tabelle (Pipelines x Kennzahlen, Filter x Kennzahlen) in STAND_2026-11-06.md, Register, versuche.jsonl; Vergleichsbild Foto 004 Bogenrand: 4 Pipelines + Abstimmung nebeneinander, SELBST ansehen.
